# Synkora SDKs

Official client SDKs for the [Synkora](https://synkora.com) AI agent platform.

All SDKs target the same public API (`/api/v1/public/`) and share the same design:

- A single client class with `chat()` (blocking, returns full response) and `chatStream()` (returns typed stream events)
- Env-var auto-detection for `SYNKORA_API_KEY` and `SYNKORA_BASE_URL`
- Strongly typed — all SSE events and REST responses are typed
- Minimal dependencies

## Available SDKs

| Language | Directory | Package | Status |
|---|---|---|---|
| Python | [`python/`](./python/) | `synkora` on PyPI | 0.1.0 |
| JavaScript / TypeScript | [`js/`](./js/) | `synkora` on npm | 0.1.0 |
| Go | [`go/`](./go/) | `github.com/getsynkora/synkora-go` | 0.1.0 |

## Quick example (Python)

```python
from synkora import SynkoraClient

client = SynkoraClient()  # reads SYNKORA_API_KEY from env

response = client.chat(agent_id="<uuid>", message="Hello")
print(response.message)
```

## Quick example (Go)

```go
client, _ := synkora.New(synkora.WithAPIKey(os.Getenv("SYNKORA_API_KEY")))

resp, err := client.Chat(context.Background(), "<uuid>", "Hello", nil)
fmt.Println(resp.Message)
```

## Quick example (JavaScript/TypeScript)

```ts
import { SynkoraClient } from 'synkora'

const client = new SynkoraClient()  // reads SYNKORA_API_KEY from env

const response = await client.chat('<uuid>', 'Hello')
console.log(response.message)
```

## Getting an API key

1. Open the Synkora dashboard and navigate to your agent
2. Go to **Settings → API Keys**
3. Create a key with the `chat` permission

## Self-hosted deployments

Pass `baseUrl` / `SYNKORA_BASE_URL` pointing at your instance:

```python
client = SynkoraClient(base_url="https://ai.your-company.com")
```

```ts
const client = new SynkoraClient({ baseUrl: 'https://ai.your-company.com' })
```
