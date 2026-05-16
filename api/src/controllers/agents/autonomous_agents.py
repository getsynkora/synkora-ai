"""
Autonomous Agent API endpoints.

Mounts at /api/v1/agents/{agent_slug}/autonomous and provides CRUD for
autonomous schedules, immediate trigger, and memory management.
"""

import logging
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.conversation import Conversation
from src.models.message import Message
from src.models.scheduled_task import ScheduledTask, TaskExecution
from src.schemas.autonomous_agent import (
    ApprovalRequestSchema,
    ApprovalRespondBody,
    AutonomousConfigCreate,
    AutonomousConfigUpdate,
    AutonomousMemoryMessageSchema,
    AutonomousRunSchema,
    AutonomousStatusSchema,
    parse_schedule,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_RUNS = 20
_MAX_MEMORY_MESSAGES = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_agent(agent_slug: str, tenant_id: UUID, db: AsyncSession) -> Agent:
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


async def _get_task(agent_id: UUID, tenant_id: UUID, db: AsyncSession) -> ScheduledTask | None:
    result = await db.execute(
        select(ScheduledTask).filter(
            ScheduledTask.config["agent_id"].as_string() == str(agent_id),
            ScheduledTask.task_type == "autonomous_agent",
            ScheduledTask.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


def _task_to_status(task: ScheduledTask | None, agent: Agent, runs: list) -> AutonomousStatusSchema:
    if task is None:
        return AutonomousStatusSchema(enabled=agent.autonomous_enabled)

    cfg = task.config or {}
    # Derive human-friendly schedule string for display
    if task.cron_expression:
        schedule_display = task.cron_expression
    elif task.interval_seconds:
        inv_map = {300: "5min", 900: "15min", 1800: "30min", 3600: "hourly"}
        schedule_display = inv_map.get(task.interval_seconds, f"{task.interval_seconds}s")
    else:
        schedule_display = None

    return AutonomousStatusSchema(
        enabled=agent.autonomous_enabled,
        task_id=task.id,
        goal=cfg.get("goal"),
        schedule=schedule_display,
        schedule_type=task.schedule_type,
        max_steps=cfg.get("max_steps", 20),
        is_active=task.is_active,
        last_run_at=task.last_run_at,
        next_run_at=task.next_run_at,
        recent_runs=runs,
        require_approval=cfg.get("require_approval", False),
        approval_mode=cfg.get("approval_mode", "smart"),
        require_approval_tools=cfg.get("require_approval_tools", []),
        approval_channel=cfg.get("approval_channel"),
        approval_channel_config=cfg.get("approval_channel_config", {}),
        approval_timeout_minutes=cfg.get("approval_timeout_minutes", 60),
    )


def _execution_to_schema(ex: TaskExecution) -> AutonomousRunSchema:
    preview = None
    if ex.result and isinstance(ex.result, dict):
        raw = ex.result.get("response_preview") or ex.result.get("output", "")
        if raw:
            preview = str(raw)[:300]
    return AutonomousRunSchema(
        id=ex.id,
        status=ex.status,
        started_at=ex.started_at,
        completed_at=ex.completed_at,
        execution_time_seconds=ex.execution_time_seconds,
        error_message=ex.error_message,
        output_preview=preview,
    )


# ---------------------------------------------------------------------------
# GET /agents/{agent_slug}/autonomous
# ---------------------------------------------------------------------------


@router.get("/{agent_slug}/autonomous", response_model=AutonomousStatusSchema)
async def get_autonomous_config(
    agent_slug: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return autonomous schedule config and last 20 run records."""
    agent = await _get_agent(agent_slug, tenant_id, db)
    task = await _get_task(agent.id, tenant_id, db)

    runs: list[AutonomousRunSchema] = []
    if task:
        result = await db.execute(
            select(TaskExecution)
            .filter(TaskExecution.task_id == task.id)
            .order_by(TaskExecution.started_at.desc())
            .limit(_MAX_RUNS)
        )
        runs = [_execution_to_schema(ex) for ex in result.scalars().all()]

    return _task_to_status(task, agent, runs)


# ---------------------------------------------------------------------------
# POST /agents/{agent_slug}/autonomous  — enable / create
# ---------------------------------------------------------------------------


@router.post("/{agent_slug}/autonomous", response_model=AutonomousStatusSchema, status_code=status.HTTP_201_CREATED)
async def create_autonomous_config(
    agent_slug: str,
    body: AutonomousConfigCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """Enable autonomous mode for an agent."""
    agent = await _get_agent(agent_slug, tenant_id, db)

    # Idempotency: if a task already exists, raise conflict
    existing = await _get_task(agent.id, tenant_id, db)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Autonomous config already exists. Use PATCH to update.",
        )

    sched = parse_schedule(body.schedule)

    task = ScheduledTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=f"[Autonomous] {agent.agent_name}",
        description=body.goal[:255],
        task_type="autonomous_agent",
        schedule_type=sched["schedule_type"],
        cron_expression=sched.get("cron_expression"),
        interval_seconds=sched.get("interval_seconds"),
        is_active=True,
        created_by=account.id,
        config={
            "agent_id": str(agent.id),
            "goal": body.goal,
            "max_steps": body.max_steps,
            "autonomous_conversation_id": None,
            # HITL approval settings
            "require_approval": body.require_approval,
            "approval_mode": body.approval_mode,
            "require_approval_tools": body.require_approval_tools,
            "approval_channel": body.approval_channel,
            "approval_channel_config": body.approval_channel_config,
            "approval_timeout_minutes": body.approval_timeout_minutes,
        },
    )
    db.add(task)

    agent.autonomous_enabled = True
    await db.commit()
    await db.refresh(task)
    await db.refresh(agent)

    return _task_to_status(task, agent, [])


# ---------------------------------------------------------------------------
# PATCH /agents/{agent_slug}/autonomous
# ---------------------------------------------------------------------------


@router.patch("/{agent_slug}/autonomous", response_model=AutonomousStatusSchema)
async def update_autonomous_config(
    agent_slug: str,
    body: AutonomousConfigUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update goal, schedule, max_steps, or active state."""
    agent = await _get_agent(agent_slug, tenant_id, db)
    task = await _get_task(agent.id, tenant_id, db)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Autonomous config not found")

    cfg = dict(task.config)
    if body.goal is not None:
        cfg["goal"] = body.goal
        task.description = body.goal[:255]

    if body.max_steps is not None:
        cfg["max_steps"] = body.max_steps

    # HITL approval settings
    if body.require_approval is not None:
        cfg["require_approval"] = body.require_approval
    if body.approval_mode is not None:
        cfg["approval_mode"] = body.approval_mode
    if body.require_approval_tools is not None:
        cfg["require_approval_tools"] = body.require_approval_tools
    if body.approval_channel is not None:
        cfg["approval_channel"] = body.approval_channel
    if body.approval_channel_config is not None:
        cfg["approval_channel_config"] = body.approval_channel_config
    if body.approval_timeout_minutes is not None:
        cfg["approval_timeout_minutes"] = body.approval_timeout_minutes

    task.config = cfg

    if body.schedule is not None:
        sched = parse_schedule(body.schedule)
        task.schedule_type = sched["schedule_type"]
        task.cron_expression = sched.get("cron_expression")
        task.interval_seconds = sched.get("interval_seconds")

    if body.is_active is not None:
        task.is_active = body.is_active
        agent.autonomous_enabled = body.is_active

    await db.commit()
    await db.refresh(task)

    result = await db.execute(
        select(TaskExecution)
        .filter(TaskExecution.task_id == task.id)
        .order_by(TaskExecution.started_at.desc())
        .limit(_MAX_RUNS)
    )
    runs = [_execution_to_schema(ex) for ex in result.scalars().all()]
    return _task_to_status(task, agent, runs)


# ---------------------------------------------------------------------------
# DELETE /agents/{agent_slug}/autonomous
# ---------------------------------------------------------------------------


@router.delete("/{agent_slug}/autonomous", status_code=status.HTTP_204_NO_CONTENT)
async def delete_autonomous_config(
    agent_slug: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete autonomous schedule and set autonomous_enabled=False."""
    agent = await _get_agent(agent_slug, tenant_id, db)
    task = await _get_task(agent.id, tenant_id, db)
    if task:
        await db.delete(task)

    agent.autonomous_enabled = False
    await db.commit()


# ---------------------------------------------------------------------------
# POST /agents/{agent_slug}/autonomous/trigger  — immediate run
# ---------------------------------------------------------------------------


@router.post("/{agent_slug}/autonomous/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_autonomous_run(
    agent_slug: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Enqueue an immediate autonomous run."""
    agent = await _get_agent(agent_slug, tenant_id, db)
    task = await _get_task(agent.id, tenant_id, db)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Autonomous config not found")

    from src.tasks.scheduled_tasks import execute_scheduled_task

    execute_scheduled_task.delay(str(task.id))
    return {"queued": True, "task_id": str(task.id)}


# ---------------------------------------------------------------------------
# GET /agents/{agent_slug}/autonomous/memory
# ---------------------------------------------------------------------------


@router.get("/{agent_slug}/autonomous/memory", response_model=list[AutonomousMemoryMessageSchema])
async def get_autonomous_memory(
    agent_slug: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return the last 50 messages from the autonomous memory conversation."""
    agent = await _get_agent(agent_slug, tenant_id, db)
    task = await _get_task(agent.id, tenant_id, db)
    if not task:
        return []

    conv_id = (task.config or {}).get("autonomous_conversation_id")
    if not conv_id:
        return []

    conv_uuid = uuid.UUID(conv_id)
    result = await db.execute(
        select(Message)
        .filter(Message.conversation_id == conv_uuid)
        .order_by(Message.created_at.desc())
        .limit(_MAX_MEMORY_MESSAGES)
    )
    messages = result.scalars().all()
    return [
        AutonomousMemoryMessageSchema(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in reversed(messages)
    ]


# ---------------------------------------------------------------------------
# GET /agents/{agent_slug}/autonomous/approvals
# ---------------------------------------------------------------------------


@router.get("/{agent_slug}/autonomous/approvals", response_model=list[ApprovalRequestSchema])
async def list_pending_approvals(
    agent_slug: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List pending approval requests for this agent, newest first."""
    from src.models.agent_approval import AgentApprovalRequest, ApprovalStatus

    agent = await _get_agent(agent_slug, tenant_id, db)
    result = await db.execute(
        select(AgentApprovalRequest)
        .filter(
            AgentApprovalRequest.agent_id == agent.id,
            AgentApprovalRequest.tenant_id == tenant_id,
            AgentApprovalRequest.status == ApprovalStatus.PENDING,
        )
        .order_by(AgentApprovalRequest.created_at.desc())
        .limit(50)
    )
    approvals = result.scalars().all()
    return [
        ApprovalRequestSchema(
            id=a.id,
            task_id=a.task_id,
            agent_name=a.agent_name,
            tool_name=a.tool_name,
            tool_args=a.tool_args,
            status=a.status,
            notification_channel=a.notification_channel,
            expires_at=a.expires_at,
            created_at=a.created_at,
        )
        for a in approvals
    ]


# ---------------------------------------------------------------------------
# POST /agents/{agent_slug}/autonomous/approvals/{approval_id}/respond
# ---------------------------------------------------------------------------


@router.post(
    "/{agent_slug}/autonomous/approvals/{approval_id}/respond",
    status_code=status.HTTP_200_OK,
)
async def respond_to_approval(
    agent_slug: str,
    approval_id: UUID,
    body: ApprovalRespondBody,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Respond to a pending approval request from the dashboard."""
    from src.models.agent_approval import AgentApprovalRequest
    from src.services.human_approval_service import HumanApprovalService

    agent = await _get_agent(agent_slug, tenant_id, db)

    # Verify approval belongs to this agent and tenant
    result = await db.execute(
        select(AgentApprovalRequest).filter(
            AgentApprovalRequest.id == approval_id,
            AgentApprovalRequest.agent_id == agent.id,
            AgentApprovalRequest.tenant_id == tenant_id,
        )
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")

    svc = HumanApprovalService(db)
    return await svc.respond_to_approval(
        approval_id=approval_id,
        decision=body.decision,
        feedback_text=body.feedback_text,
        db=db,
    )


# ---------------------------------------------------------------------------
# DELETE /agents/{agent_slug}/autonomous/memory
# ---------------------------------------------------------------------------


@router.delete("/{agent_slug}/autonomous/memory", status_code=status.HTTP_204_NO_CONTENT)
async def clear_autonomous_memory(
    agent_slug: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete all messages in the autonomous memory conversation and reset summary."""
    agent = await _get_agent(agent_slug, tenant_id, db)
    task = await _get_task(agent.id, tenant_id, db)
    if not task:
        return

    conv_id = (task.config or {}).get("autonomous_conversation_id")
    if not conv_id:
        return

    conv_uuid = uuid.UUID(conv_id)
    result = await db.execute(select(Conversation).filter(Conversation.id == conv_uuid))
    conv = result.scalar_one_or_none()
    if conv:
        await db.execute(delete(Message).where(Message.conversation_id == conv_uuid))
        conv.context_summary = None
        conv.summary_updated_at = None
        conv.summary_message_count = 0
        conv.total_tokens_estimated = 0
        conv.message_count = 0

    await db.commit()
