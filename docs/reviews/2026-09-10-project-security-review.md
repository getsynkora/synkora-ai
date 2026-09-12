# Project security review

**Remediation update:** all five findings below have been addressed in the working tree. See [implemented fixes, validation and rollout notes](2026-09-10-five-findings-remediation.md). The remainder of this document records the original pre-fix assessment; it is not a statement about deployed production code.

Reviewed September 9–10, 2026. Target: current working tree, including existing uncommitted remediation. This report supersedes neither the historical reports nor their remediation records; it identifies remaining issues in the inspected source.

**Assessment: address the findings below before security sign-off.** Five remaining findings: two high and three medium. Passing regression tests and clean dependency audits do not cover these missing boundaries. No application code was changed by this review.

## Findings

### SR-01 — High: tenant members can replace or delete Okta SSO configuration

**Locations:** `api/src/controllers/okta_sso.py:287`, `:351–387`, `:401–416`; `api/src/middleware/auth_middleware.py:175–232`; `api/src/services/sso/okta_sso.py:44–48`, `:98–110`.

POST, PUT and DELETE `/api/v1/sso/okta/config` require `get_current_tenant_id`, which checks account authentication and tenant membership, but not administrator authority. No router-level role dependency compensates for this. A regular member can replace the IdP domain/client configuration, disable SSO, or delete it. By comparison, the SAML configuration controller explicitly requires ADMIN authority.

Changing only `domain` preserves the stored client secret. A subsequent callback decrypts that secret and posts it to the token endpoint constructed from the newly supplied domain. This creates a credential-exfiltration path as well as unauthorized configuration changes: an attacker can initiate login to obtain state, then submit a callback code to trigger the exchange against their HTTPS endpoint. This chain follows the source; no real IdP secret was transmitted in this review. The current Okta callback returns a redirect with user email and does not itself issue an application session, so this finding does **not** claim demonstrated account takeover.

**Evidence:** offline probe executes the actual update function body with a synthetic database/model and changes the domain and enabled flag without any role input. Inspection of the complete dependency chain establishes why a non-admin member reaches that body. This was not an authenticated end-to-end HTTP exploit.

**Fix:** require a current database-backed ADMIN/OWNER check for configuration writes and sensitive reads. Validate the configured IdP origin, and require explicit credential replacement/reconfirmation when the credential destination changes. Add member-denial tests for all three write methods and a test that changing domains cannot forward a retained secret.

### SR-02 — High: monitoring connection tests permit server-side requests to internal services

**Locations:** `api/src/controllers/monitoring_integrations.py:26–65`, `:179–208`, `:276–296`, `:330–418`.

A tenant member can create a monitoring integration with caller-controlled configuration and invoke `/api/v1/monitoring/{integration_id}/test`. The webhook helper forwards the configured URL, HTTP method and headers directly to `requests.request`. There is no private-address, metadata-address or destination-ownership check. Prometheus, OTLP and Slack helpers also use unchecked destinations. Requests follows redirects by default. Slack's error branch returns the remote response body to the caller.

This crosses from tenant-controlled input into the API server's network authority. Depending on reachable services, an attacker can probe internal endpoints or issue state-changing requests. The generic webhook body is fixed to a small test object; it is **not** a general arbitrary-body proxy. Full internal response disclosure is limited to helper branches that return `response.text`. Network access and internal-service authentication determine actual impact; no production network was probed.

**Evidence:** actual helper functions, with HTTP I/O mocked, forwarded `http://127.0.0.1:5002/v1/tools/initialize` and the caller's DELETE method. A synthetic internal error response was returned through the Slack helper. The probe proves dispatch and disclosure behavior, not successful modification of that example service.

**Fix:** use a centralized transport that validates and pins resolved addresses, bounds response sizes, and checks redirects. Public webhooks should use public destinations. Legitimate private monitoring should require an operator-approved destination policy or a tenant-isolated connector; do not remove support for ordinary external integrations. Limit allowed methods and avoid returning internal response bodies. Add private-IP, redirect, DNS-change and response-limit tests.

### SR-03 — Medium: widget CORS permissions apply to authentication routes; dashboard origins ignore scheme and port

**Locations:** `api/src/middleware/cors_middleware.py:120–126`, `:175–180`, `:237–240`, `:294–298`, `:331–337`, `:360–363`; `api/src/controllers/console/auth.py:537–586`.

