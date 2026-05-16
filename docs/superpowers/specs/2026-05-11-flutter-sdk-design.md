# Flutter SDK Design Spec
# `synkora_chat` + `synkora_push`

**Date:** 2026-05-11
**Status:** Approved

---

## Goal

Provide a first-class native Flutter SDK that lets any Flutter developer embed a Synkora AI chat widget in their app in under 10 lines of code, with optional FCM push notifications delivered via a separate opt-in package.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Flutter App (customer)                   │
│                                                             │
│  ┌─────────────────────┐    ┌──────────────────────────┐   │
│  │  SynkoraChatWidget  │    │    SynkoraPush.init()    │   │
│  │  (drop-in UI)       │    │    (optional, FCM)       │   │
│  └────────┬────────────┘    └───────────┬──────────────┘   │
│           │ uses                        │ uses              │
│  ┌────────▼────────────┐    ┌───────────▼──────────────┐   │
│  │ SynkoraChatCtrl     │    │  SynkoraPushService      │   │
│  │ (ChangeNotifier)    │    │  (firebase_messaging)    │   │
│  └────────┬────────────┘    └───────────┬──────────────┘   │
│           │ uses                        │ calls             │
│  ┌────────▼────────────┐                │                   │
│  │  SynkoraClient      │◄───────────────┘                   │
│  │  (dio + drift)      │                                    │
│  └────────┬────────────┘                                    │
└───────────┼─────────────────────────────────────────────────┘
            │ HTTPS
┌───────────▼─────────────────────────────────────────────────┐
│                    Synkora Backend                          │
│                                                             │
│  GET  /api/v1/widgets/config         (X-Widget-API-Key)     │
│  POST /api/v1/widgets/chat           (SSE stream)           │
│  GET  /api/v1/widgets/chat/history                          │
│  POST /api/v1/widgets/push/register  ← NEW                  │
│                                                             │
│  widget.mobile_allowed  ← NEW flag (skips Origin check)     │
│  widget.fcm_server_key  ← NEW encrypted column              │
└─────────────────────────────────────────────────────────────┘
```

---

## Two Packages

| Package | pub.dev name | Purpose | Firebase dep |
|---------|-------------|---------|-------------|
| Core | `synkora_chat` | Chat UI + API client + local cache | No |
| Push | `synkora_push` | FCM push notifications | Yes |

Separating push into its own package keeps `synkora_chat` lean — apps that don't need push never pull in Firebase.

---

## Tech Stack

| Concern | Library | Version | Reason |
|---------|---------|---------|--------|
| HTTP + SSE | `dio` | ^5.7.0 | Interceptors, cancel tokens, `ResponseType.stream` for SSE |
| Local cache | `drift` | ^2.20.0 | Type-safe SQL, migrations, all platforms, actively maintained |
| SQLite native | `sqlite3_flutter_libs` | ^0.5.0 | Required by drift on mobile |
| File paths | `path_provider` + `path` | ^2.1.0 / ^1.9.0 | DB file location |
| Code gen | `build_runner` + `drift_dev` | ^2.4.0 / ^2.20.0 | drift table generation |
| FCM | `firebase_messaging` | ^15.1.0 | Official FlutterFire, all platforms |
| Firebase core | `firebase_core` | ^3.6.0 | Required by firebase_messaging |

**Minimum SDK:**
```yaml
environment:
  sdk: '>=3.3.0 <4.0.0'
  flutter: '>=3.19.0'
```

---

## Backend Changes (Synkora)

### 5 targeted changes — no existing endpoints broken

### 1. `mobile_allowed` flag on `agent_widgets`

- New `Boolean` column, default `False`
- Domain validation in `widget_chat` endpoint: if `mobile_allowed = True` AND `Origin` header is absent → allow request through
- Existing web behaviour unchanged (Origin present → validated as before)
- UI: toggle in widget settings page — "Allow Mobile Apps"
- Migration: `20260511_0001_add_widget_mobile_allowed.py`

### 2. `fcm_server_key` column on `agent_widgets`

- New encrypted `Text` column, nullable, default `None`
- Stored with Fernet encryption (same pattern as `identity_secret` and other secrets)
- UI: text input in widget settings page — "FCM Server Key"
- Migration: same migration as above

### 3. `widget_push_subscriptions` table

```
id               UUID PK
widget_id        UUID (no FK — survives widget recreation)
tenant_id        UUID (multi-tenant isolation)
conversation_id  UUID nullable
fcm_token        Text
platform         Text  ('android' | 'ios' | 'web')
created_at       DateTime
updated_at       DateTime

