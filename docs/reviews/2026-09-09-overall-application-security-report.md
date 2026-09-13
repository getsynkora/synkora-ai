# Overall application security assessment

Update: the confirmed SCIM finding is fixed in application code; see [remediation and validation](2026-09-09-scim-tenant-lifecycle-fixes.md). The assessment below records the pre-fix review and its broader verification limits.

Date: 2026-09-09

## Executive assessment

**Do not give the application a security sign-off yet.** The accumulated fixes provide stronger authentication, tenant storage, widget identity and credential isolation, and a fresh broad selection of **540 tests passed**. However, a newly confirmed enterprise provisioning flaw lets one tenant change a global account used by another tenant.

This report assesses application security across categories. It does not treat normal external integrations as vulnerabilities and does not require testing every external website. Production infrastructure remains excluded at the user's request. Tests passing in the workspace do not establish what code is deployed.

## Priority 1 — High: tenant-scoped SCIM can change global accounts

SCIM is the enterprise feature that lets an organization's identity system provision and remove employees.

**Problem:** `create_user` finds accounts globally by email and attaches an existing account to the requesting tenant without establishing that tenant's authority over the account. Subsequent PUT/PATCH operations change global `Account.email`, name and status. DELETE also marks the global account inactive, in addition to removing the local membership.

Locations in `api/src/services/scim_service.py`:

- Lines 267–303: existing-account lookup and tenant membership creation.
- Lines 326–346: PUT changes global email/status after checking local membership.
- Lines 400–430: PATCH changes global email/status.
- Lines 485–513: DELETE globally deactivates the account and revokes sessions.

**Plain-English example:** company A controls its provisioning token and knows the email of a company B administrator. It provisions that email into company A, then disables the account. Company B's administrator is now globally inactive even though their company B membership still exists. It can also change the shared account's email to an address it controls.

**Confirmed evidence:** a local probe executed the real provisioning and PATCH service methods with a real Account model, synthetic identities and modeled database results. It linked an existing foreign account, changed its global email, marked it inactive, and preserved its original owner membership in the other tenant. All four checks were true. Authentication middleware rejects inactive accounts globally (`auth_middleware.py:160–166`).

**Access required:** a valid tenant SCIM token. Token management requires tenant ADMIN/OWNER authority; this is not an anonymous attack. The issue is the ability of that tenant-scoped authority to affect users elsewhere. The target email is sufficient for the demonstrated linking step; no preexisting target membership in the attacker's tenant is required.

**Impact limits:** global email mutation and account deactivation are reproduced. Account takeover through recovery is a serious follow-on risk because recovery looks accounts up by email, but delivery, password recovery and a resulting foreign-tenant login were not executed. Do not call that full takeover demonstrated.

**Required fix:** separate tenant membership lifecycle from global account lifecycle. SCIM should suspend/remove only membership in its tenant. A tenant token must not rename another identity's global email or control its global active status. Existing-account linking needs an explicit, verified ownership/invitation policy. Review create, PUT, PATCH and DELETE together, and add two-tenant tests including administrator accounts. Domain ownership and account identity design must be explicit, not guessed.

[Local reproduction](probes/review_scim_account_scope.py): run `PYTHONPATH=api /private/tmp/synkora-harness-validation/bin/python docs/reviews/probes/review_scim_account_scope.py` from the repository root. No network or production account was used.

## Assessment by security category

| Category | Evidence and current assessment | What matters next |
|---|---|---|
| Authentication and sessions | Access-token type/version, active-account checks, current tenant membership, alternate auth paths and reset/login race regressions passed. Durable account authentication version is present. | Validate release/migration state separately; workspace tests cannot prove production runs these checks. |
| Authorization and tenant isolation | OAuth, Slack/custom-tool assignment, handoff agent scope and tenant-storage regressions passed. **SCIM remains a confirmed exception.** | Fix SCIM first; continue systematic coverage of identity-mutating entry points. |
| Enterprise identity and administration | Role checks protect SCIM token management, but the service exceeds the token's tenant authority. Permission and console-auth tests passed. | Correct provisioning scope before calling enterprise identity secure. SAML/MFA/IdP interoperability was not fully exercised live. |
| Agent tools and code execution | Security-boundary, safe-evaluation, prompt-scanner and data-analysis isolation tests passed. | Prompt detection is supplemental; it does not prove arbitrary model output is safe or certify every compute backend. No live hostile-code isolation test across production workers was done. |
| Files, uploads and storage | File-security, tenant-storage and file-analysis tests passed, including actual staged DuckDB reads. Canonical tenant object namespaces are enforced in inspected storage helpers. | These tests cover application authorization; live bucket permissions and object migration state are excluded. |
| Public widgets and webhooks | Widget identity, alternate JWT, handoff and Recall transaction tests passed. Recall checks signatures and signed routing data. | Keep anonymous/public access separate from administrative authority; full end-to-end production webhook replay was not performed. |
| Credentials and integrations | Personal-member lookup, tenant-scoped connection loading and destination tests passed. Ordinary third-party calls remain supported. | No claim that every provider flow has been exercised against a real service. No blanket restriction on external websites is proposed. |
| Browser/output security | Backend output sanitization tests passed; inspected chat SVG sinks call DOMPurify. | Full browser/XSS coverage was not rerun, so this is partial evidence, not frontend clearance. |
| Dependencies and secrets | Earlier reports record remediated dependency paths and scans. Those are historical evidence, not a fresh advisory/secret audit in this pass. | Recheck locked and shipped dependencies when releasing; previous frontend audit includes documented exclusions. Do not interpret old zero-match reports as proof of zero vulnerabilities. |
| Availability and abuse controls | Existing API-key enforcement tests passed. Prior real-Redis atomic quota tests are recorded separately. | No broad distributed load/DoS test was performed. Rate limits alone do not certify capacity or cost controls. |
| Auditability and enterprise operations | No new confirmed logging issue established here. | Audit-log completeness, tamper resistance, retention, incident response and restore/recovery behavior lack sufficient evidence for sign-off. These are unverified areas, not newly demonstrated defects. |

## Verification details

Fresh command selected the full `tests/unit/services/security` directory, controller security remediation and agent-boundary suites, OAuth authorization/settings, console authentication, permissions, and custom-tool parser/executor suites: **540 passed, four deselected**. The four deselected tests start local Redis; their unchanged prior results are not counted as fresh evidence. Existing test-client deprecation and local bottleneck-version warnings were reported.

The separate SCIM probe is evidence of a failure missing from the passing suites. Production PostgreSQL, deployed K8s/RDS configuration, live IdPs, all optional integrations, full frontend execution and current dependency advisory databases were not examined in this pass. This is a broad source-and-regression assessment, not exhaustive coverage of every route or a complete penetration test.

No application changes were made during this review. Only this report and its synthetic SCIM probe were added. The immediate code priority is the confirmed SCIM cross-tenant identity mutation; unverified categories should not be presented as invented vulnerabilities or marked secure without evidence.
