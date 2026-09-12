# Harness Performance and Enterprise Review

Date: 2026-09-09. Scope: source review of the chat execution path, tool registry, MCP lifecycle and recent uncommitted schema-cache changes, selected authentication and observability paths, browser transport, load tests, CI, and Kubernetes manifests.

This is a source-backed architectural review, not a production benchmark, penetration test, dependency audit, or compliance certification. Production configuration may differ from checked-in manifests. No application code was changed during this review. Prior uncommitted MCP changes were preserved.

## Findings

### 1. Critical: global tool wrappers can execute another agent's client or user's identity

Evidence: `api/src/services/agents/adk_tools.py:1655`, `:1693`, `:2087`, `:2093`, `:2175`; `api/src/services/agents/function_calling.py:1743`.

The singleton registry stores callable tools by name alone. Each MCP load replaces that entry with a closure capturing an agent client and request shared state. If request A loads `lookup`, then request B loads the same name while A waits for its LLM, A's subsequent name lookup resolves B's callable. This also affects two users of the same agent with different MCP identity tokens. The assigned-tool guard checks names, so it does not prevent this collision. Sanitization introduces additional collisions, such as `a.b` and `a_b`.

Fix: cache immutable schemas separately from execution bindings. Resolve calls through a request-owned tool map keyed internally by tenant, agent, server ID and original tool name. Bind credentials from the current runtime context. Reject ambiguous public tool names. Never cache user-bearing closures globally.

Validation: an isolated check executed the actual registration and lookup methods extracted from the source; the second registration replaced the first callable. Full concurrent HTTP reproduction remains to be added. Required regression: two tenants and two users, identical tool names, interleaved model responses, each reaching only its own fake MCP server and identity.

### 2. Critical: tenant-configured stdio commands run in the API environment

Evidence: `api/src/controllers/mcp_servers.py:99`, `:108`, `:127`; `api/src/services/mcp/mcp_client.py:153`; `api/src/middleware/auth_middleware.py:169`.

MCP creation accepts a command and arguments with tenant authentication but no platform-admin restriction in this route. The client launches the configured command through StdioTransport and explicitly copies `os.environ` into its environment. Loading tools for an attached stdio server can therefore execute tenant-supplied code with the API process's environment and access. Running the API as non-root does not isolate its credentials from its child process.

Fix: move stdio execution into a separately isolated, tenant-scoped runner with an explicit environment allowlist, bounded resources, restricted filesystem and egress. Restrict who can configure executable servers. Keep the API's service credentials out of the runner. Exploit execution was intentionally not attempted.

### 3. High: user-token failure falls back to shared service credentials

Evidence: `api/src/services/agents/adk_tools.py:2103`, `:2117`; `api/src/services/mcp/mcp_client.py:575`.

The user-token client factory catches connection failures and returns None. The wrapper then executes through the cached static-token client. An identity-specific authentication failure or connection problem can change the authority used for the operation.

Fix: fail closed when an explicit user identity cannot connect. Retry only under the same identity and budget. Reuse that identity's client within the request instead of reconnecting for every tool call; never pool solely by agent across different identities.

### 4. High: tool-enabled responses buffer all provider tokens

Evidence: `api/src/services/agents/function_calling.py:1232`, `:1250`, `:688`.

The LiteLLM path uses streaming upstream but collects every chunk before returning. When the response has no tool calls, the complete answer is yielded as one text event. Consequently, even an answer needing no tools waits for full generation if tools were supplied. With one tool call, first answer text waits for the tool-selection response, MCP execution, and the full final generation. This is a stronger direct TTFT finding than repeated warm discovery.

Fix: use an incremental provider event adapter that forwards answer deltas through the existing sanitization path, accumulates tool arguments per call ID, and executes only completed, validated calls. Preserve usage, finish reasons, errors and provider-specific state. Do not add a separate final-answer generation call when the existing response already contains the answer.

