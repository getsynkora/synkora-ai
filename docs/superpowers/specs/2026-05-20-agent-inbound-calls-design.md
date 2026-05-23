# Agent Inbound Phone Calls — Design Spec (Phase 1: Vapi)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or superpowers:subagent-driven-development) to implement this plan task-by-task.

**Goal:** Enable agents to receive inbound phone calls via Vapi.ai and respond using the agent's full capabilities (tools, RAG, LLM) — identical to text chat but voice-delivered.

**Scope:** Phase 1 — Vapi only, BYOP (bring your own number) only. Phase 2 adds Retell, Twilio, and number provisioning.

**Architecture:** Vapi handles all real-time audio (STT, TTS, turn detection, barge-in). Our backend receives text via Vapi's webhook, runs it through the existing `chat_service`, and returns a text response. A `PhoneCall` record is created per call and linked to a `Conversation` for full transcript storage and Lens visibility.

**Tech Stack:** FastAPI, SQLAlchemy, Redis, Vapi.ai webhooks, existing `chat_service` pipeline, Next.js 15 App Router.

---

## 1. Data Models

### 1.1 `PhoneNumber` model
**File:** `api/src/models/phone_number.py`

```python
class PhoneNumber(BaseModel):
    __tablename__ = "phone_numbers"

    tenant_id: UUID          # FK → tenants
    agent_id: UUID           # FK → agents
    provider: str            # "vapi" (phase 1 only)
    phone_number: str        # E.164 format e.g. "+14155551234"
    is_provisioned: bool     # False = BYOP (phase 1 always False)
    provider_number_id: str  # Vapi's internal reference (nullable for BYOP)
    is_active: bool          # default True
```

### 1.2 `PhoneCall` model
**File:** `api/src/models/phone_call.py`

```python
class PhoneCallStatus(str, enum.Enum):
    RINGING   = "ringing"
    ACTIVE    = "active"
    COMPLETED = "completed"
    FAILED    = "failed"
    NO_ANSWER = "no_answer"

class PhoneCall(BaseModel):
    __tablename__ = "phone_calls"

    tenant_id: UUID
    agent_id: UUID
    phone_number_id: UUID    # FK → phone_numbers
    conversation_id: UUID    # FK → conversations (set on answer, nullable)
    provider: str            # "vapi"
    provider_call_id: str    # Vapi's call ID
    caller_number: str       # E.164
    status: PhoneCallStatus
    started_at: datetime
    answered_at: datetime    # nullable
    ended_at: datetime       # nullable
    duration_seconds: int    # nullable
    recording_url: str       # nullable
    cost_cents: int          # nullable
    metadata: dict           # provider-specific extras (JSON)
```

### 1.3 `PhoneProviderCredential` model
**File:** `api/src/models/phone_provider_credential.py`

Mirrors existing `VoiceApiKey` pattern. Stores Vapi API key encrypted with Fernet.

```python
class PhoneProviderCredential(BaseModel):
    __tablename__ = "phone_provider_credentials"

    tenant_id: UUID
    provider: str            # "vapi"
    credentials_encrypted: str  # Fernet-encrypted JSON {"api_key": "..."}
    is_active: bool
```

### 1.4 Agent model extension
**File:** `api/src/models/agent.py`

Add one JSON column:
```python
phone_config = Column(JSON, nullable=True, comment="Inbound call configuration")
```

Shape of `phone_config`:
```json
{
  "enabled": true,
  "provider": "vapi",
  "greeting": "Hi, how can I help you today?",
  "end_call_message": "Goodbye! Have a great day.",
  "voice_provider": "elevenlabs",
  "voice_id": "EXAVITQu4vr4xnSDxMaL",
  "language": "en",
  "max_duration_seconds": 300,
  "record_calls": false
}
```

---

## 2. Provider Abstraction

**File:** `api/src/services/voice/inbound/base_provider.py`

