package synkora

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// ---------------------------------------------------------------------------
// Test server helpers
// ---------------------------------------------------------------------------

func jsonHandler(status int, body any) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_ = json.NewEncoder(w).Encode(body)
	}
}

func sseHandler(events ...string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		for _, e := range events {
			_, _ = io.WriteString(w, "data: "+e+"\n\n")
		}
	}
}

func newTestClient(t *testing.T, mux *http.ServeMux) (*Client, *httptest.Server) {
	t.Helper()
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	client, err := New(
		WithAPIKey("sk-test"),
		WithBaseURL(srv.URL),
		WithHTTPClient(srv.Client()),
	)
	if err != nil {
		t.Fatal(err)
	}
	return client, srv
}

// ---------------------------------------------------------------------------
// Constructor tests
// ---------------------------------------------------------------------------

func TestNewRequiresAPIKey(t *testing.T) {
	t.Setenv("SYNKORA_API_KEY", "")
	_, err := New()
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if _, ok := err.(*AuthError); !ok {
		t.Errorf("expected *AuthError, got %T", err)
	}
}

func TestNewAcceptsAPIKeyOption(t *testing.T) {
	_, err := New(WithAPIKey("sk-test"))
	if err != nil {
		t.Fatal(err)
	}
}

func TestNewReadsAPIKeyFromEnv(t *testing.T) {
	t.Setenv("SYNKORA_API_KEY", "sk-env")
	_, err := New()
	if err != nil {
		t.Fatal(err)
	}
}

func TestNewReadsBaseURLFromEnv(t *testing.T) {
	t.Setenv("SYNKORA_BASE_URL", "https://custom.example.com")
	client, err := New(WithAPIKey("sk-test"))
	if err != nil {
		t.Fatal(err)
	}
	if client.baseURL != "https://custom.example.com" {
		t.Errorf("baseURL = %q, want %q", client.baseURL, "https://custom.example.com")
	}
}

// ---------------------------------------------------------------------------
// ListAgents
// ---------------------------------------------------------------------------

func TestListAgentsReturnsAgents(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v1/public/agents", jsonHandler(200, []map[string]any{
		{"id": "a1", "name": "Agent One", "capabilities": []string{"chat"}},
	}))
	client, _ := newTestClient(t, mux)

	agents, err := client.ListAgents(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(agents) != 1 {
		t.Fatalf("expected 1 agent, got %d", len(agents))
	}
	if agents[0].Name != "Agent One" {
		t.Errorf("name = %q, want %q", agents[0].Name, "Agent One")
	}
}

func TestListAgentsRaises401AsAuthError(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v1/public/agents", jsonHandler(401, map[string]string{"detail": "Unauthorized"}))
	client, _ := newTestClient(t, mux)

	_, err := client.ListAgents(context.Background())
	if _, ok := err.(*AuthError); !ok {
		t.Errorf("expected *AuthError, got %T: %v", err, err)
	}
}

func TestListAgentsRaises429AsRateLimitError(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v1/public/agents", jsonHandler(429, map[string]string{"detail": "Too many requests"}))
	client, _ := newTestClient(t, mux)

	_, err := client.ListAgents(context.Background())
	if _, ok := err.(*RateLimitError); !ok {
		t.Errorf("expected *RateLimitError, got %T: %v", err, err)
	}
}

// ---------------------------------------------------------------------------
// GetAgent
// ---------------------------------------------------------------------------

func TestGetAgentReturnsAgent(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v1/public/agents/uuid-1", jsonHandler(200, map[string]any{
		"id": "uuid-1", "name": "My Agent", "model": "gpt-4o", "capabilities": []string{},
	}))
	client, _ := newTestClient(t, mux)

	agent, err := client.GetAgent(context.Background(), "uuid-1")
	if err != nil {
		t.Fatal(err)
	}
	if agent.Model != "gpt-4o" {
		t.Errorf("model = %q, want %q", agent.Model, "gpt-4o")
	}
}

func TestGetAgentRaises404AsAgentNotFoundError(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/v1/public/agents/missing", jsonHandler(404, map[string]string{"detail": "Not found"}))
	client, _ := newTestClient(t, mux)

	_, err := client.GetAgent(context.Background(), "missing")
	if _, ok := err.(*AgentNotFoundError); !ok {
		t.Errorf("expected *AgentNotFoundError, got %T: %v", err, err)
	}
}

// ---------------------------------------------------------------------------
// ChatStream
// ---------------------------------------------------------------------------

