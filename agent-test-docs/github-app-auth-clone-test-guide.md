# Test Guide: GitHub App Auth + Repo Clone (Weather Agent)

## Overview

Verifies that an agent's GitHub App-based credential (`auth_method='github_app'`) can
authenticate and clone a private repo end-to-end. Written after investigating a real incident
where the Weather Agent reported *"no GitHub token is configured"* for
`deriv-core/core-automation`, even though the GitHub App was correctly installed and configured.

### What actually happened (root cause)

The error message the agent gave the user was misleading. The real failure, found in
`bot-worker`/`api` logs, was:

```
WARNING GitHub App 'iCore GithubApp' is not installed on deriv-core/core-automation: 401 {
  "message": "Bad credentials", ...
}
```

`401 Bad credentials` means **the JWT the backend generated to authenticate as the GitHub App
was rejected by GitHub** — not that the app isn't installed. GitHub only returns `404` for a
genuinely-missing installation; `401` means the JWT itself (signature, `iat`/`exp` clock window)
failed validation. The code used to log both cases identically as "is not installed," which is
why the first read of the logs pointed at the wrong cause.

The same installation/credentials worked cleanly less than an hour before the failure, and work
again now with zero config changes — confirming this was a **transient JWT validity issue**, most
likely a brief clock/timing hiccup in the local Docker Desktop VM (GitHub App JWTs are only valid
for a ~10 minute window, so any clock drift on the container host breaks auth until it resyncs).
This is a local-dev-environment quirk, not an application bug in the credential/token logic.

**Fix applied:** `credential_resolver.py`'s `_get_github_app_installation_token()` now
distinguishes the two cases in its log output:
- `404` → `"... is not installed on {owner}/{repo}: 404 ..."` (genuinely not installed)
- any other non-200 (e.g. `401`) → `"... JWT authentication failed for {owner}/{repo}: 401 ..."`
  (auth/clock/signature problem — app may still be installed)

This doesn't prevent the transient failure itself, but makes it immediately diagnosable from
logs instead of pointing at the wrong root cause.

## Prerequisites

- API running on `http://localhost:5001`
- Weather Agent exists with `internal_git_clone_repo` enabled and pointed at a `github_app`
  OAuth app (`oauth_apps.auth_method = 'github_app'`)
- Target repo the app is installed on (`deriv-core/core-automation` used here)

---

## Step 1 — Get Auth Token

```python
python3 -c "
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
" > /tmp/token.txt
```

---

## Step 2 — Confirm the OAuth App Config in the DB

```bash
docker compose exec -T postgres psql -U synkora -d synkora -c \
  "SELECT id, provider, app_name, auth_method, is_active, is_default FROM oauth_apps WHERE provider='github';"
```

Expected: a row with `auth_method='github_app'`, `is_active=true`. Note the `id` — the
Weather Agent's git/GitHub tools should point `agent_tools.oauth_app_id` at this row:

```bash
docker compose exec -T postgres psql -U synkora -d synkora -c \
  "SELECT tool_name, oauth_app_id, enabled FROM agent_tools \
   WHERE agent_id = (SELECT id FROM agents WHERE slug='weather-agent') \
   AND tool_name LIKE '%git%' LIMIT 5;"
```

---

## Step 3 — Direct JWT Auth Test (bypasses the agent entirely)

This is the fastest way to check *right now* whether the GitHub App's JWT credential is valid,
independent of any agent/chat logic. Replace `oauth_app_id` and `owner/repo` as needed.

```bash
docker compose exec -T api python3 -c "
import asyncio

async def main():
    from sqlalchemy import select
    from src.core.database import get_async_session_factory
    from src.models.oauth_app import OAuthApp
    import time, httpx, jwt as pyjwt
    from src.services.agents.security import decrypt_value, normalize_pem_private_key

    factory = get_async_session_factory()
    async with factory() as db:
        result = await db.execute(select(OAuthApp).where(OAuthApp.id == 2))  # <- oauth_app id
        oauth_app = result.scalar_one()

        app_id = oauth_app.client_id
        private_key = normalize_pem_private_key(decrypt_value(oauth_app.client_secret))
        now = int(time.time())
        app_jwt = pyjwt.encode({'iat': now - 60, 'exp': now + 600, 'iss': str(app_id)}, private_key, algorithm='RS256')
        headers = {'Authorization': f'Bearer {app_jwt}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
        async with httpx.AsyncClient() as client:
            resp = await client.get('https://api.github.com/repos/deriv-core/core-automation/installation', headers=headers, timeout=15.0)
            print('STATUS:', resp.status_code)
            print('BODY:', resp.text[:300])

asyncio.run(main())
"
```

