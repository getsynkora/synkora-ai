"""Shared Slack message handler for Socket Mode and Event Mode."""

import asyncio
import json
import logging
import re
from collections.abc import Callable
from typing import Any

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.conversation import Conversation, ConversationStatus
from ...models.message import Message, MessageRole
from ...models.slack_bot import SlackBot, SlackConversation
from ...services.agents.agent_manager import AgentManager
from .slack_status_service import SlackStatusService

logger = logging.getLogger(__name__)

_EMOJI_RE = re.compile(r"[^\x00-\x7F]+")

# Tools that actually execute a data query and return row-level results. The metadata
# footer (row counts / data source / table name) is only meaningful when one of these
# ran during the turn — otherwise regex-scanning the response text produces false
# positives on any text that merely mentions a DB product name or contains a
# version-number-like token (e.g. a PR description mentioning "Supabase" as a
# technology, or a "1.6" version string).
_DATABASE_QUERY_TOOLS = {"internal_query_database", "internal_query_and_chart"}


def _to_tool_status(description: str) -> str:
    """
    Convert a tool-call description into natural Slack assistant status text.

    Strips emojis and normalises to 'is doing x...' so it reads as
    '<BotName> is searching the web...' in the native Slack status indicator.
    Truncated to fit assistant.threads.setStatus's requirement that each
    loading message be under 51 characters.
    """
    MAX_LEN = 50
    text = _EMOJI_RE.sub("", description).strip(" .")
    if not text:
        return ""
    text = text[0].lower() + text[1:]
    if not text.lower().startswith("is "):
        text = "is " + text
    text = text.removesuffix("...").rstrip(" .")
    suffix = "..."
    available = MAX_LEN - len(suffix)
    if len(text) > available:
        text = text[:available].rstrip()
    return text + suffix


