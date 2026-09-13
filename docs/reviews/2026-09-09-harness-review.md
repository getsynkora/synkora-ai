# Synkora performance, scaling, quality, security and enterprise review

Reviewed 2026-09-09 against `e59c7c2` plus the existing working-tree changes. This is an independent verification and extension of the pre-existing `PERFORMANCE_ENTERPRISE_REVIEW.md`, which was preserved. No application code was changed.

## Assessment

Synkora has useful foundations: asynchronous database access, separate worker deployments, Redis caching/invalidation, authentication revocation checks, encrypted MCP configuration, tool authorization checks, observability, and CI tests. However, the reviewed execution path has isolation and correctness defects that should block a shared, untrusted-tenant enterprise rollout until resolved. The code does not support a claim of being the world's fastest harness. No production latency or throughput was measured.

The strongest immediate speed opportunity is real incremental answer streaming. The strongest architectural opportunity is separating immutable agent configuration from request-owned execution state. That separation also fixes a critical security problem. A language rewrite is not justified by the evidence collected here.

Scope: sampled agent orchestration, MCP registration/transport/cache, persistence ordering, database pool configuration, selected tool and tracing calls, frontend message rendering, CI and Kubernetes manifests. Mobile, extension, every integration, all authorization routes, live infrastructure, SSO/SCIM flows, backup restoration and dependency vulnerabilities were not exhaustively audited.

## Prioritized findings

Severity reflects impact in the reviewed deployment model; actual external reachability depends on deployed permissions and infrastructure. Source references below are repository-relative and line numbers refer to the reviewed working tree.

### 1. Critical — shared MCP registration can cross request and tenant boundaries

Evidence: `api/src/services/agents/adk_tools.py:1655`, `:1693`, `:2087`, `:2175`, `:3162`; `api/src/services/agents/function_calling.py:1743`.

The singleton registry indexes callables by tool name. MCP registration installs closures capturing the agent client and request shared state. A second request registering the same tool name replaces the first callable. The first request can subsequently execute the second request's binding. The assigned-tool guard verifies the name, so identical names still pass. This applies to different agents and to different user identities using one agent. Sanitizing names can create further collisions.

**Action:** immutable shared schemas; request-owned executable bindings; internal keys containing tenant, agent, server and original name; explicit collision rejection. Resolve credentials from the current execution identity. Do not cache request-bearing closures globally.

**Evidence strength:** executed the actual AST-extracted registration and lookup methods and confirmed overwrite. A concurrent HTTP exploit was not attempted. Acceptance test: interleave two tenants and two users with identical tool names and verify the destination and identity of every call.

### 2. Critical — tenant-configured stdio runs with the API environment

Evidence: `api/src/controllers/mcp_servers.py:99`; `api/src/services/mcp/mcp_client.py:153`; `api/src/middleware/auth_middleware.py:169`; `api/src/router_registry.py:246`.

The creation route requires a current tenant but has no platform-admin restriction in the reviewed route. It accepts a command and arguments. The stdio transport explicitly copies `os.environ` into the child environment. An authorized tenant configuring an executable server can therefore run code with API-process credentials and access when that configuration is loaded. Non-root execution alone does not isolate these secrets.

**Action:** require an explicit executable-server permission and move execution into an isolated runner with a minimal environment, tenant-scoped filesystem, resource limits and controlled egress. Keep API credentials outside that boundary. Validate the deployed permission path before rollout. No tenant command was executed during this review.

### 3. High — explicit user identity can fall back to shared credentials

Evidence: `api/src/services/agents/adk_tools.py:2103–2127`.

If creation of a user-token MCP client fails, execution falls back to the cached static-token client. A connection/authentication failure changes the authority used for the operation.

**Action:** fail closed for explicit user identity; retry under that same identity only. Acquire once per request where lifecycle permits, rather than reconnecting for every tool invocation. Test expired tokens, rejected authentication and transport failures; none should dispatch using service credentials.

