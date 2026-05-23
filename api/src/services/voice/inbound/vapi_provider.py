"""
Vapi.ai inbound call provider.

Handles three event types from Vapi:
  - call-started      → create PhoneCall + Conversation, return greeting
  - conversation-update → run agent, return text response
  - end-of-call-report  → persist transcript, update PhoneCall status
"""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.redis import get_redis_async
from src.models.agent import Agent
from src.models.conversation import Conversation, ConversationStatus
from src.models.message import Message, MessageRole
from src.models.phone_call import PhoneCall, PhoneCallStatus
from src.models.phone_number import PhoneNumber
from src.services.voice.inbound.base_provider import BaseInboundCallProvider

logger = logging.getLogger(__name__)

# Redis key pattern: phone:call:{vapi_call_id} → JSON session info
_CALL_KEY_PREFIX = "phone:call:"
_DEFAULT_MAX_DURATION = 300


class VapiProvider(BaseInboundCallProvider):
    """Handles Vapi.ai webhook events for inbound calls."""

    def get_webhook_url(self, base_url: str) -> str:
        return f"{base_url}/api/v1/phone/webhook/vapi"

    def verify_signature(self, raw_body: bytes, headers: dict, secret: str) -> bool:
        """
        Vapi uses a simple shared secret in the x-vapi-secret header.
        Compare using constant-time digest to prevent timing attacks.
        """
        provided = headers.get("x-vapi-secret", "")
        if not provided or not secret:
            return False
        return self._constant_time_compare(provided, secret)

    async def handle_webhook(self, payload: dict, headers: dict, db: AsyncSession) -> dict:
        event_type = payload.get("message", {}).get("type") or payload.get("type", "")

        if event_type == "call-started":
            return await self._handle_call_started(payload, db)
        elif event_type == "conversation-update":
            return await self._handle_conversation_update(payload, db)
        elif event_type == "end-of-call-report":
            return await self._handle_end_of_call_report(payload, db)
        else:
            logger.debug(f"Vapi: unhandled event type '{event_type}'")
            return {}

    # ------------------------------------------------------------------
    # call-started
    # ------------------------------------------------------------------

    async def _handle_call_started(self, payload: dict, db: AsyncSession) -> dict:
        call_data = payload.get("message", payload)
        vapi_call_id = call_data.get("call", {}).get("id") or call_data.get("callId", "")
        caller_number = call_data.get("call", {}).get("customer", {}).get("number", "")
        phone_number_str = call_data.get("call", {}).get("phoneNumber", {}).get("number", "")

        # Look up the PhoneNumber record to resolve agent + tenant
        phone_record = await self._find_phone_number(phone_number_str, db)
        if not phone_record:
            logger.warning(f"Vapi call-started: no PhoneNumber found for '{phone_number_str}'")
            return {}

        agent = await db.get(Agent, phone_record.agent_id)
        if not agent or not agent.is_active:
            logger.warning(f"Vapi call-started: agent {phone_record.agent_id} not found or inactive")
            return {}

        phone_config = agent.phone_config or {}
        greeting = phone_config.get("greeting", "Hi, how can I help you today?")
        max_duration = phone_config.get("max_duration_seconds", _DEFAULT_MAX_DURATION)

        # Create Conversation
        conversation = Conversation(
            app_id=None,
            agent_id=agent.id,
            account_id=None,
            name=f"Call from {caller_number or 'unknown'}",
            status=ConversationStatus.ACTIVE,
        )
        db.add(conversation)
        await db.flush()

        # Create PhoneCall
        phone_call = PhoneCall(
            tenant_id=phone_record.tenant_id,
            agent_id=agent.id,
            phone_number_id=phone_record.id,
            conversation_id=conversation.id,
            provider="vapi",
            provider_call_id=vapi_call_id,
            caller_number=caller_number,
            status=PhoneCallStatus.ACTIVE,
            started_at=datetime.now(UTC),
            answered_at=datetime.now(UTC),
        )
        db.add(phone_call)
        await db.commit()

        # Store session in Redis
        redis = get_redis_async()
        session_data = {
            "conversation_id": str(conversation.id),
            "agent_id": str(agent.id),
            "tenant_id": str(phone_record.tenant_id),
            "phone_number_id": str(phone_record.id),
            "phone_call_id": str(phone_call.id),
        }
        await redis.setex(
            f"{_CALL_KEY_PREFIX}{vapi_call_id}",
            max_duration,
            json.dumps(session_data),
        )

        logger.info(f"Vapi call-started: call={vapi_call_id}, agent={agent.agent_name}")
        return {"assistant": {"firstMessage": greeting}}

    # ------------------------------------------------------------------
    # conversation-update
    # ------------------------------------------------------------------

    async def _handle_conversation_update(self, payload: dict, db: AsyncSession) -> dict:
        call_data = payload.get("message", payload)
        vapi_call_id = call_data.get("call", {}).get("id") or call_data.get("callId", "")
        transcript = call_data.get("transcript", [])

        # Look up session from Redis
        redis = get_redis_async()
        session_raw = await redis.get(f"{_CALL_KEY_PREFIX}{vapi_call_id}")
        if not session_raw:
            logger.warning(f"Vapi conversation-update: no session for call_id={vapi_call_id}")
            return {}

        session = json.loads(session_raw)
        conversation_id = UUID(session["conversation_id"])
        agent_id = UUID(session["agent_id"])
        tenant_id = UUID(session["tenant_id"])

        # Extract latest user utterance from transcript
        user_text = ""
        for turn in reversed(transcript):
            if turn.get("role") == "user":
                user_text = turn.get("transcript", "").strip()
                break

        if not user_text:
            logger.debug(f"Vapi conversation-update: no user text in transcript for call={vapi_call_id}")
            return {}

        # Get agent
        agent = await db.get(Agent, agent_id)
        if not agent:
            logger.error(f"Vapi conversation-update: agent {agent_id} not found")
            return {}

        # Build conversation history
        from src.services.conversation_service import ConversationService

        conversation_history = await ConversationService.get_conversation_history_cached(
            db=db,
            conversation_id=conversation_id,
            limit=30,
        )

        # Run agent pipeline
        from src.services.agents.agent_loader_service import AgentLoaderService
        from src.services.agents.agent_manager import AgentManager
        from src.services.agents.chat_service import ChatService
        from src.services.agents.chat_stream_service import ChatStreamService

        chat_stream = ChatStreamService(
            agent_loader=AgentLoaderService(AgentManager()),
            chat_service=ChatService(),
        )

        chunks = []
        async for event_data in chat_stream.stream_agent_response(
            agent_name=agent.slug,
            message=user_text,
            conversation_history=conversation_history,
            conversation_id=str(conversation_id),
            attachments=None,
            llm_config_id=None,
            db=db,
            user_id=None,
            tenant_id=tenant_id,
            trigger_source="phone",
            trigger_detail=vapi_call_id,
        ):
            if event_data.startswith("data: "):
                try:
                    evt = json.loads(event_data[6:])
                    if evt.get("type") == "chunk":
                        chunks.append(evt.get("content", ""))
                except Exception:
                    pass

        agent_response = "".join(chunks)
        logger.info(f"Vapi conversation-update: call={vapi_call_id}, response_len={len(agent_response)}")
        return {"messageResponse": {"role": "assistant", "content": agent_response}}

    # ------------------------------------------------------------------
    # end-of-call-report
    # ------------------------------------------------------------------

    async def _handle_end_of_call_report(self, payload: dict, db: AsyncSession) -> dict:
        call_data = payload.get("message", payload)
        vapi_call_id = call_data.get("call", {}).get("id") or call_data.get("callId", "")
        ended_reason = call_data.get("endedReason", "")
        duration_seconds = call_data.get("durationSeconds") or call_data.get("call", {}).get("duration")
        recording_url = call_data.get("recordingUrl") or call_data.get("call", {}).get("recordingUrl")
        artifact = call_data.get("artifact", {})
        full_transcript = artifact.get("transcript") or call_data.get("transcript", [])
        cost = call_data.get("cost")

        # Look up the PhoneCall record
        result = await db.execute(select(PhoneCall).where(PhoneCall.provider_call_id == vapi_call_id))
        phone_call = result.scalar_one_or_none()
        if not phone_call:
            logger.warning(f"Vapi end-of-call-report: no PhoneCall for vapi_call_id={vapi_call_id}")
            return {}

        # Update PhoneCall
        phone_call.status = PhoneCallStatus.COMPLETED
        phone_call.ended_at = datetime.now(UTC)
        if duration_seconds is not None:
            phone_call.duration_seconds = int(duration_seconds)
        if recording_url:
            phone_call.recording_url = recording_url
        if cost is not None:
            phone_call.cost_cents = int(float(cost) * 100)
        phone_call.call_metadata = {"ended_reason": ended_reason}

        # Save full transcript as messages if conversation exists
        _role_map = {"user": MessageRole.USER, "assistant": MessageRole.ASSISTANT}
        if phone_call.conversation_id and isinstance(full_transcript, list):
            for turn in full_transcript:
                role_str = turn.get("role", "")
                text = turn.get("transcript") or turn.get("content", "")
                role = _role_map.get(role_str)
                if role and text:
                    msg = Message(
                        conversation_id=phone_call.conversation_id,
                        role=role,
                        content=text,
                        message_metadata={"source": "phone_transcript", "vapi_call_id": vapi_call_id},
                    )
                    db.add(msg)

        await db.commit()

        # Clear Redis session
        redis = get_redis_async()
        await redis.delete(f"{_CALL_KEY_PREFIX}{vapi_call_id}")

        logger.info(f"Vapi end-of-call-report: call={vapi_call_id}, duration={duration_seconds}s")
        return {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _find_phone_number(self, number: str, db: AsyncSession) -> PhoneNumber | None:
        """Look up PhoneNumber by E.164 number string."""
        if not number:
            return None
        result = await db.execute(
            select(PhoneNumber).where(PhoneNumber.phone_number == number, PhoneNumber.is_active.is_(True))
        )
        return result.scalar_one_or_none()
