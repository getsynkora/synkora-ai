"""
Agent Lens Service

Observability analytics for agents: tool call persistence (fire-and-forget),
session stats, timeline queries, token distribution, and alert CRUD.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Strong references to background tasks prevent GC before completion.
_lens_bg_tasks: set[asyncio.Task] = set()

# Maximum bytes stored per tool result (prevents large blobs bloating the table).
_RESULT_MAX_BYTES = 2048


# ---------------------------------------------------------------------------
# Fire-and-forget tool call persistence
# ---------------------------------------------------------------------------


def _truncate_result(result) -> dict | None:
    """Cap the stored tool result to _RESULT_MAX_BYTES."""
    if result is None:
        return None
    try:
        encoded = json.dumps(result, default=str)
        if len(encoded) <= _RESULT_MAX_BYTES:
            return result if isinstance(result, dict) else {"value": result}
        # Truncate the JSON string and store as a marker object
        truncated = encoded[:_RESULT_MAX_BYTES]
        return {"_truncated": True, "preview": truncated}
    except Exception:
        return {"_truncated": True, "preview": str(result)[:_RESULT_MAX_BYTES]}


async def _persist_tool_call(data: dict) -> None:
    """Write one AgentToolCallLog row using a fresh DB session."""
    from src.core.database import get_async_session_factory
    from src.models.agent_tool_call_log import AgentToolCallLog

    factory = get_async_session_factory()
    session = factory()
    try:
        session.add(AgentToolCallLog(**data))
        await session.commit()
    except Exception as e:
        logger.warning("tool call log persist failed (non-critical): %s", e)
        try:
            await session.rollback()
        except Exception:
            pass
    finally:
        try:
            await session.close()
        except Exception:
            pass


def _fire_persist_tool_call(
    *,
    tenant_id: UUID,
    agent_id: UUID | None,
    conversation_id: UUID | None,
    message_id: UUID | None,
    tool_name: str,
    tool_args: dict | None,
    tool_result,
    success: bool,
    duration_ms: int | None,
    retry_count: int,
    error_message: str | None,
) -> None:
    """
    Fire-and-forget — never awaited, never blocks the SSE stream.

    Follows fire_persist_llm_usage pattern exactly (llm_cost_service.py).
    Failure is silent: observability data loss is acceptable vs blocking chat.
    """
    from src.config.settings import get_settings

    try:
        if not get_settings().agent_lens_enabled:
            return

        data = {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "tool_result": _truncate_result(tool_result),
            "success": success,
            "duration_ms": duration_ms,
            "retry_count": retry_count,
            "error_message": error_message,
        }
        task = asyncio.create_task(_persist_tool_call(data))
        _lens_bg_tasks.add(task)
        task.add_done_callback(_lens_bg_tasks.discard)
    except Exception as e:
        logger.warning("_fire_persist_tool_call scheduling error: %s", e)


# ---------------------------------------------------------------------------
# Date-range helpers
# ---------------------------------------------------------------------------


def _parse_range(range_str: str) -> tuple[datetime, datetime]:
    """Return (start, end) UTC datetimes for a range string like '7d', '24h', '30d'."""
    now = datetime.now(UTC)
    mapping = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
    }
    delta = mapping.get(range_str, timedelta(days=7))
    return now - delta, now


# ---------------------------------------------------------------------------
# Overview stats
# ---------------------------------------------------------------------------


async def get_overview(
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Return all 9 stat card values for the overview panel."""
    from src.models.agent_tool_call_log import AgentToolCallLog
    from src.models.conversation import Conversation
    from src.models.message import Message, MessageRole
    from src.services.billing.llm_cost_service import get_cost_summary

    # Run queries sequentially — AsyncSession cannot be shared across concurrent coroutines
    conv_result = await _query_session_stats(db, tenant_id, agent_id, start_date, end_date)
    cost_summary = await get_cost_summary(db, tenant_id, start_date, end_date, agent_id=agent_id)
    tool_stats = await _query_tool_stats(db, tenant_id, agent_id, start_date, end_date)

    total_sessions = conv_result["total_sessions"]
    avg_latency_ms = conv_result["avg_latency_ms"]
    total_requests = cost_summary["total_calls"]
    total_tokens = cost_summary["total_input_tokens"] + cost_summary["total_output_tokens"]
    input_tokens = cost_summary["total_input_tokens"]
    output_tokens = cost_summary["total_output_tokens"]
    total_cost_usd = cost_summary["total_cost_usd"]
    avg_cost_per_session = (total_cost_usd / total_sessions) if total_sessions > 0 else 0.0
    failure_rate = tool_stats["failure_rate"]

    return {
        "total_sessions": total_sessions,
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "avg_latency_ms": avg_latency_ms,
        "total_cost_usd": round(total_cost_usd, 6),
        "avg_cost_per_session": round(avg_cost_per_session, 6),
        "failure_rate": round(failure_rate, 4),
        "total_tool_calls": tool_stats["total_tool_calls"],
        "failed_tool_calls": tool_stats["failed_tool_calls"],
        "avg_tool_duration_ms": tool_stats["avg_tool_duration_ms"],
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
    }


