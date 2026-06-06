# Synkora Mobile App Design

**Date:** 2026-06-04
**Status:** Proposed
**Owner:** Product + Mobile + Platform

---

## Summary

Build **Synkora Mobile** as a dedicated Flutter app for signed-in Synkora users.

This is **not** the same product as the embeddable `synkora_chat` widget package.
The widget SDK remains useful for customer apps and branded embeds. The dedicated
mobile app is the native companion for Synkora accounts:

- users sign in with their Synkora account
- users see **all agents available in their current tenant**
- users can chat with agents using text, voice, camera, files, and push
- the app feels clearly **Synkora-branded**, using the existing Flutter chat
  visual language as the starting point

Core decision:

- **Use the same backend auth/session architecture as web**
- **Do not use widget-key auth as the primary login model for the mobile app**

---

## Product Decisions

### 1. Account-first, not widget-first

The dedicated mobile app should require login before access.

Why:

- this is the user's Synkora workspace, not a public agent surface
- users need access to all tenant agents, recent conversations, inbox items,
  notifications, and account settings
- role and tenant scoping already exist in the current backend auth model

### 2. Tenant-scoped agent directory

After login, the user lands in a native **Agents** experience that lists all
agents in the active tenant via the authenticated tenant APIs.

This should be the main difference from the embeddable Flutter chat package:

- embeddable Flutter chat = one widget / one agent entry point
- Synkora Mobile = one account / one tenant / many agents

### 3. Branded like existing Flutter chat

The mobile app should inherit the design DNA already visible in
`flutter/synkora_chat`:

- mint primary accent
- deep ink surfaces
- soft neutral background
- mesh gradients and animated states
- rounded, premium, editorial cards

Default brand palette:

- `primary`: `#79DFBC`
- `ink`: `#0F172A`
- `muted`: `#64748B`
- `bg`: `#F8FAFC`
- `panel`: `#FFFFFF`

Tenant and agent accents can layer on top of the default Synkora brand, but the
app should remain recognizably Synkora.

---

## Goals

### Primary goals

- Make mobile the fastest way to **use** Synkora agents
- Let a signed-in user access all tenant agents in one native app
- Make multimodal usage first-class: voice, camera, images, files, push
- Keep startup, scrolling, and streaming extremely fast

### Non-goals for MVP

- full mobile parity for every dashboard admin screen
- deep agent-building and system configuration workflows
- replacing the embeddable Flutter widget SDK

---

## User Experience

## App structure

Bottom navigation for MVP:

1. **Agents**
2. **Inbox**
3. **Activity**
4. **Profile**

Primary center of gravity is the **Agents** tab.

## Main flows

### Auth flow

1. Launch app
2. If valid session exists, restore user and tenant context
3. Else show sign-in
4. After sign-in:
   - if user belongs to one tenant, continue directly
   - if user belongs to multiple tenants, show a tenant picker
5. Load agent directory for selected tenant

### Agent usage flow

1. Open app
2. Browse or search tenant agents
3. Open agent detail page
4. Start or resume a conversation
5. Use text, microphone, camera, gallery, or file picker
6. Receive streamed response and optional push follow-up

### Inbox flow

Inbox is a unified place for:

- agent replies while app was backgrounded
- scheduled-task completions
- approval requests
- reminders and follow-ups

This is intentionally separate from chat history so the app feels operational,
not like a plain messenger.

---

## Screens

### 1. Sign-in

Use Synkora account login, matching the web auth model.

MVP:

- email/password
- session restore
- logout

Next:

- Google / Microsoft / Apple via PKCE native flow
- SAML handoff through hosted auth web flow when required
- 2FA support

### 2. Tenant picker

Shown only when the account belongs to multiple tenants.

Each row shows:

- tenant name
- role
- optional tenant logo / initials

### 3. Agents home

Sections:

- pinned agents
- recent agents
- all agents
- suggested actions
- unread activity badges

Capabilities:

- search
- filter by type / recent / favorites
- quick start new conversation

### 4. Agent detail

Shows:

- avatar
- name
- short description
- capabilities
- recent sessions
- quick actions

CTA:

- `Message`
- `Talk`
- `Scan with camera`

### 5. Chat

Chat experience should feel more advanced than the current widget:

- streaming response rendering
- tool activity rail
- voice input button
- camera capture button
- gallery/file attach
- upload progress
- message actions
- session list and resume