INDEX: (widget_id, fcm_token)           -- upsert dedup
INDEX: (widget_id, conversation_id)     -- lookup on agent reply
```

Migration: `20260511_0001_add_widget_mobile_allowed.py` (same file, both tables/columns in one migration)

### 4. `POST /api/v1/widgets/push/register`

```
Auth:    X-Widget-API-Key header
Body:    { fcm_token: str, platform: 'android'|'ios'|'web', conversation_id?: str }
Returns: { registered: true }
```

- Upserts on `(widget_id, fcm_token)` — safe to call on every app launch
- Updates `conversation_id` if provided (links token to active conversation)
- No `mobile_allowed` check needed here — registration is always allowed

### 5. FCM send hook in `chat_stream_service.py`

After stream completes (existing `_finish()` equivalent):
- Fire-and-forget Celery task `send_fcm_push_task`
- Task looks up `widget_push_subscriptions` by `(widget_id, conversation_id)`
- Sends push via `firebase-admin` Python SDK using agent's decrypted `fcm_server_key`
- Silent fail if `fcm_server_key` is `None` (FCM not configured)
- Silent fail if no subscriptions found for conversation

Push payload:
```json
{
  "notification": {
    "title": "<agent_name>",
    "body": "<first 100 chars of reply, markdown stripped>"
  },
  "data": {
    "widget_key": "wk_xxx",
    "conversation_id": "conv_yyy",
    "type": "agent_reply"
  }
}
```

New Python dependency: `firebase-admin>=6.5.0` added to `pyproject.toml` (optional import — only loaded if `fcm_server_key` is set).

---

## `synkora_chat` Package

### File structure

```
synkora_chat/
  lib/
    synkora_chat.dart               -- public barrel export
    src/
      client/
        synkora_client.dart         -- dio HTTP + SSE parser + config fetch
        models.dart                 -- WidgetConfig, ChatMessage, SseEvent
      cache/
        cache_database.dart         -- drift schema definition
        cache_database.g.dart       -- generated (build_runner)
        local_cache.dart            -- load/save/merge messages
      controller/
        synkora_chat_controller.dart -- ChangeNotifier, public state API
      ui/
        synkora_chat_widget.dart    -- drop-in StatefulWidget
        message_bubble.dart         -- Material chat bubbles
        typing_indicator.dart       -- animated 3-dot indicator
        suggestion_chips.dart       -- 2-column grid of prompt cards
        chat_app_bar.dart           -- avatar + agent name + optional close
        shimmer_loading.dart        -- skeleton while config loads
  example/
    lib/
      main.dart                     -- runnable demo app
  pubspec.yaml
  README.md
  CHANGELOG.md
```

### Public API surface

#### `SynkoraClient` (pure Dart, no Flutter dependency)

```dart
class SynkoraClient {
  SynkoraClient({
    required String widgetKey,
    required String baseUrl,     // no trailing slash
  });

  /// Fetches agent name, avatar, theme, suggestion prompts from server.
  Future<WidgetConfig> loadConfig();

  /// Sends a message. Returns typed SSE event stream.
  /// Caller must cancel the subscription to avoid memory leaks.
  Stream<SseEvent> sendMessage(
    String message, {
    String? conversationId,
    String? sessionId,
    WidgetUser? user,
    String? userHash,
  });

  /// Loads message history from server (max 50 messages).
  Future<List<ChatMessage>> loadHistory({
    String? userId,
    String? sessionId,
    int limit = 50,
  });

  /// Cancel all in-flight requests and close DB connection.
  void dispose();
}
```

#### `SseEvent` sealed class

```dart
sealed class SseEvent {}
class TextChunk  extends SseEvent { final String text; }
class ToolStatus extends SseEvent {
  final String toolName, status, description;
  final int? durationMs;
}
class DoneEvent  extends SseEvent { final String conversationId; }
class ErrorEvent extends SseEvent { final String message; }
```

#### `WidgetConfig`

```dart
class WidgetConfig {
  final String widgetId;
  final String agentName;
  final String agentDescription;
  final String? agentAvatarUrl;
  final Color primaryColor;         // parsed from hex, fallback to Color(0xFF6366F1)
  final String welcomeMessage;
  final String placeholder;
  final List<SuggestionPrompt> suggestionPrompts;
}

class SuggestionPrompt {
  final String title;
  final String description;
  final String icon;
  final String prompt;
}
```

#### `SynkoraChatController` (ChangeNotifier)

```dart
class SynkoraChatController extends ChangeNotifier {
  // State — read only
  List<ChatMessage> get messages;
  bool get isStreaming;
  bool get isLoading;           // true during initial config + history fetch
  String? get conversationId;
  WidgetConfig? get config;
  String? get error;

