# synkora-go

Go SDK for the [Synkora](https://synkora.com) AI agent platform.

- Zero dependencies — uses only the Go standard library
- Supports streaming via the `sql.Rows`-style `Next()` / `Event()` / `Err()` API
- Full type safety with a `StreamEvent` interface and concrete event types
- Context-aware — every method accepts `context.Context` for cancellation and deadlines

## Requirements

Go 1.21+

## Installation

```bash
go get github.com/getsynkora/synkora-go
```

## Quick start

```go
package main

import (
    "context"
    "fmt"
    "log"

    synkora "github.com/getsynkora/synkora-go"
)

func main() {
    client, err := synkora.New(synkora.WithAPIKey("sk-..."))
    if err != nil {
        log.Fatal(err)
    }

    // Non-streaming — waits for the full response
    resp, err := client.Chat(context.Background(), "<agent-uuid>", "Hello", nil)
    if err != nil {
        log.Fatal(err)
    }
    fmt.Println(resp.Message)
}
```

## Streaming

```go
stream, err := client.ChatStream(context.Background(), "<agent-uuid>", "Hello", nil)
if err != nil {
    log.Fatal(err)
}
defer stream.Close()

for stream.Next() {
    switch ev := stream.Event().(type) {
    case *synkora.ChunkEvent:
        fmt.Print(ev.Content)
    case *synkora.ToolStatusEvent:
        fmt.Printf("\n[tool: %s — %s]\n", ev.ToolName, ev.Status)
    case *synkora.DoneEvent:
        fmt.Println()
    }
}
if err := stream.Err(); err != nil {
    log.Fatal(err)
}
```

## Continue a conversation

```go
// First message — creates a new conversation
r1, err := client.Chat(ctx, agentID, "My name is Alice.", nil)

// Second message — continues the same conversation
r2, err := client.Chat(ctx, agentID, "What is my name?", &synkora.ChatOptions{
    ConversationID: r1.ConversationID,
})
fmt.Println(r2.Message) // "Your name is Alice."
```

## Environment variables

| Variable | Description |
|---|---|
| `SYNKORA_API_KEY` | Your agent API key |
| `SYNKORA_BASE_URL` | Override the API base URL (default: `https://app.synkora.com`) |

## Client options

```go
client, err := synkora.New(
    synkora.WithAPIKey("sk-..."),           // API key
    synkora.WithBaseURL("https://..."),     // override base URL
    synkora.WithTimeout(60*time.Second),    // request timeout (default: 120s)
    synkora.WithHTTPClient(myHTTPClient),  // custom *http.Client
)
```

## Stream event types

| Type assertion | Event type | Key fields |
|---|---|---|
| `*StartEvent` | `start` | `Agent`, `StartTime` |
| `*ChunkEvent` | `chunk` | `Content` |
| `*StatusEvent` | `status` | `Content` |
| `*ToolStatusEvent` | `tool_status` | `ToolName`, `Status`, `Description`, `DurationMs` |
| `*LLMCallEvent` | `llm_call` | `Status`, `Model`, `InputTokens`, `OutputTokens` |
| `*FirstTokenEvent` | `first_token` | `TimeToFirstToken` |
| `*DoneEvent` | `done` | `Metadata`, `Sources` |
| `*CompactionEvent` | `compaction` | `PrunedCount`, `TokensSaved` |
| `*SatisfactionPromptEvent` | `satisfaction_prompt` | `ConversationID` |

## Error handling

```go
import "errors"

_, err := client.GetAgent(ctx, agentID)
switch {
case errors.As(err, new(*synkora.AuthError)):
    // invalid or missing API key
case errors.As(err, new(*synkora.AgentNotFoundError)):
    // agent doesn't exist
case errors.As(err, new(*synkora.RateLimitError)):
    // back off and retry
case errors.As(err, new(*synkora.StreamError)):
    // error received in the SSE stream
}
```

## Running tests

```bash
cd sdks/go
go test ./...
```

## License

MIT
