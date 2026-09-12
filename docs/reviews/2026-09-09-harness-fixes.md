# Harness fixes and remaining release work

This records the local implementation following the [review](2026-09-09-harness-review.md). Existing working-tree changes were preserved. Nothing has been deployed. This is not an enterprise certification or a measured speed comparison.

## What changed, in plain English

| Review item | Implemented behavior | Practical consequence / remaining work |
| --- | --- | --- |
| 1. Shared tool bindings | Each chat has its own registry; runtime and Claude bridge use it. Conflicting tool names are rejected. | Simultaneous chats cannot overwrite each other's MCP bindings in this path. Other entry points still need a complete authorization audit. |
| 2. API-host command execution | Tenant MCP stdio execution is rejected at configuration and connection time. | A configured command cannot inherit API secrets. Existing stdio integrations need a separately isolated HTTP runner; building that runner is not included. |
| 3. Identity fallback | Failure to establish explicit user-token identity returns an error. | A failed personal login cannot silently become a service-account action. |
| 4. Buffered answers | Tool-enabled provider calls forward text before generation ends. Native OpenAI, Anthropic and Google adapters preserve completed responses. Malformed/truncated tool arguments fail without guessed repairs. | Users can see text earlier. Raw OpenAI chunks are still retained for response assembly; memory reduction and real-provider latency measurements remain. |
| 5. Incorrect tool caching | Removed result deduplication and identical-call suppression. | Polling sees fresh results; repeating an action deliberately remains possible; failures cannot become successful cache hits. |
| 6. Unsafe retries/fanout | Retries require explicit retry-safe registration. MCP transport does not replay calls. Writes/unknown tools run in order; explicitly read-only batches have a concurrency bound. Runs have a deadline. | A lost write response does not automatically repeat the write. This cannot prove whether the remote system completed it; durable downstream idempotency remains necessary. |
| 7. Stale/unbounded MCP clients | Configuration digests checked on acquisition/dispatch, single-flight connection creation, bounded idle eviction and owner-task cleanup. Schema keys include revision; partial discovery isn't cached as complete. | Credential rotation and disabling a server stop use of stale bindings on the next dispatch. In-flight calls finish under their original identity. Full precompiled agent snapshots remain an optimization to measure. |
| 8. Blocking calls | GitHub tool HTTP is async and pooled; synchronous chat-time trace flush removed. | These operations no longer synchronously stall the chat event loop. A complete tracing-export/shutdown audit remains. |
| 9. Deployment | Corrected startup/liveness/readiness paths. Corrected misleading HPA comments. | Scale-out intentionally remains disabled at two replicas until dependency capacity is known. Increasing it from a comment would be a guess. Stream draining still needs a rolling-deployment test. |
| 10. MCP destinations | Same-origin HTTP transport, checked/pinned DNS, redirects disabled, no ambient proxy inheritance, deployment-owned private-host allowlist. | Tenant URLs cannot freely access internal services or redirect credentials. Network-level egress rules remain an infrastructure requirement. |
| 11. Misleading benchmark | SSE success checks require text and completion and reject errors. Added incremental, open-loop latency driver. | Header arrival no longer masquerades as first answer text. No production or competitor benchmark has been run. |
| 12. Early success | Ordinary chat, workflow and Claude completion events follow successful message persistence. | A save failure produces an error instead of completion. Durable terminal run records, replay, worker-loss recovery and an outbox are still separate work. |
| 13. Health/logging | Real bounded MCP discovery test with measured duration; removed reviewed tool-argument, token-claim and response-body logging. | A failed MCP connection is no longer reported healthy. This is not a whole-repository payload-log audit. |
| 14. Quality gates | Removed missing Gitleaks config reference; added strict typing gate for the new HTTP security boundary and regression tests. | CI now has a concrete boundary to enforce. Existing project-wide mypy suppressions and broader orchestration refactoring remain. |
| 15. Browser work | Initially render 50 recent messages, load earlier history on demand, preserve reading position, batch dashboard text updates per animation frame. | Long chats do less initial rendering. This is pagination, not complete virtualization; browser profiling is still needed. |

## Deployment settings that require real inputs

