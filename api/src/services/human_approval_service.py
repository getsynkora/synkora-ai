"""
Human-in-the-Loop approval service.

Manages the full lifecycle of an approval request:
  create_and_notify → user replies → handle_reply → resume execution
"""

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_approval import AgentApprovalRequest, ApprovalStatus

logger = logging.getLogger(__name__)


class HumanApprovalService:
    """Service for creating, routing, and resolving HITL approval requests."""

    AFFIRMATIVE: frozenset[str] = frozenset(
        {
            "yes",
            "yeah",
            "yep",
            "sure",
            "ok",
            "okay",
            "go ahead",
            "proceed",
            "approve",
            "approved",
            "do it",
            "post it",
            "send it",
            "looks good",
            "lgtm",
            "go for it",
            "confirm",
        }
    )
    NEGATIVE: frozenset[str] = frozenset(
        {
            "no",
            "nope",
            "nah",
            "cancel",
            "stop",
            "dont",
            "reject",
            "not now",
            "skip",
            "wait",
            "hold",
            "abort",
            "deny",
        }
    )

    def __init__(self, db: AsyncSession):
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_and_notify(
        self,
        *,
        task_id: UUID | None,
        agent_id: UUID,
        tenant_id: UUID,
        agent_name: str,
        tool_name: str,
        tool_args: dict,
        channel: str,
        channel_config: dict,
        timeout_minutes: int = 60,
        conversation_id: UUID | None = None,
    ) -> dict:
        """
        Persist an approval request and notify the user.

        Returns a dict with approval_required=True so execute_tool() can
        return it as a non-None result (blocking the tool from running).
        """
        from src.config.redis import get_redis_async

        args_hash = hashlib.sha256(json.dumps(tool_args, sort_keys=True).encode()).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(minutes=timeout_minutes)

        approval = AgentApprovalRequest(
            task_id=task_id,
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_name=agent_name,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_args_hash=args_hash,
            status=ApprovalStatus.PENDING,
            notification_channel=channel,
            notification_ref={},
            expires_at=expires_at,
        )
        self._db.add(approval)
        await self._db.commit()
        await self._db.refresh(approval)

        # Store Redis routing key so incoming channel replies can look up this approval
        redis = get_redis_async()
        redis_key = self._routing_key(channel, agent_id, channel_config)
        ttl_seconds = timeout_minutes * 60
        await redis.set(redis_key, str(approval.id), ex=ttl_seconds)

        # Send the notification on the chosen channel
        notification_ref: dict = {}
        try:
            if channel == "slack":
                notification_ref = await self._send_slack(approval, channel_config)
            elif channel == "whatsapp":
                await self._send_whatsapp_business(approval, channel_config)
            elif channel == "whatsapp_web":
                await self._send_whatsapp_web(approval, channel_config)
            elif channel == "chat":
                await self._send_chat(approval, channel_config)
            else:
                logger.warning(f"Unknown approval channel '{channel}' for approval {approval.id}")
        except Exception as exc:
            logger.error(f"Failed to send approval notification via {channel}: {exc}", exc_info=True)

        # Persist notification_ref (e.g. Slack message_ts for threading)
        if notification_ref:
            approval.notification_ref = notification_ref
            await self._db.commit()

        # Push a WebSocket event to the dashboard
        try:
            await self._push_ws_event(approval)
        except Exception:
            pass  # non-critical

        message = (
            f"Approval required before executing '{tool_name}'. "
            f"A notification has been sent via {channel}. "
            f"The action will be cancelled if not approved within {timeout_minutes} minutes."
        )
        return {
            "approval_required": True,
            "approval_id": str(approval.id),
            "message": message,
            "status": "awaiting_approval",
            "expires_at": approval.expires_at.isoformat(),
        }

    def parse_reply(self, text: str) -> Literal["approve", "reject", "unclear"]:
        """Classify a free-text reply as approve / reject / unclear."""
        words = set(text.lower().replace("'", "").split())
        if words & self.AFFIRMATIVE:
            return "approve"
        if words & self.NEGATIVE:
            return "reject"
        return "unclear"

    async def handle_reply(
        self,
        approval_id: UUID,
        reply_text: str,
        db: AsyncSession,
    ) -> Literal["approved", "rejected", "feedback", "unclear", "expired", "not_found"]:
        """
        Process a user reply for a pending approval.

        On approve:  marks APPROVED, stores Redis execution token, fires Celery task.
        On reject:   marks REJECTED.
        On feedback: marks REJECTED, fires a new run with feedback injected.
        Returns a string status for the caller to form a reply message.
        """
        result = await db.execute(select(AgentApprovalRequest).filter(AgentApprovalRequest.id == approval_id))
        approval = result.scalar_one_or_none()
        if not approval:
            return "not_found"

        # Check expiry
        if datetime.now(UTC) > approval.expires_at:
            if approval.status == ApprovalStatus.PENDING:
                approval.status = ApprovalStatus.EXPIRED
                await db.commit()
            return "expired"

        if approval.status != ApprovalStatus.PENDING:
            return approval.status.value  # already handled

        decision = self.parse_reply(reply_text)
        now = datetime.now(UTC)

        if decision == "approve":
            approval.status = ApprovalStatus.APPROVED
            approval.responded_at = now
            await db.commit()
            await self._store_execution_token(approval)
            await self._fire_approved_run(approval)
            await self._update_slack_message_if_applicable(approval)
            return "approved"

        if decision == "reject":
            approval.status = ApprovalStatus.REJECTED
            approval.responded_at = now
            await db.commit()
            await self._update_slack_message_if_applicable(approval)
            return "rejected"

        # unclear → treat as feedback if it has some substance
        if len(reply_text.strip()) > 5:
            approval.status = ApprovalStatus.REJECTED
            approval.responded_at = now
            await db.commit()
            await self._fire_feedback_run(approval, reply_text)
            await self._update_slack_message_if_applicable(approval)
            return "feedback"

        return "unclear"

    async def respond_to_approval(
        self,
        approval_id: UUID,
        decision: Literal["approved", "rejected", "feedback"],
        feedback_text: str | None,
        db: AsyncSession,
        responded_by: str | None = None,
    ) -> dict:
        """Handle a dashboard-originated or button-click respond action."""
        result = await db.execute(select(AgentApprovalRequest).filter(AgentApprovalRequest.id == approval_id))
        approval = result.scalar_one_or_none()
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")

        now = datetime.now(UTC)

        if datetime.now(UTC) > approval.expires_at:
            if approval.status == ApprovalStatus.PENDING:
                approval.status = ApprovalStatus.EXPIRED
                await db.commit()
            return {"status": "expired"}

        if approval.status != ApprovalStatus.PENDING:
            return {"status": approval.status.value, "already_handled": True, "responded_by": approval.responded_by}

        if decision == "approved":
            approval.status = ApprovalStatus.APPROVED
            approval.responded_at = now
            approval.responded_by = responded_by
            await db.commit()
            await self._store_execution_token(approval)
            await self._fire_approved_run(approval)
        elif decision == "rejected":
            approval.status = ApprovalStatus.REJECTED
            approval.responded_at = now
            approval.responded_by = responded_by
            await db.commit()
        elif decision == "feedback" and feedback_text:
            approval.status = ApprovalStatus.REJECTED
            approval.responded_at = now
            approval.responded_by = responded_by
            await db.commit()
            await self._fire_feedback_run(approval, feedback_text)

        await self._update_slack_message_if_applicable(approval)

        return {"status": approval.status.value, "approval_id": str(approval.id)}

    @staticmethod
    async def post_slack_ephemeral(response_url: str, text: str) -> None:
        """Send an ephemeral message back to a Slack interaction via its response_url."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(response_url, json={"text": text, "replace_original": False})
        except Exception as exc:
            logger.warning(f"Failed to post ephemeral response via response_url: {exc}")

    # ------------------------------------------------------------------
    # Redis helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _routing_key(channel: str, agent_id: UUID, channel_config: dict) -> str:
        """Build the Redis key used to route incoming replies to an approval."""
        if channel == "slack":
            chan_id = channel_config.get("channel_id", "")
            return f"hitl:slack:{agent_id}:{chan_id}"
        if channel == "whatsapp":
            bot_id = channel_config.get("bot_id", "")
            phone = channel_config.get("to_phone", "")
            return f"hitl:whatsapp:{bot_id}:{phone}"
        if channel == "whatsapp_web":
            session_id = channel_config.get("session_id", "")
            phone = channel_config.get("to_phone", "")
            return f"hitl:whatsapp_web:{session_id}:{phone}"
        if channel == "chat":
            conv_id = channel_config.get("conversation_id", "")
            return f"hitl:chat:{agent_id}:{conv_id}"
        return f"hitl:{channel}:{agent_id}"

    async def _store_execution_token(self, approval: AgentApprovalRequest) -> None:
        """Store a one-time Redis token so execute_tool() knows the action is pre-approved."""
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        if approval.task_id is None:
            # Chat session: key by conversation_id
            token_key = f"approval_token:chat:{approval.conversation_id}:{approval.tool_name}:{approval.tool_args_hash}"
        else:
            token_key = f"approval_token:{approval.task_id}:{approval.tool_name}:{approval.tool_args_hash}"
        await redis.set(token_key, "1", ex=600)  # 10 minute window to execute

    # ------------------------------------------------------------------
    # Task resumption
    # ------------------------------------------------------------------

    async def _fire_approved_run(self, approval: AgentApprovalRequest) -> None:
        """Enqueue a Celery task to re-run the agent with the approved action."""
        from src.tasks.scheduled_tasks import execute_scheduled_task

        execute_scheduled_task.delay(str(approval.task_id), approval_id=str(approval.id))

    async def _fire_feedback_run(self, approval: AgentApprovalRequest, feedback: str) -> None:
        """Enqueue a Celery task to re-run with user feedback injected."""
        from src.tasks.scheduled_tasks import execute_scheduled_task

        execute_scheduled_task.delay(
            str(approval.task_id),
            approval_id=None,
            feedback_text=feedback,
        )

    # ------------------------------------------------------------------
    # Channel senders
    # ------------------------------------------------------------------

    async def _send_slack(self, approval: AgentApprovalRequest, channel_config: dict) -> dict:
        """Send approval request to Slack."""
        from slack_sdk.web.async_client import AsyncWebClient
        from sqlalchemy import select as sa_select

        from src.models.slack_bot import SlackBot
        from src.services.agents.security import decrypt_value

        # Find the Slack bot linked to this agent
        result = await self._db.execute(sa_select(SlackBot).filter(SlackBot.agent_id == approval.agent_id))
        bot = result.scalar_one_or_none()
        if not bot:
            logger.warning(f"No Slack bot found for agent {approval.agent_id}")
            return {}

        try:
            token = decrypt_value(bot.slack_bot_token)
        except Exception:
            token = bot.slack_bot_token

        client = AsyncWebClient(token=token)
        channel_id = channel_config.get("channel_id") or ""
        if not channel_id:
            logger.warning(f"No channel_id in approval channel_config for Slack bot {bot.id}")
            return {}

        # Build a concise summary of the action
        args_preview = json.dumps(approval.tool_args, ensure_ascii=False)
        if len(args_preview) > 300:
            args_preview = args_preview[:297] + "..."

        text = (
            f"*Action pending your approval*\n"
            f"Agent *{approval.agent_name}* wants to call `{approval.tool_name}`:\n"
            f"```{args_preview}```"
        )
        blocks = self._build_approval_blocks(approval, text)

        resp = await client.chat_postMessage(channel=channel_id, text=text, blocks=blocks)
        message_ts = resp.get("ts", "")
        return {"slack_bot_id": str(bot.id), "channel_id": channel_id, "message_ts": message_ts}

    @staticmethod
    def _build_approval_blocks(approval: AgentApprovalRequest, text: str) -> list[dict]:
        """Build the Block Kit blocks for a pending approval message (summary + buttons)."""
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {
                "type": "actions",
                "block_id": "hitl_approval_actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "hitl_approve",
                        "style": "primary",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "value": str(approval.id),
                    },
                    {
                        "type": "button",
                        "action_id": "hitl_reject",
                        "style": "danger",
                        "text": {"type": "plain_text", "text": "Reject"},
                        "value": str(approval.id),
                    },
                ],
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "Or reply in this thread to give feedback instead."},
                ],
            },
        ]

    async def _update_slack_message_if_applicable(self, approval: AgentApprovalRequest) -> None:
        """Best-effort: edit the original Slack message to reflect the final decision."""
        if approval.notification_channel != "slack":
            return
        if approval.status not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
            return
        try:
            await self._update_slack_message(approval)
        except Exception as exc:
            logger.warning(f"Failed to update Slack message for approval {approval.id}: {exc}")

    async def _update_slack_message(self, approval: AgentApprovalRequest) -> None:
        """Edit the original Slack approval message to show the outcome and remove the buttons."""
        from slack_sdk.web.async_client import AsyncWebClient

        from src.models.slack_bot import SlackBot
        from src.services.agents.security import decrypt_value

        ref = approval.notification_ref or {}
        bot_id = ref.get("slack_bot_id")
        channel_id = ref.get("channel_id")
        message_ts = ref.get("message_ts")
        if not bot_id or not channel_id or not message_ts:
            return

        bot = await self._db.get(SlackBot, bot_id)
        if not bot:
            return

        try:
            token = decrypt_value(bot.slack_bot_token)
        except Exception:
            token = bot.slack_bot_token

        client = AsyncWebClient(token=token)

        args_preview = json.dumps(approval.tool_args, ensure_ascii=False)
        if len(args_preview) > 300:
            args_preview = args_preview[:297] + "..."

        summary_text = f"Agent *{approval.agent_name}* wanted to call `{approval.tool_name}`:\n```{args_preview}```"
        if approval.status == ApprovalStatus.APPROVED:
            outcome_text = f"✅ Approved by <@{approval.responded_by}>" if approval.responded_by else "✅ Approved"
        else:
            outcome_text = f"❌ Rejected by <@{approval.responded_by}>" if approval.responded_by else "❌ Rejected"

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": summary_text}},
            {"type": "section", "text": {"type": "mrkdwn", "text": outcome_text}},
        ]
        await client.chat_update(channel=channel_id, ts=message_ts, text=outcome_text, blocks=blocks)

    async def _send_whatsapp_business(self, approval: AgentApprovalRequest, channel_config: dict) -> None:
        """Send approval request via WhatsApp Business API."""
        from src.models.whatsapp_bot import WhatsAppBot
        from src.services.agents.security import decrypt_value

        bot_id = channel_config.get("bot_id")
        to_phone = channel_config.get("to_phone")
        if not bot_id or not to_phone:
            logger.warning("WhatsApp approval missing bot_id or to_phone in channel_config")
            return

        bot = await self._db.get(WhatsAppBot, bot_id)
        if not bot:
            logger.warning(f"WhatsApp bot {bot_id} not found")
            return

        try:
            access_token = decrypt_value(bot.access_token)
        except Exception:
            access_token = bot.access_token

        args_preview = json.dumps(approval.tool_args, ensure_ascii=False)
        if len(args_preview) > 200:
            args_preview = args_preview[:197] + "..."

        message = (
            f"Action pending your approval.\n"
            f"Agent *{approval.agent_name}* wants to call `{approval.tool_name}`:\n"
            f"{args_preview}\n\n"
            f"Reply YES to proceed or NO to cancel."
        )

        import httpx

        url = f"https://graph.facebook.com/v21.0/{bot.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "text",
            "text": {"body": message},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(url, json=payload, headers={"Authorization": f"Bearer {access_token}"})

    async def _send_whatsapp_web(self, approval: AgentApprovalRequest, channel_config: dict) -> None:
        """Send approval request via device-linked WhatsApp (neonize)."""
        from src.services.whatsapp.whatsapp_web_service import WhatsAppWebService

        session_id = channel_config.get("session_id")
        to_phone = channel_config.get("to_phone")
        if not session_id or not to_phone:
            logger.warning("WhatsApp Web approval missing session_id or to_phone")
            return

        args_preview = json.dumps(approval.tool_args, ensure_ascii=False)
        if len(args_preview) > 200:
            args_preview = args_preview[:197] + "..."

        message = (
            f"Action pending your approval.\n"
            f"Agent {approval.agent_name} wants to call {approval.tool_name}:\n"
            f"{args_preview}\n\n"
            f"Reply YES to proceed or NO to cancel."
        )

        svc = WhatsAppWebService()
        svc.send_text_message(session_id, to_phone, message)

    async def _send_chat(self, approval: AgentApprovalRequest, channel_config: dict) -> None:
        """Persist an approval prompt into the agent's autonomous memory conversation."""
        import uuid as uuid_module

        from src.models.message import Message, MessageRole

        conv_id_str = channel_config.get("conversation_id")
        if not conv_id_str:
            logger.warning("Chat approval missing conversation_id in channel_config")
            return

        args_preview = json.dumps(approval.tool_args, ensure_ascii=False)
        if len(args_preview) > 300:
            args_preview = args_preview[:297] + "..."

        content = (
            f"I'm about to call `{approval.tool_name}`:\n"
            f"```{args_preview}```\n"
            f"Should I proceed? Reply *yes*, *no*, or describe changes you want."
        )

        msg = Message(
            id=uuid_module.uuid4(),
            conversation_id=uuid_module.UUID(conv_id_str),
            role=MessageRole.ASSISTANT,
            content=content,
            message_metadata={"approval_id": str(approval.id), "source": "hitl"},
        )
        self._db.add(msg)
        await self._db.commit()

    async def _push_ws_event(self, approval: AgentApprovalRequest) -> None:
        """Push a WebSocket notification to the dashboard (best-effort)."""
        from src.core.websocket import connection_manager

        message = {
            "type": "pending_approval",
            "data": {
                "approval_id": str(approval.id),
                "agent_name": approval.agent_name,
                "tool_name": approval.tool_name,
                "channel": approval.notification_channel,
            },
        }
        # Broadcast to all connected users (tenant filtering is not yet in the base manager;
        # the frontend will ignore events for other agents).
        await connection_manager.broadcast(message)
