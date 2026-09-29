"""SSE stream parsing for the Synkora API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any

from .exceptions import StreamError
from .models import (
    ChunkEvent,
    CompactionEvent,
    DoneEvent,
    FirstTokenEvent,
    LLMCallEvent,
    SatisfactionPromptEvent,
    StartEvent,
    StatusEvent,
    StreamEvent,
    ToolStatusEvent,
)


def _parse_event(data: dict[str, Any]) -> StreamEvent | None:
    """Convert a raw SSE data dict into a typed event. Returns None for unknown types."""
    t = data.get("type")

    if t == "start":
        return StartEvent(agent=data.get("agent", ""), start_time=data.get("start_time", 0.0))

    if t == "chunk":
        return ChunkEvent(content=data.get("content", ""))

    if t == "status":
        return StatusEvent(content=data.get("content", ""))

    if t == "tool_status":
        return ToolStatusEvent(
            tool_name=data.get("tool_name", ""),
            status=data.get("status", ""),
            description=data.get("description", ""),
            details=data.get("details"),
            duration_ms=data.get("duration_ms"),
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
        )

    if t == "llm_call":
        return LLMCallEvent(
            status=data.get("status", ""),
            model=data.get("model"),
            call_index=data.get("call_index"),
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
        )

    if t == "first_token":
        return FirstTokenEvent(time_to_first_token=data.get("time_to_first_token", 0.0))

    if t == "done":
        return DoneEvent(
            metadata=data.get("metadata", {}),
            sources=data.get("sources") or [],
        )

    if t == "error":
        raise StreamError(
            message=data.get("error", "Unknown error"),
            error_type=data.get("error_type"),
            violation_id=data.get("violation_id"),
        )

    if t == "compaction":
        return CompactionEvent(
            pruned_count=data.get("pruned_count"),
            tokens_saved=data.get("tokens_saved"),
        )

    if t == "satisfaction_prompt":
        return SatisfactionPromptEvent(conversation_id=data.get("conversation_id", ""))

    return None  # unknown / future event type — silently ignore


def _iter_sse_lines(lines: Iterator[str]) -> Iterator[StreamEvent]:
    """Parse raw SSE lines into typed events."""
    for line in lines:
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        event = _parse_event(data)
        if event is not None:
            yield event


async def _aiter_sse_lines(lines: AsyncIterator[str]) -> AsyncIterator[StreamEvent]:
    """Async version of _iter_sse_lines."""
    async for line in lines:
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        event = _parse_event(data)
        if event is not None:
            yield event
