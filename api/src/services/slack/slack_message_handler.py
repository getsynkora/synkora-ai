"""Shared Slack message handler for Socket Mode and Event Mode."""

import asyncio
import json
import logging
import re
from collections.abc import Callable
from typing import Any

_EMOJI_RE = re.compile(r"[^\x00-\x7F]+")


def _to_slack_status(content: str) -> str:
    """
    Convert a stream status string to Slack assistant thread status text.

    Strips emojis and normalises to 'is doing X...' so it reads naturally
    as '<BotName> is searching the web...' in Slack.
    Returns empty string for events that shouldn't surface as a status.
    """
    text = _EMOJI_RE.sub("", content).strip(" .")
    if not text:
        return ""
    text_lower = text.lower()
    # Skip sub-agent lifecycle noise
    if text_lower.startswith(("starting:", "completed:", "starting ", "completed ")):
        return ""
    if not text_lower.endswith("..."):
        text_lower += "..."
    if not text_lower.startswith("is "):
        text_lower = "is " + text_lower
    return text_lower


from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.conversation import Conversation, ConversationStatus
from ...models.message import Message, MessageRole
from ...models.slack_bot import SlackBot, SlackConversation
from ...services.agents.agent_manager import AgentManager

logger = logging.getLogger(__name__)


class SlackMessageHandler:
    """Shared handler for processing Slack messages.

    This class extracts the common message handling logic that is used by both
    Socket Mode (WebSocket) and Event Mode (HTTP webhooks) connections.
    """

    def __init__(self, db_session: AsyncSession, agent_manager: AgentManager | None = None):
        """Initialize the message handler.

        Args:
            db_session: SQLAlchemy async database session
            agent_manager: Optional shared AgentManager instance
        """
        self.db_session = db_session
        self.agent_manager = agent_manager or AgentManager()

    async def handle_message(
        self,
        slack_bot: SlackBot,
        channel_id: str,
        user_id: str,
        text: str,
        message_ts: str | None,
        thread_ts: str | None,
        client: AsyncWebClient,
        say: Callable[..., Any] | None = None,
    ) -> str | None:
        """
        Handle incoming Slack message and generate agent response.

        Args:
            slack_bot: SlackBot instance
            channel_id: Slack channel ID
            user_id: Slack user ID
            text: Message text
            message_ts: Message timestamp
            thread_ts: Thread timestamp (for threaded conversations)
            client: Slack web client
            say: Optional Slack say function (for Socket Mode). If None, uses client.chat_postMessage

        Returns:
            The agent's response text, or None on error
        """
        try:
            # Feedback: intercept 👍/👎 as per-message satisfaction signal
            _stripped = text.strip()
            if _stripped in ("👍", "👎", ":thumbsup:", ":thumbsdown:", "+1", "-1"):
                try:
                    from src.services.eval.feedback_service import record_feedback

                    # Find the most recent assistant message in this channel
                    _msg_result = await self.db_session.execute(
                        select(Message)
                        .join(Message.conversation)
                        .filter(Message.role == "assistant")
                        .order_by(Message.created_at.desc())
                        .limit(1)
                    )
                    _last_msg = _msg_result.scalar_one_or_none()
                    if _last_msg:
                        _rating = 1 if _stripped in ("👍", ":thumbsup:", "+1") else -1
                        record_feedback(
                            message_id=str(_last_msg.id),
                            agent_id=slack_bot.agent_id,
                            tenant_id=slack_bot.tenant_id,
                            channel="slack",
                            rating=_rating,
                        )
                        _ack = "Thanks for the feedback!" if _rating == 1 else "Thanks, I'll try to do better!"
                        if say:
                            await say(_ack)
                        else:
                            await client.chat_postMessage(channel=channel_id, text=_ack, thread_ts=thread_ts)
                        return _ack
                except Exception as _fb_err:
                    logger.debug("Slack feedback intercept failed: %s", _fb_err)

            # HITL: Check if this message is a reply to a pending approval request
            from src.config.redis import get_redis_async
            from src.services.human_approval_service import HumanApprovalService

            _redis = get_redis_async()
            _hitl_key = f"hitl:slack:{slack_bot.agent_id}:{channel_id}"
            _approval_id_str = await _redis.get(_hitl_key)
            if _approval_id_str:
                import uuid as _uuid_mod

                _approval_svc = HumanApprovalService(self.db_session)
                _result = await _approval_svc.handle_reply(_uuid_mod.UUID(_approval_id_str), text, self.db_session)
                if _result == "approved":
                    _reply = "Got it! Proceeding with the action."
                elif _result == "rejected":
                    _reply = "Got it! Action cancelled."
                elif _result == "feedback":
                    _reply = "Got it! I'll revise and ask again shortly."
                elif _result == "unclear":
                    _reply = "I didn't quite understand. Reply *yes* to proceed, *no* to cancel, or describe changes you want."
                else:  # expired, not_found
                    _reply = "This approval request has expired. The next scheduled run will ask again."

                if _result != "unclear":
                    # Clear the Redis key so subsequent messages are handled normally
                    await _redis.delete(_hitl_key)

                await client.chat_postMessage(
                    channel=channel_id,
                    text=_reply,
                    thread_ts=thread_ts or message_ts,
                )
                return _reply

            # Get or create conversation mapping
            conversation = await self._get_or_create_conversation(
                slack_bot=slack_bot, channel_id=channel_id, user_id=user_id, thread_ts=thread_ts
            )

            # Block AI while a human operator is handling this conversation
            if getattr(conversation, "handoff_status", None) == "active":
                _wait = "A human support agent is currently handling this conversation. They will respond shortly."
                if say:
                    await say(_wait)
                else:
                    await client.chat_postMessage(channel=channel_id, text=_wait, thread_ts=thread_ts)
                return _wait

            # Fetch user and channel info in parallel (suppress individual failures)
            user_info: Any
            channel_info: Any
            user_info, channel_info = await asyncio.gather(
                client.users_info(user=user_id),
                client.conversations_info(channel=channel_id),
                return_exceptions=True,
            )
            if isinstance(user_info, Exception):
                logger.warning(f"Could not fetch user info for {user_id}: {user_info}. Missing users:read scope?")
                user_name = user_id
            else:
                user_name = user_info["user"]["real_name"] or user_info["user"]["name"]
            if isinstance(channel_info, Exception):
                logger.warning(
                    f"Could not fetch channel info for {channel_id}: {channel_info}. Missing channels:read scope?"
                )
                channel_name = channel_id
            else:
                channel_name = channel_info.get("channel", {}).get("name", channel_id)

            # Remove bot mention from text if present
            clean_text = self._remove_bot_mention(text, slack_bot.slack_app_id)

            logger.info(f"Slack message: Channel: #{channel_name} (ID: {channel_id}), Message TS: {message_ts}")

            # The agent receives only the clean user text — no raw Slack metadata.
            # Injecting channel IDs and timestamps into the message confused the agent
            # into thinking it received a forwarded Slack notification rather than a
            # direct message, causing it to say it "lacks a Slack tool to reply."
            # Slack context (channel, user) is passed via shared_state for tool use.
            context_message = clean_text

            # Save user message with enhanced metadata
            user_message = Message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=context_message,
                message_metadata={
                    "slack_user_id": user_id,
                    "slack_user_name": user_name,
                    "slack_channel_id": channel_id,
                    "slack_channel_name": channel_name,
                    "slack_message_ts": message_ts,
                    "slack_thread_ts": thread_ts,
                    "original_text": text,
                },
            )
            self.db_session.add(user_message)
            conversation.increment_message_count()
            await self.db_session.flush()

            # Use native Slack status indicator
            from .slack_status_service import SlackStatusService

            status_service = SlackStatusService(client)
            effective_thread_ts = thread_ts or message_ts
            await status_service.set_thinking(channel_id, effective_thread_ts)

            # Get agent response using the existing chat infrastructure
            from ...models.agent import Agent
            from ...services.agents.agent_loader_service import AgentLoaderService
            from ...services.agents.chat_service import ChatService
            from ...services.agents.chat_stream_service import ChatStreamService
            from ...services.conversation_service import ConversationService

            # Get agent name from database
            agent = await self.db_session.get(Agent, slack_bot.agent_id)
            if not agent:
                raise ValueError(f"Agent {slack_bot.agent_id} not found")

            # Load conversation history with caching support
            conversation_history = await ConversationService.get_conversation_history_cached(
                db=self.db_session,
                conversation_id=conversation.id,
                limit=30,
            )
            logger.info(f"Loaded {len(conversation_history)} messages from conversation history")

            # Fetch Slack thread history to provide full context
            thread_context = await self._fetch_thread_context(client, channel_id, thread_ts, message_ts)

            # Merge Slack thread context with database conversation history
            if thread_context and len(thread_context) > len(conversation_history):
                logger.info(f"Using Slack thread context ({len(thread_context)} messages) instead of DB history")
                conversation_history = thread_context

            # Initialize the chat stream service
            chat_stream_service = ChatStreamService(
                agent_loader=AgentLoaderService(self.agent_manager), chat_service=ChatService()
            )

            # Collect the streamed response + chart events
            response_chunks = []
            chart_events: list[dict] = []
            async for event_data in chat_stream_service.stream_agent_response(
                agent_name=agent.slug or agent.agent_name,
                message=context_message,
                conversation_history=conversation_history,
                conversation_id=str(conversation.id),
                attachments=None,
                llm_config_id=None,
                db=self.db_session,
                user_id=str(slack_bot.created_by) if slack_bot.created_by else None,
                tenant_id=slack_bot.tenant_id,
                trigger_source="slack",
                trigger_detail=f"#{channel_name}" if channel_name else f"#{channel_id}",
                shared_state={
                    "slack_message_ts": message_ts,
                    "slack_channel_id": channel_id,
                    "slack_channel_name": channel_name,
                    "slack_user_id": user_id,
                    "slack_user_name": user_name,
                },
            ):
                if not event_data.startswith("data: "):
                    continue
                try:
                    event_json = json.loads(event_data[6:])
                    event_type = event_json.get("type")

                    if event_type == "chunk":
                        response_chunks.append(event_json.get("content", ""))

                    elif event_type == "error":
                        err_content = event_json.get("content", "An error occurred")
                        logger.error(f"Agent stream error: {err_content}")
                        response_chunks.append(err_content)

                    elif event_type == "chart":
                        chart_obj = event_json.get("chart") or event_json
                        if chart_obj and isinstance(chart_obj, dict):
                            chart_events.append(chart_obj)

                    elif event_type == "status":
                        # e.g. "💭 Thinking...", "📚 Searching knowledge bases..."
                        raw = event_json.get("content", "")
                        slack_status = _to_slack_status(raw)
                        if slack_status:
                            asyncio.ensure_future(
                                status_service.set_status(channel_id, effective_thread_ts, slack_status)
                            )

                    elif event_type == "tool_call" and event_json.get("status") == "started":
                        # e.g. description="Searching the web: AI trends"
                        desc = event_json.get("description", "")
                        if desc:
                            slack_status = f"is {desc.lower()}..."
                            asyncio.ensure_future(
                                status_service.set_status(channel_id, effective_thread_ts, slack_status)
                            )
                except Exception:
                    pass

            agent_response = "".join(response_chunks)

            # Handle empty response
            if not agent_response or not agent_response.strip():
                logger.warning("Agent returned empty response, using fallback message")
                agent_response = "Done! I've processed your request."

            # Send response using appropriate method
            await self._send_response(
                client=client,
                say=say,
                channel_id=channel_id,
                thread_ts=thread_ts or message_ts,
                response=agent_response,
            )

            # Upload charts as images (fire-and-forget, errors are non-fatal)
            if chart_events:
                asyncio.ensure_future(
                    self._upload_charts(
                        client=client,
                        channel_id=channel_id,
                        thread_ts=thread_ts or message_ts,
                        charts=chart_events,
                    )
                )

            # Post metadata footer: row counts, data sources extracted from response
            metadata_ctx = self._build_metadata_context(agent_response)
            if metadata_ctx:
                try:
                    await client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts or message_ts,
                        blocks=[metadata_ctx],
                        text="Query metadata",
                    )
                except Exception as e:
                    logger.warning(f"Failed to post metadata footer: {e}")

            # Save agent response
            assistant_message = Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=agent_response,
            )
            self.db_session.add(assistant_message)
            conversation.increment_message_count()
            await self.db_session.commit()

            # If this is a DM reply, check whether the bot previously sent this DM
            # on behalf of someone else and notify them immediately.
            if channel_id.startswith("D"):
                await self._notify_requester_if_callback(
                    client=client,
                    slack_bot=slack_bot,
                    dm_channel_id=channel_id,
                    replier_name=user_name,
                    reply_text=clean_text,
                    current_message_ts=message_ts,
                )

            return agent_response

        except Exception as e:
            logger.error(f"Error handling Slack message: {str(e)}")
            await self.db_session.rollback()
            # Send error message
            error_msg = "Sorry, I encountered an error processing your message. Please try again."
            await self._send_response(
                client=client,
                say=say,
                channel_id=channel_id,
                thread_ts=thread_ts,
                response=error_msg,
            )
            return None

    async def _send_response(
        self,
        client: AsyncWebClient,
        say: Callable[..., Any] | None,
        channel_id: str,
        thread_ts: str | None,
        response: str,
    ) -> None:
        """Send response to Slack using appropriate method.

        Args:
            client: Slack web client
            say: Optional Slack say function (from Socket Mode)
            channel_id: Channel to send to
            thread_ts: Thread timestamp (for threaded replies)
            response: Response text
        """
        from .formatters import chunk_blocks, create_slack_blocks, format_text_for_slack

        # Create blocks from the response
        blocks = create_slack_blocks(response)

        if not blocks:
            blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": response}}]

        # Check if we need to chunk the response
        if len(blocks) > 50:  # Slack's block limit
            block_chunks = chunk_blocks(blocks)

            for i, chunk in enumerate(block_chunks):
                fallback_text = (
                    format_text_for_slack(response) if i == 0 else f"(continued {i + 1}/{len(block_chunks)})"
                )
                if say:
                    await say(text=fallback_text, blocks=chunk, thread_ts=thread_ts)
                else:
                    await client.chat_postMessage(
                        channel=channel_id,
                        text=fallback_text,
                        blocks=chunk,
                        thread_ts=thread_ts,
                    )
        else:
            fallback_text = format_text_for_slack(response)
            if say:
                await say(text=fallback_text, blocks=blocks, thread_ts=thread_ts)
            else:
                await client.chat_postMessage(
                    channel=channel_id,
                    text=fallback_text,
                    blocks=blocks,
                    thread_ts=thread_ts,
                )

    async def _fetch_thread_context(
        self,
        client: AsyncWebClient,
        channel_id: str,
        thread_ts: str | None,
        message_ts: str | None,
    ) -> list[dict[str, str]]:
        """Fetch thread history from Slack to provide context.

        Args:
            client: Slack web client
            channel_id: Channel ID
            thread_ts: Thread timestamp
            message_ts: Current message timestamp

        Returns:
            List of messages in thread context format
        """
        thread_context = []

        # For DM channels: fetch channel history instead of thread replies
        if channel_id.startswith("D"):
            try:
                history = await client.conversations_history(channel=channel_id, limit=50)
                for msg in reversed(history.get("messages", [])):
                    if msg.get("ts") == message_ts:
                        continue
                    msg_text = msg.get("text", "").strip()
                    if not msg_text:
                        continue
                    if msg.get("bot_id") or msg.get("subtype") == "bot_message":
                        thread_context.append({"role": "assistant", "content": msg_text})
                    else:
                        thread_context.append({"role": "user", "content": msg_text})
                logger.info(f"Built DM history context with {len(thread_context)} messages")
            except Exception as e:
                logger.warning(f"Failed to fetch DM history: {e}")
            return thread_context

        effective_thread_ts = thread_ts if thread_ts and thread_ts != message_ts else None

        if not effective_thread_ts:
            return thread_context

        try:
            thread_replies = await client.conversations_replies(
                channel=channel_id,
                ts=effective_thread_ts,
                limit=50,
                inclusive=True,
            )

            if not thread_replies.get("ok") or not thread_replies.get("messages"):
                return thread_context

            thread_messages = thread_replies["messages"]
            logger.info(f"Fetched {len(thread_messages)} messages from Slack thread {effective_thread_ts}")

            # Batch fetch all unique user IDs
            user_ids_to_fetch = set()
            for msg in thread_messages:
                if msg.get("ts") == message_ts:
                    continue
                if not msg.get("bot_id") and msg.get("user") and msg.get("text", "").strip():
                    user_ids_to_fetch.add(msg.get("user"))

            # Fetch all users in parallel
            user_map: dict[str, str] = {}
            if user_ids_to_fetch:
                user_tasks = [client.users_info(user=uid) for uid in user_ids_to_fetch]
                user_results = await asyncio.gather(*user_tasks, return_exceptions=True)
                for result in user_results:
                    if isinstance(result, Exception):
                        continue
                    user_data = result.get("user", {})
                    uid = user_data.get("id")
                    if uid:
                        user_map[uid] = user_data.get("real_name") or user_data.get("name", "User")

            # Build thread context
            for msg in thread_messages:
                msg_ts = msg.get("ts")
                if msg_ts == message_ts:
                    continue

                msg_text = msg.get("text", "")
                msg_user = msg.get("user")
                bot_id = msg.get("bot_id")

                if not msg_text.strip():
                    continue

                if bot_id:
                    thread_context.append({"role": "assistant", "content": msg_text})
                else:
                    sender_name = user_map.get(msg_user, "User") if msg_user else "User"
                    thread_context.append({"role": "user", "content": f"[{sender_name}]: {msg_text}"})

            logger.info(f"Built thread context with {len(thread_context)} messages")

        except Exception as e:
            logger.warning(f"Failed to fetch Slack thread history: {e}")

        return thread_context

    async def _get_or_create_conversation(
        self, slack_bot: SlackBot, channel_id: str, user_id: str, thread_ts: str | None
    ) -> Conversation:
        """Get existing conversation or create new one."""
        is_dm = channel_id.startswith("D")

        if is_dm:
            # One conversation per user per DM channel — ignore thread_ts
            stmt = select(SlackConversation).where(
                SlackConversation.slack_bot_id == slack_bot.id,
                SlackConversation.slack_channel_id == channel_id,
                SlackConversation.slack_user_id == user_id,
            )
        else:
            # Channel messages: separate conversation per thread
            stmt = select(SlackConversation).where(
                SlackConversation.slack_bot_id == slack_bot.id,
                SlackConversation.slack_channel_id == channel_id,
                SlackConversation.slack_user_id == user_id,
                SlackConversation.slack_thread_ts == thread_ts,
            )
        result = await self.db_session.execute(stmt)
        slack_conv = result.scalars().first()

        if slack_conv:
            return await self.db_session.get(Conversation, slack_conv.conversation_id)

        # Create new conversation
        conversation = Conversation(
            agent_id=slack_bot.agent_id,
            name=f"Slack conversation with {user_id}",
            status=ConversationStatus.ACTIVE,
            source="slack",
        )
        self.db_session.add(conversation)
        await self.db_session.commit()
        await self.db_session.refresh(conversation)

        # Create mapping
        slack_conv = SlackConversation(
            slack_bot_id=slack_bot.id,
            conversation_id=conversation.id,
            slack_channel_id=channel_id,
            slack_user_id=user_id,
            slack_thread_ts=thread_ts,
        )
        self.db_session.add(slack_conv)
        await self.db_session.commit()

        return conversation

    async def _notify_requester_if_callback(
        self,
        client: AsyncWebClient,
        slack_bot: SlackBot,
        dm_channel_id: str,
        replier_name: str,
        reply_text: str,
        current_message_ts: str | None = None,
    ) -> None:
        """Check Redis for a report-back callback and notify the requester if one exists.

        When the agent previously sent a DM on behalf of a user (e.g., Raju asked the
        bot to reach out to Goldius), it stores a callback in Redis. This method checks
        for that callback and immediately posts an update to the requester's channel
        so they don't have to ask 'did they reply?'.
        """
        try:
            import json

            from ...config.redis import get_redis_async

            redis = get_redis_async()
            key = f"slack:dm_callback:{slack_bot.agent_id}:{dm_channel_id}"
            data = await redis.get(key)
            if not data:
                return

            callback = json.loads(data)
            requester_channel_id = callback.get("requester_channel_id")
            if not requester_channel_id:
                return

            # Skip if this is the same message turn that stored the callback (e.g. self-DM
            # where requester and DM target are the same person/channel).
            request_message_ts = callback.get("request_message_ts")
            if request_message_ts and current_message_ts and request_message_ts == current_message_ts:
                logger.info(f"Skipping report-back: callback was stored this turn (ts={current_message_ts})")
                return

            # One-time notification — delete the callback so repeat messages
            # in the same DM don't keep pinging the requester.
            await redis.delete(key)

            notification = f"*[Update]* *{replier_name} replied:* {reply_text}"
            await client.chat_postMessage(channel=requester_channel_id, text=notification)
            logger.info(f"Notified {requester_channel_id}: {replier_name} replied in {dm_channel_id}")
        except Exception as e:
            logger.warning(f"Failed to send report-back notification: {e}")

    async def _upload_charts(
        self,
        client: AsyncWebClient,
        channel_id: str,
        thread_ts: str | None,
        charts: list[dict],
    ) -> None:
        """Render each chart to PNG and upload to Slack."""
        try:
            from .slack_chart_renderer import render_chart_to_png
        except ImportError:
            logger.warning("slack_chart_renderer not available — skipping chart upload")
            return

        for i, chart in enumerate(charts):
            try:
                png_bytes = render_chart_to_png(chart)
                if not png_bytes:
                    continue

                title = chart.get("title") or f"Chart {i + 1}"
                await client.files_upload_v2(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    content=png_bytes,
                    filename=f"chart_{i + 1}.png",
                    title=title,
                )
                logger.info(f"Uploaded chart '{title}' to Slack channel {channel_id}")
            except Exception as e:
                logger.warning(f"Failed to upload chart {i}: {e}")

    def _build_metadata_context(self, response_text: str) -> dict | None:
        """Extract query metadata from response text and build a Slack context block."""
        parts: list[dict] = []

        # Row count  e.g. "8 rows", "1 record", "Found 42 results"
        row_match = re.search(
            r"\b(\d[\d,]*)\s+(?:rows?|records?|results?|accounts?|entries|items?)\b",
            response_text,
            re.IGNORECASE,
        )
        if row_match:
            count = row_match.group(1)
            parts.append({"type": "mrkdwn", "text": f":bar_chart: *{count} rows*"})

        # Data source hints  e.g. "BigQuery", "Supabase", "PostgreSQL", "clientdb.account"
        source_match = re.search(
            r"\b(BigQuery|Supabase|PostgreSQL|MySQL|Snowflake|ClickHouse|Elasticsearch|MongoDB|DuckDB)\b",
            response_text,
            re.IGNORECASE,
        )
        if source_match:
            parts.append({"type": "mrkdwn", "text": f":database: {source_match.group(1)}"})

        # Table / dataset reference  e.g.  "clientdb.account"  or  "schema.table"
        table_match = re.search(r"\b([\w-]+\.[\w-]+(?:\.[\w-]+)?)\b", response_text)
        if table_match:
            tbl = table_match.group(1)
            # Skip obvious non-table patterns (domain names, version strings)
            if "." in tbl and not any(tbl.endswith(s) for s in (".com", ".io", ".ai", ".org")):
                parts.append({"type": "mrkdwn", "text": f"`{tbl}`"})

        if not parts:
            return None

        return {"type": "context", "elements": parts[:10]}

    def _remove_bot_mention(self, text: str, app_id: str) -> str:
        """Remove bot mention from message text."""
        import re

        pattern = f"<@{app_id}>"
        return re.sub(pattern, "", text).strip()

    async def _extract_user_mentions(self, text: str, client: AsyncWebClient) -> list[dict[str, str]]:
        """Extract user mentions from message text and filter out bots.

        Args:
            text: Message text containing mentions
            client: Slack web client

        Returns:
            List of dicts with user info (id, name, is_bot=False only)
        """
        import re

        mention_pattern = r"<@([UW][A-Z0-9]+)>"
        user_ids = re.findall(mention_pattern, text)

        if not user_ids:
            return []

        # Fetch all mentioned users in parallel
        unique_user_ids = list(set(user_ids))
        user_tasks = [client.users_info(user=uid) for uid in unique_user_ids]
        user_results = await asyncio.gather(*user_tasks, return_exceptions=True)

        mentioned_users = []
        for i, result in enumerate(user_results):
            if isinstance(result, Exception):
                logger.warning(f"Could not get info for user {unique_user_ids[i]}: {result}")
                continue

            user_data = result.get("user", {})
            user_id = user_data.get("id")

            # Skip bot users
            if user_data.get("is_bot") or user_data.get("is_app_user"):
                logger.info(f"Skipping bot user: {user_data.get('name')} ({user_id})")
                continue

            mentioned_users.append(
                {"id": user_id, "name": user_data.get("real_name") or user_data.get("name", "Unknown")}
            )

        return mentioned_users
