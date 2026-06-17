"""WhatsApp Business API webhook service."""

import hmac
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.agent import Agent
from ...models.conversation import Conversation, ConversationStatus
from ...models.message import Message
from ...models.whatsapp_bot import WhatsAppBot, WhatsAppConversation
from ...services.agents.security import decrypt_value

logger = logging.getLogger(__name__)

WHATSAPP_API_VERSION = "v21.0"
WHATSAPP_API_URL = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}"


class WhatsAppWebhookService:
    """Service for handling WhatsApp webhooks and sending messages."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def verify_webhook(self, mode: str, token: str, challenge: str, bot_id: UUID) -> str | None:
        """
        Verify WhatsApp webhook.

        Args:
            mode: Verification mode (should be 'subscribe')
            token: Verification token from WhatsApp
            challenge: Challenge string to return
            bot_id: WhatsApp bot ID

        Returns:
            Challenge string if verified, None otherwise
        """
        try:
            bot = await self.db_session.get(WhatsAppBot, bot_id)
            if not bot:
                logger.warning(f"WhatsApp bot {bot_id} not found")
                return None

            # SECURITY: Use constant-time comparison to prevent timing attacks
            if mode == "subscribe" and hmac.compare_digest(token, bot.verify_token):
                logger.info(f"WhatsApp webhook verified for bot {bot_id}")
                return challenge

            logger.warning(f"WhatsApp webhook verification failed for bot {bot_id}")
            return None

        except Exception as e:
            logger.error(f"Error verifying WhatsApp webhook: {str(e)}")
            return None

    async def handle_webhook(self, bot_id: UUID, payload: dict):
        """
        Handle incoming WhatsApp webhook.

        Args:
            bot_id: WhatsApp bot ID
            payload: Webhook payload from WhatsApp
        """
        try:
            bot = await self.db_session.get(WhatsAppBot, bot_id)
            if not bot or not bot.is_active:
                logger.warning(f"WhatsApp bot {bot_id} not found or inactive")
                return

            # Parse WhatsApp webhook payload
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])

            for message in messages:
                await self._process_message(bot, message, value)

        except Exception as e:
            logger.error(f"Error handling WhatsApp webhook: {str(e)}")
            await self.db_session.rollback()

    async def _process_message(self, bot: WhatsAppBot, message: dict, value: dict):
        """
        Process individual WhatsApp message.

        Args:
            bot: WhatsAppBot instance
            message: Message data from webhook
            value: Value object containing context
        """
        try:
            message_type = message.get("type")
            from_number = message.get("from")
            message_id = message.get("id")
            message.get("timestamp")

            # Extract message text based on type
            text = ""
            if message_type == "text":
                text = message.get("text", {}).get("body", "")
            elif message_type == "interactive":
                interactive = message.get("interactive", {})
                if "button_reply" in interactive:
                    text = interactive["button_reply"].get("title", "")
                elif "list_reply" in interactive:
                    text = interactive["list_reply"].get("title", "")

            if not text:
                logger.debug(f"No text content in WhatsApp message type {message_type}")
                return

            # Feedback: intercept 👍/👎 as per-message satisfaction signal
            _stripped = text.strip()
            if _stripped in ("👍", "👎", ":thumbsup:", ":thumbsdown:", "+1", "-1"):
                try:
                    from sqlalchemy import select

                    from src.models.message import Message
                    from src.services.eval.feedback_service import record_feedback

                    _msg_result = await self.db_session.execute(
                        select(Message).filter(Message.role == "assistant").order_by(Message.created_at.desc()).limit(1)
                    )
                    _last_msg = _msg_result.scalar_one_or_none()
                    if _last_msg:
                        _rating = 1 if _stripped in ("👍", ":thumbsup:", "+1") else -1
                        record_feedback(
                            message_id=str(_last_msg.id),
                            agent_id=bot.agent_id,
                            tenant_id=bot.tenant_id,
                            channel="whatsapp",
                            rating=_rating,
                        )
                except Exception as _fb_err:
                    logger.debug("WhatsApp feedback intercept failed: %s", _fb_err)
                return

            # HITL: Check if this message is a reply to a pending approval request
            from src.config.redis import get_redis_async
            from src.services.human_approval_service import HumanApprovalService

            _redis = get_redis_async()
            _hitl_key = f"hitl:whatsapp:{bot.id}:{from_number}"
            _approval_id_str = await _redis.get(_hitl_key)
            if _approval_id_str:
                import uuid as _uuid_mod

                _approval_svc = HumanApprovalService(self.db_session)
                _decision = _approval_svc.parse_reply(text)
                if _decision != "unclear":
                    await _approval_svc.handle_reply(_uuid_mod.UUID(_approval_id_str), text, self.db_session)
                    _reply = "Got it! Proceeding." if _decision == "approve" else "Got it! Action cancelled."
                    await _redis.delete(_hitl_key)
                    await self._send_message(bot, from_number, _reply)
                    return
                else:
                    await self._send_message(bot, from_number, "Reply YES to proceed or NO to cancel.")
                    return

            # Get or create conversation
            conversation = await self._get_or_create_conversation(bot, from_number)

            # Block AI while a human operator is handling this conversation
            if getattr(conversation, "handoff_status", None) == "active":
                await self._send_message(
                    bot,
                    from_number,
                    "A human support agent is currently handling your request. They will respond shortly.",
                )
                return

            # Save user message
            user_message = Message(
                conversation_id=conversation.id,
                role="user",
                content=text,
                message_metadata={
                    "whatsapp_message_id": message_id,
                    "whatsapp_user": from_number,
                    "message_type": message_type,
                },
            )
            self.db_session.add(user_message)
            conversation.increment_message_count()
            await self.db_session.commit()

            # Mark message as read
            await self._mark_as_read(bot, message_id)

            # Get agent response
            from ...services.agents.agent_loader_service import AgentLoaderService
            from ...services.agents.agent_manager import AgentManager
            from ...services.agents.chat_service import ChatService
            from ...services.agents.chat_stream_service import ChatStreamService
            from ...services.conversation_service import ConversationService

            agent = await self.db_session.get(Agent, bot.agent_id)
            if not agent:
                logger.error(f"Agent {bot.agent_id} not found for WhatsApp bot {bot.id}")
                return

            # Load conversation history with caching support
            conversation_history = await ConversationService.get_conversation_history_cached(
                db=self.db_session,
                conversation_id=conversation.id,
                limit=30,
            )
            logger.info(f"Loaded {len(conversation_history)} messages from WhatsApp conversation history")

            chat_stream_service = ChatStreamService(
                agent_loader=AgentLoaderService(AgentManager()), chat_service=ChatService()
            )

            # Collect streamed response
            response_chunks = []
            async for event_data in chat_stream_service.stream_agent_response(
                agent_name=agent.slug or agent.agent_name,
                message=text,
                conversation_history=conversation_history,
                conversation_id=str(conversation.id),
                attachments=None,
                llm_config_id=None,
                db=self.db_session,
                user_id=str(bot.created_by) if bot.created_by else None,
                tenant_id=bot.tenant_id,
                trigger_source="whatsapp",
                trigger_detail=from_number,
            ):
                if event_data.startswith("data: "):
                    try:
                        event_json = json.loads(event_data[6:])
                        if event_json.get("type") == "chunk":
                            response_chunks.append(event_json.get("content", ""))
                    except Exception:
                        pass

            agent_response = "".join(response_chunks)

            # Send WhatsApp message
            await self._send_message(bot, from_number, agent_response)

            # Save assistant message
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=agent_response,
            )
            self.db_session.add(assistant_message)
            conversation.increment_message_count()
            bot.last_message_at = datetime.now(UTC)
            await self.db_session.commit()

            logger.info(f"Processed WhatsApp message from {from_number} for bot {bot.id}")

        except Exception as e:
            logger.error(f"Error processing WhatsApp message: {str(e)}")
            await self.db_session.rollback()

    async def _get_or_create_conversation(self, bot: WhatsAppBot, user_phone: str) -> Conversation:
        """
        Get or create conversation mapping.

        Args:
            bot: WhatsAppBot instance
            user_phone: User's phone number

        Returns:
            Conversation instance
        """
        stmt = select(WhatsAppConversation).where(
            WhatsAppConversation.whatsapp_bot_id == bot.id, WhatsAppConversation.whatsapp_user_id == user_phone
        )
        result = await self.db_session.execute(stmt)
        wa_conv = result.scalar_one_or_none()

        if wa_conv:
            return await self.db_session.get(Conversation, wa_conv.conversation_id)

        # Create new conversation
        conversation = Conversation(
            agent_id=bot.agent_id,
            name=f"WhatsApp conversation with {user_phone}",
            status=ConversationStatus.ACTIVE,
            source="whatsapp",
        )
        self.db_session.add(conversation)
        await self.db_session.commit()
        await self.db_session.refresh(conversation)

        wa_conv = WhatsAppConversation(
            whatsapp_bot_id=bot.id, conversation_id=conversation.id, whatsapp_user_id=user_phone
        )
        self.db_session.add(wa_conv)
        await self.db_session.commit()

        return conversation

    async def _send_message(self, bot: WhatsAppBot, to_number: str, text: str):
        """
        Send WhatsApp message via Business API.

        Args:
            bot: WhatsAppBot instance
            to_number: Recipient phone number
            text: Message text
        """
        try:
            access_token = decrypt_value(bot.access_token)

            url = f"{WHATSAPP_API_URL}/{bot.phone_number_id}/messages"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

            # Format text for WhatsApp (max 4096 characters)
            formatted_text = text[:4096] if len(text) > 4096 else text

            payload = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"body": formatted_text},
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()

            logger.info(f"Sent WhatsApp message to {to_number}")

        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {str(e)}")
            raise

    async def _mark_as_read(self, bot: WhatsAppBot, message_id: str):
        """
        Mark WhatsApp message as read.

        Args:
            bot: WhatsAppBot instance
            message_id: Message ID to mark as read
        """
        try:
            access_token = decrypt_value(bot.access_token)

            url = f"{WHATSAPP_API_URL}/{bot.phone_number_id}/messages"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

            payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}

            async with httpx.AsyncClient() as client:
                await client.post(url, headers=headers, json=payload, timeout=10.0)

        except Exception as e:
            logger.debug(f"Failed to mark WhatsApp message as read: {str(e)}")
