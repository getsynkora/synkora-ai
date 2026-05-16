"""
Push Notification Tools Registry

Registers FCM push notification tools with the ADK tool registry.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_push_notification_tools(registry):
    """Register push notification tools with the ADK tool registry."""
    from src.services.agents.internal_tools.push_notification_tools import (
        internal_send_push_notification,
    )

    async def internal_send_push_notification_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_send_push_notification(
            title=kwargs.get("title", ""),
            body=kwargs.get("body", ""),
            user_id=kwargs.get("user_id"),
            topic=kwargs.get("topic"),
            conversation_id=kwargs.get("conversation_id"),
            data=kwargs.get("data"),
            runtime_context=runtime_context,
            config=config,
        )

    registry.register_tool(
        name="internal_send_push_notification",
        description=(
            "Send an FCM push notification to mobile users who have the app installed and have "
            "registered for push notifications. Use this to proactively notify users — for example "
            "when a scheduled task completes, an alert threshold is crossed, or a report is ready. "
            "Requires FCM server key to be configured in widget settings.\n\n"
            "Targeting modes (evaluated in order):\n"
            "1. topic    — send to an explicit FCM topic string you supply\n"
            "2. user_id  — send to a specific user who registered with that user_id\n"
            "3. (default) — broadcast to ALL subscribers of this widget"
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Notification title shown on the device (e.g. 'Newsletter Ready')",
                },
                "body": {
                    "type": "string",
                    "description": "Notification body text shown below the title (max ~200 chars recommended)",
                },
                "user_id": {
                    "type": "string",
                    "description": (
                        "Optional — send only to the device(s) registered for this specific user ID. "
                        "Must match the user_id supplied during push registration in the Flutter app."
                    ),
                },
                "topic": {
                    "type": "string",
                    "description": (
                        "Optional — send to an explicit FCM topic string. "
                        "Takes precedence over user_id. "
                        "Use synkora_w_{widgetId} for all-users or a custom topic."
                    ),
                },
                "conversation_id": {
                    "type": "string",
                    "description": "Optional — attach a conversation ID to the notification data payload for deep-linking.",
                },
                "data": {
                    "type": "object",
                    "description": 'Optional key/value pairs attached to the notification for deep-linking (e.g. {"type": "report", "url": "https://..."})',
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["title", "body"],
        },
        function=internal_send_push_notification_wrapper,
    )

    logger.info("Registered 1 push notification tool")
