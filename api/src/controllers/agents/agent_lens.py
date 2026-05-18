"""
Agent Lens API endpoints.

Mounts at /api/v1/agents/{agent_slug}/lens and provides observability data:
overview stats, session list, session detail timeline, token distribution,
and alert CRUD.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.schemas.agent_lens import (
    AlertCreateBody,
    AlertResponse,
    AlertUpdateBody,
    LensCacheAnalyticsResponse,
    LensCompactionAnalyticsResponse,
    LensOverviewResponse,
    LensSessionDetailResponse,
    LensSessionGraphResponse,
    LensSessionsResponse,
    LensStatCard,
    LensTokenDistributionResponse,
    LensToolAnalyticsResponse,
    LensToolROIResponse,
    LensToolROIStat,
    LensToolStat,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_VALID_RANGES = {"24h", "7d", "30d", "90d"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_agent(agent_slug: str, tenant_id: UUID, db: AsyncSession) -> Agent:
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


def _parse_range(range_str: str) -> tuple[datetime, datetime]:
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
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{agent_slug}/lens/overview", response_model=LensOverviewResponse)
async def lens_overview(
    agent_slug: str,
    range: str = Query(default="7d"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return stat card values for the overview panel."""
    if range not in _VALID_RANGES:
        range = "7d"

    agent = await _get_agent(agent_slug, tenant_id, db)
    start_date, end_date = _parse_range(range)

    from src.services.agents.agent_trace_service import get_overview

    data = await get_overview(tenant_id, agent.id, start_date, end_date)

    stats = LensStatCard(
        total_sessions=data["total_sessions"],
        total_requests=data["total_requests"],
        total_tokens=data["total_tokens"],
        input_tokens=data["input_tokens"],
        output_tokens=data["output_tokens"],
        avg_latency_ms=data["avg_latency_ms"],
        total_cost_usd=data["total_cost_usd"],
        avg_cost_per_session=data["avg_cost_per_session"],
        failure_rate=data["failure_rate"],
        total_tool_calls=data["total_tool_calls"],
        failed_tool_calls=data["failed_tool_calls"],
        avg_tool_duration_ms=data["avg_tool_duration_ms"],
    )
    return LensOverviewResponse(stats=stats, period_start=data["period_start"], period_end=data["period_end"])