Validation: executed the actual collector against a fake provider gated after its first chunk. The collector remained pending until stream completion. This proves buffering, not an absolute latency saving.

### 5. High: MCP cache invalidation does not invalidate live clients across workers

Evidence: `api/src/services/cache/agent_cache_service.py:428`, `:582`; `api/src/services/mcp/mcp_client.py:459`, `:506`; `api/src/controllers/mcp_servers.py:191`, `:220`.

The Redis subscriber deletes shared cache keys but does not evict the receiving worker's MCP clients or their discovery caches. Existing clients return without a version check. Direct server update/delete routes also omit client/schema invalidation for attached agents. Endpoint, credential, status and tool changes can leave workers using stale connections. Deleting the Redis schema alone can cause it to be repopulated from stale in-memory discovery.

Fix: version server configuration and agent bindings, invalidate every affected agent, and check versions when acquiring a client. Broadcast local eviction as an optimization, with authoritative version reconciliation after missed notifications. Retire old clients safely while in-flight calls finish. Handle server tool-list changes when supported; do not require list_tools on every chat. MCP defines tool-list change notifications: [official specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).

### 6. High: tool-result deduplication changes tool semantics and hides failures

Evidence: `api/src/services/agents/function_calling.py:752`, `:773`, `:783`.

Every tool result is cached by name and arguments, including failures and state-changing operations. Cache hits reconstruct results with `success=True`. A transient failure can become a cached success on the next model iteration. A read after a write can return pre-write state. Repeated polling or deliberate repeated actions can be suppressed.

Fix: default to no result caching. Enable request-local caching only for explicitly approved stable reads, preserve the full result status, exclude failures, polling and writes, and invalidate affected reads after mutations. Write idempotency needs operation IDs and durable execution records, not argument equality. Server annotations are hints, not a security policy: [MCP guidance](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/).

### 7. High: retries and tool fan-out lack a shared execution budget

Evidence: `api/src/services/agents/config.py:33`; `api/src/services/agents/function_calling.py:1745`, `:1789`, `:1903`, `:2005`.

The runner retries broad failures, with two retries by default, without a write-idempotency contract. A remote write can succeed before the response is lost and then be issued again. Parallel mode gathers the whole batch without a semaphore in this layer; one slow call delays the batch. Provider-specific timeouts do not establish a total run deadline.

Fix: add a run deadline propagated to model and tool calls, bounded tenant/server concurrency, overload admission, cancellation and typed retry classification. Retry ambiguous writes only with downstream idempotency support. Add circuit breakers for repeatedly failing dependencies. Do not run dependent writes concurrently merely because the model emitted them in one batch.

### 8. High: synchronous operations block unrelated chats on the event loop

Evidence: `api/src/services/agents/internal_tools/blog_site_tools.py:189`, `:224`; `api/src/services/agents/chat_stream_service.py:692`; `api/src/services/observability/langfuse_service.py:339`.

An async GitHub tool directly calls requests.post with a 30-second timeout. Chat completion also synchronously flushes Langfuse. These operations can block other requests in the same worker, even when the blocked work belongs to a different agent. The flush is after the done event, but still occupies the event loop.

Fix: use a pooled asynchronous HTTP client; temporarily offload unavoidable synchronous SDK calls into a bounded executor. Batch trace export outside request execution and flush on managed shutdown. Measure event-loop delay under a deliberately slow dependency.

### 9. High: checked-in probes target a missing route, and HPA cannot scale out

Evidence: `k8s/application/api-deployment.yml` probes use `/api/health`; `api/src/app.py:533` defines `/health`, `/live`, `/ready`; `k8s/application/api-hpa.yml` sets both minReplicas and maxReplicas to 2.

The app source has no `/api/health` handler. The manifest's direct pod probes would fail as checked in. The HPA's equal minimum and maximum prevent scale-out. A 30-second termination grace period also warrants testing against long-running streams.

