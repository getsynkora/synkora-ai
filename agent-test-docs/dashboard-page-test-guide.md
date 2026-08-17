# End-to-End Test: `/dashboard` Page (Web)

## Overview

Tests the web frontend's dashboard page (`web/app/(dashboard)/dashboard/page.tsx`) at
`http://localhost:3000/dashboard` — specifically the 4 API calls the page makes directly, in
parallel, on mount:

1. `GET /api/v1/agents/` — used for the "Total Agents" stat card AND the "Recent Activity" feed
2. `GET /api/v1/knowledge-bases` — "Knowledge Bases" stat card count
3. `GET /api/v1/data-sources` — "Data Sources" stat card count
4. `GET /api/v1/mcp/servers` — "MCP Servers" stat card count

The "Quick Actions" section and stat-card links are pure `next/link` navigation — no API calls.
`user.name` in the welcome header comes from the Zustand auth store (`useAuth()`), populated
elsewhere at login/app boot — not fetched by this page.

Traced from source before testing (not guessed):
- `web/app/(dashboard)/dashboard/page.tsx::fetchDashboardData()` — all 4 calls run via
  `Promise.all([...])`, each with its own `.catch()` fallback so one failing endpoint doesn't
  break the page (see Step 5 below)
- `web/lib/api/agents.ts::getAgents()` → `GET /api/v1/agents/` (no `page`/`page_size`/`search`
  params passed, so the backend's own defaults apply)
- `web/lib/api/knowledge-bases.ts::getKnowledgeBases()` → `GET /api/v1/knowledge-bases`
- `web/lib/api/data-sources.ts::getDataSources()` → `GET /api/v1/data-sources`
- `web/lib/api/agents.ts::getMCPServers()` → `GET /api/v1/mcp/servers`

## Bug Found and Fixed

The "Recent Activity" feed builds its "Agent created" entries from the wrong field. The agents
list endpoint's response body contains **two different arrays**:

```json
{
  "data": {
    "agents": ["Dashboard Stats Test Agent"],
    "agents_list": [{"id": "...", "agent_name": "Dashboard Stats Test Agent", "created_at": "...", ...}],
    "pagination": {"total": 1, ...}
  }
}
```

- `agents` — an array of **plain agent-name strings**
- `agents_list` — an array of **full agent objects** (has `agent_name`, `created_at`, etc.)

The dashboard page was reading `agentsResponse.agents` (the string array) for the activity feed:

```typescript
// Before (bug):
const agents = Array.isArray(agentsResponse) ? agentsResponse : (agentsResponse.agents || [])
...
agents.slice(0, 3).forEach((agent: any) => {
  activities.push({
    title: 'Agent created',
    description: `${agent.agent_name || agent.name} was created`,  // agent is a STRING here
    time: agent.created_at,                                        // undefined
    ...
  })
})
```

Since `agent` is a string (e.g. `"Dashboard Stats Test Agent"`), `agent.agent_name` and
`agent.name` are both `undefined`, and `agent.created_at` is `undefined` too. Result: every
"Agent created" entry in Recent Activity rendered as **"undefined was created"** with a
**"Recently"** timestamp, regardless of the agent's real name or creation time. The stat card
("Total Agents") was unaffected — it reads `pagination.total`, a different, correct field.

**Confirmed empirically**: created a real agent and printed the raw API response (see Step 2/3
below) — `data.agents` really is `["Dashboard Stats Test Agent"]` (strings), while
`data.agents_list[0]` is the full object with `agent_name` and `created_at`.

**Fix applied** in `web/app/(dashboard)/dashboard/page.tsx`:

```typescript
// After (fixed):
const agents = Array.isArray(agentsResponse) ? agentsResponse : (agentsResponse.agents_list || [])
```

Also fixed the `.catch()` fallback shape to match (it previously fabricated `{ agents: [] }`,
which — even before this fix — was already the wrong key to be internally consistent with):

```typescript
apiClient.getAgents().catch(() => ({ agents_list: [], pagination: { total: 0 } })),
```

No backend changes were needed — both `agents` and `agents_list` are intentional, documented
fields on the list-agents response; the frontend was just reading the wrong one.

---

## Prerequisites

- API running on `http://localhost:5001`, web running on `http://localhost:3000`
- Platform admin login: `admin@localhost.com` / `Admin123!`

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

Verified: `200`, returns `data.access_token`.

---

## Step 2 — Baseline: All 4 Calls on an Empty Tenant

```python
docker compose exec -T api python3 -c "
import urllib.request, json

TOKEN = '<paste access_token here>'

def get(path):
    req = urllib.request.Request(f'http://localhost:5001{path}', headers={'Authorization': f'Bearer {TOKEN}'}, method='GET')
    with urllib.request.urlopen(req) as r:
        return r.status, r.read().decode()

for path in ['/api/v1/agents/', '/api/v1/knowledge-bases', '/api/v1/data-sources', '/api/v1/mcp/servers']:
    print(path, get(path))
"
```

Verified responses (all `200`):

```
/api/v1/agents/        {"success":true,"message":"Found 0 agents","data":{"agents":[],"agents_list":[],"pagination":{"page":1,"page_size":10,"total":0,"total_pages":0,"has_next":false,"has_prev":false}}}
/api/v1/knowledge-bases  []
/api/v1/data-sources     []
/api/v1/mcp/servers      {"success":true,"data":{"servers":[],"total":0}}
```

Note the agents endpoint's default `page_size` is `10` here — the dashboard calls
`apiClient.getAgents()` with **no params**, unlike the `/agents` listing page which explicitly
passes `page_size=9`.

---

## Step 3 — Create One of Each (Agent, Knowledge Base, Data Source)

Create a test agent:

```python
docker compose exec -T api python3 -c "
import urllib.request, json

TOKEN = '<paste access_token here>'
payload = json.dumps({
    'agent_type': 'llm',
    'api_key': 'dummy-test-key-12345',
    'config': {
        'name': 'Dashboard Stats Test Agent',
        'description': 'temp agent for /dashboard page test doc',
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

Verified (`201`):
```json
{"success":true,"message":"Agent 'Dashboard Stats Test Agent' created successfully","data":{"agent_id":"145ec0a2-9239-42e5-9ffe-133d49d3c6b9","agent_name":"Dashboard Stats Test Agent","slug":"dashboard-stats-test-agent"}}
```

Create a test knowledge base:

```python
docker compose exec -T api python3 -c "
import urllib.request, json

TOKEN = '<paste access_token here>'
payload = json.dumps({'name': 'Dashboard Stats Test KB', 'description': 'temp KB for /dashboard page test doc'}).encode()
req = urllib.request.Request(
    'http://localhost:5001/api/v1/knowledge-bases',
    data=payload,
    headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())
"
```

Verified (`201`), returns `id: 1` plus `name`, `created_at`, `updated_at`, etc.

Create a test data source (requires a `knowledge_base_id`, so run this after the KB above):

```python
docker compose exec -T api python3 -c "
import urllib.request, json

TOKEN = '<paste access_token here>'
payload = json.dumps({'name': 'Dashboard Stats Test Source', 'type': 'MANUAL', 'knowledge_base_id': 1, 'config': {}}).encode()
req = urllib.request.Request(
    'http://localhost:5001/api/v1/data-sources',
    data=payload,
    headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
    method='POST'
)
with urllib.request.urlopen(req) as r:
    print(r.status, r.read().decode())
"
```

Verified (`201`), returns `id: 1` plus `name`, `type`, `created_at`, `updated_at`, etc.
`type` must be one of the `DataSourceType` enum values (`MANUAL`, `SLACK`, `WEB`, `JIRA`, ... —
see `api/src/models/data_source.py`).

---

## Step 4 — Re-fetch and Verify Stat Cards + Recent Activity Data

```python
docker compose exec -T api python3 -c "
import urllib.request, json

TOKEN = '<paste access_token here>'

def get(path):
    req = urllib.request.Request(f'http://localhost:5001{path}', headers={'Authorization': f'Bearer {TOKEN}'}, method='GET')
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

agents = get('/api/v1/agents/')
kbs = get('/api/v1/knowledge-bases')
ds = get('/api/v1/data-sources')

print('Total Agents stat (pagination.total):', agents['data']['pagination']['total'])
print('agents_list[0].agent_name (used for activity feed):', agents['data']['agents_list'][0]['agent_name'])
print('agents_list[0].created_at (used for activity feed):', agents['data']['agents_list'][0]['created_at'])
print('Knowledge Bases stat (list length):', len(kbs))
print('Data Sources stat (list length):', len(ds))
"
```

Verified:
```
Total Agents stat (pagination.total): 1
agents_list[0].agent_name (used for activity feed): Dashboard Stats Test Agent
agents_list[0].created_at (used for activity feed): 2026-08-13T13:27:29.509062+00:00
Knowledge Bases stat (list length): 1
Data Sources stat (list length): 1
```

This confirms, post-fix, the Recent Activity feed's "Agent created" entry will correctly show
`Dashboard Stats Test Agent` and a real relative timestamp instead of `undefined` / `Recently`.

---

## Step 5 — Graceful Degradation When an Endpoint Fails

Each of the 4 calls has its own `.catch()`, so a single failing endpoint falls back to an empty
result instead of crashing the whole page. Verify with an invalid token:

```python
docker compose exec -T api python3 -c "
import urllib.request, urllib.error

req = urllib.request.Request(
    'http://localhost:5001/api/v1/mcp/servers',
    headers={'Authorization': 'Bearer invalid-token'},
    method='GET'
)
try:
    with urllib.request.urlopen(req) as r:
        print(r.status, r.read().decode())
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode())
"
```

Verified: `401` (`{"detail":"..."}`, invalid token rejected by auth middleware) — with a real
session this only happens if the access token has expired mid-page-load; the frontend's
`.catch(() => [])` on `getMCPServers()` means the "MCP Servers" stat card would show `0` rather
than the page erroring out.

---

## Cleanup

```python
docker compose exec -T api python3 -c "
import urllib.request

