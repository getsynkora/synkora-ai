"""Slack webhook controller for Event Mode."""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_db, get_async_session_factory
from ..models.slack_bot import SlackBot
from ..services.slack.slack_event_service import SlackEventService

logger = logging.getLogger(__name__)

# Public router - no authentication required (Slack sends requests here)
public_router = APIRouter(prefix="/api/webhooks/slack", tags=["slack-webhooks"])

# Rate limiting tracking (simple in-memory, production should use Redis)
_rate_limit_cache: dict[str, list[float]] = {}


def _check_rate_limit(bot_id: str, max_per_minute: int = 60, max_per_hour: int = 1000) -> bool:
    """Check if the bot is within rate limits.

    Args:
        bot_id: Bot ID to check
        max_per_minute: Maximum requests per minute
        max_per_hour: Maximum requests per hour

    Returns:
        True if within limits, False if rate limited
    """
    import time

    now = time.time()
    minute_ago = now - 60
    hour_ago = now - 3600

    if bot_id not in _rate_limit_cache:
        _rate_limit_cache[bot_id] = []

    # Clean old entries
    _rate_limit_cache[bot_id] = [t for t in _rate_limit_cache[bot_id] if t > hour_ago]

    # Count recent requests
    requests_per_minute = sum(1 for t in _rate_limit_cache[bot_id] if t > minute_ago)
    requests_per_hour = len(_rate_limit_cache[bot_id])

    if requests_per_minute >= max_per_minute or requests_per_hour >= max_per_hour:
        logger.warning(f"Rate limit exceeded for bot {bot_id}: {requests_per_minute}/min, {requests_per_hour}/hour")
        return False

    # Record this request
    _rate_limit_cache[bot_id].append(now)
    return True


async def _process_event_background(
    bot_id: UUID,
    payload: dict,
) -> None:
    """Process Slack event in background.

    Args:
        bot_id: Bot ID
        payload: Event payload
    """
    from ..services.agents.agent_manager import AgentManager

    async with get_async_session_factory()() as db:
        try:
            slack_bot = await db.get(SlackBot, bot_id)
            if not slack_bot:
                logger.error(f"Slack bot {bot_id} not found for background processing")
                return

            # Create shared agent manager for reuse
            agent_manager = AgentManager()
            event_service = SlackEventService(db, agent_manager)

            await event_service.process_event(slack_bot, payload)

        except Exception as e:
            logger.error(f"Error processing Slack event for bot {bot_id}: {e}")


async def _process_interaction_background(
    bot_id: UUID,
    payload: dict,
) -> None:
    """Process a Slack interactive component payload (e.g. button click) in background.

    Args:
        bot_id: Bot ID
        payload: Parsed interaction payload
    """
    async with get_async_session_factory()() as db:
        try:
            slack_bot = await db.get(SlackBot, bot_id)
            if not slack_bot:
                logger.error(f"Slack bot {bot_id} not found for interaction processing")
                return

            event_service = SlackEventService(db)
            await event_service.process_interaction(slack_bot, payload)

        except Exception as e:
            logger.error(f"Error processing Slack interaction for bot {bot_id}: {e}")


@public_router.post("/{bot_id}/events")
async def handle_slack_event(
    bot_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
    x_slack_request_timestamp: str = Header(None, alias="X-Slack-Request-Timestamp"),
    x_slack_signature: str = Header(None, alias="X-Slack-Signature"),
):
    """Handle incoming Slack webhook events.

    This endpoint handles:
    - URL verification challenge (immediate response)
    - Event callbacks (processed in background)

    Args:
        bot_id: Slack bot ID
        request: FastAPI request object
        background_tasks: Background task handler
        db: Async database session
        x_slack_request_timestamp: Slack timestamp header
        x_slack_signature: Slack signature header

    Returns:
        Challenge response for verification, or OK status for events
    """
    # Get raw body for signature verification
    body = await request.body()
    content_type = request.headers.get("content-type", "")

    # Get the bot
    slack_bot = await db.get(SlackBot, bot_id)
    if not slack_bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack bot not found")

    # Verify bot is active and using Event Mode
    if slack_bot.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack bot has been deleted")

    if not slack_bot.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Slack bot is not active")

    if not slack_bot.is_event_mode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This bot is configured for Socket Mode, not Event Mode",
        )

    # Check rate limits
    if not _check_rate_limit(str(bot_id)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    # Create event service
    event_service = SlackEventService(db)

    # Interactive components (button clicks) arrive as form-encoded payloads,
    # not JSON events.
    if content_type.startswith("application/x-www-form-urlencoded"):
        import json
        from urllib.parse import parse_qs

        form = parse_qs(body.decode("utf-8"))
        payload_values = form.get("payload")
        if not payload_values:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing payload field")

        if not event_service.verify_request(slack_bot, body, x_slack_request_timestamp, x_slack_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

        try:
            interaction_payload = json.loads(payload_values[0])
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid interaction payload")

        # Ack immediately (Slack requires a response within ~3 seconds); process in background.
        asyncio.create_task(_process_interaction_background(bot_id, interaction_payload))
        return JSONResponse(content={"status": "ok"})

    # Parse JSON payload (events)
    try:
        import json

        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")

    # Handle URL verification challenge (immediate response required)
    event_type = payload.get("type")
    if event_type == "url_verification":
        # Verify signature for URL verification too
        if not event_service.verify_request(slack_bot, body, x_slack_request_timestamp, x_slack_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

        response = await event_service.handle_url_verification(payload)
        return JSONResponse(content=response)

    # For event callbacks, verify signature
    if event_type == "event_callback":
        if not event_service.verify_request(slack_bot, body, x_slack_request_timestamp, x_slack_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

        # Process event in background (Slack requires response within 3 seconds)
        # Use asyncio.create_task for async background processing
        asyncio.create_task(_process_event_background(bot_id, payload))

        # Return immediately
        return JSONResponse(content={"status": "ok"})

    # Unknown event type
    logger.warning(f"Unknown Slack event type: {event_type}")
    return JSONResponse(content={"status": "ok"})


@public_router.get("/{bot_id}/health")
async def webhook_health_check(
    bot_id: UUID,
    db: AsyncSession = Depends(get_async_db),
):
    """Health check endpoint for the webhook.

    Args:
        bot_id: Slack bot ID
        db: Async database session

    Returns:
        Health status
    """
    slack_bot = await db.get(SlackBot, bot_id)
    if not slack_bot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slack bot not found")

    if not slack_bot.is_event_mode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This bot is not configured for Event Mode",
        )

    return {
        "status": "healthy",
        "bot_id": str(bot_id),
        "connection_mode": slack_bot.connection_mode,
        "is_active": slack_bot.is_active,
    }
