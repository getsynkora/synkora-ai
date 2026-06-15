# Chat HITL Approval + Human Handoff Design

## Overview

Two related features that extend agent interactions beyond fully-automated responses:

1. **Chat HITL Approval** — when an agent is about to execute a tool in a live chat session (widget or Flutter app), it can pause and show the user an inline approval card. The tool only executes if the user approves.

2. **Human Handoff** — when a user requests a human agent, the conversation transitions to a live support mode. The agent owner (or any tenant member) replies directly from the Synkora dashboard. Optionally, an external notification is sent via existing integration tools (Slack, WhatsApp, email, Zendesk ticket, etc.).

---

## Scope

### In scope
- HITL approval gate for chat sessions (widget + Flutter)
- SSE event `approval_required` delivered to the client
- Inline approval card UI in the web widget and Flutter SDK
- Human handoff triggered by the user via "talk to a human" or equivalent
- `handoff_to_human` agent tool: generates AI summary, marks conversation, emits SSE event
- Operator reply: tenant member replies to a handed-off conversation from the Synkora dashboard
- Operator reply delivered to the end user via existing WebSocket/SSE infrastructure
- Handoff resolve: operator ends handoff, AI resumes
- Optional external notification via existing integration tools (no new OAuth config)

### Out of scope
- Autonomous-mode HITL (already implemented)
- Role-based inbox routing (any tenant member can reply for now)
- Bidirectional relay with external ticketing platforms (Zendesk, Intercom) — the external tool creates the ticket; Synkora is the reply channel
- Push notifications to Flutter (FCM) — separate task

---

## Architecture

### Trigger

The user says "talk to a human", "connect me to support", or equivalent. The agent detects this intent and calls the `handoff_to_human` tool (Option 1 from design discussion). The system prompt instruction guarantees the agent calls the tool for these phrases.

### HITL Gate in Chat

The existing `_check_approval_gate()` in `adk_tools.py` runs only in autonomous mode today. For chat sessions, a separate lightweight gate is needed:

- Per-agent config controls which tools require chat approval (same `tool_category` system already used for autonomous HITL)
- When a gated tool is called during a live chat: pause execution, persist an `AgentApprovalRequest` (reusing existing model), emit SSE event `approval_required`
- Frontend renders an inline approval card; user approves/rejects
- On approval: a one-time Redis token is stored; the chat message is re-submitted with `approval_id`; the gate finds the token and allows execution
- On rejection: agent receives a rejection message and responds to the user

### Human Handoff Flow

```
User: "I need to speak to a human"
  → Agent calls handoff_to_human(reason="refund request")
    → Generates AI summary of conversation
    → Sets conversation.handoff_status = "active"
    → Emits SSE handoff_initiated { summary }
    → Optionally calls existing integration tools (send_slack_message, create_zendesk_ticket, etc.)
  → Widget/Flutter shows "Connected to a support agent"
  → AI stops responding to new messages in this conversation

Operator opens Synkora dashboard → Conversations filtered by handoff_status=active
  → Reads full chat history + AI summary
  → Types reply → POST /api/v1/conversations/{id}/handoff/reply
    → Message saved as role=operator
    → Delivered to end user via existing WebSocket broadcast

Operator clicks Resolve → POST /api/v1/conversations/{id}/handoff/resolve
  → conversation.handoff_status = "none"
  → AI resumes handling messages
  → Widget/Flutter shows "Support session ended"
```

---

## Data Model

### `Conversation` model changes

Add three fields:

```python
handoff_status: str  # "none" | "active" | "resolved"  (default: "none")
handoff_at: datetime | None
handoff_summary: str | None  # AI-generated summary stored at handoff time
```

No new table needed. All message history is already in the `Message` table. Operator replies are stored as `role="operator"` messages.

### `Message.role` enum extension

Add `"operator"` as a valid role value (alongside `"user"`, `"assistant"`, `"system"`).

### `AgentApprovalRequest` — no changes

Reused as-is for chat HITL. The `notification_channel` field will be `"chat"` for chat-session approvals.

