"""Process webhook events and trigger agent executions."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_webhook import AgentWebhook, AgentWebhookEvent
from src.services.webhooks import jev_gate
from src.services.webhooks.provider_parsers import ProviderParser
from src.services.webhooks.signature_verifier import SignatureVerifier

logger = logging.getLogger(__name__)

# GitHub pull_request actions that are NOT worth reviewing.
# We only care about: opened, synchronize (new commits), reopened.
GITHUB_PR_IGNORED_ACTIONS = {
    "closed",
    "assigned",
    "unassigned",
    "labeled",
    "unlabeled",
    "review_requested",
    "review_request_removed",
    "ready_for_review",
    "converted_to_draft",
    "auto_merge_enabled",
    "auto_merge_disabled",
    "locked",
    "unlocked",
    "milestoned",
    "demilestoned",
}

# Window (seconds) in which a duplicate review for the same PR is suppressed
PR_DEDUP_WINDOW_SECONDS = 300  # 5 minutes


class WebhookProcessor:
    """Process webhook events and trigger agent executions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def verify_signature(self, webhook: AgentWebhook, payload: bytes, headers: dict[str, str]) -> bool:
        """Verify webhook signature."""
        # SECURITY: Always require a secret for signature verification
        if not webhook.secret:
            logger.warning(f"Webhook {webhook.id} has no secret configured - rejecting request")
            return False

        from src.services.agents.security import decrypt_value

        try:
            decrypted_secret = decrypt_value(webhook.secret)
            # SECURITY: Never log secrets, even partially
        except Exception:
            logger.error(f"Failed to decrypt webhook secret for webhook {webhook.id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to decrypt webhook secret"
            )

        # SECURITY: Don't log headers or payload contents - they may contain sensitive data

        result = SignatureVerifier.verify(
            provider=webhook.provider,
            payload=payload,
            headers=headers,
            secret=decrypted_secret,
            config=webhook.config or {},
        )

        if not result:
            logger.warning(f"Signature verification failed for webhook {webhook.id}")
        return result

    def should_process_event(self, webhook: AgentWebhook, parsed_data: dict[str, Any]) -> bool:
        """Check if event should be processed based on configuration."""
        if not webhook.is_active:
            logger.info(f"Webhook {webhook.id} is inactive")
            return False

        event_type = parsed_data.get("event_type", "")

        # Filter out non-actionable GitHub pull_request actions.
        # e.g. pull_request.closed, pull_request.assigned, pull_request.review_requested
        if "." in event_type:
            category, action = event_type.split(".", 1)
            if category == "pull_request" and action in GITHUB_PR_IGNORED_ACTIONS:
                logger.info(f"Ignoring non-actionable pull_request action: {event_type}")
                return False

        # Filter by event types if configured on the webhook
        if webhook.event_types:
            # For GitHub events like "pull_request.opened", check both:
            # 1. Exact match: "pull_request.opened" in event_types
            # 2. Category match: "pull_request" in event_types (for "pull_request.opened")
            event_category = event_type.split(".")[0] if "." in event_type else event_type

            if event_type not in webhook.event_types and event_category not in webhook.event_types:
                logger.info(
                    f"Event type {event_type} (category: {event_category}) filtered out. Allowed: {webhook.event_types}"
                )
                return False

        return True

    async def is_duplicate_pr_event(self, webhook: AgentWebhook, parsed_data: dict[str, Any]) -> bool:
        """
        Check if there is already a pending/processing event for the same PR.

        Prevents the agent from being triggered multiple times for the same PR
        within the dedup window (e.g., when several synchronize events arrive
        in quick succession or when opened + synchronize both fire at once).
        """
        event_type = parsed_data.get("event_type", "")
        if not event_type.startswith("pull_request."):
            return False

        pr_number = parsed_data.get("data", {}).get("pr_number") or parsed_data.get("data", {}).get("number")
        if not pr_number:
            return False

        since = datetime.now(UTC) - timedelta(seconds=PR_DEDUP_WINDOW_SECONDS)

        result = await self.db.execute(
            select(AgentWebhookEvent).where(
                and_(
                    AgentWebhookEvent.webhook_id == webhook.id,
                    AgentWebhookEvent.status.in_(["pending", "processing", "completed"]),
                    AgentWebhookEvent.created_at >= since,
                )
            )
        )
        existing = result.scalars().all()

        for ev in existing:
            ev_pr = (ev.parsed_data or {}).get("data", {}).get("pr_number") or (ev.parsed_data or {}).get(
                "data", {}
            ).get("number")
            if ev_pr and str(ev_pr) == str(pr_number):
                logger.info(
                    f"Dedup: PR #{pr_number} already has a {ev.status} event ({ev.id}) within "
                    f"{PR_DEDUP_WINDOW_SECONDS}s window — skipping duplicate {event_type}"
                )
                return True

        return False

    async def create_webhook_event(
        self,
        webhook: AgentWebhook,
        payload: dict[str, Any],
        parsed_data: dict[str, Any],
        event_id: str | None = None,
        status: str = "pending",
    ) -> AgentWebhookEvent:
        """Create webhook event record."""
        now = datetime.now(UTC)
        event = AgentWebhookEvent(
            webhook_id=webhook.id,
            event_id=event_id,
            event_type=parsed_data.get("event_type", "unknown"),
            status=status,
            payload=payload,
            parsed_data=parsed_data,
            processing_started_at=now,
            # A skipped event is finished the moment it is recorded.
            processing_completed_at=now if status == "skipped" else None,
        )

        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)

        return event

    async def evaluate_jev_gate(
        self, webhook: AgentWebhook, parsed_data: dict[str, Any]
    ) -> jev_gate.JevGateDecision | None:
        """
        Score the event with the Jev gate when it is enabled on this webhook.

        Returns None when the gate is off. Never raises: any failure is a "run" decision
        carrying the reason, so the event is processed exactly as it would be without the gate.
        """
        cfg = jev_gate.JevGateConfig.from_webhook_config(webhook.config)
        if cfg is None:
            return None

        try:
            from src.models.agent import Agent
            from src.services.agents.context_relevance_pruner import resolve_typesafe_client_for_pruning

            result = await self.db.execute(select(Agent).where(Agent.id == webhook.agent_id))
            agent = result.scalar_one_or_none()
            if agent is None:
                return jev_gate.JevGateDecision(action="run", mode=cfg.mode, reason="agent_not_found")

            client = await resolve_typesafe_client_for_pruning(agent.tenant_id, self.db)
            decision = await jev_gate.evaluate_event(
                cfg=cfg,
                client=client,
                agent_name=agent.agent_name,
                description=agent.description,
                provider=webhook.provider,
                parsed_data=parsed_data,
            )
        except Exception as exc:
            logger.warning(f"Jev gate failed for webhook {webhook.id}: {exc}", exc_info=True)
            return jev_gate.JevGateDecision(action="run", mode=cfg.mode, reason="error")

        logger.info(
            f"Jev gate webhook={webhook.id} event_type={parsed_data.get('event_type')} "
            f"action={decision.action} mode={decision.mode} actionable={decision.actionable} "
            f"reason={decision.reason} latency_ms={decision.latency_ms}"
        )
        return decision

    async def trigger_agent_execution(
        self, webhook: AgentWebhook, event: AgentWebhookEvent, parsed_data: dict[str, Any]
    ) -> str | None:
        """
        Trigger agent execution with parsed webhook data.
        Uses Celery task for async processing.
        """
        try:
            from src.tasks.agent_tasks import process_webhook_event

            # Queue async task for agent execution
            task = process_webhook_event.delay(
                webhook_id=str(webhook.id), event_id=str(event.id), parsed_data=parsed_data
            )

            logger.info(f"Queued webhook processing task {task.id} for event {event.id}")

            return task.id

        except Exception as e:
            logger.error(f"Failed to trigger agent: {e}", exc_info=True)
            raise

    async def _record_failed_event(
        self, webhook: AgentWebhook, payload_dict: dict[str, Any], error_message: str
    ) -> None:
        """Create a failed event record so failures are visible in the UI history."""
        try:
            event = AgentWebhookEvent(
                webhook_id=webhook.id,
                event_type="unknown",
                status="failed",
                payload=payload_dict,
                parsed_data={},
                error_message=error_message,
                processing_started_at=datetime.now(UTC),
                processing_completed_at=datetime.now(UTC),
            )
            self.db.add(event)
            await self.db.commit()
        except Exception:
            logger.warning(f"Failed to record failed event for webhook {webhook.id}", exc_info=True)

    async def process_webhook(
        self, webhook: AgentWebhook, payload: bytes, payload_dict: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        """Process incoming webhook."""
        try:
            # Verify signature — only if the webhook has a secret AND verify_signature is enabled.
            # verify_signature defaults to True for providers that always sign (GitHub, Slack etc.)
            # and False for providers that don't (Sentry, custom) unless the user enables it.
            verify_signature = (webhook.config or {}).get("verify_signature", True)
            if webhook.secret and verify_signature:
                if not self.verify_signature(webhook, payload, headers):
                    webhook.failure_count += 1
                    await self.db.commit()
                    await self._record_failed_event(webhook, payload_dict, "Invalid signature")
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

            # Parse payload
            # For GitHub, pass the X-GitHub-Event header
            parse_config = webhook.config or {}
            if webhook.provider == "github":
                github_event = headers.get("x-github-event", "")
                parsed_data = ProviderParser.parse_github(payload_dict, github_event)
            else:
                parsed_data = ProviderParser.parse(provider=webhook.provider, payload=payload_dict, config=parse_config)

            # Filter events
            if not self.should_process_event(webhook, parsed_data):
                return {"status": "skipped", "message": "Event filtered"}

            # Dedup: skip if the same PR already has a recent pending/processing event
            if await self.is_duplicate_pr_event(webhook, parsed_data):
                return {"status": "skipped", "message": "Duplicate PR event suppressed"}

            # Get event ID from headers
            event_id = None
            if webhook.provider == "github":
                event_id = headers.get("x-github-delivery")
            elif webhook.provider == "slack":
                event_id = payload_dict.get("event_id")
            elif webhook.provider == "sentry":
                event_id = headers.get("sentry-hook-id")

            # SECURITY: Replay protection — reject if this delivery ID was already processed
            if event_id:
                existing = await self.db.execute(
                    select(AgentWebhookEvent).where(
                        and_(
                            AgentWebhookEvent.webhook_id == webhook.id,
                            AgentWebhookEvent.event_id == event_id,
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    logger.warning(f"Replay detected: event_id {event_id} already processed for webhook {webhook.id}")
                    return {"status": "skipped", "message": "Duplicate delivery ID — replay rejected"}

            # Jev gate: after every cheap check, before we pay for an agent run.
            gate = await self.evaluate_jev_gate(webhook, parsed_data)
            # The gate verdict is stored on the event for auditing; the agent still receives
            # the original parsed_data unchanged.
            stored_data = {**parsed_data, "jev_gate": gate.to_dict()} if gate else parsed_data

            if gate is not None and gate.action == "skip":
                event = await self.create_webhook_event(
                    webhook=webhook,
                    payload=payload_dict,
                    parsed_data=stored_data,
                    event_id=event_id,
                    status="skipped",
                )
                return {
                    "status": "skipped",
                    "message": "Skipped by Jev gate",
                    "event_id": event.id,
                    "actionable": gate.actionable,
                }

            # Create event record
            event = await self.create_webhook_event(
                webhook=webhook, payload=payload_dict, parsed_data=stored_data, event_id=event_id
            )

            # Trigger agent — event stays "pending" until the Celery task picks it up
            execution_id = await self.trigger_agent_execution(webhook=webhook, event=event, parsed_data=parsed_data)

            webhook.success_count += 1
            webhook.last_triggered_at = datetime.now(UTC)

            await self.db.commit()

            return {"status": "success", "event_id": event.id, "execution_id": execution_id}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            webhook.failure_count += 1
            await self.db.commit()
            await self._record_failed_event(webhook, payload_dict, str(e))

            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