@router.get("/{agent_slug}/lens/token-distribution", response_model=LensTokenDistributionResponse)
async def lens_token_distribution(
    agent_slug: str,
    range: str = Query(default="7d"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return token/cost distribution by model and prompt vs completion."""
    if range not in _VALID_RANGES:
        range = "7d"

    agent = await _get_agent(agent_slug, tenant_id, db)
    start_date, end_date = _parse_range(range)

    from src.schemas.agent_lens import LensModelBreakdown, LensPromptVsCompletion
    from src.services.agents.agent_trace_service import get_token_distribution

    data = await get_token_distribution(tenant_id, agent.id, start_date, end_date)
    return LensTokenDistributionResponse(
        by_model=[LensModelBreakdown(**m) for m in data["by_model"]],
        prompt_vs_completion=LensPromptVsCompletion(**data["prompt_vs_completion"]),
    )


@router.get("/{agent_slug}/lens/sessions", response_model=LensSessionsResponse)
async def lens_sessions(
    agent_slug: str,
    range: str = Query(default="7d"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return paginated list of conversation sessions."""
    if range not in _VALID_RANGES:
        range = "7d"

    agent = await _get_agent(agent_slug, tenant_id, db)
    start_date, end_date = _parse_range(range)

    from src.schemas.agent_lens import LensSessionRow
    from src.services.agents.agent_trace_service import get_sessions

    data = await get_sessions(tenant_id, agent.id, start_date, end_date, page=page, page_size=page_size)
    return LensSessionsResponse(
        sessions=[LensSessionRow(**s) for s in data["sessions"]],
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
        total_pages=data["total_pages"],
    )


@router.get("/{agent_slug}/lens/sessions/{session_id}", response_model=LensSessionDetailResponse)
async def lens_session_detail(
    agent_slug: str,
    session_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return merged message + tool call timeline for a single session."""
    agent = await _get_agent(agent_slug, tenant_id, db)

    from src.schemas.agent_lens import LensTimelineEvent
    from src.services.agents.agent_trace_service import get_session_detail

    data = await get_session_detail(tenant_id, agent.id, session_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return LensSessionDetailResponse(
        conversation_id=data["conversation_id"],
        name=data["name"],
        status=data["status"],
        created_at=data.get("created_at"),
        timeline=[LensTimelineEvent(**e) for e in data["timeline"]],
        total_tokens=data["total_tokens"],
        input_tokens=data["input_tokens"],
        output_tokens=data["output_tokens"],
        total_cost_usd=data["total_cost_usd"],
        total_tool_calls=data["total_tool_calls"],
        failed_tool_calls=data["failed_tool_calls"],
        message_count=data["message_count"],
    )


@router.get("/{agent_slug}/lens/tool-analytics", response_model=LensToolAnalyticsResponse)
async def lens_tool_analytics(
    agent_slug: str,
    range: str = Query(default="7d"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return per-tool call counts, success rates, and duration stats."""
    if range not in _VALID_RANGES:
        range = "7d"

    agent = await _get_agent(agent_slug, tenant_id, db)
    start_date, end_date = _parse_range(range)

    from src.services.agents.agent_trace_service import get_tool_analytics

    data = await get_tool_analytics(tenant_id, agent.id, start_date, end_date)
    return LensToolAnalyticsResponse(
        tools=[LensToolStat(**t) for t in data["tools"]],
        total_calls=data["total_calls"],
        total_failures=data["total_failures"],
        overall_success_rate=data["overall_success_rate"],
    )


@router.get("/{agent_slug}/lens/tool-roi", response_model=LensToolROIResponse)
async def lens_tool_roi(
    agent_slug: str,
    range: str = Query(default="7d"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return Tool ROI analysis: per-tool completion lift, cost impact, and verdict."""
    if range not in _VALID_RANGES:
        range = "7d"

    agent = await _get_agent(agent_slug, tenant_id, db)
    start_date, end_date = _parse_range(range)

    from src.services.agents.agent_trace_service import get_tool_roi

    data = await get_tool_roi(tenant_id, agent.id, start_date, end_date)
    return LensToolROIResponse(
        tools=[LensToolROIStat(**t) for t in data["tools"]],
        total_sessions=data["total_sessions"],
        period_start=data["period_start"],
        period_end=data["period_end"],
    )


@router.get("/{agent_slug}/lens/compaction", response_model=LensCompactionAnalyticsResponse)
async def lens_compaction(
    agent_slug: str,
    range: str = Query(default="7d"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return context-pruning / compaction analytics.

    Shows how often pruning triggered, how many tokens were saved, and whether
    data-bearing tool results (SQL rows, CSV contents) were trimmed — a key
    signal for understanding LLM quality degradation.
    """
    if range not in _VALID_RANGES:
        range = "7d"

    agent = await _get_agent(agent_slug, tenant_id, db)
    start_date, end_date = _parse_range(range)

    from src.schemas.agent_lens import LensPruningTrendPoint
    from src.services.agents.agent_trace_service import get_compaction_analytics

    data = await get_compaction_analytics(tenant_id, agent.id, start_date, end_date)
    return LensCompactionAnalyticsResponse(
        total_sessions=data["total_sessions"],
        sessions_with_pruning=data["sessions_with_pruning"],
        pruning_rate=data["pruning_rate"],
        pruning_events_count=data["pruning_events_count"],
        total_tokens_saved=data["total_tokens_saved"],
        avg_tokens_saved_per_session=data["avg_tokens_saved_per_session"],
        data_bearing_pruned_total=data["data_bearing_pruned_total"],
        total_results_pruned=data["total_results_pruned"],
        total_results_evaluated=data["total_results_evaluated"],
        avg_pruning_ratio=data["avg_pruning_ratio"],
        trend=[LensPruningTrendPoint(**t) for t in data["trend"]],
        period_start=data["period_start"],
        period_end=data["period_end"],
    )


@router.get("/{agent_slug}/lens/cache", response_model=LensCacheAnalyticsResponse)
async def lens_cache(
    agent_slug: str,
    range: str = Query(default="7d"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return prompt-cache analytics: hit rate, tokens saved, context window pressure."""
    if range not in _VALID_RANGES:
        range = "7d"

    agent = await _get_agent(agent_slug, tenant_id, db)
    start_date, end_date = _parse_range(range)

    from src.schemas.agent_lens import LensCacheTrendPoint
    from src.services.agents.agent_trace_service import get_cache_analytics

    data = await get_cache_analytics(tenant_id, agent.id, start_date, end_date)
    return LensCacheAnalyticsResponse(
        total_llm_calls=data["total_llm_calls"],
        total_input_tokens=data["total_input_tokens"],
        total_cache_read_tokens=data["total_cache_read_tokens"],
        total_cache_creation_tokens=data["total_cache_creation_tokens"],
        cache_hit_rate=data["cache_hit_rate"],
        estimated_savings_usd=data["estimated_savings_usd"],
        avg_context_utilization_pct=data["avg_context_utilization_pct"],
        max_context_utilization_pct=data["max_context_utilization_pct"],
        high_pressure_calls=data["high_pressure_calls"],
        trend=[LensCacheTrendPoint(**t) for t in data["trend"]],
        period_start=data["period_start"],
        period_end=data["period_end"],
    )


@router.get("/{agent_slug}/lens/sessions/{session_id}/graph", response_model=LensSessionGraphResponse)
async def lens_session_graph(
    agent_slug: str,
    session_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return the session timeline as a directed graph (nodes + edges) for visualisation.

    Each event becomes a node; edges connect them in chronological order.
    Pruning events appear inline so you can see exactly when context was compacted
    and whether data-bearing results were affected.
    """
    agent = await _get_agent(agent_slug, tenant_id, db)

    from src.schemas.agent_lens import LensGraphEdge, LensGraphNode
    from src.services.agents.agent_trace_service import get_session_graph

    data = await get_session_graph(tenant_id, agent.id, session_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return LensSessionGraphResponse(
        conversation_id=data["conversation_id"],
        nodes=[LensGraphNode(**n) for n in data["nodes"]],
        edges=[LensGraphEdge(**e) for e in data["edges"]],
    )


@router.get("/{agent_slug}/lens/alerts", response_model=list[AlertResponse])
async def get_lens_alerts(
    agent_slug: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all alerts configured for this agent."""
    agent = await _get_agent(agent_slug, tenant_id, db)

    from src.services.agents.agent_trace_service import get_alerts

    return [AlertResponse(**a) for a in await get_alerts(db, tenant_id, agent.id)]


@router.post("/{agent_slug}/lens/alerts", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_lens_alert(
    agent_slug: str,
    body: AlertCreateBody,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new alert for this agent."""
    agent = await _get_agent(agent_slug, tenant_id, db)

    from src.services.agents.agent_trace_service import create_alert

    data = body.model_dump()
    return AlertResponse(**await create_alert(db, tenant_id, agent.id, data))


@router.put("/{agent_slug}/lens/alerts/{alert_id}", response_model=AlertResponse)
async def update_lens_alert(
    agent_slug: str,
    alert_id: UUID,
    body: AlertUpdateBody,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update an existing alert."""
    await _get_agent(agent_slug, tenant_id, db)

    from src.services.agents.agent_trace_service import update_alert

    data = {k: v for k, v in body.model_dump().items() if v is not None}
    result = await update_alert(db, tenant_id, alert_id, data)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return AlertResponse(**result)


@router.delete("/{agent_slug}/lens/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lens_alert(
    agent_slug: str,
    alert_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete an alert."""
    await _get_agent(agent_slug, tenant_id, db)

    from src.services.agents.agent_trace_service import delete_alert

    deleted = await delete_alert(db, tenant_id, alert_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