---

## Backend

### New endpoints

```
POST   /api/v1/conversations/{id}/handoff/reply
       Body: { message: str }
       Auth: tenant member (Bearer token)
       Effect: saves Message(role="operator"), broadcasts via WebSocket

POST   /api/v1/conversations/{id}/handoff/resolve
       Auth: tenant member
       Effect: handoff_status="resolved", broadcasts SSE handoff_resolved

GET    /api/v1/conversations?handoff_status=active
       Already exists — just add handoff_status filter to query
```

### `handoff_to_human` tool

Registered in `adk_tools.py` like any other tool. Parameters: `reason: str` (why handoff was requested).

Implementation:
1. Load conversation from `shared_state["conversation_id"]`
2. Call LLM to generate 2-3 sentence summary of the conversation
3. Set `conversation.handoff_status = "active"`, `conversation.handoff_at = now()`, `conversation.handoff_summary = summary`
4. Emit SSE event `handoff_initiated` with `{ summary }` via the streaming response
5. Return a string for the agent to relay to the user: "I've connected you with a support agent. They'll be with you shortly."

The tool does NOT call external integrations itself. If the agent has Slack/Zendesk tools configured, the agent can call those separately as part of the same turn (the system prompt can instruct this).

### Chat HITL gate

New function `_check_chat_approval_gate()` in `adk_tools.py`:
- Checks `shared_state.get("session_type") == "chat"` (set by `chat_stream_service.py`)
- If tool requires approval per agent config: creates `AgentApprovalRequest(notification_channel="chat")`, emits SSE `approval_required`, raises `ToolPausedException`
- `chat_stream_service.py` catches `ToolPausedException`, sends `approval_required` SSE event, ends stream
- On next message with `approval_id`: validate one-time Redis token, re-run tool

### SSE events (new)

```
event: approval_required
data: { approval_id, tool_name, tool_args, expires_at }

event: handoff_initiated
data: { summary }

event: handoff_resolved
data: {}
```

---

## Frontend

### Web widget (`widget.js`)

- On `approval_required` event: render inline approval card (Approve / Reject / Feedback buttons)
- On `handoff_initiated` event: replace input box with "Connected to support — waiting for agent" banner; disable user input while handoff is active
- On `handoff_resolved` event: restore normal chat UI, show "Support session ended"
- Operator messages (`role="operator"`) rendered with "Support" label instead of agent name

### Flutter SDK (`synkora_chat`)

- Handle `approval_required` SSE event: show `ApprovalCard` widget inline in chat list
- Handle `handoff_initiated`: show handoff state banner, disable input
- Handle `handoff_resolved`: restore normal chat
- Operator messages: render with distinct "Support" label

### Dashboard (Synkora web app)

- Conversation list: add filter tab "Handoffs" (`handoff_status=active`)
- Conversation view: when `handoff_status=active`, show reply box (bypasses AI) and "Resolve" button
- Reply box sends to `POST /api/v1/conversations/{id}/handoff/reply`
- Resolve button sends to `POST /api/v1/conversations/{id}/handoff/resolve`
- Show AI summary at the top of the conversation when in handoff mode

---

## Error Handling

- If `handoff_to_human` is called but conversation is already in handoff: return "A support agent is already connected."
- If HITL approval expires (TTL elapsed): `AgentApprovalRequest.status = "expired"`, agent resumes with "Action was not approved in time."
- If operator reply fails WebSocket delivery: message is still persisted; user will see it on next poll/reconnect
- Handoff with no operator response: no auto-timeout for now (keep it simple)

---

## Testing

- Unit: `handoff_to_human` tool sets correct conversation fields and emits SSE event
- Unit: `_check_chat_approval_gate()` creates approval request and raises correct exception
- Unit: `/handoff/reply` endpoint saves operator message with correct role
- Integration: full handoff flow — user triggers → operator replies → user receives message
- Integration: HITL gate — tool call paused → user approves → tool executes → response delivered
- E2E: widget sends "talk to a human" → handoff banner appears → operator replies from dashboard → message appears in widget
