# Synkora Chrome Extension — Design Spec

**Date:** 2026-05-12
**Status:** Approved
**Author:** Raju (via brainstorming session)

---

## Overview

A Manifest V3 Google Chrome extension that gives Synkora agent builders access to their custom agents on any webpage. The extension runs as a native Chrome side panel — agents are page-aware, can read selected text, and are available everywhere the user browses.

---

## Goals

- Agent builders can use any of their Synkora agents while browsing any website
- Agents are aware of the current page content (viewport or full page, user-controlled)
- Right-click selected text sends it directly to the active agent
- Consistent, high-quality UI with per-agent identity (avatar, name, accent color) inside a stable extension shell
- Zero new chat/agent backend endpoints — reuses existing `/api/v1` API for all messaging
- One small backend addition required: `/console/api/auth/extension` PKCE endpoint for secure login

## Non-Goals (v1)

- End-user (customer) access to agents via the extension — agent builders only
- Firefox / Safari support — Chrome only for v1
- Offline mode
- Extension-specific backend proxy layer (can be added as v2 optimization)

---

## Approach

Standalone Chrome MV3 extension (Approach B) — fresh React app in the side panel, authenticates via Synkora JWT, calls existing API directly. No iframe wrapping of `widget.js`. Purpose-built UX for the extension context.

---

## Architecture

### Extension Structure

```
extension/
├── wxt.config.ts                  # WXT config (Vite under the hood)
├── package.json
├── src/
│   ├── entrypoints/
│   │   ├── background.ts          # MV3 service worker
│   │   ├── content.ts             # Content script (page context extraction)
│   │   ├── sidepanel/
│   │   │   ├── index.html
│   │   │   ├── main.tsx
│   │   │   └── App.tsx
│   │   └── popup/                 # Toolbar click — login + quick settings
│   │       ├── index.html
│   │       └── App.tsx
│   ├── components/
│   │   ├── AgentPicker.tsx        # Agent list + default selection dropdown
│   │   ├── ChatPanel.tsx          # Main chat container
│   │   ├── MessageList.tsx        # Scrollable message history
│   │   ├── ContextBadge.tsx       # Page context on/off indicator
│   │   └── TextSelectionBadge.tsx # Badge shown when text pre-filled from page
│   ├── hooks/
│   │   ├── useChat.ts             # SSE streaming, message management
│   │   ├── useAgents.ts           # Agent list, default, switching
│   │   └── usePageContext.ts      # Reads context from content script
│   ├── store/
│   │   └── extension.ts           # Zustand store
│   ├── lib/
│   │   ├── api.ts                 # Typed Synkora API client
│   │   ├── auth.ts                # Token management, PKCE helpers
│   │   └── page-extractor.ts      # Viewport + full-page text extraction
│   └── types/
│       └── index.ts
```

### Tech Stack

| Concern | Choice | Reason |
|---|---|---|
| Build framework | WXT (latest) | Best MV3 DX, Vite-based, HMR across all entry points |
| UI | React 19 + TypeScript 5 | Consistent with Synkora web app |
| Styling | Tailwind CSS v4 | Consistent with Synkora web app |
| State | Zustand | Already used in Synkora web app |
| Icons | Lucide React | Already used in Synkora web app |
| HTTP / Streaming | Native `fetch` + `EventSource` | No extra dependencies needed |
| Chrome types | `@types/chrome` | Official Chrome API types |

### MV3 Constraints Addressed

- **SSE runs directly in the side panel** — the side panel is a long-lived page. The service worker is ephemeral (killed after ~30s idle) and cannot maintain persistent connections. All streaming happens in the side panel.
- **Service worker keepalive** — `chrome.alarms` fires every 20s to prevent premature termination during token refresh cycles.
- **No `eval()` or inline scripts** — strict CSP compliance, all code bundled by WXT.
- **Long-lived port connection** — `chrome.runtime.connect` between content script and side panel for continuous page context updates. Not one-shot `sendMessage`.
- **`chrome.storage.session`** for ephemeral data (access token, current page context). **`chrome.storage.local`** for persistent data (refresh token, agent preferences, conversation history).

---

## Authentication

### Flow

