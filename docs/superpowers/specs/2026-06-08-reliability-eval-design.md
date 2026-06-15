# Reliability & Eval Pipeline Design

**Date:** 2026-06-08
**Status:** Approved

## Overview

Wire end-to-end reliability measurement into Synkora: per-message user feedback across all channels, session outcome tracking (implicit + explicit), on-demand LLM-as-judge eval with dataset management, and a prompt regression test suite. All signals feed into both Langfuse (tracing/scoring) and Agent Lens (dashboard).

## Goals

- Measure factuality, consistency, and user satisfaction at scale
- Surface quality metrics alongside cost/latency in Agent Lens
- Enable non-technical users to build eval datasets through the UI
- Enable CI regression gates on prompt changes via pytest
- Zero latency impact on the chat hot path

## Non-Goals

- Real-time hallucination detection (deferred — can be added to on-demand eval later)
- Automatic scheduled eval runs (manual / CI-triggered only for now)
- RAG faithfulness scoring in the hot path (on-demand only)

---

## Architecture: Option A — Dedicated `eval` service layer

One new module `api/src/services/eval/` owns all reliability concerns. Every channel calls the same service functions. Both Langfuse and Elasticsearch are written to from within the service — never scattered across controllers.

**Why not ES-only or PG-only for storage:**
All eval/reliability data lives exclusively in Elasticsearch. No new PostgreSQL tables. Rationale:
- Eval data (feedback, outcomes, results) is observational and append-only — ES is the right fit
- Consistent with the existing `agent_trace_service.py` fire-and-forget pattern
- No cross-store dependency at eval run time (read cases from ES, write results to ES)
- Data loss risk is acceptable — eval data is not sensitive or difficult to recreate

---

## Module Structure

```
api/src/services/eval/
  __init__.py
  feedback_service.py     # per-message thumbs up/down
  outcome_service.py      # session outcome (implicit + explicit)
  dataset_service.py      # eval dataset and case CRUD
  judge_service.py        # on-demand LLM-as-judge runner
```

```
api/tests/eval/
  conftest.py             # agent fixture, judge helper
  datasets/
    *.yaml                # golden cases per agent type
  test_regression.py      # parametrised over all YAML files, marked @pytest.mark.eval
```

---

## Elasticsearch Indices

All indices use per-tenant prefix: `{tenant_id}_{index_name}`.

| Index | Documents | Written by |
|---|---|---|
| `agent_trace_*` (existing) | llm_call, tool_call, user_message, assistant_message, tool_pruning | agent_trace_service |
| `agent_feedback_*` | MessageFeedback events | feedback_service |
| `agent_outcomes_*` | SessionOutcome documents | outcome_service |
| `agent_eval_datasets_*` | EvalDataset + EvalCase documents | dataset_service |
| `agent_eval_runs_*` | EvalRun + EvalResult documents | judge_service |

---

## Service Logic

### `feedback_service.py`

Single entry point: `record_feedback(message_id, agent_id, tenant_id, channel, rating, comment, trace_id)`.

1. Fires a `MessageFeedback` document to `agent_feedback_*` index (fire-and-forget)
2. Calls `langfuse_service.score_generation(trace_id, "user_feedback", 1.0 or 0.0, comment)` if `trace_id` present
3. Document shape: `{ message_id, agent_id, tenant_id, channel, rating (1/-1), comment, trace_id, @timestamp }`

Upsert semantics: if the same `message_id` is rated again, the document is overwritten (ES `doc_as_upsert`).

### `outcome_service.py`

Two paths, both write to `agent_outcomes_*`:

**Implicit** — called at stream close from `chat_stream_service.py`. Reads last N ES trace events for the conversation and scores:
- Re-ask count (same intent within 3 turns) → partial/failure
- Tool error rate → partial
- Natural close (no follow-up within 5 minutes of final assistant message) → success
- Abrupt disconnect → unknown

Produces `{ conversation_id, agent_id, tenant_id, outcome, source: "implicit", implicit_signals: {...}, @timestamp }`.

