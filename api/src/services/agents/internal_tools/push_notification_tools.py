"""
Push Notification Tools for AI Agents.

Allows agents to proactively send FCM push notifications to mobile users
who have registered via the synkora_push Flutter package.

Sending modes (mutually exclusive, evaluated in order):
1. topic      — send to an explicit FCM topic string
2. user_id    — send to a specific app user via synkora_w_{wid}_u_{uid} topic
3. (default)  — broadcast to all widget subscribers via synkora_w_{wid} topic
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _safe_topic_segment(value: str, max_len: int = 100) -> str:
    """Sanitize a value for use inside an FCM topic name."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)[:max_len]


async def internal_send_push_notification(
    title: str,
    body: str,
    user_id: str | None = None,
    topic: str | None = None,
    conversation_id: str | None = None,
    data: dict[str, str] | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Send an FCM push notification.

    Sending modes (evaluated in order):
    - topic     — send directly to a caller-supplied FCM topic string
    - user_id   — send to synkora_w_{widget_id}_u_{user_id} (per-user)
    - (default) — send to synkora_w_{widget_id} (all widget subscribers)

    The topic approach sends a single FCM message regardless of subscriber
    count, so it scales to any number of devices without a token multicast.
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        if isinstance(runtime_context, dict):
            widget_id = runtime_context.get("widget_id")
            _tenant_id = runtime_context.get("tenant_id")
            db = runtime_context.get("db_session")
        else:
            widget_id = getattr(runtime_context, "widget_id", None)
            _tenant_id = getattr(runtime_context, "tenant_id", None)
            db = getattr(runtime_context, "db_session", None)

        if not widget_id:
            return {
                "success": False,
                "error": "widget_id not available in runtime context — agent must be called via a widget",
            }
        if not db:
            return {"success": False, "error": "db_session not available in runtime context"}

        if not title or not body:
            return {"success": False, "error": "title and body are required"}

        from uuid import UUID

        from sqlalchemy import select

        from src.models.agent_widget import AgentWidget
        from src.utils.encryption import decrypt_value

        # Load widget and FCM server key
        widget_result = await db.execute(select(AgentWidget).where(AgentWidget.id == UUID(str(widget_id))))
        widget = widget_result.scalar_one_or_none()
        if not widget:
            return {"success": False, "error": "Widget not found"}

        if not widget.fcm_server_key:
            return {
                "success": False,
                "error": "FCM server key not configured on this widget. Add it in widget settings → Mobile & Push Notifications.",
            }

        try:
            fcm_key = decrypt_value(widget.fcm_server_key)
        except Exception:
            fcm_key = widget.fcm_server_key  # plain text fallback (legacy)

        import firebase_admin
        from firebase_admin import credentials, messaging

        app_name = f"synkora_{abs(hash(fcm_key))}"
        try:
            app = firebase_admin.get_app(app_name)
        except ValueError:
            cred = credentials.Certificate(fcm_key)
            app = firebase_admin.initialize_app(cred, name=app_name)

        # Build extra data payload
        extra_data: dict[str, str] = {
            "widget_id": str(widget_id),
            "type": "agent_push",
        }
        if conversation_id:
            extra_data["conversation_id"] = conversation_id
        if data:
            extra_data.update({k: str(v) for k, v in data.items()})

        # Determine target topic
        widget_topic_id = str(widget_id).replace("-", "")

        if topic:
            # Caller supplied an explicit topic — use it directly
            target_topic = topic
        elif user_id:
            # Per-user topic
            safe_uid = _safe_topic_segment(user_id)
            target_topic = f"synkora_w_{widget_topic_id}_u_{safe_uid}"
        else:
            # Broadcast to all widget subscribers
            target_topic = f"synkora_w_{widget_topic_id}"

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=extra_data,
            topic=target_topic,
        )
        import asyncio

        await asyncio.to_thread(messaging.send, message, app=app)

        logger.info(f"Push notification sent to topic '{target_topic}' — widget={widget_id}")
        return {"success": True, "topic": target_topic}

    except Exception as e:
        logger.warning(f"Push notification failed: {e}")
        return {"success": False, "error": str(e)}
