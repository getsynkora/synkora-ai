package synkora

import (
	"io"
	"strings"
	"testing"
)

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

func sseBody(payloads ...string) io.ReadCloser {
	var sb strings.Builder
	for _, p := range payloads {
		sb.WriteString("data: ")
		sb.WriteString(p)
		sb.WriteString("\n\n")
	}
	return io.NopCloser(strings.NewReader(sb.String()))
}

func collectStream(t *testing.T, body io.ReadCloser) ([]StreamEvent, error) {
	t.Helper()
	s := newStream(body)
	defer s.Close()
	var events []StreamEvent
	for s.Next() {
		events = append(events, s.Event())
	}
	return events, s.Err()
}

// ---------------------------------------------------------------------------
// tests
// ---------------------------------------------------------------------------

func TestStreamChunkEvent(t *testing.T) {
	events, err := collectStream(t, sseBody(`{"type":"chunk","content":"Hello"}`))
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 1 {
		t.Fatalf("expected 1 event, got %d", len(events))
	}
	ev, ok := events[0].(*ChunkEvent)
	if !ok {
		t.Fatalf("expected *ChunkEvent, got %T", events[0])
	}
	if ev.Content != "Hello" {
		t.Errorf("content = %q, want %q", ev.Content, "Hello")
	}
}

func TestStreamStartEvent(t *testing.T) {
	events, err := collectStream(t, sseBody(`{"type":"start","agent":"bot","start_time":1234.5}`))
	if err != nil {
		t.Fatal(err)
	}
	ev, ok := events[0].(*StartEvent)
	if !ok {
		t.Fatalf("expected *StartEvent, got %T", events[0])
	}
	if ev.Agent != "bot" {
		t.Errorf("agent = %q, want %q", ev.Agent, "bot")
	}
	if ev.StartTime != 1234.5 {
		t.Errorf("start_time = %v, want 1234.5", ev.StartTime)
	}
}

func TestStreamStatusEvent(t *testing.T) {
	events, err := collectStream(t, sseBody(`{"type":"status","content":"Thinking..."}`))
	if err != nil {
		t.Fatal(err)
	}
	ev, ok := events[0].(*StatusEvent)
	if !ok {
		t.Fatalf("expected *StatusEvent, got %T", events[0])
	}
	if ev.Content != "Thinking..." {
		t.Errorf("content = %q, want %q", ev.Content, "Thinking...")
	}
}

func TestStreamToolStatusEvent(t *testing.T) {
	events, err := collectStream(t, sseBody(
		`{"type":"tool_status","tool_name":"search","status":"done","description":"Searched","duration_ms":120}`,
	))
	if err != nil {
		t.Fatal(err)
	}
	ev, ok := events[0].(*ToolStatusEvent)
	if !ok {
		t.Fatalf("expected *ToolStatusEvent, got %T", events[0])
	}
	if ev.ToolName != "search" {
		t.Errorf("tool_name = %q, want %q", ev.ToolName, "search")
	}
	if ev.DurationMs != 120 {
		t.Errorf("duration_ms = %v, want 120", ev.DurationMs)
	}
}

func TestStreamLLMCallEvent(t *testing.T) {
	events, err := collectStream(t, sseBody(
		`{"type":"llm_call","status":"completed","model":"gpt-4o","input_tokens":50}`,
	))
	if err != nil {
		t.Fatal(err)
	}
	ev, ok := events[0].(*LLMCallEvent)
	if !ok {
		t.Fatalf("expected *LLMCallEvent, got %T", events[0])
	}
	if ev.Model != "gpt-4o" {
		t.Errorf("model = %q, want %q", ev.Model, "gpt-4o")
	}
	if ev.InputTokens != 50 {
		t.Errorf("input_tokens = %d, want 50", ev.InputTokens)
	}
}

func TestStreamFirstTokenEvent(t *testing.T) {
	events, err := collectStream(t, sseBody(`{"type":"first_token","time_to_first_token":0.42}`))
	if err != nil {
		t.Fatal(err)
	}
	ev, ok := events[0].(*FirstTokenEvent)
	if !ok {
		t.Fatalf("expected *FirstTokenEvent, got %T", events[0])
	}
	if ev.TimeToFirstToken != 0.42 {
		t.Errorf("time_to_first_token = %v, want 0.42", ev.TimeToFirstToken)
	}
}

func TestStreamDoneEvent(t *testing.T) {
	events, err := collectStream(t, sseBody(
		`{"type":"done","metadata":{"generated_by_ai":true},"sources":[]}`,
	))
	if err != nil {
		t.Fatal(err)
	}
	ev, ok := events[0].(*DoneEvent)
	if !ok {
		t.Fatalf("expected *DoneEvent, got %T", events[0])
	}
	if ev.Metadata["generated_by_ai"] != true {
		t.Errorf("metadata generated_by_ai = %v, want true", ev.Metadata["generated_by_ai"])
	}
	if len(ev.Sources) != 0 {
		t.Errorf("sources len = %d, want 0", len(ev.Sources))
	}
}

