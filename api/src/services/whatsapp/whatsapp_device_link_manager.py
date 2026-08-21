"""WhatsApp device-link bot manager.

Restores neonize sessions from DB, keeps clients connected, and routes
incoming WhatsApp messages to the agent chat pipeline.
"""

import asyncio
import base64
import json
import logging
import shutil
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.conversation import Conversation, ConversationStatus
from ...models.message import Message
from ...models.whatsapp_bot import WhatsAppBot, WhatsAppConversation
from ...services.agents.security import decrypt_value

logger = logging.getLogger(__name__)

# Possible MessageEv names across neonize versions
_MESSAGE_EV_CANDIDATES = ["MessageEv", "MessageEvent"]


class WhatsAppDeviceLinkManager:
    """
    Manages persistent neonize clients for all active device-link bots.

    On startup, loads every active device_link WhatsAppBot from DB, restores
    its neonize SQLite session to a temp dir, and starts a background thread
    running client.connect().  Incoming messages are bridged back to the
    asyncio event loop via asyncio.run_coroutine_threadsafe().
    """

    # bot_id (str) -> {client, thread, session_dir, agent_id}
    _running: dict[str, dict] = {}
    _loop: asyncio.AbstractEventLoop | None = None

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    @classmethod
    def set_event_loop(cls, loop: asyncio.AbstractEventLoop) -> None:
        """Store the running asyncio loop so background threads can schedule coroutines."""
        cls._loop = loop

    @classmethod
    async def start_all_active_bots(cls, db: AsyncSession) -> None:
        """Called at server startup — restore and connect every active device_link bot."""
        cls._loop = asyncio.get_running_loop()

        result = await db.execute(
            select(WhatsAppBot).where(
                WhatsAppBot.connection_type == "device_link",
                WhatsAppBot.is_active.is_(True),
                WhatsAppBot.session_data.isnot(None),
            )
        )
        bots = result.scalars().all()
        logger.info(f"Starting {len(bots)} active device-link WhatsApp bot(s)")

        for bot in bots:
            try:
                await cls._start_bot(bot)
            except Exception:
                logger.exception(f"Failed to start device-link bot {bot.id} ({bot.bot_name})")

    @classmethod
    async def start_bot_by_id(cls, bot_id: UUID, db: AsyncSession) -> None:
        """Start (or restart) a single bot — called from the API when a bot is activated."""
        result = await db.execute(select(WhatsAppBot).where(WhatsAppBot.id == bot_id))
        bot = result.scalar_one_or_none()
        if not bot:
            raise ValueError(f"Bot {bot_id} not found")
        if bot.connection_type != "device_link":
            raise ValueError("Only device_link bots use this manager")
        await cls._start_bot(bot)

    @classmethod
    async def stop_bot_by_id(cls, bot_id: str) -> None:
        """Stop a running bot client and clean up its temp session dir."""
        entry = cls._running.pop(bot_id, None)
        if entry is None:
            return
        client = entry.get("client")
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                logger.debug(f"Error disconnecting bot {bot_id}", exc_info=True)
        session_dir = entry.get("session_dir")
        if session_dir:
            try:
                shutil.rmtree(session_dir, ignore_errors=True)
            except Exception:
                pass
        logger.info(f"Stopped device-link bot {bot_id}")

    @classmethod
    async def stop_all(cls) -> None:
        """Graceful shutdown — stop all running bots."""
        for bot_id in list(cls._running.keys()):
            await cls.stop_bot_by_id(bot_id)

    # -------------------------------------------------------------------------
    # Internal: restore session and start client thread
    # -------------------------------------------------------------------------

    @classmethod
    async def _start_bot(cls, bot: WhatsAppBot) -> None:
        bot_id = str(bot.id)

        # Already running — skip
        if bot_id in cls._running:
            logger.debug(f"Bot {bot_id} already running, skipping")
            return

        # Decrypt and parse stored session
        raw_json = decrypt_value(bot.session_data)
        if not raw_json:
            logger.warning(f"Bot {bot_id} has no decryptable session_data, skipping")
            return
        try:
            session_payload = json.loads(raw_json)
            db_bytes = base64.b64decode(session_payload["session_db"])
        except Exception:
            logger.exception(f"Failed to parse session_data for bot {bot_id}")
            return

        # Write SQLite to temp dir
        session_dir = tempfile.mkdtemp(prefix=f"neonize_bot_{bot_id[:8]}_")
        db_path = str(Path(session_dir) / "session.db")
        Path(db_path).write_bytes(db_bytes)

        cls._running[bot_id] = {
            "client": None,
            "session_dir": session_dir,
            "agent_id": str(bot.agent_id),
            "bot_name": bot.bot_name,
        }

        agent_id = str(bot.agent_id)

        def _run() -> None:
            try:
                import neonize.events as neonize_events  # type: ignore[import]
                from neonize.client import NewClient  # type: ignore[import]
            except Exception:
                logger.exception(f"neonize import failed for bot {bot_id}")
                cls._running.pop(bot_id, None)
                shutil.rmtree(session_dir, ignore_errors=True)
                return

            # Find MessageEv class
            message_ev = None
            for name in _MESSAGE_EV_CANDIDATES:
                message_ev = getattr(neonize_events, name, None)
                if message_ev is not None:
                    break

            try:
                client = NewClient(db_path)
                cls._running[bot_id]["client"] = client

                if message_ev is not None:

                    @client.event(message_ev)
                    def _on_message(cli, evt) -> None:
                        _handle_message(cli, evt)

                logger.info(f"Connecting device-link bot {bot_id} ({bot.bot_name})")
                client.connect()

            except Exception:
                logger.exception(f"Neonize client error for bot {bot_id}")
            finally:
                # Clean up if the thread exits (disconnected / error)
                cls._running.pop(bot_id, None)
                shutil.rmtree(session_dir, ignore_errors=True)
                logger.info(f"Device-link bot {bot_id} thread exited")

        def _handle_message(cli, evt) -> None:
            """Called in the neonize background thread — bridge to asyncio."""
            try:
                # Skip messages we sent
                is_from_me = False
                try:
                    is_from_me = evt.Info.MessageSource.IsFromMe
                except Exception:
                    pass
                if is_from_me:
                    return

                # Extract text
                text = _extract_text(evt)
                if not text:
                    return

                # Extract sender phone and JID server
                sender_phone = _extract_sender_phone(evt)
                if not sender_phone:
                    return
                sender_server = _extract_sender_jid_server(evt)

                # Schedule the async handler on the main event loop
                loop = cls._loop
                if loop is None or not loop.is_running():
                    logger.warning(f"No event loop available for bot {bot_id}")
                    return

                future = asyncio.run_coroutine_threadsafe(
                    _process_message_async(cli, bot_id, agent_id, sender_phone, sender_server, text),
                    loop,
                )
                # Log any exception from the coroutine
                future.add_done_callback(
                    lambda f: logger.exception(f"Message processing error for bot {bot_id}") if f.exception() else None
                )

            except Exception:
                logger.exception(f"Error in message handler for bot {bot_id}")

        thread = threading.Thread(target=_run, daemon=True, name=f"wa-bot-{bot_id[:8]}")
        thread.start()
        logger.info(f"Started device-link bot thread for {bot_id} ({bot.bot_name})")


