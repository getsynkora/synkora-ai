---
sidebar_position: 1
---

# Flutter Chat SDK

Synkora ships a Flutter chat SDK for embedding agent conversations into mobile or Flutter-based products.

## Package

Use the `synkora_chat` package.

## What It Includes

- drop-in chat widget
- headless controller for custom UI
- local message cache
- markdown rendering
- widget-key based connection model

## Basic Example

```dart
import 'package:synkora_chat/synkora_chat.dart';

SynkoraChatWidget(
  widgetKey: 'wk_your_key_here',
  baseUrl: 'https://your-synkora-instance.com',
)
```

## Good Fit

Use the Flutter SDK when you want a mobile or embedded app experience backed by the same Synkora widget/agent model.