func TestStreamDoneEventWithSources(t *testing.T) {
	events, err := collectStream(t, sseBody(
		`{"type":"done","metadata":{},"sources":[{"title":"Doc 1"}]}`,
	))
	if err != nil {
		t.Fatal(err)
	}
	ev := events[0].(*DoneEvent)
	if len(ev.Sources) != 1 {
		t.Fatalf("sources len = %d, want 1", len(ev.Sources))
	}
	if ev.Sources[0]["title"] != "Doc 1" {
		t.Errorf("source title = %v, want Doc 1", ev.Sources[0]["title"])
	}
}

func TestStreamErrorEventReturnsStreamError(t *testing.T) {
	body := sseBody(`{"type":"error","error":"Policy violation","error_type":"policy"}`)
	s := newStream(body)
	defer s.Close()
	for s.Next() {
	}
	err := s.Err()
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	se, ok := err.(*StreamError)
	if !ok {
		t.Fatalf("expected *StreamError, got %T: %v", err, err)
	}
	if se.ErrorType != "policy" {
		t.Errorf("error_type = %q, want %q", se.ErrorType, "policy")
	}
}

func TestStreamCompactionEvent(t *testing.T) {
	events, err := collectStream(t, sseBody(
		`{"type":"compaction","pruned_count":5,"tokens_saved":300}`,
	))
	if err != nil {
		t.Fatal(err)
	}
	ev, ok := events[0].(*CompactionEvent)
	if !ok {
		t.Fatalf("expected *CompactionEvent, got %T", events[0])
	}
	if ev.PrunedCount != 5 {
		t.Errorf("pruned_count = %d, want 5", ev.PrunedCount)
	}
	if ev.TokensSaved != 300 {
		t.Errorf("tokens_saved = %d, want 300", ev.TokensSaved)
	}
}

func TestStreamSatisfactionPromptEvent(t *testing.T) {
	events, err := collectStream(t, sseBody(
		`{"type":"satisfaction_prompt","conversation_id":"abc-123"}`,
	))
	if err != nil {
		t.Fatal(err)
	}
	ev, ok := events[0].(*SatisfactionPromptEvent)
	if !ok {
		t.Fatalf("expected *SatisfactionPromptEvent, got %T", events[0])
	}
	if ev.ConversationID != "abc-123" {
		t.Errorf("conversation_id = %q, want %q", ev.ConversationID, "abc-123")
	}
}

func TestStreamUnknownEventTypeIgnored(t *testing.T) {
	events, err := collectStream(t, sseBody(`{"type":"future_type","data":"x"}`))
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 0 {
		t.Errorf("expected 0 events, got %d", len(events))
	}
}

func TestStreamNonDataLinesIgnored(t *testing.T) {
	body := io.NopCloser(strings.NewReader(
		"event: message\n\ndata: {\"type\":\"chunk\",\"content\":\"Hi\"}\n\n",
	))
	events, err := collectStream(t, body)
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 1 {
		t.Fatalf("expected 1 event, got %d", len(events))
	}
}

func TestStreamMalformedJSONSkipped(t *testing.T) {
	events, err := collectStream(t, sseBody(
		"not json",
		`{"type":"chunk","content":"ok"}`,
	))
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 1 {
		t.Fatalf("expected 1 event, got %d", len(events))
	}
}

func TestStreamDONESentinelSkipped(t *testing.T) {
	events, err := collectStream(t, sseBody("[DONE]"))
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 0 {
		t.Errorf("expected 0 events, got %d", len(events))
	}
}

func TestStreamMultipleEventsInOrder(t *testing.T) {
	events, err := collectStream(t, sseBody(
		`{"type":"chunk","content":"Hello"}`,
		`{"type":"chunk","content":" world"}`,
		`{"type":"done","metadata":{},"sources":[]}`,
	))
	if err != nil {
		t.Fatal(err)
	}
	if len(events) != 3 {
		t.Fatalf("expected 3 events, got %d", len(events))
	}
	if events[0].(*ChunkEvent).Content != "Hello" {
		t.Errorf("first chunk = %q, want %q", events[0].(*ChunkEvent).Content, "Hello")
	}
	if events[1].(*ChunkEvent).Content != " world" {
		t.Errorf("second chunk = %q, want %q", events[1].(*ChunkEvent).Content, " world")
	}
	if _, ok := events[2].(*DoneEvent); !ok {
		t.Errorf("last event type = %T, want *DoneEvent", events[2])
	}
}
