# Application security remediation — 9 September 2026

Scope: application code and compatible dependency updates from the deep security review. No Kubernetes, cloud, database TLS, network-policy, deployment workflow, or production configuration changes were made in this remediation. Earlier workspace changes to deployment files have been preserved. Nothing has been committed, pushed, or deployed.

This is **not a clean security bill of health**. Runtime isolation remains outside scope, and three dependency families still have advisories. Existing production data and infrastructure were not inspected or changed.

## What changed, in plain English

| Review finding | Application change | Practical effect / limitation |
|---|---|---|
| S01 — local command escape | Reject executable paths outside system binary directories; block `awk` and `find` child execution; give local commands a minimal environment. Claude CLI receives selected runtime variables and its own provider key, rather than every API environment variable. | The demonstrated fake `ls`, environment-reading `awk`, and `find -exec` inputs are rejected. This is hardening, **not an isolation boundary**. Other allowed programs can still execute code, and Claude retains tools and filesystem access. |
| S02 — shared sandbox | Excluded: no sandbox/container topology changes. | Different working directories do not isolate tenants. This risk remains if production uses the reviewed shared execution model. |
| S03 — DuckDB | Require trusted runtime tenant context; check the configured bucket and actual tenant upload prefixes; stage one authorized object; remove AWS credentials and HTTP extensions from the SQL engine. Permit one SELECT with only that file accessible and lock engine settings. Bound input to 64 MiB, output to 1,000 rows, memory setting to 256 MB, threads to one, concurrent analyses to two, and interrupt queries after 15 seconds. | Queries cannot use the demonstrated SQL-comment bypass to obtain arbitrary filesystem/network access or another tenant's object. Tests use the real locked DuckDB engine. Engine settings and interruption are defense in depth, not an OS resource or security boundary. |
| S04 — forged widget identity | Require proof whenever a user identity is supplied, including widgets where identified login is optional. Organization routing and downstream user-token claims require signed organization claims. Token-generation failure stops the request. | Knowing a public widget key or another customer's user ID no longer grants that identity. A legacy user-ID HMAC cannot authorize a different organization. |
| S05 — widget history/session access | Share verified identity checks across history, session listing, session closure, push registration, and approval responses. Anonymous conversations require a signed, widget-specific session capability and cannot match identified or dashboard-owned records. Dashboard session closure uses normal account revocation and current membership checks. | A caller cannot read a customer's history, close their chat, subscribe to their notifications, or approve their action with just the public widget key. |
| S06 — public portal signup | Remove automatic internal membership based on a publicly supplied portal slug. | A customer signing up through a portal does not become internal staff. Existing historical membership rows were not deleted: the code cannot reliably distinguish legitimate staff from previously auto-joined customers. |
| S07 — removed members | Every tenant dependency checks current account membership in the database after account/token validation. | Removing a member takes effect on tenant-scoped routes even while their old JWT is unexpired. This adds one indexed membership lookup per request, shared by FastAPI dependencies. |
| S08 — database TLS | Excluded under the requested configuration scope. | No assumptions about production RDS certificates or connection settings. The reviewed code's `verify-full` behavior has not been corrected here. |
| S09 — RSS/newsletter SSRF | Public-only, DNS-pinned HTTP transport; validate every redirect destination; disable environment proxy inheritance; bound download size and total duration. | An article/feed URL cannot direct these fetchers to loopback, private services, or link-local metadata endpoints. The MCP private-host allowlist does not apply to public-content fetching. |
| S10 — Recall webhooks | Require verification even when secret lookup fails; implement Recall's documented signed ID/timestamp/body format; accept standard and legacy Svix header names; reject timestamps outside five minutes; suppress duplicate IDs with shared Redis; route only using signed bot metadata. | Unsigned requests, stale deliveries, changed query-string agent IDs, and duplicate IDs cannot trigger the handler. Missing/ambiguous secret lookup or unavailable replay storage fails closed. Duplicate suppression lasts 24 hours; this is not a durable exactly-once event store. |
| S11 — authentication policy failures | SAML/MFA policy lookup errors stop password login with HTTP 503. | A database error cannot silently bypass the organization's login policy. |
| S12 — reset revocation failure | Revoke sessions before committing the password reset; treat a false revocation result as failure; roll back and return HTTP 503 if revocation fails. | The API cannot report successful recovery while knowingly leaving old sessions valid. This does not replace Redis-based revocation with a durable database epoch or make Redis and SQL one atomic transaction. |

The new widget approval and push-subscription checks address additional instances of the same ownership flaw discovered while implementing the fixes.

## Widget integration contract

Deploy updated clients with the API change. Old unsigned identified clients will receive 403. This intentional behavior change closes impersonation; it must not be bypassed by turning off identity verification.

For an identified customer with no organization, the existing `userHash` remains supported: HMAC-SHA256 of the exact user ID, signed by the widget identity secret on the customer's backend. The same proof is now required on history/session/action calls through `X-Widget-User-Id` and `X-Widget-User-Hash`.

