"""Telegram Polling service for handling real-time messages."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ...models.conversation import Conversation, ConversationStatus
from ...models.message import Message, MessageRole
from ...models.telegram_bot import TelegramBot, TelegramConversation
from ...services.agents.agent_manager import AgentManager
from ...services.agents.security import decrypt_value

logger = logging.getLogger(__name__)


class TelegramPollingService:
    """Service for managing Telegram long polling connections and message handling."""

    # Class-level storage for active applications (shared across all instances)
    _active_applications: dict[str, Application] = {}

    def __init__(self, db_session: AsyncSession, agent_manager: AgentManager | None = None):
        self.db_session = db_session
        # OPTIMIZATION: Allow passing a shared AgentManager to avoid re-creation overhead
        self.agent_manager = agent_manager or AgentManager()

    @property
    def active_applications(self) -> dict[str, Application]:
        """Access the shared active_applications dictionary."""
        return TelegramPollingService._active_applications

    async def start_bot(self, telegram_bot: TelegramBot) -> bool:
        """
        Start a Telegram bot with long polling.

        Args:
            telegram_bot: TelegramBot instance to start

        Returns:
            bool: True if started successfully
        """
        try:
            # Decrypt token
            bot_token = decrypt_value(telegram_bot.bot_token)

            # Create application
            application = Application.builder().token(bot_token).build()

            # Get bot info and update model
            bot = Bot(token=bot_token)
            bot_info = await bot.get_me()

            # Update bot info if not set
            if not telegram_bot.bot_username:
                telegram_bot.bot_username = bot_info.username
            if not telegram_bot.telegram_bot_id:
                telegram_bot.telegram_bot_id = bot_info.id

            logger.info(f"Bot info: @{bot_info.username} (ID: {bot_info.id})")

            # Delete any existing webhook (ensure we're using polling)
            await bot.delete_webhook(drop_pending_updates=False)

            # Register handlers
            self._register_handlers(application, telegram_bot)

            # Initialize application
            await application.initialize()

            # Start polling in background
            asyncio.create_task(self._run_polling(application, telegram_bot))

            # Store application reference
            self.active_applications[str(telegram_bot.id)] = application

            # Update bot status
            telegram_bot.connection_status = "connected"
            telegram_bot.last_connected_at = datetime.now(UTC)
            telegram_bot.last_error = None
            await self.db_session.commit()

            logger.info(f"Started Telegram bot {telegram_bot.bot_name} (@{telegram_bot.bot_username})")
            return True

        except Exception as e:
            logger.error(f"Failed to start Telegram bot {telegram_bot.id}: {str(e)}")
            telegram_bot.connection_status = "error"
            telegram_bot.last_error = str(e)
            await self.db_session.commit()
            return False

    async def _run_polling(self, application: Application, telegram_bot: TelegramBot):
        """Run the polling loop."""
        try:
            await application.start()
            await application.updater.start_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)
            logger.info(f"Polling started for bot {telegram_bot.bot_name}")

            # Keep running until stopped
            while str(telegram_bot.id) in self.active_applications:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Polling error for bot {telegram_bot.id}: {str(e)}")
            telegram_bot.connection_status = "error"
            telegram_bot.last_error = str(e)
            await self.db_session.commit()

    async def stop_bot(self, telegram_bot_id: UUID) -> bool:
        """
        Stop a running Telegram bot.

        Args:
            telegram_bot_id: ID of the bot to stop

        Returns:
            bool: True if stopped successfully
        """
        try:
            bot_id_str = str(telegram_bot_id)

            if bot_id_str in self.active_applications:
                application = self.active_applications[bot_id_str]

                # Stop updater and application
                if application.updater and application.updater.running:
                    await application.updater.stop()
                if application.running:
                    await application.stop()
                await application.shutdown()

                del self.active_applications[bot_id_str]
                logger.info(f"Stopped Telegram bot {telegram_bot_id}")
            else:
                logger.info(f"Telegram bot {telegram_bot_id} was not running")

            # Update bot status
            telegram_bot = await self.db_session.get(TelegramBot, telegram_bot_id)
            if telegram_bot:
                telegram_bot.connection_status = "disconnected"
                await self.db_session.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to stop Telegram bot {telegram_bot_id}: {str(e)}")
            return False

    def _register_handlers(self, application: Application, telegram_bot: TelegramBot):
        """Register message handlers for the Telegram application."""

        async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Handle /start command."""
            if update.effective_chat and update.effective_user:
                await self._handle_message(
                    telegram_bot=telegram_bot,
                    chat_id=update.effective_chat.id,
                    chat_type=update.effective_chat.type,
                    chat_title=update.effective_chat.title,
                    user_id=update.effective_user.id,
                    user_name=update.effective_user.username,
                    user_first_name=update.effective_user.first_name,
                    user_last_name=update.effective_user.last_name,
                    text="/start",
                    message_id=update.message.message_id if update.message else None,
                    context=context,
                    is_start_command=True,
                )

        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """Handle all text messages."""
            if not update.message or not update.message.text:
                return

            if not update.effective_chat or not update.effective_user:
                return

            # Skip bot messages
            if update.effective_user.is_bot:
                return

            await self._handle_message(
                telegram_bot=telegram_bot,
                chat_id=update.effective_chat.id,
                chat_type=update.effective_chat.type,
                chat_title=update.effective_chat.title,
                user_id=update.effective_user.id,
                user_name=update.effective_user.username,
                user_first_name=update.effective_user.first_name,
                user_last_name=update.effective_user.last_name,
                text=update.message.text,
                message_id=update.message.message_id,
                context=context,
            )

        # Register handlers
        application.add_handler(CommandHandler("start", handle_start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async def _handle_message(
        self,
        telegram_bot: TelegramBot,
        chat_id: int,
        chat_type: str,
        chat_title: str | None,
        user_id: int,
        user_name: str | None,
        user_first_name: str | None,
        user_last_name: str | None,
        text: str,
        message_id: int | None,
        context: ContextTypes.DEFAULT_TYPE,
        is_start_command: bool = False,
    ):
        """
        Handle incoming Telegram message and generate agent response.
        """
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

            # Handle /start command specially
            if is_start_command:
                welcome_message = f"Hello {user_display}! I'm here to help. What can I do for you?"
                sent_msg = await context.bot.send_message(chat_id=chat_id, text=welcome_message)
                # Update last bot message ID
                tg_conv = await self._get_telegram_conversation(telegram_bot.id, chat_id, user_id)
                if tg_conv:
                    tg_conv.last_bot_message_id = sent_msg.message_id
                    await self.db_session.commit()
                return

            # Build context message for the agent
            chat_display = chat_title or f"Chat {chat_id}"
            context_message = (
                f"[Telegram Context: {chat_type} chat '{chat_display}', User: {user_display} (@{user_name})]\n\n{text}"
            )

            logger.info(f"Received message from {user_display} in {chat_display}: {text[:100]}...")

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
            # OPTIMIZATION: Use flush() instead of commit() - saves ~100-200ms by avoiding fsync
            # The final commit happens after assistant message is saved
            await self.db_session.flush()

            # Start continuous typing indicator task
            typing_task = asyncio.create_task(self._send_typing_continuously(context, chat_id))

            # Get agent response using chat infrastructure
            from ...models.agent import Agent
            from ...services.agents.agent_loader_service import AgentLoaderService
            from ...services.agents.chat_service import ChatService
            from ...services.agents.chat_stream_service import ChatStreamService
            from ...services.conversation_service import ConversationService

            # Get agent
            agent = await self.db_session.get(Agent, telegram_bot.agent_id)
            if not agent:
                raise ValueError(f"Agent {telegram_bot.agent_id} not found")

            # Load conversation history
            conversation_history = await ConversationService.get_conversation_history_cached(
                db=self.db_session, conversation_id=conversation.id, limit=30
            )
            logger.info(f"Loaded {len(conversation_history)} messages from conversation history")

            # Initialize chat stream service
            chat_stream_service = ChatStreamService(
                agent_loader=AgentLoaderService(self.agent_manager), chat_service=ChatService()
            )

            # Collect streamed response
            response_chunks = []
            async for event_data in chat_stream_service.stream_agent_response(
                agent_name=agent.slug or agent.agent_name,
                message=context_message,
                conversation_history=conversation_history,
                conversation_id=str(conversation.id),
                attachments=None,
                llm_config_id=None,
                db=self.db_session,
                user_id=str(telegram_bot.created_by) if telegram_bot.created_by else None,
                tenant_id=telegram_bot.tenant_id,
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

            # Stop typing indicator
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass

            # Handle empty response
            if not agent_response or not agent_response.strip():
                logger.warning("Agent returned empty response, using fallback")
                agent_response = "Done! I've processed your request."

            # Convert markdown to Telegram HTML and send (4096 char limit per message)
            from ...services.telegram.markdown_utils import md_to_telegram_html, split_html_message

            html_response = md_to_telegram_html(agent_response)
            chunks = split_html_message(html_response)
            for chunk in chunks:
                sent_msg = await context.bot.send_message(chat_id=chat_id, text=chunk, parse_mode="HTML")

            # Update last bot message ID
            tg_conv = await self._get_telegram_conversation(telegram_bot.id, chat_id, user_id)
            if tg_conv:
                tg_conv.last_bot_message_id = sent_msg.message_id
                # No commit yet - will be committed with assistant message

            # Save assistant response
            assistant_message = Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=agent_response,
            )
            self.db_session.add(assistant_message)
            conversation.increment_message_count()
            # OPTIMIZATION: Single commit for user message, bot message ID, and assistant message
            await self.db_session.commit()

        except Exception as e:
            logger.error(f"Error handling Telegram message: {str(e)}")
            await self.db_session.rollback()

            # Cancel typing task if it exists
            if "typing_task" in locals():
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass

            # Send error message to user
            try:
                await context.bot.send_message(
                    chat_id=chat_id, text="Sorry, I encountered an error processing your message. Please try again."
                )
            except Exception as send_err:
                logger.debug(f"Could not send error message to user: {send_err}")

    async def _send_typing_continuously(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, interval: float = 4.0):
        """
        Continuously send typing indicator to Telegram chat.

        Telegram's typing indicator lasts about 5 seconds, so we send it
        every 4 seconds to maintain the "typing..." status during long operations.

        Args:
            context: Telegram bot context
            chat_id: Chat ID to send typing indicator to
            interval: Seconds between typing actions (default: 4.0)
        """
        try:
            while True:
                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            # Task was cancelled, this is expected when response is ready
            pass
        except Exception as e:
            # Log but don't raise - typing indicator is not critical
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
        # Try to find existing conversation
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

    async def get_bot_status(self, telegram_bot_id: UUID) -> dict[str, Any]:
        """Get status of a Telegram bot."""
        bot_id_str = str(telegram_bot_id)
        is_running = bot_id_str in self.active_applications

        telegram_bot = await self.db_session.get(TelegramBot, telegram_bot_id)

        return {
            "bot_id": str(telegram_bot_id),
            "is_running": is_running,
            "connection_status": telegram_bot.connection_status if telegram_bot else "unknown",
            "last_connected_at": telegram_bot.last_connected_at.isoformat()
            if telegram_bot and telegram_bot.last_connected_at
            else None,
            "last_error": telegram_bot.last_error if telegram_bot else None,
        }
