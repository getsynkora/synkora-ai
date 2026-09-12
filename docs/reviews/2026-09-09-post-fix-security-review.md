# Post-fix application security review

Remediation update: the findings below were subsequently addressed. See [authentication-path remediation](2026-09-09-auth-path-remediation.md) for changes, validation and rollout notes. The original findings are retained as baseline evidence.

Reviewed 9 September 2026. Scope: current working-tree code, recent fixes, alternative authentication paths, OAuth ownership, S3 tenant isolation and Recall retry behavior. Infrastructure and production configuration were excluded. This was a targeted follow-up review, not an exhaustive penetration test.

## Summary

Three high-priority application findings remain. The recent fixes pass their regression tests, but authentication enforcement is inconsistent across entry points. The earlier completion summary overstated how widely the account-version protection was enforced.

### 1. High: anonymous OAuth flow can replace an integration's credentials

Evidence: `api/src/controllers/oauth/github.py:42` accepts an absent account and tenant for app-level authorization. `_get_oauth_app_secure` in `api/src/controllers/oauth/base.py:107` checks ownership only when a tenant is supplied. The callback at `github.py:129` trusts the state created by that anonymous request; its app-level branch assigns the new provider token and commits. Router registration adds no shared authentication dependency.

Plain-English example: someone who knows an OAuth app ID can start connecting their own GitHub account to that app. If they complete the provider's authorization flow, the callback can replace another company's stored integration credentials. This demonstrates unauthorized credential replacement, not theft of the old token or takeover of the company's GitHub account.

Local proof: the actual authorize and callback functions accepted an anonymous request, created state with no account identity, replaced a synthetic tenant-owned app's token, and committed once. Database, Redis state storage and GitHub responses were mocked; no real credentials or provider accounts were touched. Provider consent/code exchange remains an exploitation prerequisite. Similar provider routes use the same helper, but their complete flows were not individually reproduced.

Fix first: require an authenticated, currently authorized tenant member with permission to manage integrations before creating state; bind state to that account and tenant; recheck authorization at callback before writing. Preserve deliberately public login flows separately from integration-management flows. Platform-app callbacks must never fall back to writing shared credentials when tenant identity is missing.

### 2. High: handoff API bypasses current account and membership checks

Evidence: `api/src/middleware/agent_api_auth.py:353` decodes a JWT and returns its tenant claim. It does not consult account status, current membership, the blacklist, Redis revocation version or database authentication version. Handoff routes use this dependency, including conversation history at `api/src/controllers/agents/handoff.py:206` and handoff management routes.

Plain-English example: a staff member removed from a company, or someone holding a revoked but unexpired token, can still pass this authentication dependency for the old company. The routes can expose conversation history or allow handoff actions because their tenant check trusts the returned claim.

Local proof: a genuinely signed synthetic access token was accepted and its tenant returned with zero database calls. Code inspection confirms there is also no revocation-service call. Existing tenant filtering does prevent choosing an arbitrary different tenant; this finding concerns continued access to the tenant in the previously issued token.

Fix first: route account JWTs through the same active-account, access-token, revocation and current-membership validation as protected HTTP endpoints. Retain API-key support with explicit management permissions.

Related medium-priority exposure: portal listing and members-only detail at `api/src/controllers/portal.py:188` and `:247` also trust a decoded tenant claim without current membership/revocation checks. This is confirmed by code inspection, not a separate runtime reproduction. Apply the shared validation there too.

### 3. High: WebSocket chat misses authentication-version and membership enforcement

Evidence: `api/src/controllers/agents/chat.py:720` checks JWT decoding and Redis revocation, then loads an active account. It does not compare `av` to `account.auth_version` or verify current tenant membership. After `auth_ok`, the message loop at `:765` keeps the original identity without rechecking expiry, revocation or membership before later chats.

Plain-English example: someone removed from a company can continue using a connection that is already open. The recent reset protection also does not cover this entry point when a token has the current Redis version but an outdated database authentication version.

Local proof: the actual WebSocket handler sent `auth_ok` for a synthetic token at database authentication version zero while the modeled account was at version one. Redis allowed the token, and the account was active. The handler made only the account query. The probe did not invoke a real model or execute an agent tool; continued message dispatch without revalidation is established by code inspection.

Fix first: share authentication and membership validation with HTTP, enforce the durable version at handshake, and revalidate authorization before each new chat turn on a long-lived socket.

## What remains verified

Fresh run: **60 tests passed** covering tenant storage, the controlled reset/login race, transactional Recall rollback/retry, security-remediation controller cases and shared authentication middleware. This verifies those tested paths, not every alternate endpoint.

The local diagnostic script is `docs/reviews/probes/review_auth_paths.py`; it uses synthetic credentials and mocked external boundaries. Reproduce from the repository root:

```sh
PYTHONPATH=api /private/tmp/synkora-harness-validation/bin/python docs/reviews/probes/review_auth_paths.py
```

The Python interpreter path refers to this workspace's temporary validation environment. Its diagnostic output confirms:

```json
{"handoff":{"tenant_accepted":true,"database_checks":0},"websocket":{"stale_account_version_accepted":true,"database_queries":1},"oauth":{"anonymous_start_status":307,"state_has_account":false,"foreign_app_token_replaced":true,"commits":1}}
```

Prior same-day dependency audits reported zero Python findings and zero frontend production findings with existing frontend exclusions unchanged. Those audits and the frontend build were not rerun during this review; no dependency or frontend code changed in this turn.

No application fixes or production changes were made in this review. Only this report and the local diagnostic probe were added. The previously added database migration still needs application before deployment of those earlier fixes. A production PostgreSQL concurrency test and live provider integration tests remain outside the evidence collected here.
