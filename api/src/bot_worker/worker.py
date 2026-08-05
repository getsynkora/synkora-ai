"""Bot Worker - manages multiple bot connections in a single process.

This is the core worker class that:
- Registers with Redis on startup
- Sends periodic heartbeats
- Claims and manages bot connections via consistent hashing
- Handles graceful shutdown
"""

import asyncio
import logging
import random
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_session_factory
from ..models.slack_bot import SlackBot
from ..models.telegram_bot import TelegramBot
from ..models.whatsapp_bot import WhatsAppBot
from ..services.agents.security import decrypt_value
from .config import BotWorkerConfig
from .consistent_hash import ConsistentHash
from .health_server import HealthServer
from .redis_state import BotEvent, BotEventType, BotRedisState, BotType

logger = logging.getLogger(__name__)


class BotWorker:
    """Worker that manages multiple Slack and Telegram bot connections."""

    def __init__(
        self,
        config: BotWorkerConfig,
        redis_client: redis.Redis,
    ):
        """Initialize the bot worker.

        Args:
            config: Worker configuration
            redis_client: Connected Redis client
        """
        self.config = config
        self.worker_id = config.worker_id
        self.capacity = config.worker_capacity

        # Redis state management
        self.redis_state = BotRedisState(redis_client)
        self._redis_client = redis_client

        # Consistent hash ring (populated from Redis on startup)
        self._hash_ring = ConsistentHash(replicas=config.hash_replicas)

        # Active bot connections: bot_id -> connection info
        self._active_bots: dict[str, dict[str, Any]] = {}

        # Slack handlers: bot_id -> AsyncSocketModeHandler
        self._slack_handlers: dict[str, Any] = {}

        # Slack polling tasks: bot_id -> asyncio.Task (start_async loop)
        self._slack_tasks: dict[str, asyncio.Task] = {}

        # Telegram applications: bot_id -> Application
        self._telegram_apps: dict[str, Any] = {}

        # WhatsApp device-link: bot_id -> {client, session_dir, thread}
        self._whatsapp_clients: dict[str, dict[str, Any]] = {}

        # Worker state
        self._started_at: float | None = None
        self._is_ready = False
        self._is_shutting_down = False
        self._last_event_id = "0"

        # Background tasks
        self._heartbeat_task: asyncio.Task | None = None
        self._event_listener_task: asyncio.Task | None = None
        self._command_listener_task: asyncio.Task | None = None
        self._dead_worker_check_task: asyncio.Task | None = None

        # Health server
        self._health_server = HealthServer(self, config.health_port)

        # OPTIMIZATION: Bot metadata cache to avoid DB lookup per message
        self._bot_cache: dict[str, tuple[Any, float]] = {}  # {bot_id: (bot_data_dict, timestamp)}
        self._cache_ttl = 60.0  # 60 second TTL

        # OPTIMIZATION: Reuse service instances per bot
        self._slack_services: dict[str, Any] = {}  # {bot_id: SlackSocketService}
        self._telegram_services: dict[str, Any] = {}  # {bot_id: TelegramPollingService}

        # OPTIMIZATION: Shared AgentManager instance (expensive to create)
        from ..services.agents.agent_manager import AgentManager

        self._shared_agent_manager = AgentManager()

    async def _get_cached_bot_data(self, bot_id: str, bot_class: type) -> dict[str, Any] | None:
        """Get bot data from cache or refresh from DB.

        Args:
            bot_id: Bot ID as string
            bot_class: SlackBot or TelegramBot class

        Returns:
            Dict with bot attributes needed for message handling, or None if not found
        """
        cached = self._bot_cache.get(bot_id)
        if cached and time.time() - cached[1] < self._cache_ttl:
            return cached[0]

        # Refresh from DB
        async with get_async_session_factory()() as db:
            bot = await db.get(bot_class, UUID(bot_id))
            if not bot:
                return None

            # Cache essential attributes as a dict (avoid detached instance issues)
            bot_data = {
                "id": bot.id,
                "agent_id": bot.agent_id,
                "is_active": bot.is_active,
            }

            # Add bot-type specific fields
            if bot_class == SlackBot:
                bot_data.update(
                    {
                        "bot_name": bot.bot_name,
                        "slack_app_id": bot.slack_app_id,
                        "slack_bot_token": bot.slack_bot_token,
                        "slack_app_token": bot.slack_app_token,
                    }
                )
            elif bot_class == TelegramBot:
                bot_data.update(
                    {
                        "bot_name": bot.bot_name,
                        "bot_token": bot.bot_token,
                        "bot_username": bot.bot_username,
                    }
                )

            self._bot_cache[bot_id] = (bot_data, time.time())
            return bot_data

    def _invalidate_bot_cache(self, bot_id: str) -> None:
        """Remove a bot from the cache."""
        self._bot_cache.pop(bot_id, None)

    @property
    def active_bot_count(self) -> int:
        """Get the number of active bot connections."""
        return len(self._active_bots)

    @property
    def is_ready(self) -> bool:
        """Check if the worker is ready to handle bots."""
        return self._is_ready

    @property
    def is_shutting_down(self) -> bool:
        """Check if the worker is shutting down."""
        return self._is_shutting_down

    @property
    def uptime_seconds(self) -> float:
        """Get worker uptime in seconds."""
        if self._started_at is None:
            return 0.0
        return time.time() - self._started_at

    async def start(self) -> None:
        """Start the bot worker."""
        logger.info(f"Starting bot worker {self.worker_id}")
        self._started_at = time.time()

        # Start health server
        await self._health_server.start()

        # Register with Redis
        self.redis_state.register_worker(self.worker_id, self.capacity)

        # Wait for peer workers to register before building the ring.
        # Without this, two pods starting in parallel both see only themselves,
        # map every bot to themselves, and double-poll (Telegram Conflict error).
        await asyncio.sleep(self.config.startup_jitter_max)

        # Build initial hash ring from all workers
        await self._rebuild_hash_ring()

        # Claim and start bots assigned to this worker
        await self._claim_assigned_bots()

        # Snapshot the current stream tail so the event listener only processes
        # events that arrive AFTER this pod starts — not historical replays.
        self._last_event_id = self.redis_state.get_latest_event_id()

        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._event_listener_task = asyncio.create_task(self._event_listener_loop())
        self._command_listener_task = asyncio.create_task(self._command_listener_loop())
        self._dead_worker_check_task = asyncio.create_task(self._dead_worker_check_loop())

        self._is_ready = True
        logger.info(f"Bot worker {self.worker_id} started with {self.active_bot_count} bots")

    async def stop(self) -> None:
        """Stop the bot worker gracefully."""
        logger.info(f"Stopping bot worker {self.worker_id}")
        self._is_shutting_down = True
        self._is_ready = False

        # Cancel background tasks
        for task in [
            self._heartbeat_task,
            self._event_listener_task,
            self._command_listener_task,
            self._dead_worker_check_task,
        ]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Stop all bot connections
        await self._stop_all_bots()

        # Unregister from Redis
        self.redis_state.unregister_worker(self.worker_id)

        # Stop health server
        await self._health_server.stop()

        logger.info(f"Bot worker {self.worker_id} stopped")

    async def _rebuild_hash_ring(self) -> None:
        """Rebuild the consistent hash ring from current healthy workers."""
        healthy_workers = self.redis_state.get_healthy_workers(self.config.heartbeat_timeout)

        # Clear and rebuild ring
        self._hash_ring = ConsistentHash(replicas=self.config.hash_replicas)
        for worker_id in healthy_workers:
            self._hash_ring.add_node(worker_id)

        # Ensure we're in the ring
        if self.worker_id not in self._hash_ring:
            self._hash_ring.add_node(self.worker_id)

        logger.debug(f"Hash ring rebuilt with {len(self._hash_ring)} workers")

    async def _claim_assigned_bots(self) -> None:
        """Claim and start all bots that should be managed by this worker."""
        async with get_async_session_factory()() as db:
            # Get all active bots
            all_bot_ids = await self._get_all_active_bot_ids(db)

            # Determine which bots this worker should manage
            my_bots = self._hash_ring.get_keys_for_node(self.worker_id, all_bot_ids)

            logger.info(f"Worker {self.worker_id} claiming {len(my_bots)} bots out of {len(all_bot_ids)} total")

            # Start each bot with jitter to avoid thundering herd
            for bot_id in my_bots:
                if self._is_shutting_down:
                    break

                # Add random jitter
                jitter = random.uniform(0, self.config.startup_jitter_max)
                await asyncio.sleep(jitter)

                await self._start_bot(bot_id, db)

    async def _get_all_active_bot_ids(self, db: AsyncSession) -> list[str]:
        """Get all active bot IDs from the database.

        Args:
            db: Database session

        Returns:
            List of bot IDs (as strings)
        """
        bot_ids = []

        # Get active Slack bots (Socket Mode only - Event Mode bots don't need workers)
        slack_stmt = select(SlackBot.id).where(
            SlackBot.is_active == True,  # noqa: E712
            SlackBot.deleted_at.is_(None),
            SlackBot.connection_mode == "socket",  # Exclude Event Mode bots
        )
        slack_result = await db.execute(slack_stmt)
        for (bot_id,) in slack_result:
            bot_ids.append(str(bot_id))

        # Get active Telegram bots (polling mode only - webhook bots don't need workers)
        telegram_stmt = select(TelegramBot.id).where(
            TelegramBot.is_active == True,  # noqa: E712
            TelegramBot.deleted_at.is_(None),
            TelegramBot.use_webhook == False,  # noqa: E712
        )
        telegram_result = await db.execute(telegram_stmt)
        for (bot_id,) in telegram_result:
            bot_ids.append(str(bot_id))

        # Get active WhatsApp device-link bots
        whatsapp_stmt = select(WhatsAppBot.id).where(
            WhatsAppBot.is_active == True,  # noqa: E712
            WhatsAppBot.connection_type == "device_link",
            WhatsAppBot.session_data.isnot(None),
            WhatsAppBot.deleted_at.is_(None),
        )
        whatsapp_result = await db.execute(whatsapp_stmt)
        for (bot_id,) in whatsapp_result:
            bot_ids.append(str(bot_id))

        return bot_ids

    async def _start_bot(self, bot_id: str, db: AsyncSession) -> bool:
        """Start a specific bot connection.

        Args:
            bot_id: Bot ID to start
            db: Database session

        Returns:
            True if started successfully
        """
        if bot_id in self._active_bots:
            logger.debug(f"Bot {bot_id} is already running")
            return True

        # Check capacity
        if self.active_bot_count >= self.capacity:
            logger.warning(f"Worker {self.worker_id} at capacity, cannot start bot {bot_id}")
            return False

        # Try Slack first
        slack_bot = await db.get(SlackBot, UUID(bot_id))
        if slack_bot:
            return await self._start_slack_bot(slack_bot)

        # Try Telegram
        telegram_bot = await db.get(TelegramBot, UUID(bot_id))
        if telegram_bot:
            return await self._start_telegram_bot(telegram_bot)

        # Try WhatsApp device-link
        whatsapp_bot = await db.get(WhatsAppBot, UUID(bot_id))
        if whatsapp_bot and whatsapp_bot.connection_type == "device_link":
            return await self._start_whatsapp_bot(whatsapp_bot)

        logger.warning(f"Bot {bot_id} not found in database")
        return False

    async def _start_slack_bot(self, slack_bot: SlackBot) -> bool:
        """Start a Slack bot connection."""
        try:
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
            from slack_bolt.async_app import AsyncApp

            bot_id = str(slack_bot.id)

            # Decrypt tokens
            bot_token = decrypt_value(slack_bot.slack_bot_token)
            app_token = decrypt_value(slack_bot.slack_app_token)

            # Create Slack app with handlers
            app = AsyncApp(token=bot_token)
            self._register_slack_handlers(app, slack_bot)

            # Create and start Socket Mode handler; keep the task so we can cancel it on stop
            handler = AsyncSocketModeHandler(app, app_token)
            task = asyncio.create_task(handler.start_async())
            self._slack_tasks[bot_id] = task

            # Store references
            self._slack_handlers[bot_id] = handler
            self._active_bots[bot_id] = {
                "type": "slack",
                "started_at": time.time(),
                "bot_name": slack_bot.bot_name,
            }

            # Update Redis assignment
            self.redis_state.assign_bot(bot_id, self.worker_id, BotType.SLACK)

            # Update database (columns are TIMESTAMP WITHOUT TIME ZONE — strip tzinfo)
            now_naive = datetime.now(UTC).replace(tzinfo=None)
            async with get_async_session_factory()() as db:
                bot = await db.get(SlackBot, slack_bot.id)
                if bot:
                    bot.assigned_worker_id = self.worker_id
                    bot.worker_connected_at = now_naive
                    bot.connection_status = "connected"
                    bot.last_connected_at = now_naive
                    await db.commit()

            logger.info(f"Started Slack bot {slack_bot.bot_name} ({bot_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to start Slack bot {slack_bot.id}: {e}")
            return False

    async def _start_telegram_bot(self, telegram_bot: TelegramBot) -> bool:
        """Start a Telegram bot connection."""
        try:
            from telegram.ext import Application

            bot_id = str(telegram_bot.id)

            # Decrypt token
            bot_token = decrypt_value(telegram_bot.bot_token)

            # Create application
            application = Application.builder().token(bot_token).build()

            # Register handlers
            self._register_telegram_handlers(application, telegram_bot)

            # Initialize and start
            await application.initialize()
            asyncio.create_task(self._run_telegram_polling(application, telegram_bot))

            # Store references
            self._telegram_apps[bot_id] = application
            self._active_bots[bot_id] = {
                "type": "telegram",
                "started_at": time.time(),
                "bot_name": telegram_bot.bot_name,
            }

            # Update Redis assignment
            self.redis_state.assign_bot(bot_id, self.worker_id, BotType.TELEGRAM)

            # Update database (columns are TIMESTAMP WITHOUT TIME ZONE — strip tzinfo)
            now_naive = datetime.now(UTC).replace(tzinfo=None)
            async with get_async_session_factory()() as db:
                bot = await db.get(TelegramBot, telegram_bot.id)
                if bot:
                    bot.assigned_worker_id = self.worker_id
                    bot.worker_connected_at = now_naive
                    bot.connection_status = "connected"
                    bot.last_connected_at = now_naive
                    await db.commit()

            logger.info(f"Started Telegram bot {telegram_bot.bot_name} ({bot_id})")
            return True

        except Exception as e:
            logger.error(f"Failed to start Telegram bot {telegram_bot.id}: {e}")
            return False

    async def _start_whatsapp_bot(self, whatsapp_bot: WhatsAppBot) -> bool:
        """Start a WhatsApp device-link bot by restoring its neonize session."""
        import base64
        import json as _json
        import shutil
        import tempfile
        import threading
        from pathlib import Path

        bot_id = str(whatsapp_bot.id)
        try:
            raw_json = decrypt_value(whatsapp_bot.session_data)
            if not raw_json:
                logger.warning(f"WhatsApp bot {bot_id} has no decryptable session_data")
                return False
            session_payload = _json.loads(raw_json)
            db_bytes = base64.b64decode(session_payload["session_db"])
        except Exception as e:
            logger.error(f"Failed to parse session_data for WhatsApp bot {bot_id}: {e}")
            return False

        session_dir = tempfile.mkdtemp(prefix=f"neonize_worker_{bot_id[:8]}_")
        db_path = str(Path(session_dir) / "session.db")
        Path(db_path).write_bytes(db_bytes)

        event_loop = asyncio.get_event_loop()
        agent_id = str(whatsapp_bot.agent_id)

        def _run() -> None:
            try:
                import neonize.events as neonize_events  # type: ignore[import]
                from neonize.client import NewClient  # type: ignore[import]

                from ..services.whatsapp.whatsapp_device_link_manager import (
                    _MESSAGE_EV_CANDIDATES,
                    _extract_sender_jid_server,
                    _extract_sender_phone,
                    _extract_text,
                    _process_message_async,
                )
            except Exception:
                logger.exception(f"Import error for WhatsApp bot {bot_id}")
                shutil.rmtree(session_dir, ignore_errors=True)
                return

            message_ev = None
            for name in _MESSAGE_EV_CANDIDATES:
                message_ev = getattr(neonize_events, name, None)
                if message_ev is not None:
                    break

            if message_ev is None:
                available = [x for x in dir(neonize_events) if not x.startswith("_")]
                logger.error(f"[WA {bot_id}] MessageEv not found in neonize.events. Available: {available}")
            else:
                logger.info(f"[WA {bot_id}] Using event class: {message_ev.__name__}")

            try:
                client = NewClient(db_path)
                self._whatsapp_clients[bot_id]["client"] = client

                if message_ev is not None:

                    @client.event(message_ev)
                    def _on_message(cli, evt) -> None:
                        try:
                            logger.debug(f"[WA {bot_id}] Raw event received: {type(evt).__name__}")
                            # Skip messages sent by this device
                            try:
                                if evt.Info.MessageSource.IsFromMe:
                                    logger.debug(f"[WA {bot_id}] Skipping own message")
                                    return
                            except Exception:
                                pass
                            # Skip group messages (only handle direct/private chats)
                            try:
                                chat_jid = evt.Info.MessageSource.Chat
                                chat_str = str(chat_jid)
                                if "@g.us" in chat_str or "@newsletter" in chat_str:
                                    logger.debug(f"[WA {bot_id}] Skipping group/channel message")
                                    return
                            except Exception:
                                pass
                            text = _extract_text(evt)
                            sender = _extract_sender_phone(evt)
                            sender_server = _extract_sender_jid_server(evt)
                            logger.info(f"[WA {bot_id}] Message from {sender!r}@{sender_server}: {text!r}")
                            if text and sender:
                                asyncio.run_coroutine_threadsafe(
                                    _process_message_async(cli, bot_id, agent_id, sender, sender_server, text),
                                    event_loop,
                                )
                        except Exception:
                            logger.exception(f"Message handler error for WhatsApp bot {bot_id}")

                logger.info(f"Connecting WhatsApp device-link bot {bot_id} ({whatsapp_bot.bot_name})")
                client.connect()

            except Exception:
                logger.exception(f"Neonize error for WhatsApp bot {bot_id}")
            finally:
                self._whatsapp_clients.pop(bot_id, None)
                self._active_bots.pop(bot_id, None)
                shutil.rmtree(session_dir, ignore_errors=True)
                logger.info(f"WhatsApp bot {bot_id} thread exited")

        self._whatsapp_clients[bot_id] = {"client": None, "session_dir": session_dir}
        self._active_bots[bot_id] = {"type": "whatsapp", "started_at": time.time(), "bot_name": whatsapp_bot.bot_name}

        thread = threading.Thread(target=_run, daemon=True, name=f"wa-{bot_id[:8]}")
        thread.start()
        self._whatsapp_clients[bot_id]["thread"] = thread

        self.redis_state.assign_bot(bot_id, self.worker_id, BotType.WHATSAPP)

        async with get_async_session_factory()() as db:
            bot = await db.get(WhatsAppBot, whatsapp_bot.id)
            if bot:
                bot.connection_status = "connected"
                await db.commit()

        logger.info(f"Started WhatsApp device-link bot {whatsapp_bot.bot_name} ({bot_id})")
        return True

    async def _run_telegram_polling(self, application: Any, telegram_bot: TelegramBot) -> None:
        """Run Telegram polling loop."""
        from telegram import Update

        bot_id = str(telegram_bot.id)
        try:
            await application.start()
            await application.updater.start_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)

            # Keep running until stopped
            while bot_id in self._active_bots and not self._is_shutting_down:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Telegram polling error for bot {bot_id}: {e}")
        finally:
            if bot_id in self._telegram_apps:
                try:
                    if application.updater and application.updater.running:
                        await application.updater.stop()
                    if application.running:
                        await application.stop()
                    await application.shutdown()
                except Exception as e:
                    logger.debug(f"Error during Telegram cleanup: {e}")

    def _register_slack_handlers(self, app: Any, slack_bot: SlackBot) -> None:
        """Register event handlers for Slack app."""
        # Import the actual message handler from existing service
        from ..services.slack.slack_socket_service import SlackSocketService

        # Store bot_id for fresh DB lookups
        bot_id = slack_bot.id
        # OPTIMIZATION: Capture shared agent_manager for reuse
        shared_agent_manager = self._shared_agent_manager

        @app.event("app_mention")
        async def handle_app_mention(event, say, client):
            # Create fresh session for each message
            async with get_async_session_factory()() as db:
                # Get fresh bot instance
                fresh_bot = await db.get(SlackBot, bot_id)
                if not fresh_bot:
                    logger.error(f"Slack bot {bot_id} not found in database")
                    return

                # OPTIMIZATION: Pass shared agent_manager to avoid re-creation overhead
                service = SlackSocketService(db, agent_manager=shared_agent_manager)
                await service._handle_message(
                    slack_bot=fresh_bot,
                    channel_id=event["channel"],
                    user_id=event["user"],
                    text=event["text"],
                    message_ts=event.get("ts"),
                    thread_ts=event.get("thread_ts"),
                    say=say,
                    client=client,
                )

        @app.event("message")
        async def handle_message(event, say, client):
            subtype = event.get("subtype")
            if subtype == "bot_message" or event.get("bot_id"):
                return
            if subtype in ("message_changed", "message_deleted", "channel_join", "channel_leave"):
                return

            channel_id = event.get("channel", "")
            channel_type = event.get("channel_type")
            is_dm = channel_type == "im" or channel_id.startswith("D")

            if is_dm:
                # Create fresh session for each message
                async with get_async_session_factory()() as db:
                    # Get fresh bot instance
                    fresh_bot = await db.get(SlackBot, bot_id)
                    if not fresh_bot:
                        logger.error(f"Slack bot {bot_id} not found in database")
                        return

                    # OPTIMIZATION: Pass shared agent_manager to avoid re-creation overhead
                    service = SlackSocketService(db, agent_manager=shared_agent_manager)
                    await service._handle_message(
                        slack_bot=fresh_bot,
                        channel_id=channel_id,
                        user_id=event["user"],
                        text=event.get("text", ""),
                        message_ts=event.get("ts"),
                        thread_ts=event.get("thread_ts"),
                        say=say,
                        client=client,
                    )

    def _register_telegram_handlers(self, application: Any, telegram_bot: TelegramBot) -> None:
        """Register message handlers for Telegram application."""
        from telegram import Update
        from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

        # Import the actual message handler from existing service
        from ..services.telegram.telegram_polling_service import TelegramPollingService

        # Store bot_id for fresh DB lookups
        bot_id = telegram_bot.id
        # OPTIMIZATION: Capture shared agent_manager for reuse
        shared_agent_manager = self._shared_agent_manager

        async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.effective_chat and update.effective_user:
                # Create fresh session for each message
                async with get_async_session_factory()() as db:
                    # Get fresh bot instance
                    fresh_bot = await db.get(TelegramBot, bot_id)
                    if not fresh_bot:
                        logger.error(f"Telegram bot {bot_id} not found in database")
                        return

                    # OPTIMIZATION: Pass shared agent_manager to avoid re-creation overhead
                    service = TelegramPollingService(db, agent_manager=shared_agent_manager)
                    await service._handle_message(
                        telegram_bot=fresh_bot,
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
            if not update.message or not update.message.text:
                return
            if not update.effective_chat or not update.effective_user:
                return
            if update.effective_user.is_bot:
                return

            # Create fresh session for each message
            async with get_async_session_factory()() as db:
                # Get fresh bot instance
                fresh_bot = await db.get(TelegramBot, bot_id)
                if not fresh_bot:
                    logger.error(f"Telegram bot {bot_id} not found in database")
                    return

                # OPTIMIZATION: Pass shared agent_manager to avoid re-creation overhead
                service = TelegramPollingService(db, agent_manager=shared_agent_manager)
                await service._handle_message(
                    telegram_bot=fresh_bot,
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

        application.add_handler(CommandHandler("start", handle_start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async def _stop_bot(self, bot_id: str) -> bool:
        """Stop a specific bot connection.

        Args:
            bot_id: Bot ID to stop

        Returns:
            True if stopped successfully
        """
        if bot_id not in self._active_bots:
            return True

        bot_info = self._active_bots[bot_id]
        bot_type = bot_info.get("type")

        try:
            if bot_type == "slack" and bot_id in self._slack_handlers:
                # Cancel the start_async task first so its retry loop stops before the session closes
                task = self._slack_tasks.pop(bot_id, None)
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
                handler = self._slack_handlers.pop(bot_id)
                try:
                    await asyncio.wait_for(handler.close_async(), timeout=5)
                except (TimeoutError, Exception):
                    pass

            elif bot_type == "telegram" and bot_id in self._telegram_apps:
                app = self._telegram_apps.pop(bot_id)
                if app.updater and app.updater.running:
                    await app.updater.stop()
                if app.running:
                    await app.stop()
                await app.shutdown()

            elif bot_type == "whatsapp" and bot_id in self._whatsapp_clients:
                entry = self._whatsapp_clients.pop(bot_id)
                client = entry.get("client")
                if client is not None:
                    try:
                        client.disconnect()
                    except Exception:
                        pass
                import shutil

                session_dir = entry.get("session_dir")
                if session_dir:
                    shutil.rmtree(session_dir, ignore_errors=True)

            # Remove from active bots
            del self._active_bots[bot_id]

            # Update Redis
            self.redis_state.unassign_bot(bot_id)

            logger.info(f"Stopped {bot_type} bot {bot_id}")
            return True

        except Exception as e:
            logger.error(f"Error stopping bot {bot_id}: {e}")
            # Still remove from tracking
            self._active_bots.pop(bot_id, None)
            self._slack_handlers.pop(bot_id, None)
            task = self._slack_tasks.pop(bot_id, None)
            if task and not task.done():
                task.cancel()
            self._telegram_apps.pop(bot_id, None)
            self._whatsapp_clients.pop(bot_id, None)
            return False

    async def _stop_all_bots(self) -> None:
        """Stop all active bot connections."""
        bot_ids = list(self._active_bots.keys())
        for bot_id in bot_ids:
            await self._stop_bot(bot_id)

    # ==================== Background Tasks ====================

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to Redis."""
        while not self._is_shutting_down:
            try:
                self.redis_state.send_heartbeat(self.worker_id, self.active_bot_count)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

            await asyncio.sleep(self.config.heartbeat_interval)

    async def _event_listener_loop(self) -> None:
        """Listen for bot lifecycle events from Redis stream."""
        loop = asyncio.get_event_loop()
        while not self._is_shutting_down:
            try:
                # Run blocking Redis call in executor to not block the event loop
                events = await loop.run_in_executor(
                    None,
                    lambda: self.redis_state.read_bot_events(
                        last_id=self._last_event_id,
                        count=10,
                        block=1000,  # 1 second timeout
                    ),
                )

                for event_id, event in events:
                    self._last_event_id = event_id
                    await self._handle_bot_event(event)

            except Exception as e:
                logger.error(f"Event listener error: {e}")
                await asyncio.sleep(1)

    async def _handle_bot_event(self, event: BotEvent) -> None:
        """Handle a bot lifecycle event.

        Args:
            event: Event to handle
        """
        # If the ring is empty (e.g. after a dead-worker cleanup removed us),
        # rebuild it before deciding who owns this bot.
        if not self._hash_ring.ring:
            logger.warning("Hash ring is empty when handling event — rebuilding")
            await self._rebuild_hash_ring()

        # Check if this bot should be managed by this worker
        try:
            assigned_worker = self._hash_ring.get_node(event.bot_id)
        except ValueError:
            logger.warning("No workers in hash ring after rebuild, skipping event")
            return

        if assigned_worker != self.worker_id:
            return  # Not our bot

        async with get_async_session_factory()() as db:
            if event.event_type == BotEventType.ACTIVATE:
                await self._start_bot(event.bot_id, db)
            elif event.event_type == BotEventType.DEACTIVATE:
                await self._stop_bot(event.bot_id)
            elif event.event_type == BotEventType.RESTART:
                await self._stop_bot(event.bot_id)
                await asyncio.sleep(1)
                await self._start_bot(event.bot_id, db)

    async def _command_listener_loop(self) -> None:
        """Listen for direct commands via Redis pub/sub."""
        loop = asyncio.get_event_loop()
        pubsub = self.redis_state.subscribe_to_commands(self.worker_id)

        while not self._is_shutting_down:
            try:
                # Run blocking Redis call in executor to not block the event loop
                message = await loop.run_in_executor(
                    None,
                    lambda: pubsub.get_message(timeout=1.0),
                )
                if message and message["type"] == "message":
                    import json

                    command = json.loads(message["data"])
                    await self._handle_command(command)

            except Exception as e:
                logger.error(f"Command listener error: {e}")
                await asyncio.sleep(1)

        pubsub.close()

    async def _handle_command(self, command: dict[str, Any]) -> None:
        """Handle a direct command from Redis pub/sub.

        Args:
            command: Command data (should have 'action' key)
        """
        action = command.get("action")
        bot_id = command.get("bot_id")

        async with get_async_session_factory()() as db:
            if action == "start_bot" and bot_id:
                await self._start_bot(bot_id, db)
            elif action == "stop_bot" and bot_id:
                await self._stop_bot(bot_id)
            elif action == "restart_bot" and bot_id:
                await self._stop_bot(bot_id)
                await asyncio.sleep(1)
                await self._start_bot(bot_id, db)
            else:
                logger.warning(f"Unknown command: {command}")

    async def _dead_worker_check_loop(self) -> None:
        """Periodically check for dead workers and ensure our assigned bots are running."""
        while not self._is_shutting_down:
            try:
                # Check every 15 seconds
                await asyncio.sleep(15)

                # Find dead workers
                dead_workers = self.redis_state.get_dead_workers(self.config.heartbeat_timeout)

                if dead_workers:
                    logger.info(f"Found {len(dead_workers)} dead workers: {dead_workers}")

                    # Unregister dead workers from Redis
                    for worker_id in dead_workers:
                        self.redis_state.unregister_worker(worker_id)

                    # Rebuild ring from scratch so the current worker is always present
                    await self._rebuild_hash_ring()

                # Always self-heal: start any bots that should be ours but stopped.
                # This handles bots lost to dead-worker redistribution, event-driven
                # stop without a matching activate, or transient startup failures.
                await self._claim_orphaned_bots()

            except Exception as e:
                logger.error(f"Dead worker check error: {e}")

    async def _claim_orphaned_bots(self) -> None:
        """Claim bots that were previously assigned to dead workers."""
        async with get_async_session_factory()() as db:
            all_bot_ids = await self._get_all_active_bot_ids(db)
            my_bots = self._hash_ring.get_keys_for_node(self.worker_id, all_bot_ids)

            for bot_id in my_bots:
                if bot_id not in self._active_bots:
                    # Skip if Redis says a healthy worker already owns this bot — only claim
                    # truly orphaned bots (unassigned or assigned to a now-dead worker).
                    existing = self.redis_state.get_bot_assignment(bot_id)
                    if existing:
                        assigned_worker, _ = existing
                        if assigned_worker != self.worker_id:
                            healthy = self.redis_state.get_healthy_workers(self.config.heartbeat_timeout)
                            if assigned_worker in healthy:
                                logger.debug(f"Bot {bot_id} is owned by healthy worker {assigned_worker}, skipping")
                                continue
                    logger.info(f"Claiming orphaned bot {bot_id}")
                    await self._start_bot(bot_id, db)
