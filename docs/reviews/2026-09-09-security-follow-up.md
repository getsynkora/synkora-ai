# Code security follow-up — 2026-09-09

Second targeted review following the harness fixes. Five confirmed code defects were fixed locally. No live attack, production deployment or credential inspection was performed. Severity describes potential impact; this review does not establish that any customer data was accessed.

## Confirmed findings and fixes

| Priority | Defect and practical example | Fix and evidence |
| --- | --- | --- |
| High | **Public agents exposed private channel conversation lists.** A logged-in user in tenant B could request tenant A's public agent with `source=slack`, `whatsapp`, `widget`, `flutter` or `chrome`. The agent query allowed public access, then the channel query omitted both account and tenant ownership. Conversation records were returned through `to_dict()`. | `api/src/controllers/agents/conversations.py`: channel inbox access now requires the agent's owning tenant before querying conversations. Public users retain access to their own web conversations. Tests cover all five channel selectors, owner access and own-web access. This finding concerns the list response; message retrieval routes have separate checks. |
| High when private headers are configured | **Public model configuration exposed arbitrary provider parameters.** Public users could read `additional_params`, including configured `extra_headers`; these can contain gateway authorization credentials. Private provider endpoints and routing configuration were also returned. | `api/src/controllers/agents/llm_configs.py`: both list and individual GET responses omit private parameters, API base URL and routing rules for non-owning tenants. Model choices remain available for public-agent UI. Tests exercise both endpoints with a synthetic authorization header and verify owner configuration remains intact. No real credential was read. |
| Medium | **Public MCP listing exposed private integration configuration.** Public access to an agent allowed listing internal MCP URLs and arbitrary per-agent `mcp_config`. | `api/src/controllers/agents/mcp_servers.py`: configuration listing now queries the owning tenant only. Negative test verifies the ownership predicate and absence of the public-access alternative. The test uses a mocked database; an actual two-tenant database integration test remains desirable. Public chat context panels may now receive 404 for private MCP configuration, intentionally. |
| Medium | **Widget wildcard matching accepted lookalike domains.** An allowlist of `*.example.com` accepted `evil-example.com` because matching used a bare suffix. | `api/src/middleware/widget_auth.py`: parse HTTP(S) URLs, reject malformed ports/userinfo, normalize hostnames and require the dot boundary for subdomains. Tests include lookalikes, nested subdomains, uppercase names, Referer paths and malformed origins. `*.example.com` now covers subdomains only; add `example.com` explicitly when the apex must also be allowed. Origin headers can be forged by non-browser clients; this policy is not user authentication. |
| Medium | **Widget rate limits could be exceeded concurrently.** Reading a count and adding a request were separate operations; simultaneous workers could all pass the same limit. Timestamp-based members could also collide. | Both sync and async widget limiters now use the same atomic Redis Lua operation, Redis server time and unique request IDs. A real isolated Redis test submitted 50 simultaneous attempts at a limit of 3: exactly 3 succeeded. It also checks expiry and independent widget allowances. |

## Review coverage and limits

Inspected public-versus-owner access in selected agent configuration and conversation controllers; widget domain authentication and distributed limits; OAuth state consumption; selected JWT and Slack webhook signature verification call sites; dangerous execution/deserialization patterns; and the already changed MCP boundary. Existing atomic OAuth `GETDEL` and explicit JWT algorithm selection were observed, not replaced.

This is a focused source and regression-test review, not an exhaustive audit of every integration or route. Additional areas warrant dedicated tests: anonymous widget session ownership/recovery, full tenant-role authorization matrices, public context-file/knowledge-base metadata exposure policy, command execution runners, outbound destinations beyond MCP, and dependency/image vulnerability scans. Their presence here is not a claim of a proven vulnerability. Existing earlier-review release work remains tracked in `2026-09-09-harness-fixes.md`.

## Validation

- Security boundary plus existing conversation/widget controller tests: 53 passed.
- Real Redis concurrency integration: 1 passed, using a temporary Unix socket with TCP disabled. Initial sandbox startup failed; the isolated test passed after approved execution outside the sandbox.
- Ruff and `git diff --check` passed for this change.
- Tests ran in the existing temporary validation environment described in the harness fix record. Full CI, live multi-tenant HTTP tests and production verification were not run.

All previous user changes were preserved. Nothing was committed, pushed or deployed during this pass.
