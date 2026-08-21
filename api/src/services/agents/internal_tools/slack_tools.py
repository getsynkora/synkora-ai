"""Slack Tools for Autonomous Agent Interaction.

These tools allow agents to interact with Slack channels autonomously,
reading messages, understanding context, and deciding when to respond.
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy import select

from src.core.database import get_async_db
from src.models.slack_bot import SlackBot
from src.services.agents.internal_tools.web_tools import internal_download_url_bytes
from src.services.agents.security import decrypt_value
from src.services.storage.s3_storage import get_s3_storage

logger = logging.getLogger(__name__)


async def _get_slack_client(runtime_context: dict[str, Any], config: dict[str, Any] = None) -> AsyncWebClient | None:
    """
    Get Slack client using OAuth app or legacy Slack bot.

    Tries OAuth app first (via credential_resolver), then falls back to legacy Slack bot.

    Args:
        runtime_context: Runtime context with agent_id and db_session
        config: Config dict that may contain _tool_name from adk_tools
    """
    try:
        # Extract agent_id first
        if isinstance(runtime_context, dict):
            agent_id = runtime_context.get("agent_id")
        else:
            agent_id = getattr(runtime_context, "agent_id", None)

        if not agent_id:
            logger.error("No agent_id in runtime_context")
            return None

        # Try using credential resolver for OAuth app (preferred method)
        # RuntimeContext doesn't have credential_resolver as attribute, we need to create one
        try:
            from src.services.agents.credential_resolver import CredentialResolver

            # Extract tool_name from config (added by adk_tools.py)
            tool_name = None
            if config:
                tool_name = config.get("_tool_name")

            if not tool_name:
                logger.warning("⚠️ No _tool_name in config, using fallback 'slack'")
                tool_name = "slack"

            logger.info(f"🔍 [Slack Tools] Looking up OAuth for tool_name='{tool_name}'")

            # Create credential resolver with runtime_context
            resolver = CredentialResolver(runtime_context)
            token = await resolver.get_slack_token(tool_name)

            if token:
                logger.info(f"✅ Using Slack OAuth token for agent {agent_id}")
                return AsyncWebClient(token=token)
            else:
                logger.info("No Slack OAuth token found, falling back to legacy Slack bot")
        except Exception as e:
            logger.warning(f"Error trying OAuth method: {e}, falling back to legacy Slack bot")

        if not agent_id:
            logger.error("No agent_id in runtime_context")
            return None

        async for db in get_async_db():
            # Find active Slack bot for this agent — use first() to handle multiple connected bots gracefully
            result = await db.execute(
                select(SlackBot)
                .filter(SlackBot.agent_id == agent_id, SlackBot.connection_status == "connected")
                .limit(1)
            )
            slack_bot = result.scalar_one_or_none()

            if not slack_bot:
                logger.warning(f"No active Slack bot found for agent {agent_id}")
                return None

            # Decrypt bot token
            bot_token = decrypt_value(slack_bot.slack_bot_token)
            logger.info(f"✅ Using legacy Slack bot for agent {agent_id}")
            return AsyncWebClient(token=bot_token)

    except Exception as e:
        logger.error(f"Error getting Slack client: {e}", exc_info=True)
        return None


def _resolve_thread_ts(thread_ts: str | None, runtime_context: dict[str, Any] | None) -> str | None:
    """Fall back to the triggering message's thread when the LLM omits thread_ts.

    Without this, tools like internal_slack_send_message/post_blocks/upload_file post
    to the main channel whenever the LLM forgets to pass thread_ts, splitting a single
    turn's replies between the thread and the channel. slack_message_handler.py stores
    the effective thread timestamp in shared_state["slack_thread_ts"] so every tool call
    within a turn defaults to the same thread unless the LLM explicitly overrides it.
    """
    if thread_ts:
        return thread_ts
    if isinstance(runtime_context, dict):
        shared_state = runtime_context.get("shared_state") or {}
    else:
        shared_state = getattr(runtime_context, "shared_state", None) or {}
    return shared_state.get("slack_thread_ts")


def _get_requesting_slack_user_id(runtime_context: dict[str, Any] | None) -> str | None:
    """The Slack user who sent the triggering message, if this tool call happened inside
    a real Slack conversation (stored in shared_state by slack_message_handler.py).
    None when triggered outside Slack (e.g. the web console) — there's no one to invite.
    """
    if isinstance(runtime_context, dict):
        shared_state = runtime_context.get("shared_state") or {}
    else:
        shared_state = getattr(runtime_context, "shared_state", None) or {}
    return shared_state.get("slack_user_id")


async def _invite_requesting_user(client: Any, channel_id: str, runtime_context: dict[str, Any] | None) -> None:
    """Invite the human who asked for this channel, so it shows up for them in Slack —
    a newly created (or reused-but-never-joined) channel otherwise only has the bot as a
    member. Best-effort: swallow already_in_channel and any other invite failure.
    """
    user_id = _get_requesting_slack_user_id(runtime_context)
    if not user_id:
        return
    try:
        await client.conversations_invite(channel=channel_id, users=user_id)
    except SlackApiError as e:
        if e.response.get("error") != "already_in_channel":
            logger.warning(f"Failed to invite requesting user {user_id} to {channel_id}: {e}")


async def internal_slack_list_channels(
    include_private: bool = False, runtime_context: dict[str, Any] | None = None, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    List all Slack channels the bot can see.

    Args:
        include_private: Whether to include private channels
        runtime_context: Runtime context from agent execution
        config: Config dict with _tool_name

    Returns:
        Dictionary with channels list and metadata
    """
    try:
        client = await _get_slack_client(runtime_context, config)
        if not client:
            return {"success": False, "error": "No Slack connection available. Please connect a Slack bot first."}

        channels = []
        cursor = None

        while True:
            response = await client.conversations_list(
                exclude_archived=True,
                types="public_channel,private_channel" if include_private else "public_channel",
                cursor=cursor,
                limit=200,
            )

            for channel in response.get("channels", []):
                channels.append(
                    {
                        "id": channel.get("id"),
                        "name": channel.get("name"),
                        "is_private": channel.get("is_private", False),
                        "is_member": channel.get("is_member", False),
                        "num_members": channel.get("num_members", 0),
                        "topic": channel.get("topic", {}).get("value", ""),
                        "purpose": channel.get("purpose", {}).get("value", ""),
                    }
                )

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return {"success": True, "channels": channels, "total": len(channels)}

    except SlackApiError as e:
        logger.error(f"Slack API error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error listing channels: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_slack_read_channel_messages(
    channel_id: str,
    limit: int = 50,
    hours_ago: int | None = None,
    runtime_context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Read recent messages from a Slack channel.

    The agent can use this to understand what's being discussed in a channel
    and decide if/how to participate.

    Args:
        channel_id: Slack channel ID (e.g., "C1234567890")
        limit: Maximum number of messages to retrieve (default 50, max 1000)
        hours_ago: Only get messages from the last N hours (optional)
        runtime_context: Runtime context from agent execution
        config: Config dict with _tool_name

    Returns:
        Dictionary with messages and context
    """
    try:
        client = await _get_slack_client(runtime_context, config)
        if not client:
            return {"success": False, "error": "No Slack connection available"}

        # Calculate oldest timestamp if hours_ago specified
        oldest = None
        if hours_ago:
            oldest_time = datetime.now(UTC) - timedelta(hours=hours_ago)
            oldest = str(oldest_time.timestamp())

        # Get channel messages — auto-join if the bot is not yet a member
        try:
            response = await client.conversations_history(channel=channel_id, limit=min(limit, 1000), oldest=oldest)
        except SlackApiError as join_err:
            if "not_in_channel" in str(join_err):
                logger.info(f"Bot not in channel {channel_id}, attempting auto-join")
                try:
                    await client.conversations_join(channel=channel_id)
                    response = await client.conversations_history(
                        channel=channel_id, limit=min(limit, 1000), oldest=oldest
                    )
                except SlackApiError as retry_err:
                    err_str = str(retry_err)
                    if "cant_invite_self" in err_str or "method_not_supported" in err_str:
                        return {
                            "success": False,
                            "error": (
                                f"Cannot auto-join channel {channel_id} — it may be private. "
                                "Please invite the bot manually with /invite @bot in the channel."
                            ),
                        }
                    return {"success": False, "error": f"Slack error after joining: {retry_err}"}
            else:
                raise

        # Get channel info
        channel_info = await client.conversations_info(channel=channel_id)
        channel_name = channel_info.get("channel", {}).get("name", "unknown")

        # Process messages
        messages = []
        user_cache = {}
        is_dm = channel_id.startswith("D")

        for msg in response.get("messages", []):
            subtype = msg.get("subtype", "")
            is_bot_msg = bool(msg.get("bot_id")) or subtype == "bot_message"

            # Non-DM channels: skip bot/system messages to reduce noise
            if not is_dm and subtype in ("bot_message", "channel_join", "channel_leave"):
                continue

            # All channels: skip system join/leave noise
            if subtype in ("channel_join", "channel_leave"):
                continue

            user_id = msg.get("user")

            if is_bot_msg:
                sender_name = "Bot"
                display_name = "Bot"
            else:
                # Get user info (cached)
                if user_id and user_id not in user_cache:
                    try:
                        user_info = await client.users_info(user=user_id)
                        user_data = user_info.get("user", {})
                        user_cache[user_id] = {
                            "name": user_data.get("real_name") or user_data.get("name"),
                            "display_name": user_data.get("profile", {}).get("display_name", ""),
                        }
                    except Exception:
                        user_cache[user_id] = {"name": "Unknown", "display_name": ""}

                user = user_cache.get(user_id, {"name": "Unknown", "display_name": ""})
                sender_name = user.get("name")
                display_name = user.get("display_name")

            messages.append(
                {
                    "text": msg.get("text", ""),
                    "user_name": sender_name,
                    "user_display_name": display_name,
                    "is_bot": is_bot_msg,
                    "timestamp": msg.get("ts"),
                    "thread_ts": msg.get("thread_ts"),
                    "is_thread_reply": bool(msg.get("thread_ts") and msg.get("thread_ts") != msg.get("ts")),
                    "reply_count": msg.get("reply_count", 0),
                }
            )

        # Reverse to show oldest first (chronological order)
        messages.reverse()

        return {
            "success": True,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "messages": messages,
            "total_messages": len(messages),
        }

    except SlackApiError as e:
        logger.error(f"Slack API error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error reading messages: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_slack_read_thread(
    channel_id: str, thread_ts: str, runtime_context: dict[str, Any] | None = None, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Read all messages in a specific thread.

    Use this when you see a thread with replies and want to understand
    the full conversation context.

    Args:
        channel_id: Slack channel ID
        thread_ts: Thread timestamp (the parent message timestamp)
        runtime_context: Runtime context from agent execution
        config: Config dict with _tool_name

    Returns:
        Dictionary with thread messages
    """
    try:
        client = await _get_slack_client(runtime_context, config)
        if not client:
            return {"success": False, "error": "No Slack connection available"}

        # Get thread replies
        response = await client.conversations_replies(channel=channel_id, ts=thread_ts)

        # Process messages
        messages = []
        user_cache = {}

        for msg in response.get("messages", []):
            user_id = msg.get("user")

            # Get user info (cached)
            if user_id and user_id not in user_cache:
                try:
                    user_info = await client.users_info(user=user_id)
                    user_data = user_info.get("user", {})
                    user_cache[user_id] = {
                        "name": user_data.get("real_name") or user_data.get("name"),
                        "display_name": user_data.get("profile", {}).get("display_name", ""),
                    }
                except Exception:
                    user_cache[user_id] = {"name": "Unknown", "display_name": ""}

            user = user_cache.get(user_id, {"name": "Unknown", "display_name": ""})

            messages.append(
                {
                    "text": msg.get("text", ""),
                    "user_name": user.get("name"),
                    "timestamp": msg.get("ts"),
                    "is_parent": msg.get("ts") == thread_ts,
                }
            )

        return {
            "success": True,
            "channel_id": channel_id,
            "thread_ts": thread_ts,
            "messages": messages,
            "total_messages": len(messages),
        }

    except SlackApiError as e:
        logger.error(f"Slack API error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error reading thread: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_slack_send_message(
    channel_id: str,
    text: str,
    thread_ts: str | None = None,
    runtime_context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Send a message to a Slack channel or thread.

    Use this when you've decided that responding would be valuable.
    Consider the context and only respond when you have something meaningful to contribute.

    Args:
        channel_id: Slack channel ID
        text: Message text to send (supports markdown - will be converted to Slack format)
        thread_ts: Optional thread timestamp to reply in thread
        runtime_context: Runtime context from agent execution
        config: Config dict with _tool_name

    Returns:
        Dictionary with send status
    """
    try:
        client = await _get_slack_client(runtime_context, config)
        if not client:
            return {"success": False, "error": "No Slack connection available"}

        thread_ts = _resolve_thread_ts(thread_ts, runtime_context)

        # Format text for Slack (convert markdown to Slack's mrkdwn format)
        from src.services.slack.formatters import format_text_for_slack

        formatted_text = format_text_for_slack(text)

        response = await client.chat_postMessage(channel=channel_id, text=formatted_text, thread_ts=thread_ts)

        return {
            "success": True,
            "channel_id": channel_id,
            "message_ts": response.get("ts"),
            "thread_ts": thread_ts,
            "message": "Message sent successfully",
        }

    except SlackApiError as e:
        logger.error(f"Slack API error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_slack_join_channel(
    channel_id: str, runtime_context: dict[str, Any] | None = None, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Join a Slack channel.

    Use this when you need to participate in a channel you're not currently a member of.

    Args:
        channel_id: Slack channel ID to join
        runtime_context: Runtime context from agent execution
        config: Config dict with _tool_name

    Returns:
        Dictionary with join status
    """
    try:
        client = await _get_slack_client(runtime_context, config)
        if not client:
            return {"success": False, "error": "No Slack connection available"}

        response = await client.conversations_join(channel=channel_id)

        channel_name = response.get("channel", {}).get("name", "unknown")

        return {
            "success": True,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "message": f"Successfully joined #{channel_name}",
        }

    except SlackApiError as e:
        logger.error(f"Slack API error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error joining channel: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_slack_create_channel(
    name: str,
    is_private: bool = False,
    runtime_context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create a new Slack channel.

    Use this when the user asks you to open/create a channel that doesn't exist yet.
    Slack channel names must be lowercase, without spaces, and use hyphens or
    underscores instead (e.g. "bughunt-home-deriv").

    Args:
        name: Name for the new channel
        is_private: Whether to create a private channel (default False, i.e. public)
        runtime_context: Runtime context from agent execution
        config: Config dict with _tool_name

    Returns:
        Dictionary with the created channel's id and name
    """
    try:
        client = await _get_slack_client(runtime_context, config)
        if not client:
            return {"success": False, "error": "No Slack connection available"}

        response = await client.conversations_create(name=name, is_private=is_private)

        channel = response.get("channel", {})
        channel_id = channel.get("id")
        channel_name = channel.get("name", name)

        await _invite_requesting_user(client, channel_id, runtime_context)

        return {
            "success": True,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "is_private": is_private,
            "message": f"Successfully created #{channel_name}",
        }

    except SlackApiError as e:
        if e.response.get("error") == "name_taken":
            logger.info(f"Channel #{name} already exists, looking up existing channel")
            existing = await _find_channel_by_name(client, name, include_private=is_private)
            if existing:
                await _invite_requesting_user(client, existing["id"], runtime_context)
                return {
                    "success": True,
                    "channel_id": existing["id"],
                    "channel_name": existing["name"],
                    "is_private": is_private,
                    "message": f"#{existing['name']} already exists, reusing it",
                }
        logger.error(f"Slack API error creating channel: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error creating channel: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def _find_channel_by_name(client: Any, name: str, include_private: bool = False) -> dict[str, Any] | None:
    """Look up a channel by exact name via paginated conversations_list."""
    cursor = None
    while True:
        response = await client.conversations_list(
            exclude_archived=True,
            types="public_channel,private_channel" if include_private else "public_channel",
            cursor=cursor,
            limit=200,
        )
        for channel in response.get("channels", []):
            if channel.get("name") == name:
                return channel

        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            return None


async def internal_slack_search_messages(
    query: str, count: int = 20, runtime_context: dict[str, Any] | None = None, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Search for messages across all channels.

    Use this to find discussions about specific topics or keywords.

    Args:
        query: Search query (supports Slack search operators)
        count: Number of results to return (max 100)
        runtime_context: Runtime context from agent execution
        config: Config dict with _tool_name

    Returns:
        Dictionary with search results
    """
    try:
        client = await _get_slack_client(runtime_context, config)
        if not client:
            return {"success": False, "error": "No Slack connection available"}

        response = await client.search_messages(query=query, count=min(count, 100))

        matches = []
        for match in response.get("messages", {}).get("matches", []):
            matches.append(
                {
                    "text": match.get("text", ""),
                    "username": match.get("username", ""),
                    "channel_name": match.get("channel", {}).get("name", ""),
                    "channel_id": match.get("channel", {}).get("id", ""),
                    "timestamp": match.get("ts", ""),
                    "permalink": match.get("permalink", ""),
                }
            )

        return {
            "success": True,
            "query": query,
            "matches": matches,
            "total_results": response.get("messages", {}).get("total", 0),
        }

    except SlackApiError as e:
        logger.error(f"Slack API error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error searching messages: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_slack_add_reaction(
    channel_id: str,
    timestamp: str,
    emoji: str,
    runtime_context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Add an emoji reaction to a message.

    Use this for lightweight acknowledgment or to show agreement without sending a message.

    Args:
        channel_id: Slack channel ID
        timestamp: Message timestamp
        emoji: Emoji name (without colons, e.g., "thumbsup" or "eyes")
        runtime_context: Runtime context from agent execution
        config: Config dict with _tool_name

    Returns:
        Dictionary with reaction status
    """
    try:
        client = await _get_slack_client(runtime_context, config)
        if not client:
            return {"success": False, "error": "No Slack connection available"}

        await client.reactions_add(channel=channel_id, timestamp=timestamp, name=emoji)

        return {
            "success": True,
            "channel_id": channel_id,
            "timestamp": timestamp,
            "emoji": emoji,
            "message": f"Added reaction :{emoji}:",
        }

    except SlackApiError as e:
        logger.error(f"Slack API error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error adding reaction: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_slack_send_dm(
    user_id: str,
    text: str,
    report_back_channel_id: str | None = None,
    runtime_context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Send a direct message to a Slack user.

    Use this to send private messages directly to users.

    Args:
        user_id: Slack user ID (e.g., "U1234567890")
        text: Message text to send (supports markdown - will be converted to Slack format)
        report_back_channel_id: Channel ID to notify when the DM recipient replies (pass the
            channel from the [Slack Context] header when sending on behalf of another user)
        runtime_context: Runtime context from agent execution
        config: Config dict with _tool_name

    Returns:
        Dictionary with send status
    """
    try:
        client = await _get_slack_client(runtime_context, config)
        if not client:
            return {"success": False, "error": "No Slack connection available"}

        # Format text for Slack (convert markdown to Slack's mrkdwn format)
        from src.services.slack.formatters import format_text_for_slack

        formatted_text = format_text_for_slack(text)

        # Open a DM channel with the user
        dm_response = await client.conversations_open(users=[user_id])
        dm_channel_id = dm_response.get("channel", {}).get("id")

        if not dm_channel_id:
            return {"success": False, "error": "Could not open DM channel"}

        # Send the message
        response = await client.chat_postMessage(channel=dm_channel_id, text=formatted_text)

        # Store report-back callback in Redis so handle_message can notify the
        # requester automatically when the DM recipient replies.
        if report_back_channel_id:
            agent_id = None
            if isinstance(runtime_context, dict):
                agent_id = runtime_context.get("agent_id")
            else:
                agent_id = getattr(runtime_context, "agent_id", None)

            if agent_id:
                try:
                    import json

                    from src.config.redis import get_redis_async

                    # Include the current message_ts so the callback check can skip
                    # the same turn that stored this callback (prevents spurious fire
                    # when requester_channel == dm_channel, e.g. self-DM test cases).
                    request_message_ts = None
                    if isinstance(runtime_context, dict):
                        request_message_ts = (runtime_context.get("shared_state") or {}).get("slack_message_ts")
                    elif runtime_context is not None:
                        request_message_ts = (runtime_context.shared_state or {}).get("slack_message_ts")

                    redis = get_redis_async()
                    key = f"slack:dm_callback:{agent_id}:{dm_channel_id}"
                    await redis.set(
                        key,
                        json.dumps(
                            {
                                "requester_channel_id": report_back_channel_id,
                                "request_message_ts": request_message_ts,
                            }
                        ),
                        ex=604800,  # 7 days
                    )
                    logger.info(
                        f"Stored DM callback: {dm_channel_id} → {report_back_channel_id} (request_ts={request_message_ts})"
                    )
                except Exception as e:
                    logger.warning(f"Failed to store DM callback: {e}")

        return {
            "success": True,
            "user_id": user_id,
            "channel_id": dm_channel_id,
            "message_ts": response.get("ts"),
            "message": "DM sent successfully",
        }

    except SlackApiError as e:
        logger.error(f"Slack API error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error sending DM: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


_IMAGE_BLOCK_ERROR_RE = re.compile(r"json-pointer:/blocks/(\d+)/image_url")


async def _heal_unreachable_image_blocks(
    blocks_list: list[dict[str, Any]],
    error: SlackApiError,
    client: AsyncWebClient,
    channel_id: str,
    thread_ts: str | None,
) -> list[dict[str, Any]] | None:
    """On invalid_blocks "downloading image failed" errors, re-upload any failing
    image block that points at our own storage as a file attachment instead, and
    return the remaining blocks with those image blocks removed. Returns None if
    the error isn't this specific failure mode, or none of the failing images are
    ours to re-fetch (nothing we can self-heal).
    """
    if error.response.get("error") != "invalid_blocks":
        return None

    indices = {
        int(m.group(1)) for err in error.response.get("errors") or [] for m in _IMAGE_BLOCK_ERROR_RE.finditer(err)
    }
    if not indices:
        return None

    try:
        s3 = get_s3_storage()
    except Exception:
        return None

    healed_blocks = list(blocks_list)
    healed_any = False
    for idx in sorted(indices, reverse=True):
        if idx >= len(healed_blocks) or not isinstance(healed_blocks[idx], dict):
            continue
        block = healed_blocks[idx]
        image_url = block.get("image_url")
        if not image_url:
            continue

        content = await s3.download_if_own_url(image_url)
        if content is None:
            continue

        filename = image_url.rsplit("/", 1)[-1].split("?")[0] or "image.png"
        try:
            await client.files_upload_v2(
                channel=channel_id,
                content=content,
                filename=filename,
                title=block.get("alt_text") or "Image",
                thread_ts=thread_ts,
            )
        except Exception as upload_exc:
            logger.warning(f"Failed to re-upload unreachable image block as file: {upload_exc}")
            continue

        del healed_blocks[idx]
        healed_any = True

    return healed_blocks if healed_any else None


async def internal_slack_post_blocks(
    channel_id: str,
    blocks: str,
    text: str = "",
    thread_ts: str | None = None,
    runtime_context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Post a Block Kit message to a Slack channel.

    Use this to post rich messages with images, sections, and formatted content.
    The primary use-case is posting infographic images generated by
    internal_generate_infographic — pass the png_url or svg_url in an image block.

    Args:
        channel_id: Slack channel ID (e.g. 'C1234567890')
        blocks: JSON string of Slack Block Kit blocks array. Example with image::

            [
              {"type": "section", "text": {"type": "mrkdwn", "text": "*Daily Briefing*"}},
              {"type": "image",
               "image_url": "https://your-s3-bucket/infographic.png",
               "alt_text": "Daily Operations Briefing"}
            ]

        text: Fallback plain text shown in notifications and accessibility contexts.
        thread_ts: Optional thread timestamp to reply in thread.
        runtime_context: Runtime context from agent execution.
        config: Config dict with _tool_name.

    Returns:
        ``{"success": True, "message_ts": "...", "channel_id": "..."}``
        or ``{"success": False, "error": "..."}``
    """
    import json as _json

    try:
        client = await _get_slack_client(runtime_context, config)
        if not client:
            return {"success": False, "error": "No Slack connection available"}

        thread_ts = _resolve_thread_ts(thread_ts, runtime_context)

        # Parse blocks JSON
        try:
            blocks_list = _json.loads(blocks) if isinstance(blocks, str) else blocks
        except _json.JSONDecodeError as exc:
            return {"success": False, "error": f"Invalid blocks JSON: {exc}"}

        if not isinstance(blocks_list, list):
            return {"success": False, "error": "blocks must be a JSON array"}

        try:
            response = await client.chat_postMessage(
                channel=channel_id,
                blocks=blocks_list,
                text=text or "Message",
                thread_ts=thread_ts,
            )
        except SlackApiError as e:
            # Slack's OWN servers try to download image_url to render an image block.
            # Our presigned MinIO/S3 URLs are signed with the public endpoint (e.g.
            # http://localhost:9000 in dev), which is only reachable from our own
            # network/browser, never from Slack's infrastructure — Slack rejects the
            # whole message with invalid_blocks. Self-heal: fetch the image ourselves
            # (it's our own storage), upload it as a file attachment instead, drop the
            # failing image block(s), and retry with the rest of the message.
            healed_blocks = await _heal_unreachable_image_blocks(blocks_list, e, client, channel_id, thread_ts)
            if healed_blocks is None:
                raise
            response = await client.chat_postMessage(
                channel=channel_id,
                blocks=healed_blocks,
                text=text or "Message",
                thread_ts=thread_ts,
            )

        return {
            "success": True,
            "channel_id": channel_id,
            "message_ts": response.get("ts"),
            "thread_ts": thread_ts,
            "message": "Blocks posted successfully",
        }

    except SlackApiError as e:
        logger.error(f"Slack API error posting blocks: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error posting blocks: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_slack_upload_file(
    channel_id: str,
    filename: str,
    file_content: str = "",
    file_url: str = "",
    title: str = "",
    initial_comment: str = "",
    thread_ts: str | None = None,
    runtime_context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Upload a file to a Slack channel.

    Use this to share infographic images, CSVs, PDFs, or any file directly in Slack.
    Prefer this over posting image URLs when you have the raw file content (e.g. SVG
    from internal_generate_infographic returns svg_content for small infographics).

    For infographics: if svg_content is returned by internal_generate_infographic,
    pass it here as file_content with filename ending in .svg.

    If you only have a URL (e.g. the image_url returned by internal_browser_screenshot),
    pass it as file_url instead — this tool will download it and attach the bytes as
    a genuine Slack file. file_content takes precedence if both are given.

    Args:
        channel_id: Slack channel ID (e.g. 'C1234567890')
        filename: Filename including extension (e.g. 'briefing.svg', 'report.csv')
        file_content: Raw file content as a string (SVG markup, CSV data, etc.)
        file_url: URL to download and upload as the file (e.g. an S3 image_url)
        title: Optional display title shown above the file in Slack
        initial_comment: Optional message text posted alongside the file
        thread_ts: Optional thread timestamp to upload into a thread
        runtime_context: Runtime context from agent execution
        config: Config dict with _tool_name

    Returns:
        ``{"success": True, "file_id": "...", "permalink": "..."}``
        or ``{"success": False, "error": "..."}``
    """
    try:
        client = await _get_slack_client(runtime_context, config)
        if not client:
            return {"success": False, "error": "No Slack connection available"}

        if not file_content and not file_url:
            return {"success": False, "error": "Either file_content or file_url is required"}

        content: str | bytes
        if file_content:
            content = file_content
        else:
            # file_url is often our own presigned S3/MinIO URL (e.g. from
            # internal_browser_screenshot), signed with the PUBLIC endpoint for browser
            # access (e.g. "http://localhost:9000" in dev). Fetching that host from inside
            # a container is correctly SSRF-blocked by the generic downloader below, so
            # detect our own storage first and fetch bytes directly via the S3 client.
            own_bytes: bytes | None = None
            try:
                own_bytes = await get_s3_storage().download_if_own_url(file_url)
            except Exception:
                own_bytes = None

            if own_bytes is not None:
                content = own_bytes
            else:
                download = await internal_download_url_bytes(file_url, config=config)
                if "error" in download:
                    return {"success": False, "error": f"Failed to download file_url: {download['error']}"}
                content = download["content"]

        thread_ts = _resolve_thread_ts(thread_ts, runtime_context)

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        upload_kwargs: dict[str, Any] = {
            "content": content,
            "filename": filename,
            "filetype": ext or "auto",
        }
        if title:
            upload_kwargs["title"] = title
        if initial_comment:
            upload_kwargs["initial_comment"] = initial_comment
        if thread_ts:
            upload_kwargs["thread_ts"] = thread_ts

        try:
            # files_upload_v2's `channels` kwarg takes a List[str] for multi-channel
            # uploads; passing a plain channel_id string there gets iterated character-by-
            # character downstream (files_completeUploadExternal does ",".join(channels)),
            # producing an invalid channel id and a misleading "channel_not_found" error.
            # We always upload to exactly one channel, so use the singular `channel` kwarg.
            response = await client.files_upload_v2(channel=channel_id, **upload_kwargs)
        except AttributeError:
            # Older slack_sdk — files_upload's equivalent param is `channels`
            # (comma-separated string, so a single channel_id works as-is).
            response = await client.files_upload(channels=channel_id, **upload_kwargs)

        file_obj = response.get("file", {})
        return {
            "success": True,
            "file_id": file_obj.get("id"),
            "filename": file_obj.get("name"),
            "permalink": file_obj.get("permalink"),
            "permalink_public": file_obj.get("permalink_public"),
            "message": f"File '{filename}' uploaded to channel {channel_id}",
        }

    except SlackApiError as e:
        logger.error(f"Slack API error uploading file: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error uploading file: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
