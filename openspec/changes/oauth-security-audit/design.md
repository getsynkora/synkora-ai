## Context

The OAuth integration spans 15+ providers, two token storage layers (app-level and user-level), a platform app clone mechanism, Redis-backed state management, and a runtime credential resolver used by all agent tools. The full read of the codebase during explore mode revealed the following architecture:

- `controllers/oauth/base.py` — generic initiation, IDOR protection, platform clone, redirect helpers
- `controllers/oauth/<provider>.py` — per-provider authorize + callback + disconnect endpoints
- `services/oauth/base_oauth.py` + per-provider implementations — token exchange, user info, refresh, revoke
- `services/security/oauth_state_service.py` — Redis-backed state (10 min TTL, single-use getdel)
- `services/security/oauth_security.py` — redirect URL validation, error URL builder
- `services/agents/credential_resolver.py` — runtime token resolution for agent tools
- `models/oauth_app.py` — credentials encrypted at rest; supports oauth / api_token / github_app auth methods
- `models/user_oauth_token.py` — per-user tokens alongside app-level tokens

This audit covers every layer.

---

## Goals / Non-Goals

**Goals:**
- Identify and fix all exploitable security vulnerabilities (CSRF, open redirect, IDOR, cross-tenant leakage, token theft)
- Identify and fix correctness bugs that degrade security guarantees (state double-consumption, TTL refresh, sync-in-async)
- Establish security requirements (specs) that can be tested and regression-prevented
- Add defense-in-depth where single-point failures exist (e.g., credential resolver tenant check)

**Non-Goals:**
- Adding new OAuth providers
- Changing the fundamental architecture (Redis state, platform clone, two-layer token storage)
- Frontend OAuth UI changes
- Rate limiting on OAuth endpoints (separate concern)

---

## Decisions

### Decision 1: Fix sync Redis in async context
`oauth_state_service.py` uses `get_redis()` (sync client) in async FastAPI handlers. This blocks the event loop under load. Fix: use `get_redis_async()` with an async pipeline or `await redis.setex(...)`. All methods in `OAuthStateService` become async.

**Alternative considered**: wrap in `run_in_executor`. Rejected — adds thread pool pressure and is the exact anti-pattern Pass 7 already fixed in auth_middleware.

### Decision 2: Fix error-path state consumption
In callback handlers (e.g., `github_callback`), the `except` block calls `get_oauth_state(state, delete=False)` to recover the redirect URL, but the state was already consumed by the `try` block's `get_oauth_state(state)` call. Result: error redirects always go to the default path.

Fix: capture `redirect_url` from state_data in the `try` block before any async operation, and use a nonlocal/outer variable in the `except` block. No second Redis call needed.

### Decision 3: Add tenant_id filter in credential_resolver OAuthApp lookup
`get_github_client` (and similar methods) fetch `OAuthApp` by `id` only — no `tenant_id` check. While the upstream `agent_tool` is tenant-validated, defense-in-depth requires the OAuthApp query to also filter by the agent's tenant. Fixes a single-layer IDOR risk.

Fix: add `OAuthApp.tenant_id == self.context.tenant_id` (or `OAuthApp.is_platform_app == True` for platform apps) to every OAuthApp fetch in the resolver.

### Decision 4: Prevent TTL refresh in update_oauth_state
`update_oauth_state` calls `store_state` which calls `setex` again, resetting the 10-minute TTL. For PKCE flows, this means the state lifetime is measured from the last update, not creation.

Fix: use Redis `GETEX` / direct `SET` with the remaining TTL rather than a fresh `setex`. Compute `remaining_ttl = OAUTH_STATE_TTL_SECONDS - (now - created_at)` and use that. If `remaining_ttl <= 0`, treat the update as expired.

### Decision 5: Validate platform_app_id type consistency
`_get_or_create_tenant_clone` queries `OAuthApp.config["platform_app_id"].as_string() == str(platform_app.id)`. If a clone was previously created with an integer JSON value rather than a string, the query misses it and a duplicate clone is created. Fix: normalize to string on write and handle both types on read.

### Decision 6: Token refresh coverage
Most providers store `refresh_token` on `OAuthApp.refresh_token` but no background task or middleware auto-refreshes. The credential resolver has one-off refresh for Google Calendar. A minimal fix: add a `_refresh_if_expired()` helper in the resolver that providers with known expiry (Google, Jira, Zoom, HubSpot, Salesforce, Intercom) can opt into. GitHub, Slack, and API-token providers are excluded (tokens don't expire by default or have no refresh grant).

---

## Risks / Trade-offs

- **async oauth_state_service** — Changing sync → async affects every caller in all 15 callback controllers. Risk: one missed `await`. Mitigation: grep all call sites, update tests.
- **Tenant filter in resolver** — If `context.tenant_id` is None (e.g., background task context), the filter could incorrectly block valid platform app access. Mitigation: allow platform apps explicitly (`OAuthApp.tenant_id == tenant_id OR OAuthApp.is_platform_app == True`).
- **TTL preservation** — Redis `OBJECT IDLETIME` is not the same as remaining TTL. Must use `TTL` command directly. Available on all Redis versions we target.
- **Duplicate clone fix** — Normalizing `platform_app_id` to string requires a migration or dual-read. Dual-read (`CAST` + `OR`) is safer than a data migration.

---

## Migration Plan

All fixes are backward-compatible — no schema changes, no API changes. Deploy steps:
1. Merge and deploy API changes (async state service, callback fixes, resolver hardening, clone fix)
2. No migration needed; existing Redis state keys will expire naturally (10 min TTL)
3. Verify via existing OAuth flow tests + new unit tests

Rollback: revert to prior commit; no state incompatibility since Redis keys auto-expire.

---

## Open Questions

- Should `UserOAuthToken` gain a `token_expires_at` column to support expiry-aware refresh for user-level tokens? (Out of scope for this audit — track separately)
- Should we add observability (metric/alert) when an OAuth state is not found in Redis (possible CSRF attempt)? (Recommended future work)
- Twitter's PKCE `code_verifier` is stored in Redis state — is 10-minute TTL sufficient for the PKCE exchange window? (Yes, PKCE exchange happens immediately after redirect, so this is fine)
