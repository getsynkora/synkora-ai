# Widget Page-Context-Awareness E2E Test Guide

Verifies the widget page-context-awareness feature (host apps pushing arbitrary, schema-less
context describing what the end user is currently looking at into the embeddable chat widget),
per `docs/superpowers/specs/2026-08-18-widget-page-context-design.md` and
`docs/superpowers/plans/2026-08-18-widget-page-context.md` (11 tasks).

All backend steps below were run against the live local stack (`docker-compose`, `api` on
`http://localhost:5001`) using Python's `urllib` inside the `api` container (avoids shell
`!`/quoting issues — see project memory). Frontend-only behaviors (SPA navigation detection,
`setContext`/`clearContext` public API) have no browser available in this environment and are
instead verified by direct code inspection of `web/public/widget.js`, cross-checked against the
backend-observable effects they produce (documented per step below).

## Prerequisites

- `docker compose up -d` running, `api` container healthy, restarted after code changes
  (`docker compose restart api` — no hot-reload for these files).
- A widget with `allowed_domains: ["*"]` and its plaintext `X-Widget-API-Key` (created via
  `POST /api/v1/widgets` or regenerated via `POST /api/v1/widgets/{id}/regenerate-key`, both
  requiring a console Bearer token — `admin@localhost.com` / `Admin123!` via
  `POST /console/api/auth/login`).
- **Gotcha**: `WidgetAuthMiddleware.validate_domain()` rejects requests with no `Origin` header
  even when `allowed_domains == ["*"]` — an `Origin` header (any value) must be present for the
  wildcard to match. All calls below send `Origin: http://widget-test.local`.
- **Gotcha**: the SSE `done` event's discriminator key is `"type"` (`{"type": "done", ...}`), not
  `"event"` — `conversation_id` lives under `metadata.conversation_id` on that event.

## Real bug found and fixed during this test: cache-append bypassed page_context persistence

**Symptom**: sending a second message with `page_context` identical to the first message's did
NOT get deduped (both messages persisted the same `page_context` in `message_metadata`), and the
historical loop in `_build_prompt` never applied the `[Page context...]` prefix to the first
turn when building the prompt for the second request — only the current turn got it.

**Root cause** (confirmed via `superpowers:systematic-debugging`, not guessed): every call to
`ChatService.save_user_message` (`api/src/services/agents/chat_service.py`) fires a background
task (`_append_message_to_cache`) that incrementally appends `{"role": "user", "content": message}`
straight into the Redis conversation-history cache — **without** `page_context` — regardless of
what was saved to the DB's `message_metadata`. Because this happens on every turn, the Redis cache
is always "warm" by the second request. `ConversationService.get_conversation_history_cached()`
therefore always gets a cache **HIT** and returns this incomplete cached data; it never falls
through to the DB-load branch where the `page_context` extraction logic (added in Task 1) lives.
Both `_resolve_page_context_for_persistence` (dedup) and `_build_prompt`'s historical loop read
from this same incomplete `conversation_history`, so both were silently blind to `page_context` on
every turn except the current one.

**Fix**: `_append_message_to_cache` now accepts a `page_context` param and includes it in the
cached message dict when present; `save_user_message` passes `metadata.get("page_context")`
through to it. This mirrors the same extraction the DB-load path already did, keeping the two
code paths consistent. Added `api/tests/unit/services/agents/test_chat_service.py` (2 new tests)
to lock in the fix — `docker compose exec -T api pytest tests/unit/ -q` → **4015 passed** (up from
4013) after the fix, zero regressions.

## Step 1 — First message with `page_context`

```
POST http://localhost:5001/api/v1/widgets/chat
X-Widget-API-Key: {plaintext widget api key}
Origin: http://widget-test.local
Content-Type: application/json

{
  "message": "Hello, what can you help with?",
  "session_id": "e2e_pagecontext_retest2",
  "page_context": {"url": "http://test.local/page1", "title": "Test Page 1"}
}
```

**Actual response (verified live)**: `200`, SSE stream ending in
`{"type": "done", "metadata": {..., "conversation_id": "af5ef8c6-8138-4eb4-873c-7b16931a66f5"}}`.

DB check:
```sql
SELECT role, message_metadata->'page_context' FROM messages
WHERE conversation_id='af5ef8c6-8138-4eb4-873c-7b16931a66f5' AND role='USER';
```
Result: `{"url": "http://test.local/page1", "title": "Test Page 1"}` — persisted correctly.

## Step 2 — Second message, identical `page_context` (dedup check)

Same request shape, `conversation_id` set to the value from Step 1, same `page_context`.

**Actual DB result (verified live, after the fix)**:
```
role | page_context
-----+--------------------------------------------------------------
USER | {"url": "http://test.local/page1", "title": "Test Page 1"}
USER | (null)
```
Second turn's `page_context` is `NULL` — deduped correctly (`_resolve_page_context_for_persistence`
found an identical prior turn in `conversation_history` and skipped re-persisting it).

**Prompt check** (API logs, `docker compose logs api`): the LLM request payload for this second
call includes the `[Page context...]` prefix on **both** the historical first turn and the
current turn:
```
{'role': 'user', 'content': '[Page context — reference data from the host app, not user-authored: {"url": "http://test.local/page1", "title": "Test Page 1"}]\nHello, what can you help with?'},
{'role': 'assistant', 'content': '...'},
{'role': 'user', 'content': '[Page context — ...]\nSecond message, still page1'}
```
Confirms the historical replay logic (`_build_prompt`) now correctly sees `page_context` on prior
turns instead of only the current one.

