# Follow-up security review — 9 September 2026

Status: Remediated in application code; see [fixes and verification](2026-09-09-remaining-auth-controls-fixes.md). Findings below describe the pre-fix state.

## Summary

One high-priority credential-isolation issue and two medium-priority API-key control issues remain. All three have local reproduction evidence. The latest handoff agent/permission and personal Salesforce/Jira fixes still pass their regression tests.

This was a targeted review of remaining credential resolution and handoff authorization paths, not a whole-project security certification. Infrastructure and production configuration were excluded.

## 1. High — micromobility fallback can select another tenant's personal token

**Location:** `api/src/services/agents/credential_resolver.py:2253`.

The micromobility-specific resolver falls back to selecting a personal token using only `oauth_app_id`. It does not constrain that fallback to an account or tenant. It also decrypts the `UserOAuthToken.access_token` property a second time even though the property already decrypts its stored value.

**Reproduction:** a modeled tenant A agent used a shared platform OAuth app without a current-user mapping. The only matching personal token belonged to a modeled user in tenant B. The actual resolver returned tenant B's token when the stored row used the legacy double-encrypted format. The compiled personal-token query had only `oauth_app_id_1` as a parameter. With the current single-encrypted format, the extra decryption failed and the resolver returned no credentials in the tested setup.

**Practical example:** a background agent in company A could use company B's provider identity when both reference the same platform app and a matching legacy personal token is selected. New-format personal connections can instead fail to resolve.

**Prerequisites and limits:** the reproduced disclosure requires a shared app, a fallback lookup returning one matching foreign record, and the legacy token format. Database responses and tenant memberships were modeled, but the resolver and encryption properties were real. No provider action was performed and no production token inventory was inspected.

**Fix first:** replace the unscoped fallback with explicitly authorized account/tenant selection, fail closed when no authorized connection exists, and use the established token-property decoding helper. Test both current and legacy rows and user-less background contexts.

## 2. Medium — handoff endpoints skip API-key IP, origin and rate controls

**Location:** `api/src/middleware/agent_api_auth.py:334`.

The handoff dependency checks key validity and retains the agent/permissions, but never invokes the IP allowlist, origin allowlist or rate-limit checks enforced by the other API-key authentication path.

**Reproduction:** an in-process HTTP request from an IP outside the synthetic key's allowlist, with an unapproved Origin and valid `handoff:read` permission, received HTTP 200. IP and origin validators were invoked zero times. A rate-limit checker configured to deny the request was also invoked zero times; this proves the missing invocation, not a live Redis quota test.

**Practical example:** a key intended for a partner's fixed server can still be used through handoff endpoints from elsewhere. Its configured request quota is not enforced on that path.

**Fix:** enforce the same key restrictions consistently before handoff dispatch while retaining the new agent scope and explicit read/write permissions. This is missing application enforcement of stored key policy, not a Kubernetes or production-configuration finding. A valid key with the required handoff permission is still necessary.

## 3. Medium — wildcard origin matching accepts unrelated domains

**Location:** `api/src/services/agent_api/api_key_service.py:282`.

Wildcard matching uses `domain.endswith(base_domain)` without requiring a dot boundary.

**Reproduction:** the actual validator returned true for origin `https://notexample.com` when the allowlist contained only `*.example.com`.

**Practical example:** an unrelated hostname ending in the same characters is treated as an approved subdomain. This weakens origin restrictions on paths that call this validator; it does not itself disclose a key or bypass key authentication.

**Fix:** parse the origin as a URL, normalize the hostname and match exact DNS label boundaries. Test legitimate subdomains, unrelated suffix lookalikes, ports and malformed inputs. Merely calling the existing matcher from the handoff path would not fix this separate bug.

## Validation and scope

- Fresh regression run: **116 tests passed**, covering handoff permissions/agent scoping, personal provider settings and migration, alternate JWT authentication, and OAuth authorization/callback boundaries.
- Reproduction script: `docs/reviews/probes/review_remaining_credentials.py`. It uses synthetic credentials, mocked persistence/provider boundaries and in-process HTTP; it does not contact production or external services.
- Previous dependency audits and production build results were not rerun. Application code and dependencies were not changed during this review.
- Only this report and its diagnostic probe were added. The earlier reports remain historical evidence with their remediation links.

Reproduce from the repository root using the existing temporary validation environment:

```sh
PYTHONPATH=api /private/tmp/synkora-harness-validation/bin/python docs/reviews/probes/review_remaining_credentials.py
```