Composer actions:

- text
- voice-to-text
- photo capture
- image upload
- document upload
- data file upload

### 6. Inbox

Unified timeline for:

- push notifications
- completed background tasks
- approvals
- alerts

### 7. Profile

- account info
- current tenant
- switch tenant
- notification settings
- voice preferences
- sign out

---

## Design Direction

## Brand language

Use the existing Flutter chat styling as the base, then expand it into a fuller
app shell.

Visual rules:

- strong contrast between `ink` top bars and light content surfaces
- mint highlight for primary CTA and voice state
- artistic mesh gradient backgrounds on key surfaces
- large expressive cards instead of flat utility tables
- motion only where meaningful: chat streaming, voice pulse, card reveal

## UI tone

The app should feel:

- premium
- modern
- artistic
- operationally clear

It should not feel:

- like a generic messenger
- like a wrapped admin dashboard
- like a web app inside a phone frame

---

## Revised Technical Plan

## Auth architecture

### Decision

Use the same **Synkora account and session backend** as web:

- `POST /console/api/auth/signin`
- `POST /console/api/auth/refresh`
- `GET /console/api/auth/me`
- `POST /console/api/auth/logout`

The backend already supports a mobile-safe refresh fallback:

- `/console/api/auth/refresh` accepts `refresh_token` in the request body
- this is suitable for native clients that are not relying on browser cookies

### Mobile token storage

Use platform-secure storage:

- iOS: Keychain
- Android: EncryptedSharedPreferences / Keystore-backed secure storage

Storage model:

- access token in memory + secure storage
- refresh token in secure storage
- no token storage in plain shared preferences

This keeps the **same session architecture** as web while adapting storage to a
native app. The architecture is shared; the storage mechanism is platform-appropriate.

### Tenant handling

The current backend login returns a tenants list, and access tokens are
tenant-scoped via `tenant_id` in JWT claims.

Plan:

- if one tenant: use it automatically
- if multiple tenants: show picker after login
- on tenant switch:
  - preferred: use `POST /console/api/auth/refresh` with `tenant_id`
  - better long-term: expose a controller endpoint for the existing
    `SessionService.switch_tenant(...)`

Required API addition:

- `POST /console/api/auth/switch-tenant`
  - request: `{ tenant_id }`
  - response: new access token bound to selected tenant

This avoids mobile clients overloading refresh semantics for tenant switching.

### Social login

For mobile social sign-in, do not embed provider pages in a WebView.

Use:

- iOS `ASWebAuthenticationSession`
- Android Chrome Custom Tabs
- PKCE flow

Recommendation:

- adapt the existing extension PKCE pattern in `console/auth.py`
- add mobile-specific authorize/token endpoints or generalize the PKCE helpers

---

## API model for the app

## Existing APIs to reuse

### Tenant-authenticated

- `GET /api/v1/agents/`
- `GET /api/v1/agents/{agent}`
- `GET /api/v1/agents/{agent_id}/conversations`
- `POST /api/v1/agents/conversations`
- `GET /api/v1/agents/conversations/{conversation_id}`
- `GET /api/v1/agents/conversations/{conversation_id}/messages`
- `POST /api/v1/agents/chat/upload-attachment`
- voice endpoints in `/api/v1/voice/...`

### Existing Flutter/widget APIs that remain useful as reference

- widget config
- widget sessions
- widget mobile allowance
- Flutter local cache behavior

These are good implementation references, but the dedicated app should favor
tenant-authenticated APIs over widget-key APIs.

## API additions recommended for mobile

### MVP additions

1. `POST /console/api/auth/switch-tenant`
2. `GET /api/v1/mobile/bootstrap`
   - returns account summary
   - current tenant
   - tenant branding
   - pinned/recent agent metadata
3. `GET /api/v1/mobile/inbox`
4. `POST /api/v1/mobile/push/register`
   - account/device scoped, not widget scoped

### Multimodal additions

5. `POST /api/v1/agents/chat/transcribe-and-send`
   - optional convenience endpoint for lower-latency voice UX
6. `POST /api/v1/agents/chat/scan-image`
   - normalize camera capture + OCR + attachment + prompt assist

These are not mandatory for v1 launch, but they reduce app logic duplication
and make mobile behavior cleaner.

---

## Flutter app architecture

## Stack

