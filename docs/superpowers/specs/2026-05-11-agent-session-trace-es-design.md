# Agent Session Trace — Elasticsearch Design

**Date:** 2026-05-11
**Status:** Approved
**Scope:** Replace all Agent Lens data storage and queries with Elasticsearch. Add full per-session event tracing covering every user message, LLM call, tool call, and assistant response. Build a debug-friendly session detail UI.

---

## Context

Agent Lens currently stores observability data across three PostgreSQL tables: `AgentToolCallLog`, `LLMTokenUsage`, and the core `Message`/`Conversation` tables. PostgreSQL is not well-suited for high-volume append-only log data — no schema-free extension, no native time-series aggregations, and no full-text search on event content.

The existing session detail timeline is also incomplete: it only shows user/assistant messages and tool calls. The intermediate LLM reasoning calls inside an agentic loop (call #0 initial reasoning → tool calls → call #1 synthesis) are never captured, making it impossible to debug why an agent made a particular decision.

---

## Goals

1. Move all lens data to Elasticsearch — no more PG lens queries.
2. Capture every step of the agentic loop: user message → LLM call(s) → tool call(s) → assistant message.
3. Build a debug-first session detail UI with failure highlighting, filters, copy buttons, and timing visualization.
4. Zero latency impact on the chat streaming path.

---

## What Changes

| Component | Before | After |
|---|---|---|
| `AgentToolCallLog` (PG table) | Stores tool calls for lens | Removed — ES replaces it |
| `agent_lens_service.py` | PG queries for all lens endpoints | Deleted — replaced by `agent_trace_service.py` |
| `LLMTokenUsage` (PG) | Source for cost/token lens stats | Unchanged for billing; ES used for lens |
| `Message` / `Conversation` (PG) | Source for session list and timeline | Unchanged for chat; ES used for lens reads |
| `AgentLensAlert` (PG) | Alert config CRUD | Unchanged — config data stays in PG |
| Session detail page | Shows messages + tool calls | Shows full trace: user → LLM call → tool → LLM call → assistant |

---

## Elasticsearch Index

### Index name
`agent-session-events`

### ILM policy
Created on app startup (idempotent). Delete phase triggers at 7 days (configurable via `AGENT_TRACE_RETENTION_DAYS`). Attached to the index via an index template.

### Document schema

Every document shares a common envelope. Type-specific fields are present only when relevant.

```json
{
  "tenant_id": "uuid — always present, all queries filter on this",
  "agent_id": "uuid",
  "conversation_id": "uuid",
  "event_type": "user_message | llm_call | tool_call | assistant_message",
  "sequence": 3,
  "timestamp": "2026-05-11T10:00:00.000Z",

  "user_message": {
    "content": "first 500 chars of user input",
    "message_id": "uuid",
    "conversation_name": "name from Conversation.name — stored on first event so sessions list needs no PG join",
    "conversation_status": "ACTIVE | ARCHIVED"
  },

  "llm_call": {
    "model": "claude-sonnet-4-6",
    "call_index": 0,
    "input_tokens": 1234,
    "output_tokens": 456,
    "cost_usd": 0.002,
    "latency_ms": 1200,
    "response_preview": "first 500 chars of LLM output",
    "status": "success | error",
    "error": "error message if failed"
  },

  "tool_call": {
    "tool_name": "search_web",
    "success": true,
    "duration_ms": 234,
    "retry_count": 0,
    "args": "full dict if failed — 500-char JSON preview if success",
    "result": "full dict if failed — 500-char JSON preview if success",
    "error_message": "full error text if failed"
  },

  "assistant_message": {
    "content_preview": "first 500 chars of final response",
    "message_id": "uuid",
    "total_input_tokens": 2100,
    "total_output_tokens": 890,
    "total_cost_usd": 0.004,
    "total_latency_ms": 3400
  }
}
```

**Tenant isolation:** every query includes a `term` filter on `tenant_id`. No cross-tenant data is ever accessible.

---

## Settings

Add a `TracingConfig` group to `api/src/config/settings.py`:

```python
class TracingConfig(BaseSettings):
    ELASTICSEARCH_URL: str = "http://elasticsearch:9200"
    ELASTICSEARCH_USERNAME: str = "elastic"
    ELASTICSEARCH_PASSWORD: str = "changeme"
    AGENT_TRACE_ENABLED: bool = True
    AGENT_TRACE_INDEX: str = "agent-session-events"
    AGENT_TRACE_RETENTION_DAYS: int = 7
```

Add to `.env.example`.

---

## New Files

### `api/src/services/agents/agent_trace_service.py`

Single file — write path + read path.

**Write path (fire-and-forget):**

```python
_trace_bg_tasks: set[asyncio.Task] = set()
_es_client: AsyncElasticsearch | None = None

def _fire_index_event(event: dict) -> None:
    """Returns in ~1µs. Never raises. Same pattern as _fire_persist_tool_call."""
    try:
        task = asyncio.create_task(_index_event(event))
        _trace_bg_tasks.add(task)
        task.add_done_callback(_trace_bg_tasks.discard)
    except Exception as e:
        logger.warning("_fire_index_event scheduling error: %s", e)

async def _index_event(event: dict) -> None:
    """Silently discards on ES error — never affects chat."""
    try:
        client = await _get_es_client()
        await client.index(index=settings.tracing.AGENT_TRACE_INDEX, document=event)
    except Exception as e:
        logger.warning("ES index event failed (non-critical): %s", e)
```

**Public fire functions** (called from hooks, all return immediately):

- `fire_user_message(tenant_id, agent_id, conversation_id, message_id, content, conversation_name, conversation_status, sequence)` — includes conversation metadata so sessions list needs no PG join
- `fire_llm_call(tenant_id, agent_id, conversation_id, model, call_index, input_tokens, output_tokens, cost_usd, latency_ms, response_preview, status, error, sequence)`
- `fire_tool_call(tenant_id, agent_id, conversation_id, tool_name, success, duration_ms, retry_count, args, result, error_message, sequence)` — failed calls store full args+result, success stores truncated preview
- `fire_assistant_message(tenant_id, agent_id, conversation_id, message_id, content_preview, total_input_tokens, total_output_tokens, total_cost_usd, total_latency_ms, sequence)`

**Read path** (ES aggregation queries, called from lens controller):

- `get_overview(tenant_id, agent_id, start, end) -> dict`
  Single ES request with multi-metric aggregations: cardinality of `conversation_id`, count/sum/avg on `llm_call` events, count + filtered count on `tool_call` events.

- `get_sessions(tenant_id, agent_id, start, end, page, page_size) -> dict`
  Terms aggregation bucketed by `conversation_id`. Sub-aggregations: sum tokens, sum cost, count messages, min timestamp. Paginated via `from`/`size` on the bucket list.

- `get_token_distribution(tenant_id, agent_id, start, end) -> dict`
  Terms aggregation by `llm_call.model` — sum tokens, sum cost per model. Plus global sum of input vs output tokens.

- `get_tool_analytics(tenant_id, agent_id, start, end) -> dict`
  Terms aggregation by `tool_call.tool_name` — count, filtered success count, avg/max duration, sum retries.

- `get_session_detail(tenant_id, agent_id, conversation_id) -> dict`
  Simple `term` query on `conversation_id` + `agent_id` + `tenant_id`. Sort by `sequence` asc. Returns all events for the timeline renderer.

### `api/src/services/agents/agent_trace_setup.py`

Called once in `app.py` lifespan on startup. Idempotent — safe to run on every restart.

1. Create ILM policy `agent-trace-ilm` with delete phase at `AGENT_TRACE_RETENTION_DAYS` days.
2. Create index template `agent-session-events-template` pointing to the ILM policy.
3. Create the index if it does not exist.

---

## Modified Files

### `api/src/services/agents/function_calling.py`

Replace `_fire_persist_tool_call()` (PG) with `fire_tool_call()` (ES). Gate on `AGENT_TRACE_ENABLED`. Store full args+result for failed calls; 500-char preview for success.

### `api/src/services/agents/chat_stream_service.py`

Two hooks:
1. After user message is saved to PG → `fire_user_message()`
2. After `save_assistant_message()` → `fire_assistant_message()` with turn totals

### `api/src/services/agents/llm_client.py`

Wrap the actual LLM API call:
```python
start = time.monotonic()
response = await self._call_provider(...)
latency_ms = int((time.monotonic() - start) * 1000)
fire_llm_call(..., call_index=self._call_index, latency_ms=latency_ms, ...)
self._call_index += 1
```

`call_index` is a per-turn counter — it resets to 0 at the start of each new user turn (passed in via `RuntimeContext.llm_call_index`, incremented before each fire). This means call #0 is always the initial reasoning call for that turn, call #1 is the synthesis call after tools return, etc. It does not accumulate across the whole conversation.

### `api/src/controllers/agents/agent_lens.py`

All 5 read endpoints switch import from `agent_lens_service` → `agent_trace_service`. No Pydantic schema changes — same response models.

### `api/src/app.py`

Add to lifespan startup:
```python
from src.services.agents.agent_trace_setup import setup_agent_trace
await setup_agent_trace()
```

### `api/src/models/__init__.py`

Remove `AgentToolCallLog` export.

### `api/src/router_registry.py`

No change — `agent_lens` router stays registered.

---

## Deleted Files

- `api/src/models/agent_tool_call_log.py`
- `api/src/services/agents/agent_lens_service.py`
- Migration that created `agent_tool_call_logs` table (add a downgrade migration to drop it)

---

## Sequence Tracking

`RuntimeContext` gains an `event_sequence` counter (atomic int). Every hook increments it before firing. This guarantees ES documents for the same conversation turn sort correctly even if they arrive at ES out of order.

---

## Frontend

### `lens/sessions/[sessionId]/page.tsx` — Full rewrite for debug UX

**Session summary bar** — shows `Failures: N` badge in red if any tool calls failed. Clicking it activates the Failures filter.

**Event type filter bar:**
```
[All]  [Messages]  [LLM Calls]  [Tool Calls]  [Failures only]
```

**Timeline events:**

`user_message`:
- Blue user icon, full content, timestamp

`llm_call`:
- Purple brain icon, model name, call index badge (#0, #1…)
- Token counts (in → out), cost, latency
- Response preview (first 500 chars), [expand full] + [Copy] button
- Timing bar showing duration relative to longest event in session

`tool_call` (success):
- Green wrench icon, tool name, duration, success badge
- Args preview collapsed by default, [expand] to see full + [Copy]
- Result preview collapsed, [expand] to see full + [Copy]

`tool_call` (failed):
- Red wrench icon, `FAILED` badge, retry count badge if > 0
- Error auto-expanded — no click required:
  ```
  ┌─ Error ─────────────────────────────────────────── [Copy] ─┐
  │ ConnectionError: timeout after 30s                          │
  └─────────────────────────────────────────────────────────────┘
  ┌─ Args (full) ───────────────────────────────────── [Copy] ─┐
  │ { "query": "SELECT ...", "connection_id": "abc123" }        │
  └─────────────────────────────────────────────────────────────┘
  ```
- If retried N times, all attempts grouped under one collapsible block with `N retries` badge

`assistant_message`:
- Indigo bot icon, content preview, turn totals (tokens, cost, latency)

**Timing bar** — horizontal bar on each event proportional to its `duration_ms` / `latency_ms` relative to the max in the session. Lets you spot at a glance where time was spent.

**Copy buttons** — on every code block (args, result, error, LLM response). Uses `navigator.clipboard.writeText`.

### `lens/page.tsx` and `lens/sessions/page.tsx`

No UI changes — same endpoints, now backed by ES.

---

## Performance

| Concern | Impact | Mitigation |
|---|---|---|
| `fire_*` hooks in streaming path | ~1µs — `create_task` returns immediately | Fire-and-forget, never awaited |
| ES write per event | None on stream latency — happens concurrently | Own ES connection, not the request session |
| ES unavailable | Events silently dropped | Acceptable for observability; logged as warning |
| Large tool results | Controlled | 500-char preview for success; full only for failures |
| Index growth | ~1–5 KB per event | ILM deletes after 7 days automatically |
| Tenant isolation | Hard requirement | Every ES query includes `term: {tenant_id: ...}` filter |

---

## Verification Checklist

1. Start app — verify ILM policy and index template created in ES (`GET _ilm/policy/agent-trace-ilm`)
2. Send a chat message to an agent with tools — query ES: `GET agent-session-events/_search` — verify `user_message`, `llm_call`, `tool_call`, `assistant_message` documents appear
3. Deliberately trigger a tool failure — verify full args + error stored in the `tool_call` document
4. Load `GET /api/v1/agents/{slug}/lens/overview` — verify stat cards populated from ES aggregations
5. Load sessions list — verify sessions appear with correct token/cost/message totals
6. Load session detail — verify full timeline with all 4 event types in sequence order
7. Test filter bar: "Failures only" should show only failed tool call events
8. Test copy buttons on args, result, error blocks
9. Verify 7-day ILM: check index rollover date on ILM explain endpoint
10. Cross-tenant check: verify `tenant_id` filter prevents accessing another tenant's events
11. Verify chat streaming is unaffected — send multiple messages and confirm no latency increase