## Step 3 — Baseline: no `page_context` field at all

```json
{"message": "Baseline message with no context field", "session_id": "e2e_baseline_session"}
```
(Simulates a widget page load with no `setContext()` call — `widget.js`'s `_pageContext` defaults
to `this._basePageContext()` = `{url: location.href, title: document.title}`, but this test omits
the field entirely to isolate backend behavior when it's absent.)

**Actual DB result (verified live)**: `message_metadata->'page_context'` is `NULL` — no crash, no
spurious context injected into the prompt.

## Step 4 — Oversized `page_context` (size cap)

```json
{"message": "Oversized context test", "session_id": "e2e_oversize_session",
 "page_context": {"blob": "xxxxxx...(600 bytes)..."}}
```

**Actual DB result (verified live)**: `message_metadata->'page_context'` is `NULL` — silently
discarded by `_cap_page_context()` (500-byte cap), confirmed via `api` logs
(`Discarding oversized page_context (... bytes > 500 byte cap)`), request still succeeded (`200`,
never fails the request per design).

## Step 5 — Changed `page_context` mid-conversation (not deduped)

First turn with `page_context={"url": ".../page1", ...}`, second turn in the same conversation
with a **different** `page_context={"url": ".../page2", ...}`.

**Actual DB result (verified live)**:
```
role | page_context
-----+--------------------------------------------------------------
USER | {"url": "http://test.local/page1", "title": "Test Page 1"}
USER | {"url": "http://test.local/page2", "title": "Test Page 2"}
```
Both persisted (not deduped, since they differ) — confirms `_resolve_page_context_for_persistence`
only dedups on an exact match against the prior user turn, not unconditionally.

**Prompt check**: API logs confirm each turn's own prefix is attributed correctly per-turn — the
historical (page1) turn keeps its page1 prefix, the current (page2) turn gets its own page2
prefix. No cross-contamination between turns.

## Step 6 — Real agent grounding on `page_context` (not just prompt-injection)

The design doc's own Testing Plan calls for confirming "the agent grounds ... on ... context
without the user stating it" — not merely that the prefix text appears in the LLM request. This
was verified separately, with a `page_context` payload the agent has no other way to have known:

```json
{
  "message": "What invoice am I currently looking at, and is it overdue?",
  "session_id": "e2e_grounding_test",
  "page_context": {
    "page": "invoice_detail",
    "invoice_id": "INV-88213",
    "customer_name": "Acme Rockets",
    "amount_due": "$4,250.00",
    "status": "overdue"
  }
}
```

**Actual agent response (verified live)**:
> "You're currently viewing **Invoice INV-88213** for **Acme Rockets**, with an amount due of
> **$4,250.00**. Yes — the status is **overdue**."

The agent correctly answered with data it could only have obtained from `page_context` — confirms
real grounding, not just prefix presence in the request payload.

## Step 7 — SPA navigation reset (`pushState`/`replaceState`/`popstate`/`hashchange`)

No browser available in this environment. Verified by code inspection instead:
- `web/public/widget.js:14-21` monkey-patches `history.pushState`/`replaceState` once (guarded by
  the existing `if (global.SynkoraWidget) return;` early-return) to dispatch a
  `synkoralocationchange` `Event` after calling through to the original method.
- `web/public/widget.js:1042-1048` (in the `Widget` constructor): initializes
  `this._pageContext = this._basePageContext()` and registers a shared handler on
  `synkoralocationchange`, `popstate`, and `hashchange` that resets `_pageContext` back to
  `this._basePageContext()` (`web/public/widget.js:1055`, `{url: location.href, title:
  document.title}`).
- Net effect: any SPA navigation (real or `pushState`-driven) resets stale host-supplied context
  to a safe default before the next message is sent — consistent with the backend behavior
  verified in Step 3 (absent/default context never breaks the request).

## Step 8 — `setContext` / `clearContext` public API

No browser available. Verified by code inspection:
- `web/public/widget.js:3054-3057`: `SynkoraWidget.setContext(id, context)` looks up the widget
  instance and does a **full replace** — `w._pageContext = context || null` (not a merge).
- `web/public/widget.js:3060-3063`: `SynkoraWidget.clearContext(id)` resets `_pageContext` back to
  `w._basePageContext()` (same baseline as nav-reset, not `null`).
- `web/public/widget.js:2643`: `Widget.prototype._send`'s POST body includes
  `page_context: this._pageContext || undefined` — whatever `setContext`/`clearContext`/nav-reset
  last set is what gets sent on the next message, matching every backend scenario exercised in
  Steps 1-5 above (this is the same `page_context` field the backend test requests set directly).

## Summary

| Scenario | Expected | Actual (live) |
|---|---|---|
| New `page_context` on first turn | Persisted | Persisted |
| Identical `page_context` on next turn | Deduped (`null`) | `null` (after fix) |
| Historical turn's prefix in next prompt | Present | Present (after fix) |
| No `page_context` field | `null`, no crash | `null` |
| Oversized `page_context` (>500 bytes) | Capped to `null` | `null` |
| Changed `page_context` mid-conversation | Persisted (not deduped) | Persisted, correctly attributed per-turn |
| Agent grounds answer on `page_context` (not just prompt-injected) | Agent uses the data | Verified — invoice example answered correctly with data only available via context |
| SPA navigation resets `_pageContext` | Baseline `{url, title}` | Verified via code inspection |
| `setContext`/`clearContext` public API | Full replace / reset to baseline | Verified via code inspection |

Unit tests: `docker compose exec -T api pytest tests/unit/ -q` → **4015 passed**, 0 failed.
