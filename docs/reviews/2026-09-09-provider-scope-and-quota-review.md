# Application security re-review

Status: Remediated in application code; see [fixes and validation](2026-09-09-provider-scope-and-quota-fixes.md). The findings below describe the pre-fix state.

Date: 2026-09-09

## Summary

Three remaining application-code issues were reproduced locally: two high-priority credential authorization problems and one medium-priority quota race. Fix the cross-tenant connection issue first. The recent micromobility, handoff restriction and origin fixes retain passing regression coverage, but did not secure every provider path.

## 1. High — an agent can be assigned another tenant's OAuth connection

Locations: `api/src/controllers/agents/tools.py:170–204`, `api/src/services/agents/credential_resolver.py:454–459,530–594`.

The save-tool controller checks ownership of the agent, then accepts the submitted `oauth_app_id` without checking ownership of that connection. The GitLab resolver subsequently loads that app by ID, provider and active status, without a tenant condition, and decrypts its app token. Capability assignment also stores submitted OAuth IDs without a connection-ownership check (`tools.py:730–767`).

**Use case:** a user who can configure an agent in company A supplies the numeric ID of company B's active GitLab connection. The agent can then use company B's connected provider identity, subject to that token's provider permissions.

**Evidence:** the actual save controller accepted synthetic connection ID 912 with only the agent and existing-tool lookups. In a subsequent actual GitLab resolver invocation, modeled app 912 belonged to another tenant and its synthetic token was returned. Compiled app lookup contained no tenant constraint. GitLab tool code calls this resolver directly (`internal_tools/gitlab_tools.py:54`).

**Prerequisites/limits:** requires authenticated tool-configuration access, a known or guessed existing connection ID, an active GitLab OAuth app, and a usable app token. Database responses were modeled; no live foreign tenant or provider operation was used. This demonstrates the application authorization gap, not observed production exploitation.

**Fix:** validate every referenced connection during tool/capability assignment and enforce tenant ownership again at credential resolution. Shared platform apps should be templates, not sources of another tenant's runtime credentials. Audit other provider resolvers for the same lookup pattern and add cross-tenant route-to-resolver regression tests.

## 2. High — other providers still borrow another member's personal token

Locations: `api/src/services/agents/credential_resolver.py:42–104,483`.

The older `_get_user_token_record` helper first tries the current user. If that user has no token, it selects the first personal token associated with any member of the current tenant. This happens even when a current user is present; it is not limited to background jobs. GitLab and several other provider paths still call this helper, unlike the recently corrected micromobility/Jira/Salesforce paths.

**Use case:** Alice has connected her personal GitLab account. Bob uses a configured agent but has not connected his own account. The resolver can use Alice's personal connection, including provider access Bob may not have.

**Evidence:** a synthetic current user with no matching token fell through to another member's record; the actual GitLab resolver returned that other member's token. The fallback SQL constrained the tenant but not the current account.

**Prerequisites/limits:** requires a configured provider tool and another tenant member's personal token for the same app. This reproduction concerns within-tenant identity substitution, not a demonstrated cross-tenant personal-token leak. Provider-side action was not attempted.

**Fix:** use the current-member-only helper consistently. Background/service access should require an explicitly shared tenant connection rather than implicitly borrowing a personal connection. Preserve support for existing encryption formats.

## 3. Medium — concurrent requests can exceed API-key quotas

Location: `api/src/services/agent_api/api_key_service.py:390–423`.

The limiter reads Redis counters, checks quotas, and adds the request in separate operations. Concurrent requests can all observe available capacity before any adds its entry. Running this function in worker threads makes overlapping invocations possible within one application process as well as across replicas.

**Use case:** a valid key sends a simultaneous burst. More requests than its configured limit can reach expensive agent operations, increasing load or cost.

**Evidence:** a deterministic Redis-operation model paused eight callers after each count read. With minute/hour/day limits all set to one, all eight invocations of the real limiter returned allowed. This is a valid interleaving of the existing separate operations, not a live Redis load benchmark.

**Fix:** make expiry, all-window quota checks and recording one atomic Redis operation, typically a Lua script. Use unique request members and test concurrent callers. Retain failure-closed behavior when Redis is unavailable.

## Verification and limits

- Fresh run: **176 tests passed**, covering remaining auth controls, handoff scope, alternate authentication, API-key service, personal OAuth settings, OAuth connection authorization, and migration shape.
- Reproduction: [synthetic provider/quota probe](probes/review_provider_scope_and_quota.py). Run from repository root with `PYTHONPATH=api /private/tmp/synkora-harness-validation/bin/python docs/reviews/probes/review_provider_scope_and_quota.py`.
- Probe output: foreign connection assignment accepted; foreign app token returned; another member's token returned; eight of eight concurrent requests accepted against limit one.
- No application fixes were made in this review. Only the report and probe were added.
- Infrastructure, production configuration, live services, dependency advisories, frontend and performance benchmarks were not re-audited. No external network calls or production credentials were used. The passing tests are not a whole-project security certification.