# -------------------------------------------------------------------------
# Helpers (module-level to keep class clean)
# -------------------------------------------------------------------------


def _extract_text(evt) -> str:
    """Pull plain text from a neonize MessageEv."""
    try:
        msg = evt.Message
        # Log all non-default fields for debugging
        try:
            all_fields = [(f.name, getattr(msg, f.name, None)) for f in msg.DESCRIPTOR.fields]
            non_empty = [(k, v) for k, v in all_fields if v and str(v) not in ("", "0", "False", "b''")]
            logger.debug(f"Message fields: {non_empty}")
        except Exception:
            logger.debug(f"Message repr: {msg!r}")

        # Simple text message
        text = getattr(msg, "conversation", None) or getattr(msg, "Conversation", None)
        if text:
            return str(text).strip()
        # Extended text (links, formatting)
        ext = getattr(msg, "extendedTextMessage", None) or getattr(msg, "ExtendedTextMessage", None)
        if ext:
            text = getattr(ext, "text", None) or getattr(ext, "Text", None)
            if text:
                return str(text).strip()
        # Ephemeral/view-once wrapper
        ephemeral = getattr(msg, "ephemeralMessage", None) or getattr(msg, "EphemeralMessage", None)
        if ephemeral:
            inner = getattr(ephemeral, "message", None) or getattr(ephemeral, "Message", None)
            if inner:
                text = getattr(inner, "conversation", None) or getattr(inner, "Conversation", None)
                if text:
                    return str(text).strip()
    except Exception:
        logger.debug("_extract_text exception", exc_info=True)
    return ""


def _extract_sender_phone(evt) -> str | None:
    """Extract the sender's user ID (phone number or LID) as a plain string."""
    try:
        sender_jid = evt.Info.MessageSource.Sender
        user = getattr(sender_jid, "User", None)
        if user and str(user) not in ("", "0", "None"):
            return str(user)
        # Fallback: regex on string representation
        import re

        match = re.search(r'User:\s*"(\d+)"', str(sender_jid))
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def _extract_sender_jid_server(evt) -> str:
    """Extract the JID server component from the sender (e.g. 's.whatsapp.net' or 'lid')."""
    try:
        sender_jid = evt.Info.MessageSource.Sender
        server = getattr(sender_jid, "Server", None)
        if server and str(server) not in ("", "None"):
            return str(server)
        # Fallback: check string representation for @lid or @s.whatsapp.net
        jid_str = str(sender_jid)
        if "lid" in jid_str:
            return "lid"
    except Exception:
        pass
    return "s.whatsapp.net"


