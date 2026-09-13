# Project security review — 9 September 2026

Update: these nine findings have been addressed in the workspace; see [remediation, validation and rollout requirements](2026-09-09-independent-security-fixes.md). The assessment below records the pre-fix state.

The current workspace still has serious security vulnerabilities. The highest priority is shared sandbox isolation, followed by phone webhook authentication and browser session/file boundaries. Passing existing tests does not cover these failures.

Reviewed base commit: `e59c7c267681d476ce78870da747c648a5e3ace8`, **including existing uncommitted changes**. Earlier reports describe vulnerabilities that have since been fixed; they are not treated as current findings without checking current code. This review added only this report and an offline probe. No application remediation or deployment was performed.

## Findings

Severity reflects impact and prerequisites in the checked source. Production exposure depends on deployed features and configuration. References are relative to the repository root.

### 1. Critical — shared sandbox permits cross-tenant file access

**Locations:** `api/src/services/agents/internal_tools/command_tools.py:825–860`, `services/sandbox/app.py:130–164`, `services/sandbox/Dockerfile:25–26`, `api/src/services/compute/backends/factory.py:14–35`.

The remote command path deliberately skips file path authorization. The sandbox only constrains the command's working directory; arguments can name arbitrary files. All tenant workspaces are accessible to processes running as the same sandbox user. The backend factory routes tenants to this shared service.

**Reproduced:** the real command validator accepted `cat` with a synthetic tenant B file path, and the real sandbox handler executed it under tenant A and returned tenant B's marker. No interpreter bypass, secret service key theft, or container escape was necessary. The probe supplied a synthetic service key, as the normal backend would do.

**Impact/prerequisite:** a user able to invoke an agent's remote command tool can read other tenants' staged files. Broader integrity and process risks follow from shared execution, but this probe demonstrated a read only. Guessing a file UUID is not a dependable defense when directory listing also runs in the same filesystem.

**Fix:** isolate execution at the OS/container boundary per tenant or stronger per-session scope, mount only that scope's files, and keep control-plane credentials outside executable workloads. Enforce path authorization before dispatch as defense in depth. Add a real two-tenant execution test. A safe `cwd` and non-root shared UID do not create tenant isolation.

### 2. High — omitting the phone webhook secret bypasses authentication

**Locations:** `api/src/controllers/phone_calls.py:103–123`; `api/src/services/voice/inbound/vapi_provider.py:49–63,66–145,149–215,233–277`.

`POST /api/v1/phone/webhook/vapi` enters signature verification only when the caller supplies `x-vapi-secret`. Omitting the header reaches `handle_webhook` directly, including when an agent has a configured secret. There is no second verification in the provider dispatcher. A supplied header also bypasses checking when the phone lookup does not resolve a secret; the handler supports assistant-ID routing separately.

**Reproduced:** executing the actual controller function with a synthetic request and omitted header invoked the mocked business handler without consulting its signature verifier or database. Real downstream code creates call/conversation records, processes agent messages, and persists end-of-call transcripts.

**Impact/prerequisite:** an unauthenticated caller who knows a configured phone number or assistant ID can forge call-start events; subsequent forged events can affect call data and agent execution. Full database/LLM side effects were traced, not executed.

**Fix:** resolve the trusted integration for every supported routing mode, require its configured secret and the supplied header, reject unknown/missing credentials, and verify before side effects. Add missing-header, unknown-number, assistant-ID and incorrect-secret tests; then check duplicate event handling.

### 3. High — explicit browser session IDs override tenant isolation

**Locations:** `api/src/services/agents/tool_registrations/browser_tools_registry.py:15–39`; `services/scraper/browser_session.py:202–215`.

Browser tool arguments expose `session_id`. `_resolve_session_id` returns any explicit value unchanged before considering trusted runtime identity. The scraper indexes sessions globally using only that string. Cookie, storage, navigation and page interaction tools consequently address the same browser context across tenants when given the same ID.

**Reproduced:** the actual resolver returned an identical session key for two distinct tenant/conversation contexts supplying the same explicit ID. The source confirms that scraper lookup has no tenant ownership check. No live browser cookies were accessed.

**Impact/prerequisite:** a browser-tool user who knows or causes reuse of another session's ID can address its authenticated browsing context. Tool schemas advertise the literal `default`, making collisions plausible even without learning a random conversation ID. Random IDs alone do not authorize access.

**Fix:** derive the service session identity from trusted tenant, conversation and principal context; treat a caller's session label only as a namespaced suffix. Pass authenticated ownership metadata to the scraper and reject mismatches. Remove the global fallback for authenticated work.