**Explicit** — called when user submits "Did this help?" prompt. Stores `explicit_rating` bool, sets `outcome` to success/failure, fires Langfuse score `"session_outcome"` (1.0/0.0). Overwrites the implicit document for the same `conversation_id`.

Agent-level config flag `show_satisfaction_prompt: bool` (default `false`). When `true`, the SSE stream emits a `{ type: "satisfaction_prompt" }` event after the final assistant message.

### `dataset_service.py`

CRUD for `EvalDataset` and `EvalCase` documents in ES.

- Dataset document: `{ dataset_id, agent_id, tenant_id, name, description, case_count, @timestamp }`
- Case document: `{ case_id, dataset_id, agent_id, tenant_id, input, expected_criteria, tags, @timestamp }`
- `list_cases(dataset_id)` — ES term query, returns all cases for a dataset
- `delete_dataset(dataset_id)` — deletes dataset doc + all case docs (ES delete by query)

### `judge_service.py`

On-demand runner triggered by "Run Eval" button:

1. Load all `EvalCase` docs for the dataset from ES
2. For each case, call `chat_stream_service` in non-streaming mode to get actual response
3. Call LLM-as-judge via `llm_client.py` with structured prompt:
   - Input: user message
   - Expected criteria: rubric text or JSON from the case
   - Actual output: agent response
   - Returns: `{ score (0–1), reasoning, passed (bool) }`
4. Write `EvalResult` doc per case to `agent_eval_runs_*`
5. Write `EvalRun` summary doc: `{ run_id, dataset_id, agent_id, tenant_id, status, total_cases, passed, failed, pass_rate, avg_score, avg_latency_ms, ran_at }`
6. Push run to Langfuse as a dataset run (if Langfuse configured) — enables Langfuse's built-in eval comparison UI

For RAG agents, judge prompt additionally evaluates faithfulness: retrieved sources are included in the prompt and the judge checks whether the answer is grounded in them.

Run status lifecycle: `pending → running → completed | failed`.

---

## API Surface

All endpoints respect tenant isolation via `get_current_tenant_id` dependency.

```
# Per-message feedback
POST /api/v1/agents/{agent_slug}/feedback
  body: { message_id, channel, rating (1/-1), comment?, trace_id? }

# Explicit session outcome
POST /api/v1/agents/{agent_slug}/outcome
  body: { conversation_id, helpful (bool) }

# Eval dataset management
GET    /api/v1/agents/{agent_slug}/eval/datasets
POST   /api/v1/agents/{agent_slug}/eval/datasets
GET    /api/v1/agents/{agent_slug}/eval/datasets/{dataset_id}
PUT    /api/v1/agents/{agent_slug}/eval/datasets/{dataset_id}
DELETE /api/v1/agents/{agent_slug}/eval/datasets/{dataset_id}
POST   /api/v1/agents/{agent_slug}/eval/datasets/{dataset_id}/cases
DELETE /api/v1/agents/{agent_slug}/eval/datasets/{dataset_id}/cases/{case_id}

# On-demand eval run
POST /api/v1/agents/{agent_slug}/eval/datasets/{dataset_id}/run
GET  /api/v1/agents/{agent_slug}/eval/runs
GET  /api/v1/agents/{agent_slug}/eval/runs/{run_id}

# Agent Lens quality endpoints (new)
GET /api/v1/agents/{agent_slug}/lens/quality
GET /api/v1/agents/{agent_slug}/lens/eval-history
```

---

## Channel Wiring

| Channel | Feedback trigger | Wired in |
|---|---|---|
| Console chat | Thumbs up/down button on assistant message | `controllers/agents/chat.py` new endpoint |
| Public widget | Same button, anonymous session token | Widget auth middleware already handles this |
| Slack | User reacts with 👍/👎 to bot message (reaction event) | `services/slack/slack_message_handler.py` |
| WhatsApp | User replies "👍" or "👎" within 60s of assistant message | `services/whatsapp/whatsapp_webhook_service.py` |
| Teams | Same pattern as WhatsApp | `services/teams/teams_webhook_service.py` |

Implicit outcome inference: called from `chat_stream_service.py` at stream close.

---

## Agent Lens Additions

### New `lens/quality` response

