# Credential boundary fixes — 9 September 2026

Both findings in `2026-09-09-credential-boundary-review.md` are addressed in application code. Production has not been deployed or modified.

## Handoff API-key authorization

Handoff authentication now returns a structured identity containing the tenant, permitted agent and key permissions. All seven routes retain that identity. Lists, detail/history reads and mutations use the same tenant-and-agent-scoped conversation query before loading messages or writing changes.

- `handoff:read` permits handoff listing, detail and conversation history.
- `handoff:write` permits replies, assignment, resolution and reopening.
- Read and write grants are independent. Chat/history/conversations permissions alone do not grant handoff access.
- Existing `*` keys retain all-operation permission, but remain restricted to their agent. Keys without an agent cannot use handoff endpoints.
- Dashboard key-creation forms expose both handoff permissions, unselected by default.

Account JWTs continue using the current account, membership and revocation checks introduced in the previous remediation. No automatic permission grants were applied to existing keys.

## Personal Salesforce and Jira settings

New nullable `UserOAuthToken.provider_config` stores destination settings with the personal token. Personal callbacks update that record, including when using a platform OAuth app; they no longer change shared `OAuthApp.config`.

Salesforce and Jira credential resolution selects the current member's personal record and uses its destination with its token. It does not select another user's personal connection when that identity is absent. App-level fallback uses the tenant app's own destination and token; shared platform templates are not used as a token fallback. Jira token refresh preserves the personal destination, and refresh failure cannot pair an app token with the personal destination.

The application migration `20260909_0002_personal_oauth_settings.py` adds the JSON field after `20260909_0001`. Existing personal destinations remain NULL: copying shared configuration would guess which destination belonged to which token.

## Verification

- **500 selected backend tests passed**, including the earlier security/authentication suites, all OAuth authorization regression tests, the new personal-setting tests and existing Jira refresh tests.
- Handoff tests cover denial of chat/history/conversations-only keys across all seven routes, permitted operations, read/write separation, scoped 404 responses, and real SQLite SQL execution proving that normal and wildcard keys cannot select another agent or tenant.
- Personal callback tests cover both providers, new and existing personal tokens, and tenant-owned/platform apps. They verify that shared settings and tokens remain unchanged, then call the credential resolver and verify the correct personal destination/token pair.
- Migration upgrade, NULL preservation, JSON roundtrip and downgrade passed on isolated SQLite. Alembic has one head, `20260909_0002`.
- **123 frontend tests passed**. TypeScript, targeted ESLint, Python Ruff, `git diff --check` and the production webpack build passed.

A broader credential-resolver test run encountered two unrelated Google SDK tests failing on the temporary environment's `httplib2`/`pyparsing` incompatibility and one database-backed token roundtrip test unable to connect to local PostgreSQL on port 5439. Those failures were not counted as passes. The affected Jira tests and new security suites passed separately. No live Salesforce/Jira calls or production PostgreSQL validation were performed.

## Rollout requirements

1. Apply migration `20260909_0002` and its predecessors before starting the updated API.
2. Grant the needed explicit handoff permissions to integrations that should retain handoff access, or create appropriately scoped replacement keys. No existing keys were silently expanded.
3. Reconnect existing personal Salesforce/Jira connections so their own destinations are verified and stored. Legacy personal records without destination settings fail closed. Background jobs without a current user should use an explicitly configured tenant-wide connection.

The migration does not reconstruct previously overwritten shared configuration; recovering such values requires verified provider settings. Infrastructure/configuration files were not changed in this turn, and preexisting workspace changes were preserved. Historical diagnostic probes remain baseline evidence; the new regression tests describe the fixed behavior.