For organization access, the customer's backend must issue a short-lived HS256 assertion using that widget's identity secret. The backend must derive the user and organization from its authenticated session, not accept arbitrary browser claims. Example claims:

```json
{
  "sub": "authenticated-customer-id",
  "organization_id": "authorized-organization-id",
  "aud": "synkora-widget:ACTUAL-WIDGET-UUID",
  "iat": 1788912000,
  "exp": 1788912300
}
```

Use current timestamps: the example above is only a shape. Maximum lifetime is 300 seconds. Optional `name`, `email`, and `org_name` must also come from that authenticated backend context if used as trusted downstream claims. Keep the signing secret off browsers/mobile devices.

- Chat sends `identity_token`; history/session/action requests send `X-Widget-Identity-Token` and `X-Widget-User-Id`.
- Browser SDK accepts `identityToken` and exposes `SynkoraWidget.setIdentityToken(widgetId, refreshedToken)` for renewal.
- Flutter widget/controller accepts `identityToken`; its client exposes `setIdentity(...)` for renewal.
- Anonymous chat returns a signed capability in an early SSE `session` event and final `done` metadata. Subsequent chat sends `session_token`; other requests use `X-Widget-Session-Token`. These tokens last 24 hours and are scoped to one widget/session.
- Browser SDK stores the anonymous capability locally. Flutter's `onSessionToken` callback and `restoreAnonymousSession` let the host app persist it alongside the conversation. Without restoration, server-side anonymous history cannot resume after app restart.
- Existing anonymous conversations without a capability cannot safely be recovered from their old client-supplied session ID alone.
- Widgets without a usable identity secret fail closed. This remediation does not generate or rotate production secrets.

API CORS headers were extended only to carry these new proofs; allowed origins and deployment settings were not changed.

## Dependency results and remaining issues

Frontend: Next.js is now 16.3.3. Tiptap, DOMPurify, Mermaid, and affected compatible transitive dependencies were updated in `package.json` and `pnpm-lock.yaml`. The production audit fell from **52 matches to 1 critical match** across 915 dependencies.

Python: locked Snowflake connector 4.7.3, Tornado 6.5.8, pytest 9.1.1, and pytest-asyncio 1.4.0. The lockfile audit fell from **9 advisories across 5 packages to 4 across 2 packages**. Python audit includes optional and development dependencies; these are package advisories, not proof of a production exploit.

Still unresolved:

1. **MapLibre via Plotly: critical advisory.** The advertised fix starts at 6.4.1; the existing Plotly dependency uses an older major. Even the checked latest Plotly manifest declares MapLibre 5.x. No unsupported forced major override was applied. This needs a verified compatible replacement/update or a deliberate change to available chart functionality.
2. **Thrift via Databricks: three advisories.** The security floor 0.24.0 conflicts with the installed Databricks connector's `<0.21.0` requirement. Dependency resolution verified the conflict. Upgrade/replace the connector with integration testing rather than override its declared compatibility.
3. **ecdsa via SendGrid: one advisory with no fixed release reported.** No guessed package version or unverified exploit claim.

No new audit ignores were added. Existing audit configuration was preserved. Machine-readable before/after audit files are alongside this report. The old diagnostic probe script records vulnerable baseline behavior and is not a regression test for the remediated code.

## Validation

- 396 selected backend tests passed under the updated pytest/pytest-asyncio versions, covering security services, auth middleware/services, widget/auth controllers, command/file tools, and tenant boundaries.
- After the Recall protocol correction, all 18 remediation-controller tests passed, including current signatures, expired/future timestamps, signed routing, and duplicate delivery.
- Real SQLite predicates verify anonymous history excludes another session, identified users, and dashboard accounts.
- Real DuckDB tests verify authorized analysis and denial of another local file, private HTTP access, configuration-changing SQL, extension installation, and multiple statements.
- Frontend: 111 tests passed; TypeScript passed; ESLint passed with 19 warnings. Widget JavaScript syntax checked.
- Flutter: analysis of all three updated SDK files passed.
- Production webpack build passed, including TypeScript and generation of all 147 static pages. The default Turbopack build remains unverified here because its PostCSS subprocess could not bind a local port; deployment build settings were not changed.

Tests use synthetic identities, isolated files, and mocked external services. No live production database, cluster, or tenant data was used. No end-to-end production rollout test was performed.

## Primary references

- [Recall request verification](https://docs.recall.ai/docs/authenticating-requests-from-recallai): signed ID/timestamp/body and supported header names.
- [DuckDB security restrictions](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview): external access, allowed paths, and locked settings. These are not a substitute for process isolation.
- [Next.js security advisory](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4): patched release used for the update.
- [MapLibre security advisory](https://github.com/maplibre/maplibre-gl-js/security/advisories/GHSA-jrc7-96c5-q579): remaining dependency finding.