```json
{
  "period_start": "...", "period_end": "...",
  "satisfaction": {
    "total_rated": 412,
    "thumbs_up": 334,
    "thumbs_down": 78,
    "satisfaction_rate": 0.811,
    "by_channel": { "widget": 0.84, "slack": 0.76, "whatsapp": 0.79 }
  },
  "outcomes": {
    "total_sessions": 891,
    "success": 612, "partial": 156, "failure": 89, "unknown": 34,
    "success_rate": 0.687,
    "explicit_rate": 0.823,
    "implicit_rate": 0.634
  },
  "top_disliked_tools": [
    { "tool_name": "web_search", "dislike_rate": 0.21 }
  ]
}
```

### New `lens/eval-history` response

```json
{
  "runs": [
    {
      "run_id": "...", "dataset_name": "Core QA",
      "ran_at": "...", "status": "completed",
      "total_cases": 24, "passed": 21, "failed": 3,
      "pass_rate": 0.875, "avg_score": 0.91, "avg_latency_ms": 1240
    }
  ]
}
```

### Existing schema additions

- `LensStatCard` gains: `satisfaction_rate: float`, `session_success_rate: float`, `latest_eval_pass_rate: float | None`
- `AlertCreateBody.metric` enum extended with: `"satisfaction_rate"`, `"session_success_rate"`

---

## Frontend (web/)

Two new tabs in the Agent Lens panel:

**Quality tab:**
- Satisfaction rate over time (line chart), range selector (24h/7d/30d/90d)
- Outcome breakdown donut (success/partial/failure/unknown)
- Per-channel satisfaction breakdown table
- Top disliked responses list (most-downvoted assistant messages, linkable to session timeline)

**Eval tab:**
- Dataset list with case counts, create/edit/delete
- Case editor (input + expected criteria textarea)
- "Run Eval" button → shows progress, then results
- Run history table: dataset name, ran at, pass rate, avg score, drill-down to per-case results

---

## pytest Regression Suite

```yaml
# api/tests/eval/datasets/general_qa.yaml
dataset: General QA
cases:
  - input: "What is the capital of France?"
    criteria: "Answer must be Paris"
    tags: [factual, geography]
  - input: "Summarise the uploaded document in 3 bullet points"
    criteria: "Response must contain exactly 3 bullet points and not introduce facts not in the document"
    tags: [rag, faithfulness]
```

```python
# api/tests/eval/test_regression.py
@pytest.mark.eval
@pytest.mark.parametrize("case", load_all_cases())
async def test_eval_case(agent_fixture, judge, case):
    response = await agent_fixture.chat(case["input"])
    result = await judge.score(case["input"], case["criteria"], response)
    assert result.passed, f"Failed: {result.reasoning}"
```

Running `pytest -m eval` pushes results to Langfuse as a named dataset run when `LANGFUSE_*` env vars are set. Designed to run in CI on every prompt change.

---

## Settings additions

```python
# api/src/config/settings.py additions
agent_feedback_index: str = "agent_feedback"
agent_outcomes_index: str = "agent_outcomes"
agent_eval_datasets_index: str = "agent_eval_datasets"
agent_eval_runs_index: str = "agent_eval_runs"
eval_judge_model: str = "gpt-4o-mini"   # model used for LLM-as-judge; configurable
eval_judge_max_tokens: int = 512
```

---

## Sequence: Per-message feedback flow

```
User clicks thumbs up
  → POST /agents/{slug}/feedback
  → feedback_service.record_feedback()
    → ES fire-and-forget (agent_feedback_*)
    → langfuse_service.score_generation() if trace_id present
  → 200 OK (< 5ms, no blocking)
```

## Sequence: On-demand eval run

```
User clicks "Run Eval"
  → POST /eval/datasets/{id}/run
  → judge_service.run_dataset() (Celery task)
    → load EvalCases from ES
    → for each case:
        → chat_stream_service.chat_non_streaming()
        → llm_client.complete() [judge prompt]
        → write EvalResult to ES
    → write EvalRun summary to ES
    → push to Langfuse dataset run (if configured)
  → GET /eval/runs/{run_id} polls for completion
```
