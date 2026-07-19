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
