"""Tests for SSE stream parsing."""

import pytest

from synkora.exceptions import StreamError
from synkora.models import (
    ChunkEvent,
    CompactionEvent,
    DoneEvent,
    FirstTokenEvent,
    LLMCallEvent,
    SatisfactionPromptEvent,
    StartEvent,
    StatusEvent,
    ToolStatusEvent,
)
from synkora.streaming import _iter_sse_lines


def sse(*payloads: str) -> list[str]:
    """Build SSE lines from JSON payloads."""
    return [f"data: {p}" for p in payloads]


def collect(lines: list[str]) -> list[object]:
    return list(_iter_sse_lines(iter(lines)))


class TestIterSseLines:
    def test_chunk_event(self):
        events = collect(sse('{"type":"chunk","content":"Hello"}'))
        assert len(events) == 1
        assert isinstance(events[0], ChunkEvent)
        assert events[0].content == "Hello"

    def test_start_event(self):
        events = collect(sse('{"type":"start","agent":"my-agent","start_time":1234.5}'))
        assert isinstance(events[0], StartEvent)
        assert events[0].agent == "my-agent"
        assert events[0].start_time == 1234.5

    def test_status_event(self):
        events = collect(sse('{"type":"status","content":"Thinking..."}'))
        assert isinstance(events[0], StatusEvent)
        assert events[0].content == "Thinking..."

    def test_tool_status_event(self):
        events = collect(
            sse('{"type":"tool_status","tool_name":"search","status":"done","description":"Searched","duration_ms":120}')
        )
        ev = events[0]
        assert isinstance(ev, ToolStatusEvent)
        assert ev.tool_name == "search"
        assert ev.status == "done"
        assert ev.duration_ms == 120

    def test_llm_call_event(self):
        events = collect(
            sse('{"type":"llm_call","status":"completed","model":"gpt-4o","input_tokens":50,"output_tokens":20}')
        )
        ev = events[0]
        assert isinstance(ev, LLMCallEvent)
        assert ev.status == "completed"
        assert ev.model == "gpt-4o"
        assert ev.input_tokens == 50

    def test_first_token_event(self):
        events = collect(sse('{"type":"first_token","time_to_first_token":0.42}'))
        ev = events[0]
        assert isinstance(ev, FirstTokenEvent)
        assert ev.time_to_first_token == 0.42

    def test_done_event(self):
        events = collect(
            sse('{"type":"done","metadata":{"generated_by_ai":true},"sources":[]}')
        )
        ev = events[0]
        assert isinstance(ev, DoneEvent)
        assert ev.metadata == {"generated_by_ai": True}
        assert ev.sources == []

    def test_done_event_with_sources(self):
        events = collect(
            sse('{"type":"done","metadata":{},"sources":[{"title":"Doc 1","url":"http://x"}]}')
        )
        ev = events[0]
        assert isinstance(ev, DoneEvent)
        assert len(ev.sources) == 1
        assert ev.sources[0]["title"] == "Doc 1"

    def test_compaction_event(self):
        events = collect(sse('{"type":"compaction","pruned_count":5,"tokens_saved":300}'))
        ev = events[0]
        assert isinstance(ev, CompactionEvent)
        assert ev.pruned_count == 5
        assert ev.tokens_saved == 300

    def test_satisfaction_prompt_event(self):
        events = collect(sse('{"type":"satisfaction_prompt","conversation_id":"abc-123"}'))
        ev = events[0]
        assert isinstance(ev, SatisfactionPromptEvent)
        assert ev.conversation_id == "abc-123"

    def test_error_event_raises(self):
        with pytest.raises(StreamError) as exc_info:
            collect(sse('{"type":"error","error":"Tool failed","error_type":"tool_error"}'))
        assert "Tool failed" in str(exc_info.value)
        assert exc_info.value.error_type == "tool_error"

    def test_unknown_event_type_ignored(self):
        events = collect(sse('{"type":"future_event","data":"x"}'))
        assert events == []

    def test_non_data_lines_ignored(self):
        lines = ["event: message", "", 'data: {"type":"chunk","content":"Hi"}', ""]
        events = collect(lines)
        assert len(events) == 1
        assert isinstance(events[0], ChunkEvent)

    def test_malformed_json_skipped(self):
        lines = [
            "data: not json",
            'data: {"type":"chunk","content":"ok"}',
        ]
        events = collect(lines)
        assert len(events) == 1
        assert isinstance(events[0], ChunkEvent)

    def test_done_sentinel_skipped(self):
        events = collect(["data: [DONE]"])
        assert events == []

    def test_multiple_chunks_in_order(self):
        lines = sse(
            '{"type":"chunk","content":"Hello"}',
            '{"type":"chunk","content":" world"}',
            '{"type":"done","metadata":{}}',
        )
        events = collect(lines)
        assert len(events) == 3
        assert events[0].content == "Hello"  # type: ignore[attr-defined]
        assert events[1].content == " world"  # type: ignore[attr-defined]
        assert isinstance(events[2], DoneEvent)