Any request carrying `X-Widget-API-Key` uses that widget's origin policy, regardless of the requested route. A valid widget key whose policy allows an origin therefore enables credentialed CORS on `/console/api/auth/refresh`. The key need not belong to the authenticated user or tenant. Separately, dashboard matching falls back to hostname comparisons and accepts different schemes and ports from the configured origin.

The refresh handler accepts its HttpOnly cookie and returns fresh access and refresh tokens in JSON. A malicious **same-site** page with an allowed widget key can potentially send the victim's refresh cookie and read those tokens. A page at another HTTPS port on the allowed dashboard hostname can also pass the origin comparison. `SameSite=Strict` blocks an ordinary unrelated-site cookie attack; possession of a widget key alone is not sufficient. An attacker-controlled sibling subdomain, same-host service, or comparable same-site foothold is a material prerequisite. Browser cookie delivery and exploitation were not exercised live.

**Evidence:** probe executes the current CORS class, models an accepted widget lookup, and demonstrates credentialed origin approval on the refresh path. It separately confirms that both a different scheme and a different port pass dashboard matching.

**Fix:** use exact scheme/hostname/effective-port matching for dashboard origins. Restrict widget CORS handling to explicit widget routes and disable ambient credentials there where possible. Require an approved dashboard Origin/CSRF control for cookie-authenticated refresh. Add browser tests for a sibling-subdomain page and a different-port page, including valid foreign widget keys.

### SR-04 — Medium, configuration-dependent: download tokens use an empty signing key with dotenv-only settings

**Locations:** `api/src/controllers/data_analysis.py:31–64`, `:339–376`; `api/src/config/settings.py:127–132`; `api/src/config/security.py:21–26`, `:124–132`.

The application supports loading validated settings from `.env`. The download-token helpers bypass those settings and independently read `os.getenv("SECRET_KEY", "")`. Pydantic dotenv loading does not populate the process environment. Consequently, a deployment that supplies its key through `.env` alone can have a valid application signing setting while download tokens are signed and verified using an empty key.

Any authenticated user can then forge a token for a known file under `/tmp` on Linux. The download route validates only the token and `/tmp` containment, not the user's tenant ownership. This can expose other jobs' temporary files where paths are known. It does not allow arbitrary files outside `/tmp`, and deployments that export a strong `SECRET_KEY` into the process environment do not have this empty-key condition. On this macOS workspace `/tmp` resolves to `/private/tmp`, so the full file-serving path was not demonstrated locally.

**Evidence:** probe independently creates a token with an empty HMAC key and the actual verification function accepts it when `SECRET_KEY` is absent from `os.environ`. Application settings and entry-point inspection establish the supported configuration mismatch. No real file was read.

**Fix:** use the validated settings object and fail closed on missing keys. Sign a tenant-bound resource identifier rather than an arbitrary filesystem path; resolve and authorize the resource server-side. Reject future timestamps as well as expired tokens. Test dotenv-only configuration, foreign-tenant access, and canonical path handling.

### SR-05 — Medium: OpenAPI import validates DNS separately from the connection

**Locations:** `api/src/controllers/custom_tools.py:245–266`; `api/src/services/security/url_validator.py:87–104`, `:178–187`.

The OpenAPI import route resolves and checks the URL with `validate_url_for_openapi_import`, then passes the original hostname to an ordinary `httpx.AsyncClient`. The connection resolves DNS again; the validated address is not pinned. An attacker controlling DNS can return a public address during validation and a private address during connection. DNS failures also return an empty list from the validator's resolver, which does not itself reject the URL. The response is buffered without an explicit byte limit.

This is a remaining SSRF/availability gap in an otherwise deliberate SSRF protection path. The initial direct private-IP check works. HTTPX does not follow redirects here by default, so this finding does **not** allege a redirect bypass. Successful exploitation depends on DNS timing, reachable destinations, and—in the case of content imported into a tool—a suitable JSON/OpenAPI response.

**Evidence:** source-level validation/connection analysis; no live rebinding exploit was run. Confidence is high that the address check and connection are separate, while exploitability in a specific network is unverified.

**Fix:** use the existing `fetch_public_url` bounded, DNS-pinned transport or an equivalent explicitly authorized private connector. Add a transport-level regression where DNS changes between validation and connection, plus failed-resolution and oversized-response cases.

## Verification performed

