# Synkora adversarial security review

**Date:** 2026-09-09. **Baseline:** current local working tree, including earlier uncommitted fixes. **Decision:** do not approve hostile multi-tenant enterprise use yet. Several application boundaries permit one user or tenant to reach resources outside their authority. The earlier five fixes do not close these newly examined paths.

This report contains **12 application findings**, plus dependency and deployment findings. Five application findings are rated critical in a shared, untrusted-tenant deployment. Severity includes the stated prerequisites; it does not mean every visitor can exploit every issue. No evidence of a historical compromise was collected.

## What matters most, in plain English

| Priority | Problem | Example of what could happen |
| --- | --- | --- |
| Critical | Local command execution is not safely isolated | An agent command accesses the API process environment or launches another program despite the allowlist. |
| Critical | The sandbox does not isolate tenants | A task for customer A reads a file belonging to customer B. This was reproduced using synthetic files. |
| Critical | File-analysis SQL restrictions are bypassable | A supposed CSV analysis runs unrelated SQL with the application's storage permissions. |
| Critical | Widgets sign unverified user and organization claims | A visitor supplies somebody else's identity and receives a backend-signed credential indirectly used by tools. |
| Critical | Widget history/session routes do not enforce user identity | A visitor with the public widget key requests another user's conversation history, even with identity verification enabled. |
| High | Portal signup creates ordinary tenant membership | A public portal customer becomes a tenant member accepted by management routes that require only tenant membership. |
| High | Removing a team member does not immediately remove access | A former employee continues using an existing token carrying the tenant and role. |
| High | Database TLS does not authenticate the server | An attacker able to intercept the connection can impersonate RDS despite encrypted transport. |
| High | Outbound URL restrictions are inconsistent | An RSS tool sends requests to internal destinations; fixing MCP alone does not prevent this. |
| High | Recall webhook verification fails open | Missing or unavailable verification configuration allows unsigned events into processing. |
| High | Enterprise login policies fail open on errors | Failed SSO/MFA policy lookups let the password-login flow continue. |
| High | Password-reset revocation is best-effort | A password reset can report success while a stolen session remains valid. |

**Immediate containment:** restrict the affected local-command, shared-sandbox and DuckDB tools to trusted operators or disable them for untrusted tenants; suspend unsigned widget identity use and protect history/session routes; prioritize dependency remediation and authenticated database TLS. These are proposed containment actions, not changes deployed by this review.

## Evidence standard and coverage

Inventory found **861 API source Python files**, **123 controller Python files**, and **750 route decorators**. These are inventory counts, not counts of individually audited routes. Manual review traced selected high-risk paths through controllers, dependencies, services and deployment files, including adjacent alternative entry points. It was broader than the earlier pass but is not an exhaustive line-by-line audit of all 861 files.

A [reproducible probe script](probes/security_review_probe.py) recorded **16 unsafe behaviors** across the findings; [recorded results](2026-09-09-security-probe-results.json) are included. It invokes actual functions, selected actual AST blocks, and one actual SQL predicate against synthetic SQLite data. HTTP/DB side effects are mocked except for a controlled sandbox command reading a temporary synthetic marker. It never contacted a production endpoint, read real credentials, or executed an attacker-supplied payload.

Evidence labels below:

- **Reproduced:** the named boundary failed in a controlled local probe. This is not necessarily a complete HTTP exploit.
- **Source-confirmed:** the control flow is present in code; an end-to-end deployed exploit was not attempted.
- **Deployment-dependent:** repository configuration is unsafe or incomplete; whether it is active requires live inspection.

## Application findings

### S01 — Critical: command allowlisting does not isolate execution

**Evidence:** `api/src/services/agents/internal_tools/command_tools.py:641`, `:682`, `:907`; `api/src/services/agents/implementations/claude_code_agent.py:93`.

The validator reduces the executable to its basename. A path to an untrusted program named `ls` passes. Allowed programs also have execution capabilities: `find -exec` is explicitly allowed, and `awk` can read its environment. Path checking applies to only a subset of commands; it does not confine child processes. The local subprocess inherits the parent environment. Separately, the Claude CLI environment explicitly copies the API environment, with filesystem/command tools available in that agent path.

**Prerequisite:** an attacker can influence an agent with these tools enabled, or an authorized tenant configures such an agent. A prompt scanner is not an OS security boundary.

**Reproduced:** validators accepted an untrusted executable path, an environment-reading awk expression and a find child command. A synthetic environment marker propagated into the Claude CLI environment. The validator payloads were not executed.

