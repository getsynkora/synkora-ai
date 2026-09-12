# SCIM tenant lifecycle security fix

Date: 2026-09-09

The confirmed SCIM issue in the [overall application security report](2026-09-09-overall-application-security-report.md) is fixed in the workspace. A tenant provisioning token no longer changes shared login identity or globally deactivates an account.

## Resulting behavior

- Provisioning an email that already has a global Account is rejected; an email match alone cannot create a new tenant association. Existing accounts must first enter through the application's authorized membership/invitation process. Existing tenant members remain visible to SCIM and can be managed locally.
- PUT/PATCH cannot change global login email or global account status. Changed login/email values are rejected with HTTP 400. Names are stored in a tenant-local SCIM profile rather than overwriting the Account name.
- `active=false` removes only the current tenant membership and retains a tenant-local SCIM record so the IdP can find and reactivate it. Existing live-membership authorization checks deny access to that tenant.
- `active=true` restores the tenant membership with its prior role, custom role and permission settings. It does not reactivate an account disabled globally.
- DELETE removes only the current tenant's membership and SCIM profile. Other tenant memberships, account email/name/status, credential version and global sessions are unchanged.
- PATCH validates all operations before any mutation; a later rejected operation cannot leave an earlier deactivation ready to commit.
- Account-level database locks serialize SCIM lifecycle operations for an authorized resource. No production concurrency benchmark was performed.

Example: disabling an employee through company A's IdP removes company A access while company B access remains intact. A provisioning token from company A cannot use an email match to take control of company B's account.

## Migration and compatibility

Apply application migration **`20260909_0003_scim_memberships.py`** before releasing the updated API. It adds tenant-local SCIM profiles, suspended membership attributes and a unique tenant/account constraint. It follows `20260909_0002`; the migration chain has one head.

No backfill guesses account ownership. Existing active memberships are still discoverable and acquire a local profile when managed. Previously globally disabled accounts or suspicious historical memberships are not automatically modified: the code cannot reliably determine whether those were legitimate administrative changes.

Existing IdPs that rename global login emails through SCIM must use a separately authorized identity-change workflow; requests now fail safely. Existing-account provisioning needs an authorized membership first. These are intentional security boundaries, not silent success responses.

Migration downgrade drops the new SCIM state and does not restore suspended memberships. Use normal release rollback planning; no production migration, downgrade or deployment was performed here.

## Verification

**554 distinct tests passed:** 552 in the broad security/authentication/permissions/OAuth/storage/widget/custom-tool regression run, plus two new HTTP rejection cases in the final targeted run. The final targeted run included 15 passing cases, overlapping the broad run.

The new SCIM suite uses real SQLAlchemy ORM and SQLite persistence with synthetic two-tenant accounts. It covers foreign-account linking rejection, PUT/PATCH/DELETE tenant isolation, retained access in the other tenant, reactivation and permission preservation, local profile names, initially inactive provisioning, foreign tenant resource denial, immutable login email, rejected mixed PATCH batches, and HTTP 400 responses. SQLite test table copies omit foreign-key constraints; PostgreSQL locking, constraint enforcement and IdP interoperability are not claimed as tested.

Migration upgrade/downgrade and single-head checks passed locally. Ruff and `git diff --check` passed. The unchanged four real-Redis quota tests were excluded from the broad run; previous results are not counted as fresh evidence. Existing test-client deprecation and bottleneck-version warnings remain in the validation environment.

The old SCIM review probe assumes the pre-fix unsafe linking behavior and is historical evidence. `api/tests/unit/services/security/test_scim_tenant_lifecycle.py` is the post-fix regression contract. Production credentials, database records and infrastructure were untouched. These results validate this fix; they do not grant a whole-project security certification.
