# Post-remediation security review

**Remediation update:** both findings below are fixed in the working tree. See [changes, validation, and migration requirements](2026-09-10-template-database-remediation.md). The findings below describe the pre-fix behavior; they are not deployment status.

Reviewed September 10, 2026 against the current working tree, including existing uncommitted changes. **Two additional confirmed findings remain: one critical and one high. Do not treat the earlier five fixes as security sign-off.** This review added only this report and an offline probe; no application code was changed.

## PR-01 — Critical: tenant-controlled templates execute unrestricted Python operations

Locations:
- `api/src/services/newsletter/render_service.py:32` creates a normal Jinja2 Environment for custom HTML.
- `api/src/services/email/email_template_apply_service.py:97` independently does the same for custom email templates.
- `api/src/controllers/email_templates.py:108` accepts tenant-provided `html_content`; line 222 assigns an owned template to an owned agent.
- `api/src/controllers/newsletter_templates.py:40` accepts uploaded Jinja2 HTML.
- `api/src/services/agents/internal_tools/newsletter_tools.py:99` loads custom content from the assigned template or tenant S3 storage and passes it to the renderer at line 204.
- `api/src/services/agents/internal_tools/email_tools.py:98` applies the assigned email template during sending.

**Attack path:** an authenticated tenant user creates a CUSTOM_HTML email template, assigns it to their agent, then triggers newsletter rendering or email sending. Alternatively, they upload a newsletter template and select it when rendering. These paths accept tenant content as executable Jinja2 source. The normal environment exposes object attributes and Python globals, so template expressions can reach Python built-ins. HTML autoescaping does not sandbox template execution.

**Impact:** server-side template injection permits code execution with the rendering process's privileges, including access to application credentials and other tenants' data available to that process. It requires the relevant rendering tool/workflow to execute; merely previewing an inert HTML iframe is not the demonstrated trigger. Tenant ownership checks on the template and agent do not protect the shared Python process.

**Evidence:** the attached probe invokes both actual production rendering functions with a template expression that reaches `cycler.__init__.__globals__.__builtins__.open`. Both return a marker from a synthetic temporary file. This confirms unrestricted Python built-in invocation and local file access. No shell command, real credential access, email delivery, S3 operation, or live API exploit was performed. HTTP creation/assignment reachability was established by source inspection, not a deployed end-to-end test.

**Required fix:** use a restricted template language or an immutable sandboxed Jinja2 environment for every tenant-supplied template path. Remove unnecessary globals/callables and restrict context to inert data. Add rendering time, memory, and output limits; sandboxing alone does not prevent resource exhaustion. For full user-programmable templates, execute in a separate unprivileged worker without application credentials, with constrained filesystem and network access. Cover both email and newsletter renderers with regression tests rejecting Python global/attribute traversal while retaining supported placeholders.

## PR-02 — High: in-process database connectors expose the shared server filesystem

Locations:
- `api/src/controllers/database_connections.py:175` accepts connection definitions; SQLite and DuckDB accept caller-supplied `database_path` without a tenant storage boundary.
- `api/src/controllers/data_analysis.py:256` exposes `/api/v1/data-analysis/query-database` to authenticated tenant users.
- `api/src/services/data_analysis_service.py:527` verifies ownership of the connection record, then executes caller SQL; SQLite and DuckDB dispatch at lines 571 and 623.
- `api/src/services/database/duckdb_connector.py:137` opens the chosen database with default DuckDB capabilities; line 273 executes arbitrary SQL.
- `api/src/services/database/sqlite_connector.py:90` creates parent directories and opens the caller's path directly; line 161 executes SQL.

**Attack path:** a tenant user creates their own in-memory DuckDB connection and submits `SELECT content FROM read_text(...)` for a server path. No external extension is needed for the demonstrated read. `COPY ... TO ...` also writes files accessible to the API process. A SQLite connection can instead point directly at an existing server database belonging to another tenant or subsystem. Connection-record ownership does not authorize the files accessed by that connection.

**Impact:** arbitrary readable server-file disclosure and DuckDB writes within the application's filesystem permissions. SQLite exposes readable database contents outside tenant storage. This can compromise credentials or cross tenant boundaries when those files are accessible. The probe does not claim root privileges, guaranteed access to a particular production secret, SQLite persistence of all write statements, or demonstrated code execution via DuckDB.

**Evidence:** actual DuckDBConnector calls read a synthetic text file and write a synthetic CSV outside any tenant root. Actual SQLiteConnector calls read a precreated synthetic foreign database. All three checks succeeded. The service's optional LIMIT handling does not restrict filesystem functions; the request permits omitting the limit. No real server secrets or foreign customer data were accessed. API reachability was inspected in source; no deployed HTTP request was issued.

**Required fix:** confine local databases and their data inputs to server-selected tenant storage; reject arbitrary client paths, traversal, and symlink escapes. Disable DuckDB external access, extension installation/autoload, and configuration changes by untrusted SQL, with configuration locked before executing queries. If file/network analytics are required, isolate execution in a tenant-scoped process with explicitly mounted inputs and bounded egress rather than giving the engine API-process capabilities. Apply the boundary in the shared connector layer so test-connection routes and agent/tool paths cannot bypass it. Add negative tests for file table functions, COPY, ATTACH, foreign SQLite paths, symlinks, and attempts to re-enable capabilities. Enforce query time/resource/result limits separately.

## Validation and scope

- **598 backend tests passed; 4 deselected; 7 warnings**, in 44.19 seconds. The selected suite covers security services, data analysis, custom tools, console authentication, Okta, controller security boundaries, agent boundaries, and MCP HTTP transport. Four private-Redis quota cases were excluded from this run; their prior successful run is recorded in the earlier review. This is not the full project or production integration suite.
- Five new offline checks all confirmed the behaviors above. Run `PYTHONPATH=.:<optional-local-test-dependencies> python ../docs/reviews/probes/post_remediation_boundaries.py` from `api/` with project dependencies installed. The probe loads synthetic `.env.test` settings, uses temporary files, and cleans them up. A successful exit demonstrates vulnerable behavior; this is a diagnostic probe, not a passing security regression test.
- The earlier five remediations remain covered by the passing targeted suite: Okta administration/configuration binding, monitoring outbound HTTP policy, refresh/widget CORS boundaries, tenant-bound report downloads, and DNS-pinned OpenAPI fetching. See [remediation record](2026-09-10-five-findings-remediation.md).
- Source inspection also sampled database CRUD and dispatch, agent versions/context files/skills, newsletter/email template ownership and rendering, frontend SVG sanitization and template iframe sandboxing, scraper request guards, and deployment settings. No additional confirmed finding is asserted for those samples.
- Dependency audits, frontend tests, and secret scanning were **not rerun in this follow-up**. Their earlier dated results and limitations are in [the preceding review](2026-09-10-project-security-review.md); they are not fresh clearance for every current dependency or deployment. No production/cloud configuration, live attack, full history secret verification, Linux image audit, or exhaustive endpoint coverage was performed.

Prioritize PR-01 first, then PR-02. Both demonstrate that tenant-configurable execution still reaches shared application-process privileges despite the recently repaired HTTP and authorization boundaries.