**Fix:** move untrusted execution out of API/worker credentials and into enforced per-run OS isolation. Use trusted executable resolution where an allowlist remains useful. Remove broad API environment inheritance. **Acceptance:** commands, uploaded executables and nested child processes cannot access API secrets or another tenant's files, including after prompt injection.

### S02 — Critical: the sandbox is a shared executor, not a tenant security boundary

**Evidence:** `services/sandbox/app.py:72`, `:132`; `k8s/application/sandbox-service-deployment.yaml:27`.

The service computes a tenant workspace and uses it as `cwd`, then executes arbitrary commands inside the same sandbox container. All tenant workspaces share `/workspaces`. `_safe_path` protects selected file API parameters but does not constrain what executed programs read or write. A minimal environment does not provide filesystem/process isolation.

**Reproduced:** the real executor received tenant A/agent A and a controlled command. It successfully read a synthetic marker under tenant B/agent B. Only temporary test files were accessed.

**Fix:** use a separate container/job or stronger isolation per trust boundary, mount only that tenant/run's files, and enforce process, network and resource separation. Do not rely on path-string filtering or a shared service key as tenant isolation. **Acceptance:** two concurrent tenant jobs cannot read files, processes, environment or handles belonging to each other; cancellation terminates the full process tree.

### S03 — Critical: DuckDB accepts unrelated SQL with broad storage authority

**Evidence:** `api/src/services/agents/internal_tools/file_analysis_tools.py:30`, `:41`, `:55`, `:83`, `:92`; registration in `tool_registrations/data_analysis_tools_registry.py:307`.

Validation requires only that the query text contain an allowed reader function and the supplied S3 URL. A SQL comment satisfies both conditions. The supplied URL is checked for scheme and `..`, not ownership of an uploaded object. The query executes in an in-process DuckDB connection configured from application AWS credentials, with external access available. Fetching all results precedes output truncation, adding a resource-exhaustion concern.

**Reproduced:** a query containing only `SELECT 1` plus a comment passed the data-source restriction; an arbitrary other-tenant-shaped S3 URL passed URL validation. The probe did not access S3 or execute a filesystem-reading SQL payload. The actual data accessible depends on IAM and DuckDB configuration.

**Fix:** authorize a stored file ID against the execution tenant, construct the data relation server-side, and run analysis with scoped credentials and isolated filesystem/network access. Reject arbitrary statements and external data sources rather than inspecting SQL substrings. **Acceptance:** comments, additional statements, local readers, alternate buckets and oversized result sets cannot escape the authorized dataset or resource budget.

### S04 — Critical: widget identity assertions are signed without adequate verification

**Evidence:** `api/src/controllers/widgets.py:143`, `:1317`, `:1331`, `:1368`, `:1380`, `:1406`.

New widgets receive an identity secret but default to verification disabled. JWT minting checks only for a supplied user and an identity secret, so it still signs client-supplied identity claims. With verification enabled, the HMAC covers only `user.id`, while organization, email and other claims come from the request. Organization input also selects agent routing. A valid proof of one user ID is not proof that the user belongs to a supplied organization.

**Reproduced:** the actual minting block generated a valid signed JWT for a synthetic user and organization while verification was disabled. The organization-claim gap is source-confirmed from the HMAC input and routing/minting inputs. Actual downstream impact depends on how MCP servers authorize these claims; token disclosure to the browser is not required for abuse.

**Fix:** mint tool credentials only from a verified identity. Derive membership server-side or require a canonical, expiring, audience-bound assertion covering every authorization-relevant claim. Never elevate unverified display data into authorization. **Acceptance:** changing user, organization, widget or expiry invalidates the assertion; unsigned widget requests never receive signed downstream authority.

### S05 — Critical: public widget keys authorize other users' history/session operations

**Evidence:** `api/src/controllers/widgets.py:315`, `:354`, `:430`, `:518`, `:1460`, `:1505`.

History accepts a public widget API key plus a conversation ID, external user ID or session ID. It checks the agent's tenant but not a verified end-user identity. Session listing trusts `X-Widget-User-Id`; the widget-key branch of session close makes that header optional. These paths do not enforce `identity_verification_required`. In chat, the anonymous fallback checks `account_id IS NULL`, which also matches identified widget conversations created with `external_user_id` and no account ID.

**Reproduced:** history returned a synthetic private message with verification required and no user proof. The actual anonymous SQL predicate selected a synthetic identified user's conversation in SQLite. Session listing/closing weaknesses are source-confirmed. A conversation UUID is not assumed guessable: external user IDs and session-list discovery are separate access paths.