### 4. High — tool-enabled answers wait for full model generation

Evidence: `api/src/services/agents/function_calling.py:1232–1289`, including `chunks = [chunk async for chunk in stream]`.

The provider connection streams, but the collector waits for all chunks and builds a complete response. This postpones answer delivery on the affected tool-enabled path even when the model answers without calling a tool. It also retains all raw chunks in memory until completion. This is a direct source-level bottleneck; its absolute cost depends on generation duration.

**Action:** introduce provider event adapters that forward valid answer deltas immediately and accumulate tool arguments by call ID. Dispatch only complete, validated tool calls. Preserve sanitization, usage, stop reasons, errors and provider-specific state. Do not expose private reasoning as answer content.

**Evidence strength:** a fake provider yielded a first chunk and paused; the actual extracted collector remained pending until the remaining stream was released. This verifies buffering, not a measured production speedup.

### 5. High — result caching changes tool semantics and failure status

Evidence: `api/src/services/agents/function_calling.py:752–785`.

The request-local dedup cache stores every tool result by name and arguments. Cache hits construct `ToolExecutionResult(..., success=True)`. Failures can become apparent successes; read-after-write and polling can return stale data; deliberate repeated actions can be suppressed.

**Action:** default tool-result caching off. Opt in only policy-approved stable reads; preserve full status and exclude errors, writes and polling. Invalidate relevant reads after mutations. Handle write idempotency using durable operation IDs and downstream support, not equal arguments.

### 6. High — retries and parallel tools need an end-to-end budget

Evidence: `api/src/services/agents/function_calling.py:1725`, `:1903`, `:2005`.

The runner retries broad exceptions and gathers a full parallel batch without a semaphore in this layer. Some deterministic failures are excluded using error-string checks, but ambiguous remote writes still lack an evident idempotency contract here. A write can succeed remotely and be repeated after its response is lost. One slow tool delays the gathered batch. Individual provider timeouts do not establish a total run deadline.

**Action:** propagate one remaining deadline; classify failures with typed outcomes; bound concurrency by tenant, server and process; admit work only within capacity. Retry writes only when safe. Cancel child operations when the run policy requires cancellation. Separate independent reads from ordered side effects.

### 7. High — live MCP state does not follow shared-cache invalidation

Evidence: `api/src/services/cache/agent_cache_service.py:428`, `:582`; `api/src/services/mcp/mcp_client.py:446–510`.

The invalidation subscriber removes Redis keys but does not evict the receiving worker's live clients. Client acquisition immediately returns an existing agent entry without checking a configuration version. Redis schema deletion can be followed by repopulation from stale in-memory discovery. The manager also has no acquisition lock, size bound or idle eviction in the reviewed implementation: concurrent cold requests can connect twice, and long-lived workers can retain clients for an increasing number of agents.

**Action:** use authoritative configuration revisions, verify revisions on acquisition, and retire obsolete clients safely. Add per-key single-flight acquisition and bounded idle eviction with disconnect. Treat pub/sub eviction as an optimization; recover correctly after missed messages. Include server updates, deletion, credential rotation and permission revocation in tests.

### 8. High — blocking I/O can stall other chats in the worker

Evidence: `api/src/services/agents/internal_tools/blog_site_tools.py:189`, `:224`; `api/src/services/agents/chat_stream_service.py:692`; `api/src/services/observability/langfuse_service.py:339`.

An async GitHub tool directly invokes `requests.post`. Chat completion synchronously flushes Langfuse. The latter occurs after the done event, but can still block unrelated requests sharing the event loop.

**Action:** use pooled async transports; put unavoidable sync SDK operations in a bounded executor. Export traces in batches outside the request path, with bounded buffering and explicit shutdown behavior. Validate event-loop delay while a fake dependency responds slowly.

### 9. High — checked-in API deployment has broken probes and fixed scaling

