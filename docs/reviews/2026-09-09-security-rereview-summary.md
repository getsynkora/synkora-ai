# Security re-review summary — 9 September 2026

Verdict: the application is materially improved, but it should not yet receive a security sign-off. A newly confirmed storage-tool authorization gap remains. This review checked current workspace code, not the deployed production application. Infrastructure/configuration remains excluded as requested. No application code was modified during this re-review.

## Findings ordered by priority

### 1. Critical — S3 tools do not enforce tenant ownership (newly confirmed)

The DuckDB entry point now checks file ownership, but separate agent storage tools bypass that protection:

- `api/src/services/agents/internal_tools/storage_tools.py:291`: download uses the supplied key directly.
- `api/src/services/agents/internal_tools/storage_tools.py:334`: presigned URL generation uses the supplied key directly.
- `api/src/services/agents/internal_tools/storage_tools.py:401`: deletion uses the supplied key directly.
- The registered wrappers in `api/src/services/agents/tool_registrations/storage_tools_registry.py:55` pass runtime context through, but the handlers do not use its tenant identity for authorization. The shared storage service calls its configured bucket with the supplied key.

Plain-English example: a customer with access to an agent assigned these tools supplies another customer's storage key. If the application's storage credentials can access that object, the agent can read it, create a downloadable link, or delete it.

Evidence: executed the actual handlers with synthetic tenant A context and tenant B object keys, replacing the storage backend with a mock. Download returned the synthetic victim marker; presigning and deletion were dispatched with the victim key. All four diagnostic checks were true. No live S3, production credentials, or customer data was accessed.

Fix priority: first. Put one authorization check around every storage operation, including list/upload/overwrite/metadata/existence, using trusted runtime tenant identity and canonical object ownership. Do not let model-supplied tenant IDs authorize access. Test denial across tenants and success within the owning tenant.

### 2. High — password reset is not atomic with session issuance (remaining code gap)

`api/src/services/auth_service.py:787` increments Redis revocation state before the password transaction commits at line 794. `api/src/services/session_service.py:59` independently reads the current version when issuing sessions.

Plain-English example: a login that authenticated with the old password can overlap a reset, then receive the newly incremented token version. The previous fix correctly stops resets when revocation fails, but does not eliminate concurrent issuance or make revocation durable after Redis state loss.

Evidence level: code-path/interleaving analysis, not a reproduced production exploit or database-concurrency test. Recommended next step: a persistent account session/credential version, checked by access-token validation and refresh, with a concurrent reset/login regression test.

### 3. Critical advisory / exposure not established — MapLibre remains in the frontend dependency graph

The saved post-update production audit reports one critical match for MapLibre through Plotly. Thrift and ecdsa also remain in the Python audit: four advisories across two packages. These are dependency findings, not evidence that every advisory is exploitable through this application's features. The advisory registry was not queried again in this re-review; these counts refer to the preceding remediation audit.

Plain-English example: malicious map attribution content could become browser-executed content if the vulnerable rendering path is exposed. The installed MapLibre source still assigns attribution HTML using `innerHTML`; end-to-end reachability through the current chart UI was not established here.

Fix: validate compatible dependency replacements or a tested maintainer patch/workaround. Thrift's patched version conflicts with the existing Databricks connector range; ecdsa has no fixed version reported in the saved audit. Do not force incompatible versions and call the issue solved.

### 4. Medium — Recall may acknowledge an event that was never processed

`api/src/controllers/recall_webhooks.py:210` claims an event ID before business processing. Handler errors are caught at line 239 and the request still returns success at line 244. Retries with the same ID are rejected as duplicates for 24 hours.

Plain-English example: a meeting event arrives during a transient processing failure. The provider sees success, and a retry does not rerun the handler. This is an event-delivery reliability problem, not a signature bypass. Some current handlers only log or use optional notification storage, so the business effect depends on the event handler.

Fix: distinguish processing from completed events; acknowledge completion only after successful processing, with safe retry behavior and idempotent side effects.

## What remains improved

The reviewed fixes still require verified widget identities and anonymous session capabilities; restrict widget history/actions to the verified principal; check current tenant membership; prevent public portal signup from adding internal membership; fail closed on SSO/MFA policy errors; reject unverified Recall events; and restrict RSS/newsletter destinations and DuckDB file access.

This re-review reran 48 focused tests covering widget identity, outbound HTTP restrictions, real DuckDB file restrictions, remediation controllers, and command-tool bypass cases: **48 passed**. Earlier broader results—396 selected backend tests, 111 frontend tests, TypeScript/Dart checks and the webpack production build—were read from the prior validation record, not rerun here.

Tests passing establish the cases they cover. They do not establish that every storage entry point or concurrency scenario is protected.

## Rollout and scope limits

Updated widget clients and backend-issued identity proofs are required with the API changes. Old anonymous IDs alone cannot safely restore protected history. Previous portal-created memberships need a separate data review; the code change does not remove existing access.

Kubernetes, cloud networking, database TLS configuration and execution isolation were excluded. Local command/Claude execution and shared sandbox isolation are therefore not certified secure by this report. No claim is made that production matches the local files or that the changes have been deployed.

Recommended order: close the S3 authorization gap first; address reset/session concurrency and dependency exposure next; then make webhook processing retry-safe and validate the widget rollout end to end.