**Fix:** establish one verified widget session principal and apply it to history, listing, close, resume and chat. Bind anonymous sessions to an unguessable server-issued capability and exclude identified records from anonymous access. **Acceptance:** a public key alone never reads/closes another user's conversation; omission of identity cannot downgrade access checks.

### S06 — High: portal registration grants management-relevant tenant membership

**Evidence:** `api/src/controllers/console/auth.py:482`, `:510`; `api/src/models/tenant_portal.py`; `api/src/controllers/mcp_servers.py` tenant-only management dependencies; `api/src/controllers/agents/mcp_servers.py` attachment/configuration dependencies.

Unauthenticated registration accepts a portal slug, finds an enabled portal and adds the new account to its tenant as `NORMAL`. Public customers and internal team members then share the tenant membership boundary. Several integration management routes require current tenant identity without a separate management permission. Admin checks on agent CRUD do not cover those routes.

**Prerequisite:** an enabled public portal and successful signup/login. **Source-confirmed**, not exercised against a real tenant. The intended public signup feature is not itself the defect; merging customer identity with internal management authorization is.

**Fix:** separate portal customers from staff membership and require explicit permissions for integration management. **Acceptance:** a freshly self-registered portal customer cannot list private integrations, change MCP bindings, alter credentials or read staff channel inboxes, even after switching tenant context.

### S07 — High: membership removal and role changes leave stale token authority

**Evidence:** `api/src/services/team/team_service.py:162`, `:566`; `api/src/middleware/auth_middleware.py:169`, `:212`.

Team removal deletes the membership but does not revoke associated tokens. The common tenant dependency verifies account activity/revocation, then returns the token's tenant claim without checking current membership. Role dependencies similarly consume token claims. The account may legitimately remain active in other tenants.

**Reproduced:** the tenant dependency accepted a synthetic stale tenant claim without any membership lookup. Removal and claim-trusting behavior are source-confirmed. Complete removal-to-HTTP replay was not tested; some endpoints perform additional membership checks, but tenant-only routes remain exposed until token expiry or another revocation event.

**Fix:** check current membership/authorization version at the common boundary; invalidate tenant sessions/role caches on removal or role change. **Acceptance:** an already-issued token loses that tenant's access immediately after removal/demotion across all workers, without disabling unrelated tenant memberships.

### S08 — High: RDS TLS disables server identity verification

**Evidence:** `api/src/config/database.py:189–203`.

Any non-disabled `sslmode`, including `verify-full`, is converted into an SSL context with hostname checking off and `CERT_NONE`. The connection is encrypted but does not establish that the peer is the intended database.

**Reproduced:** constructing the actual async engine options with `sslmode=verify-full` produced disabled certificate/hostname verification. No network interception was attempted. Impact requires an attacker able to intercept or redirect traffic; the DigitalOcean-to-AWS path warrants particular attention.

**Fix:** preserve strict verification semantics, load the appropriate RDS CA trust and validate the endpoint hostname. **Acceptance:** valid RDS certificates connect; wrong-host, untrusted and expired certificates fail. Do not solve CA errors by disabling verification.

### S09 — High: non-MCP tools still permit internal outbound requests

**Evidence:** `api/src/services/agents/internal_tools/news_tools.py:307–342`; `newsletter_tools.py:134`.

RSS validates only the URL scheme and follows redirects. Newsletter image enrichment follows URLs drawn from content. Neither path applies the MCP destination policy. Such requests run from the service network and can reach destinations unavailable to the visitor, depending on deployed egress rules.

**Reproduced:** a loopback URL reached the RSS HTTP client's `get()` method; HTTP was mocked, so no internal endpoint was contacted. Redirect-to-private behavior follows from the configured client and absent destination policy; it was not separately tested.

**Fix:** use a common checked/pinned outbound transport or enforcing egress proxy across tools, fetchers and redirects, with explicit internal-service permissions. **Acceptance:** literal/private IPs, DNS changes, redirects and nested URL fetches cannot reach unauthorized internal or metadata destinations.

### S10 — High: Recall webhook verification accepts missing configuration

**Evidence:** `api/src/controllers/recall_webhooks.py:133`, `:163`, `:195–220`.

Verification is conditional on obtaining a secret. Missing configuration or lookup failure returns no secret and allows processing to continue. `agent_id` is accepted from the query string. The handler can process spoofed status events and attempt notifications for the supplied agent. Notification persistence depends on the model/runtime path; a stored fake notification is not claimed from the probe.