### 4. High — browser file upload accepts arbitrary scraper filesystem paths

**Locations:** `api/src/services/agents/tool_registrations/browser_tools_registry.py:1201–1211`; `api/src/services/agents/internal_tools/browser_interactive.py:656–675`; `services/scraper/app.py:1547–1565`.

Model-supplied `file_paths` pass directly to Playwright `set_input_files`. No upload ownership lookup or filesystem containment check occurs along that path. Restricting navigation to public websites does not stop upload to an attacker-controlled public website.

**Reproduced:** the actual scraper handler passed an absolute path outside any workspace to a mocked Playwright locator. This proves missing authorization at the sink; a real browser upload or theft of a deployed secret was not performed.

**Impact/prerequisite:** an agent with browser upload and navigation capabilities can attach files readable by the scraper process to a web page. The exact sensitive files available depend on its image, volumes and runtime.

**Fix:** accept tenant-authorized upload/object IDs; stage permitted content in a private session directory and pass bytes or canonical staged paths to Playwright. Reject arbitrary local paths, traversal, symlink escapes and cross-session files. Test an actual browser with synthetic permitted and forbidden files.

### 5. High — public debate responses disclose callback bearer credentials

**Locations:** `api/src/controllers/agents/war_room.py:527–543,929–938,1002–1020`.

Participants store `auth_token` and `callback_url`. The unauthenticated public endpoint returns `_session_to_schema`, which returns entire participant dictionaries. It does not apply the safer `DebateParticipantSchema` allowlist, and the route has no response model filtering.

**Reproduced:** the actual serializer returned a synthetic callback bearer secret in the public payload.

**Impact/prerequisite:** anyone with a public debate link can obtain configured external-agent callback credentials. Their authority depends on the external service. This affects secrets of participants who legitimately joined the debate, not merely attacker-supplied secrets.

**Fix:** separate persisted participant credentials from public DTOs; explicitly select public fields in every response and stream. Rotate real tokens that were exposed in public debates after correcting serialization. Test with a populated secret, not just participants without credentials.

### 6. High — public debate callbacks permit internal-network requests

**Locations:** `api/src/schemas/debate.py:84–91`; `api/src/controllers/agents/war_room.py:448–462,929–938`; `api/src/services/agents/workflows/debate_executor.py:459–499`.

An external participant can provide an unrestricted `callback_url`. During execution the server POSTs debate data to it using a normal HTTP client, without the existing public-destination protections. Callback JSON is returned as participant content. Public external participation requires possession of the debate share link, not a tenant login.

**Reproduced:** the actual callback method dispatched a loopback URL and returned a synthetic internal response through an HTTP mock transport. No real internal host was contacted. Real response disclosure depends on the target accepting the fixed POST payload and returning usable JSON; arbitrary GET or arbitrary request bodies are not demonstrated.

