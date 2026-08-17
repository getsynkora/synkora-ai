"""Service for managing Slack thread status indicators."""

import logging
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

logger = logging.getLogger(__name__)


class SlackStatusService:
    """
    Service for managing native Slack typing/status indicators.

    Uses the assistant.threads.setStatus API to show native Slack
    typing indicators like "BotName is thinking..." instead of posting
    actual messages that clutter the conversation.
    """

    def __init__(self, client: AsyncWebClient) -> None:
        """
        Initialize the status service.

        Args:
            client: Slack AsyncWebClient instance
        """
        self.client = client

    async def set_status(
        self,
        channel_id: str,
        thread_ts: str,
        status: str = "is thinking...",
        loading_messages: list[str] | None = None,
    ) -> bool:
        """
        Set a status indicator on a Slack thread.

        This uses the assistant.threads.setStatus API to show a native
        Slack typing/status indicator like "BotName is thinking..."

        Args:
            channel_id: The channel ID containing the thread
            thread_ts: The thread timestamp (parent message ts)
            status: The status text to display (e.g., "is thinking...")
            loading_messages: Custom messages Slack rotates through in the
                in-thread loading indicator (max 10). Without this, Slack
                substitutes its own generic placeholder text (e.g.
                "Summarising findings...") instead of our real status.

        Returns:
            True if status was set successfully, False otherwise

        Note:
            Failures are logged but don't raise exceptions to avoid blocking
            message processing if the status API is unavailable.
        """
        payload: dict[str, Any] = {
            "status": status,
            "channel_id": channel_id,
            "thread_ts": thread_ts,
        }
        if loading_messages:
            payload["loading_messages"] = loading_messages[:10]
        try:
            response = await self.client.api_call(
                api_method="assistant.threads.setStatus",
                json=payload,
            )
            if not response.get("ok"):
                error = response.get("error", "unknown_error")
                if error == "missing_scope":
                    needed_scope = response.get("needed", "assistant:write")
                    logger.warning(
                        f"Status API requires '{needed_scope}' scope. "
                        f"Add this scope in your Slack app settings and reinstall the app."
                    )
                else:
                    logger.warning(f"Failed to set thread status: {error}")
                return False
            logger.debug(f"Set thread status for channel {channel_id}, thread {thread_ts}: {status}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set thread status for channel {channel_id}: {e}")
            return False

    async def set_thinking(self, channel_id: str, thread_ts: str) -> bool:
        """
        Set the "thinking" status indicator.

        Args:
            channel_id: The channel ID containing the thread
            thread_ts: The thread timestamp

        Returns:
            True if status was set successfully
        """
        status = "is thinking..."
        return await self.set_status(channel_id, thread_ts, status, loading_messages=[status])

    async def set_generating(self, channel_id: str, thread_ts: str) -> bool:
        """
        Set the "generating response" status indicator.

        Args:
            channel_id: The channel ID containing the thread
            thread_ts: The thread timestamp

        Returns:
            True if status was set successfully
        """
        status = "is generating a response..."
        return await self.set_status(channel_id, thread_ts, status, loading_messages=[status])

    async def set_custom_status(self, channel_id: str, thread_ts: str, action: str) -> bool:
        """
        Set a custom status indicator.

        Args:
            channel_id: The channel ID containing the thread
            thread_ts: The thread timestamp
            action: Custom action text (e.g., "is searching...", "is analyzing...")

        Returns:
            True if status was set successfully
        """
        return await self.set_status(channel_id, thread_ts, action, loading_messages=[action])

    async def clear_status(self, channel_id: str, thread_ts: str) -> bool:
        """
        Clear the status indicator on a Slack thread.

        This sends an empty status string to remove the typing indicator.
        Note that Slack also auto-clears the status when a message is sent.

        Args:
            channel_id: The channel ID containing the thread
            thread_ts: The thread timestamp

        Returns:
            True if status was cleared successfully
        """
        try:
            response = await self.client.api_call(
                api_method="assistant.threads.setStatus",
                json={
                    "status": "",
                    "channel_id": channel_id,
                    "thread_ts": thread_ts,
                },
            )
            if not response.get("ok"):
                error = response.get("error", "unknown_error")
                if error != "missing_scope":
                    logger.warning(f"Failed to clear thread status: {error}")
                return False
            logger.debug(f"Cleared thread status for channel {channel_id}, thread {thread_ts}")
            return True
        except Exception as e:
            logger.warning(f"Failed to clear thread status for channel {channel_id}: {e}")
            return False
