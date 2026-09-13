"""
Recall.ai Webhook Handler

Receives webhook events from Recall.ai for meeting bot status changes,
transcripts, and participant events.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.models.oauth_app import OAuthApp
from src.services.agents.security import decrypt_value
from src.services.performance.rate_limiter import get_rate_limiter
from src.services.recall.recall_service import RecallService

logger = logging.getLogger(__name__)

public_router = APIRouter()


# Status messages for user-friendly notifications
STATUS_MESSAGES = {
    "ready": "Meeting bot is ready and waiting to join.",
    "joining_call": "Meeting bot is joining the call...",
    "in_waiting_room": "Meeting bot is in the waiting room. Please admit the bot to start recording.",
    "in_call_not_recording": "Meeting bot has joined but is not recording yet.",
    "in_call_recording": "Meeting bot is now recording the meeting.",
    "call_ended": "The meeting has ended.",
    "done": "Meeting recording is complete! Transcript and recording are now available.",
    "fatal": "Meeting bot encountered an error and could not complete the recording.",
    "analysis_done": "Meeting analysis and processing is complete.",
}


def _get_status_message(status_code: str, bot_id: str) -> str:
    """Get a user-friendly status message."""
    base_message = STATUS_MESSAGES.get(status_code, f"Bot status: {status_code}")
    return f"[Bot {bot_id[:8]}...] {base_message}"


async def _store_meeting_notification(
    db: AsyncSession,
    agent_id: str,
    bot_id: str,
    event_type: str,
    status: str,
    message: str,
):
    """Store a meeting notification for the agent to retrieve."""
    try:
        from src.models.agent_notification import AgentNotification

        notification = AgentNotification(
            agent_id=agent_id,
            notification_type="recall_meeting",
            title=f"Meeting Update: {status}",
            message=message,
            metadata={
                "bot_id": bot_id,
                "event_type": event_type,
                "status": status,
            },
        )
        db.add(notification)
        await db.flush()
        logger.info(f"Stored meeting notification for agent {agent_id}: {event_type}")
    except ImportError:
        # AgentNotification model doesn't exist yet, just log
        logger.info(f"Meeting notification (no storage): agent={agent_id}, event={event_type}, status={status}")
    except Exception as e:
        logger.warning(f"Failed to store meeting notification: {e}")
        raise


# Recall webhook rate limiting uses the global Redis-backed RateLimiter for
# distributed, multi-instance correctness.  Higher limits than standard API
# endpoints because Recall.ai can emit many transcript events per meeting.
_RECALL_REQUESTS_PER_MINUTE = 120


async def _get_webhook_secret(db: AsyncSession) -> str | None:
    """Get Recall.ai webhook secret from OAuthApp config."""
    try:
        # Find any active Recall.ai OAuth app (webhook secret is shared across tenant)
        result = await db.execute(
            select(OAuthApp).filter(
                OAuthApp.provider.ilike("recall"),
                OAuthApp.is_active.is_(True),
            )
        )
        oauth_app = result.scalar_one_or_none()

        if not oauth_app:
            return None

        # Get webhook_secret from config JSON
        if oauth_app.config and isinstance(oauth_app.config, dict):
            secret = oauth_app.config.get("webhook_secret")
            if secret and secret.startswith("enc:"):
                secret = decrypt_value(secret)
            return secret

        return None

    except Exception as e:
        logger.error(f"Failed to get Recall webhook secret: {e}")
        return None


@public_router.post("/api/webhooks/recall")
async def receive_recall_webhook(request: Request, db: AsyncSession = Depends(get_async_db)):
    """
    Receive webhook events from Recall.ai.

    Events handled:
    - bot.status_change: Bot status updates (joining, recording, done)
    - transcript.data: Real-time transcript segments
    - transcript.partial_data: Partial/interim transcript updates
    - participant_events.join: Participant joined meeting
    - participant_events.leave: Participant left meeting
    """
    # Rate limit check — uses Redis-backed distributed rate limiter
    from src.utils.ip_utils import get_client_ip

    client_ip = get_client_ip(
        direct_ip=request.client.host if request.client else "unknown",
        forwarded_for=request.headers.get("x-forwarded-for"),
        real_ip=request.headers.get("x-real-ip"),
    )

    rate_limiter = get_rate_limiter()
    rate_result = await rate_limiter.check(
        key=f"recall_webhook:{client_ip}",
        max_requests=_RECALL_REQUESTS_PER_MINUTE,
        window=60,
    )
    if not rate_result.allowed:
        logger.warning(f"Rate limit exceeded for Recall webhook from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {_RECALL_REQUESTS_PER_MINUTE} requests per minute",
        )

    # Get request body
    try:
        payload = await request.body()
        if not payload:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty request body")

        event_data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    # Verify every webhook before processing
    webhook_secret = await _get_webhook_secret(db)
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook verification is unavailable")
    if not RecallService.verify_webhook_signature(payload, request.headers, webhook_secret):
        raise HTTPException(status_code=401, detail="Missing, invalid or expired webhook signature")

    # Unique receipt and all handler database writes commit together. Concurrent
    # deliveries wait on the unique key; a rolled-back attempt can be retried.
    import hashlib

    from sqlalchemy.dialects.postgresql import insert

    from src.models.recall_webhook_receipt import RecallWebhookReceipt

    message_id = request.headers.get("webhook-id") or request.headers.get("svix-id")
    event_key = hashlib.sha256((webhook_secret + ":" + message_id).encode()).hexdigest()

    # Extract event type
    event_type = event_data.get("event")
    bot_id = event_data.get("data", {}).get("bot", {}).get("id")

    # Routing must be covered by the signature, never by unsigned query parameters.
    agent_id = event_data.get("data", {}).get("bot", {}).get("metadata", {}).get("synkora_agent_id")

    logger.info(f"Received Recall webhook: event={event_type}, bot_id={bot_id}, agent_id={agent_id}")

    try:
        async with asyncio.timeout(60):
            receipt = await db.execute(
                insert(RecallWebhookReceipt)
                .values(event_key=event_key)
                .on_conflict_do_nothing(index_elements=["event_key"])
                .returning(RecallWebhookReceipt.event_key)
            )
            if receipt.scalar_one_or_none() is None:
                await db.rollback()
                return {"status": "duplicate"}
            if event_type == "bot.status_change":
                await _handle_bot_status_change(db, event_data, agent_id)
            elif event_type == "transcript.data":
                await _handle_transcript_data(db, event_data, agent_id)
            elif event_type == "transcript.partial_data":
                logger.debug(f"Received partial transcript for bot {bot_id}")
            elif event_type in ["participant_events.join", "participant_events.leave"]:
                await _handle_participant_event(db, event_data, agent_id)
            else:
                logger.info(f"Unhandled Recall event type: {event_type}")
            await db.commit()
    except BaseException as exc:
        await db.rollback()
        if isinstance(exc, asyncio.CancelledError):
            raise
        if not isinstance(exc, Exception):
            raise
        logger.error("Recall webhook processing failed", exc_info=True)
        raise HTTPException(503, "Webhook processing failed; please retry") from None

    return {"status": "ok", "event": event_type}


async def _handle_bot_status_change(db: AsyncSession, event_data: dict, agent_id: str | None):
    """Handle bot status change events."""
    data = event_data.get("data", {})
    bot_info = data.get("bot", {})
    status_info = data.get("status", {})

    bot_id = bot_info.get("id")
    status_code = status_info.get("code")
    status_message = status_info.get("message")

    logger.info(f"Bot {bot_id} status changed to: {status_code} - {status_message}")

    # Store notification for agent
    if agent_id:
        await _store_meeting_notification(
            db=db,
            agent_id=agent_id,
            bot_id=bot_id,
            event_type="status_change",
            status=status_code,
            message=_get_status_message(status_code, bot_id),
        )

    # When meeting is complete, trigger transcript retrieval notification
    if status_code == "done" and agent_id:
        logger.info(f"Meeting complete for bot {bot_id}. Notifying agent {agent_id}.")
        await _store_meeting_notification(
            db=db,
            agent_id=agent_id,
            bot_id=bot_id,
            event_type="meeting_complete",
            status="done",
            message=f"Meeting recording complete! Bot {bot_id} has finished recording. You can now retrieve the transcript and recording using the bot ID.",
        )


async def _handle_transcript_data(db: AsyncSession, event_data: dict, agent_id: str | None):
    """Handle real-time transcript data events."""
    data = event_data.get("data", {})
    transcript_data = data.get("data", {})
    participant = transcript_data.get("participant", {})
    words = transcript_data.get("words", [])

    if words:
        text = " ".join([w.get("text", "") for w in words])
        speaker = participant.get("name", "Unknown")
        logger.debug(f"Transcript segment: [{speaker}] {text[:100]}...")

    # For post-meeting processing, we don't need to store real-time segments
    # The full transcript will be fetched after the meeting is complete
    # This handler is here for future real-time voice agent implementation


async def _handle_participant_event(db: AsyncSession, event_data: dict, agent_id: str | None):
    """Handle participant join/leave events."""
    data = event_data.get("data", {})
    bot_info = data.get("bot", {})
    participant = data.get("participant", {})
    event_type = event_data.get("event", "")

    bot_id = bot_info.get("id", "unknown")
    participant_name = participant.get("name", "Unknown")
    action = "joined" if "join" in event_type else "left"

    logger.info(f"Participant {participant_name} {action} the meeting")

    # Store notification for agent
    if agent_id:
        await _store_meeting_notification(
            db=db,
            agent_id=agent_id,
            bot_id=bot_id,
            event_type=f"participant_{action}",
            status=action,
            message=f"Participant '{participant_name}' {action} the meeting.",
        )
