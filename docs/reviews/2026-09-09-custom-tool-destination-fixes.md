# Custom-tool destination fix

Date: 2026-09-09

The [confirmed destination-change issue](2026-09-09-custom-tool-destination-review.md) is fixed in application code.

- Path parameter values are percent-encoded before substitution, including slashes, URL delimiters and percent signs. A value such as `/attacker.example.invalid/collect` remains path data on the configured server.
- The executor compares the final request's normalized HTTPX scheme, host and effective port with the configured server before URL validation, authentication construction or HTTP client creation. Foreign origins and embedded URL credentials fail closed, including absolute or scheme-relative schema paths.
- The existing public-destination validation remains in place. This change does not claim to redesign DNS resolution or other outbound HTTP controls.

**94 tests passed**, including 15 new request-capture/denial cases, existing parser/executor tests, tenant-ownership tests and tool-loading tests. Ruff and `git diff --check` passed. The old mocked parser fixture now supplies its configured server URL so existing executor behavior is exercised with the new check.

The new tests verify normal IDs, slashes, spaces, Unicode, percent-encoded input, backslashes and query/fragment delimiters remain data; and that foreign hosts, scheme/port changes and embedded credentials are rejected before secrets or HTTP are accessed. HTTPX MockTransport captures actual constructed requests with synthetic authentication; external DNS and HTTP are not used in these regression cases.

Compatibility: integrations relying on raw slashes inside path parameter values now receive encoded values. Deliberate cross-origin schema paths are rejected; a different API origin needs its own configured connection.

No migration, infrastructure change or deployment was performed. Existing test-client deprecation and web-tool AsyncMock warnings remain. These tests validate this fix and adjacent behavior, not the security of the entire project.
