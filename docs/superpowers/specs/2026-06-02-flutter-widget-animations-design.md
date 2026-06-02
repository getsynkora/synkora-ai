# Flutter Widget Animations Design

**Date:** 2026-06-02
**Scope:** `flutter/synkora_chat` package — add Lottie + SVG illustration layer to all major screens

---

## Goal

Make the synkora_chat Flutter widget visually distinctive and polished by adding:
- A Lottie animation hero on the home screen
- An artistic mesh gradient background on the home screen
- A custom animated loading state (replacing plain shimmer)
- A colorful flat-design SVG robot illustration for the empty chat state
- A session-ended SVG illustration with robot waving

Style: colorful flat design (robot character in `primaryColor`, chat bubbles, modern)

---

## Packages

| Package | Version | Purpose |
|---|---|---|
| `lottie` | `^3.1.0` | Play bundled Lottie JSON on home screen |
| `flutter_svg` | `^2.0.0` | Render SVG illustrations |

Added to `flutter/synkora_chat/pubspec.yaml` dependencies.

---

## Assets

### Lottie
- Source: `/Users/raju/Downloads/choose-your-colors.json`
- Destination: `flutter/synkora_chat/lib/src/assets/animations/choose_your_colors.json`
- Used on: Home screen hero card

### SVG Illustrations (generated, embedded as Dart string constants)
All SVGs use `currentColor` / parameterised color so `primaryColor` can be injected at render time via `flutter_svg` `colorFilter`.

| File | Used on |
|---|---|
| `lib/src/assets/illustrations/robot_chat.dart` | Empty chat state |
| `lib/src/assets/illustrations/robot_wave.dart` | Session ended banner |

SVGs are stored as Dart `const String` — no asset declaration needed, works seamlessly in a Flutter package.

---

## Screen Designs

### 1. Home Screen

**Background:** `_MeshGradientBackground` — a `CustomPaint` widget that draws 3-4 soft gaussian blobs derived from `primaryColor` at varying opacities (0.08–0.18). Blobs are positioned at fixed offsets to create an aurora/mesh gradient effect. Static (no animation needed — keeps battery usage low).

**Hero card changes:**
- Remove the current `CircleAvatar` with sparkle icon
- Replace with `Lottie.asset('packages/synkora_chat/...choose_your_colors.json')` sized 120×120, `repeat: true`
- Card still has white background, shadow, title + subtitle + CTA buttons

### 2. Loading Screen

Replace the existing `_LoadingSkeleton` shimmer with `_AiLoadingIndicator`:
- Three concentric circles that pulse outward (scale + fade) using a single `AnimationController` with staggered intervals
- Center dot uses `primaryColor`
- Outer rings use `primaryColor.withOpacity(0.3)` and `0.1`
- Duration: 1.5s repeat
- No external assets required — pure `CustomPainter`

### 3. Empty Chat State

Replace "No messages yet" text block with `_EmptyChatIllustration`:
- SVG robot character (flat design, colorful): robot body in `primaryColor`, antenna, eyes, chat bubble floating above
- Caption: "Ask me anything" in `_brandMuted`
- SVG rendered via `SvgPicture.string(robotChatSvg, colorFilter: ...)` at 160px width

### 4. Session Ended Banner

Replace the plain yellow `_sessionEndedBanner` with a richer treatment:
- SVG robot waving hand, small green checkmark badge
- "This session has ended" text
- "Start new chat" action button

---

## Architecture

```
lib/src/
  assets/
    animations/
      choose_your_colors.json        ← Lottie file (bundled asset)
    illustrations/
      robot_chat.dart                ← const String robotChatSvg = '...'
      robot_wave.dart                ← const String robotWaveSvg = '...'
  ui/
    synkora_chat_widget.dart         ← add _MeshGradientBackground, _AiLoadingIndicator
    message_bubble.dart              ← unchanged
    suggestion_chips.dart            ← unchanged
```

pubspec.yaml flutter assets section:
```yaml
flutter:
  assets:
    - lib/src/assets/animations/choose_your_colors.json
```

---

## Implementation Steps

1. Add `lottie` and `flutter_svg` to `pubspec.yaml`
2. Copy Lottie JSON to `lib/src/assets/animations/`
3. Declare asset in `pubspec.yaml`
4. Write `robot_chat.dart` — SVG string constant, robot with chat bubble
5. Write `robot_wave.dart` — SVG string constant, robot waving + checkmark
6. Implement `_MeshGradientBackground` CustomPainter in `synkora_chat_widget.dart`
7. Replace home screen avatar with `Lottie.asset(...)`
8. Wrap home screen Scaffold body in `Stack` with `_MeshGradientBackground` behind
9. Replace `_LoadingSkeleton` with `_AiLoadingIndicator`
10. Replace `_ChatEmptyState` with `_EmptyChatIllustration`
11. Update session-ended banner with robot wave SVG
12. Run `flutter pub get` and test on macOS

---

## Constraints

- Package size increase: ~200KB (lottie) + ~100KB (flutter_svg) + ~50KB (JSON) = ~350KB acceptable
- The Lottie animation must not auto-play when widget is off-screen — use `animate: true` only when `_activeView == home`
- SVGs must not use hardcoded colors — all accent colors driven by `primaryColor` via `colorFilter`
- No network requests for any animation asset — all bundled
