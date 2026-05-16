# synkora_chat

Flutter SDK for embedding [Synkora](https://synkora.com) AI agent chat into your app. Includes a drop-in `SynkoraChatWidget` and a headless `SynkoraChatController` for custom UIs.

## Features

- Drop-in chat UI with streaming responses
- Headless controller for fully custom interfaces
- Local message cache (SQLite via Drift) — messages persist across sessions
- Markdown rendering in assistant messages
- Suggestion chip prompts configured from the Synkora dashboard
- Identity verification via HMAC user hash
- Conversation history loading

## Installation

```yaml
dependencies:
  synkora_chat: ^1.0.0
```

## Usage

### Drop-in widget

```dart
import 'package:synkora_chat/synkora_chat.dart';

SynkoraChatWidget(
  widgetKey: 'wk_your_key_here',
  baseUrl: 'https://your-synkora-instance.com',
)
```

### With user identity

```dart
SynkoraChatWidget(
  widgetKey: 'wk_your_key_here',
  baseUrl: 'https://your-synkora-instance.com',
  user: WidgetUser(id: 'user_123', name: 'Alice', email: 'alice@example.com'),
  userHash: 'hmac_sha256_of_user_id', // generated server-side
)
```

### Headless (BYO UI)

```dart
final controller = SynkoraChatController(
  client: SynkoraClient(
    widgetKey: 'wk_your_key_here',
    baseUrl: 'https://your-synkora-instance.com',
  ),
);

await controller.init();

// Send a message
controller.send('Hello!');

// Listen for updates
controller.addListener(() {
  final messages = controller.messages;
  final isStreaming = controller.isStreaming;
});

// Clean up
controller.dispose();
```

## Widget Key

Get your `widgetKey` from the **Synkora dashboard → Agents → Widget** tab.

## Requirements

- Flutter `>=3.19.0`
- Dart SDK `>=3.3.0`
