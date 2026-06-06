# Synkora Mobile

Dedicated Flutter app for signed-in Synkora users.

## Features in this slice

- Synkora account sign-in
- secure token storage
- tenant selection and tenant switching
- tenant agent directory
- agent detail page
- authenticated streaming chat
- GitHub Actions CI and release workflows

## Local development

```bash
cd flutter/synkora_mobile
flutter pub get
flutter run --dart-define=SYNKORA_API_URL=http://localhost:5001
```

Or use the example defines file:

```bash
flutter run --dart-define-from-file=dart_defines.example.json
```

For Android release builds that produce an `.aab`, make sure the local Android
SDK includes `cmdline-tools`. Flutter uses them after bundling to inspect native
debug symbols.

## Build-time configuration

The app reads its API base URL from a Dart define:

```bash
--dart-define=SYNKORA_API_URL=https://api.your-synkora-instance.com
```

If omitted, it falls back to `http://localhost:5001`.