async def _process_message_async(
    cli, bot_id: str, agent_id: str, sender_phone: str, sender_server: str, text: str
) -> None:
    """Async: get or create conversation, call agent, send reply."""
    from ...core.database import get_async_session_factory
    from ...models.agent import Agent
    from ...services.agents.agent_loader_service import AgentLoaderService
    from ...services.agents.agent_manager import AgentManager
    from ...services.agents.chat_service import ChatService
    from ...services.agents.chat_stream_service import ChatStreamService
    from ...services.conversation_service import ConversationService

    AsyncSessionLocal = get_async_session_factory()
    async with AsyncSessionLocal() as db:
        try:
            bot = await db.get(WhatsAppBot, UUID(bot_id))
            if not bot or not bot.is_active:
                return

            agent = await db.get(Agent, UUID(agent_id))
            if not agent:
                logger.error(f"Agent {agent_id} not found for bot {bot_id}")
                return

            # Get or create conversation
            conversation = await _get_or_create_conversation(db, bot, sender_phone, message_text=text)

            # Save user message
            user_msg = Message(
                conversation_id=conversation.id,
                role="USER",
                content=text,
                message_metadata={"whatsapp_user": sender_phone, "connection_type": "device_link"},
            )
            db.add(user_msg)
            conversation.increment_message_count()
            await db.commit()

            # Load conversation history
            history = await ConversationService.get_conversation_history_cached(
                db=db,
                conversation_id=conversation.id,
                limit=30,
            )

            # Call the agent via ChatStreamService (same as Telegram polling service)
            chat_stream_service = ChatStreamService(
                agent_loader=AgentLoaderService(AgentManager()),
                chat_service=ChatService(),
            )

            chunks = []
            async for event_data in chat_stream_service.stream_agent_response(
                agent_name=agent.slug or agent.agent_name,
                message=text,
                conversation_history=history,
                conversation_id=str(conversation.id),
                attachments=None,
                llm_config_id=None,
                db=db,
            ):
                if event_data.startswith("data: "):
                    try:
                        ev = json.loads(event_data[6:])
                        if ev.get("type") == "chunk":
                            chunks.append(ev.get("content", ""))
                    except Exception:
                        pass

            response_text = "".join(chunks).strip()
            if not response_text:
                return

            # Send reply via neonize — run in executor so it doesn't block the event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _send_reply, cli, sender_phone, sender_server, response_text)

            # Save assistant message
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="ASSISTANT",
                content=response_text,
            )
            db.add(assistant_msg)
            conversation.increment_message_count()
            bot.last_message_at = datetime.now(UTC)
            await db.commit()

            logger.info(f"Replied to {sender_phone} via device-link bot {bot_id}")

        except Exception:
            logger.exception(f"Error processing message for bot {bot_id} from {sender_phone}")
            await db.rollback()


async def _get_or_create_conversation(
    db: AsyncSession, bot: WhatsAppBot, user_phone: str, message_text: str | None = None
) -> Conversation:
    result = await db.execute(
        select(WhatsAppConversation).where(
            WhatsAppConversation.whatsapp_bot_id == bot.id,
            WhatsAppConversation.whatsapp_user_id == user_phone,
        )
    )
    wa_conv = result.scalars().first()
    if wa_conv:
        conv = await db.get(Conversation, wa_conv.conversation_id)
        if conv:
            return conv

    conv_name = (
        message_text.strip()[:60] if message_text and message_text.strip() else f"WhatsApp conversation with {user_phone}"
    )
    conv = Conversation(
        agent_id=bot.agent_id,
        name=conv_name,
        status=ConversationStatus.ACTIVE,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    wa_conv = WhatsAppConversation(
        whatsapp_bot_id=bot.id,
        conversation_id=conv.id,
        whatsapp_user_id=user_phone,
    )
    db.add(wa_conv)
    await db.commit()

    return conv


def _send_reply(cli, to_phone: str, sender_server: str, text: str) -> None:
    """Send a text message via neonize (called from async context but neonize is sync)."""
    msg = text[:4096]
    try:
        from neonize.proto.Neonize_pb2 import JID  # type: ignore[import]

        jid = JID(User=to_phone, Server=sender_server, RawAgent=0, Device=0, Integrator=0)
    except Exception:
        logger.exception(f"Failed to build JID for {to_phone}")
        return

    # Correct import path discovered: waE2E.WAWebProtobufsE2E_pb2.Message
    try:
        from waE2E.WAWebProtobufsE2E_pb2 import Message as WAMessage  # type: ignore[import]

        cli.send_message(jid, WAMessage(conversation=msg))
        logger.info(f"Sent reply to {to_phone}")
        return
    except Exception as e:
        logger.warning(f"WAWebProtobufsE2E_pb2.Message failed: {type(e).__name__}: {e}")

    # Fallback via neonize.utils.message re-export
    try:
        from neonize.utils.message import Message as WAMessage  # type: ignore[import]

        cli.send_message(jid, WAMessage(conversation=msg))
        logger.info(f"Sent reply to {to_phone} via utils.Message")
        return
    except Exception as e:
        logger.warning(f"utils.Message failed: {type(e).__name__}: {e}")

    logger.error(f"All neonize send_message variants failed for {to_phone}")