async def _query_session_stats(
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Count conversations and compute avg latency from message_metadata."""
    from src.models.conversation import Conversation
    from src.models.message import Message, MessageRole

    # Count distinct conversations for this agent in period
    conv_q = select(func.count(Conversation.id)).where(
        Conversation.agent_id == agent_id,
        Conversation.created_at >= start_date,
        Conversation.created_at < end_date,
        Conversation.deleted_at.is_(None),
    )
    total_sessions = (await db.execute(conv_q)).scalar() or 0

    # Avg latency from message_metadata["timing"]["total_time"] (assistant messages only)
    # Cast JSON path to float using PostgreSQL syntax
    latency_q = select(
        func.avg(Message.message_metadata["timing"]["total_time"].as_float()).label("avg_latency_s")
    ).where(
        Message.conversation_id.in_(
            select(Conversation.id).where(
                Conversation.agent_id == agent_id,
                Conversation.created_at >= start_date,
                Conversation.created_at < end_date,
                Conversation.deleted_at.is_(None),
            )
        ),
        Message.role == MessageRole.ASSISTANT,
        Message.message_metadata["timing"]["total_time"].as_float().isnot(None),
    )
    avg_latency_s = (await db.execute(latency_q)).scalar()
    avg_latency_ms = int((avg_latency_s or 0) * 1000)

    return {"total_sessions": int(total_sessions), "avg_latency_ms": avg_latency_ms}


async def _query_tool_stats(
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Aggregate tool call counts, failure rate, and avg duration."""
    from src.models.agent_tool_call_log import AgentToolCallLog

    q = select(
        func.count(AgentToolCallLog.id).label("total"),
        func.sum(
            case((AgentToolCallLog.success == False, 1), else_=0)  # noqa: E712
        ).label("failed"),
        func.avg(AgentToolCallLog.duration_ms).label("avg_duration"),
    ).where(
        AgentToolCallLog.tenant_id == tenant_id,
        AgentToolCallLog.agent_id == agent_id,
        AgentToolCallLog.created_at >= start_date,
        AgentToolCallLog.created_at < end_date,
    )
    row = (await db.execute(q)).one()
    total = int(row.total or 0)
    failed = int(row.failed or 0)
    avg_dur = int(row.avg_duration or 0)
    failure_rate = (failed / total) if total > 0 else 0.0
    return {
        "total_tool_calls": total,
        "failed_tool_calls": failed,
        "avg_tool_duration_ms": avg_dur,
        "failure_rate": failure_rate,
    }


# ---------------------------------------------------------------------------
# Sessions list
# ---------------------------------------------------------------------------


async def get_sessions(
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
    start_date: datetime,
    end_date: datetime,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Paginated list of conversation sessions with token/cost summary."""
    from src.models.conversation import Conversation
    from src.models.llm_token_usage import LLMTokenUsage
    from src.models.message import Message

    page = max(1, page)
    page_size = min(100, max(1, page_size))
    offset = (page - 1) * page_size

    # Subquery: aggregate LLM usage per conversation
    usage_sq = (
        select(
            LLMTokenUsage.conversation_id,
            func.sum(LLMTokenUsage.input_tokens + LLMTokenUsage.output_tokens).label("total_tokens"),
            func.sum(LLMTokenUsage.estimated_cost_usd).label("cost_usd"),
            func.count(LLMTokenUsage.id).label("llm_calls"),
            func.min(LLMTokenUsage.model_name).label("model_name"),
        )
        .group_by(LLMTokenUsage.conversation_id)
        .subquery()
    )

    # Message count subquery
    msg_sq = (
        select(
            Message.conversation_id,
            func.count(Message.id).label("message_count"),
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    base_filter = [
        Conversation.agent_id == agent_id,
        Conversation.created_at >= start_date,
        Conversation.created_at < end_date,
        Conversation.deleted_at.is_(None),
    ]

    total_q = select(func.count(Conversation.id)).where(*base_filter)
    total = (await db.execute(total_q)).scalar() or 0

    rows_q = (
        select(
            Conversation.id,
            Conversation.name,
            Conversation.status,
            Conversation.created_at,
            func.coalesce(usage_sq.c.total_tokens, 0).label("total_tokens"),
            func.coalesce(usage_sq.c.cost_usd, 0).label("cost_usd"),
            func.coalesce(msg_sq.c.message_count, 0).label("message_count"),
            usage_sq.c.model_name,
        )
        .outerjoin(usage_sq, usage_sq.c.conversation_id == Conversation.id)
        .outerjoin(msg_sq, msg_sq.c.conversation_id == Conversation.id)
        .where(*base_filter)
        .order_by(Conversation.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    rows = (await db.execute(rows_q)).all()

    sessions = [
        {
            "id": str(r.id),
            "name": r.name,
            "status": r.status,
            "model_name": r.model_name,
            "total_tokens": int(r.total_tokens or 0),
            "cost_usd": float(r.cost_usd or 0),
            "message_count": int(r.message_count or 0),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

    return {
        "sessions": sessions,
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (int(total) + page_size - 1) // page_size),
    }


# ---------------------------------------------------------------------------
# Session detail
# ---------------------------------------------------------------------------


async def get_session_detail(
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
    conversation_id: UUID,
) -> dict:
    """Return merged message + tool call timeline for a single session."""
    from src.models.agent_tool_call_log import AgentToolCallLog
    from src.models.conversation import Conversation
    from src.models.llm_token_usage import LLMTokenUsage
    from src.models.message import Message

    # Validate ownership
    conv_q = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.agent_id == agent_id,
    )
    conv = (await db.execute(conv_q)).scalar_one_or_none()
    if conv is None:
        return {}

    # Messages
    msgs_q = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    messages = (await db.execute(msgs_q)).scalars().all()

    # Tool calls
    tools_q = (
        select(AgentToolCallLog)
        .where(
            AgentToolCallLog.conversation_id == conversation_id,
            AgentToolCallLog.tenant_id == tenant_id,
        )
        .order_by(AgentToolCallLog.created_at)
    )
    tool_calls = (await db.execute(tools_q)).scalars().all()

    # LLM usage summary
    usage_q = select(
        func.sum(LLMTokenUsage.input_tokens).label("input_tokens"),
        func.sum(LLMTokenUsage.output_tokens).label("output_tokens"),
        func.sum(LLMTokenUsage.estimated_cost_usd).label("cost_usd"),
    ).where(LLMTokenUsage.conversation_id == conversation_id)
    usage = (await db.execute(usage_q)).one()

    # Build timeline — merge messages + tool calls sorted by created_at
    timeline = []
    for m in messages:
        meta = m.message_metadata or {}
        timing = meta.get("timing", {})
        usage_meta = meta.get("usage", {})
        timeline.append(
            {
                "event_type": "message",
                "id": str(m.id),
                "timestamp": m.created_at.isoformat() if m.created_at else None,
                "role": m.role,
                "content": m.content,
                "token_count": m.token_count,
                "input_tokens": usage_meta.get("input_tokens"),
                "output_tokens": usage_meta.get("output_tokens"),
                "latency_ms": int(timing.get("total_time", 0) * 1000) if timing.get("total_time") else None,
                "status": m.status,
                "error": m.error,
            }
        )
    for t in tool_calls:
        timeline.append(
            {
                "event_type": "tool_call",
                "id": str(t.id),
                "timestamp": t.created_at.isoformat() if t.created_at else None,
                "tool_name": t.tool_name,
                "tool_args": t.tool_args,
                "tool_result": t.tool_result,
                "success": t.success,
                "duration_ms": t.duration_ms,
                "retry_count": t.retry_count,
                "error_message": t.error_message,
            }
        )

    timeline.sort(key=lambda x: x.get("timestamp") or "")

    total_tool = len(tool_calls)
    failed_tool = sum(1 for t in tool_calls if not t.success)

    return {
        "conversation_id": str(conversation_id),
        "name": conv.name,
        "status": conv.status,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "timeline": timeline,
        "total_tokens": int((usage.input_tokens or 0) + (usage.output_tokens or 0)),
        "input_tokens": int(usage.input_tokens or 0),
        "output_tokens": int(usage.output_tokens or 0),
        "total_cost_usd": float(usage.cost_usd or 0),
        "total_tool_calls": total_tool,
        "failed_tool_calls": failed_tool,
        "message_count": len(messages),
    }


# ---------------------------------------------------------------------------
# Token distribution
# ---------------------------------------------------------------------------


async def get_token_distribution(
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Token + cost breakdown by model, plus prompt vs completion totals."""
    from src.models.llm_token_usage import LLMTokenUsage
    from src.services.billing.llm_cost_service import get_cost_summary

    # By model breakdown (filter by agent_id)
    model_q = (
        select(
            LLMTokenUsage.model_name,
            func.sum(LLMTokenUsage.input_tokens + LLMTokenUsage.output_tokens).label("tokens"),
            func.sum(LLMTokenUsage.estimated_cost_usd).label("cost_usd"),
            func.count(LLMTokenUsage.id).label("calls"),
        )
        .where(
            LLMTokenUsage.tenant_id == tenant_id,
            LLMTokenUsage.agent_id == agent_id,
            LLMTokenUsage.created_at >= start_date,
            LLMTokenUsage.created_at < end_date,
        )
        .group_by(LLMTokenUsage.model_name)
        .order_by(func.sum(LLMTokenUsage.estimated_cost_usd).desc().nulls_last())
    )
    model_rows = (await db.execute(model_q)).all()

    summary = await get_cost_summary(db, tenant_id, start_date, end_date, agent_id=agent_id)

    return {
        "by_model": [
            {
                "model_name": r.model_name,
                "tokens": int(r.tokens or 0),
                "cost_usd": float(r.cost_usd or 0),
                "calls": int(r.calls or 0),
            }
            for r in model_rows
        ],
        "prompt_vs_completion": {
            "input_tokens": summary["total_input_tokens"],
            "output_tokens": summary["total_output_tokens"],
        },
    }


# ---------------------------------------------------------------------------
# Tool analytics
# ---------------------------------------------------------------------------


async def get_tool_analytics(
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """Per-tool breakdown: call count, success rate, duration stats."""
    from src.models.agent_tool_call_log import AgentToolCallLog

    q = (
        select(
            AgentToolCallLog.tool_name,
            func.count(AgentToolCallLog.id).label("total_calls"),
            func.sum(case((AgentToolCallLog.success == True, 1), else_=0)).label("success_count"),  # noqa: E712
            func.sum(case((AgentToolCallLog.success == False, 1), else_=0)).label("failure_count"),  # noqa: E712
            func.avg(AgentToolCallLog.duration_ms).label("avg_duration_ms"),
            func.max(AgentToolCallLog.duration_ms).label("max_duration_ms"),
            func.sum(AgentToolCallLog.retry_count).label("total_retries"),
        )
        .where(
            AgentToolCallLog.tenant_id == tenant_id,
            AgentToolCallLog.agent_id == agent_id,
            AgentToolCallLog.created_at >= start_date,
            AgentToolCallLog.created_at < end_date,
        )
        .group_by(AgentToolCallLog.tool_name)
        .order_by(func.count(AgentToolCallLog.id).desc())
        .limit(20)
    )
    rows = (await db.execute(q)).all()

    tools = []
    total_calls = 0
    total_failures = 0
    for r in rows:
        calls = int(r.total_calls or 0)
        failures = int(r.failure_count or 0)
        successes = int(r.success_count or 0)
        total_calls += calls
        total_failures += failures
        tools.append(
            {
                "tool_name": r.tool_name,
                "total_calls": calls,
                "success_count": successes,
                "failure_count": failures,
                "success_rate": round((successes / calls) if calls > 0 else 1.0, 4),
                "avg_duration_ms": int(r.avg_duration_ms or 0),
                "max_duration_ms": int(r.max_duration_ms or 0),
                "total_retries": int(r.total_retries or 0),
            }
        )

    overall_success_rate = round(((total_calls - total_failures) / total_calls) if total_calls > 0 else 1.0, 4)
    return {
        "tools": tools,
        "total_calls": total_calls,
        "total_failures": total_failures,
        "overall_success_rate": overall_success_rate,
    }


# ---------------------------------------------------------------------------
# Alert CRUD
# ---------------------------------------------------------------------------


async def get_alerts(db: AsyncSession, tenant_id: UUID, agent_id: UUID) -> list[dict]:
    from src.models.agent_lens_alert import AgentLensAlert

    q = (
        select(AgentLensAlert)
        .where(
            AgentLensAlert.tenant_id == tenant_id,
            AgentLensAlert.agent_id == agent_id,
        )
        .order_by(AgentLensAlert.created_at.desc())
    )
    rows = (await db.execute(q)).scalars().all()
    return [_alert_to_dict(r) for r in rows]


async def create_alert(db: AsyncSession, tenant_id: UUID, agent_id: UUID, data: dict) -> dict:
    from src.models.agent_lens_alert import AgentLensAlert

    alert = AgentLensAlert(tenant_id=tenant_id, agent_id=agent_id, **data)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return _alert_to_dict(alert)


async def update_alert(db: AsyncSession, tenant_id: UUID, alert_id: UUID, data: dict) -> dict | None:
    from src.models.agent_lens_alert import AgentLensAlert

    q = select(AgentLensAlert).where(
        AgentLensAlert.id == alert_id,
        AgentLensAlert.tenant_id == tenant_id,
    )
    alert = (await db.execute(q)).scalar_one_or_none()
    if alert is None:
        return None
    for k, v in data.items():
        setattr(alert, k, v)
    await db.commit()
    await db.refresh(alert)
    return _alert_to_dict(alert)


async def delete_alert(db: AsyncSession, tenant_id: UUID, alert_id: UUID) -> bool:
    from src.models.agent_lens_alert import AgentLensAlert

    q = select(AgentLensAlert).where(
        AgentLensAlert.id == alert_id,
        AgentLensAlert.tenant_id == tenant_id,
    )
    alert = (await db.execute(q)).scalar_one_or_none()
    if alert is None:
        return False
    await db.delete(alert)
    await db.commit()
    return True


def _alert_to_dict(alert) -> dict:
    return {
        "id": str(alert.id),
        "agent_id": str(alert.agent_id),
        "name": alert.name,
        "metric": alert.metric,
        "condition": alert.condition,
        "threshold": float(alert.threshold),
        "window_minutes": alert.window_minutes,
        "notify_method": alert.notify_method,
        "notify_config": alert.notify_config,
        "is_active": alert.is_active,
        "last_triggered_at": alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }
