---
sidebar_position: 8
---

# Languages

Synkora's screens and chat clients can run in **English** and **German**. This page
shows where the language comes from on each surface, and how to set it.

## How a language is chosen

| Surface | Language comes from | How to set it |
|---|---|---|
| Dashboard | The language picked in this browser, else the account's, else the browser's | Language picker in the header (and on the sign-in pages) |
| Mobile app | The picker under **Profile → Language**, else the account, else the phone | Profile → Language |
| Web widget | `locale`, else `<html lang>`, else the browser | `SynkoraWidget.init({ locale: "de" })` |
| Flutter chat widget | `locale`, else the host app's language | `SynkoraChatWidget(locale: Locale('de'))` |
| Chrome extension | The browser's UI language | Browser settings |
| API and SDKs | The `language` field of a chat request | `language: "de"` |

## What changes

- **Fixed text** (buttons, menus, errors, times, dates) is shown in the language.
- **Widget text** (title, welcome message, placeholder, agent description, suggested
  prompts, privacy text) is the text you saved for that language under the widget's
  **Translations**. Anything left blank uses the default text.
- **Agent replies** default to that language. Chat clients send it with each message
  and the server asks the agent to reply in it; if the user writes in another
  language, the agent follows them. Replies depend on the model following that
  instruction.
- **Voice** (mobile app): the assistant's own lines, the spoken commands it listens for
  ("goodbye", "switch to …", and their German forms) and the recognizer hints follow
  the language of the **agent's voice setting**, so a German-speaking conversation is
  answered in German even if the app is in English.

## Use it from the API

Chat requests take an optional `language`, a BCP-47 code such as `de` or `pt-BR`:

```json
{ "agent_slug": "muse", "message": "Hallo!", "language": "de" }
```

It is accepted by the app chat (`POST /api/v1/agents/chat/stream` and the websocket),
the widget chat, and the public Agent API. Invalid values are ignored. The SDKs expose it
as `language` (JavaScript, Python) or `Language` (Go).

## Per-user language

A signed-in person's language is stored on their account as `interface_language`
(`GET`/`PUT /api/v1/profile/me`, and returned by `GET /console/api/auth/me`). Supported
values are `en` and `de`; older accounts holding `en-US` read as `en`.

## Not translated yet

- Many dashboard screens still show English; they are converted screen by screen.
- Text that comes from the API (validation and error messages).
- Emails, the docs site and the marketing pages.
- Right-to-left layout.

To add a language, see `web/README.md` (dashboard), `flutter/synkora_mobile/l10n.yaml`
(mobile) and `SUPPORTED_LANGUAGES` in `api/src/services/i18n/languages.py`.