- `MCP_ALLOWED_PRIVATE_HOSTS`: comma-separated exact hostnames controlled by deployment administrators. Empty by default. Private/internal HTTP MCP integrations must be inventoried before rollout. Link-local, multicast and unspecified destinations remain blocked, even when named in this list. Use the final HTTP endpoint; redirects are disabled.
- `HARNESS_MAX_ACTIVE_RUNS_PER_TENANT`: distributed admission is opt-in; default `0` disables it. Set this and `HARNESS_MAX_ACTIVE_RUNS` together after measuring capacity. The implementation rejects excess runs and fails closed if Redis is unavailable while admission is enabled. It currently covers the chat service path, including its workflow/Claude branches, not every independent background-job entry point.
- Admission uses atomic Redis leases with a 3,630-second expiry and a 3,600-second maximum chat duration. A worker crash can reserve capacity until the lease expires; heartbeat-based early recovery is not implemented.
- `MCP_MAX_CACHED_CLIENTS` defaults to 128 per process; `MCP_CLIENT_IDLE_SECONDS` defaults to 300. These are protective implementation bounds, not measured production capacity. Eviction is checked on acquisition.
- HPA remains at two replicas. Budget connections across sync and async pools, API worker processes, replicas, task workers, rollout surge and administrative reserve before choosing a higher ceiling. Confirm the actual deployed manifest/overlay and database/PgBouncer limits.
- Existing stdio integrations need migration to an isolated runner. The runner must have separate credentials, filesystem isolation, resource limits and controlled network access. Blocking unsafe execution is not equivalent to implementing that infrastructure.

## Measurement procedure

Use an isolated staging agent and test identity. Benchmark calls can incur model costs and perform configured tool actions.

From `api`, with `AUTH_TOKEN` already set securely in the environment:

```sh
python tests/load/streaming_latency.py \
  --url https://YOUR-STAGING-HOST \
  --agent YOUR-TEST-AGENT \
  --requests 100 --rate 1 --max-inflight 16 \
  --expected-text 'benchmark complete'
```

The workload settings above are an example, not a capacity recommendation. The report separates offered requests, generator drops, failures, successful throughput, first answer text, first tool event and completion. It checks expected text only when supplied. A substring check is insufficient for complex tool-task correctness; provide task-specific assertions before competitive comparisons. Run matching before/after workloads on isolated revisions, with identical provider/model, prompts, tools, region and security policy. Do not subtract unrelated percentile values to infer harness overhead.

## Validation evidence

Validation used an isolated temporary Python environment with key provider/MCP SDK versions constrained from `api/uv.lock`. It inherited some system packages; this is not a pristine full `uv sync` environment.

- Broad agent suite: **687 passed**, one database fixture error because PostgreSQL on localhost:5439 was unavailable. The test was retried outside the sandbox; connection was refused. No database test pass is claimed.
- Separate MCP/controller/GitHub-tool suite: **61 passed** before the additional direct-connection regression; the subsequent lifecycle run passed all five lifecycle tests.
- Final focused backend regression run after the last edits: **126 passed**, including successful/failed persistence ordering and concurrent direct connection ownership. Ruff checks and `git diff --check` passed.
- Earlier isolated Redis admission integration run: **2 passed**, against a temporary Redis Unix socket with TCP disabled.
- Frontend component/batcher tests: **5 passed**. TypeScript and targeted ESLint passed.
- SSE benchmark assertions: **3 passed**. Python benchmark parser checks are included in the agent suite.
- Strict mypy check passed for the new MCP HTTP transport boundary only.

Focused tests cover early provider text delivery, complete tool-argument assembly, Google thought-signature preservation, request registry isolation, no credential fallback, bounded tool concurrency, cancellation/deadlines, configuration rotation/disablement, connection ownership and network destination restrictions. They use controlled dependencies; they do not prove live provider/infrastructure behavior.

An aiohttp unclosed-session warning appeared in the broad test environment and has not been attributed. Full CI, all application integrations, rolling upgrades, crash recovery, restore drills, browser performance and sustained live load remain unverified. SSO/SCIM lifecycle, retention/export/deletion, backups, audit governance and compliance evidence were release-gate recommendations in the review, not demonstrated defects that can truthfully be marked fixed by these code changes.
