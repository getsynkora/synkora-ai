# synkora-python

Official Python SDK for the [Synkora](https://synkora.com) AI agent platform.

## Requirements

- Python 3.11+
- `httpx` (the only runtime dependency)

## Installation

```bash
pip install synkora
```

## Quick start

```python
import os
from synkora import SynkoraClient

client = SynkoraClient(api_key=os.environ["SYNKORA_API_KEY"])

# Non-streaming — wait for the full response
response = client.chat(
    agent_id="<your-agent-uuid>",
    message="Summarise last quarter's sales figures.",
)
print(response.message)
```

## Streaming

```python
for event in client.chat_stream(agent_id="<uuid>", message="Hello"):
    if event.type == "chunk":
        print(event.content, end="", flush=True)
    elif event.type == "tool_status":
        print(f"\n[tool: {event.tool_name} — {event.status}]")
    elif event.type == "done":
        print()
```

## Async

```python
import asyncio
from synkora import AsyncSynkoraClient

async def main():
    async with AsyncSynkoraClient(api_key="sk-...") as client:
        response = await client.chat(agent_id="<uuid>", message="Hello")
        print(response.message)

        async for event in client.chat_stream(agent_id="<uuid>", message="Hello"):
            if event.type == "chunk":
                print(event.content, end="", flush=True)

asyncio.run(main())
```

## Continue a conversation

```python
# First message — creates a new conversation
r1 = client.chat(agent_id="<uuid>", message="My name is Alice.")

# Second message — continues the same conversation
r2 = client.chat(
    agent_id="<uuid>",
    message="What is my name?",
    conversation_id=r1.conversation_id,
)
print(r2.message)  # "Your name is Alice."
```

## Environment variables

| Variable | Description |
|---|---|
| `SYNKORA_API_KEY` | Your agent API key |
| `SYNKORA_BASE_URL` | Override the API base URL (default: `https://app.synkora.com`) |

## Stream event types

| Event type | Class | Key fields |
|---|---|---|
| `start` | `StartEvent` | `agent`, `start_time` |
| `chunk` | `ChunkEvent` | `content` |
| `status` | `StatusEvent` | `content` |
| `tool_status` | `ToolStatusEvent` | `tool_name`, `status`, `description`, `duration_ms` |
| `llm_call` | `LLMCallEvent` | `status`, `model`, `input_tokens`, `output_tokens` |
| `first_token` | `FirstTokenEvent` | `time_to_first_token` |
| `done` | `DoneEvent` | `metadata`, `sources` |
| `compaction` | `CompactionEvent` | `pruned_count`, `tokens_saved` |
| `satisfaction_prompt` | `SatisfactionPromptEvent` | `conversation_id` |

## Error handling

```python
from synkora.exceptions import AuthError, AgentNotFoundError, RateLimitError, StreamError

try:
    response = client.chat(agent_id="<uuid>", message="Hello")
except AuthError:
    print("Check your API key")
except AgentNotFoundError:
    print("Agent not found")
except RateLimitError:
    print("Rate limited — back off and retry")
except StreamError as e:
    print(f"Stream error: {e.error_type} — {e}")
```

## License

MIT