| Check | Result and limits |
| --- | --- |
| Backend security suites | 433 passed initially; four quota tests could not create a private Redis socket in the sandbox. Reran the complete quota module with the necessary access: nine passed, including the four previously blocked cases. **437 distinct tests passed**, not 442. |
| Frontend suite | **123 tests in 11 files passed** with Node 22.19.0. Node 20.17.0 initially failed while loading Vitest's ESM dependency; this was an environment compatibility failure. |
| New offline probes | All nine diagnostic outputs demonstrated the reported boundary behavior. I/O and widget lookup were synthetic; see `probes/review_remaining_boundaries.py`. |
| Python dependency audit | Fresh frozen `uv.lock` export; pip-audit 2.10.1 checked **251 applicable packages**, no advisories returned, no ignore flags supplied. Environment markers reflect this macOS audit; Linux-only and optional dependency sets are not fully covered. |
| Frontend dependency audit | Fresh `pnpm audit --prod`: zero reported advisories, metadata counts 673 dependencies. `web/package.json` configures exclusions for `CVE-2026-4800` and `CVE-2026-14257`; this is not an unfiltered clearance. |
| Secret scan | TruffleHog filesystem scan with verification disabled returned 42 unverified candidates. Inspected source candidates were documentation examples, test/default credentials, function-name matches and a dependency checksum; generated-cache matches also occurred. No live credential was confirmed. This was not a complete Git-history scan, and zero verified results is expected with verification disabled. |

Backend command (from `api/`):

```sh
/private/tmp/synkora-harness-validation/bin/python -m pytest \
  tests/unit/services/security \
  tests/unit/controllers/test_security_remediation.py \
  tests/unit/controllers/agents/test_security_boundaries.py -q -k 'not redis' --tb=short
/private/tmp/synkora-harness-validation/bin/python -m pytest \
  tests/unit/services/security/test_provider_scope_and_quota.py -q --tb=short
```

Offline probe (from repository root):

```sh
PYTHONPATH=api /private/tmp/synkora-harness-validation/bin/python \
  docs/reviews/probes/review_remaining_boundaries.py
```

The source hashes, fresh dependency reports and probe output are recorded beside this report as `2026-09-10-review-evidence.json`, `2026-09-10-python-audit.json`, and `2026-09-10-web-audit.json`. Raw secret-scan output was kept outside the repository and is not included in the report.

## Broader coverage and remaining uncertainty

- **Authentication and tenant isolation:** inspected the common account/membership dependencies and alternate-auth regression suites, including SCIM, widgets, OAuth credentials, password-reset/session versioning, handoffs and webhook boundaries. Earlier fixed findings are not repeated as current defects. This does not cover every registered API route or every role/resource combination.
- **Agent execution and file access:** examined storage/public-HTTP helpers, execution-related searches and sandbox isolation configuration; relevant existing security tests passed. Bubblewrap intentionally shares the service network (`services/sandbox/isolation.py:46`). The Compose sandbox uses a development default service key and the common service network. This configuration must not be treated as a hostile multi-tenant boundary. Linux namespace escape resistance and all compute backends were not tested live.
- **Browser security:** inspected HTML/SVG sinks, strict Mermaid settings, token storage and extension permissions; frontend tests passed. Full browser XSS/CSRF testing, extension execution and mobile runtime security remain unverified.
- **Infrastructure:** inspected Compose, Kubernetes network policies, Dockerfiles and selected CI workflows as source. Default-deny and non-root controls exist in some manifests, but actual application of policies is unknown. In particular, the API egress rule's `to: []` on ports 80/443 is not restricted to public destinations; it does not compensate for application SSRF. The internal ML service has no request authentication or model/cache limits and accepts caller-selected models; exposure depends on network access. It is not host-published in the inspected Compose definition.
- **Supply chain:** the main lockfile audits exclude packages installed independently in service Dockerfiles, globally installed PM2, container OS packages, browser binaries/models, docs/extension dependencies, and Flutter packages. `services/ml/Dockerfile` installs unpinned packages. Scan built images/SBOMs and each shipped component before treating dependency coverage as complete.
- **Operations and availability:** no production requests, live cloud/IdP/payment tests, penetration testing, broad stress testing, recovery tests, or audit-log retention/tamper-resistance verification were performed. No assertion is made that the working tree is deployed.

## Remediation order

1. Add Okta administrative authorization and prevent retained credentials from following a changed IdP origin.
2. Close monitoring SSRF paths and use the same approved transport for OpenAPI imports.
3. Separate widget CORS from dashboard/session routes and enforce exact dashboard origins.
4. Replace download-token environment lookups with validated settings and tenant-bound resource authorization.
5. Run the new negative tests and end-to-end browser cases, then validate the actual Linux images, dependency sets and deployment policies.
