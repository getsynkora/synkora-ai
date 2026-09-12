# Template and local database remediation

Both findings from the [post-remediation review](2026-09-10-post-remediation-security-review.md) are fixed locally. No deployment or production data migration was performed.

## PR-01: custom templates

Email and newsletter custom HTML now use one immutable sandbox with no globals, object attribute access, or callable access. A restricted syntax validator rejects calls, arithmetic, macros, imports, assignment, and recursive loops. Context accepts only bounded plain data. Templates support placeholders, conditions, at most two loops over bounded lists/dictionaries, comparisons, and the `escape`, `e`, `safe`, `default`, `length`, `upper`, `lower`, and `trim` filters. Supported tests are `defined`, `undefined`, and `none`.

Source and context are limited to 512 KiB, collections to 100 items, context depth to eight, syntax nodes to 1,000, and rendered output to 1 MiB. String iteration is rejected, including empty nested loops that would otherwise consume time without producing output. These are structural work limits, not a separate OS process or hard wall-clock termination guarantee. Built-in repository templates retain their trusted renderer. Custom email wrappers preserve HTML body insertion; newsletter values retain autoescaping.

Existing custom templates using unsupported Jinja features must be simplified. For example, use `{{ title|upper }}` instead of `{{ title.upper() }}`. Rejected email wrappers retain the existing behavior of falling back to the original email body without applying the wrapper. Newsletter rendering rejects an invalid custom template.

## PR-02: local database execution

The shared path resolver requires a valid tenant UUID and a filename under `LOCAL_DATABASE_ROOT/<tenant UUID>/`. Absolute paths, path separators, URI paths, missing files, symlink components (including root ancestors), and hardlinked files are rejected. No directory or database is created by the connector. SQLite callers in the controller, analysis service, and agent tools all pass the connection's tenant identity. DuckDB derives it from the same connection record. Thus connection tests and alternate callers use the same boundary.

SQLite opens provisioned databases in read-only URI mode, disables trusted schemas, and installs an engine authorizer rejecting writes, attachments, extension loading, and unsafe PRAGMAs. Queries retain SELECT and schema introspection. SQLite also limits SQL/value size, results, and execution through a progress handler with a connection-lifetime deadline capped at 30 seconds.

DuckDB opens provisioned files read-only or uses `:memory:`. External file/network access, extension autoload/install, unsigned/community extensions, and disk spilling are disabled. Configuration is locked before caller SQL executes. Execution uses one thread, a 128 MiB engine memory limit, an interrupting query deadline capped at 30 seconds, a 64 KiB SQL limit, and a result limit of 10,000 rows / approximately 2 MiB. These are per-connection limits, not a global concurrency budget. In-memory table creation and ordinary analytics still work.

### Configuration migration

1. Set `LOCAL_DATABASE_ROOT` consistently for API and workers; the default is `storage/databases` relative to their working directory.
2. Operators must provision a normal database file under `<root>/<tenant UUID>/<filename>`. Mount this tree read-only for application processes and keep it unavailable to tenant upload/write tools. Filesystem provisioning is a trusted operator boundary; do not modify files or replace path components while queries are opening them.
3. Replace each legacy absolute `database_path` with its filename, such as `sales.sqlite` or `sales.duckdb`. Existing absolute paths now fail closed. DuckDB `:memory:` remains supported.
4. Remove DuckDB extension settings. Direct CSV/Parquet/HTTP/S3/federated reads through this connector are intentionally unavailable. Import approved data during operator provisioning or use the project's separately authorized remote connector rather than restoring shared-process external access.

Create/edit forms now describe filenames and the restricted behavior. `.env.example` documents the root setting. No production files were moved automatically because the local workspace does not establish their ownership or deployment locations.

## Validation

- Broad backend run: **693 passed, four deselected**, including the previous security suites, both database connector suites, database controller tests, and agent database-tool tests.
- Final focused run after adding the empty-loop regression: **68 passed**, including **22 new security regression cases**. Across both runs, **694 distinct tests passed**; the overlapping focused tests are not added twice.
- Actual DuckDB/SQLite engines verify positive tenant reads and negative filesystem access, COPY, ATTACH, unsafe PRAGMAs, extensions, configuration changes, timeouts, and oversized results. Actual email/newsletter renderers reject the demonstrated Python built-in exploit and preserve supported rendering.
- Ruff checks and `git diff --check` passed. Frontend edits are explanatory text only; no frontend suite was rerun.
- Four private-Redis quota cases were excluded from the broad run as in the previous review. This is not a full production integration run, Linux image test, or live deployment validation.

The original offline exploit probe is retained as historical evidence. It intentionally expects the old vulnerable behavior and should no longer succeed on the fixed tree; use `api/tests/unit/services/security/test_template_database_boundaries.py` for current regression checks.
