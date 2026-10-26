# Synkora Mobile

Dedicated Flutter app for signed-in Synkora users.

## Features in this slice

- Synkora account sign-in
- secure token storage
- tenant selection and tenant switching
- tenant agent directory
- agent detail page
- authenticated streaming chat
- hands-free voice conversations with any agent (see below)
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

## Voice conversations

Talk to any agent hands-free, with the phone as the hardware and the agent as
the software. Start from the **Talk to …** card on Home, an agent's **Talk**
button, or the waveform button in a chat. Turn on **Hey Synkora** in the voice
settings and the app opens a conversation when it hears the phrase.

### How it works

```
mic ─► voice-activity detection ─► Whisper (your workspace's OpenAI key)
                                        │
                  agent reply (SSE, voice_mode=true) ◄─┘
                        │ sentence by sentence
                        ▼
                  TTS (OpenAI or ElevenLabs) ─► speaker
```

- **Low latency.** The reply is split into sentences and spoken as soon as the
  first one is ready, with later sentences synthesized while earlier ones play.
- **Interruptible.** Talk over the assistant and it stops; what you started
  saying becomes your next turn. Playback loudness raises the bar so it does not
  hear itself.
- **Spoken commands.** "Switch to Muse", "say that again", "stop", "goodbye".
- **Per-agent voice.** Each agent's voice, model and language from its web
  Voice settings are used.
- **Agent replies are written for speech** (`voice_mode`): short, no markdown.

### Requirements

- The workspace needs an OpenAI key for speech recognition (`openai_whisper`)
  and either `openai_tts` or `elevenlabs` for speech output, saved under Voice
  settings in the dashboard. Without them the app says what is missing.
- Microphone permission.

### Wake word ("Hey Synkora")

Detection runs **on the device** with a small keyword-spotting model
(`assets/voice/wake`, Apache-2.0) in a background isolate. No audio is sent
anywhere until a conversation starts. It is **foreground only**: mobile OSes
suspend apps that are not visible, so the phrase is heard while Synkora is open,
not while the phone is locked or the app is in the background.

Three sensitivity presets are available. They were measured on synthetic speech
(24 voices, 144 phrase clips, 192 look-alike clips, 192 sentences that mention
"Synkora" without "hey", and 26 minutes of continuous speech):

| Preset | Phrases caught | False wakes |
|---|---|---|
| Fewer wakes | ~70% | none in the test data |
| Balanced (default) | ~84% | none in the test data |
| Catch more | ~86% | none in the test data, may rarely wake on the bare name |

These are synthetic voices, not people. Expect real-world accuracy to differ,
and use the sensitivity setting. Tapping the orb always works.

### Previewing and testing

```bash
flutter test                                   # unit + widget tests
flutter run -t lib/dev/voice_demo.dart         # scripted preview, no backend
flutter run -t lib/dev/voice_smoke.dart \
  --dart-define=SMOKE_WAV=/path/to/hey.wav     # real mic/speaker/wake check
```

`wake_word_test.dart` runs the real model on macOS using speech from the
built-in `say` command, and is skipped on other machines.

### Known limits

- Android has not been built or run in this repository's CI; the iOS simulator
  is the verified platform. Check capture, echo cancellation and the wake model
  on a real Android device before release.
- iOS enables echo cancellation through voice-chat audio mode, and Android
  through the communication source. Both are only fully verifiable on a real
  device with a speaker and microphone (a simulator cannot show whether the
  assistant hears itself).
- Always-on listening while locked or in the background is not supported.