```python
class BaseInboundCallProvider(ABC):
    @abstractmethod
    async def handle_webhook(self, payload: dict, headers: dict, agent_slug: str, db: AsyncSession) -> dict:
        """Handle incoming webhook event. Returns response dict sent back to provider."""

    @abstractmethod
    def verify_signature(self, payload: bytes, headers: dict, secret: str) -> bool:
        """Verify webhook authenticity."""

    @abstractmethod
    def get_webhook_url(self, agent_slug: str, base_url: str) -> str:
        """Return the URL to register with the provider."""
```

**File:** `api/src/services/voice/inbound/vapi_provider.py`

Handles three Vapi event types:

| Vapi event type | Action |
|---|---|
| `call-started` | Create `PhoneCall` + `Conversation`, store in Redis, return greeting |
| `conversation-update` | Extract latest user turn, run `chat_service`, return agent text |
| `end-of-call-report` | Update `PhoneCall` (duration, recording, status), save transcript, deduct credits, clear Redis |

Vapi uses `voice_id` and `language` from `agent.phone_config` for TTS. Our backend only handles text.

**File:** `api/src/services/voice/inbound/__init__.py`

```python
def get_call_provider(provider: str) -> BaseInboundCallProvider:
    if provider == "vapi":
        return VapiProvider()
    raise ValueError(f"Unsupported provider: {provider}")
```

---

## 3. Webhook Controller

**File:** `api/src/controllers/phone_calls.py`

Router mounted at `/api/v1/phone/` in `app.py`.

### 3.1 Webhook endpoint (public — no auth, signature-verified)
```
POST /api/v1/phone/webhook/vapi
```
- Reads raw body for signature verification (`x-vapi-secret` header)
- Looks up agent by slug from payload
- Calls `VapiProvider.verify_signature()` then `VapiProvider.handle_webhook()`
- Returns provider-specific response JSON

### 3.2 Management endpoints (authenticated)
```
GET    /api/v1/phone/numbers              List phone numbers for tenant
POST   /api/v1/phone/numbers              Register BYOP number
DELETE /api/v1/phone/numbers/{number_id}  Remove number

GET    /api/v1/phone/calls                List calls (paginated, filterable by agent_id)
GET    /api/v1/phone/calls/{call_id}      Single call detail + transcript messages

POST   /api/v1/phone/credentials          Save/update Vapi API key (encrypted)
GET    /api/v1/phone/credentials          Check if credential exists (no key returned)

GET    /api/v1/agents/{slug}/phone-config   Get agent phone config
PUT    /api/v1/agents/{slug}/phone-config   Save agent phone config + register webhook with Vapi
```

---

## 4. Call Session Flow

```
Caller dials number
  │
  ▼
Vapi: POST /api/v1/phone/webhook/vapi  {type: "call-started"}
  │
  ├─ Verify x-vapi-secret signature
  ├─ Create PhoneCall (status=active)
  ├─ Create Conversation (linked to PhoneCall)
  ├─ Store Redis key: phone:call:{vapi_call_id} → {conversation_id, agent_id, tenant_id}  TTL=max_duration
  └─ Return {"assistant": {"firstMessage": "<greeting>"}}
  │
  ▼
Caller speaks
  │
  ▼
Vapi: POST /api/v1/phone/webhook/vapi  {type: "conversation-update", transcript: [...]}
  │
  ├─ Verify signature
  ├─ Look up conversation from Redis by vapi_call_id
  ├─ Extract latest user utterance from transcript
  ├─ Run chat_service.process_message(conversation_id, user_text)
  │    └─ Full agent pipeline: tools, RAG, LLM
  └─ Return {"messageResponse": {"role": "assistant", "content": "<agent_response>"}}
  │
  ▼  (turn loop repeats)
  │
  ▼
Vapi: POST /api/v1/phone/webhook/vapi  {type: "end-of-call-report"}
  │
  ├─ Update PhoneCall: status=completed, duration, recording_url, ended_at
  ├─ Save full transcript to Conversation messages (user+assistant turns)
  ├─ Deduct credits via existing billing pipeline
  ├─ Delete Redis key
  └─ Return 200 OK
```