Evidence: `k8s/application/api-deployment.yml:75–97`, `:135`; `k8s/application/api-hpa.yml`; `api/src/app.py:533–583`.

All three probes use `/api/health`; the app declares `/health`, `/live` and `/ready`. No alternative handler was found in the reviewed source. The HPA has both minimum and maximum replicas set to two. Its comments describe a different maximum. These manifests therefore do not provide the intended startup/health checks or scale-out. Other deployment paths and live overlays may differ.

**Action:** check startup/liveness against the appropriate live endpoint and readiness against `/ready`; validate rendered manifests against a running app. Raise the replica ceiling only after dependency capacity is budgeted. Test stream draining under the current 30-second termination grace period. Kubernetes readiness controls traffic eligibility, while startup/liveness failures can trigger restarts: [official probe documentation](https://kubernetes.io/docs/concepts/workloads/pods/probes/).

### 10. High — MCP HTTP destination policy is incomplete in this path

Evidence: `api/src/controllers/mcp_servers.py:108–115`; `api/src/services/mcp/mcp_client.py:170`.

Creation checks URL presence and transport selection; connection uses the configured URL directly. No destination validation was found in this reviewed path. A tenant-controlled destination therefore needs a separate boundary preventing access to unauthorized internal services and unintended credential forwarding. This is a source-level exposure; internal endpoints were not probed.

**Action:** apply explicit destination policy at connection time, including schemes, resolved addresses and redirects. Permit private enterprise endpoints through explicit administration rather than an unconditional private-address exception. Enforce egress at a proxy/runner boundary and review credential destinations on configuration changes.

### 11. High for benchmark credibility — stress tests misidentify success and first-token latency

Evidence: `api/tests/load/chat-stress.js:55`, `:83`, `:115`; `api/src/helpers/streaming_helpers.py:261`.

The test calls HTTP waiting time TTFB, accepts greater than 90% success, and searches for `event_type` while the server emits `type`. Its error predicate can accept an HTTP-200 stream containing an application error. The first response byte can be headers or a status event, not answer text. A fixed-VU workload also reduces offered load as requests slow.

**Action:** incrementally parse actual SSE and assert terminal success and expected results. Measure first nonempty answer text, tool dispatch, final token and durable completion separately. Combine arrival-rate and concurrency tests; publish failures and rejected work alongside latency. Keep mock-provider overhead tests separate from real-provider task benchmarks.

### 12. Medium — completion precedes persistence

Evidence: `api/src/services/agents/chat_stream_service.py:661–715`.

The service sends done and marks execution complete before saving the assistant response. A worker failure or database error in that interval can leave an apparently successful answer absent on reload.

**Action:** distinguish answer-finished from durably-completed. Persist the response and terminal run record, or a durable outbox, before acknowledging durability. Add ordered event IDs and replay/reconnect semantics. Test worker loss between final text and persistence, without repeating completed side effects.

### 13. Medium — diagnostics misrepresent health and expose payloads

Evidence: `api/src/controllers/mcp_servers.py:249`; `api/src/services/agents/function_calling.py:1757`.

The MCP connection-test endpoint explicitly returns mock success and a fixed 45 ms without connecting. Tool arguments are logged at INFO and can contain confidential user content or integration data.

**Action:** perform a bounded real connection/discovery test and return actual results. Default to metadata-only logs; make content capture explicit, redacted, access-controlled and retention-limited. Verify both failed connections and sensitive argument redaction.

### 14. Medium — code-quality gates provide weaker assurance than they appear to

Evidence: `api/pyproject.toml` under `[tool.mypy]`; `.github/workflows/main-ci.yml:32`; `.github/workflows/style.yml`.

Mypy disables many meaningful error classes, including argument, return, attribute and unused-coroutine checks. No mypy invocation was found in the reviewed workflows. The main CI secret-scan command references `.gitleaks.toml`, but that file is absent from both the working tree and tracked file list. The pipeline does not create it before use. The live CI outcome was not inspected.

**Action:** supply a reviewed scanner configuration or remove the explicit absent-config reference, and test the command in clean CI. Introduce strict typing first at provider-event, tool-result and execution-context boundaries. Keep linting, but do not equate lint success with concurrency or authorization safety. Pin the lint tool used by CI for reproducibility.

### 15. Medium — frontend message rendering is not virtualized

Evidence: `web/components/chat/components/ChatMessages.tsx:63`, `:131`; used by the dashboard chat page and shared-chat view.

The comment claims virtual scrolling, but implementation maps the entire message list and auto-scrolls whenever messages change. Long conversations retain the whole rendered history; streaming creates repeated list work and scrolling. Browser profiling was not performed, so the user-visible cost is unmeasured.

**Action:** profile long histories with rich content, then window old messages or paginate history, preserve scroll anchors and memoize stable message props. Batch streaming display updates. Record time from received answer delta to painted text, frame time and DOM size. Keep frontend delivery latency separate from backend TTFT.

## Architecture for a faster harness

Move configuration work out of each run. Configuration writes should produce a versioned, immutable execution snapshot: resource bindings, normalized provider schemas, policy references and stable prompt material. Cache it in bounded worker memory with Redis backing. Use current authorization and revocation state when admitting each run. Bind tools and credentials into a small request-owned context.

Reuse correctly scoped model and MCP transports. Cache empty discovery results explicitly; distinguish successful empty, failed and partial discovery. Do not keep failed partial schemas as a healthy snapshot. Refresh on configuration/schema changes and use a bounded cold fallback. Precompute history summaries when possible instead of blocking the next response on a summarization model call.

Run only necessary retrieval before generation. Stream answer deltas as they arrive. Execute tools under explicit deadlines, fairness and side-effect policy. Persist durable completion and export noncritical analytics outside the critical path.

For a one-tool answer, model the critical path as:

`admission + snapshot/history + model tool selection + tool call + final-model first token + delivery`

The buffered implementation substitutes final-model full generation for final-model first token. Removing buffering can improve perceived latency without changing model speed. It does not remove tool execution time or necessarily improve final-answer completion time.

Database scaling needs a complete connection budget. Defaults are pool size 5 plus overflow 5, applied separately to sync and async pools (`api/src/config/database.py:58–76`; `api/src/core/database.py`). If both pools are exercised, an API process can use up to 20 pooled client connections at these defaults. This is a ceiling, not an eagerly opened count. Multiply by worker processes and replicas, then add workers, jobs and operational reserve. PgBouncer backend capacity and application client capacity are different budgets. Monitor pool wait and transaction duration; do not simply enlarge pools. Keep a separate AsyncSession for each concurrent task, consistent with [SQLAlchemy's session guidance](https://docs.sqlalchemy.org/en/20/orm/session_basics.html).

Refactor around four explicit contracts: configuration snapshot, execution context, provider events and tool outcomes. Large orchestration modules currently mix discovery, mutable registration, provider adaptation, retries, caching, tracing and persistence. Introduce focused behavior tests before moving those responsibilities. Optimize allocations or consider a lower-level runtime only after profiling shows they materially limit the target workload.

## Benchmark plan and acceptance criteria

Define “fastest” as lowest measured harness overhead at a stated task-success rate and sustainable load for a published workload. A fast empty stream or cached answer is a separate category from a fresh, correct tool-using answer.

Use two benchmark tracks:

1. **Deterministic overhead:** a controllable fake streaming model and fake tools, configurable delay/output size, fixed datasets and injected failures. This isolates scheduling, serialization, caching, persistence and delivery costs without provider variability.
2. **Real end-to-end:** direct model-plus-tool baseline and selected competing harnesses with the same model, region, prompts, tools, output limits, security requirements and success criteria. Publish versions and configuration. Do not infer competitive ranking from this source review.

Test warm/cold no-tool responses, one MCP read, user-token MCP, independent tools, large schemas, long history, compaction, slow tools, provider throttling, Redis failure, tenant contention, revocation, disconnects and rolling deployment. Include writes with lost responses and recovery.

Record p50/p95/p99 for admission, snapshot/history, provider first token, completed tool arguments, tool execution, first answer text, final text and durable completion. Also record achieved/offered rate, rejection/error rate, task success, tokens/cost, CPU/RSS, event-loop lag, DB pool wait and connection counts. Use per-run spans to separate upstream and harness time; subtracting unrelated aggregate percentiles is invalid.

Suggested initial engineering targets, explicitly **unmeasured hypotheses**: warm snapshot lookup under 5 ms p95; pre-model harness work under 50 ms p95 excluding necessary remote I/O; answer-delta forwarding under 10 ms p95 after receipt. Set workload-specific user SLOs after baseline measurement. Increase arrival rate until latency/error/task-success targets fail, then use a capacity reserve rather than deploying at that cliff.

## Enterprise release gates

| Area | Evidence required before enterprise sign-off |
| --- | --- |
| Isolation and access | Concurrent tenant/user tests, negative authorization matrix, cross-worker revocation, executable-tool isolation and destination policy |
| Reliable execution | Durable terminal state, idempotent writes, bounded retries, cancellation, worker-loss recovery and stream replay |
| Capacity | Repeatable open-loop and soak tests, tenant fairness, measured dependency budgets and graceful deployment |
| Identity | End-to-end SSO/SCIM lifecycle tests including deprovisioning and role changes; feature presence is insufficient |
| Data governance | Secret rotation, scoped audit access, payload redaction, documented retention/export/deletion across stores and backups |
| Operations | Restore drills with agreed RPO/RTO, failover tests, actionable alerts and incident runbooks |
| Supply chain | Working secret/dependency/image scans, reviewed exceptions, reproducible artifacts and deployment provenance |

These are acceptance requirements, not assertions that every listed capability is absent. Live organizational controls and compliance evidence were outside this review.

## Delivery sequence

1. **Isolation and correctness:** request-local bindings, fail-closed identity, stdio boundary, destination policy, safe result caching and write retry semantics. Exit: deterministic concurrent identity and side-effect tests pass.
2. **Trustworthy operations and measurement:** fix probes/HPA configuration, real connection tests, CI scanner reference and SSE success/latency measurement. Establish baseline traces and capacity budgets.
3. **Latency:** incremental provider events, pooled async tool HTTP and asynchronous trace export. Exit: first answer is observable before fake provider completion and measured tail latency improves at unchanged success criteria.
4. **Scaling:** versioned snapshots, single-flight bounded clients, bounded admission/concurrency and revocation-aware invalidation. Exit: cold-start, contention and multi-worker configuration tests pass.
5. **Enterprise hardening:** durable completion/recovery, restore and deployment drills, governance validation and long-history browser optimization. Publish repeatable comparative benchmarks only after these controls are represented fairly.

## Validation performed in this review

- Read and cross-checked the cited source and configuration, preserving three existing modified application files and the existing review document.
- Executed four dependency-light checks: actual extracted registry overwrite, actual extracted provider buffering, health-route/probe mismatch and absent CI scanner configuration. All four confirmed the stated conditions. Temporary reproduction script: `/private/tmp/synkora_review_checks.py`.
- Ran available local Ruff against six reviewed backend files: `adk_tools.py`, `function_calling.py`, `chat_stream_service.py`, `mcp_client.py`, `agent_cache_service.py`, and `controllers/mcp_servers.py`. All checks passed. The project-local Ruff executable was absent; the available PATH installation was used.
- Consulted primary Kubernetes and SQLAlchemy documentation for probe/session recommendations.
- Did not run the full application suite, real-provider benchmarks, live exploits, a current dependency audit, browser profiling, or infrastructure restoration. The isolated checks do not replace integration tests. No measured throughput, percentage speedup or world ranking is claimed.
