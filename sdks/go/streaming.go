package synkora

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"strings"
)

// rawEvent is used solely for unmarshalling the "type" discriminator.
type rawEvent struct {
	Type string `json:"type"`

	// start
	Agent     string  `json:"agent"`
	StartTime float64 `json:"start_time"`

	// chunk / status
	Content string `json:"content"`

	// tool_status
	ToolName     string  `json:"tool_name"`
	Status       string  `json:"status"`
	Description  string  `json:"description"`
	Details      string  `json:"details"`
	DurationMs   float64 `json:"duration_ms"`
	InputTokens  int     `json:"input_tokens"`
	OutputTokens int     `json:"output_tokens"`

	// llm_call
	Model     string `json:"model"`
	CallIndex int    `json:"call_index"`

	// first_token
	TimeToFirstToken float64 `json:"time_to_first_token"`

	// done
	Metadata map[string]any   `json:"metadata"`
	Sources  []map[string]any `json:"sources"`

	// error
	Error       string `json:"error"`
	ErrorType   string `json:"error_type"`
	ViolationID string `json:"violation_id"`

	// compaction
	PrunedCount int `json:"pruned_count"`
	TokensSaved int `json:"tokens_saved"`

	// satisfaction_prompt
	ConversationID string `json:"conversation_id"`
}

func parseRaw(r rawEvent) (StreamEvent, error) {
	switch r.Type {
	case "start":
		return &StartEvent{Agent: r.Agent, StartTime: r.StartTime}, nil

	case "chunk":
		return &ChunkEvent{Content: r.Content}, nil

	case "status":
		return &StatusEvent{Content: r.Content}, nil

	case "tool_status":
		return &ToolStatusEvent{
			ToolName:     r.ToolName,
			Status:       r.Status,
			Description:  r.Description,
			Details:      r.Details,
			DurationMs:   r.DurationMs,
			InputTokens:  r.InputTokens,
			OutputTokens: r.OutputTokens,
		}, nil

	case "llm_call":
		return &LLMCallEvent{
			Status:       r.Status,
			Model:        r.Model,
			CallIndex:    r.CallIndex,
			InputTokens:  r.InputTokens,
			OutputTokens: r.OutputTokens,
		}, nil

	case "first_token":
		return &FirstTokenEvent{TimeToFirstToken: r.TimeToFirstToken}, nil

	case "done":
		sources := r.Sources
		if sources == nil {
			sources = []map[string]any{}
		}
		meta := r.Metadata
		if meta == nil {
			meta = map[string]any{}
		}
		return &DoneEvent{Metadata: meta, Sources: sources}, nil

	case "error":
		msg := r.Error
		if msg == "" {
			msg = "unknown stream error"
		}
		return nil, errStream(msg, r.ErrorType, r.ViolationID)

	case "compaction":
		return &CompactionEvent{PrunedCount: r.PrunedCount, TokensSaved: r.TokensSaved}, nil

	case "satisfaction_prompt":
		return &SatisfactionPromptEvent{ConversationID: r.ConversationID}, nil

	default:
		// Unknown / future event type — caller should skip nil results.
		return nil, nil
	}
}

// ---------------------------------------------------------------------------
// Stream — scanner-based SSE reader following the sql.Rows / bufio.Scanner
// pattern: call Next() in a loop, read Event(), check Err() after the loop.
// ---------------------------------------------------------------------------

// Stream reads typed events from an SSE response body.
// Always call Close() when done, even if Next() returned false.
type Stream struct {
	body    io.ReadCloser
	scanner *bufio.Scanner
	current StreamEvent
	err     error
}

func newStream(body io.ReadCloser) *Stream {
	return &Stream{
		body:    body,
		scanner: bufio.NewScanner(body),
	}
}

// Next advances to the next event. Returns false when the stream ends or an
// error occurs. Check Err() after a false return.
func (s *Stream) Next() bool {
	for s.scanner.Scan() {
		line := s.scanner.Text()
		if !strings.HasPrefix(line, "data:") {
			continue
		}
		payload := strings.TrimSpace(line[len("data:"):])
		if payload == "" || payload == "[DONE]" {
			continue
		}

		var r rawEvent
		if err := json.Unmarshal([]byte(payload), &r); err != nil {
			// skip malformed lines
			continue
		}

		ev, err := parseRaw(r)
		if err != nil {
			// error event in the stream
			s.err = err
			return false
		}
		if ev == nil {
			// unknown / future event type — skip
			continue
		}

		s.current = ev
		return true
	}

	if err := s.scanner.Err(); err != nil {
		s.err = fmt.Errorf("synkora: reading stream: %w", err)
	}
	return false
}

// Event returns the most recently parsed event.
// Only valid after a successful call to Next().
func (s *Stream) Event() StreamEvent { return s.current }

// Err returns any error encountered during streaming.
// Call after Next() returns false.
func (s *Stream) Err() error { return s.err }

// Close releases the underlying HTTP response body.
func (s *Stream) Close() error { return s.body.Close() }
