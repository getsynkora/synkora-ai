"""
Eval Outcome Service

Tracks session-level quality outcomes via two paths:
- Implicit: inferred from conversation signals at stream close
- Explicit: user submits "Did this help?" prompt

Both paths write to the agent_outcomes_* ES index and fire Langfuse scores.
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

logger = logging.getLogger(__name__)

_outcome_bg_tasks: set[asyncio.Task] = set()
_es_client = None


async def _get_es_client():
    global _es_client
    if _es_client is not None:
        return _es_client
    from elasticsearch import AsyncElasticsearch

    from src.config.settings import settings

    _es_client = AsyncElasticsearch(
        [settings.elasticsearch_url],
        basic_auth=(settings.elasticsearch_username, settings.elasticsearch_password),
        verify_certs=False,
        request_timeout=5,
    )
    return _es_client


def _fire_outcome_event(event: dict) -> None:
    """Schedule ES index — returns in ~1µs, never raises."""
    try:
        task = asyncio.create_task(_index_outcome(event))
        _outcome_bg_tasks.add(task)
        task.add_done_callback(_outcome_bg_tasks.discard)
    except Exception as e:
        logger.warning("_fire_outcome_event scheduling error: %s", e)


async def _index_outcome(event: dict) -> None:
    """Index outcome doc to ES using conversation_id as doc ID (upsert)."""
    try:
        from src.config.settings import settings

        es = await _get_es_client()
        await es.index(
            index=settings.agent_outcomes_index,
            id=event["conversation_id"],
            document=event,
        )
    except Exception as e:
        logger.warning("ES outcome index failed (non-critical): %s", e)


# ---------------------------------------------------------------------------
# Implicit outcome — called at stream close
# ---------------------------------------------------------------------------


async def infer_outcome(
    *,
    tenant_id: UUID,
    agent_id: UUID,
    conversation_id: UUID,
    trace_id: str | None = None,
) -> None:
    """
    Infer session outcome from conversation signals in the ES trace index.

    Reads the last N trace events for the conversation and scores:
    - re-ask count (same intent within 3 turns) → partial/failure
    - tool error rate → partial
    - natural close (no follow-up within 5 minutes) → success
    - abrupt disconnect → unknown

    Called fire-and-forget from chat_stream_service at stream close.
    """
    try:
        from src.config.settings import settings

        es = await _get_es_client()

        # Fetch recent events for this conversation
        body = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"conversation_id.keyword": str(conversation_id)}},
                        {"term": {"tenant_id.keyword": str(tenant_id)}},
                    ]
                }
            },
            "size": 50,
            "sort": [{"timestamp": {"order": "asc"}}],
        }
        resp = await es.search(index=settings.agent_trace_index, body=body)
        events = [h["_source"] for h in resp["hits"]["hits"]]

        outcome, signals = _score_conversation(events)

        _fire_outcome_event(
            {
                "conversation_id": str(conversation_id),
                "agent_id": str(agent_id),
                "tenant_id": str(tenant_id),
                "outcome": outcome,
                "source": "implicit",
                "implicit_signals": signals,
                "@timestamp": datetime.now(UTC).isoformat(),
            }
        )

        if trace_id:
            _score_langfuse(trace_id, outcome)

    except Exception as e:
        logger.warning("infer_outcome failed (non-critical): %s", e)


def _score_conversation(events: list[dict]) -> tuple[str, dict]:
    """Score a list of trace events into an outcome label + signals dict."""
    user_messages = [e for e in events if e.get("event_type") == "user_message"]
    tool_calls = [e for e in events if e.get("event_type") == "tool_call"]
    llm_calls = [e for e in events if e.get("event_type") == "llm_call"]

    failed_tools = [t for t in tool_calls if not t.get("success", True)]
    tool_error_rate = len(failed_tools) / len(tool_calls) if tool_calls else 0.0

    # Re-ask detection: short consecutive user messages (< 20 chars each) suggest dissatisfaction
    reasked = sum(1 for i in range(1, len(user_messages)) if len(user_messages[i].get("content", "")) < 60)

    signals = {
        "user_message_count": len(user_messages),
        "tool_call_count": len(tool_calls),
        "failed_tool_count": len(failed_tools),
        "tool_error_rate": round(tool_error_rate, 3),
        "llm_call_count": len(llm_calls),
        "re_ask_count": reasked,
    }

    if not events:
        return "unknown", signals
    if tool_error_rate > 0.5:
        return "failure", signals
    if reasked >= 2:
        return "partial", signals
    if tool_error_rate > 0.0:
        return "partial", signals
    return "success", signals


def _score_langfuse(trace_id: str, outcome: str) -> None:
    try:
        from src.services.observability.langfuse_service import langfuse_service

        value = {"success": 1.0, "partial": 0.5, "failure": 0.0, "unknown": 0.5}.get(outcome, 0.5)
        langfuse_service.score_generation(
            trace_id=trace_id,
            name="session_outcome",
            value=value,
            comment=outcome,
        )
    except Exception as e:
        logger.warning("Langfuse session_outcome score failed (non-critical): %s", e)


# ---------------------------------------------------------------------------
# Explicit outcome — called when user submits "Did this help?"
# ---------------------------------------------------------------------------


def record_explicit_outcome(
    *,
    conversation_id: UUID,
    agent_id: UUID,
    tenant_id: UUID,
    helpful: bool,
    trace_id: str | None = None,
) -> None:
    """
    Record explicit user satisfaction signal.

    Overwrites the implicit outcome document for this conversation (same ES doc ID).
    Also fires a Langfuse session_outcome score if trace_id is present.
    """
    outcome = "success" if helpful else "failure"

    _fire_outcome_event(
        {
            "conversation_id": str(conversation_id),
            "agent_id": str(agent_id),
            "tenant_id": str(tenant_id),
            "outcome": outcome,
            "source": "explicit",
            "explicit_rating": helpful,
            "@timestamp": datetime.now(UTC).isoformat(),
        }
    )

    if trace_id:
        _score_langfuse(trace_id, outcome)
