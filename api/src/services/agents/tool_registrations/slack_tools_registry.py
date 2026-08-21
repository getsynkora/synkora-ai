"""
Slack Tools Registry

Registers all Slack-related tools with the ADK tool registry.
This modular approach keeps tool registration organized and maintainable.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_slack_tools(registry):
    """
    Register all Slack tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.slack_tools import (
        internal_slack_add_reaction,
        internal_slack_create_channel,
        internal_slack_join_channel,
        internal_slack_list_channels,
        internal_slack_post_blocks,
        internal_slack_read_channel_messages,
        internal_slack_read_thread,
        internal_slack_search_messages,
        internal_slack_send_dm,
        internal_slack_send_message,
        internal_slack_upload_file,
    )

    # Slack tools - create wrappers that inject runtime_context
    async def internal_slack_list_channels_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_slack_list_channels(
            include_private=kwargs.get("include_private", False), runtime_context=runtime_context, config=config
        )

    async def internal_slack_read_channel_messages_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_slack_read_channel_messages(
            channel_id=kwargs.get("channel_id"),
            limit=kwargs.get("limit", 50),
            hours_ago=kwargs.get("hours_ago"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_slack_read_thread_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_slack_read_thread(
            channel_id=kwargs.get("channel_id"),
            thread_ts=kwargs.get("thread_ts"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_slack_send_message_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_slack_send_message(
            channel_id=kwargs.get("channel_id"),
            text=kwargs.get("text"),
            thread_ts=kwargs.get("thread_ts"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_slack_join_channel_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_slack_join_channel(
            channel_id=kwargs.get("channel_id"), runtime_context=runtime_context, config=config
        )

    async def internal_slack_search_messages_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_slack_search_messages(
            query=kwargs.get("query"), count=kwargs.get("count", 20), runtime_context=runtime_context, config=config
        )

    async def internal_slack_add_reaction_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_slack_add_reaction(
            channel_id=kwargs.get("channel_id"),
            timestamp=kwargs.get("timestamp"),
            emoji=kwargs.get("emoji"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_slack_send_dm_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_slack_send_dm(
            user_id=kwargs.get("user_id"),
            text=kwargs.get("text"),
            report_back_channel_id=kwargs.get("report_back_channel_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_slack_post_blocks_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_slack_post_blocks(
            channel_id=kwargs.get("channel_id"),
            blocks=kwargs.get("blocks"),
            text=kwargs.get("text", ""),
            thread_ts=kwargs.get("thread_ts"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_slack_upload_file_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_slack_upload_file(
            channel_id=kwargs.get("channel_id"),
            file_content=kwargs.get("file_content", ""),
            file_url=kwargs.get("file_url", ""),
            filename=kwargs.get("filename"),
            title=kwargs.get("title", ""),
            initial_comment=kwargs.get("initial_comment", ""),
            thread_ts=kwargs.get("thread_ts"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_slack_create_channel_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_slack_create_channel(
            name=kwargs.get("name"),
            is_private=kwargs.get("is_private", False),
            runtime_context=runtime_context,
            config=config,
        )

    # Register all Slack tools
    registry.register_tool(
        name="internal_slack_list_channels",
        description="List all Slack channels you can see. Use this to discover channels you might want to monitor or join.",
        parameters={
            "type": "object",
            "properties": {
                "include_private": {
                    "type": "boolean",
                    "description": "Whether to include private channels in the list",
                    "default": False,
                }
            },
            "required": [],
        },
        function=internal_slack_list_channels_wrapper,
    )

    registry.register_tool(
        name="internal_slack_read_channel_messages",
        description="Read recent messages from a Slack channel or DM conversation. Works for public/private channels AND direct message channels (IDs starting with 'D'). Use this to check for replies after sending a DM via internal_slack_send_dm — pass the channel_id returned by that tool. Also use this to monitor channels and decide if you should participate.",
        parameters={
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Slack channel ID (e.g., 'C1234567890')"},
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of messages to retrieve (default 50, max 1000)",
                    "default": 50,
                },
                "hours_ago": {"type": "integer", "description": "Only get messages from the last N hours (optional)"},
            },
            "required": ["channel_id"],
        },
        function=internal_slack_read_channel_messages_wrapper,
    )

    registry.register_tool(
        name="internal_slack_read_thread",
        description="Read all messages in a specific thread. Use this when you see a thread with replies and want to understand the full conversation context before responding.",
        parameters={
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Slack channel ID"},
                "thread_ts": {"type": "string", "description": "Thread timestamp (the parent message timestamp)"},
            },
            "required": ["channel_id", "thread_ts"],
        },
        function=internal_slack_read_thread_wrapper,
    )

    registry.register_tool(
        name="internal_slack_send_message",
        description="Send a message to a Slack channel or thread. Only call this tool when the user explicitly asks you to send or post a message to a specific channel or thread. Do not call this tool to echo, summarize, or follow up on a response you have already given.",
        parameters={
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Slack channel ID"},
                "text": {"type": "string", "description": "Message text to send"},
                "thread_ts": {
                    "type": "string",
                    "description": "Optional thread timestamp to reply in thread (recommended to keep conversations organized)",
                },
            },
            "required": ["channel_id", "text"],
        },
        function=internal_slack_send_message_wrapper,
    )

    registry.register_tool(
        name="internal_slack_join_channel",
        description="Join a Slack channel. Use this when you discover a channel that's relevant to your role and you want to monitor or participate in it.",
        parameters={
            "type": "object",
            "properties": {"channel_id": {"type": "string", "description": "Slack channel ID to join"}},
            "required": ["channel_id"],
        },
        function=internal_slack_join_channel_wrapper,
    )

    registry.register_tool(
        name="internal_slack_search_messages",
        description="Search for messages across all channels. Use this to find discussions about specific topics, features, or issues that might be relevant to your work.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (supports Slack search operators like 'from:@user', 'in:#channel', etc.)",
                },
                "count": {"type": "integer", "description": "Number of results to return (max 100)", "default": 20},
            },
            "required": ["query"],
        },
        function=internal_slack_search_messages_wrapper,
    )

    registry.register_tool(
        name="internal_slack_add_reaction",
        description="Add an emoji reaction to a message. Use this for lightweight acknowledgment or to show agreement without sending a message. This is a human-like way to participate without being verbose.",
        parameters={
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Slack channel ID"},
                "timestamp": {"type": "string", "description": "Message timestamp"},
                "emoji": {
                    "type": "string",
                    "description": "Emoji name without colons (e.g., 'thumbsup', 'eyes', 'white_check_mark')",
                },
            },
            "required": ["channel_id", "timestamp", "emoji"],
        },
        function=internal_slack_add_reaction_wrapper,
    )

    registry.register_tool(
        name="internal_slack_send_dm",
        description=(
            "Send a direct message (DM) to a Slack user. Returns channel_id and message_ts. "
            "When sending this DM on behalf of a user in another channel (e.g., Raju asked you "
            "to reach out to someone), set report_back_channel_id to the channel ID from the "
            "[Slack Context] header of Raju's message. The bot will then automatically notify "
            "Raju's channel the moment the DM recipient replies — Raju does not need to ask."
        ),
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "Slack user ID (e.g., 'U1234567890'). This is the unique identifier for the user, not their display name.",
                },
                "text": {"type": "string", "description": "Message text to send to the user"},
                "report_back_channel_id": {
                    "type": "string",
                    "description": (
                        "Optional. Channel ID to notify automatically when the DM recipient replies. "
                        "Extract this from the (ID: ...) part of the [Slack Context] header in the "
                        "current message. Set this whenever you are sending a DM on behalf of someone "
                        "else so they receive an instant update without needing to ask."
                    ),
                },
            },
            "required": ["user_id", "text"],
        },
        function=internal_slack_send_dm_wrapper,
    )

    registry.register_tool(
        name="internal_slack_post_blocks",
        description=(
            "Post a rich Block Kit message to a Slack channel — supports images, sections, "
            "dividers, and formatted text.\n\n"
            "PRIMARY USE-CASE — posting infographic images:\n"
            "After calling internal_generate_infographic, post the result to Slack like this:\n\n"
            "[\n"
            '  {"type": "section", "text": {"type": "mrkdwn", "text": "*Daily Briefing*"}},\n'
            '  {"type": "image",\n'
            '   "image_url": "<png_url from infographic result>",\n'
            '   "alt_text": "Daily Operations Briefing"}\n'
            "]\n\n"
            "The image block requires a publicly accessible URL. Use the png_url or svg_url "
            "returned by internal_generate_infographic (uploaded to S3). "
            "If S3 is not configured, use internal_slack_upload_file with svg_content instead.\n\n"
            "Other useful block types: section (text), divider, context (small text), "
            "actions (buttons), header (bold title)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Slack channel ID (e.g. 'C1234567890')"},
                "blocks": {
                    "type": "string",
                    "description": "JSON array of Block Kit block objects as a string",
                },
                "text": {
                    "type": "string",
                    "description": "Fallback plain text for notifications and accessibility (recommended)",
                    "default": "",
                },
                "thread_ts": {
                    "type": "string",
                    "description": "Optional thread timestamp to reply in thread",
                },
            },
            "required": ["channel_id", "blocks"],
        },
        function=internal_slack_post_blocks_wrapper,
    )

    registry.register_tool(
        name="internal_slack_upload_file",
        description=(
            "Upload a file (SVG, PNG, CSV, PDF, etc.) directly to a Slack channel.\n\n"
            "PRIMARY USE-CASE — posting infographics without S3:\n"
            "If internal_generate_infographic returns svg_content (for small infographics), "
            "pass it here as file_content with filename='briefing.svg'. Slack renders SVG inline.\n\n"
            "Also useful for: sharing CSV exports, PDF reports, or any file the agent generates.\n\n"
            "If you only have a URL (e.g. the image_url returned by internal_browser_screenshot or "
            "internal_generate_infographic), pass it as file_url — this tool will download it and "
            "attach the bytes as a genuine Slack file. Provide either file_content or file_url, not both "
            "(file_content wins if both are given).\n\n"
            "Prefer internal_slack_post_blocks with image_url when you have a public S3 URL, "
            "because that renders at full resolution. Use this tool (with file_url) when you want "
            "a real Slack-native file attachment instead of a linked image."
        ),
        parameters={
            "type": "object",
            "properties": {
                "channel_id": {"type": "string", "description": "Slack channel ID (e.g. 'C1234567890')"},
                "file_content": {
                    "type": "string",
                    "description": "Raw file content as a string (SVG markup, CSV text, etc.)",
                },
                "file_url": {
                    "type": "string",
                    "description": "URL to download and upload as the file, e.g. an S3 image_url from a screenshot",
                },
                "filename": {
                    "type": "string",
                    "description": "Filename including extension, e.g. 'daily-briefing.svg' or 'report.csv'",
                },
                "title": {
                    "type": "string",
                    "description": "Optional display title shown above the file in Slack",
                    "default": "",
                },
                "initial_comment": {
                    "type": "string",
                    "description": "Optional message text posted alongside the file",
                    "default": "",
                },
                "thread_ts": {
                    "type": "string",
                    "description": "Optional thread timestamp to upload into a thread",
                },
            },
            "required": ["channel_id", "filename"],
        },
        function=internal_slack_upload_file_wrapper,
    )

    registry.register_tool(
        name="internal_slack_create_channel",
        description=(
            "Create a new Slack channel. Use this when asked to open/create a channel that "
            "doesn't already exist — internal_slack_list_channels only finds existing channels. "
            "Channel names must be lowercase, without spaces (use hyphens or underscores instead)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name for the new channel (lowercase, no spaces, e.g. 'bughunt-home-deriv')",
                },
                "is_private": {
                    "type": "boolean",
                    "description": "Whether to create a private channel (default False, i.e. public)",
                    "default": False,
                },
            },
            "required": ["name"],
        },
        function=internal_slack_create_channel_wrapper,
    )

    logger.info("Registered 11 Slack tools")
