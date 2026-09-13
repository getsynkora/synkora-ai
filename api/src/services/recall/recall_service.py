"""
Recall.ai Service for Meeting Bot Integration.

Provides functionality to send bots to meetings (Zoom, Google Meet, Teams, Slack Huddles),
retrieve transcripts, recordings, and manage meeting bot lifecycle.

Docs: https://docs.recall.ai/
"""

import base64
import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class RecallService:
    """
    Service for interacting with Recall.ai Meeting Bot API.

    Supports:
    - Sending bots to meetings (Zoom, Google Meet, Teams, Webex, Slack Huddles)
    - Retrieving transcripts and recordings
    - Managing bot lifecycle
    - Webhook verification
    """

    def __init__(self, api_key: str, region: str = "us-east-1", webhook_base_url: str | None = None):
        """
        Initialize Recall.ai service.

        Args:
            api_key: Recall.ai API key
            region: API region (us-east-1 or eu-west-1)
            webhook_base_url: Base URL for webhooks (e.g., https://api.synkora.ai)
        """
        self.api_key = api_key
        self.region = region
        self.base_url = f"https://{region}.recall.ai/api/v1"
        self.webhook_base_url = webhook_base_url
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }

    async def send_bot_to_meeting(
        self,
        meeting_url: str,
        bot_name: str = "Synkora Agent",
        join_at: datetime | None = None,
        automatic_leave: dict | None = None,
        recording_config: dict | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Send a bot to join a meeting.

        Args:
            meeting_url: Meeting URL (Zoom, Google Meet, Teams, Slack Huddle, etc.)
            bot_name: Display name for the bot in the meeting
            join_at: Scheduled time to join (None = join immediately)
            automatic_leave: Auto-leave config (e.g., {"waiting_room_timeout": 300})
            recording_config: Custom recording configuration
            agent_id: Synkora agent ID for webhook routing

        Returns:
            Bot creation response with bot ID and status
        """
        try:
            # Build recording config with transcription and webhooks
            config = recording_config or {}

            # Enable transcription if not configured
            if "transcript" not in config:
                config["transcript"] = {
                    "provider": {
                        "recallai_streaming": {}  # Use Recall.ai's built-in transcription
                    }
                }

            # Add webhook endpoints for real-time events
            if self.webhook_base_url and "realtime_endpoints" not in config:
                webhook_url = f"{self.webhook_base_url}/api/webhooks/recall"
                if agent_id:
                    webhook_url = f"{webhook_url}?agent_id={agent_id}"

                config["realtime_endpoints"] = [
                    {
                        "type": "webhook",
                        "url": webhook_url,
                        "events": [
                            "transcript.data",
                            "bot.status_change",
                            "participant_events.join",
                            "participant_events.leave",
                        ],
                    }
                ]

            # Build request payload
            payload: dict[str, Any] = {
                "meeting_url": meeting_url,
                "bot_name": bot_name,
                "recording_config": config,
            }

            # Add scheduled join time if specified
            if join_at:
                payload["join_at"] = join_at.isoformat()

            # Add automatic leave config
            if automatic_leave:
                payload["automatic_leave"] = automatic_leave
            else:
                # Default: leave after 5 min in waiting room or 2 min alone
                payload["automatic_leave"] = {
                    "waiting_room_timeout": 300,
                    "noone_joined_timeout": 120,
                }

            # Add metadata for tracking
            if agent_id:
                payload["metadata"] = {"synkora_agent_id": agent_id}

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self.base_url}/bot/",
                    headers=self.headers,
                    json=payload,
                ) as response,
            ):
                if response.status in [200, 201]:
                    result = await response.json()
                    logger.info(f"Successfully created Recall bot: {result.get('id')}")
                    return {
                        "success": True,
                        "data": {
                            "bot_id": result.get("id"),
                            "status": result.get("status", {}).get("code"),
                            "meeting_url": meeting_url,
                            "bot_name": bot_name,
                            "join_at": payload.get("join_at"),
                        },
                        "message": f"Bot '{bot_name}' sent to join meeting",
                    }
                else:
                    error_data = await response.json()
                    logger.error(f"Recall API error: {error_data}")
                    return {
                        "success": False,
                        "error": error_data.get("detail", str(error_data)),
                    }

        except Exception as e:
            logger.error(f"Failed to send bot to meeting: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_bot(self, bot_id: str) -> dict[str, Any]:
        """
        Get bot details and status.

        Args:
            bot_id: Recall bot ID

        Returns:
            Bot details including status, recordings, transcript
        """
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    f"{self.base_url}/bot/{bot_id}/",
                    headers=self.headers,
                ) as response,
            ):
                if response.status == 200:
                    result = await response.json()

                    # Extract useful info
                    status = result.get("status", {})
                    recordings = result.get("recordings", [])
                    media_shortcuts = result.get("media_shortcuts", {})

                    return {
                        "success": True,
                        "data": {
                            "bot_id": bot_id,
                            "status_code": status.get("code"),
                            "status_message": status.get("message"),
                            "meeting_url": result.get("meeting_url", {}).get("url"),
                            "bot_name": result.get("bot_name"),
                            "join_at": result.get("join_at"),
                            "recordings": recordings,
                            "video_url": media_shortcuts.get("video_mixed", {}).get("data", {}).get("download_url"),
                            "transcript_url": media_shortcuts.get("transcript", {}).get("data", {}).get("download_url"),
                            "created_at": result.get("created_at"),
                        },
                    }
                elif response.status == 404:
                    return {"success": False, "error": f"Bot {bot_id} not found"}
                else:
                    error_data = await response.json()
                    return {"success": False, "error": error_data.get("detail", str(error_data))}

        except Exception as e:
            logger.error(f"Failed to get bot {bot_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def list_bots(
        self,
        status: str | None = None,
        meeting_url: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """
        List bots with optional filtering.

        Args:
            status: Filter by status (e.g., "in_call_recording", "done")
            meeting_url: Filter by meeting URL
            limit: Maximum number of bots to return

        Returns:
            List of bots
        """
        try:
            params: dict[str, Any] = {"limit": limit}
            if status:
                params["status"] = status
            if meeting_url:
                params["meeting_url"] = meeting_url

            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    f"{self.base_url}/bot/",
                    headers=self.headers,
                    params=params,
                ) as response,
            ):
                if response.status == 200:
                    result = await response.json()
                    bots = result.get("results", [])

                    formatted_bots = []
                    for bot in bots:
                        status_info = bot.get("status", {})
                        formatted_bots.append(
                            {
                                "bot_id": bot.get("id"),
                                "bot_name": bot.get("bot_name"),
                                "status_code": status_info.get("code"),
                                "meeting_url": bot.get("meeting_url", {}).get("url"),
                                "created_at": bot.get("created_at"),
                            }
                        )

                    return {
                        "success": True,
                        "data": {
                            "bots": formatted_bots,
                            "total": len(formatted_bots),
                        },
                    }
                else:
                    error_data = await response.json()
                    return {"success": False, "error": error_data.get("detail", str(error_data))}

        except Exception as e:
            logger.error(f"Failed to list bots: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def remove_bot(self, bot_id: str) -> dict[str, Any]:
        """
        Remove/stop a bot from a meeting.

        Args:
            bot_id: Recall bot ID

        Returns:
            Removal status
        """
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    f"{self.base_url}/bot/{bot_id}/leave_call/",
                    headers=self.headers,
                ) as response,
            ):
                if response.status in [200, 204]:
                    logger.info(f"Successfully removed bot {bot_id} from meeting")
                    return {
                        "success": True,
                        "message": f"Bot {bot_id} removed from meeting",
                    }
                elif response.status == 404:
                    return {"success": False, "error": f"Bot {bot_id} not found"}
                else:
                    error_data = await response.json()
                    return {"success": False, "error": error_data.get("detail", str(error_data))}

        except Exception as e:
            logger.error(f"Failed to remove bot {bot_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_transcript(self, bot_id: str) -> dict[str, Any]:
        """
        Get the transcript for a completed meeting.

        Args:
            bot_id: Recall bot ID

        Returns:
            Transcript data with speaker identification
        """
        try:
            # First get bot to check status and get transcript URL
            bot_result = await self.get_bot(bot_id)
            if not bot_result.get("success"):
                return bot_result

            bot_data = bot_result.get("data", {})
            status = bot_data.get("status_code")

            if status != "done":
                return {
                    "success": False,
                    "error": f"Meeting not yet complete. Current status: {status}",
                }

            transcript_url = bot_data.get("transcript_url")
            if not transcript_url:
                return {
                    "success": False,
                    "error": "No transcript available for this meeting",
                }

            # Fetch the transcript
            async with aiohttp.ClientSession() as session, session.get(transcript_url) as response:
                if response.status == 200:
                    transcript_data = await response.json()

                    # Format transcript with speaker labels
                    formatted_transcript = []
                    for segment in transcript_data:
                        speaker = segment.get("speaker", "Unknown")
                        words = segment.get("words", [])
                        text = " ".join([w.get("text", "") for w in words])
                        start_time = words[0].get("start_timestamp") if words else None

                        formatted_transcript.append(
                            {
                                "speaker": speaker,
                                "text": text,
                                "start_time": start_time,
                            }
                        )

                    # Create full text version
                    full_text = "\n\n".join([f"**{seg['speaker']}**: {seg['text']}" for seg in formatted_transcript])

                    return {
                        "success": True,
                        "data": {
                            "bot_id": bot_id,
                            "segments": formatted_transcript,
                            "full_text": full_text,
                            "segment_count": len(formatted_transcript),
                        },
                    }
                else:
                    return {"success": False, "error": "Failed to fetch transcript"}

        except Exception as e:
            logger.error(f"Failed to get transcript for bot {bot_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_recording(self, bot_id: str) -> dict[str, Any]:
        """
        Get the recording URL for a completed meeting.

        Args:
            bot_id: Recall bot ID

        Returns:
            Recording download URL
        """
        try:
            bot_result = await self.get_bot(bot_id)
            if not bot_result.get("success"):
                return bot_result

            bot_data = bot_result.get("data", {})
            status = bot_data.get("status_code")

            if status != "done":
                return {
                    "success": False,
                    "error": f"Meeting not yet complete. Current status: {status}",
                }

            video_url = bot_data.get("video_url")
            if not video_url:
                return {
                    "success": False,
                    "error": "No recording available for this meeting",
                }

            return {
                "success": True,
                "data": {
                    "bot_id": bot_id,
                    "video_url": video_url,
                    "meeting_url": bot_data.get("meeting_url"),
                },
            }

        except Exception as e:
            logger.error(f"Failed to get recording for bot {bot_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    @staticmethod
    def verify_webhook_signature(payload: bytes, headers: Any, webhook_secret: str) -> bool:
        """Verify Recall/Standard Webhooks ID, timestamp and raw body together.

        Supports both webhook-* and legacy svix-* header names. See
        https://docs.recall.ai/docs/authenticating-requests-from-recallai
        """
        try:
            message_id = headers.get("webhook-id") or headers.get("svix-id")
            timestamp = headers.get("webhook-timestamp") or headers.get("svix-timestamp")
            signature = headers.get("webhook-signature") or headers.get("svix-signature")
            if not message_id or not timestamp or not signature or not webhook_secret.startswith("whsec_"):
                return False
            if abs(time.time() - int(timestamp)) > 300:
                return False
            key = base64.b64decode(webhook_secret[6:], validate=True)
            if not key:
                return False
            signed = f"{message_id}.{timestamp}.".encode() + payload
            expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
            return any(
                candidate.startswith("v1,") and hmac.compare_digest(expected, candidate[3:])
                for candidate in signature.split()
            )
        except (ValueError, TypeError, AttributeError):
            return False


# Bot status codes reference
BOT_STATUS_CODES = {
    "ready": "Bot is ready to join",
    "joining_call": "Bot is joining the meeting",
    "in_waiting_room": "Bot is in the waiting room",
    "in_call_not_recording": "Bot joined but not recording yet",
    "in_call_recording": "Bot is actively recording",
    "call_ended": "Meeting has ended",
    "done": "Recording complete and processed",
    "fatal": "Bot encountered an error",
    "analysis_done": "Post-processing complete",
}
