# Credential boundary follow-up review — 9 September 2026

Remediation update: both findings below were subsequently addressed. See [credential boundary fixes](2026-09-09-credential-boundary-fixes.md) for validation and rollout requirements. Original findings are retained as baseline evidence.

## Summary

Two high-priority application issues remain, confirmed through local diagnostic calls to the actual application methods. The previous fixes pass their regression tests. Those fixes covered account-JWT handoff authentication and authenticated OAuth initiation/callback ownership; the remaining findings concern agent-key authorization and personal OAuth callbacks changing shared configuration.

This was a targeted follow-up review of credential and authorization boundaries in the current working tree. Infrastructure and production configuration were excluded. It is not an exhaustive application audit or production penetration test.

## 1. High — an agent API key grants handoff access beyond its agent and permissions

**Evidence:** `api/src/middleware/agent_api_auth.py:343` validates the key and then returns only its tenant. Its `agent_id` and `permissions` are discarded. Handoff handlers scope their queries to that tenant, without retaining the key's allowed agent. For example, `api/src/controllers/agents/handoff.py:173` returns conversation details and messages after checking the conversation's agent belongs to the tenant.

**Local reproduction:** a synthetic, encrypted API key scoped to agent A with `permissions=['chat']` passed the real key-validation method. The real handoff detail method then returned a private message from agent B in the same tenant. The database responses were mocked; the key comparison, authorization dependency and route method were real.

**Plain-English example:** giving a partner a key to chat with your public support bot can also give them access to another bot's handoff conversations if they know its conversation ID. The handoff list endpoint also operates at tenant scope. This does not demonstrate access to another company; the confirmed boundary bypass is between agents and allowed operations within one company.

**Fix first:** retain the authenticated key identity through handoff handling. Require explicit handoff permissions and restrict list, read and mutation queries to the key's agent. Test both access to the permitted agent and rejection of another agent, including chat-only keys.

## 2. High — personal Salesforce/Jira connections modify shared platform configuration

**Evidence:** `api/src/controllers/oauth/base.py:136` deliberately requires `oauth_apps.update` only for app-level connections. However, the personal Salesforce callback still writes `instance_url` into `OAuthApp.config` at `api/src/controllers/oauth/salesforce.py:158`; its platform clone is created only for app-level connections. The personal Jira branch writes `cloud_id` onto the same shared app at `api/src/controllers/oauth/jira.py:211`.

**Local reproduction:** for each provider, the actual callback accepted state bound to an active tenant member with `user_level=True`, changed the configuration of a modeled shared platform app, and committed once. The shared-update permission service was configured to deny access but was never called. The existing shared access token remained unchanged. Provider responses and database boundaries were mocked; the callback and authorization helper ran normally.

**Plain-English example:** an employee connects their personal Jira or Salesforce account. That changes the shared integration's destination settings, which other users or tenants may rely on. It can disrupt their integration or make later requests use the wrong workspace settings. The probe demonstrates an unauthorized shared-configuration update, not theft of a provider token or a successful request against another provider account.

**Fix first:** store personal destination settings with the personal connection and resolve them with that connection's token. Require shared-update permission for tenant-wide settings, and keep platform templates immutable during user connection flows. Test both personal and app-level writes, not only access-token storage.

## What was verified

- Fresh run: **78 tests passed** covering alternate account authentication, all 19 OAuth authorization routes and callbacks, authorized connection flows, S3 tenant isolation, reset/login overlap and Recall retry transactions.
- Local diagnostic script: `docs/reviews/probes/review_credential_boundaries.py`.
- Probe output: agent A's chat-only key returned an agent B message; Salesforce and Jira each changed platform configuration with zero shared-permission checks and one commit.
- No application fixes or production changes were made in this review. Only this report and its diagnostic probe were added.
- Previous dependency audits and frontend build results were not rerun. No dependency changes were made in this review.

Reproduce the diagnostic from the repository root using the existing temporary validation environment:

```sh
PYTHONPATH=api /private/tmp/synkora-harness-validation/bin/python docs/reviews/probes/review_credential_boundaries.py
```

The script creates synthetic identities and credentials and uses mocked database/provider boundaries. It does not contact production or third-party services. Its acceptance checks document the vulnerable baseline; permanent regression tests should assert rejection after remediation.
