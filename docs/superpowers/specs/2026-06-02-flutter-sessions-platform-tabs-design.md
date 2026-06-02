# Flutter Sessions + Web Platform Tabs — Design Spec

**Date:** 2026-06-02
**Status:** Approved

## Overview

Two connected features:
1. **Flutter widget** gains a sessions list screen — users can browse past sessions, resume an active one, or start a new one.
2. **Web dashboard** chat page gains a platform tabs row — conversations from Web, Flutter, Widget, WhatsApp, Slack, and Chrome are shown in separate tabs.

Both features are driven by a new `source` column on the `conversations` table and two new widget-authenticated session endpoints.

---

## Section 1 — Data Model

### `conversations` table additions

| Column | Type | Default | Notes |
|---|---|---|---|
| `source` | `VARCHAR(20)` | `'web'` | Stamped at creation; immutable |
| `closed_at` | `TIMESTAMPTZ` | `NULL` | Set when session is manually or automatically closed |
| `last_activity_at` | `TIMESTAMPTZ` | `NOW()` | Updated on every message sent or received |

**Valid source values:** `web`, `flutter`, `widget`, `whatsapp`, `slack`, `chrome`

### Existing data
Rows with `source IS NULL` are treated as `web` in all query filters. No backfill migration needed.

### Existing `status` column
`ACTIVE` / `ARCHIVED` / `DELETED` already exists. `closed_at` is set when status transitions to `ARCHIVED`. A closed session is read-only — no new messages accepted.

---

## Section 2 — API Layer

### Source stamping
`source` is written at conversation creation from the request context:

| Entry point | Source stamped |
|---|---|
| Web dashboard chat | `web` |
| Flutter widget (`/api/v1/widgets/chat`) | `flutter` |
| Embedded widget JS | `widget` |
| WhatsApp webhook handler | `whatsapp` |
| Slack message handler | `slack` |
| Chrome extension | `chrome` |

`last_activity_at` is updated on every message in all handlers.

### New widget-authenticated endpoints

```
GET  /api/v1/widgets/sessions
     Query: page, page_size (default 20), status (active|closed|all, default all)
     Response: { sessions: [{ id, first_message, last_activity_at, status, created_at }], total }

POST /api/v1/widgets/sessions/{session_id}/close
     Body: {}
     Response: { success: true }
     Effect: sets closed_at = now(), status = ARCHIVED
```

Both endpoints use existing widget JWT auth (`X-Widget-Token` header).

### Updated conversations list endpoint

```
GET /api/v1/agents/{agent_id}/conversations
    Added query param: source (optional; one of web|flutter|widget|whatsapp|slack|chrome)
    Web tab filter: WHERE source = 'web' OR source IS NULL
    Other tabs: WHERE source = '<value>'
    No source param: returns all (existing behaviour)
```

---

## Section 3 — Flutter Widget Design

### Screen flow

```
App launch
  └─ fetch sessions
       ├─ most-recent session is active → open chat directly (skip list)
       └─ otherwise → show sessions list screen
            └─ tap session → open chat (read-only if closed)
            └─ "New chat" button → create session → open chat
```

`_ChatSurfaceView` enum gains a third value: `sessions` (alongside existing `home` and `chat`).

### Sessions list screen
- Scrollable list fetched from `GET /api/v1/widgets/sessions`
- Each row: relative timestamp, first message preview (truncated ~60 chars), status chip (green dot = active, grey = closed)
- "New chat" FAB creates a fresh session
- Back button from chat screen → `sessions` (not `home`)

### Controller changes (`SynkoraChatController`)

New fields:
- `List<WidgetSession> sessions` — populated by `loadSessions()`
- `WidgetSession? activeSession` — currently open session
- `Timer? _inactivityTimer` — reset on every message; fires after 60 minutes

New methods:
- `loadSessions()` — calls `SynkoraClient.listSessions()`
- `closeSession(String id)` — calls `SynkoraClient.closeSession(id)`, updates local state, stops inactivity timer
- `_resetInactivityTimer()` — called on every send/receive; restarts 60-min timer

Inactivity behaviour: timer fires → `closeSession(activeSession.id)` → session marked closed, chat input disabled.

### Client additions (`SynkoraClient`)

```dart
Future<List<WidgetSession>> listSessions();
Future<void> closeSession(String sessionId);
```

Both call the new widget-authenticated endpoints above.

### New model (`WidgetSession`)

```dart
class WidgetSession {
  final String id;
  final String? firstMessage;
  final DateTime lastActivityAt;
  final String status; // "active" | "closed"
}
```

### Cache
Sessions list stored in `CacheDatabase` in a `sessions` table keyed by `external_user_id`. Stale cache renders immediately on launch while fresh data loads in the background (same pattern as existing message cache).

### Closed session UX
- Chat input disabled
- "This session has ended" banner shown above input area
- All past messages visible and scrollable

---

## Section 4 — Web Dashboard Design

### Platform tabs row
Location: above the conversation list in the chat history sidebar on `/agents/[agentName]/chat`.

Tabs (in order): `Web · Flutter · Widget · WhatsApp · Slack · Chrome`

- Active tab: underlined/highlighted
- Default on page load: `Web`
- Tab selection is reflected in the URL as `?source=flutter` etc. (preserves selection on refresh/deep link)
- Selecting a tab fires `GET /api/v1/agents/{agent_id}/conversations?source=<tab>` and replaces the conversation list

### Per-tab behaviour
- All tabs show the same conversation row format (timestamp, preview, status)
- Closed/archived sessions shown with muted styling
- `Web` tab: shows conversations where `source = 'web' OR source IS NULL`
- Other tabs: exact match on `source`
- "New conversation" button: visible on `Web` tab only; hidden on all other tabs (sessions on those channels are initiated from the client)

### State management
Single `selectedSource` local state variable, type `'web' | 'flutter' | 'widget' | 'whatsapp' | 'slack' | 'chrome'`, initialized from URL param or defaults to `'web'`. No new Zustand store needed.

---

## Error Handling

- Widget `listSessions` failure: show empty list with retry button; do not block app launch
- `closeSession` failure: show toast error, leave session as active
- Web tab API failure: show inline error state in conversation list (existing pattern)
- Inactivity timer fires while app is backgrounded: session closes on next foreground resume (timer callback runs on next tick)

---

## Out of Scope

- Push notifications when a session is closed server-side
- Cross-device session sync for Flutter (single device per external_user_id)
- Bulk session management from the web dashboard
- Exporting session history