- Flutter
- Riverpod for state management
- `go_router` for routing
- `dio` for HTTP and SSE
- `flutter_secure_storage` for tokens
- Drift / SQLite for local persistence
- Firebase Messaging for push

## Modules

- `core`
- `auth`
- `tenants`
- `agents`
- `chat`
- `voice`
- `camera`
- `uploads`
- `inbox`
- `profile`

## Local persistence

Persist:

- active account summary
- selected tenant
- agent directory cache
- recent sessions
- recent messages
- upload draft state

Do not persist:

- tokens outside secure storage

## Networking

- `Authorization: Bearer <access_token>` on authenticated requests
- refresh on 401 using stored refresh token
- rotate refresh token on every refresh
- update local tenant context after tenant switch

---

## Multimodal plan

## Voice

MVP:

- hold-to-talk or tap-to-record
- upload audio to existing `/api/v1/voice/transcribe`
- insert text into composer

V2:

- direct speech mode
- streamed partial transcription
- optional TTS playback for agent replies

## Camera

MVP meaning of "camera read everything":

- capture image
- compress locally
- upload as chat attachment
- add helper prompt:
  - "Read this receipt"
  - "Summarize this document"
  - "What is in this image?"

V2:

- OCR pipeline
- document edge detection
- receipt/invoice templates
- whiteboard summarization

## Files

Support:

- images
- PDF
- DOCX
- TXT / MD / CSV

Use the existing authenticated attachment upload endpoint for MVP.

---

## Performance plan

## Targets

- cold start under 2 seconds on mid-range phones
- warm resume near-instant
- 60fps scrolling in agent lists and chat
- first cached content visible immediately
- no WebView-based main product flows

## Tactics

- local-first boot with stale-while-revalidate
- paginated agent and conversation lists
- image compression off the UI thread
- streaming updates appended incrementally
- avoid rebuilding full message list during stream
- background upload queue with retry
- prefetch top agents and recent sessions after login

## Observability

Track:

- app cold start
- screen load latency
- token refresh failures
- chat stream start time
- time to first chunk
- attachment upload time
- push delivery/open rate
- crash-free sessions

---

## Delivery Phases

## Phase 1: Signed-in mobile foundation

- native sign-in with Synkora account
- secure token storage
- tenant picker
- agent directory
- agent detail
- text chat
- session history
- push registration
- Synkora-branded app shell

## Phase 2: Multimodal usage

- voice-to-text
- camera capture
- image and file upload
- improved tool activity UI
- inbox tab

## Phase 3: Advanced mobile agent experience

- TTS playback
- live voice mode
- approvals and actions from notifications
- mobile-specific productivity shortcuts

---

## Sprint Backlog

## Sprint 1

- create Flutter app shell
- implement auth repository
- sign-in / restore / logout
- build tenant picker
- fetch agent directory
- design system foundation with Synkora colors

## Sprint 2

- agents home
- agent detail
- conversations list
- chat screen with streaming
- recent sessions

## Sprint 3

- push registration and inbox skeleton
- attachment upload
- camera picker
- voice transcription
- offline cache refinement

## Backend tasks in parallel

- expose `switch-tenant` endpoint
- define mobile push registration model
- verify authenticated attachment upload path for native clients
- confirm voice endpoint auth behavior for mobile app users

---

## Repo alignment

This plan intentionally builds on the current repo instead of replacing it.

Relevant current assets:

- `flutter/synkora_chat`
- `flutter/synkora_push`
- `api/src/controllers/console/auth.py`
- `api/src/services/session_service.py`
- `api/src/controllers/widgets.py`
- `api/src/controllers/voice.py`
- `api/src/controllers/agents/index.py`

Important implementation stance:

- keep `synkora_chat` as the embeddable chat package
- create a separate dedicated app, likely under `flutter/synkora_mobile`
- share visual tokens and some UI components where practical
- do not force the dedicated app through widget-key auth

---

## Open questions

1. Should MVP support only email/password, or also Google on day one?
2. Do we want mobile users to switch tenants in-app at launch, or lock to the
   most recent tenant until profile settings are opened?
3. Should the first mobile release allow only agent usage, or lightweight agent
   controls such as pause, reset, and view analytics?

---

## Recommendation

Ship the first release as a **signed-in native Synkora companion app** focused
on using tenant agents beautifully and quickly.

That gives Synkora a coherent product story:

- web = build and manage agents
- mobile = use your agents anywhere
- Flutter SDK = embed Synkora agents inside customer apps
