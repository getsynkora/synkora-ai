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

Voice follows each agent's own settings (**Agents → the agent → Voice** on the
web): `voice_enabled`, `stt_provider`, `tts_provider`, `tts_voice`, `tts_model`
and `language`. The app never picks a provider for you.

| Agent setting | What the phone does |
|---|---|
| `web_speech` (the default) | Uses the phone's own recognizer and voice. Free, no keys. |
| `openai_whisper` (listening) | Records you and sends the audio through the workspace's Voice API key. |
| `openai_tts` / `elevenlabs` (speaking) | Synthesizes through the workspace's Voice API key, sentence by sentence. |

Listening and speaking are chosen independently. If an agent is set to a paid
provider with no key saved, the app says which one is missing and offers
**Use my phone's voice**. If voice is turned off for the agent it offers
**Turn on voice** (owner only).

```
mic ─► speech recognition (cloud Whisper, or the phone's own)
                │
   agent reply (SSE, voice_mode=true) ◄─┘
                │ sentence by sentence
                ▼
   speech (OpenAI / ElevenLabs, or the phone's own voice) ─► speaker
```

- **Low latency.** The reply is split into sentences and spoken as soon as the
  first one is ready; later sentences are synthesized while earlier ones play.
- **Interruptible.** Talk over the assistant and it stops. With cloud listening
  your first words are kept; with the phone's recognizer they are lost (it needs
  the microphone to itself). Tapping the orb always works.
- **Spoken commands.** "Switch to Muse", "say that again", "stop", "goodbye".
- **Agent replies are written for speech** (`voice_mode`): short, no markdown.

### Requirements

- Microphone permission, and Speech Recognition permission for the phone's own
  recognizer.
- Only agents set to a paid provider need a key, saved under Voice settings in
  the dashboard.

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
flutter run -t lib/dev/voice_demo.dart         # scripted cloud-voice preview, no backend
flutter run -t lib/dev/voice_live.dart         # REAL mic, wake word and phone speech with a
                                               #   stand-in agent (--dart-define=LIVE_TYPE=true
                                               #   types the question instead of speaking it)
flutter run -t lib/dev/voice_stt_check.dart    # only the phone's own recognizer
flutter run -t lib/dev/voice_smoke.dart \
  --dart-define=SMOKE_WAV=/path/to/hey.wav     # real mic/speaker/wake check
```

`wake_word_test.dart` runs the real model on macOS using speech from the
built-in `say` command, and is skipped on other machines.

### Known limits

- The phone's own **recognizer** could not be verified end to end: on the iOS
  simulator used for testing it fails with `error_unknown (300)` even in
  isolation (`voice_stt_check.dart`), so only the failure handling is verified
  there. Its speaking side (the phone's voice) was verified on the simulator.
  Try both on a real phone.
- Android has not been built or run in this repository's CI; the iOS simulator
  is the verified platform. Check capture, echo cancellation and the wake model
  on a real Android device before release.
- iOS enables echo cancellation through voice-chat audio mode, and Android
  through the communication source. Both are only fully verifiable on a real
  device with a speaker and microphone (a simulator cannot show whether the
  assistant hears itself).
- Always-on listening while locked or in the background is not supported.