Fix: wire startup/liveness to the appropriate live endpoint and readiness to `/ready`; test the rendered deployment against the real app. Set a capacity-backed replica range, then scale using active runs, queue wait and dependency saturation alongside CPU/memory. Add stream draining and decide explicitly whether disconnects cancel or detach runs. Kubernetes distinguishes readiness from restart-triggering liveness: [official documentation](https://kubernetes.io/docs/concepts/workloads/pods/probes/).

Validation: AST inspection confirmed the app's declared health routes; repository search found no alternate handler. Live cluster behavior and deployment overlays were not tested.

### 10. High: load tests cannot substantiate fast answer delivery or reliable success

Evidence: `api/tests/load/chat-stress.js` records `res.timings.waiting`, accepts 90% success, and checks `event_type`; `api/src/helpers/streaming_helpers.py:261` emits `type`.

The first HTTP byte may be headers or a start/status event, not an answer token. The error predicate looks for a field the server does not emit, allowing an HTTP-200 SSE error to pass that predicate. A fixed-VU workload also reduces offered traffic as responses slow, so it is insufficient by itself to locate sustainable throughput.

Fix: parse SSE incrementally and measure first nonempty answer chunk, first tool dispatch, final answer and durable completion separately. Assert terminal success and correct tool results. Run open-loop arrival-rate tests as well as concurrency/soak tests. Include errors, rejection rate and quality in every latency comparison.

### 11. Medium: warm chat still reloads static resources

Evidence: `api/src/services/agents/chat_stream_service.py:1541`, `:1555`, `:1682`, `:1985`; `api/src/services/agents/adk_tools.py:2187`, `:2205`, `:2254`.

KB and tool associations are queried each request; custom and sub-agent loaders also execute. MCP schema hits still register wrappers, and cache misses still connect before the first model request. Empty MCP configurations are not negatively cached. Partial discovery can cache only successful servers for an hour. Conversation summarization can add a blocking model call before the answer request.

Fix: build an immutable, versioned agent execution snapshot containing resource bindings, normalized schemas and stable prompt material. Keep a bounded worker cache backed by Redis. Cache successful empty configurations explicitly. Track discovery per server and do not treat incomplete results as a complete healthy snapshot. Precompute summaries asynchronously with a bounded recent-history fallback.

### 12. Medium: cold MCP acquisition races and retains clients indefinitely

Evidence: `api/src/services/mcp/mcp_client.py:446`, `:459`, `:482`.

Two requests can both miss the dictionary and connect before either stores its client. The last assignment loses the manager reference to the other connection. The dictionary has no size limit or idle eviction; increasing agents and workers multiplies live connections and memory.

Fix: single-flight acquisition per versioned identity, bounded idle client pools, disconnect-on-eviction and reconnect health checks. Do not serialize all agents behind one global lock. Establish FastMCP task/lifecycle ownership before sharing persistent connections.

### 13. Medium: completion is emitted before response persistence

Evidence: `api/src/services/agents/chat_stream_service.py:661`, `:681`, `:715`.

The client sees done and execution status becomes complete before the assistant message is saved. A process failure or persistence error can leave an apparently successful answer missing on reload. The Redis execution registry is useful telemetry, but is not proof of durable execution recovery.

Fix: define separate answer-finished and durably-completed semantics. Commit the message and terminal run record, or a durable outbox entry, before acknowledging persistence. Use monotonic event IDs and explicit reconnect/replay behavior for long runs. Avoid repeating side effects when recovering.

### 14. Medium: diagnostics can expose sensitive tool data and report fake health

Evidence: `api/src/services/agents/function_calling.py:1757`; `api/src/services/mcp/mcp_client.py:26`; `api/src/controllers/mcp_servers.py:249`.

Tool arguments are logged at INFO. JWT diagnostics log every claim except email, although arbitrary claims may contain identity or sensitive attributes. The MCP test endpoint always reports connected and a hard-coded 45 ms without connecting.

Fix: redact by default, log approved metadata, make payload capture opt-in with tenant retention/access controls, and report actual bounded connection/discovery timing. A failed integration must not receive a successful health response.

### 15. High: MCP HTTP destinations lack the validation used by other integrations

Evidence: `api/src/controllers/mcp_servers.py:112`; `api/src/services/mcp/mcp_client.py:176`; `k8s/application/network-policies.yml` API egress rules.

The controller checks that a URL exists and the transport uses it directly. No destination validation is present in this path. The API network policy permits same-namespace traffic and unrestricted destinations on ports 80/443, so it does not independently prevent access to internal HTTP services. A malicious configured MCP endpoint also receives supplied authentication material.

Fix: enforce scheme and destination policy at connection time, covering resolution, redirects, private/link-local addresses and explicitly authorized private enterprise endpoints. Enforce egress restrictions at the runner/proxy boundary. Validate server ownership and destination changes before forwarding credentials. No internal endpoints were probed during review.

## Proposed Low-Latency Architecture

Keep Python until profiling establishes that its runtime is the limiting factor. Removing unnecessary work and fixing streaming should precede a language rewrite.

1. Configuration writes produce a versioned immutable execution snapshot. Discover schemas when attaching/updating an MCP server, with a bounded cold fallback and server-change refresh.
2. Chat admission authenticates the current principal, verifies current authorization/configuration versions and acquires tenant capacity.
3. Load the snapshot from bounded local memory or Redis; load conversation state separately. Instantiate a small request context and request-local tool bindings.
4. Reuse model transports and correctly scoped MCP sessions. Start the model call after only required retrieval and prompt construction.
5. Forward answer deltas immediately. Execute complete validated tool calls under the remaining deadline and permitted concurrency.
6. Stream the final answer, persist completion and dispatch noncritical tracing/analytics asynchronously through bounded infrastructure.

For a single MCP-backed question, the latency decomposition is:

`admission + snapshot/history + model tool selection + MCP execution + final-model first token + delivery`

The current buffered path substitutes final-model full generation for final-model first token. Cache work addresses snapshot/discovery overhead; it cannot remove the remote tool's latency. An explicitly configured deterministic route may bypass tool selection when the operation and argument mapping are known. A server having one tool does not make arbitrary natural-language arguments deterministic.

## What to Cache

| Object | Key / scope | Invalidation and limits |
| --- | --- | --- |
| Compiled agent snapshot | tenant + agent + configuration revision | Update revision on all affected configuration writes; bounded worker LRU and Redis backing |
| MCP schemas | server ID + server revision + visibility/auth scope where relevant | Tool-list changes, config/permission updates, bounded expiry; distinguish empty, failed and partial discovery |
| Enabled tool bindings | tenant + agent + policy/config revision | Attachment, enabled-tool and role changes |
| Schema validators/provider tool definitions | schema digest + provider format | Rebuild on schema change; deterministic tool ordering |
| Stable prompt sections/context-file extraction | tenant + content revision | Content changes and access-policy changes; no cross-tenant sharing by filename |
| MCP connection | server/config revision + identity/security scope + worker loop | Idle/max-size eviction, expiry, disconnect and safe retirement; acquire once per user-bound request initially |
| Conversation summary | tenant + conversation + summarized-message revision | Append-aware revisions; background compaction; bounded recent-message fallback |
| Tool output | approved stable read + identity + arguments + data revision | Opt-in only; exclude failures, writes and polling; short TTL or mutation invalidation |

Do not store live ORM sessions, bearer tokens, mutable request state or request-bearing callables in shared execution snapshots. Authorization decisions require revocation-aware freshness. Provider prompt-cache optimization should follow stable prefix ordering and be evaluated using actual cache-hit telemetry for the chosen provider.

## Benchmark Required Before Claiming Fastest

Compare against a direct model-plus-tool implementation and selected harnesses using identical provider, model, region, tool server, tool schemas, prompts, output limits and task-success criteria. Keep safety/authorization settings equivalent and disclose differences. Measure harness overhead separately from upstream service time; do not subtract unrelated percentile values.

Scenarios: warm no-tool answer; one MCP read; cold worker with schema hit; fully cold discovery; user-token MCP; multiple independent tools; large schemas; long history/compaction; slow tool; provider throttling; Redis failure; two-tenant contention; config invalidation during calls; client disconnect; rolling deployment and worker loss.

Record p50/p95/p99 admission wait, snapshot loading, provider first token, complete tool arguments, MCP connect/list/call, first answer token, final token and durable completion. Also record achieved request rate, active runs, rejection/error rate, task success, token cost, event-loop lag, CPU, memory, DB pool wait and connection counts. Use representative output lengths and publish run duration, sample count, repetitions and workload mix.

Initial engineering hypotheses, not measured promises: target warm snapshot lookup below 5 ms p95, warm pre-model harness work below 50 ms p95 excluding required remote I/O, and answer-delta forwarding below 10 ms p95 after receipt. Set sustainable throughput from the latency/error/quality SLO instead of a maximum connection count. No evidence from this review establishes a world-fastest ranking.

## Enterprise Readiness and Code Quality

Useful foundations already present include async database access, dedicated sessions for concurrent resource loaders, a runtime assigned-tool check, encrypted MCP secret properties, authentication revocation/version checks, Redis-based rate limiting, separate worker deployments, non-root container configuration, readiness code, trace infrastructure and CI unit/integration/dependency-audit steps. These controls need end-to-end validation; their presence does not neutralize the findings above.

The four core agent modules reviewed total 9,447 lines. Size is not itself a defect, but the concrete coupling is problematic: discovery mutates global execution state; orchestration performs provider normalization, retries, caching, persistence and tracing; error dictionaries erase typed failure semantics. Extract boundaries around immutable configuration, request execution, provider events and tool transport. Use typed tool results that retain success, error category, retryability and side-effect status. Add focused contract and concurrency tests before structural refactoring.

Enterprise acceptance should include: tenant/user isolation under concurrency; permission and credential revocation across workers; tested SSO/SCIM and role policy coverage where offered; durable run recovery and idempotent writes; measured noisy-neighbor isolation; restore drills with agreed RPO/RTO; secret rotation; tenant-level audit/trace retention and export/deletion; controlled outbound access; signed/scanned deployment artifacts; and compatibility tests for supported providers/MCP transports. These are verification requirements, not assertions that every capability is missing. Backup automation and restore outcomes cannot be established from the README's manual commands.

## Delivery Order

1. Fix global execution binding, stdio isolation, identity fallback and MCP egress boundaries. Add interleaved tenant/user tests and fail-closed connection tests.
2. Correct probes, HPA settings, cache version propagation, retry/result-cache semantics and fake health responses.
3. Implement true incremental answer streaming and trustworthy SSE benchmarks. Remove blocking tool HTTP and synchronous trace flushes.
4. Add immutable snapshots, prewarmed schemas, negative caching, single-flight bounded pools and stable provider-format schema caches.
5. Add admission budgets, tenant fairness, durable completion/recovery and representative soak/failure/deploy tests. Optimize measured remaining bottlenecks.

## Validation Performed

- Read the relevant source paths and checked existing uncommitted MCP cache changes without reverting them.
- Executed isolated, dependency-light checks using actual AST-extracted methods for tool registry overwrite and provider stream buffering; both confirmed the described behavior.
- Checked health-route declarations against deployment probes and verified emitted SSE field names against load-test predicates.
- Consulted primary MCP and Kubernetes documentation for protocol/lifecycle recommendations.
- Did not run the complete application test suite, contact live MCP/model services, perform exploitation, benchmark production, inspect live cloud controls or establish a dependency vulnerability inventory. Absolute latency, throughput, attack reachability in a deployed environment and recovery guarantees remain to be measured.
