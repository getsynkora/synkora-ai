# Agent Pricing Gaps — Design Spec

**Date:** 2026-05-12
**Status:** Approved

## Problem

The agent monetisation layer has data models, a paywall check, and service methods but the purchase-to-access loop is broken in five distinct ways:

1. No HTTP endpoints exist to actually purchase agent access (credit-based or Stripe guest checkout).
2. `AgentPricingService.record_agent_usage()` is never called, so creator revenue is never recorded.
3. The Stripe `checkout.session.completed` webhook handler does not recognise agent-access sessions, so guest purchases never grant access.
4. The WebSocket chat endpoint (`/chat/ws`) skips the paywall check that the SSE endpoint (`/chat/stream`) performs.
5. Creators are blocked by their own paywall when testing their agents.
6. (Minor) `AgentPricingUpsertRequest.pricing_model` is typed `str`, so invalid values pass Pydantic validation and fail silently at the DB layer.

## Scope

Six targeted fixes. No new models or migrations. No breaking API changes.

---

## Fix 1 — Purchase endpoints

**New file:** `api/src/controllers/agents/monetization.py`

Two routers: `router` (auth-required) and `public_router` (no auth). Registered in `router_registry.py`.

### `POST /api/v1/agents/{agent_slug}/subscribe`

Auth required. Account user pays with their platform credits.

**Request body:**
```json
{
  "pricing_id": "<uuid>",
  "tier": "SESSION | DAILY | WEEKLY | MONTHLY",
  "discount_code": "<string | null>"
}
```

**Logic:**
1. Load agent by slug + tenant_id (ownership not required — subscriber != creator).
2. Call `AgentUserSubscriptionService.subscribe_account_user(agent_id, pricing_id, subscriber_tenant_id, tier, db, discount_code)`.
3. Return subscription record on success.
4. Surface `ValueError` (insufficient credits, bad tier, pricing not found) as 400.

**Response:**
```json
{ "subscription": { "id": "...", "pricing_tier": "SESSION", "expires_at": "...", "status": "ACTIVE" } }
```

### `POST /api/public/agents/{agent_slug}/checkout`

No auth. Guest Stripe checkout.

**Request body:**
```json
{
  "pricing_id": "<uuid>",
  "tier": "SESSION | DAILY | WEEKLY | MONTHLY",
  "guest_email": "user@example.com",
  "success_url": "https://...",
  "cancel_url": "https://..."
}
```

**Logic:**
1. Load agent by slug (public = `is_public` flag or no restriction needed for checkout).
2. Call `AgentUserSubscriptionService.create_stripe_checkout_session(agent_id, pricing_id, tier, guest_email, success_url, cancel_url, db)`.
3. Return the Stripe checkout URL.

**Response:**
```json
{ "checkout_url": "https://checkout.stripe.com/..." }
```

---

## Fix 2 — Stripe webhook: agent-access sessions

### Part A — Tag sessions at creation time

**File:** `api/src/services/billing/agent_user_subscription_service.py`

In `create_stripe_checkout_session()`, add `"type": "agent_access"` to the metadata dict passed to `stripe.checkout.Session.create()`. All other fields (`agent_id`, `pricing_id`, `tier`, `guest_email`, `amount_cents`) are already present.

### Part B — Handle in existing webhook dispatcher

**File:** `api/src/services/billing/stripe_service.py`

In `_handle_checkout_session_completed()`, add an `elif event_type == "agent_access"` branch:

```python
elif event_type == "agent_access":
    from src.services.billing.agent_user_subscription_service import AgentUserSubscriptionService
    raw_token, guest_email = await AgentUserSubscriptionService.fulfill_guest_subscription(
        session["id"], self.db
    )
    logger.info(f"Agent access granted for guest {guest_email}")
```

The guest token (`raw_token`) is what the frontend reads from the Stripe `success_url` redirect — it must be passed back to the frontend via a query parameter appended to `success_url`, or stored server-side and retrieved via a lookup endpoint. The simplest approach: encode it as a query param `?agent_token=<raw_token>` appended to the success URL before creating the Stripe session.

**Updated flow in `create_stripe_checkout_session()`:**
- Append `&agent_token_placeholder=1` is not needed.
- Instead: after `fulfill_guest_subscription` returns `raw_token`, the webhook handler cannot modify the redirect URL. The frontend must call a `GET /api/public/agents/checkout/token?session_id=<id>` endpoint to retrieve the token after Stripe redirects to `success_url`.

**Token retrieval endpoint** (added to `public_router` in `monetization.py`):

`GET /api/public/agents/checkout/token?session_id=<stripe_session_id>`

