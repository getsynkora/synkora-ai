"""Telegram Webhook service for handling incoming webhook updates."""

import asyncio
import hmac
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot, Update

from ...models.conversation import Conversation, ConversationStatus
from ...models.message import Message, MessageRole
from ...models.telegram_bot import TelegramBot, TelegramConversation
from ...services.agents.agent_manager import AgentManager
from ...services.agents.security import decrypt_value

logger = logging.getLogger(__name__)


class TelegramWebhookService:
    """Service for handling Telegram webhook updates."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.agent_manager = AgentManager()

    async def setup_webhook(self, telegram_bot: TelegramBot, base_url: str) -> bool:
        """
        Set up webhook for a Telegram bot.

        Args:
            telegram_bot: TelegramBot instance to configure
            base_url: Base URL of the API (e.g., https://api.example.com)

        Returns:
            bool: True if webhook was set up successfully
        """
        try:
            bot_token = decrypt_value(telegram_bot.bot_token)
            bot = Bot(token=bot_token)

            # Get bot info
            bot_info = await bot.get_me()
            if not telegram_bot.bot_username:
                telegram_bot.bot_username = bot_info.username
            if not telegram_bot.telegram_bot_id:
                telegram_bot.telegram_bot_id = bot_info.id

            # Build webhook URL - use bot_id as identifier
            webhook_url = f"{base_url}/api/webhooks/telegram/{telegram_bot.id}"

            # Store the webhook URL
            telegram_bot.webhook_url = webhook_url

            # Decrypt webhook secret if set
            webhook_secret = None
            if telegram_bot.webhook_secret:
                webhook_secret = decrypt_value(telegram_bot.webhook_secret)

            # Set webhook with Telegram
            await bot.set_webhook(
                url=webhook_url,
                secret_token=webhook_secret,
                allowed_updates=["message", "edited_message", "callback_query"],
            )

            # Update bot status
            telegram_bot.connection_status = "connected"
            telegram_bot.last_connected_at = datetime.now(UTC)
            telegram_bot.last_error = None
            await self.db_session.commit()

            logger.info(
                f"Set up webhook for bot {telegram_bot.bot_name} (@{telegram_bot.bot_username}) at {webhook_url}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to set up webhook for bot {telegram_bot.id}: {str(e)}")
            telegram_bot.connection_status = "error"
            telegram_bot.last_error = str(e)
            await self.db_session.commit()
            return False

    async def remove_webhook(self, telegram_bot: TelegramBot) -> bool:
        """
        Remove webhook for a Telegram bot.

        Args:
            telegram_bot: TelegramBot instance

        Returns:
            bool: True if webhook was removed successfully
        """
        try:
            bot_token = decrypt_value(telegram_bot.bot_token)
            bot = Bot(token=bot_token)

            await bot.delete_webhook(drop_pending_updates=False)

            telegram_bot.connection_status = "disconnected"
            await self.db_session.commit()

            logger.info(f"Removed webhook for bot {telegram_bot.bot_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove webhook for bot {telegram_bot.id}: {str(e)}")
            return False

    def verify_webhook_secret(self, telegram_bot: TelegramBot, secret_token: str | None) -> bool:
        """
        Verify the webhook secret token from Telegram.

        Args:
            telegram_bot: TelegramBot instance
            secret_token: Secret token from X-Telegram-Bot-Api-Secret-Token header

        Returns:
            bool: True if verification passed
        """
        if not telegram_bot.webhook_secret:
            # No secret configured, accept all requests
            return True

        if not secret_token:
            return False

        expected_secret = decrypt_value(telegram_bot.webhook_secret)
        return hmac.compare_digest(secret_token, expected_secret)

    async def process_update(self, telegram_bot: TelegramBot, update_data: dict) -> dict:
        """
        Process an incoming webhook update from Telegram.

        Args:
            telegram_bot: TelegramBot instance
            update_data: Raw update data from Telegram

        Returns:
            dict: Processing result
        """
        try:
            bot_token = decrypt_value(telegram_bot.bot_token)
            bot = Bot(token=bot_token)
            update = Update.de_json(update_data, bot)

            if not update:
                return {"success": False, "error": "Invalid update data"}

            # Handle message updates
            if update.message and update.message.text:
                if not update.effective_chat or not update.effective_user:
                    return {"success": True, "message": "Missing chat or user info"}

                # Skip bot messages
                if update.effective_user.is_bot:
                    return {"success": True, "message": "Skipped bot message"}

                # Process in background to return quickly to Telegram
                asyncio.create_task(
                    self._handle_message(
                        telegram_bot=telegram_bot,
                        bot=bot,
                        chat_id=update.effective_chat.id,
                        chat_type=update.effective_chat.type,
                        chat_title=update.effective_chat.title,
                        user_id=update.effective_user.id,
                        user_name=update.effective_user.username,
                        user_first_name=update.effective_user.first_name,
                        user_last_name=update.effective_user.last_name,
                        text=update.message.text,
                        message_id=update.message.message_id,
                    )
                )
                return {"success": True}

            return {"success": True, "message": "Update type not handled"}

        except Exception as e:
            logger.error(f"Error processing webhook update: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _handle_message(
        self,
        telegram_bot: TelegramBot,
        bot: Bot,
        chat_id: int,
        chat_type: str,
        chat_title: str | None,
        user_id: int,
        user_name: str | None,
        user_first_name: str | None,
        user_last_name: str | None,
        text: str,
        message_id: int | None,
    ):
        """Handle incoming Telegram message and generate agent response."""
        try:
            # Get or create conversation mapping
            conversation = await self._get_or_create_conversation(
                telegram_bot=telegram_bot,
                chat_id=chat_id,
                chat_type=chat_type,
                chat_title=chat_title,
                user_id=user_id,
                user_name=user_name,
                user_first_name=user_first_name,
                user_last_name=user_last_name,
                message_text=text,
            )

            # Build user display name
            user_display = f"{user_first_name or ''} {user_last_name or ''}".strip()
            if not user_display:
                user_display = user_name or f"User {user_id}"

            # Handle /start command
            if text == "/start":
                welcome_message = f"Hello {user_display}! I'm here to help. What can I do for you?"
                sent_msg = await bot.send_message(chat_id=chat_id, text=welcome_message)
                tg_conv = await self._get_telegram_conversation(telegram_bot.id, chat_id, user_id)
                if tg_conv:
                    tg_conv.last_bot_message_id = sent_msg.message_id
                    await self.db_session.commit()
                return

            # Build context message
            chat_display = chat_title or f"Chat {chat_id}"
            context_message = (
                f"[Telegram Context: {chat_type} chat '{chat_display}', User: {user_display} (@{user_name})]\n\n{text}"
            )

            logger.info(f"Webhook received message from {user_display}: {text[:100]}...")

            # Save user message
            user_message = Message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=context_message,
                message_metadata={
                    "telegram_chat_id": chat_id,
                    "telegram_chat_type": chat_type,
                    "telegram_user_id": user_id,
                    "telegram_user_name": user_name,
                    "telegram_user_display": user_display,
                    "telegram_message_id": message_id,
                    "original_text": text,
                },
            )
            self.db_session.add(user_message)
            conversation.increment_message_count()
            await self.db_session.commit()

            # Start typing indicator
            typing_task = asyncio.create_task(self._send_typing_continuously(bot, chat_id))

            try:
                # Get agent response
                from ...models.agent import Agent
                from ...services.agents.agent_loader_service import AgentLoaderService
                from ...services.agents.chat_service import ChatService
                from ...services.agents.chat_stream_service import ChatStreamService
                from ...services.conversation_service import ConversationService

                agent = await self.db_session.get(Agent, telegram_bot.agent_id)
                if not agent:
                    raise ValueError(f"Agent {telegram_bot.agent_id} not found")

                conversation_history = await ConversationService.get_conversation_history_cached(
                    db=self.db_session, conversation_id=conversation.id, limit=30
                )

                chat_stream_service = ChatStreamService(
                    agent_loader=AgentLoaderService(self.agent_manager), chat_service=ChatService()
                )

                # Collect response
                response_chunks = []
                async for event_data in chat_stream_service.stream_agent_response(
                    agent_name=agent.slug or agent.agent_name,
                    message=context_message,
                    conversation_history=conversation_history,
                    conversation_id=str(conversation.id),
                    attachments=None,
                    llm_config_id=None,
                    db=self.db_session,
                    trigger_source="telegram",
                ):
                    if event_data.startswith("data: "):
                        try:
                            import json

                            event_json = json.loads(event_data[6:])
                            if event_json.get("type") == "chunk":
                                response_chunks.append(event_json.get("content", ""))
                        except (json.JSONDecodeError, KeyError, TypeError):
                            pass

                agent_response = "".join(response_chunks)

            finally:
                # Stop typing indicator
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass

            # Handle empty response
            if not agent_response or not agent_response.strip():
                agent_response = "Done! I've processed your request."

            # Convert markdown to Telegram HTML and send (4096 char limit per message)
            from ...services.telegram.markdown_utils import md_to_telegram_html, split_html_message

            html_response = md_to_telegram_html(agent_response)
            chunks = split_html_message(html_response)
            for chunk in chunks:
                sent_msg = await bot.send_message(chat_id=chat_id, text=chunk, parse_mode="HTML")

            # Update last bot message ID
            tg_conv = await self._get_telegram_conversation(telegram_bot.id, chat_id, user_id)
            if tg_conv:
                tg_conv.last_bot_message_id = sent_msg.message_id
                await self.db_session.commit()

            # Save assistant response
            assistant_message = Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=agent_response,
            )
            self.db_session.add(assistant_message)
            conversation.increment_message_count()
            await self.db_session.commit()

        except Exception as e:
            logger.error(f"Error handling webhook message: {str(e)}")
            await self.db_session.rollback()

            try:
                await bot.send_message(
                    chat_id=chat_id, text="Sorry, I encountered an error processing your message. Please try again."
                )
            except Exception as send_err:
                logger.debug(f"Could not send error message: {send_err}")

    async def _send_typing_continuously(self, bot: Bot, chat_id: int, interval: float = 4.0):
        """Send typing indicator continuously."""
        try:
            while True:
                await bot.send_chat_action(chat_id=chat_id, action="typing")
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Error sending typing indicator: {e}")

    async def _get_telegram_conversation(
        self, telegram_bot_id: UUID, chat_id: int, user_id: int
    ) -> TelegramConversation | None:
        """Get existing Telegram conversation mapping."""
        stmt = select(TelegramConversation).where(
            TelegramConversation.telegram_bot_id == telegram_bot_id,
            TelegramConversation.telegram_chat_id == chat_id,
            TelegramConversation.telegram_user_id == user_id,
        )
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_or_create_conversation(
        self,
        telegram_bot: TelegramBot,
        chat_id: int,
        chat_type: str,
        chat_title: str | None,
        user_id: int,
        user_name: str | None,
        user_first_name: str | None,
        user_last_name: str | None,
        message_text: str | None = None,
    ) -> Conversation:
        """Get existing conversation or create new one."""
        stmt = select(TelegramConversation).where(
            TelegramConversation.telegram_bot_id == telegram_bot.id,
            TelegramConversation.telegram_chat_id == chat_id,
            TelegramConversation.telegram_user_id == user_id,
        )
        result = await self.db_session.execute(stmt)
        tg_conv = result.scalar_one_or_none()

        if tg_conv:
            return await self.db_session.get(Conversation, tg_conv.conversation_id)

        # Build user display name
        user_display = f"{user_first_name or ''} {user_last_name or ''}".strip()
        if not user_display:
            user_display = user_name or f"User {user_id}"

        # Create new conversation
        conv_name = (
            message_text.strip()[:60] if message_text and message_text.strip() else f"Telegram chat with {user_display}"
        )
        conversation = Conversation(agent_id=telegram_bot.agent_id, name=conv_name, status=ConversationStatus.ACTIVE)
        self.db_session.add(conversation)
        await self.db_session.commit()
        await self.db_session.refresh(conversation)

        # Create mapping
        tg_conv = TelegramConversation(
            telegram_bot_id=telegram_bot.id,
            conversation_id=conversation.id,
            telegram_chat_id=chat_id,
            telegram_chat_type=chat_type,
            telegram_chat_title=chat_title,
            telegram_user_id=user_id,
            telegram_user_name=user_name,
            telegram_user_display=user_display,
        )
        self.db_session.add(tg_conv)
        await self.db_session.commit()

        return conversation
