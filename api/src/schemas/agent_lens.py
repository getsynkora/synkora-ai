"""
Agent Lens Schemas

Request/response Pydantic models for the observability API.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


class LensStatCard(BaseModel):
    total_sessions: int
    total_requests: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    avg_latency_ms: int
    total_cost_usd: float
    avg_cost_per_session: float
    failure_rate: float
    total_tool_calls: int
    failed_tool_calls: int
    avg_tool_duration_ms: int


class LensOverviewResponse(BaseModel):
    stats: LensStatCard
    period_start: str
    period_end: str


# ---------------------------------------------------------------------------
# Sessions list
# ---------------------------------------------------------------------------


class LensSessionRow(BaseModel):
    id: str
    name: str
    status: str
    model_name: str | None = None
    total_tokens: int
    cost_usd: float
    message_count: int
    created_at: str | None = None


class LensSessionsResponse(BaseModel):
    sessions: list[LensSessionRow]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Session detail / timeline
# ---------------------------------------------------------------------------


class LensTimelineEvent(BaseModel):
    event_type: Literal["user_message", "llm_call", "tool_call", "assistant_message", "tool_pruning"]
    id: str
    timestamp: str | None = None
    sequence: int | None = None
    # user_message / assistant_message fields
    role: str | None = None
    content: str | None = None
    content_preview: str | None = None
    token_count: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    total_latency_ms: int | None = None
    total_cost_usd: float | None = None
    status: str | None = None
    error: str | None = None
    # llm_call fields
    model: str | None = None
    call_index: int | None = None
    cost_usd: float | None = None
    response_preview: str | None = None
    # llm_call input inspection fields
    system_prompt_preview: str | None = None
    messages_json: str | None = None  # JSON string: list of chat messages sent to LLM
    tools_json: str | None = None  # JSON string: list of tool definitions sent to LLM
    # llm_call prompt cache fields
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    # llm_call context window pressure (0–100 %)
    context_utilization_pct: float | None = None
    # tool call fields
    tool_name: str | None = None
    tool_args: str | None = None  # JSON string stored in ES text field
    tool_result: str | None = None  # JSON string stored in ES text field
    success: bool | None = None
    duration_ms: int | None = None
    retry_count: int | None = None
    error_message: str | None = None
    # tool_pruning fields
    turn_index: int | None = None
    tool_results_count: int | None = None
    tool_results_pruned: int | None = None
    data_bearing_pruned: int | None = None  # > 0 means data-holding results were trimmed
    chars_saved: int | None = None
    estimated_tokens_saved: int | None = None
    original_chars: int | None = None
    pruned_chars: int | None = None


class LensSessionDetailResponse(BaseModel):
    conversation_id: str
    name: str
    status: str
    created_at: str | None = None
    timeline: list[LensTimelineEvent]
    total_tokens: int
    input_tokens: int
    output_tokens: int
    total_cost_usd: float
    total_tool_calls: int
    failed_tool_calls: int
    message_count: int


# ---------------------------------------------------------------------------
# Token distribution
# ---------------------------------------------------------------------------


class LensModelBreakdown(BaseModel):
    model_name: str | None
    tokens: int
    cost_usd: float
    calls: int


class LensPromptVsCompletion(BaseModel):
    input_tokens: int
    output_tokens: int


class LensTokenDistributionResponse(BaseModel):
    by_model: list[LensModelBreakdown]
    prompt_vs_completion: LensPromptVsCompletion


# ---------------------------------------------------------------------------
# Tool analytics
# ---------------------------------------------------------------------------


class LensToolStat(BaseModel):
    tool_name: str
    total_calls: int
    success_count: int
    failure_count: int
    success_rate: float  # 0.0 – 1.0
    avg_duration_ms: int
    max_duration_ms: int
    total_retries: int


class LensToolAnalyticsResponse(BaseModel):
    tools: list[LensToolStat]
    total_calls: int
    total_failures: int
    overall_success_rate: float


# ---------------------------------------------------------------------------
# Tool ROI
# ---------------------------------------------------------------------------


class LensToolROIStat(BaseModel):
    tool_name: str
    total_calls: int
    calls_per_session: float
    sessions_with: int
    sessions_without: int
    error_rate: float
    avg_cost_with: float
    avg_cost_without: float
    cost_impact_pct: float  # positive = adds cost, negative = saves cost
    avg_llm_calls_with: float
    avg_llm_calls_without: float
    completion_rate_with: float  # 0.0–1.0
    completion_rate_without: float  # 0.0–1.0
    completion_lift: float  # positive = tool helps resolution
    verdict: str  # keep | review | remove | neutral


class LensToolROIResponse(BaseModel):
    tools: list[LensToolROIStat]
    total_sessions: int
    period_start: str
    period_end: str


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


class AlertCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    metric: Literal["failure_rate", "cost_per_session", "avg_latency_ms", "total_cost_usd", "token_count"]
    condition: Literal["gt", "lt"]
    threshold: float
    window_minutes: int = Field(default=60, ge=1, le=10080)
    notify_method: Literal["email", "webhook"] = "email"
    notify_config: dict[str, Any] | None = None
    is_active: bool = True


class AlertUpdateBody(BaseModel):
    name: str | None = None
    metric: Literal["failure_rate", "cost_per_session", "avg_latency_ms", "total_cost_usd", "token_count"] | None = None
    condition: Literal["gt", "lt"] | None = None
    threshold: float | None = None
    window_minutes: int | None = None
    notify_method: Literal["email", "webhook"] | None = None
    notify_config: dict[str, Any] | None = None
    is_active: bool | None = None


class AlertResponse(BaseModel):
    id: str
    agent_id: str
    name: str
    metric: str
    condition: str
    threshold: float
    window_minutes: int
    notify_method: str
    notify_config: dict[str, Any] | None = None
    is_active: bool
    last_triggered_at: str | None = None
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Compaction / pruning analytics
# ---------------------------------------------------------------------------


class LensPruningTrendPoint(BaseModel):
    date: str
    pruning_events: int
    tokens_saved: int
    data_bearing_pruned: int


class LensCompactionAnalyticsResponse(BaseModel):
    total_sessions: int
    sessions_with_pruning: int
    pruning_rate: float  # 0.0–1.0
    pruning_events_count: int
    total_tokens_saved: int
    avg_tokens_saved_per_session: float
    data_bearing_pruned_total: int  # how many data-bearing results were trimmed
    total_results_pruned: int
    total_results_evaluated: int
    avg_pruning_ratio: float  # pruned/evaluated ratio
    trend: list[LensPruningTrendPoint]
    period_start: str
    period_end: str


# ---------------------------------------------------------------------------
# Cache analytics
# ---------------------------------------------------------------------------


class LensCacheTrendPoint(BaseModel):
    date: str
    input_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    cache_hit_rate: float


class LensCacheAnalyticsResponse(BaseModel):
    total_llm_calls: int
    total_input_tokens: int
    total_cache_read_tokens: int
    total_cache_creation_tokens: int
    cache_hit_rate: float  # fraction of calls with any cache reads
    estimated_savings_usd: float
    avg_context_utilization_pct: float
    max_context_utilization_pct: float
    high_pressure_calls: int  # calls with context_utilization_pct >= 80
    trend: list[LensCacheTrendPoint]
    period_start: str
    period_end: str


# ---------------------------------------------------------------------------
# Session graph
# ---------------------------------------------------------------------------


class LensGraphNode(BaseModel):
    id: str
    event_type: str
    label: str
    status: str  # normal | warning | error | info
    metadata: dict[str, Any] | None = None


class LensGraphEdge(BaseModel):
    source: str
    target: str


class LensSessionGraphResponse(BaseModel):
    conversation_id: str
    nodes: list[LensGraphNode]
    edges: list[LensGraphEdge]
