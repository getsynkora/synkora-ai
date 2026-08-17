# Slack Data Source Credential Reuse — E2E Test Guide

Verifies the "reuse an existing agent's connected Slack bot instead of a separate Slack
OAuth app" feature (`docs/superpowers/plans/2026-08-17-slack-data-source-credential-reuse.md`),
and the frontend fix for the silent-stuck bug when no OAuth apps/Slack bots exist.

All steps below were run against the live local stack (`docker compose`), not speculative.

## Backend verification (real API calls)

Login and setup used the standard local dev credentials (see `memory/MEMORY.md`):
`admin@localhost.com` / `Admin123!` against `POST /console/api/auth/login`.

1. **List connected Slack bots** — `GET /api/v1/slack-bots`
   Confirmed one existing connected bot for the admin tenant:
   ```json
   {"id": "1a425cd3-0938-431a-8abe-4e0d245c56fa", "bot_name": "Syn",
    "slack_workspace_name": "Raju-Test-Workspace", "connection_status": "connected", ...}
   ```

2. **Create a Slack data source with `slack_bot_id`** — `POST /api/v1/data-sources`
   ```json
   {
     "name": "Test Slack Bot Reuse Source 2",
     "type": "SLACK",
     "knowledge_base_id": 2,
     "config": {"channels": []},
     "slack_bot_id": "1a425cd3-0938-431a-8abe-4e0d245c56fa"
   }
   ```
   Result: `201 Created`, `"status": "ACTIVE"` (confirms `slack_bot_id` is treated as an
   active credential source, same as `oauth_app_id`). Verified directly in Postgres:
   ```
   id | name                           | type  | status | oauth_app_id | slack_bot_id
   3  | Test Slack Bot Reuse Source 2  | SLACK | ACTIVE |              | 1a425cd3-...
   ```
   **Note:** required an `docker compose restart api` first — the running `uvicorn --reload`
   process had not picked up the `data_sources.py`/`data_source.py`/`slack_connector.py` file
   changes via `WatchFiles` (confirmed via `docker compose logs api` showing no "Reloading..."
   event after the edits' mtimes, despite the reloader process being active). After restart,
   the same request correctly returned `"status": "ACTIVE"` (before restart it incorrectly
   returned `"status": "INACTIVE"` with `slack_bot_id` left `NULL` in the DB — stale code).

3. **Create with a non-existent `slack_bot_id`** — `POST /api/v1/data-sources`
   ```json
   {"name": "Bad Bot Source", "type": "SLACK", "knowledge_base_id": 2, "config": {},
    "slack_bot_id": "00000000-0000-0000-0000-000000000000"}
   ```
   Result: `404 Not Found`, `{"detail": "Slack bot not found"}` — matches plan Task 2's
   verification block.

4. Cleaned up test rows (`DELETE FROM data_sources WHERE id IN (2,3)`) after verification.

## Frontend verification

`web/` has no dedicated docker-compose service in this environment (`web:` block is
commented out in `docker-compose.yml`); frontend was verified via:
- `pnpm type-check` (from `web/`) — passes with zero errors after all JSX changes to
  `web/app/(dashboard)/data-sources/connect/page.tsx`.
- Manual code trace of the modified flow (dev server not started interactively in this
  session):
  1. `fetchOAuthApps(provider)` now also calls `apiClient.getSlackBots()` when
     `provider === 'SLACK'`, filters to `connection_status === 'connected'`, and returns
     `apps.length > 0 || hasSlackBots` — so a tenant with zero OAuth apps but one connected
     Slack bot (the exact case verified above) is no longer treated as "no credentials".
  2. `handleTypeSelect`/`handleKbSelect` now call `setError(...)` with a concrete message
     when `hasCredentials` is `false`, instead of leaving the wizard on the same step with
     no feedback (the original silent-stuck bug).
  3. The "OAuth app not configured" panel's render condition was extended with
     `!(selectedType === 'SLACK' && slackBots.length > 0)` so it no longer incorrectly shows
     when a usable Slack bot exists.
  4. The `'configure'` step's render condition was extended from `oauthApps.length > 0` to
     `oauthApps.length > 0 || (selectedType === 'SLACK' && slackBots.length > 0)` — otherwise
     the configure UI (name field, connect button) would never render for a Slack-bot-only
     tenant with zero OAuth apps.
  5. A "Use existing Slack bot" / "Set up new OAuth app" toggle renders above the OAuth-app
     selector when `selectedType === 'SLACK' && slackBots.length > 0`; selecting a bot hides
     the OAuth-app dropdown (redundant in that path).
  6. `handleConnect()` now sends `oauth_app_id: null, slack_bot_id: <id>` when
     `useExistingSlackBot` is active, or the original `oauth_app_id` path otherwise.

## Result

Backend: fully verified end-to-end against the live stack, including the ACTIVE-status
credential-source logic and the 404 not-found path. Frontend: type-checked cleanly; logic
verified by code trace since no interactive dev server session was run in this pass.