def _convert_image_blocks_to_links(blocks: list[dict]) -> list[dict]:
    """Convert `image` blocks to plain clickable-link section blocks.

    Slack renders `image` blocks by having its own servers fetch `image_url`
    directly, which fails with `invalid_blocks: downloading image failed` when
    the URL isn't reachable from Slack's infrastructure (e.g. a local-dev
    presigned URL). Used as a fallback so the message still gets delivered.
    """
    converted = []
    for block in blocks:
        if block.get("type") == "image" and block.get("image_url"):
            alt_text = block.get("alt_text") or "image"
            converted.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": f"<{block['image_url']}|{alt_text}>"}}
            )
        else:
            converted.append(block)
    return converted


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
            # Block Slack Connect (externally-shared) channels unless explicitly allowed.
            # is_ext_shared = true external company; is_org_shared = same Enterprise Grid
            # org (not external) and must NOT be blocked.
            channel_info: Any = None
            try:
                channel_info = await client.conversations_info(channel=channel_id)
            except Exception as e:
                logger.warning(
                    f"Could not fetch channel info for {channel_id} (external-share check): {e}. "
                    "Failing open — missing channels:read/groups:read scope?"
                )
                channel_info = None

            if (
                channel_info
                and channel_info.get("channel", {}).get("is_ext_shared")
                and not slack_bot.allow_external_shared_channels
            ):
                decline_msg = (
                    "This bot isn't available in externally-shared channels. An admin can enable "
                    "this for this bot in its settings if this is expected."
                )
                if say:
                    await say(decline_msg)
                else:
                    await client.chat_postMessage(
                        channel=channel_id,
                        text=decline_msg,
                        thread_ts=thread_ts or message_ts,
                    )
                return decline_msg

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

            # Get or create conversation mapping.
            # Slack only sets thread_ts on *replies* — the message that starts a thread has
            # no thread_ts of its own (only its own ts, which becomes the thread root once
            # someone replies). Normalize to "thread_ts or message_ts" so the root message
            # and its replies always resolve to the same conversation.
            conversation = await self._get_or_create_conversation(
                slack_bot=slack_bot,
                channel_id=channel_id,
                user_id=user_id,
                thread_ts=thread_ts or message_ts,
                message_text=text,
            )

            # Block AI while a human operator is handling this conversation
            if getattr(conversation, "handoff_status", None) == "active":
                _wait = "A human support agent is currently handling this conversation. They will respond shortly."
                if say:
                    await say(_wait)
                else:
                    await client.chat_postMessage(channel=channel_id, text=_wait, thread_ts=thread_ts)
                return _wait

            # Fetch user info (channel_info was already fetched above for the
            # external-share check, so only one call is needed here now).
            try:
                user_info = await client.users_info(user=user_id)
                user_name = user_info["user"]["real_name"] or user_info["user"]["name"]
            except Exception as e:
                logger.warning(f"Could not fetch user info for {user_id}: {e}. Missing users:read scope?")
                user_name = user_id
            if channel_info:
                channel_name = channel_info.get("channel", {}).get("name", channel_id)
            else:
                channel_name = channel_id

            # Remove bot mention from text if present
            clean_text = self._remove_bot_mention(text, slack_bot.slack_app_id)

            logger.info(f"Slack message: Channel: #{channel_name} (ID: {channel_id}), Message TS: {message_ts}")

            # The agent receives only the clean user text — no raw Slack metadata.
            # Injecting channel IDs and timestamps into the message confused the agent
            # into thinking it received a forwarded Slack notification rather than a
            # direct message, causing it to say it "lacks a Slack tool to reply."
            # Slack context (channel, user) is passed via shared_state for tool use.
            context_message = clean_text

            # Slack-specific metadata to attach to the user message. The actual message row
            # is saved by ChatStreamService.stream_agent_response() below (via
            # user_message_metadata) — saving it here too would create a duplicate row.
            user_message_metadata = {
                "slack_user_id": user_id,
                "slack_user_name": user_name,
                "slack_channel_id": channel_id,
                "slack_channel_name": channel_name,
                "slack_message_ts": message_ts,
                "slack_thread_ts": thread_ts,
                "original_text": text,
            }

            # Show Slack's native "<BotName> is thinking..." status indicator
            # (assistant.threads.setStatus) below the composer while the agent
            # works, updating it with live per-tool-call status text.
            effective_thread_ts = thread_ts or message_ts
            status_service = SlackStatusService(client)
            await status_service.set_thinking(channel_id, effective_thread_ts)
            first_chunk_seen = False

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

            # Collect the streamed response + chart/diagram events
            response_chunks = []
            chart_events: list[dict] = []
            diagram_events: list[dict] = []
            kb_sources: list[dict] = []
            db_query_used = False
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
                user_message_metadata=user_message_metadata,
                # We already merged DB history with Slack's own thread history above —
                # don't let ChatStreamService clobber that with a plain DB/cache reload.
                trust_provided_history=True,
            ):
                if not event_data.startswith("data: "):
                    continue
                try:
                    event_json = json.loads(event_data[6:])
                    event_type = event_json.get("type")

                    if event_type == "chunk":
                        response_chunks.append(event_json.get("content", ""))
                        if not first_chunk_seen:
                            first_chunk_seen = True
                            asyncio.ensure_future(status_service.set_generating(channel_id, effective_thread_ts))

                    elif event_type == "error":
                        err_content = event_json.get("content", "An error occurred")
                        logger.error(f"Agent stream error: {err_content}")
                        response_chunks.append(err_content)

                    elif event_type == "chart":
                        chart_obj = event_json.get("chart") or event_json
                        if chart_obj and isinstance(chart_obj, dict):
                            chart_events.append(chart_obj)

                    elif event_type == "diagram":
                        diagram_obj = event_json.get("diagram") or event_json
                        if diagram_obj and isinstance(diagram_obj, dict):
                            diagram_events.append(diagram_obj)

                    elif event_type == "tool_status" and event_json.get("status") == "started":
                        description = event_json.get("description") or event_json.get("tool_name", "tool")
                        if event_json.get("tool_name") in _DATABASE_QUERY_TOOLS:
                            db_query_used = True
                        slack_status = _to_tool_status(description)
                        if slack_status:
                            asyncio.ensure_future(
                                status_service.set_custom_status(channel_id, effective_thread_ts, slack_status)
                            )

                    elif event_type == "done":
                        kb_sources = event_json.get("sources") or []
                except Exception:
                    pass

            agent_response = "".join(response_chunks)

            # Handle empty response. ChatStreamService only persists an assistant message
            # when it actually produced content, so this fallback case is the one situation
            # where we still need to save it ourselves below.
            response_was_empty = not agent_response or not agent_response.strip()
            if response_was_empty:
                logger.warning("Agent returned empty response, using fallback message")
                agent_response = "Done! I've processed your request."

            # Posting the final message clears the native status indicator automatically.
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

            # Upload diagrams as images (fire-and-forget, errors are non-fatal). Diagrams
            # render as SVG for the web chat UI, which Slack cannot preview inline, so they
            # must be converted to PNG and uploaded as image files like chart events above.
            if diagram_events:
                asyncio.ensure_future(
                    self._upload_diagrams(
                        client=client,
                        channel_id=channel_id,
                        thread_ts=thread_ts or message_ts,
                        diagrams=diagram_events,
                    )
                )

            # Post metadata footer: row counts, data sources extracted from response.
            # Only when a database query tool actually ran this turn — otherwise the
            # regex scan below produces false positives on unrelated text.
            metadata_ctx = self._build_metadata_context(agent_response) if db_query_used else None
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

            # Post knowledge base sources retrieved for this turn, if any. These are the
            # documents ChatStreamService's RAG step surfaced to the LLM as context — shown
            # regardless of whether the final answer quoted them, so the user can see what
            # was searched (mirrors the web chat UI's SourcesList).
            kb_sources_ctx = self._build_kb_sources_context(kb_sources)
            if kb_sources_ctx:
                try:
                    await client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts or message_ts,
                        blocks=[kb_sources_ctx],
                        text="Knowledge base sources",
                    )
                except Exception as e:
                    logger.warning(f"Failed to post KB sources footer: {e}")

            # Save the fallback response ourselves — ChatStreamService already saved the
            # assistant message for any non-empty response, so saving it again here would
            # duplicate the row.
            if response_was_empty:
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

        # chunk_blocks() enforces both Slack's 50-block count limit and a
        # conservative total-serialized-size budget (see SLACK_MAX_TOTAL_PAYLOAD_CHARS
        # in formatters.py) — a message can be rejected with `msg_blocks_too_long`
        # even at exactly 50 blocks if their combined payload is too large, so this
        # must always run rather than being gated behind a block-count check.
        block_chunks = chunk_blocks(blocks)

        if len(block_chunks) == 1:
            fallback_text = format_text_for_slack(response)
            await self._post_with_image_fallback(client, say, channel_id, thread_ts, fallback_text, blocks)
        else:
            for i, chunk in enumerate(block_chunks):
                fallback_text = (
                    format_text_for_slack(response) if i == 0 else f"(continued {i + 1}/{len(block_chunks)})"
                )
                await self._post_with_image_fallback(client, say, channel_id, thread_ts, fallback_text, chunk)

    async def _post_with_image_fallback(
        self,
        client: AsyncWebClient,
        say: Callable[..., Any] | None,
        channel_id: str,
        thread_ts: str | None,
        text: str,
        blocks: list[dict],
    ) -> None:
        """Post a message, falling back to plain links if Slack can't fetch an image block.

        Slack renders `image` blocks by having its own servers fetch `image_url` directly.
        If that URL isn't reachable from Slack's infrastructure (e.g. a local-dev presigned
        URL), the whole call fails with `invalid_blocks: downloading image failed` instead
        of just the image — so on that specific error, retry with image blocks converted
        to plain clickable links rather than failing the whole message.
        """
        try:
            if say:
                await say(text=text, blocks=blocks, thread_ts=thread_ts)
            else:
                await client.chat_postMessage(channel=channel_id, text=text, blocks=blocks, thread_ts=thread_ts)
        except SlackApiError as e:
            error_data = e.response.data if e.response is not None else {}
            is_image_fetch_failure = error_data.get("error") == "invalid_blocks" and any(
                "image" in str(err) for err in error_data.get("errors", [])
            )
            if not is_image_fetch_failure:
                raise
            logger.warning(f"Slack couldn't fetch an image block, falling back to a link: {error_data}")
            fallback_blocks = _convert_image_blocks_to_links(blocks)
            if say:
                await say(text=text, blocks=fallback_blocks, thread_ts=thread_ts)
            else:
                await client.chat_postMessage(
                    channel=channel_id, text=text, blocks=fallback_blocks, thread_ts=thread_ts
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
        self,
        slack_bot: SlackBot,
        channel_id: str,
        user_id: str,
        thread_ts: str | None,
        message_text: str | None = None,
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
        conv_name = message_text.strip()[:60] if message_text and message_text.strip() else f"Slack conversation with {user_id}"
        conversation = Conversation(
            agent_id=slack_bot.agent_id,
            name=conv_name,
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

    async def _upload_diagrams(
        self,
        client: AsyncWebClient,
        channel_id: str,
        thread_ts: str | None,
        diagrams: list[dict],
    ) -> None:
        """Convert each diagram's SVG to PNG and upload to Slack.

        internal_generate_diagram/internal_generate_quick_diagram render SVG for inline
        display in the web chat UI, but Slack has no inline SVG preview — without this,
        the LLM's tool result ("displayed to the user inline") is accurate for web chat
        but leaves Slack with only the LLM's descriptive text and no actual image.
        """
        try:
            import cairosvg
        except ImportError:
            logger.warning("cairosvg not available — skipping diagram upload")
            return

        for i, diagram in enumerate(diagrams):
            try:
                svg_content = diagram.get("svg_content")
                if not svg_content:
                    svg_url = diagram.get("svg_url")
                    if not svg_url:
                        continue
                    import httpx

                    async with httpx.AsyncClient(timeout=15.0) as http_client:
                        resp = await http_client.get(svg_url)
                        resp.raise_for_status()
                        svg_content = resp.text

                png_bytes = cairosvg.svg2png(bytestring=svg_content.encode(), output_width=1920)
                if not png_bytes:
                    continue

                title = diagram.get("title") or f"Diagram {i + 1}"
                await client.files_upload_v2(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    content=png_bytes,
                    filename=f"diagram_{i + 1}.png",
                    title=title,
                )
                logger.info(f"Uploaded diagram '{title}' to Slack channel {channel_id}")
            except Exception as e:
                logger.warning(f"Failed to upload diagram {i}: {e}")

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

    def _build_kb_sources_context(self, sources: list[dict]) -> dict | None:
        """Build a Slack context block listing retrieved knowledge-base sources.

        `sources` is the RAG `retrieved_sources` list from ChatStreamService (one entry
        per retrieved chunk, may include multiple chunks per document). Dedupe by
        document, keep each document's best-scoring chunk, and cap to the top 3.
        """
        if not sources:
            return None

        best_by_doc: dict[str, dict] = {}
        for source in sources:
            doc_key = source.get("document_id") or source.get("segment_id") or source.get("title") or source.get("source")
            if not doc_key:
                continue
            existing = best_by_doc.get(doc_key)
            if existing is None or (source.get("score") or 0) > (existing.get("score") or 0):
                best_by_doc[doc_key] = source

        top_docs = sorted(best_by_doc.values(), key=lambda s: s.get("score") or 0, reverse=True)[:3]
        if not top_docs:
            return None

        parts: list[dict] = [{"type": "mrkdwn", "text": ":books: *Sources:*"}]
        for doc in top_docs:
            title = doc.get("title") or doc.get("kb_name") or "Document"
            kb_name = doc.get("kb_name")
            score_pct = round((doc.get("score") or 0) * 100)
            label = f"{title} ({kb_name})" if kb_name and kb_name not in title else title
            parts.append({"type": "mrkdwn", "text": f"{label} — {score_pct}%"})

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