**Fix:** apply the shared public HTTP boundary to callbacks, validate destinations at connection time, constrain redirects and response size, and block private/link-local destinations with network egress rules. Keep normal public integration endpoints supported. This follows [OWASP's SSRF prevention guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).

### 7. Medium — spectators can impersonate external debate participants

**Locations:** `api/src/controllers/agents/war_room.py:465–477,966–999,1014–1015`.

The public respond endpoint accepts only the public share token and `participant_id`. Participant IDs are disclosed in public data/messages. `_respond_internal` validates that the ID exists and is external, but requires no participant credential. The callback `auth_token` is not checked here and would not be an appropriate public identifier.

**Reproduced:** an ID taken from the public serializer was sufficient for the actual response method to accept a synthetic response for that participant. Database commit was mocked.

**Impact:** a spectator can submit an argument as another external participant and occupy its response slot. Round/status bounds also need enforcement; the method currently does not require an active current round.

**Fix:** issue a separate private participant capability on join, store its hash, require it on respond, and never disclose it to spectators. Enforce current-round/session status and atomic uniqueness of accepted responses.

### 8. Medium — generated debate scripts permit Python code injection

**Locations:** `api/src/controllers/agents/war_room.py:596–626,633–715`.

The public script generator embeds query-controlled `agent_name` and `model` inside quoted Python strings without escaping them. `provider` is also interpolated into generated code later. An attacker can construct a download link whose returned script includes additional Python statements.

**Reproduced:** a synthetic `agent_name` created a new top-level assignment in the generated script's parsed AST. The downloaded script was not executed.

**Impact/prerequisite:** a victim must download and run the generated Python script, as the feature instructs. This is client-machine code injection, not demonstrated server-side execution.

**Fix:** serialize all interpolated data as safe Python literals or load separate JSON data; validate provider against an enum. Parse generated scripts in regression tests using quotes, backslashes, newlines and statement separators in every input.

### 9. Medium — async database TLS disables certificate verification

**Location:** `api/src/config/database.py:192–203` (also SSL mode stripping at `135–143`).

For any non-disabled SSL mode, the async connection options create a default SSL context and then explicitly turn off hostname and certificate checks. Even an operator requesting `sslmode=verify-full` receives `CERT_NONE`. The mode regex only captures word characters, further losing the distinction between `verify-ca` and `verify-full`.

**Evidence:** direct source inspection. No TLS interception or database connection was attempted.

**Impact/prerequisite:** an attacker able to intercept or reroute database traffic can impersonate the database endpoint; encryption alone does not authenticate the server. This is conditional on network position, unlike the remotely accessible authorization failures above.

**Fix:** preserve explicit SSL mode semantics, use a trusted CA with certificate verification and hostname validation for `verify-full`, and test rejection of an untrusted certificate and wrong hostname. [Python SSL documentation](https://docs.python.org/3.12/library/ssl.html) describes the certificate and hostname checks.

## Validation and scope

- **545 distinct existing tests passed:** 461 in the broad security/controller selection, four quota tests after rerunning outside filesystem sandbox restrictions so private Redis could start, and 80 sandbox-client/KB-webhook/general-webhook tests. Initial four Redis setup errors were environmental; they are not counted as product defects. Warnings concerned TestClient deprecation and a local bottleneck version.
- **Nine offline diagnostic checks reproduced the new boundary failures**, using [the saved probe](probes/review_execution_and_debates.py). Some are two checks for one finding; database TLS is source-only. The probe uses actual extracted functions, mocks HTTP/database/browser dependencies, and executes only a bounded `cat` against a temporary synthetic file. It does not prove an end-to-end deployed exploit.
- Authentication, revocation, current tenant membership, SCIM membership lifecycle, personal OAuth authorization, tenant storage, widget identity, custom tool destinations and Recall transactions have current passing regression evidence. Earlier reports' fixed SCIM/storage/session findings are not repeated here.
- Frontend review inspected HTML/SVG sinks, Mermaid sanitization and CSP. Inspected SVG renderers use DOMPurify; Mermaid also selects strict mode. CSP still includes `unsafe-inline` and `unsafe-eval`, a defense-in-depth limitation rather than a newly demonstrated XSS finding. No full frontend build or browser penetration test was run.
- Deployment review included sandbox Docker/Kubernetes definitions, network policy and CI snippets. Kubernetes settings were read from the repository, not queried from a cluster. Pod/service isolation does not isolate tenants inside one process/filesystem. Runtime IAM, mounted secrets, CNI enforcement, bucket policies and deployed revision remain unverified.
- A fresh TruffleHog filesystem scan covered `api/src`, `services`, `web/app`, `web/components`, `extension`, `k8s`, `helm` and `.github`, with credential verification disabled. It completed with 39 unverified matches, including bytecode duplicates and source examples/templates. Sampled source matches were placeholders or identifier false positives; no live credential was confirmed. It logged sandbox-related temporary-artifact cleanup warnings. This was not a full Git history scan and does not clear all secrets or local environment files. Raw candidate values were not placed in this report.
- **Fresh frontend production dependency audit: zero advisories across 673 dependencies.** Ran `pnpm audit --prod --json` against a temporary copy of the current `web/package.json` and `web/pnpm-lock.yaml`, with `pnpm.auditConfig` removed so the two configured CVE suppressions did not apply. The registry request succeeded after a sandbox DNS failure was rerun with approval. The result is saved as [audit evidence](2026-09-09-independent-web-audit.json). This establishes registry matches for that lockfile, not reachability or deployed-image contents. Python dependency reports read in this review remain historical; container/OS packages, Flutter, docs and extension dependency graphs were not freshly audited.

Reproduce the offline checks from the repository root:

```sh
/private/tmp/synkora-harness-validation/bin/python docs/reviews/probes/review_execution_and_debates.py
```

The probe intentionally asserts that vulnerabilities reproduce. After remediation, replace those diagnostic expectations with denial/isolation regression tests.

## Remediation order

First close shared sandbox access and missing phone webhook authentication. Then bind browser sessions and uploads to trusted ownership. Correct public debate serialization and callback destinations together, rotate exposed callback credentials, and add participant authentication. Fix script generation and database certificate verification. Validate each change with negative cases spanning two tenants and with the actual deployment boundary before considering security sign-off.
