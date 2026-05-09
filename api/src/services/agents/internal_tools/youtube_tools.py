"""
YouTube Tools for video transcript extraction and summarization.
Uses youtube-transcript-api for transcript extraction (no auth required).
Uses YouTube Data API v3 for video search (requires API key via OAuthApp).

This tool enables:
- Transcript extraction from YouTube videos
- Multi-language support with translation
- Video summarization via transcript processing
- Searching recent videos by query or channel (YouTube Data API v3)
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


async def _get_youtube_api_key(runtime_context: Any) -> str:
    """
    Resolve YouTube Data API key from OAuthApp via runtime context.

    Resolution order:
    1. User's personal token (UserOAuthToken.access_token)
    2. OAuthApp.api_token fallback
    """
    from sqlalchemy import select

    from src.models.agent_tool import AgentTool
    from src.models.oauth_app import OAuthApp
    from src.models.user_oauth_token import UserOAuthToken
    from src.services.agents.security import decrypt_value

    db = runtime_context.db_session

    result = await db.execute(
        select(AgentTool).filter(
            AgentTool.agent_id == runtime_context.agent_id,
            AgentTool.tool_name == "internal_youtube_search_videos",
            AgentTool.enabled,
        )
    )
    agent_tool = result.scalar_one_or_none()

    if not agent_tool or not agent_tool.oauth_app_id:
        raise ValueError(
            "No OAuth app configured for internal_youtube_search_videos. Please add a YouTube Data API OAuth app."
        )

    result = await db.execute(
        select(OAuthApp).filter(
            OAuthApp.id == agent_tool.oauth_app_id,
            OAuthApp.provider.ilike("youtube"),
            OAuthApp.is_active,
        )
    )
    oauth_app = result.scalar_one_or_none()

    if not oauth_app:
        raise ValueError("No active YouTube OAuth app found")

    result = await db.execute(select(UserOAuthToken).filter(UserOAuthToken.oauth_app_id == oauth_app.id))
    user_token = result.scalar_one_or_none()

    if user_token and user_token.access_token:
        return decrypt_value(user_token.access_token)

    if oauth_app.api_token:
        return decrypt_value(oauth_app.api_token)

    raise ValueError("No YouTube API key available. Please add an api_token to the YouTube OAuth app.")


async def internal_youtube_search_videos(
    query: str,
    channel_id: str | None = None,
    max_results: int = 10,
    published_after_hours: int = 168,
    order: str = "date",
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Search for recent YouTube videos using the YouTube Data API v3.

    Args:
        query: Search query string (e.g., "AI news", "machine learning tutorial")
        channel_id: Optional channel ID to restrict search to a specific channel
        max_results: Maximum number of results (1-50, default 10)
        published_after_hours: Only return videos published in the last N hours (default 168 = 7 days)
        order: Sort order: date | relevance | viewCount | rating (default: date)
        runtime_context: Agent runtime context for credential resolution
        config: Optional configuration dictionary

    Returns:
        Dictionary with videos list and metadata

    Example:
        result = await internal_youtube_search_videos(
            query="AI news today",
            max_results=5,
            published_after_hours=48,
        )
    """
    if not runtime_context:
        return {"success": False, "error": "Runtime context is required"}

    if not query and not channel_id:
        return {"success": False, "error": "Either query or channel_id is required"}

    try:
        api_key = await _get_youtube_api_key(runtime_context)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    published_after = (datetime.now(UTC) - timedelta(hours=published_after_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    params: dict[str, Any] = {
        "part": "snippet",
        "type": "video",
        "order": order,
        "maxResults": min(max(1, max_results), 50),
        "publishedAfter": published_after,
        "key": api_key,
    }
    if query:
        params["q"] = query
    if channel_id:
        params["channelId"] = channel_id

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{YOUTUBE_API_BASE}/search", params=params)

        if response.status_code == 400:
            return {
                "success": False,
                "error": f"Bad request: {response.json().get('error', {}).get('message', 'unknown')}",
            }
        if response.status_code == 403:
            return {"success": False, "error": "YouTube API quota exceeded or invalid key"}
        response.raise_for_status()

        data = response.json()
        videos = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            videos.append(
                {
                    "title": snippet.get("title", ""),
                    "channel": snippet.get("channelTitle", ""),
                    "description": snippet.get("description", "")[:200],
                    "published_at": snippet.get("publishedAt", ""),
                    "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
                    "thumbnail_url": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                    "video_id": video_id,
                }
            )

        return {
            "success": True,
            "videos": videos,
            "count": len(videos),
            "total_results": data.get("pageInfo", {}).get("totalResults", len(videos)),
        }

    except httpx.TimeoutException:
        return {"success": False, "error": "YouTube API request timed out"}
    except Exception as e:
        logger.error(f"YouTube search failed: {e}", exc_info=True)
        return {"success": False, "error": f"YouTube search failed: {str(e)}"}


# Check for youtube-transcript-api availability
_TRANSCRIPT_API_AVAILABLE = False
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
    )

    _TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    logger.warning("youtube-transcript-api not installed. Install with: pip install youtube-transcript-api")


def _extract_video_id(url_or_id: str) -> str:
    """
    Extract video ID from YouTube URL or return as-is if already an ID.

    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - VIDEO_ID (direct ID)
    """
    if not url_or_id:
        return ""

    # Already a video ID (11 characters, alphanumeric with _ and -)
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
        return url_or_id

    # YouTube URL patterns
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    return url_or_id


async def internal_youtube_get_transcript(
    video_id: str,
    languages: list[str] | None = None,
    translate_to: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get transcript/captions from a YouTube video.

    Args:
        video_id: YouTube video ID or URL
        languages: Preferred languages in order of preference (e.g., ['en', 'es'])
                  Defaults to ['en'] if not specified
        translate_to: Translate transcript to this language code (e.g., 'en', 'es', 'fr')

    Returns:
        Transcript text with metadata
    """
    if not _TRANSCRIPT_API_AVAILABLE:
        return {
            "success": False,
            "error": "youtube-transcript-api not installed. Install with: pip install youtube-transcript-api",
        }

    try:
        # Extract video ID from URL if needed
        video_id = _extract_video_id(video_id)
        if not video_id:
            return {"success": False, "error": "Invalid video ID or URL"}

        # Default to English
        if not languages:
            languages = ["en"]

        # Get available transcripts
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Try to find transcript in preferred languages
        transcript = None
        transcript_language = None

        # First, try manually created transcripts
        for lang in languages:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                transcript_language = lang
                break
            except NoTranscriptFound:
                continue

        # If no manual transcript, try auto-generated
        if not transcript:
            for lang in languages:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    transcript_language = lang
                    break
                except NoTranscriptFound:
                    continue

        # If still no transcript, get any available
        if not transcript:
            try:
                # Get first available transcript
                for t in transcript_list:
                    transcript = t
                    transcript_language = t.language_code
                    break
            except Exception:
                pass

        if not transcript:
            return {
                "success": False,
                "error": "No transcript available for this video",
                "video_id": video_id,
            }

        # Translate if requested
        if translate_to and translate_to != transcript_language:
            try:
                transcript = transcript.translate(translate_to)
                transcript_language = translate_to
            except Exception as e:
                logger.warning(f"Translation failed: {e}")

        # Fetch the transcript data
        transcript_data = transcript.fetch()

        # Combine into full text
        full_text = " ".join([entry["text"] for entry in transcript_data])

        # Also create timestamped version
        timestamped_entries = []
        for entry in transcript_data:
            start_time = entry["start"]
            minutes = int(start_time // 60)
            seconds = int(start_time % 60)
            timestamped_entries.append(
                {
                    "timestamp": f"{minutes:02d}:{seconds:02d}",
                    "start_seconds": entry["start"],
                    "duration": entry["duration"],
                    "text": entry["text"],
                }
            )

        return {
            "success": True,
            "video_id": video_id,
            "language": transcript_language,
            "is_generated": transcript.is_generated,
            "full_text": full_text,
            "word_count": len(full_text.split()),
            "segments": timestamped_entries,
            "segment_count": len(timestamped_entries),
        }

    except TranscriptsDisabled:
        return {
            "success": False,
            "error": "Transcripts are disabled for this video",
            "video_id": video_id,
        }
    except VideoUnavailable:
        return {
            "success": False,
            "error": "Video is unavailable",
            "video_id": video_id,
        }
    except Exception as e:
        logger.error(f"Failed to get YouTube transcript: {e}")
        return {"success": False, "error": str(e), "video_id": video_id}


async def internal_youtube_list_transcript_languages(
    video_id: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    List available transcript languages for a YouTube video.

    Args:
        video_id: YouTube video ID or URL

    Returns:
        List of available languages with metadata
    """
    if not _TRANSCRIPT_API_AVAILABLE:
        return {
            "success": False,
            "error": "youtube-transcript-api not installed. Install with: pip install youtube-transcript-api",
        }

    try:
        video_id = _extract_video_id(video_id)
        if not video_id:
            return {"success": False, "error": "Invalid video ID or URL"}

        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        languages = []
        for transcript in transcript_list:
            languages.append(
                {
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated,
                    "is_translatable": transcript.is_translatable,
                }
            )

        return {
            "success": True,
            "video_id": video_id,
            "languages": languages,
            "count": len(languages),
        }

    except TranscriptsDisabled:
        return {
            "success": False,
            "error": "Transcripts are disabled for this video",
            "video_id": video_id,
        }
    except VideoUnavailable:
        return {
            "success": False,
            "error": "Video is unavailable",
            "video_id": video_id,
        }
    except Exception as e:
        logger.error(f"Failed to list transcript languages: {e}")
        return {"success": False, "error": str(e), "video_id": video_id}


async def internal_youtube_get_transcript_segment(
    video_id: str,
    start_time: float,
    end_time: float,
    languages: list[str] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Get a specific segment of transcript by time range.

    Args:
        video_id: YouTube video ID or URL
        start_time: Start time in seconds
        end_time: End time in seconds
        languages: Preferred languages

    Returns:
        Transcript segment for the specified time range
    """
    if not _TRANSCRIPT_API_AVAILABLE:
        return {
            "success": False,
            "error": "youtube-transcript-api not installed",
        }

    try:
        # Get full transcript first
        result = await internal_youtube_get_transcript(
            video_id=video_id,
            languages=languages,
            config=config,
            runtime_context=runtime_context,
        )

        if not result.get("success"):
            return result

        # Filter segments by time range
        segments = result.get("segments", [])
        filtered_segments = [
            seg for seg in segments if seg["start_seconds"] >= start_time and seg["start_seconds"] <= end_time
        ]

        # Combine text
        segment_text = " ".join([seg["text"] for seg in filtered_segments])

        return {
            "success": True,
            "video_id": _extract_video_id(video_id),
            "start_time": start_time,
            "end_time": end_time,
            "text": segment_text,
            "segments": filtered_segments,
            "segment_count": len(filtered_segments),
        }

    except Exception as e:
        logger.error(f"Failed to get transcript segment: {e}")
        return {"success": False, "error": str(e)}
