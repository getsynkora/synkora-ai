# Tool Bulk Assignment — Design Spec

**Date:** 2026-06-11
**Status:** Approved

## Problem

The agent tools page groups tools by provider category (e.g. GitHub has 41 tools). To assign an OAuth account to all tools in a category a user must click "Configure" on each tool individually and select the same account 41 times. There is also no way to enable all tools in a category in a single action.

## Goals

1. Enable all tools in a category with one click.
2. Assign a selected OAuth account to all enabled tools in a category with one click.
3. No backend changes required in this iteration — use existing per-tool API. A bulk API endpoint will be added later to optimise the network calls.

## Non-Goals

- Partial selection (checkboxes per tool) — out of scope.
- Bulk assignment across multiple categories at once — out of scope.
- New backend endpoints — deferred to a follow-up.

## UI Layout

A bulk-action toolbar is rendered inside each expanded category panel, between the header and the tool grid.

```
┌──────────────────────────────────────────────────────────────────┐
│ GitHub   [41 tools]  [Token configured]                [chevron] │
├──────────────────────────────────────────────────────────────────┤
│  [Enable all]  [Disable all]  │  [My GitHub ▼]  [Apply to all]  │
├──────────────────────────────────────────────────────────────────┤
│  tool grid...                                                    │
└──────────────────────────────────────────────────────────────────┘
```

- **Left side:** "Enable all" and "Disable all" buttons — always shown for every category.
- **Right side:** OAuth account dropdown + "Apply to all enabled" button — only shown for categories that have a `groupOAuthProvider` value (i.e. categories that require OAuth/API token).
- The "Apply to all enabled" button is disabled until an account is selected from the dropdown.
- Non-OAuth categories (file system, browser, commands, etc.) render only the left side.
- A per-group loading spinner replaces both sides while a bulk operation is in progress.

## Behaviour

### Enable all

- Iterates every tool in the group that is not already enabled.
- Non-configurable tools: calls `addToolToAgent` with empty config.
- Configurable tools (require `oauth_app_id`): calls `addToolToAgent` with empty config — the tool is enabled but unconfigured. The user can then use "Apply to all enabled" to assign an account.
- All calls run in `Promise.all`.
- On completion: reloads agent tools, shows a success toast with the count of newly enabled tools.
- On partial failure: shows a toast with success/failure counts.

### Disable all

- Finds all enabled `AgentTool` rows for the group by matching `tool_name` against the group's tool list.
- Calls `deleteAgentTool` for each in `Promise.all`.
- On completion: reloads agent tools, shows a success toast.

### Apply to all enabled (OAuth assignment)

- Finds every tool in the group that is currently enabled AND has `oauthProvider` set (i.e. is configurable).
- For each, calls `addToolToAgent` with `oauth_app_id` set to the selected value. This is an upsert — it replaces any previously assigned account.
- All calls run in `Promise.all`.
- On completion: reloads agent tools, shows a success toast.
- "Apply to all enabled" does not affect disabled tools.

## State Changes (frontend only)

Two new state entries added to `page.tsx`:

```ts
// Maps groupId -> selected oauth_app_id string for the bulk dropdown
const [bulkOAuthSelection, setBulkOAuthSelection] = useState<Record<string, string>>({})

// Maps groupId -> boolean for per-group loading state
const [bulkLoading, setBulkLoading] = useState<Record<string, boolean>>({})
```

Three new handler functions:

- `handleEnableAll(group: ToolGroup)` — enables all tools in the group.
- `handleDisableAll(group: ToolGroup)` — disables all tools in the group.
- `handleApplyOAuthToAll(group: ToolGroup, oauthAppId: string)` — assigns OAuth to all enabled configurable tools.

## OAuth Dropdown Population

Reuses the existing `getOAuthAppsForProvider(provider)` helper which returns all `allOAuthApps` entries for the given provider. Each option shows:

```
{app_name}  · Default     (connected)
{app_name}               (not connected)
```

Same label format as the individual configure modal.

## Future: Bulk API

When the bulk API is added the three handlers will be replaced with single API calls:

- `POST /api/v1/agents/{id}/tools/bulk-enable`  — body: `{ group_id, oauth_app_id? }`
- `POST /api/v1/agents/{id}/tools/bulk-disable` — body: `{ group_id }`
- `POST /api/v1/agents/{id}/tools/bulk-assign`  — body: `{ group_id, oauth_app_id }`

The frontend handler signatures will not change.

## Files Changed

| File | Change |
|------|--------|
| `web/app/(dashboard)/agents/[agentName]/tools/page.tsx` | Add bulk toolbar UI, two state entries, three handlers |

No other files are modified.