**Reproduced:** an unsigned synthetic request reached the real status-handler dispatch and returned OK when secret lookup returned None. The event handler itself was mocked.

**Fix:** reject unavailable verification configuration; bind signed provider identity/bot ownership to the stored tenant/agent; add replay protection appropriate to the provider protocol. **Acceptance:** missing/failed secret lookup, bad signatures, replay and agent substitution never reach business handlers.

### S11 — High: SSO and tenant MFA policy lookup failures continue login

**Evidence:** `api/src/controllers/console/auth.py:151–177`, `:180–209`.

Both enterprise-policy checks catch unexpected exceptions, log them and continue. Therefore an unavailable policy check can remove the organization's login restriction. Account-level configured TOTP still has its separate check; this finding does not mean every TOTP-enabled account is bypassed.

**Reproduced:** the actual SAML and tenant-MFA policy blocks continued under injected database errors. A complete successful login during a real database outage was not demonstrated; some DB errors also poison the transaction and later fail. A transient/recoverable policy failure is the relevant case.

**Fix:** return a temporary authentication failure when mandatory policy cannot be evaluated, and centralize policy enforcement for all session-issuance paths. **Acceptance:** induced policy-store failures never issue sessions that violate SSO/MFA requirements.

### S12 — High: password reset reports success when session revocation fails

**Evidence:** `api/src/services/auth_service.py:735–797`.

The password update commits first. Revocation then runs in a caught exception block; failure is logged while reset returns success. A stolen session can survive the recovery action that a user expects to terminate access.

**Reproduced:** the actual reset method returned the synthetic account after a forced revocation failure and successful mocked commit. The probe did not use real reset tokens or sessions.

**Fix:** make an authorization-version change durable with the password update, enforce it at request/refresh boundaries and reliably reconcile caches. **Acceptance:** after reset succeeds, all pre-reset access and refresh tokens fail even if Redis was unavailable during the reset and later recovers.

## Dependency findings — current audit, separate from exploit proof

The live `pnpm audit --prod --json` query covered **942 production dependency entries** and reported **52 vulnerability matches: 3 critical, 11 high, 32 moderate and 6 low**, represented by **47 distinct advisory records**. Dependency paths can duplicate advisory counts. These numbers are not 52 demonstrated application exploits. [Machine-readable results](2026-09-09-web-dependency-audit.json) include package versions and dependency paths.

Urgent triage:

