// Package synkora provides a Go client for the Synkora AI agent platform.
//
// Usage:
//
//	client, err := synkora.New(synkora.WithAPIKey("sk-..."))
//	if err != nil {
//	    log.Fatal(err)
//	}
//
//	// Non-streaming
//	resp, err := client.Chat(ctx, agentID, "Hello", nil)
//	fmt.Println(resp.Message)
//
//	// Streaming
//	stream, err := client.ChatStream(ctx, agentID, "Hello", nil)
//	if err != nil { log.Fatal(err) }
//	defer stream.Close()
//	for stream.Next() {
//	    switch ev := stream.Event().(type) {
//	    case *synkora.ChunkEvent:
//	        fmt.Print(ev.Content)
//	    case *synkora.DoneEvent:
//	        fmt.Println()
//	    }
//	}
//	if err := stream.Err(); err != nil { log.Fatal(err) }
package synkora

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	defaultBaseURL = "https://app.synkora.com"
	defaultTimeout = 120 * time.Second
	sdkVersion     = "0.1.0"
)

// ---------------------------------------------------------------------------
// Client options (functional options pattern)
// ---------------------------------------------------------------------------

type clientConfig struct {
	apiKey     string
	baseURL    string
	timeout    time.Duration
	httpClient *http.Client
}

// ClientOption configures a Client.
type ClientOption func(*clientConfig)

// WithAPIKey sets the API key. If not set, SYNKORA_API_KEY env var is used.
func WithAPIKey(key string) ClientOption {
	return func(c *clientConfig) { c.apiKey = key }
}

// WithBaseURL overrides the API base URL.
// If not set, SYNKORA_BASE_URL env var is used, falling back to https://app.synkora.com.
func WithBaseURL(url string) ClientOption {
	return func(c *clientConfig) { c.baseURL = url }
}

// WithTimeout sets the HTTP request timeout. Default: 120 seconds.
func WithTimeout(d time.Duration) ClientOption {
	return func(c *clientConfig) { c.timeout = d }
}

// WithHTTPClient replaces the underlying *http.Client. Useful for proxies or testing.
func WithHTTPClient(h *http.Client) ClientOption {
	return func(c *clientConfig) { c.httpClient = h }
}

// ---------------------------------------------------------------------------
// Chat options
// ---------------------------------------------------------------------------

// ChatOptions configures a single chat request.
type ChatOptions struct {
	// ConversationID continues an existing conversation.
	ConversationID string
	// Metadata is arbitrary key-value data passed to the agent.
	Metadata map[string]any
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

// Client is the Synkora API client. Create one with New() and reuse it.
type Client struct {
	baseURL    string
	httpClient *http.Client
	headers    map[string]string
}

// New creates a new Client. Returns an error if no API key is available.
func New(opts ...ClientOption) (*Client, error) {
	cfg := &clientConfig{
		baseURL: defaultBaseURL,
		timeout: defaultTimeout,
	}
	for _, o := range opts {
		o(cfg)
	}

	// Resolve API key: option → env var
	if cfg.apiKey == "" {
		cfg.apiKey = os.Getenv("SYNKORA_API_KEY")
	}
	if cfg.apiKey == "" {
		return nil, &AuthError{SynkoraError{
			Message: "no API key provided; pass WithAPIKey() or set SYNKORA_API_KEY",
		}}
	}

	// Resolve base URL: option → env var → default
	if cfg.baseURL == defaultBaseURL {
		if v := os.Getenv("SYNKORA_BASE_URL"); v != "" {
			cfg.baseURL = v
		}
	}
	baseURL := strings.TrimRight(cfg.baseURL, "/")

	httpClient := cfg.httpClient
	if httpClient == nil {
		httpClient = &http.Client{Timeout: cfg.timeout}
	}

	return &Client{
		baseURL:    baseURL,
		httpClient: httpClient,
		headers: map[string]string{
			"Authorization": "Bearer " + cfg.apiKey,
			"Content-Type":  "application/json",
			"Accept":        "application/json",
			"User-Agent":    "synkora-go/" + sdkVersion,
		},
	}, nil
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

func (c *Client) do(ctx context.Context, method, path string, body any) (*http.Response, error) {
	var bodyReader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("synkora: marshal request: %w", err)
		}
		bodyReader = bytes.NewReader(b)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("synkora: build request: %w", err)
	}
	for k, v := range c.headers {
		req.Header.Set(k, v)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("synkora: HTTP request: %w", err)
	}
	return resp, nil
}

