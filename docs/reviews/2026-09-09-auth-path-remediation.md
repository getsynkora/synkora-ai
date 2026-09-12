# Authentication-path remediation — 9 September 2026

The three high-priority findings and related portal finding in `2026-09-09-post-fix-security-review.md` have been addressed in the working tree. This records application changes and local validation; no production deployment was performed.

| Finding | Fix | Practical result |
| --- | --- | --- |
| Anonymous OAuth integration setup | All 19 provider authorization routes require an authenticated account and current tenant membership. App-level connections require the existing `oauth_apps.update` permission. Every integration state binds account, tenant and authentication version. Callbacks recheck account status, membership, permission, version and app ownership. | An anonymous visitor cannot create an integration authorization flow, and removing a member before the callback prevents their credential update. |
| Handoff JWT bypass | Account JWTs use shared access-token validation, Redis revocation, active account checks, durable authentication version and current tenant membership. | A revoked token or removed member cannot keep passing handoff authentication using the old tenant claim. |
| WebSocket authentication bypass | Shared checks run at the handshake and before every new chat turn, using a fresh database session. Authentication rejection closes the socket with code 1008. | Expired or revoked tokens, disabled accounts, old authentication versions and removed memberships cannot start another chat turn. This does not forcibly cancel a turn already running. |
| Members-only portal exposure | Member-only visibility uses the same validated account and membership context. Invalid credentials give public-only listing results; members-only detail requires authorization. | An old tenant claim alone no longer grants member-only portal visibility. |

The dashboard's connection buttons now use authenticated `POST /api/v1/oauth/initiate`, then navigate to the returned provider URL. This preserves browser connection setup after anonymous initiation is removed. Provider-specific initiation is retained for HubSpot, Salesforce, Intercom and Micromobility. Salesforce state now carries its tenant, and app-level Salesforce credentials and instance configuration go to a tenant clone when connecting a platform app.

## Validation

- **449 backend tests passed**, including the new alternate-authentication and OAuth authorization regressions and the earlier security regression suites.
- All 19 provider authorization routes reject anonymous requests. All 19 callbacks reject legacy state lacking the initiating identity.
- Authorized GitHub connection roundtrips pass for tenant-owned and platform apps; platform credentials remain unchanged while the clone receives the token.
- Dashboard initiation tests pass for GitHub, HubSpot, Salesforce, Intercom and Micromobility. Salesforce app-level clone storage is separately tested.
- WebSocket tests exercise a successful first turn followed by rejection after expiry, revocation, account deactivation, membership removal or authentication-version change.
- **122 frontend tests passed**. The production webpack build, including TypeScript checking, passed. Targeted frontend ESLint, Python Ruff and `git diff --check` passed.

External providers, Redis and database boundaries in the new diagnostic tests are mocked. JWT encoding/decoding and the application authorization methods are real. These results do not establish live provider compatibility or constitute a production penetration test. Dependency versions were not changed in this remediation; audits were not rerun.

## Rollout notes

Deploy the updated frontend and API together. External callers that used an anonymous browser navigation to a provider `/authorize` route must use authenticated initiation. OAuth flows started before this update lack the new state binding and must be restarted. Shared connection setup requires the tenant's existing `oauth_apps.update` permission; personal connection setup requires current membership.

No additional schema migration was introduced in this turn. The earlier migration `20260909_0001` adding `accounts.auth_version` and Recall receipts remains required before deploying the accumulated API changes. Production infrastructure and configuration were not changed. Preexisting workspace changes were preserved.

The earlier review and its probe remain historical baseline evidence. Regression tests, rather than the baseline probe's former acceptance assertions, describe the fixed behavior.
