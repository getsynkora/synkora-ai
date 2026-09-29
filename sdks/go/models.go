package synkora

// ---------------------------------------------------------------------------
// SSE stream events
//
// Users type-switch on StreamEvent:
//
//	switch ev := stream.Event().(type) {
//	case *ChunkEvent:
//	    fmt.Print(ev.Content)
//	case *DoneEvent:
//	    fmt.Println(ev.Metadata)
//	}
// ---------------------------------------------------------------------------

// StreamEvent is implemented by all typed SSE events.
type StreamEvent interface {
	eventType() string
}

// StartEvent is emitted at the beginning of a stream.
type StartEvent struct {
	Agent     string
	StartTime float64
}

func (*StartEvent) eventType() string { return "start" }

// ChunkEvent carries a content chunk from the LLM — the main text output.
type ChunkEvent struct {
	Content string
}

func (*ChunkEvent) eventType() string { return "chunk" }

// StatusEvent carries a human-readable status/thinking message.
type StatusEvent struct {
	Content string
}

func (*StatusEvent) eventType() string { return "status" }

// ToolStatusEvent reports the status of a tool invocation.
type ToolStatusEvent struct {
	ToolName    string
	Status      string // "running" | "done" | "error"
	Description string
	Details     string  // optional
	DurationMs  float64 // 0 when not present
	InputTokens int
	OutputTokens int
}

func (*ToolStatusEvent) eventType() string { return "tool_status" }

// LLMCallEvent is emitted when an LLM call starts or completes.
type LLMCallEvent struct {
	Status       string // "started" | "completed"
	Model        string
	CallIndex    int
	InputTokens  int
	OutputTokens int
}

func (*LLMCallEvent) eventType() string { return "llm_call" }

// FirstTokenEvent is emitted when the first token is received.
type FirstTokenEvent struct {
	TimeToFirstToken float64
}

func (*FirstTokenEvent) eventType() string { return "first_token" }

// DoneEvent is the final event in a stream.
type DoneEvent struct {
	Metadata map[string]any
	Sources  []map[string]any
}

func (*DoneEvent) eventType() string { return "done" }

// CompactionEvent is emitted when conversation history is pruned.
type CompactionEvent struct {
	PrunedCount int
	TokensSaved int
}

func (*CompactionEvent) eventType() string { return "compaction" }

// SatisfactionPromptEvent is emitted to request user feedback.
type SatisfactionPromptEvent struct {
	ConversationID string
}

func (*SatisfactionPromptEvent) eventType() string { return "satisfaction_prompt" }

// ---------------------------------------------------------------------------
// REST response types
// ---------------------------------------------------------------------------

// AgentInfo holds metadata for a Synkora agent.
type AgentInfo struct {
	ID           string
	Name         string
	Description  string
	Model        string
	Capabilities []string
}

// ConversationInfo holds metadata for a stored conversation.
type ConversationInfo struct {
	ID           string
	AgentID      string
	CreatedAt    string
	UpdatedAt    string
	MessageCount int
}

// ChatResponse is the aggregated result of a completed chat exchange.
type ChatResponse struct {
	ConversationID string
	Message        string
	TokensUsed     int // 0 when not reported
	Metadata       map[string]any
	Sources        []map[string]any
}
