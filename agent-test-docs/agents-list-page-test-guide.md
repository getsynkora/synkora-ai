# End-to-End Test: `/agents` Listing Page (Web)

## Overview

Tests the web frontend's agents listing page (`web/app/(dashboard)/agents/page.tsx`) at
`http://localhost:3000/agents` — specifically, the API calls the page makes directly:

1. `GET /api/v1/agents/` — paginated, debounced-search agent list
2. `DELETE /api/v1/agents/{agent_slug}` — delete an agent

The page's other actions (edit, landing-page, sub-agents, clone, lens, chat, view) are pure
client-side navigation (`router.push`) to other pages — they don't call any API from this page
itself, so they aren't covered here.

Traced from source before testing (not guessed):
- `web/app/(dashboard)/agents/page.tsx` — `fetchAgents()` calls `apiClient.getAgents(page, pageSize, search)`;
  `handleDeleteAgent()` calls `apiClient.deleteAgent(agentToDelete.id)`
- `web/lib/api/agents.ts` — `getAgents()` → `GET /api/v1/agents/?page=&page_size=&search=`;
  `deleteAgent(agentName)` → `DELETE /api/v1/agents/${agentName}`
- `api/src/controllers/agents/index.py` — list endpoint filters by `Agent.tenant_id`; delete endpoint
  (`delete_agent`) filters strictly by `Agent.slug == agent_slug` (line ~1300), never by `Agent.id`

## Bug Found and Fixed

**Every navigation link on the agents grid uses `agent.slug`** (e.g.
`router.push('/agents/${agent.slug}/edit')`), but the delete flow was the one exception — it used
`agent.id` (the UUID primary key) instead:

```typescript
// Before (bug):
onDelete={() => onDelete({ id: agent.id, name: agent.agent_name })}
// → apiClient.deleteAgent(agentToDelete.id)
// → DELETE /api/v1/agents/{uuid}
```

