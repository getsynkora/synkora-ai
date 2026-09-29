"""Typed data models for the Synkora SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# SSE streaming events
# ---------------------------------------------------------------------------


@dataclass
class StartEvent:
    """Emitted at the beginning of a stream."""

    agent: str
    start_time: float
    type: str = "start"


@dataclass
class ChunkEvent:
    """A content chunk from the LLM — the main text output."""

    content: str
    type: str = "chunk"


@dataclass
class StatusEvent:
    """A human-readable status/thinking message (not final output)."""

    content: str
    type: str = "status"


@dataclass
class ToolStatusEvent:
    """Status update from a tool invocation."""

    tool_name: str
    status: str  # "running" | "done" | "error"
    description: str
    details: str | None = None
    duration_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    type: str = "tool_status"


@dataclass
class LLMCallEvent:
    """Notification that an LLM call started or completed."""

    status: str  # "started" | "completed"
    model: str | None = None
    call_index: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    type: str = "llm_call"


@dataclass
class FirstTokenEvent:
    """Emitted when the first token is received from the LLM."""

    time_to_first_token: float
    type: str = "first_token"


@dataclass
class DoneEvent:
    """Final event in a stream — contains metadata and optional sources."""

    metadata: dict[str, Any]
    sources: list[dict[str, Any]] = field(default_factory=list)
    type: str = "done"


@dataclass
class CompactionEvent:
    """Emitted when conversation history is pruned to save tokens."""

    pruned_count: int | None = None
    tokens_saved: int | None = None
    type: str = "compaction"


@dataclass
class SatisfactionPromptEvent:
    """Emitted to solicit user satisfaction feedback."""

    conversation_id: str
    type: str = "satisfaction_prompt"


# Union of all possible stream events
StreamEvent = (
    StartEvent
    | ChunkEvent
    | StatusEvent
    | ToolStatusEvent
    | LLMCallEvent
    | FirstTokenEvent
    | DoneEvent
    | CompactionEvent
    | SatisfactionPromptEvent
)


# ---------------------------------------------------------------------------
# REST response models
# ---------------------------------------------------------------------------


@dataclass
class AgentInfo:
    """Summary of a Synkora agent from the public API."""

    id: str
    name: str
    description: str | None = None
    model: str | None = None
    capabilities: list[str] = field(default_factory=list)


@dataclass
class ConversationInfo:
    """Metadata for a stored conversation."""

    id: str
    agent_id: str
    created_at: str
    updated_at: str
    message_count: int


@dataclass
class ChatResponse:
    """Non-streaming chat response (aggregated from stream)."""

    conversation_id: str
    message: str
    tokens_used: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
