## 1. OAuth State Service — Async + TTL Fix

- [ ] 1.1 Rewrite `OAuthStateService.store_state` to use `await redis.setex(...)` (async Redis client via `get_redis_async()`)
- [ ] 1.2 Rewrite `OAuthStateService.retrieve_state` to use `await redis.getdel(...)` for atomic single-use deletion
- [ ] 1.3 Rewrite `OAuthStateService.validate_state` and `delete_state` to use async Redis
- [ ] 1.4 Fix `update_oauth_state`: use `await redis.ttl(key)` to get remaining TTL, then `await redis.setex(key, remaining_ttl, ...)` instead of full `OAUTH_STATE_TTL_SECONDS`; return False if remaining TTL <= 0
- [ ] 1.5 Update all module-level convenience functions (`create_oauth_state`, `get_oauth_state`, `update_oauth_state`) to be async
- [ ] 1.6 Update all 15 provider callback handlers and `base.py:initiate_oauth` to `await` the now-async state functions

## 2. Callback Error Path Fix

- [ ] 2.1 In each callback handler (`github_callback`, `slack_callback`, etc.), capture `redirect_url` into a local variable immediately after `get_oauth_state` returns
- [ ] 2.2 Remove the second `get_oauth_state(state, delete=False)` call from all `except` blocks — use the pre-captured `redirect_url` instead
- [ ] 2.3 Verify the same fix is applied to all 15 provider callbacks (grep for `get_oauth_state` in except blocks)

## 3. Credential Resolver — Tenant Guard

- [ ] 3.1 In `CredentialResolver.get_github_client`: add `(OAuthApp.tenant_id == self.context.tenant_id) | (OAuthApp.is_platform_app == True)` to the OAuthApp SELECT query
- [ ] 3.2 Apply the same tenant guard to all other provider client getters in `credential_resolver.py` (Slack, Gmail, Google Drive, Google Calendar, Jira, HubSpot, Intercom, Salesforce, LinkedIn, Twitter, ClickUp, Zoom, Zendesk, Zoho)
- [ ] 3.3 Handle `context.tenant_id is None` (background task context): restrict to platform apps only, log warning for tenant-owned app attempts

## 4. Platform Clone Type Safety

- [ ] 4.1 In `_get_or_create_tenant_clone`, ensure `config["platform_app_id"]` is stored as `str(platform_app.id)`
- [ ] 4.2 Update the clone lookup query to handle both string and integer JSON values using SQLAlchemy `cast` or an OR condition: `config["platform_app_id"].as_string() == str(id) OR config["platform_app_id"].as_integer() == id`
- [ ] 4.3 Write a unit test covering the case where an existing clone has integer `platform_app_id` and verify no duplicate is created

## 5. Token Refresh — Expiry-Aware Providers

- [ ] 5.1 Add `_refresh_if_expired(oauth_app)` helper to `CredentialResolver`: checks `token_expires_at`, calls provider's `refresh_token()` if expired, persists updated token
- [ ] 5.2 Integrate `_refresh_if_expired` into the app-level token fetch for Google Calendar, Google Drive, Gmail (already partially done — consolidate)
- [ ] 5.3 Integrate `_refresh_if_expired` for Jira, Zoom, HubSpot, Salesforce, Intercom (all issue short-lived tokens with refresh grants)
- [ ] 5.4 Skip refresh for GitHub, Slack, API-token, and github_app providers (tokens don't expire or have no refresh grant)

## 6. Scope Governance

- [ ] 6.1 Audit each provider's hardcoded default scopes in `base.py:initiate_oauth` and in provider-specific authorize endpoints; update to least-privilege defaults (document rationale in code comments)
- [ ] 6.2 After token exchange, check if provider response includes a `scope` field; if present and it differs from requested scopes, log a warning with provider, requested, and granted scope lists
- [ ] 6.3 Add scope mismatch logging to providers that return scope in token response: Slack, Google, Jira, LinkedIn, Zendesk, HubSpot, Salesforce, Intercom, Zoho

## 7. Tests

- [ ] 7.1 Unit tests for `oauth_state_service.py`: state creation, single-use retrieval, TTL preservation on update, expired state handling
- [ ] 7.2 Unit tests for `oauth_security.py`: valid domain, subdomain, localhost, external domain rejection, ENV var override
- [ ] 7.3 Unit tests for `credential_resolver.py`: tenant guard blocks cross-tenant app, user token priority over app token, refresh triggered on expired token
- [ ] 7.4 Unit tests for `_get_or_create_tenant_clone`: integer platform_app_id in existing clone returns existing (no duplicate), first-time creates clone with string type
- [ ] 7.5 Integration test: full callback flow where token exchange fails — verify error redirect uses captured `redirect_url` not default

## 8. Verification

- [ ] 8.1 Run `ruff check api/src/controllers/oauth/ api/src/services/oauth/ api/src/services/security/` — fix any lint errors introduced
- [ ] 8.2 Run `pytest tests/unit/services/agents/ tests/unit/middleware/ -v` — all pass
- [ ] 8.3 Run `basedpyright api/src/controllers/oauth/ api/src/services/oauth/ api/src/services/security/` — no type errors
- [ ] 8.4 Manual smoke test: complete GitHub OAuth flow (authorize → callback → token stored on correct row)
- [ ] 8.5 Manual smoke test: platform app GitHub OAuth flow (authorize → callback → tenant clone created, token on clone)