- Locked Next.js **16.2.12** matches an AVIF image-optimization code-execution advisory. The maintainer lists **16.3.3** as patched on the 16.x branch. Production image optimization is enabled in the checked-in Next configuration. Actual exposure depends on reachable image inputs and the deployed native image libraries; no image exploit was attempted. [Next.js maintainer advisory](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4).
- A separate Next.js code-execution advisory is explicitly **Windows-hosted**. It must not be presented as a demonstrated Linux/DOKS exploit merely because the scanner matches the package version. [Next.js Windows advisory](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36).
- Transitive **maplibre-gl 4.7.1** appears through React Plotly/Plotly and matches a critical sanitizer-bypass advisory. Whether attacker-controlled content reaches the affected API needs tracing; the package match alone does not prove exploitable XSS. [MapLibre maintainer advisory](https://github.com/maplibre/maplibre-gl-js/security/advisories/GHSA-jrc7-96c5-q579).

Other matches include DOMPurify, Mermaid, Tiptap, sharp and supporting packages. Review affected features and patch compatibility; do not blindly override incompatible major versions or dismiss sanitizer dependencies because surrounding code already calls a sanitizer.

The Python lockfile audit queried **305 unique pinned package/version entries**, including optional and development packages. It reported **9 advisories across 5 packages**: `ecdsa 0.19.2`, `pytest 8.4.2`, `snowflake-connector-python 4.4.0`, `thrift 0.16.0` and `tornado 6.5.7`. [Python audit results](2026-09-09-python-dependency-audit.json) record advisory IDs and suggested fixed versions. This does not establish nine production vulnerabilities: pytest is a development dependency, optional connector activation varies, and exact deployed extras/image contents must be checked. The scanner reported no fixed version for its ecdsa match; applicability or replacement must be evaluated instead of promising an upgrade that does not exist in the audit results. Python advisory exploitability was not independently reproduced.

## Deployment findings — live state not verified

**D01 — High if absent in production: network policies are not applied by the reviewed GitHub deployment step.** `k8s/application/network-policies.yml` exists, but `.github/workflows/deploy-production.yml` explicitly lists applied files and omits it. The file's presence therefore does not prove enforcement. It also allows all destinations on ports 80/443, which is not a complete internal-address exclusion. Confirm live policies/CNI behavior and implement policies that preserve required DNS, RDS and internal traffic. Test enforcement; do not blindly apply an untested default-deny policy during production traffic.

**D02 — High if enabled: optional dashboard configuration grants cluster-admin and provisions a long-lived token.** `k8s/dashboard/dashboard-adminuser.yaml` binds `admin-user` to `cluster-admin`; `k8s/dashboard/get-token.sh` requests `87600h`. That is a requested lifetime, not proof the API server grants it. Dashboard deployment was not found in the reviewed production workflow, so live exposure is unknown. Remove the shared administrative identity or replace it with short-lived, individually attributable least-privilege access.

## Secret scanning

TruffleHog filesystem scanning ran with **verification disabled** over `api/src`, `web`, `k8s` and `.github`, excluding generated/dependency directories. It completed and produced **16 unverified candidates**. Output retained only detector, file and line metadata; no credential values were displayed or checked against provider APIs. Candidates include source-code URI construction and documentation and must be triaged before calling them leaked live credentials. This was not a full Git history scan or an audit of deployed GitHub/Kubernetes secrets.

## Protections observed, with limits

- OAuth state retrieval uses atomic Redis `GETDEL` by default; the examined JWT decoder specifies accepted algorithms.
- Normal authentication checks active account state and revocation. S07 explains why this does not itself verify current tenant membership.
- Examined Slack signature verification uses constant-time comparison and a timestamp window; the separate Recall path differs.
- Examined Mermaid rendering uses strict mode plus DOMPurify. Dependency advisories and actual content paths still require evaluation.
- The sandbox removes most inherited environment variables and guards file-route paths; S02 demonstrates why these do not isolate commands.
- Earlier local fixes cover registry isolation, MCP egress, explicit-identity fallback, public model-config filtering and widget wildcard/rate-limit behavior. Those changes are not proof that every similar path is protected or that production runs the fixes.

## Required remediation and verification

1. **Contain the five critical application findings.** Establish real execution isolation; scope file analysis; replace unsigned/partially signed widget identity; require that identity for every conversation operation. Triage the critical dependency findings alongside this work.
2. **Repair shared authorization and trust controls.** Separate portal customers from staff, enforce membership/version checks, preserve certificate verification, and fail closed on mandatory authentication/webhook policy errors.
3. **Run hostile multi-tenant tests against a production-like deployment.** Two tenants, two users per tenant, anonymous widgets, routed organizations, staff/customer roles, expired/revoked sessions, simultaneous requests and worker restarts. Test access through every alternative route, not only the main chat screen.
4. **Test fault handling.** Redis/database failures during reset, SSO checks and revocation; cancellation and process-tree termination; DNS/redirect changes; oversized output and uploaded files; rollout draining.
5. **Verify live supply chain and infrastructure.** Deployed image digests/native dependencies, RDS CA verification, effective network policies, secret scope, service-account privileges, dashboard presence, ingress configuration and security alerts. Review audit exceptions with owners and expiry dates.
6. **Obtain an independent penetration test before making strong enterprise security claims.** Use a staging replica with synthetic data and explicitly agreed scope. Require closure evidence for each finding and rerun negative tests after remediation.

**Not established in this review:** complete 750-route coverage, absence of SQL injection/XSS in all integrations, live SSRF reachability, cloud IAM correctness, exploitation of any dependency advisory, full Git-history secret cleanliness, kernel/container escape resistance, backup/restore security, or compliance certification. No numeric security score is assigned because it would imply assurance the evidence does not support.

This turn produced the report, scan artifacts and probes; it did not patch these newly discovered application defects, change production, commit or push code. Earlier local fixes were preserved. A report with reproduced failures is evidence of work to do, not a passing security certification.

## Reproducing the evidence safely

From `api`, using an environment with the project's dependencies:

```sh
PYTHONPATH=. python ../docs/reviews/probes/security_review_probe.py
```

The probe supplies synthetic application secrets and in-memory/mock dependencies. Its sandbox test executes only a fixed local Python command against a temporary marker. A `true` result means the unsafe behavior was reproduced; these are diagnostic probes, not passing security regression tests. Turn them into tests asserting rejection as fixes are implemented. The controller/policy probes do not start the full API or replace real multi-user HTTP acceptance tests.