  // Actions
  Future<void> init({String? userId, String? sessionId});
  Future<void> send(String text);
  void retry();                 // retries last failed send
  @override void dispose();
}
```

`init()` runs in parallel:
1. `client.loadConfig()` → populates `config`
2. `localCache.loadMessages()` → instant display of cached messages
3. After both: `client.loadHistory()` → merges server messages (server wins by message id)

#### `SynkoraChatWidget` (drop-in)

```dart
SynkoraChatWidget({
  // Required
  required String widgetKey,
  required String baseUrl,

  // Identity (for history continuity)
  String? userId,
  String? sessionId,
  WidgetUser? user,
  String? userHash,

  // BYO controller — advanced use only
  SynkoraChatController? controller,

  // Appearance overrides (win over server theme_config)
  Color? primaryColor,
  ThemeData? theme,

  // Behaviour
  Widget? emptyStateWidget,    // replaces suggestion chips
  VoidCallback? onClose,       // shows close/back button in AppBar when set
})
```

### Branding / theme loading

Priority order (highest wins):

1. `primaryColor` passed directly to `SynkoraChatWidget` constructor
2. `theme_config.primary_color` returned by `GET /api/v1/widgets/config`
3. `Theme.of(context).colorScheme.primary` from the host app

Applied fields from server config:
- AppBar title → `config.agentName`
- AppBar background → `config.primaryColor`
- Agent avatar → `config.agentAvatarUrl` (Flutter `NetworkImage`, cached in memory)
- Input hint text → `config.placeholder`
- Welcome message → `config.welcomeMessage` (rendered as first virtual message, not stored in DB)
- Suggestion chips → `config.suggestionPrompts` (shown only when `messages` is empty)

While `isLoading = true`, a shimmer skeleton is shown (AppBar placeholder + 3 shimmer message rows). Config is cached in-memory per controller instance — reopening the widget (without disposing controller) skips the network fetch.

### UI layout

```
┌────────────────────────────────┐
│  [avatar] Agent Name    [×]    │  ← AppBar, primaryColor background
├────────────────────────────────┤
│                                │
│   [User bubble        right]   │  ← ListView.builder, reverse: true
│        [Agent bubble   left]   │     (auto-scroll to bottom on new msg)
│   [●●● typing indicator]       │
│                                │
├────────────────────────────────┤
│  [ Chip 1 ] [ Chip 2 ]         │  ← 2-column grid, visible when empty
│  [ Chip 3 ] [ Chip 4 ]         │
├────────────────────────────────┤
│ [___ placeholder text ___] [→] │  ← TextField + IconButton
└────────────────────────────────┘
```

Bubbles adapt to `Theme.of(context)` dark/light automatically.

### Local cache (drift)

Single `messages` table:

```dart
class Messages extends Table {
  TextColumn get id          => text()();
  TextColumn get widgetKey   => text()();
  TextColumn get convId      => text().nullable()();
  TextColumn get role        => text()();          // 'user' | 'assistant'
  TextColumn get content     => text()();
  DateTimeColumn get ts      => dateTime()();
  BoolColumn get isStreaming  => boolean().withDefault(const Constant(false))();
}
```

Merge strategy on `init()`:
- Load local messages instantly (zero latency first render)
- Fetch server history
- Upsert server messages by `id` (server content wins)
- Delete local messages with `isStreaming = true` (app was killed mid-stream — incomplete assistant messages)

DB file stored at `path_provider.getApplicationDocumentsDirectory() / synkora_cache.db`.

### SSE parsing

Uses `dio` with `Options(responseType: ResponseType.stream)`. Raw bytes → UTF-8 string buffer → split on `\n\n` → parse each block:

```
data: {"type":"text_chunk","content":"Hello"}
data: {"type":"tool_status","tool_name":"search","status":"started"}
data: {"type":"done","conversation_id":"conv_xxx"}
data: {"type":"error","message":"Rate limit exceeded"}
```

Each line maps to a `SseEvent` subclass. `TextChunk` events update the last `assistant` message in place (streaming effect). On `DoneEvent`, message is finalized and persisted to drift.

---

## `synkora_push` Package

### File structure

```
synkora_push/
  lib/
    synkora_push.dart               -- public API
    src/
      synkora_push_service.dart     -- init, register, handlers
  pubspec.yaml
  README.md