The backend delete endpoint only matches on `slug`, never `id`, so every delete click from this
page would 404 and silently fail (caught by the generic `catch` block, showing a "Failed to delete
agent" toast with no useful detail).

**Confirmed empirically** by creating a real agent and calling both variants directly:

```
DELETE /api/v1/agents/5e0caadc-b7be-4842-b7f6-4762ac0d0d59  (the UUID id)
→ 404 {"detail":"Agent '5e0caadc-b7be-4842-b7f6-4762ac0d0d59' not found"}

DELETE /api/v1/agents/e2e-delete-test-agent  (the slug)
→ 200 {"success":true,"message":"Agent 'e2e-delete-test-agent' deleted successfully","data":{}}
```

**Fix applied** in `web/app/(dashboard)/agents/page.tsx`:

```typescript
// After (fixed):
onDelete={() => onDelete({ id: agent.slug, name: agent.agent_name })}
```

This keeps the delete flow consistent with every other link on the page, all of which key off
`agent.slug`. No backend changes were needed — the backend's slug-only contract is correct; the
frontend was passing the wrong field.

---

## Prerequisites

- API running on `http://localhost:5001`, web running on `http://localhost:3000`
- Platform admin login: `admin@localhost.com` / `Admin123!` (confirmed via
  `SELECT email FROM accounts WHERE is_platform_admin='true'`)
- At least a valid dummy LLM `api_key` string — agent creation requires either a per-request
  `api_key` or a tenant-wide Platform Engineer LLM config (see Notes)

Run all commands via `docker compose exec -T api ...` from the repo root — this project has no
local Python env, only Docker (see `MEMORY.md`).

---

## Step 1 — Get Auth Token

```python
docker compose exec -T api python3 -c "
import urllib.request, json
data = json.dumps({'email': 'admin@localhost.com', 'password': 'Admin123!'}).encode()
req = urllib.request.Request(
    'http://localhost:5001/console/api/auth/login',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read())
    print(d['data']['access_token'])
"
```

Verified: `200`, returns `data.access_token`. Use this as `Authorization: Bearer {token}` for the
rest of this guide.

---

## Step 2 — Create a Test Agent

```python
docker compose exec -T api python3 -c "
import urllib.request, json

TOKEN = '<paste access_token here>'

payload = json.dumps({
    'agent_type': 'llm',
    'api_key': 'dummy-test-key-12345',
    'config': {
        'name': 'Agents Page Test Agent',
        'description': 'temp agent for /agents page test doc',
        'llm_config': {'provider': 'gemini', 'model_name': 'gemini-2.0-flash-exp', 'api_key': 'dummy-test-key-12345'}
    }
}).encode()
req = urllib.request.Request(
    'http://localhost:5001/api/v1/agents/',
    data=payload,
    headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())
"
```

Verified response (`201`):

```json
{"success":true,"message":"Agent 'Agents Page Test Agent' created successfully","data":{"agent_id":"28ea24d3-7d67-4a66-99f4-631f4ba158b7","agent_name":"Agents Page Test Agent","slug":"agents-page-test-agent"}}
```

Note `agent_id` (UUID) and `slug` are distinct values — this is exactly what makes the delete bug
above possible.

---

## Step 3 — List Agents (What Loading `/agents` Actually Calls)

This is the exact call `fetchAgents()` makes on page load, with the default page size (9) used by
the frontend:

```python
docker compose exec -T api python3 -c "
import urllib.request, json

TOKEN = '<paste access_token here>'
req = urllib.request.Request(
    'http://localhost:5001/api/v1/agents/?page=1&page_size=9',
    headers={'Authorization': f'Bearer {TOKEN}'},
    method='GET'
)
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())
"
```

Verified response (`200`) shape:

```json
{
  "success": true,
  "data": {
    "agents": [...],
    "agents_list": [
      {"id": "28ea24d3-...", "agent_name": "Agents Page Test Agent", "slug": "agents-page-test-agent", "public_slug": null, "agent_type": "llm", "status": "ACTIVE", ...}
    ],
    "pagination": {"page": 1, "page_size": 9, "total": 1, "total_pages": 1, "has_next": false, "has_prev": false}
  }
}
```

The frontend reads `response.agents_list` and `response.pagination` (see `agents.ts::getAgents` —
it unwraps `data.data || data` first).

---

## Step 4 — Search (Debounced 300ms on the Frontend)

Matching search term:

```python
docker compose exec -T api python3 -c "
import urllib.request, json
TOKEN = '<paste access_token here>'
req = urllib.request.Request(
    'http://localhost:5001/api/v1/agents/?page=1&page_size=9&search=Agents%20Page',
    headers={'Authorization': f'Bearer {TOKEN}'},
    method='GET'
)
with urllib.request.urlopen(req) as r:
    d = json.loads(r.read().decode())['data']
    print(d['pagination']['total'], [a['slug'] for a in d['agents_list']])
"
```

Verified: `1 ['agents-page-test-agent']`

Non-matching search term:

```python
# search=zzz-no-match-zzz
```

Verified: `pagination.total == 0`, `agents_list == []`.

---

## Step 5 — Delete the Agent (Correct, Post-Fix Behavior)

This is what the fixed frontend now sends — `DELETE` using the agent's **slug**, not its UUID `id`:

```python
docker compose exec -T api python3 -c "
import urllib.request, json
TOKEN = '<paste access_token here>'
req = urllib.request.Request(
    'http://localhost:5001/api/v1/agents/agents-page-test-agent',
    headers={'Authorization': f'Bearer {TOKEN}'},
    method='DELETE'
)
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())
"
```

Verified response (`200`):

```json
{"success":true,"message":"Agent 'agents-page-test-agent' deleted successfully","data":{}}
```

For contrast, calling `DELETE /api/v1/agents/{uuid}` (the pre-fix, buggy behavior) returns `404`
— see "Bug Found and Fixed" above for the exact verified output.

---

## Cleanup

The agent created in Step 2 is deleted by Step 5 itself. If a run is aborted early, remove any
leftover test agent directly:

```bash
docker compose exec -T postgres psql -U synkora -d synkora -c \
  "DELETE FROM agents WHERE slug='agents-page-test-agent';"
```

---

## Endpoint Reference

| Purpose | Method | Path | Auth required |
|---------|--------|------|----------------|
| List agents (paginated, searchable) | GET | `/api/v1/agents/?page=&page_size=&search=` | Bearer token |
| Create agent | POST | `/api/v1/agents/` | Bearer token (ADMIN role) |
| Get single agent | GET | `/api/v1/agents/{agent_slug}` | Bearer token |
| Delete agent | DELETE | `/api/v1/agents/{agent_slug}` | Bearer token (ADMIN role) |

## Notes

- Agent creation requires either a per-request `api_key` (top-level or nested in
  `config.llm_config.api_key`) or a tenant-wide Platform Engineer LLM configuration. Without
  either, creation fails with `422: "No API key provided and no Platform Engineer LLM
  configuration found."`
- `Agent` has three distinct identifier-like columns: `id` (UUID PK), `agent_name` (unique per
  tenant, human-readable), and `slug` (globally unique, used for all URL routing). Only `slug` is
  valid for the `GET /{agent_slug}` and `DELETE /{agent_slug}` routes.
- Delete requires `ADMIN` role (`require_role(AccountRole.ADMIN)`) — a non-admin token gets `403`,
  not `404`, so a `404` on delete specifically indicates a slug/id mismatch, not a permissions
  issue.
