"""Celery task for executing followup reminders.

This task is triggered by scheduled tasks to send followup reminders
for pending followup items.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from src.celery_app import celery_app
from src.core.database import get_db
from src.models.followup import FollowupItem, FollowupStatus
from src.models.scheduled_task import ScheduledTask
from src.services.agents.internal_tools.followup_tools import internal_send_followup_message
from src.services.agents.runtime_context import RuntimeContext

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.execute_followup_reminder")
def execute_followup_reminder(
    task_id: str, tenant_id: str, agent_id: str, task_config: dict[str, Any]
) -> dict[str, Any]:
    """
    Execute a followup reminder task.

    This task:
    1. Retrieves the followup item
    2. Checks if it's still pending/in_progress
    3. Generates an appropriate followup message
    4. Sends the message via the followup tools
    5. Updates the scheduled task for next run

    Args:
        task_id: UUID of the scheduled task
        tenant_id: Tenant ID
        agent_id: Agent ID
        task_config: Task configuration containing followup_item_id

    Returns:
        Dictionary with execution result
    """
    try:
        followup_item_id = task_config.get("followup_item_id")
        if not followup_item_id:
            return {"success": False, "error": "Missing followup_item_id in task_config"}

        db = next(get_db())
        try:
            # Reload authoritative scope and references; queue payloads are not authority.
            task = (
                db.query(ScheduledTask)
                .filter(
                    ScheduledTask.id == uuid.UUID(task_id),
                    ScheduledTask.tenant_id == uuid.UUID(tenant_id),
                    ScheduledTask.task_type == "followup_reminder",
                    ScheduledTask.is_active.is_(True),
                )
                .first()
            )
            if task is None:
                return {"success": False, "error": "Scheduled task unavailable"}
            tenant_id = str(task.tenant_id)
            agent_id = str(uuid.UUID(str(task.config.get("agent_id", ""))))
            followup_item_id = str(uuid.UUID(str(task.config.get("followup_item_id", ""))))
            from src.models.agent import Agent

            agent = db.query(Agent).filter(Agent.id == uuid.UUID(agent_id), Agent.tenant_id == task.tenant_id).first()
            if agent is None:
                return {"success": False, "error": "Agent unavailable in this tenant"}

            # Get followup item
            followup_item = (
                db.query(FollowupItem)
                .filter(
                    FollowupItem.id == uuid.UUID(followup_item_id),
                    FollowupItem.agent_id == uuid.UUID(agent_id),
                    FollowupItem.tenant_id == task.tenant_id,
                )
                .first()
            )

            if not followup_item:
                logger.warning(f"Followup item {followup_item_id} not found")
                return {"success": False, "error": "Followup item not found", "should_disable_task": True}

            # Check if followup is still active
            if followup_item.status not in [FollowupStatus.PENDING.value, FollowupStatus.IN_PROGRESS.value]:
                logger.info(f"Followup item {followup_item_id} is {followup_item.status}, skipping reminder")

                # Disable the scheduled task
                scheduled_task = db.query(ScheduledTask).filter(ScheduledTask.id == uuid.UUID(task_id)).first()
                if scheduled_task:
                    scheduled_task.is_active = False
                    db.commit()

                return {
                    "success": True,
                    "message": f"Followup is {followup_item.status}, task disabled",
                    "should_disable_task": True,
                }

            # Check if we've reached max attempts
            if followup_item.current_attempt_count >= followup_item.max_followup_attempts:
                logger.info(f"Followup item {followup_item_id} has reached max attempts, escalating")

                # Mark as escalated
                followup_item.status = FollowupStatus.ESCALATED.value
                followup_item.escalated = True
                followup_item.escalated_at = datetime.now(UTC)
                followup_item.next_followup_at = None
                db.commit()

                # Disable the scheduled task
                scheduled_task = db.query(ScheduledTask).filter(ScheduledTask.id == uuid.UUID(task_id)).first()
                if scheduled_task:
                    scheduled_task.is_active = False
                    db.commit()

                return {
                    "success": True,
                    "message": "Max attempts reached, followup escalated",
                    "should_disable_task": True,
                }

            # Generate followup message
            attempt_num = followup_item.current_attempt_count + 1
            message = _generate_followup_message(followup_item, attempt_num)

            # Create runtime context with proper RuntimeContext object
            runtime_context = RuntimeContext(
                tenant_id=uuid.UUID(tenant_id), agent_id=uuid.UUID(agent_id), db_session=db
            )

            # Send followup message to channel thread using internal tools
            import asyncio

            result = asyncio.run(
                internal_send_followup_message(
                    followup_item_id=str(followup_item.id),
                    message=message,
                    message_channel="slack_channel",
                    ai_reasoning=f"Automated followup reminder (attempt {attempt_num})",
                    ai_tone="professional_friendly",
                    runtime_context=runtime_context,
                )
            )

            # Also send DMs to mentioned users if available
            if followup_item.mentioned_users and result.get("success"):
                from src.services.agents.internal_tools.slack_tools import internal_slack_send_dm

                dm_message = _generate_dm_message(followup_item, attempt_num)
                dm_results = []

                for user_id in followup_item.mentioned_users:
                    try:
                        dm_result = asyncio.run(
                            internal_slack_send_dm(user_id=user_id, text=dm_message, runtime_context=runtime_context)
                        )
                        dm_results.append({"user_id": user_id, "success": dm_result.get("success", False)})
                        logger.info(f"Sent DM to user {user_id}: {dm_result.get('success')}")
                    except Exception as e:
                        logger.error(f"Failed to send DM to user {user_id}: {e}")
                        dm_results.append({"user_id": user_id, "success": False, "error": str(e)})

                result["dm_results"] = dm_results
                logger.info(
                    f"Sent {len([r for r in dm_results if r.get('success')])} DMs out of {len(dm_results)} users"
                )

            if result.get("success"):
                # Update scheduled task for next run
                scheduled_task = db.query(ScheduledTask).filter(ScheduledTask.id == uuid.UUID(task_id)).first()

                if scheduled_task and followup_item.next_followup_at:
                    scheduled_task.next_run_at = followup_item.next_followup_at
                    scheduled_task.last_run_at = datetime.now(UTC)
                    db.commit()
                elif scheduled_task:
                    # No more followups scheduled
                    scheduled_task.is_active = False
                    db.commit()

                logger.info(f"✅ Followup reminder sent for {followup_item.id}")
                return {
                    "success": True,
                    "message": f"Followup reminder sent (attempt {attempt_num})",
                    "followup_item_id": str(followup_item.id),
                    "next_run_at": followup_item.next_followup_at.isoformat()
                    if followup_item.next_followup_at
                    else None,
                }
            else:
                logger.error(f"Failed to send followup reminder: {result.get('error')}")
                return {"success": False, "error": f"Failed to send message: {result.get('error')}"}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error executing followup reminder task: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _generate_followup_message(followup_item: FollowupItem, attempt_num: int) -> str:
    """
    Generate an appropriate followup message based on context.

    Args:
        followup_item: The followup item
        attempt_num: Current attempt number

    Returns:
        Formatted followup message
    """
    # Build message based on attempt number and context
    if attempt_num == 1:
        # First followup - gentle reminder
        message = f"👋 Hi! Just following up on: *{followup_item.title}*\n\n"
        if followup_item.description:
            message += f"{followup_item.description}\n\n"
        message += "Any updates you can share?"

    elif attempt_num == 2:
        # Second followup - more direct
        message = f"Hi again! I'm still waiting for an update on: *{followup_item.title}*\n\n"
        # Mention users using Slack format so names appear automatically
        if followup_item.mentioned_users:
            mentions = " ".join([f"<@{user_id}>" for user_id in followup_item.mentioned_users])
            message += f"cc: {mentions}\n\n"
        message += "Could you please provide a status update?"

    else:
        # Third+ followup - urgent
        message = f"⚠️ *Urgent:* Still need an update on: *{followup_item.title}*\n\n"
        # Mention users using Slack format so names appear automatically
        if followup_item.mentioned_users:
            mentions = " ".join([f"<@{user_id}>" for user_id in followup_item.mentioned_users])
            message += f"cc: {mentions}\n\n"
        message += f"This is followup attempt {attempt_num}. Please respond as soon as possible."

    # Add link to original message if available
    if followup_item.source_url:
        message += f"\n\n🔗 [View original message]({followup_item.source_url})"

    return message


def _generate_dm_message(followup_item: FollowupItem, attempt_num: int) -> str:
    """
    Generate a direct message for followup reminders.

    Args:
        followup_item: The followup item
        attempt_num: Current attempt number

    Returns:
        Formatted DM message
    """
    # Build DM message - more personal and direct
    if attempt_num == 1:
        message = "Hi! 👋\n\n"
        message += f"I'm following up on *{followup_item.title}*"
    elif attempt_num == 2:
        message = "Hi there,\n\n"
        message += f"This is a reminder about *{followup_item.title}*"
    else:
        message = "⚠️ Urgent reminder:\n\n"
        message += f"*{followup_item.title}*"

    if followup_item.description:
        message += f"\n\n{followup_item.description}"

    message += f"\n\nCould you please provide an update? This is followup #{attempt_num}."

    # Add link to original message if available
    if followup_item.source_url:
        message += f"\n\n🔗 [View original message]({followup_item.source_url})"

    return message


@celery_app.task(name="tasks.process_due_followups")
def process_due_followups() -> dict[str, Any]:
    """
    Process all followup items that are due for a reminder.

    This task runs periodically (e.g., every hour) to check for followup items
    that need reminders sent, even if the scheduled task system fails.

    Returns:
        Dictionary with processing results
    """
    try:
        db = next(get_db())
        try:
            # Find all followup items that are due
            now = datetime.now(UTC)
            due_followups = (
                db.query(FollowupItem)
                .filter(
                    FollowupItem.status.in_([FollowupStatus.PENDING.value, FollowupStatus.IN_PROGRESS.value]),
                    FollowupItem.next_followup_at <= now,
                    FollowupItem.next_followup_at.isnot(None),
                )
                .all()
            )

            logger.info(f"Found {len(due_followups)} followup items due for reminder")

            results = []
            for followup in due_followups:
                try:
                    # Find the scheduled task for this followup
                    scheduled_task = (
                        db.query(ScheduledTask)
                        .filter(
                            ScheduledTask.task_type == "followup_reminder",
                            ScheduledTask.tenant_id == followup.tenant_id,
                            ScheduledTask.config["followup_item_id"].as_string() == str(followup.id),
                            ScheduledTask.is_active,
                        )
                        .first()
                    )

                    if scheduled_task:
                        # Execute the reminder
                        result = execute_followup_reminder(
                            task_id=str(scheduled_task.id),
                            tenant_id=str(followup.tenant_id),
                            agent_id=str(followup.agent_id),
                            task_config=scheduled_task.config,
                        )
                        results.append({"followup_id": str(followup.id), "result": result})
                    else:
                        logger.warning(f"No active scheduled task found for followup {followup.id}")

                except Exception as e:
                    logger.error(f"Error processing followup {followup.id}: {e}", exc_info=True)
                    results.append({"followup_id": str(followup.id), "error": str(e)})

            return {"success": True, "processed": len(results), "results": results}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in process_due_followups: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