Looks up `AgentUserSubscription` by `stripe_customer_id` (from session) — returns the raw unhashed token only once (one-time read: stored temporarily in Redis for 10 minutes keyed by Stripe session ID).

**Revised webhook handler:** after `fulfill_guest_subscription()`, store `raw_token` in Redis: `agent_token:{stripe_session_id}` with 10-minute TTL.

---

## Fix 3 — Revenue recording in billing Celery task

**File:** `api/src/tasks/billing_tasks.py`

In `deduct_credits_async()`, after a successful `transaction` is returned from `credit_service.deduct_credits_idempotent()`, add:

```python
if transaction:
    # Record creator revenue for paid agents
    try:
        from src.services.billing.agent_pricing_service import AgentPricingService
        await AgentPricingService.record_agent_usage(
            agent_id=agent_uuid,
            transaction_id=transaction.id,
            credits_used=abs(transaction.amount),
            db=db,
        )
    except Exception as rev_err:
        logger.warning(f"Agent revenue recording failed (non-fatal): {rev_err}")
```

The call is wrapped in try/except so a revenue recording failure never blocks credit deduction.

`record_agent_usage` already returns `None` for free agents (line ~143 in the service), so no guard is needed here.

---

## Fix 4 — WebSocket paywall

**File:** `api/src/controllers/agents/chat.py`

In `_ws_chat_pipeline()`, after the billing validation block and before the `stream_agent_response` call, insert a paywall block that mirrors the SSE endpoint paywall (lines 337–403 of `chat_stream`):

- Loads `AgentPricing` for `_ws_agent`.
- Calls `AgentUserSubscriptionService.check_access()`.
- Tracks trial messages in Redis.
- On paywall hit: yields `{"type": "paywall", "data": {...}}` and `return`.

The guest token for WebSocket is read from the same `agent_access_token` cookie (passed via HTTP upgrade headers).

---

## Fix 5 — Creator bypass

**File:** `api/src/controllers/agents/chat.py`

In **both** the SSE paywall block (`chat_stream`) and the new WS paywall block (`_ws_chat_pipeline`), before calling `check_access()`, add:

```python
# Creator always has access to their own agent
if tenant_id == _preflight_agent.tenant_id:
    _has_access = True
else:
    _has_access = await AgentUserSubscriptionService.check_access(...)
```

---

## Fix 6 — Enum validation for pricing_model

**File:** `api/src/controllers/billing.py`

Change `AgentPricingUpsertRequest`:
```python
# Before
pricing_model: str = "FREE"

# After
from src.models.agent_pricing import PricingModel
pricing_model: PricingModel = PricingModel.FREE
```

Pydantic will now reject unknown values with a 422 before the DB is touched.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| `subscribe`: insufficient credits | 400 with `ValueError` message from `CreditService` |
| `subscribe`: tier not configured (e.g., `DAILY` with no `daily_credits`) | 400 |
| `checkout`: Stripe not configured | 503 with `"Stripe is not configured"` |
| Revenue recording failure in Celery task | Logged as warning, non-fatal |
| Guest token Redis key expired before retrieval | 404 on token endpoint; user must retry checkout |
| Creator accessing own agent | Access granted unconditionally (no trial decrement) |

---

## Testing

- Unit tests for the new `monetization.py` controller (mock service layer).
- Integration test: extend `test_agent_monetization_integration.py` with:
  - `test_subscribe_with_credits` — sets up pricing, grants credits to subscriber, calls subscribe endpoint, verifies active subscription and trial-bypass in chat.
  - `test_checkout_endpoint_returns_url` — mocks Stripe, verifies URL returned.
  - `test_ws_paywall_blocks_unauthenticated` — verifies WS chat returns `{"type":"paywall"}` when no subscription.
  - `test_creator_bypasses_paywall` — creator can chat without subscription.
- Unit test: `billing_tasks.py` — verify `record_agent_usage` called when agent is paid.

---

## Files Changed

| File | Change |
|------|--------|
| `api/src/controllers/agents/monetization.py` | **New** — subscribe + guest checkout + token retrieval endpoints |
| `api/src/router_registry.py` | Register new `monetization` routers |
| `api/src/services/billing/agent_user_subscription_service.py` | Add `"type": "agent_access"` to Stripe metadata |
| `api/src/services/billing/stripe_service.py` | Handle `agent_access` in `_handle_checkout_session_completed` + store token in Redis |
| `api/src/tasks/billing_tasks.py` | Call `record_agent_usage` after successful deduction |
| `api/src/controllers/agents/chat.py` | Add WS paywall + creator bypass in both SSE and WS paths |
| `api/src/controllers/billing.py` | Fix `pricing_model` type to `PricingModel` enum |
| `api/tests/integration/test_agent_monetization_integration.py` | New integration test cases |
