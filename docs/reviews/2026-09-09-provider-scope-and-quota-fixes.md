# Provider scope and quota fixes

Date: 2026-09-09

All three findings in [the preceding review](2026-09-09-provider-scope-and-quota-review.md) have application-code fixes and regression coverage. No production configuration, infrastructure or deployed services were changed.

## What changed

1. **Connection ownership:** saving a tool and assigning single/bulk capabilities validates all supplied OAuth connection IDs against the current tenant or an active platform app before mutating tools. Missing, inactive and foreign private connections receive the same 404 response. Every OAuth app lookup in `CredentialResolver` now uses a shared authorization query, protecting previously saved configurations as well as new assignments. Missing tenant identity returns no app. Platform connections outside the current tenant are usable only as OAuth templates with no stored access, refresh or API token.
2. **Personal identity:** the older personal-token helper delegates to the current-member-only query. It never selects another member's token when the current user has no connection. User-less execution cannot borrow personal credentials. GitLab's personal-token return path supports both current and legacy double-encrypted values.
3. **Atomic quotas:** one Redis Lua invocation checks all three sliding windows and reserves the request atomically. Random request IDs prevent requests with identical timestamps from collapsing into a single quota entry. Existing Redis keys are retained so deployment does not reset accumulated quota. Redis errors continue to propagate to the failure-closed authentication handling.

## Practical compatibility

- Tenant-owned shared provider connections remain supported. Background agents need one of these explicitly configured connections, or a mapped user with their own personal connection.
- Shared platform apps containing runtime tokens, or using non-OAuth authentication, cannot supply credentials across tenants. Such connections need tenant-owned configuration. Existing foreign connection assignments fail at use time; no production records were silently rewritten.
- No database migration is added by these fixes.
- The quota implementation was verified against standalone Redis. Its three-key Lua operation requires keys on the same Redis node; Redis Cluster cross-slot compatibility was not established. No production Redis topology was assumed or modified.

## Verification

**200 distinct tests passed:** 196 in the final selected backend run, plus four real-Redis quota tests run separately outside the sandbox because sandbox restrictions prevented creating the local socket.

New tests execute actual SQLite authorization queries for owned, foreign, inactive, missing and platform-template connections; reject a foreign assignment before commit; check current-member-only lookup; and validate both GitLab personal-token formats. Real Redis tests use a temporary private Unix socket, disabled persistence, and terminate the process afterward. Each minute/hour/day quota test accepted exactly one of 32 concurrent requests against a limit of one. Additional coverage verifies window expiry and distinct requests sharing a timestamp.

Existing handoff, OAuth authorization, credential resolver, API-key and migration regression coverage passed. Ruff checks and `git diff --check` passed.

Three existing credential-resolver cases requiring the unavailable local PostgreSQL fixture or the known Google SDK environment dependency mismatch were excluded. The four Redis tests were excluded from the final sandbox run because they had already passed separately. Existing test-client deprecation and AsyncMock warnings remain in the validation environment. No external provider calls, live tenant credentials, production Redis or deployment checks were performed.

The earlier review probe is historical evidence of the bypasses; its mocks assume the pre-fix queries and non-atomic Redis interface. The regression tests are the post-fix verification contract.
