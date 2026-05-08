"""
YouTube Tools Registry

Registers YouTube transcript tools with the ADK tool registry.
These tools enable video transcript extraction and summarization.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_youtube_tools(registry):
    """
    Register all YouTube tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.youtube_tools import (
        internal_youtube_get_transcript,
        internal_youtube_get_transcript_segment,
        internal_youtube_list_transcript_languages,
        internal_youtube_search_videos,
    )

    # YouTube tools - create wrappers that inject runtime_context
    async def internal_youtube_get_transcript_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_youtube_get_transcript(
            video_id=kwargs.get("video_id"),
            languages=kwargs.get("languages"),
            translate_to=kwargs.get("translate_to"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_youtube_list_transcript_languages_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_youtube_list_transcript_languages(
            video_id=kwargs.get("video_id"),
            runtime_context=runtime_context,
            config=config,
        )

    async def internal_youtube_get_transcript_segment_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_youtube_get_transcript_segment(
            video_id=kwargs.get("video_id"),
            start_time=kwargs.get("start_time"),
            end_time=kwargs.get("end_time"),
            languages=kwargs.get("languages"),
            runtime_context=runtime_context,
            config=config,
        )

    # Register YouTube tools
    registry.register_tool(
        name="internal_youtube_get_transcript",
        description="Extract the full transcript/captions from a YouTube video. Use this to get the text content of videos for summarization, analysis, or reference. Supports multiple languages and translation.",
        parameters={
            "type": "object",
            "properties": {
                "video_id": {
                    "type": "string",
                    "description": "YouTube video ID or full URL (e.g., 'dQw4w9WgXcQ' or 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')",
                },
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Preferred languages in order of preference (e.g., ['en', 'es']). Defaults to ['en']",
                },
                "translate_to": {
                    "type": "string",
                    "description": "Translate the transcript to this language code (e.g., 'en', 'es', 'fr')",
                },
            },
            "required": ["video_id"],
        },
        function=internal_youtube_get_transcript_wrapper,
    )

    registry.register_tool(
        name="internal_youtube_list_transcript_languages",
        description="List all available transcript languages for a YouTube video. Use this to discover what language options are available before fetching a transcript.",
        parameters={
            "type": "object",
            "properties": {
                "video_id": {
                    "type": "string",
                    "description": "YouTube video ID or full URL",
                },
            },
            "required": ["video_id"],
        },
        function=internal_youtube_list_transcript_languages_wrapper,
    )

    registry.register_tool(
        name="internal_youtube_get_transcript_segment",
        description="Get a specific segment of a YouTube transcript by time range. Use this when you only need a portion of a video's content.",
        parameters={
            "type": "object",
            "properties": {
                "video_id": {
                    "type": "string",
                    "description": "YouTube video ID or full URL",
                },
                "start_time": {
                    "type": "number",
                    "description": "Start time in seconds",
                },
                "end_time": {
                    "type": "number",
                    "description": "End time in seconds",
                },
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Preferred languages",
                },
            },
            "required": ["video_id", "start_time", "end_time"],
        },
        function=internal_youtube_get_transcript_segment_wrapper,
    )

    async def internal_youtube_search_videos_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_youtube_search_videos(
            query=kwargs.get("query", ""),
            channel_id=kwargs.get("channel_id"),
            max_results=kwargs.get("max_results", 10),
            published_after_hours=kwargs.get("published_after_hours", 168),
            order=kwargs.get("order", "date"),
            runtime_context=runtime_context,
            config=config,
        )

    registry.register_tool(
        name="internal_youtube_search_videos",
        description="Search for recent YouTube videos using the YouTube Data API v3. Use this to find the latest AI/tech videos by keyword or from specific channels. Requires a YouTube Data API key configured as an OAuth app.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g. 'AI news today', 'machine learning new model')",
                },
                "channel_id": {
                    "type": "string",
                    "description": "Optional YouTube channel ID to restrict search to a specific channel",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-50, default 10)",
                    "default": 10,
                },
                "published_after_hours": {
                    "type": "integer",
                    "description": "Only return videos published in the last N hours (default 168 = 7 days)",
                    "default": 168,
                },
                "order": {
                    "type": "string",
                    "description": "Sort order: date | relevance | viewCount | rating (default: date)",
                    "enum": ["date", "relevance", "viewCount", "rating"],
                    "default": "date",
                },
            },
            "required": ["query"],
        },
        function=internal_youtube_search_videos_wrapper,
    )

    logger.info("Registered 4 YouTube tools")