func checkStatus(resp *http.Response) error {
	if resp.StatusCode < 400 {
		return nil
	}

	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	detail := string(raw)
	// Try to extract {"detail": "..."} from JSON bodies
	var payload struct {
		Detail string `json:"detail"`
	}
	if json.Unmarshal(raw, &payload) == nil && payload.Detail != "" {
		detail = payload.Detail
	}

	code := resp.StatusCode
	switch {
	case code == 401 || code == 403:
		return errAuth(detail, code)
	case code == 404:
		return errNotFound(detail, code)
	case code == 429:
		return errRateLimit(detail, code)
	case code >= 500:
		return errAPI("server error: "+strconv.Itoa(code), code)
	default:
		return &SynkoraError{Message: detail, StatusCode: code}
	}
}

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

// ListAgents returns all agents accessible with this API key.
func (c *Client) ListAgents(ctx context.Context) ([]*AgentInfo, error) {
	resp, err := c.do(ctx, http.MethodGet, "/api/v1/public/agents", nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if err := checkStatus(resp); err != nil {
		return nil, err
	}

	// API may return a list or {"agents": [...]}
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("synkora: read response: %w", err)
	}

	var list []agentPayload
	if raw[0] == '[' {
		if err := json.Unmarshal(raw, &list); err != nil {
			return nil, fmt.Errorf("synkora: decode agents: %w", err)
		}
	} else {
		var wrapper struct {
			Agents []agentPayload `json:"agents"`
		}
		if err := json.Unmarshal(raw, &wrapper); err != nil {
			return nil, fmt.Errorf("synkora: decode agents: %w", err)
		}
		list = wrapper.Agents
	}

	out := make([]*AgentInfo, len(list))
	for i, a := range list {
		out[i] = a.toAgentInfo()
	}
	return out, nil
}

// GetAgent returns metadata for a single agent.
func (c *Client) GetAgent(ctx context.Context, agentID string) (*AgentInfo, error) {
	resp, err := c.do(ctx, http.MethodGet, "/api/v1/public/agents/"+agentID, nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if err := checkStatus(resp); err != nil {
		return nil, err
	}
	var a agentPayload
	if err := json.NewDecoder(resp.Body).Decode(&a); err != nil {
		return nil, fmt.Errorf("synkora: decode agent: %w", err)
	}
	return a.toAgentInfo(), nil
}

// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------

// ListConversations returns stored conversations for an agent.
func (c *Client) ListConversations(ctx context.Context, agentID string) ([]*ConversationInfo, error) {
	resp, err := c.do(ctx, http.MethodGet, "/api/v1/public/agents/"+agentID+"/conversations", nil)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if err := checkStatus(resp); err != nil {
		return nil, err
	}

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("synkora: read response: %w", err)
	}

	var list []convPayload
	if raw[0] == '[' {
		if err := json.Unmarshal(raw, &list); err != nil {
			return nil, fmt.Errorf("synkora: decode conversations: %w", err)
		}
	} else {
		var wrapper struct {
			Conversations []convPayload `json:"conversations"`
		}
		if err := json.Unmarshal(raw, &wrapper); err != nil {
			return nil, fmt.Errorf("synkora: decode conversations: %w", err)
		}
		list = wrapper.Conversations
	}

	out := make([]*ConversationInfo, len(list))
	for i, cv := range list {
		out[i] = cv.toConversationInfo()
	}
	return out, nil
}