1. User clicks toolbar icon → popup opens with "Connect to Synkora" button
2. Click opens `{SYNKORA_URL}/auth/extension?code_challenge=...&state=...` (PKCE + state nonce)
3. User logs in (or is already logged in) → Synkora redirects to `chrome-extension://<ext-id>/popup/callback.html` with auth code
4. Extension validates `state` nonce (from `chrome.storage.session`) — abort if mismatch
5. Extension exchanges code for JWT access token + refresh token
6. Access token → `chrome.storage.session` (in-memory, cleared on browser close)
7. Refresh token → `chrome.storage.local` (persisted, sandboxed to extension)
8. Popup transitions to connected state — user picks default agent, done

### Token Lifecycle

- Access token refreshed silently 60s before expiry via `chrome.alarms`
- On 401 response → silent refresh attempt → if fails, show "Reconnect" banner
- Hard logout clears both storage locations

### Security Model

| Threat | Mitigation |
|---|---|
| Auth code interception | PKCE with S256 code challenge |
| CSRF on callback | `state` nonce validated from session storage, abort on mismatch |
| Token theft by other extensions | `chrome.storage` is sandboxed per extension by Chrome |
| XSS in extension page | Strict CSP in manifest — no inline scripts, no `eval`, no remote scripts |
| Token leakage to content script | Message protocol never includes tokens. Content script only sends page text. |
| Token leakage in logs | Tokens never logged anywhere in extension code |
| Message spoofing | All `chrome.runtime.onMessage` handlers validate `sender.id === chrome.runtime.id` |
| Access token on disk | Stored only in `chrome.storage.session` (in-memory only) |
| HTTPS bypass | All API calls assert `https://` scheme before fetch |
| Overprivileged extension | Minimum permissions only (see below) |
| Passive tab surveillance | `activeTab` model — content script only activates on explicit user interaction |

### Manifest Permissions (minimum viable)

```json
{
  "permissions": ["storage", "sidePanel", "alarms", "contextMenus", "activeTab"],
  "host_permissions": ["https://<synkora-instance>/*"]
}
```

---

## Chat & Streaming

### SSE Connection

The side panel connects directly to `/api/v1/chat/stream` via `fetch` with `ReadableStream`. Same endpoint as the web app — no new backend work.

### Conversation Modes

| Mode | Behavior | Storage |
|---|---|---|
| Per-page | New conversation when URL changes | `chrome.storage.session` keyed by URL |
| Persistent | One conversation across all pages | `chrome.storage.local` keyed by agent ID |

User controls this via a toggle in the panel. Default is per-page.

Conversation history stored locally. Only the active messages window sent to the API (last 20 messages or ~4k tokens, whichever is smaller — token-budgeted to stay within model context limit).

### Page Context Flow

```
Content script
  → extracts viewport text via IntersectionObserver (default)
  → or document.body.innerText truncated to 8k chars (full page mode)
  → sends via chrome.runtime.connect port to service worker
  → service worker relays to side panel

Side panel
  → "Include page context" toggle ON → prepend text as system context before next message
  → context prepended as system message (not mid-conversation injection)
```

### Right-Click Selected Text

1. Content script detects `mouseup` → selection exists → sends text to service worker
2. `chrome.contextMenus` item "Ask [Agent Name]" appears
3. User clicks → side panel opens, selected text pre-filled in input with "From page selection" badge
4. User can edit before sending

---

## UI/UX

### Side Panel Layout

```
┌─────────────────────────────────┐
│ [Avatar] Agent Name    [Switch] │  <- Agent identity bar
│ synkora.com · Page context: ON  │  <- Current site + context toggle
├─────────────────────────────────┤
│                                 │
│         Message list            │  <- Scrollable, markdown rendered
│                                 │
│  [From page selection badge]    │  <- Shown when text was pre-filled
│                                 │
├─────────────────────────────────┤
│ [Full page] [Clear] [History]   │  <- Toolbar controls
├─────────────────────────────────┤
│ [Input field.................]  │  <- Textarea, auto-resize
│                          [Send] │
└─────────────────────────────────┘
```

### Branding Model