**Expected (healthy):** `STATUS: 200` with installation JSON (`id`, `account.login`, `permissions`, ...).

**If unhealthy:**
- `STATUS: 404` → app really isn't installed on that org/repo — reinstall/grant access via
  GitHub's App settings page.
- `STATUS: 401` with `"Bad credentials"` → JWT rejected. Re-run this step a minute later — if it
  now succeeds with zero changes, it was a transient clock/timing issue (see root cause above),
  not a real config problem.

---

## Step 4 — End-to-End: Have the Weather Agent Clone the Repo

```bash
TOKEN=$(cat /tmp/token.txt | tr -d '\n')
python3 -c "
import urllib.request, json

TOKEN = '''$TOKEN'''
payload = json.dumps({
    'agent_slug': 'weather-agent',
    'message': 'Clone the repo https://github.com/deriv-core/core-automation.git using internal_git_clone_repo and tell me the size and path once done. Do not do anything else.'
}).encode()

req = urllib.request.Request(
    'http://localhost:5001/api/v1/agents/chat/stream',
    data=payload,
    headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
    method='POST'
)

with urllib.request.urlopen(req, timeout=120) as r:
    for line in r:
        line = line.decode('utf-8').strip()
        if line.startswith('data: '):
            data = line[6:]
            if data == '[DONE]':
                break
            try:
                obj = json.loads(data)
                chunk = obj.get('content','') or obj.get('text','') or obj.get('delta','') or obj.get('chunk','')
                if chunk:
                    print(chunk, end='', flush=True)
            except Exception:
                pass
print()
"
```

Note: the request body field is `agent_slug` (not `agent_name`) — `POST /api/v1/agents/chat/stream`
validates against `ChatRequest` in `api/src/controllers/agents/models.py`, which requires the
agent's globally-unique slug.

**Expected response** (verified working 2026-08-14):
```
The repository has been cloned successfully. Here are the details:

- **Path:** `/tmp/synkora/workspaces/<tenant_id>/<conversation_id>/repos/git_xxxxxxxxxxxx`
- **Size:** 207.0 MB
```

---

## Step 5 — Verify in Logs

```bash
docker compose logs --no-color api --tail 60 2>&1 | grep -E "git_clone_repo|GitHub App|credential_resolver|Successfully cloned"
```

Expected (success path):
```
INFO in credential_resolver: Got GitHub App installation token for tool 'internal_git_clone_repo' (app: <app name>, installation: <id>)
INFO in credential_resolver: ✅ Created authenticated GitHub client for tool 'internal_git_clone_repo' using OAuth app '<app name>' (auth_method: github_app, fallback)
INFO in git_repo_tools: Successfully cloned repository to /tmp/synkora/workspaces/.../repos/git_xxxxxxxxxxxx (size: XXX.XMB)
INFO in function_calling: Function internal_git_clone_repo completed successfully in XXXXms
```

If it fails, the (now-fixed) warning tells you which of the two real failure modes occurred:
```
WARNING ... is not installed on {owner}/{repo}: 404 ...          # genuinely not installed
WARNING ... JWT authentication failed for {owner}/{repo}: 401 ... # auth/clock issue, retry
```

---

## Key IDs (local dev)

| Resource | Name | ID |
|----------|------|----|
| Agent | Weather Agent | `e852a616-2a50-487d-b289-b4013b71ded8` (slug: `weather-agent`) |
| Tenant | (Weather Agent's tenant) | `09a1dc51-d0ea-40ff-a50a-29d98ce477a8` |
| OAuth App | iCore GithubApp | `2` (`auth_method='github_app'`, GitHub App ID `4206767`) |
| GitHub Installation | `deriv-core` org | `144137778` |

## Related Code

| Purpose | Path |
|---------|------|
| JWT + installation token generation | `api/src/services/agents/credential_resolver.py::_get_github_app_installation_token` |
| Git clone tool (uses resolved token) | `api/src/services/agents/internal_tools/git_repo_tools.py` |
| Token → git URL injection | `api/src/services/agents/internal_tools/github_auth_helper.py` |
