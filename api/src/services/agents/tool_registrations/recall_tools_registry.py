"""
Recall.ai Tools Registry

Registers Recall.ai meeting bot tools with the ADK tool registry.
Requires Recall.ai API key configuration via OAuth Apps.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_recall_tools(registry):
    """
    Register all Recall.ai tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.recall_tools import (
        internal_recall_get_bot_status,
        internal_recall_get_recording,
        internal_recall_get_transcript,
        internal_recall_list_bots,
        internal_recall_remove_bot,
        internal_recall_send_bot,
        internal_recall_summarize_meeting,
    )

    # Create wrappers that inject runtime_context

    async def internal_recall_send_bot_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        # Check meeting_bot.enabled from voice_meetings_config
        if runtime_context and hasattr(runtime_context, "agent"):
            vm_cfg = ((runtime_context.agent.agent_metadata or {}).get("voice_meetings_config") or {})
            if not vm_cfg.get("meeting_bot", {}).get("enabled", False):
                return {"success": False, "error": "Meeting bot is not enabled for this agent. Enable it in Voice & Meetings settings."}
            bot_name = vm_cfg.get("meeting_bot", {}).get("bot_name") or kwargs.get("bot_name", "AI Assistant")
        else:
            bot_name = kwargs.get("bot_name", "AI Assistant")
        return await internal_recall_send_bot(
            meeting_url=kwargs.get("meeting_url"),
            bot_name=bot_name,
            join_at=kwargs.get("join_at"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_recall_get_bot_status_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_recall_get_bot_status(
            bot_id=kwargs.get("bot_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_recall_list_bots_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_recall_list_bots(
            status=kwargs.get("status"),
            limit=kwargs.get("limit", 20),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_recall_get_transcript_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_recall_get_transcript(
            bot_id=kwargs.get("bot_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_recall_get_recording_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_recall_get_recording(
            bot_id=kwargs.get("bot_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_recall_remove_bot_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_recall_remove_bot(
            bot_id=kwargs.get("bot_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_recall_summarize_meeting_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_recall_summarize_meeting(
            bot_id=kwargs.get("bot_id"),
            save_to_knowledge_base=kwargs.get("save_to_knowledge_base", False),
            knowledge_base_id=kwargs.get("knowledge_base_id"),
            runtime_context=runtime_context,
            config=config,
        )

    # Register tools

    registry.register_tool(
        name="internal_recall_send_bot",
        description="Send a meeting bot to join and record a meeting. Supports Zoom, Google Meet, Microsoft Teams, Webex, Slack Huddles, and GoTo Meeting. The bot will join, record audio/video, and generate a transcript.",
        parameters={
            "type": "object",
            "properties": {
                "meeting_url": {
                    "type": "string",
                    "description": "Meeting URL (e.g., https://zoom.us/j/123456789, https://meet.google.com/abc-defg-hij)",
                },
                "bot_name": {
                    "type": "string",
                    "description": "Display name for the bot in the meeting (default: 'Synkora Meeting Assistant')",
                    "default": "Synkora Meeting Assistant",
                },
                "join_at": {
                    "type": "string",
                    "description": "Scheduled time to join in ISO format (e.g., '2024-01-15T10:00:00Z'). If not provided, bot joins immediately.",
                },
            },
            "required": ["meeting_url"],
        },
        function=internal_recall_send_bot_wrapper,
    )

    registry.register_tool(
        name="internal_recall_get_bot_status",
        description="Get the current status of a meeting bot. Check if the bot has joined, is recording, or has finished. Status codes: ready, joining_call, in_waiting_room, in_call_recording, done, fatal.",
        parameters={
            "type": "object",
            "properties": {
                "bot_id": {
                    "type": "string",
                    "description": "The bot ID returned from send_bot",
                },
            },
            "required": ["bot_id"],
        },
        function=internal_recall_get_bot_status_wrapper,
    )

    registry.register_tool(
        name="internal_recall_list_bots",
        description="List all meeting bots with optional status filtering. Useful for checking ongoing or completed meeting recordings.",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["ready", "joining_call", "in_waiting_room", "in_call_recording", "done", "fatal"],
                    "description": "Filter bots by status",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of bots to return (default: 20)",
                    "default": 20,
                },
            },
            "required": [],
        },
        function=internal_recall_list_bots_wrapper,
    )

    registry.register_tool(
        name="internal_recall_get_transcript",
        description="Get the transcript from a completed meeting. Returns speaker-identified transcript with timestamps. The meeting must be complete (status='done') before transcript is available.",
        parameters={
            "type": "object",
            "properties": {
                "bot_id": {
                    "type": "string",
                    "description": "The bot ID from send_bot",
                },
            },
            "required": ["bot_id"],
        },
        function=internal_recall_get_transcript_wrapper,
    )

    registry.register_tool(
        name="internal_recall_get_recording",
        description="Get the video/audio recording URL from a completed meeting. The meeting must be complete (status='done') before recording is available.",
        parameters={
            "type": "object",
            "properties": {
                "bot_id": {
                    "type": "string",
                    "description": "The bot ID from send_bot",
                },
            },
            "required": ["bot_id"],
        },
        function=internal_recall_get_recording_wrapper,
    )

    registry.register_tool(
        name="internal_recall_remove_bot",
        description="Remove a bot from a meeting, making it leave early. Use this to stop recording before the meeting ends.",
        parameters={
            "type": "object",
            "properties": {
                "bot_id": {
                    "type": "string",
                    "description": "The bot ID to remove from the meeting",
                },
            },
            "required": ["bot_id"],
        },
        function=internal_recall_remove_bot_wrapper,
    )

    registry.register_tool(
        name="internal_recall_summarize_meeting",
        description="Get the transcript from a completed meeting and prepare it for summarization. Optionally save to knowledge base. Use this after a meeting is complete to get key points, action items, and decisions.",
        parameters={
            "type": "object",
            "properties": {
                "bot_id": {
                    "type": "string",
                    "description": "The bot ID from a completed meeting",
                },
                "save_to_knowledge_base": {
                    "type": "boolean",
                    "description": "Whether to save the transcript to knowledge base",
                    "default": False,
                },
                "knowledge_base_id": {
                    "type": "string",
                    "description": "Specific knowledge base ID to save to (uses agent's default if not specified)",
                },
            },
            "required": ["bot_id"],
        },
        function=internal_recall_summarize_meeting_wrapper,
    )

    logger.info("Registered 7 Recall.ai meeting bot tools")