- Extension shell UI uses a consistent Synkora design system (stable colors, layout)
- Each agent shows its own avatar, name, and accent color as an identity badge at the top
- Switching agents updates the identity badge only — layout and chrome remain stable
- No full re-theme on agent switch (avoids disorienting color changes)

### Agent Switcher

- Click `[Switch]` → dropdown lists all agents with avatars
- Default agent marked with a pin icon
- "Set as default" option per agent
- Switch is instant — starts new conversation (or continues if persistent mode)

### Quick Actions

- "Summarize this page" button in empty state — one click, no typing required
- Matches the UX pattern of top competitors (Perplexity, Monica)

### UI States

| State | Behavior |
|---|---|
| Not connected | Popup shows login CTA; side panel shows "Connect Synkora" screen |
| Loading agents | Skeleton loaders (not spinners) |
| Streaming response | Animated typing indicator; stop button appears |
| Page context unavailable | Context badge greyed out with tooltip |
| API/network error | Inline error with retry button (no modals) |
| Token expired | Silent refresh; "Reconnect" banner only if refresh fails |
| Content script blocked | Side panel still works; context badge shows "Unavailable on this page" |
| Extension updated mid-session | Graceful reload prompt; conversation saved to storage first |

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl/Cmd + Shift + S` | Toggle side panel open/close |
| `Enter` | Send message |
| `Shift + Enter` | New line in input |
| `Esc` | Close panel |

### Markdown Rendering

Reuses the same inline markdown parser pattern from `widget.js` (inline code, links, bold, italic, lists) for consistency with the web app chat experience.

---

## Competitor Analysis

| Extension | Strengths | Weaknesses |
|---|---|---|
| Monica | Polished side panel, page summarization | Generic AI, not custom agents |
| Perplexity | Fast, clean, great search | No custom agents, no personality |
| Sider | Multi-model, sidebar, selection | Cluttered UI |
| ChatGPT Extension | Brand recognition | Basic, shallow page context |
| Merlin | Right-click on any text | Cheap feel, ads |

**Differentiators for Synkora extension:**

- Your own custom-trained agent with knowledge base, tools, personality
- Multi-agent switching in one extension
- Agents can use RAG, database connections, custom tools — not just LLM chat
- Self-hosted option — point extension at your own Synkora instance

**Three things competitors do well that we must match:**

1. Sub-200ms panel open — instant feel, no loading flash
2. Clean empty state — first open is inviting, not blank
3. One-click "Summarize this page" quick action

---

## Error Handling

- API unreachable → inline banner + retry button, previous messages stay visible
- SSE drops mid-response → show partial response + "Response interrupted — retry?"
- Page context extraction fails → silently disable context toggle, tooltip explains
- Agent has no response → show agent's configured fallback message, never raw error
- Content script blocked by page CSP → side panel still works, context badge shows "Unavailable on this page"

---

## Testing

| Layer | Tool | What |
|---|---|---|
| Unit | Vitest | Hooks, store logic, page extractor, auth utils |
| Component | React Testing Library | AgentPicker, ChatPanel, MessageList |
| Integration | Playwright + chrome-extension plugin | Full extension load, auth flow, send message, stream |
| Manual | Chrome Extension DevTools | Service worker inspector, storage viewer, message passing |

CI: GitHub Actions — build + unit/component tests on every PR. Integration tests on merge to main.

---

## Chrome Web Store Publishing Checklist

- Privacy policy disclosing page content reading
- Justification for `activeTab` permission documented
- Extension ID pinned for production (prevents change on re-upload)
- Source maps excluded from production build
- Screenshots and promotional images prepared
- Extension description mentions self-hosted Synkora support

---

## Implementation Phases

### Phase 1 — Core (ship this)
- WXT project scaffold with React + TypeScript + Tailwind
- Auth flow (PKCE + state nonce + token storage)
- Side panel with chat UI and SSE streaming
- Agent list + default agent selection + switching
- Page context extraction (viewport mode)

### Phase 2 — Page Awareness
- Full-page context mode
- Right-click context menu + text selection flow
- Per-page vs persistent conversation toggle
- "Summarize this page" quick action

### Phase 3 — Polish
- Keyboard shortcuts
- Conversation history browser
- Extension settings page
- Chrome Web Store submission
