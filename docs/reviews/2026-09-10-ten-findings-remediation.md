# Security review remediation — 2026-09-10

## Status

Nine of the ten reported findings are addressed in source. Finding 10 is partly
addressed: sandbox dependencies are fully locked, but ML dependency and model
revision pinning remains pending permission to retrieve registry/model metadata.
No external systems were accessed, no packages installed, and no deployment or
production-data changes were performed. Existing unrelated workspace changes
were preserved.

| Finding | Source change | Status |
| --- | --- | --- |
| 1. Local command escape | Command tools, directory-tree helper and LocalComputeSession refuse API-process execution. Legacy local/unconfigured agents resolve to the isolated sandbox. Removed xargs, curl and wget from command allowlist. | Addressed |
| 2. Sandbox network/service pivot | Bubblewrap keeps its private network namespace. Mandatory sandbox signing secret; short-lived tenant/workspace capabilities on all execution/file/delete endpoints. ML service requires authenticated API/worker requests and restricts model names. | Addressed |
| 3. Cross-tenant feedback/outcomes | Message/conversation ownership is checked against the tenant-authorized agent before recording. ES IDs include tenant and agent. Client trace IDs cannot modify Langfuse scores. | Addressed |
| 4. Foreign eval dataset mutation | Case creation checks parent tenant and agent before writes. Case deletion checks its parent. Counter scripts recheck ownership; dataset case deletion includes tenant filtering. | Addressed |
| 5. Unverified identity linking | Direct identity-claim linking returns 410 before any database mutation. Provider-proven OAuth login remains available. | Addressed by disabling unsafe entry point |
| 6. Provider-config privilege escalation | All provider-config routes require tenant admin/owner permission; platform-tenant configuration additionally requires platform-admin status. | Addressed |
| 7. OAuth replay race | State and exchange-token consumption use Redis GETDEL, never separate GET/DELETE. | Addressed |
| 8. Disabled ES TLS checks | All six reviewed clients verify certificates, with an optional configured CA bundle. | Addressed |
| 9. Audit integrity | Both writer interfaces share per-tenant transaction advisory locking, monotonic timestamps and canonical full-field HMAC signing. Verification checks the versioned predecessor and all protected fields. Settings-derived key cannot be empty. | Addressed |
| 10. Unlocked sidecar dependencies/models | Sandbox Docker installs a complete 14-package hash-pinned dependency closure derived from api/uv.lock; CI audits it. ML requirements input is prepared, but the ML Dockerfile still needs a generated lock and immutable model revisions. | Partially addressed; unresolved ML portion |

## Validation

**121 focused tests passed** in the existing local validation environment. Two
existing dependency/parser deprecation warnings were reported.

Run with an already installed project test environment:

```sh
python api/scripts/test_security_review_offline.py
```

The runner blocks DNS and IPv4/IPv6 socket operations before pytest loads project
configuration. Tests use mocked databases, Elasticsearch and Redis, and in-process
ASGI transports. No live service credentials or connections are used.

The focused tests cover foreign message/conversation rejection, namespaced ES
writes, poisoned dataset parents, direct identity-claim rejection, single-use
OAuth consumption under concurrency, provider admin restrictions, every sandbox
file/execution endpoint's foreign-capability rejection, capability expiration and
signature validation, isolated execution selection, all six ES TLS clients,
audit writer/verifier agreement, audit-field tampering, and ML authentication.

Also checked: Ruff, YAML parsing of affected deployment/CI configuration, service
Python syntax, and the sandbox lock's complete transitive dependency coverage and
artifact hashes against the existing API lock.

Live PostgreSQL lock behavior, Elasticsearch operations, Linux namespace behavior,
image builds and model compatibility have not been exercised here. The updated
`services/sandbox/test_isolation.py` checks Linux execution, foreign workspace
access, service-loopback denial, capability boundaries and existing sandbox
resource controls when run in the built image. Container builds would install
packages and contact external registries, so none were run.

## Deployment and compatibility requirements

- Configure independent random `ML_API_KEY` and `SANDBOX_API_KEY` secrets of at
  least 32 characters. Compose now requires them. Production deployment reads
  `K8S_ML_API_KEY` and the existing `K8S_SANDBOX_API_KEY` secrets. Deploy matching
  API/worker and service versions together: old raw sandbox headers are rejected.
- Legacy `local` compute now uses the isolated platform backend. A missing or
  unhealthy sandbox makes command execution unavailable. Tenant commands have no
  network access; git clone/fetch and other network operations will fail until a
  separately reviewed, restricted egress mechanism is provided. Do not restore
  `--share-net` or the local subprocess fallback.
- Direct `/api/v1/auth/link-provider` requests return 410. A future linking UI must
  complete a dedicated OAuth flow that proves provider ownership and binds state
  to the initiating account; accepting provider IDs from JSON remains forbidden.
- Redis must support GETDEL (Redis 6.2+). Redis errors cannot authorize a replay.
- Set `ELASTICSEARCH_CA_CERTS` to a mounted trusted CA file for private TLS issuers.
  Certificate checks only apply when the Elasticsearch URL uses HTTPS; existing
  HTTP deployments still need transport encryption configured separately.
- Prefer a dedicated stable `AUDIT_CHAIN_SECRET`; otherwise validated `SECRET_KEY`
  is used. Preserve signing keys when retaining audit history. Per-tenant advisory
  locking is PostgreSQL-specific. Audit write failure propagates instead of
  silently saving an unsigned entry.
- Audit metadata includes `_audit.version=2` and `prev_hash`. Old entries are not
  rewritten or falsely certified: verification reports legacy coverage as invalid
  for full-field integrity. A verification limit checks only a prefix and reports
  whether coverage is complete. Independently retain chain checkpoints to detect
  tail truncation. Historical retention/deletion must account for chain continuity.

## Existing data and operational follow-up

These source fixes prevent the reviewed future writes; they do not establish that
production data was never exploited. Review any identity links created through
the disabled endpoint and revoke affected sessions if compromise is found. Review
historical eval cases for mismatched parent tenant/agent IDs and recalculate case
counts. Reindex/deduplicate legacy unnamespaced feedback/outcome IDs before treating
historical analytics as authoritative; preserve historical evidence first. No
production-data migration or deletion was performed in this task.

## Remaining approval-dependent work

The workspace contains no ML dependency lock or immutable Hugging Face model
revisions. Completing finding 10 requires package-registry metadata for a full
Python 3.11 dependency resolution and model-registry metadata for the two existing
approved MiniLM models. The intended change is hash-required locked installation,
CI auditing of that lock, model snapshots fixed to commit revisions, disabled
remote model code, and offline-only runtime loading. Versions/hashes will not be
invented. Package installation and deployment are not needed to prepare these
source changes; image-build validation would require separate authorization.