TOKEN = '<paste access_token here>'

def delete(path):
    req = urllib.request.Request(f'http://localhost:5001{path}', headers={'Authorization': f'Bearer {TOKEN}'}, method='DELETE')
    with urllib.request.urlopen(req) as r:
        return r.status, r.read().decode()

print('agent:', delete('/api/v1/agents/dashboard-stats-test-agent'))
print('data source:', delete('/api/v1/data-sources/1'))
print('knowledge base:', delete('/api/v1/knowledge-bases/1'))
"
```

Verified: agent delete `200`, data source delete `204`, knowledge base delete `204`. Confirmed
tenant back to `0` agents / `[]` knowledge bases / `[]` data sources afterward.

---

## Endpoint Reference

| Purpose | Method | Path | Auth required | Used for |
|---------|--------|------|----------------|----------|
| List agents | GET | `/api/v1/agents/` | Bearer token | "Total Agents" stat + Recent Activity |
| List knowledge bases | GET | `/api/v1/knowledge-bases` | Bearer token | "Knowledge Bases" stat + Recent Activity |
| List data sources | GET | `/api/v1/data-sources` | Bearer token | "Data Sources" stat + Recent Activity |
| List MCP servers | GET | `/api/v1/mcp/servers` | Bearer token | "MCP Servers" stat |

## Notes

- The agents list endpoint returns **both** `agents` (name strings only) and `agents_list` (full
  objects) in its `data` payload. Any frontend code that needs agent fields (`agent_name`,
  `created_at`, `slug`, etc.) must use `agents_list`, never `agents`. This is the same underlying
  field this page's bug was rooted in.
- `knowledge-bases` and `data-sources` list endpoints return plain arrays directly (no `data`
  wrapper, no pagination) — different response convention from the agents endpoint.
- Data source creation requires an existing `knowledge_base_id` (foreign key) — create the KB
  first if setting up a fresh test scenario.
- Dashboard's `apiClient.getAgents()` call passes no `page_size`, so the backend's own default
  (`10`) applies — different from the `/agents` listing page (`page_size=9`, see
  `agent-test-docs/agents-list-page-test-guide.md`).
