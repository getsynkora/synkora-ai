"""
Celery tasks for notification operations (Slack, Teams, WhatsApp, etc.).
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from celery.exceptions import MaxRetriesExceededError

from src.celery_app import celery_app
from src.core.database import SessionLocal

logger = logging.getLogger(__name__)

# DLQ key for failed notifications
NOTIFICATION_DLQ_KEY = "notifications:failed"


def _store_failed_notification(
    notification_type: str,
    destination: str,
    tenant_id: str | None,
    message: str | None,
    error: str,
    task_id: str,
    extra_data: dict | None = None,
) -> None:
    """Store failed notification for monitoring and potential replay."""
    try:
        from src.config.redis import get_redis

        redis = get_redis()
        if not redis:
            logger.error(f"Redis unavailable, cannot store failed notification: {notification_type} to {destination}")
            return

        failed_data = {
            "notification_type": notification_type,
            "destination": destination,
            "tenant_id": tenant_id,
            "message_preview": message[:200] if message else None,
            "error": error[:500],
            "task_id": task_id,
            "failed_at": datetime.now(UTC).isoformat(),
        }
        if extra_data:
            failed_data["extra"] = extra_data

        redis.zadd(NOTIFICATION_DLQ_KEY, {json.dumps(failed_data): datetime.now(UTC).timestamp()})
        logger.warning(f"Stored failed {notification_type} notification to DLQ: {destination}")

    except Exception as e:
        logger.error(f"Error storing failed notification to DLQ: {e}")


@celery_app.task(name="send_slack_notification_task", bind=True, max_retries=3, default_retry_delay=60)
def send_slack_notification_task(
    self, channel_id: str, message: str, tenant_id: str, thread_ts: str | None = None, blocks: list[dict] | None = None
) -> dict[str, Any]:
    """
    Send a Slack notification message.

    Args:
        channel_id: Slack channel ID
        message: Message text
        tenant_id: Tenant UUID
        thread_ts: Optional thread timestamp for replies
        blocks: Optional Slack blocks for rich formatting

    Returns:
        dict: Sending results with message timestamp
    """
    db = SessionLocal()

    try:
        from src.services.slack.slack_service import SlackService

        logger.info(f"📤 Sending Slack notification to {channel_id}")

        slack_service = SlackService(db, tenant_id=uuid.UUID(tenant_id))

        result = slack_service.send_message(channel_id=channel_id, text=message, thread_ts=thread_ts, blocks=blocks)

        logger.info(f"✅ Slack notification sent to {channel_id}")

        return {"success": True, "channel_id": channel_id, **result}

    except Exception as exc:
        logger.error(f"❌ Error sending Slack notification: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
        except MaxRetriesExceededError:
            _store_failed_notification(
                notification_type="slack",
                destination=channel_id,
                tenant_id=tenant_id,
                message=message,
                error=str(exc),
                task_id=self.request.id,
            )
            raise

    finally:
        db.close()


@celery_app.task(name="send_teams_notification_task", bind=True, max_retries=3, default_retry_delay=60)
def send_teams_notification_task(
    self, conversation_id: str, message: str, tenant_id: str, activity_id: str | None = None
) -> dict[str, Any]:
    """
    Send a Microsoft Teams notification message.

    Args:
        conversation_id: Teams conversation ID
        message: Message text
        tenant_id: Tenant UUID
        activity_id: Optional activity ID for replies

    Returns:
        dict: Sending results
    """
    db = SessionLocal()

    try:
        from src.services.teams.teams_service import TeamsService

        logger.info(f"📤 Sending Teams notification to {conversation_id}")

        teams_service = TeamsService(db, tenant_id=uuid.UUID(tenant_id))

        result = teams_service.send_message(conversation_id=conversation_id, text=message, reply_to_id=activity_id)

        logger.info(f"✅ Teams notification sent to {conversation_id}")

        return {"success": True, "conversation_id": conversation_id, **result}

    except Exception as exc:
        logger.error(f"❌ Error sending Teams notification: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
        except MaxRetriesExceededError:
            _store_failed_notification(
                notification_type="teams",
                destination=conversation_id,
                tenant_id=tenant_id,
                message=message,
                error=str(exc),
                task_id=self.request.id,
            )
            raise

    finally:
        db.close()


@celery_app.task(name="send_whatsapp_notification_task", bind=True, max_retries=3, default_retry_delay=60)
def send_whatsapp_notification_task(self, phone_number: str, message: str, tenant_id: str) -> dict[str, Any]:
    """
    Send a WhatsApp notification message.

    Args:
        phone_number: Recipient phone number
        message: Message text
        tenant_id: Tenant UUID

    Returns:
        dict: Sending results
    """
    db = SessionLocal()

    try:
        from src.services.whatsapp.whatsapp_service import WhatsAppService

        logger.info(f"📤 Sending WhatsApp notification to {phone_number}")

        whatsapp_service = WhatsAppService(db, tenant_id=uuid.UUID(tenant_id))

        result = whatsapp_service.send_message(phone_number=phone_number, text=message)

        logger.info(f"✅ WhatsApp notification sent to {phone_number}")

        return {"success": True, "phone_number": phone_number, **result}

    except Exception as exc:
        logger.error(f"❌ Error sending WhatsApp notification: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
        except MaxRetriesExceededError:
            _store_failed_notification(
                notification_type="whatsapp",
                destination=phone_number,
                tenant_id=tenant_id,
                message=message,
                error=str(exc),
                task_id=self.request.id,
            )
            raise

    finally:
        db.close()


@celery_app.task(name="send_webhook_notification_task", bind=True, max_retries=3, default_retry_delay=60)
def send_webhook_notification_task(
    self, webhook_url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, method: str = "POST"
) -> dict[str, Any]:
    """
    Send a webhook notification to an external URL.

    Args:
        webhook_url: Webhook URL
        payload: JSON payload to send
        headers: Optional HTTP headers
        method: HTTP method (POST, PUT, etc.)

    Returns:
        dict: Webhook response
    """
    try:
        import requests

        logger.info(f"📤 Sending webhook to {webhook_url}")

        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)

        response = requests.request(method=method, url=webhook_url, json=payload, headers=default_headers, timeout=30)

        response.raise_for_status()

        logger.info(f"✅ Webhook sent successfully to {webhook_url}")

        return {
            "success": True,
            "status_code": response.status_code,
            "response": response.text[:500],  # Limit response size
        }

    except Exception as exc:
        logger.error(f"❌ Error sending webhook: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
        except MaxRetriesExceededError:
            _store_failed_notification(
                notification_type="webhook",
                destination=webhook_url,
                tenant_id=None,
                message=None,
                error=str(exc),
                task_id=self.request.id,
                extra_data={"method": method},
            )
            raise


@celery_app.task(name="send_in_app_notification_task")
def send_in_app_notification_task(
    account_id: str, title: str, message: str, notification_type: str = "info", action_url: str | None = None
) -> dict[str, Any]:
    """
    Create an in-app notification for a user.

    Args:
        account_id: Account UUID
        title: Notification title
        message: Notification message
        notification_type: Type (info, success, warning, error)
        action_url: Optional URL for notification action

    Returns:
        dict: Created notification details
    """
    db = SessionLocal()

    try:
        from src.models.notification import Notification

        logger.info(f"🔔 Creating in-app notification for account {account_id}")

        notification = Notification(
            account_id=uuid.UUID(account_id),
            title=title,
            message=message,
            type=notification_type,
            action_url=action_url,
            is_read=False,
        )

        db.add(notification)
        db.commit()
        db.refresh(notification)

        logger.info(f"✅ In-app notification created: {notification.id}")

        return {"success": True, "notification_id": str(notification.id), "account_id": account_id}

    except Exception as exc:
        logger.error(f"❌ Error creating in-app notification: {exc}", exc_info=True)
        db.rollback()
        return {"success": False, "error": str(exc)}

    finally:
        db.close()


@celery_app.task(name="send_bulk_notifications_task")
def send_bulk_notifications_task(
    account_ids: list[str], title: str, message: str, notification_type: str = "info"
) -> dict[str, Any]:
    """
    Send in-app notifications to multiple users.

    Args:
        account_ids: List of account UUIDs
        title: Notification title
        message: Notification message
        notification_type: Type (info, success, warning, error)

    Returns:
        dict: Bulk sending results
    """
    try:
        logger.info(f"📢 Sending bulk notifications to {len(account_ids)} users")

        results = {"total": len(account_ids), "sent": 0, "failed": 0}

        for account_id in account_ids:
            try:
                send_in_app_notification_task.delay(
                    account_id=account_id, title=title, message=message, notification_type=notification_type
                )
                results["sent"] += 1
            except Exception as e:
                logger.error(f"Failed to queue notification for {account_id}: {e}")
                results["failed"] += 1

        logger.info(f"✅ Queued {results['sent']} bulk notifications")

        return results

    except Exception as exc:
        logger.error(f"❌ Error in bulk notifications: {exc}", exc_info=True)
        return {"success": False, "error": str(exc)}


@celery_app.task(name="send_task_notification", bind=True, max_retries=3, default_retry_delay=60)
def send_task_notification(self, execution_id: int) -> dict[str, Any]:
    """
    Send notification about scheduled task execution

    Args:
        execution_id: ID of the task execution

    Returns:
        Dict containing notification results
    """
    db = SessionLocal()

    try:
        from src.models.scheduled_task import TaskExecution, TaskStatus

        logger.info(f"📬 Sending task notification for execution {execution_id}")

        # Get task execution
        execution = db.query(TaskExecution).filter(TaskExecution.id == execution_id).first()

        if not execution:
            raise ValueError(f"Task execution {execution_id} not found")

        task = execution.task

        if not task or not task.notifications:
            logger.info(f"No notifications configured for task execution {execution_id}")
            return {"success": True, "message": "No notifications configured"}

        # Build notification message
        if execution.status == TaskStatus.COMPLETED:
            status_emoji = "✅"
            status_text = "completed successfully"
        elif execution.status == TaskStatus.FAILED:
            status_emoji = "❌"
            status_text = "failed"
        else:
            status_emoji = "ℹ️"
            status_text = execution.status.value

        message = f"{status_emoji} Scheduled Task: {task.name}\n"
        message += f"Status: {status_text}\n"
        message += f"Execution ID: {execution.id}\n"

        if execution.started_at:
            message += f"Started: {execution.started_at.isoformat()}\n"
        if execution.completed_at:
            message += f"Completed: {execution.completed_at.isoformat()}\n"

        if execution.error_message:
            message += f"Error: {execution.error_message}\n"

        # Send notifications based on configuration
        notification_config = task.notifications
        results = []

        # Slack notifications
        if notification_config.get("slack"):
            for channel in notification_config["slack"].get("channels", []):
                result = send_slack_notification_task.delay(
                    channel_id=channel, message=message, tenant_id=str(task.tenant_id)
                )
                results.append({"type": "slack", "channel": channel, "task_id": result.id})

        # Teams notifications
        if notification_config.get("teams"):
            for conversation in notification_config["teams"].get("conversations", []):
                result = send_teams_notification_task.delay(
                    conversation_id=conversation, message=message, tenant_id=str(task.tenant_id)
                )
                results.append({"type": "teams", "conversation": conversation, "task_id": result.id})

        # Email notifications
        if notification_config.get("email"):
            from src.tasks.email_tasks import send_email_task

            for email in notification_config["email"].get("recipients", []):
                result = send_email_task.delay(
                    tenant_id=str(task.tenant_id),
                    to_email=email,
                    subject=f"Scheduled Task {status_text}: {task.name}",
                    text_body=message,
                )
                results.append({"type": "email", "recipient": email, "task_id": result.id})

        logger.info(f"✅ Task notification sent for execution {execution_id}: {len(results)} notifications queued")

        return {"success": True, "execution_id": execution_id, "notifications_sent": len(results), "results": results}

    except Exception as exc:
        logger.error(f"❌ Error sending task notification: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
        except MaxRetriesExceededError:
            _store_failed_notification(
                notification_type="task_notification",
                destination=str(execution_id),
                tenant_id=None,
                message=None,
                error=str(exc),
                task_id=self.request.id,
            )
            raise

    finally:
        db.close()


@celery_app.task(name="send_fcm_push_task", bind=True, max_retries=2, default_retry_delay=30)
def send_fcm_push_task(
    self,
    widget_id: str,
    conversation_id: str,
    agent_name: str,
    reply_preview: str,
) -> dict[str, Any]:
    """
    Send FCM push notification to all subscribed devices for a conversation.
    Silently skips if no FCM key is configured or no subscriptions exist.
    """
    import re
    import uuid as uuid_mod

    db = SessionLocal()
    try:
        from src.models.agent_widget import AgentWidget
        from src.models.widget_push_subscription import WidgetPushSubscription

        widget_uuid = uuid_mod.UUID(widget_id)
        conv_uuid = uuid_mod.UUID(conversation_id)

        widget = db.query(AgentWidget).filter(AgentWidget.id == widget_uuid).first()
        if not widget or not widget.fcm_server_key:
            return {"skipped": True, "reason": "no_fcm_key"}

        from src.services.agents.security import decrypt_value

        try:
            fcm_key = decrypt_value(widget.fcm_server_key)
        except Exception as e:
            logger.warning(f"FCM key decryption failed for widget {widget_id}: {e}")
            return {"skipped": True, "reason": "decrypt_error"}

        subs = (
            db.query(WidgetPushSubscription)
            .filter(
                WidgetPushSubscription.widget_id == widget_uuid,
                WidgetPushSubscription.conversation_id == conv_uuid,
            )
            .all()
        )

        if not subs:
            return {"skipped": True, "reason": "no_subscriptions"}

        clean_preview = re.sub(r"[#*_`\[\]()]", "", reply_preview).strip()[:100]

        import firebase_admin
        from firebase_admin import credentials, messaging

        app_name = f"widget_{widget_id}"
        try:
            app = firebase_admin.get_app(app_name)
        except ValueError:
            cred = credentials.Certificate(fcm_key if isinstance(fcm_key, dict) else {"private_key": fcm_key})
            app = firebase_admin.initialize_app(cred, name=app_name)

        tokens = [s.fcm_token for s in subs]
        notification = messaging.Notification(title=agent_name, body=clean_preview or "Your answer is ready.")
        data = {"widget_id": widget_id, "conversation_id": conversation_id, "type": "agent_reply"}

        batch = messaging.MulticastMessage(notification=notification, data=data, tokens=tokens)
        response = messaging.send_each_for_multicast(batch, app=app)

        logger.info(
            f"FCM push: {response.success_count} sent, {response.failure_count} failed for conv {conversation_id}"
        )
        return {"success_count": response.success_count, "failure_count": response.failure_count}

    except Exception as exc:
        logger.warning(f"FCM push task failed (non-critical): {exc}")
        try:
            raise self.retry(exc=exc)
        except Exception:
            return {"error": str(exc)}
    finally:
        db.close()
