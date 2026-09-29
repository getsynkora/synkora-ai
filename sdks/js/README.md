# synkora

JavaScript/TypeScript SDK for the [Synkora](https://synkora.com) AI agent platform.

- Zero runtime dependencies — uses the native `fetch` API (Node 18+, Deno, Cloudflare Workers, browsers)
- Full TypeScript types included
- Ships both ESM and CommonJS

## Installation

```bash
npm install synkora
# or
pnpm add synkora
# or
yarn add synkora
```

## Quick start

```ts
import { SynkoraClient } from 'synkora'

const client = new SynkoraClient({ apiKey: process.env.SYNKORA_API_KEY })

// Non-streaming — waits for the full response
const response = await client.chat('<agent-uuid>', 'Summarise last quarter's sales figures.')
console.log(response.message)
```

## Streaming

```ts
for await (const event of client.chatStream('<agent-uuid>', 'Hello')) {
  if (event.type === 'chunk') {
    process.stdout.write(event.content)
  } else if (event.type === 'tool_status') {
    console.log(`\n[tool: ${event.toolName} — ${event.status}]`)
  } else if (event.type === 'done') {
    console.log() // newline at end
  }
}
```

## Continue a conversation

```ts
// First message — creates a new conversation
const r1 = await client.chat('<agent-uuid>', 'My name is Alice.')

// Second message — continues the same conversation
const r2 = await client.chat('<agent-uuid>', 'What is my name?', {
  conversationId: r1.conversationId,
})
console.log(r2.message) // "Your name is Alice."
```

## Environment variables

| Variable | Description |
|---|---|
| `SYNKORA_API_KEY` | Your agent API key |
| `SYNKORA_BASE_URL` | Override the API base URL (default: `https://app.synkora.com`) |

## API reference

### `new SynkoraClient(options?)`

| Option | Type | Description |
|---|---|---|
| `apiKey` | `string` | API key. Falls back to `SYNKORA_API_KEY` env var. |
| `baseUrl` | `string` | Base URL override. Falls back to `SYNKORA_BASE_URL` env var. |
| `timeoutMs` | `number` | Request timeout. Default: `120000`. |

### `client.chat(agentId, message, options?)`

Send a message and await the full response.

```ts
const response: ChatResponse = await client.chat(agentId, message, {
  conversationId?: string   // continue an existing conversation
  metadata?: Record<string, unknown>
})
```

### `client.chatStream(agentId, message, options?)`

Returns an async generator of typed stream events.

```ts
for await (const event of client.chatStream(agentId, message)) { ... }
```

### `client.listAgents()`

```ts
const agents: AgentInfo[] = await client.listAgents()
```

### `client.getAgent(agentId)`

```ts
const agent: AgentInfo = await client.getAgent(agentId)
```

### `client.listConversations(agentId)`

```ts
const conversations: ConversationInfo[] = await client.listConversations(agentId)
```

### `client.deleteConversation(agentId, conversationId)`

```ts
await client.deleteConversation(agentId, conversationId)
```

## Stream event types

| `event.type` | Interface | Key fields |
|---|---|---|
| `start` | `StartEvent` | `agent`, `startTime` |
| `chunk` | `ChunkEvent` | `content` |
| `status` | `StatusEvent` | `content` |
| `tool_status` | `ToolStatusEvent` | `toolName`, `status`, `description`, `durationMs` |
| `llm_call` | `LLMCallEvent` | `status`, `model`, `inputTokens`, `outputTokens` |
| `first_token` | `FirstTokenEvent` | `timeToFirstToken` |
| `done` | `DoneEvent` | `metadata`, `sources` |
| `compaction` | `CompactionEvent` | `prunedCount`, `tokensSaved` |
| `satisfaction_prompt` | `SatisfactionPromptEvent` | `conversationId` |

## Error handling

```ts
import {
  AuthError,
  AgentNotFoundError,
  RateLimitError,
  StreamError,
} from 'synkora'

try {
  const response = await client.chat(agentId, 'Hello')
} catch (e) {
  if (e instanceof AuthError)          console.error('Check your API key')
  else if (e instanceof AgentNotFoundError) console.error('Agent not found')
  else if (e instanceof RateLimitError) console.error('Rate limited — back off and retry')
  else if (e instanceof StreamError)   console.error('Stream error:', e.errorType, e.message)
  else throw e
}
```

## CommonJS

```js
const { SynkoraClient } = require('synkora')
```

## License

MIT