// DeleteConversation deletes a conversation and all its messages.
func (c *Client) DeleteConversation(ctx context.Context, agentID, conversationID string) error {
	resp, err := c.do(ctx, http.MethodDelete,
		"/api/v1/public/agents/"+agentID+"/conversations/"+conversationID, nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return checkStatus(resp)
}

// ---------------------------------------------------------------------------
// Chat — streaming
// ---------------------------------------------------------------------------

// ChatStream opens a streaming chat request and returns a *Stream.
// The caller MUST call stream.Close() when done.
//
//	stream, err := client.ChatStream(ctx, agentID, "Hello", nil)
//	if err != nil { ... }
//	defer stream.Close()
//	for stream.Next() {
//	    switch ev := stream.Event().(type) {
//	    case *synkora.ChunkEvent:
//	        fmt.Print(ev.Content)
//	    }
//	}
//	if err := stream.Err(); err != nil { ... }
func (c *Client) ChatStream(
	ctx context.Context,
	agentID string,
	message string,
	opts *ChatOptions,
) (*Stream, error) {
	body := chatRequestBody(message, opts)
	resp, err := c.do(ctx, http.MethodPost,
		"/api/v1/public/agents/"+agentID+"/chat/stream", body)
	if err != nil {
		return nil, err
	}
	if err := checkStatus(resp); err != nil {
		return nil, err
	}
	return newStream(resp.Body), nil
}

// ---------------------------------------------------------------------------
// Chat — non-streaming (aggregates the stream)
// ---------------------------------------------------------------------------

// Chat sends a message and waits for the complete response.
func (c *Client) Chat(
	ctx context.Context,
	agentID string,
	message string,
	opts *ChatOptions,
) (*ChatResponse, error) {
	stream, err := c.ChatStream(ctx, agentID, message, opts)
	if err != nil {
		return nil, err
	}
	defer stream.Close()

	var sb strings.Builder
	conversationID := ""
	if opts != nil {
		conversationID = opts.ConversationID
	}
	var done *DoneEvent

	for stream.Next() {
		switch ev := stream.Event().(type) {
		case *ChunkEvent:
			sb.WriteString(ev.Content)
		case *DoneEvent:
			done = ev
			if id, ok := ev.Metadata["conversation_id"].(string); ok && id != "" {
				conversationID = id
			}
		}
	}
	if err := stream.Err(); err != nil {
		return nil, err
	}

	var meta map[string]any
	var sources []map[string]any
	var tokensUsed int
	if done != nil {
		meta = done.Metadata
		sources = done.Sources
		if v, ok := done.Metadata["total_tokens"].(float64); ok {
			tokensUsed = int(v)
		}
	}

	return &ChatResponse{
		ConversationID: conversationID,
		Message:        sb.String(),
		TokensUsed:     tokensUsed,
		Metadata:       meta,
		Sources:        sources,
	}, nil
}

// ---------------------------------------------------------------------------
// Internal JSON payload structs
// ---------------------------------------------------------------------------

type chatRequest struct {
	Message        string         `json:"message"`
	ConversationID string         `json:"conversation_id,omitempty"`
	Metadata       map[string]any `json:"metadata,omitempty"`
}

func chatRequestBody(message string, opts *ChatOptions) chatRequest {
	r := chatRequest{Message: message}
	if opts != nil {
		r.ConversationID = opts.ConversationID
		r.Metadata = opts.Metadata
	}
	return r
}

type agentPayload struct {
	ID           string   `json:"id"`
	Name         string   `json:"name"`
	Description  string   `json:"description"`
	Model        string   `json:"model"`
	Capabilities []string `json:"capabilities"`
}

func (a agentPayload) toAgentInfo() *AgentInfo {
	caps := a.Capabilities
	if caps == nil {
		caps = []string{}
	}
	return &AgentInfo{
		ID:           a.ID,
		Name:         a.Name,
		Description:  a.Description,
		Model:        a.Model,
		Capabilities: caps,
	}
}

type convPayload struct {
	ID           string `json:"id"`
	AgentID      string `json:"agent_id"`
	CreatedAt    string `json:"created_at"`
	UpdatedAt    string `json:"updated_at"`
	MessageCount int    `json:"message_count"`
}

func (cv convPayload) toConversationInfo() *ConversationInfo {
	return &ConversationInfo{
		ID:           cv.ID,
		AgentID:      cv.AgentID,
		CreatedAt:    cv.CreatedAt,
		UpdatedAt:    cv.UpdatedAt,
		MessageCount: cv.MessageCount,
	}
}