```

### Dependencies

```yaml
dependencies:
  synkora_chat: ^1.0.0
  firebase_core: ^3.6.0
  firebase_messaging: ^15.1.0
```

### Public API

```dart
class SynkoraPush {
  /// Call once in main() after Firebase.initializeApp().
  static Future<void> init({
    required String widgetKey,
    required String baseUrl,
    /// Returns current conversationId — called at registration time.
    String? Function()? conversationIdProvider,
  });

  /// Optional foreground message handler.
  static void Function(RemoteMessage)? onMessage;
}
```

### `init()` internal flow

1. `FirebaseMessaging.instance.requestPermission()` — iOS prompt + Android 13+
2. `FirebaseMessaging.instance.getToken()` → FCM device token
3. `POST /api/v1/widgets/push/register` with `{ fcm_token, platform, conversation_id? }`
4. `FirebaseMessaging.instance.onTokenRefresh.listen(...)` → re-register on token rotation
5. `FirebaseMessaging.onMessage.listen(...)` → call `SynkoraPush.onMessage` if set

Background and terminated state handled automatically by FCM — no additional code needed.

### Developer integration (3 steps)

```dart
// Step 1 — main.dart
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  await SynkoraPush.init(
    widgetKey: 'wk_xxx',
    baseUrl: 'https://your-synkora.com',
    conversationIdProvider: () => chatController.conversationId,
  );
  runApp(MyApp());
}

// Step 2 — optional foreground handler
SynkoraPush.onMessage = (message) {
  // show your own in-app banner, navigate to chat, etc.
  // message.data['conversation_id'] available for deep-linking
};

// Step 3 — nothing else needed
```

---

## Developer Experience

### Minimal integration (10 lines)

```dart
import 'package:synkora_chat/synkora_chat.dart';

// Place anywhere in your widget tree
SynkoraChatWidget(
  widgetKey: 'wk_live_xxxxxxxx',
  baseUrl: 'https://your-synkora.com',
)
```

### BYO controller (headless / custom UI)

```dart
final controller = SynkoraChatController(
  client: SynkoraClient(widgetKey: 'wk_xxx', baseUrl: '...'),
);
await controller.init(userId: currentUser.id);

// Use controller.messages, controller.send(), etc.
// Build any UI on top.
```

### Self-hosted

`baseUrl` is always required. No Synkora cloud URLs are hardcoded anywhere in either package.

---

## Verification Checklist

### Backend
- [ ] `alembic upgrade head` — `widget_push_subscriptions` + `mobile_allowed` + `fcm_server_key` columns created
- [ ] Widget settings page shows "Allow Mobile Apps" toggle and "FCM Server Key" input
- [ ] `POST /api/v1/widgets/push/register` returns `{ registered: true }` with valid key
- [ ] With `mobile_allowed = true` and no Origin header, `POST /api/v1/widgets/chat` returns 200
- [ ] With `mobile_allowed = false` and no Origin header, returns 403
- [ ] After agent reply, FCM push arrives on test device (when FCM key configured)
- [ ] No FCM key configured → no error thrown, silent skip

### Flutter SDK
- [ ] `flutter pub add synkora_chat` installs with no conflicts on Flutter 3.19+
- [ ] `SynkoraChatWidget(widgetKey:, baseUrl:)` renders in a fresh app with no other config
- [ ] AppBar shows agent name + avatar loaded from server
- [ ] Primary color from server `theme_config` is applied
- [ ] `primaryColor:` constructor override wins over server value
- [ ] Suggestion chips visible when no messages; hidden after first send
- [ ] SSE stream renders tokens progressively (streaming effect)
- [ ] Typing indicator shows during stream, disappears on `DoneEvent`
- [ ] Chat history loads on second open (drift cache → server merge)
- [ ] App killed mid-stream → incomplete message cleaned up on next `init()`
- [ ] `dispose()` on controller cancels in-flight dio request, no memory leaks
- [ ] Dark mode: bubbles adapt to host app's `ThemeData`

### synkora_push
- [ ] `SynkoraPush.init()` requests permission and registers token
- [ ] Push notification arrives on device when agent reply completes
- [ ] `onMessage` handler fires for foreground messages
- [ ] Token refresh re-registers automatically
- [ ] Works on Android (FCM) and iOS (APNs via FCM)

---

## Out of Scope (v1)

- File/image attachment sending (v2)
- Audio message support (v2)
- Web platform support for `synkora_push` (requires VAPID — separate effort)
- Typing indicators from the user side (server not implemented)
- Multi-agent routing from Flutter (widget routing already server-side)
- pub.dev automated publishing CI (manual `dart pub publish` for v1)
