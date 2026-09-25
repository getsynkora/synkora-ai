## 1.15.4

- Fix: removed the duplicate error banner shown above the chat when a message
  fails to send. Every case it covered was already shown as an in-chat message
  bubble (the same error text, appended via _appendAssistantErrorMessage) --
  the banner and its "Retry" button were pure duplication. The separate
  full-screen connection-error state (shown when the widget can't load at
  all) is unaffected.

## 1.15.3

- Fix: chat send failures shown inside the live chat no longer mention Synkora,
  HTTP status codes, or any other backend/implementation detail — the widget is
  embedded inside a third-party app, and the person seeing a chat error is that
  app's end user, not the developer integrating the widget. `loadConfig()`
  (used by developers during integration/testing, not shown to end users)
  keeps its detailed diagnostic messages unchanged.

## 1.15.2

- Fix: `SynkoraChatWidget` now picks up updated `userHash`/`identityToken`/`user`/`userId`
  props on rebuild. Previously these were only ever read once, in `initState`, and silently
  ignored on every rebuild after — so an app that fetches its identity proof asynchronously
  and rebuilds the widget with the fresh value kept sending whatever (possibly null/stale)
  value was available at the widget's very first build, indefinitely. Fixed by adding
  `didUpdateWidget` change-detection and a new `SynkoraChatController.updateIdentity()`
  method (also usable directly if you construct/own your own controller).

## 1.15.1

- Fix: error messages from the API no longer collapse a 401 (invalid widget key) and a
  403 (valid key, but blocked by a domain/identity/rate-limit check) into the same
  "Synkora rejected this widget key" message. The real `detail` from the server is now
  surfaced when present, so 403s from misconfigured domains or missing identity proof
  no longer look like an invalid-key problem.

## 1.15.0

- Bottom tab navigation — Home and Chat tabs replace the dropdown menu
- Chat tab shows conversation history (sessions list)
- Session cards now display agent name and avatar
- Tapping a session opens the message view; back arrow returns to sessions list
- New chat button moved to AppBar inside the message view
- Removed duplicate close button from AppBar leading

## 1.14.0

- Full UI redesign — card-style chat bubbles, teal gradient home screen, adaptive AppBar foreground color
- `triggerMessage(String)` on `SynkoraChatController` — send messages programmatically from outside the widget
- Centralized `ChatTextStyles` with GlassdoorSans font family
- "Powered by" footer in input bar
- "Chat closed" read-only banner for ended sessions
- FAQ rows on home screen replacing suggestion chips
- Sessions list redesigned as flat cards

## 1.13.6

- New UI/UX improvements
- History tab refactored
- Session close/end support
- Optional email and full name entry

## 1.13.4

- New UI/UX improvements
- History tab refactored
- Session close/end support
- Optional email and full name entry

## 1.13.3

- Agent Lens support and UI improvements
- Voice widget integration
- Performance and stability improvements

## 1.0.0

- Initial release
- Drop-in `SynkoraChatWidget` for embedding Synkora AI agents in Flutter apps
- `SynkoraChatController` for headless / BYO-UI usage
- `SynkoraClient` — pure-Dart API client with SSE streaming support
- Local message cache via Drift (SQLite)
- Markdown rendering in assistant messages
- Suggestion chip prompts from server config
- Identity verification via HMAC user hash
- Conversation history loading
