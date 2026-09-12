# Security follow-up fixes — 9 September 2026

Application changes are complete in the working tree. No deployment or production database changes were made. Infrastructure and production configuration were excluded as requested.

| Issue | What changed | Plain-English example |
| --- | --- | --- |
| Cross-tenant S3 access — highest priority | Every internal S3 tool checks the trusted runtime tenant and the object namespace before accessing storage. Uploads, listings, links, metadata, downloads and deletion are covered. Foreign buckets and ambiguous paths are rejected. | An agent from company A cannot download or delete company B's files by supplying B's storage key. |
| Password reset overlapping with login | Password changes increment a database-backed authentication version in the same transaction. Tokens carry that version; session validation, refresh and account authentication check it. Reset-token rows are locked during consumption. | A login that used the old password while reset was finishing no longer leaves a valid session after reset completes. The user's reset steps are unchanged. |
| Recall webhook retry loss | Event receipts and handler database writes commit together. Failed processing rolls back and returns HTTP 503, allowing retry. A committed duplicate is acknowledged without processing again. | A temporary database error no longer permanently marks an unfinished event as completed. |
| Vulnerable dependency paths | SendGrid 6.12.5 removes its ecdsa dependency. Databricks 4.5.0 permits patched Thrift 0.24.0. Plotly Cartesian and financial bundles replace the full package and remove MapLibre. | The affected packages are removed or updated without forcing an incompatible Thrift version into the old connector. |

## Evidence and corrections

The password-reset concern was initially a code observation, not a demonstrated exploit. A controlled regression test subsequently reproduced the overlap through the actual authentication, reset and session methods with a modeled database commit barrier. It failed before the fix and passed afterward. This is deterministic regression evidence, not a production attack or a live PostgreSQL concurrency test.

The earlier dependency summary was incomplete: newer SendGrid and Databricks releases do address the dependency paths. This report supersedes those remaining-issue statements.

Validation completed:

- 361 selected backend tests passed, covering security services, authentication middleware, reset/session regression, S3 tools, webhook rollback/retry, and email integrations.
- 122 frontend tests passed; TypeScript checking and production webpack build passed.
- Real Chromium rendering passed for heatmap, box, violin, candlestick and waterfall; the shipped partial bundles expose no map trace types.
- Ruff passed for the changed security/authentication files. Targeted frontend ESLint passed after renaming a loader variable.
- Migration upgrade, existing-account default value, receipt insertion and downgrade passed on an isolated SQLite database. Alembic has one head: `20260909_0001`.
- Installed Databricks SDK connection signature and cursor methods match this application's DBAPI use. A live Databricks warehouse was not contacted; email tests mock delivery.
- Python lockfile audit: no known vulnerabilities reported. Frontend production audit: zero reported vulnerabilities across 673 dependencies, with the existing exclusions for `CVE-2026-4800` and `CVE-2026-14257` unchanged. This is not an exclusion-free audit or proof that every dependency is safe. Machine-readable results are saved beside this report.

## Deployment and compatibility

Apply application migration `api/migrations/versions/20260909_0001_auth_version_and_recall_receipts.py` before deploying the updated API. It adds `accounts.auth_version` and `recall_webhook_receipts`. Existing accounts start at version zero, so legacy sessions remain valid until their account version changes. All API instances must run the updated authentication checks for the new revocation guarantee to hold; old instances do not enforce it.

Previously unscoped shared S3 objects are intentionally not available through tenant tools. Relative keys now resolve under `tenants/<trusted tenant>/`; `data-uploads/<trusted tenant>/` remains supported. Existing data requiring access must have verified tenant ownership and a supported namespace.

The application-declared Plotly chart types remain supported. Arbitrary map, 3D, or unsupported mixed-family Plotly specifications now show a chart error rather than loading the full distribution. Recall receipts persist in the database; this change does not introduce a retention job. Transactional deduplication covers current database effects, not any future external side effects added to handlers.

These checks validate the listed application fixes. Production infrastructure, live third-party integrations, and production PostgreSQL behavior were not penetration-tested.