### Redis key schema
```
phone:call:{vapi_call_id} → JSON {
  "conversation_id": "uuid",
  "agent_id": "uuid",
  "tenant_id": "uuid",
  "phone_number_id": "uuid",
  "phone_call_id": "uuid"
}
TTL: agent.phone_config.max_duration_seconds (default 300)
```

---

## 5. Agent Phone Configuration Service

**File:** `api/src/services/phone/phone_config_service.py`

Handles reading/writing `agent.phone_config`, saving/retrieving encrypted credentials, registering the webhook URL with Vapi's API when the user saves their config.

```python
async def save_phone_config(agent_id, tenant_id, config: PhoneConfigSchema, db) -> None
async def get_phone_config(agent_id, tenant_id, db) -> PhoneConfigSchema | None
async def save_vapi_credential(tenant_id, api_key: str, db) -> None
async def register_webhook_with_vapi(agent_slug: str, api_key: str) -> str:
    """Creates a Vapi assistant with our webhook URL. Returns vapi_assistant_id."""
```

---

## 6. Frontend

### 6.1 Agent Settings — Phone tab
**File:** `web/app/(dashboard)/agents/[agentName]/settings/phone/page.tsx`

Fields:
- Enable phone calls (toggle)
- Vapi API Key (password input, stored encrypted)
- Phone Number — E.164 input (BYOP)
- Greeting message (textarea)
- End call message (textarea)
- Voice ID (text input)
- Language (select: en, es, fr, de, pt, etc.)
- Max call duration (number input, seconds)
- Record calls (toggle)
- Save button → calls `PUT /api/v1/agents/{agentName}/phone-config`
- Webhook URL display (read-only): `https://your-instance.com/api/v1/phone/webhook/vapi`

### 6.2 Agent Lens — Calls tab
**File:** `web/app/(dashboard)/agents/[agentName]/lens/calls/page.tsx`

Table columns: `#`, Caller, Duration, Status (badge), Started.
Click row → opens call detail page.

**File:** `web/app/(dashboard)/agents/[agentName]/lens/calls/[callId]/page.tsx`

Shows: call metadata card (caller, duration, status, recording link if available) + full transcript rendered using existing `ChatMessage` component.

### 6.3 API client additions
**File:** `web/lib/api/phone.ts`

```typescript
getPhoneConfig(agentSlug)
savePhoneConfig(agentSlug, config)
saveVapiCredential(apiKey)
getPhoneNumbers()
addPhoneNumber(e164)
removePhoneNumber(id)
getPhoneCalls(agentId, page)
getPhoneCall(callId)
```

---

## 7. Database Migration

**File:** `api/migrations/versions/2026XXXX_0001_add_phone_calls.py`

Creates:
- `phone_numbers` table
- `phone_calls` table
- `phone_provider_credentials` table
- Adds `phone_config` JSON column to `agents` table

Indexes:
- `phone_calls(tenant_id, agent_id, started_at DESC)` — for call list queries
- `phone_calls(provider_call_id)` — for webhook lookup
- `phone_numbers(tenant_id, agent_id)` — for settings page

---

## 8. Security

- Webhook endpoint verified via `x-vapi-secret` header (HMAC, constant-time compare) — same pattern as `signature_verifier.py`
- Vapi API key stored encrypted with Fernet via `encrypt_value()` / `decrypt_value()`
- Phone numbers stored in E.164 format, treated as PII
- Call recordings (if enabled) stored as Vapi-hosted URLs — no audio stored on our servers
- Rate limit: webhook endpoint rate-limited per IP (existing middleware)
- Caller number redacted in logs if PII redaction enabled on agent

---

## 9. Out of Scope (Phase 2)

- Retell AI provider
- Twilio TwiML provider
- Platform-provisioned phone numbers (buying via Vapi/Twilio API)
- Outbound calls
- DTMF/keypad input handling
- Call queuing / hold music
- Voicemail
- Post-call AI summary generation
- Call analytics in Lens overview