func TestChatStreamYieldsEvents(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/public/agents/agent-1/chat/stream", sseHandler(
		`{"type":"chunk","content":"Hello"}`,
		`{"type":"chunk","content":" world"}`,
		`{"type":"done","metadata":{},"sources":[]}`,
	))
	client, _ := newTestClient(t, mux)

	stream, err := client.ChatStream(context.Background(), "agent-1", "Hi", nil)
	if err != nil {
		t.Fatal(err)
	}
	defer stream.Close()

	var chunks []string
	for stream.Next() {
		if ev, ok := stream.Event().(*ChunkEvent); ok {
			chunks = append(chunks, ev.Content)
		}
	}
	if err := stream.Err(); err != nil {
		t.Fatal(err)
	}
	if len(chunks) != 2 {
		t.Fatalf("expected 2 chunks, got %d", len(chunks))
	}
	if chunks[0] != "Hello" || chunks[1] != " world" {
		t.Errorf("chunks = %v, want [Hello  world]", chunks)
	}
}

func TestChatStreamErrorEventReturnsStreamError(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/public/agents/agent-1/chat/stream", sseHandler(
		`{"type":"error","error":"Policy violation","error_type":"policy"}`,
	))
	client, _ := newTestClient(t, mux)

	stream, err := client.ChatStream(context.Background(), "agent-1", "bad", nil)
	if err != nil {
		t.Fatal(err)
	}
	defer stream.Close()
	for stream.Next() {
	}
	if _, ok := stream.Err().(*StreamError); !ok {
		t.Errorf("expected *StreamError, got %T: %v", stream.Err(), stream.Err())
	}
}

func TestChatStreamSendsConversationID(t *testing.T) {
	var gotBody map[string]any
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/public/agents/agent-1/chat/stream", func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewDecoder(r.Body).Decode(&gotBody)
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = io.WriteString(w, "data: {\"type\":\"done\",\"metadata\":{},\"sources\":[]}\n\n")
	})
	client, _ := newTestClient(t, mux)

	stream, err := client.ChatStream(context.Background(), "agent-1", "Hi", &ChatOptions{
		ConversationID: "conv-99",
	})
	if err != nil {
		t.Fatal(err)
	}
	defer stream.Close()
	for stream.Next() {
	}

	if gotBody["conversation_id"] != "conv-99" {
		t.Errorf("conversation_id = %v, want conv-99", gotBody["conversation_id"])
	}
}

func TestChatStreamSendsBearerToken(t *testing.T) {
	var gotAuth string
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/public/agents/agent-1/chat/stream", func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = io.WriteString(w, "data: {\"type\":\"done\",\"metadata\":{},\"sources\":[]}\n\n")
	})
	client, _ := newTestClient(t, mux)

	stream, err := client.ChatStream(context.Background(), "agent-1", "Hi", nil)
	if err != nil {
		t.Fatal(err)
	}
	defer stream.Close()
	for stream.Next() {
	}

	if !strings.HasPrefix(gotAuth, "Bearer ") {
		t.Errorf("Authorization = %q, want Bearer ...", gotAuth)
	}
}

// ---------------------------------------------------------------------------
// Chat (non-streaming)
// ---------------------------------------------------------------------------

func TestChatAggregatesChunks(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/public/agents/agent-1/chat/stream", sseHandler(
		`{"type":"chunk","content":"Hello"}`,
		`{"type":"chunk","content":" world"}`,
		`{"type":"done","metadata":{"total_tokens":10},"sources":[]}`,
	))
	client, _ := newTestClient(t, mux)

	resp, err := client.Chat(context.Background(), "agent-1", "Hi", nil)
	if err != nil {
		t.Fatal(err)
	}
	if resp.Message != "Hello world" {
		t.Errorf("message = %q, want %q", resp.Message, "Hello world")
	}
	if resp.TokensUsed != 10 {
		t.Errorf("tokens_used = %d, want 10", resp.TokensUsed)
	}
}

func TestChatIncludesSources(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/v1/public/agents/agent-1/chat/stream", sseHandler(
		`{"type":"done","metadata":{},"sources":[{"title":"Doc 1"}]}`,
	))
	client, _ := newTestClient(t, mux)

	resp, err := client.Chat(context.Background(), "agent-1", "Hi", nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(resp.Sources) != 1 {
		t.Fatalf("sources len = %d, want 1", len(resp.Sources))
	}
	if resp.Sources[0]["title"] != "Doc 1" {
		t.Errorf("source title = %v, want Doc 1", resp.Sources[0]["title"])
	}
}

// ---------------------------------------------------------------------------
// DeleteConversation
// ---------------------------------------------------------------------------

func TestDeleteConversationCallsDeleteEndpoint(t *testing.T) {
	var method string
	mux := http.NewServeMux()
	mux.HandleFunc("/api/v1/public/agents/agent-1/conversations/conv-1", func(w http.ResponseWriter, r *http.Request) {
		method = r.Method
		w.WriteHeader(http.StatusNoContent)
	})
	client, _ := newTestClient(t, mux)

	err := client.DeleteConversation(context.Background(), "agent-1", "conv-1")
	if err != nil {
		t.Fatal(err)
	}
	if method != http.MethodDelete {
		t.Errorf("method = %q, want DELETE", method)
	}
}
