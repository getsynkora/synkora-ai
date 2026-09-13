# Remaining authentication controls: remediation

Date: 2026-09-09

All three findings in [the preceding review](2026-09-09-remaining-auth-controls-review.md) have application-code fixes and regression coverage. No infrastructure, production configuration, or deployed services were changed.

## Changes and practical impact

1. **Micromobility personal credentials:** the resolver selects only the current account's token with a live membership in the current tenant. OAuth app lookup requires tenant ownership or a platform template. Platform templates cannot supply shared runtime secrets. The existing decoding helper supports both current and legacy double-encrypted personal tokens. Independent database sessions remain in place for concurrent tool calls.
   - Example: a background job from company A cannot borrow company B's personal provider login through a shared platform app.
   - Compatibility: a job without a mapped user needs an explicitly configured tenant-owned app connection. No personal-token owner is guessed. Valid tenant-owned app OAuth fallback remains supported.
2. **Handoff API-key restrictions:** handoff and standard API-key authentication share IP, origin and rate-limit enforcement. Disallowed requests receive 403, exhausted quotas receive 429, and a rate-limit service failure receives 503. The synchronous rate-limit operation runs in a worker thread. Existing handoff agent scope and explicit permissions remain enforced.
   - Example: a partner key restricted to its server address cannot use handoff routes from another address.
   - Compatibility: keys with an origin allowlist now reject missing Origin headers consistently. Keys without that restriction continue to support server requests without Origin. IP enforcement uses the request client address supplied by the application server; production proxy configuration was not evaluated.
3. **Origin matching:** wildcard matching requires an actual subdomain boundary. The parser rejects malformed origins and supports exact URL scheme/port matching. Bare hostname entries retain scheme-independent matching; an explicit configured port must match.
   - Example: `*.example.com` allows `team.example.com`, rejects `notexample.com`, and does not include the apex `example.com`. Add an exact apex entry if that is intended.

## Verification

**176 tests passed** across the new remaining-controls suite, handoff scope, alternate authentication paths, API-key service, personal OAuth settings, OAuth authorization boundaries, and personal OAuth migration tests. Ruff checks and `git diff --check` passed.

New coverage includes real in-process HTTP denial/acceptance, synthetic quota and outage responses, both token encryption formats, user-less contexts, platform-secret rejection, tenant-app fallback, and an actual SQLite execution of the personal-token account/tenant query. Permission-focused handoff tests isolate request controls; the new HTTP tests exercise the real IP and origin validators separately.

Tests use synthetic credentials. Redis responses and provider persistence are mocked except for the isolated SQLite query test. No live PostgreSQL, Redis quota concurrency, external provider, Kubernetes, or production verification was performed. One test-client deprecation warning remains in the validation environment. These results validate the stated fixes, not a guarantee that the whole project has no security issues.

No new migration is introduced by these three fixes. Previously added migrations remain separate deployment requirements. The historical probe in the preceding review documents the original bypasses; its output assumptions should not be used as the post-fix regression contract.
