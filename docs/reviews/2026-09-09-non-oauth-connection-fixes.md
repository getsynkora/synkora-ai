# Verified non-OAuth connection fixes

Date: 2026-09-09

Both paths in [the preceding review](2026-09-09-non-oauth-connection-review.md) were confirmed and fixed in application code. Verification now executes the actual ownership SQL against a local SQLite database containing separate synthetic tenants, rather than relying only on mocked query responses.

## Changes

- Tool assignment checks Slack bot and custom-tool ownership before updating or inserting an AgentTool. Foreign and nonexistent resources return 404. Malformed UUIDs and invalid custom-tool operation IDs return 400. OAuth validation remains in place.
- Pinned and auto-discovered Slack bot lookups constrain the bot to the runtime tenant before decrypting its token.
- Custom-tool loading constrains each CustomTool to the owning agent's tenant through a scalar SQL subquery. Foreign records never reach executor construction. This also protects assignments saved before the fix, without rewriting production records or adding a query per tool.
- Same-tenant connections remain usable. The change does not introduce a new restriction on same-tenant cross-agent bot sharing.

## Evidence and validation

**205 tests passed**, including five new regressions plus existing tool loading, OAuth, credential, handoff and API-key tests. Ruff checks and `git diff --check` passed.

The new tests:

1. Execute actual assignment and runtime SQL against foreign tenant records: reject both connection types, return no Slack token, and register no custom operation.
2. Execute the same paths with same-tenant records: accept the connections, resolve the synthetic Slack token, and register the custom operation.
3. Invoke the real save controller separately for foreign Slack and custom-tool IDs: both return 404 before any add or commit.
4. Reject an operation absent from an owned custom tool's OpenAPI definition.

The first two cases also model already-saved assignments, so enforcement does not depend solely on new-write validation. No Slack or custom API requests were sent.

Four unchanged real-Redis quota tests were deliberately excluded from this run; their earlier results are not counted in the 205. Existing test-client deprecation and web-tool AsyncMock warnings remain. No production PostgreSQL, credentials, deployments or infrastructure were accessed or changed. No new migration is required.

The historical probe documents the original bypass and assumes pre-fix queries; the new regression suite is the post-fix verification contract. This validates these fixes, not a guarantee that the entire application is vulnerability-free.
