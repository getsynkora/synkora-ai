# Non-OAuth connection security re-review

Status: Confirmed and fixed in application code. See [fixes and SQL-backed verification](2026-09-09-non-oauth-connection-fixes.md). The findings below describe the pre-fix state.

Date: 2026-09-09

## Summary

**Two high-priority paths remain vulnerable to cross-tenant credential use.** Both have the same root cause: the latest assignment authorization covers `oauth_app_id`, but not `slack_bot_id` or `custom_tool_id`. Their runtime consumers also omit ownership checks. The previous OAuth fix is present; it did not cover these different connection types.

Fix both paths before considering connection isolation complete. Centralize authorization for all referenced connection types and enforce it again when loading credentials or tools, including existing saved assignments.

## 1. High — foreign Slack bot can be pinned to an agent

Locations:
- `api/src/controllers/agents/tools.py:193–223`: validates OAuth IDs, then stores the supplied Slack bot UUID without validating its tenant.
- `api/src/services/agents/credential_resolver.py:1555–1567`: pinned-bot lookup checks ID and connection status, but not tenant or agent ownership; decrypts and returns its bot token.
- `api/src/services/agents/internal_tools/slack_tools.py:64`: live tool path calls the resolver.

**Plain-English example:** a company A user who can configure an agent supplies the ID of company B's connected Slack bot. The agent can use company B's Slack identity, within that bot token's granted permissions.

**Reproduction:** the actual save controller accepted a synthetic foreign bot UUID. The actual Slack resolver then returned the modeled foreign bot's synthetic decrypted token. The bot lookup had no tenant parameter. No Slack request was sent.

**Prerequisites:** authenticated agent-configuration access, knowledge of a foreign bot UUID, and a connected bot with a usable token. UUID discovery was not demonstrated; UUID secrecy is not a replacement for ownership authorization. Database results were modeled, not fetched from production.

**Fix:** validate bot ownership on assignment and constrain pinned and auto-discovered bot queries at use time. Define whether same-tenant cross-agent sharing is permitted explicitly; cross-tenant use must fail. Cover both existing and new tool assignments.

## 2. High — foreign custom tool loads its saved authentication

Locations:
- `api/src/controllers/agents/tools.py:205–222`: stores a custom-tool UUID and operation ID without checking custom-tool ownership.
- `api/src/services/agents/adk_tools.py:1874–1915`: loads referenced enabled CustomTool records by ID without a tenant constraint, then constructs an executor using their authentication configuration.
- `api/src/services/custom_tools/tool_executor.py:45–61`: decrypts saved bearer/basic authentication into request headers.
- `api/src/services/agents/chat_stream_service.py:1616–1622`: chat initialization invokes this loader.

**Plain-English example:** company B saves an authenticated integration for its business API. A company A user who knows the custom-tool UUID and operation ID attaches it to their agent. The loader registers the operation using company B's saved authentication.

**Reproduction:** the actual save controller accepted a synthetic foreign custom-tool UUID. The actual loader registered its operation. The real executor, constructed with the foreign tool's modeled configuration, produced the corresponding synthetic bearer header. Its CustomTool query had no tenant parameter. No HTTP operation was executed.

**Prerequisites:** authenticated agent-configuration access, knowledge of an enabled foreign custom-tool UUID and valid operation ID, and useful stored credentials. The potential operation is limited by the saved API definition and credential permissions. Production data access was not attempted.

**Fix:** check custom-tool ownership and operation validity before assignment. Load custom tools through the authorized agent's tenant, and reject foreign records before constructing an executor. Derive or pass validated tenant context to the loader; its current interface takes only agent ID and database session.

## Validation and scope

- Fresh selected regression run: **196 passed**, including OAuth connection scope, current-member credential selection, handoff controls and alternate authentication paths.
- Four real Redis quota tests were not rerun; their previous passing result is historical. Three existing tests needing unavailable local PostgreSQL or the known Google SDK environment dependency mismatch remained excluded.
- Existing test-client deprecation and AsyncMock warnings remain.
- [Reproduction probe](probes/review_non_oauth_connections.py) uses synthetic encryption, actual controller/resolver/loader/executor code and modeled database results. Run from repository root with `PYTHONPATH=api /private/tmp/synkora-harness-validation/bin/python docs/reviews/probes/review_non_oauth_connections.py`.
- Probe confirmed both assignments accepted, foreign Slack token returned, and foreign custom operation registered with its saved bearer authentication.
- No application fixes were made in this review; only this report and its probe were added. Production, infrastructure, dependencies, frontend and performance were not re-audited. This is a focused source review with local reproductions, not a complete penetration test or a security guarantee.
