"""
Agent Trace Service

Fire-and-forget write path: index every session event (user_message, llm_call,
tool_call, assistant_message) into Elasticsearch with zero latency impact.

Read path: ES aggregation queries backing all Agent Lens API endpoints.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

logger = logging.getLogger(__name__)

# Strong refs prevent GC before background tasks complete
_trace_bg_tasks: set[asyncio.Task] = set()

# Singleton ES client (lazy-initialised)
_es_client = None


def reset_trace_client() -> None:
    """Reset the ES client singleton so the next call creates a fresh one.

    Must be called before each asyncio.run() in a Celery worker to prevent
    'Event loop is closed' errors from reusing a client bound to a prior loop.
    """
    global _es_client
    _es_client = None


async def flush_trace_tasks() -> None:
    """Await all pending fire-and-forget trace tasks.

    Call this at the end of an asyncio.run() coroutine to ensure trace events
    are actually written before the event loop closes.
    """
    if _trace_bg_tasks:
        await asyncio.gather(*list(_trace_bg_tasks), return_exceptions=True)


# Max bytes stored for tool args/result on success path
_PREVIEW_MAX_BYTES = 500


# ---------------------------------------------------------------------------
# ES client
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Internal fire-and-forget plumbing
# ---------------------------------------------------------------------------


def _fire_index_event(event: dict) -> None:
    """Schedule ES index — returns in ~1µs, never raises, never blocks the stream."""
    try:
        task = asyncio.create_task(_index_event(event))
        _trace_bg_tasks.add(task)
        task.add_done_callback(_trace_bg_tasks.discard)
    except Exception as e:
        logger.warning("_fire_index_event scheduling error: %s", e)


async def _index_event(event: dict) -> None:
    """Silently discards on ES error — observability loss is acceptable."""
    try:
        from src.config.settings import settings

        es = await _get_es_client()
        await es.index(index=settings.agent_trace_index, document=event)
    except Exception as e:
        logger.warning("ES index event failed (non-critical): %s", e)


async def _safe_es_search(es, index: str, body: dict) -> dict:
    """Wrap es.search; raises HTTP 503 when Elasticsearch is unavailable."""
    from elasticsearch import ApiError
    from elasticsearch import ConnectionError as ESConnectionError
    from fastapi import HTTPException

    try:
        return await es.search(index=index, body=body)
    except (ApiError, ESConnectionError, Exception) as exc:
        logger.warning("Elasticsearch search failed: %s", exc)
        raise HTTPException(status_code=503, detail="Analytics service temporarily unavailable (Elasticsearch)")


def _truncate_to_preview(value) -> str | None:
    """Return a valid JSON string preview capped at _PREVIEW_MAX_BYTES chars."""
    if value is None:
        return None
    try:
        encoded = json.dumps(value, default=str)
        if len(encoded) <= _PREVIEW_MAX_BYTES:
            return encoded
        # Wrap in envelope so the result is always valid parseable JSON
        return json.dumps(
            {"_truncated": True, "preview": encoded[:_PREVIEW_MAX_BYTES], "total_chars": len(encoded)},
            default=str,
        )
    except Exception:
        return json.dumps({"_error": str(value)[:_PREVIEW_MAX_BYTES]})


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Public fire functions — called from hook points in the streaming path
# ---------------------------------------------------------------------------


def fire_user_message(
    *,
    tenant_id: UUID,
    agent_id: UUID | None,
    conversation_id: UUID | None,
    message_id: UUID | None,
    content: str,
    conversation_name: str,
    conversation_status: str,
    sequence: int,
) -> None:
    """Fire-and-forget: index a user_message event."""
    from src.config.settings import settings

    if not settings.agent_trace_enabled:
        return

    _fire_index_event(
        {
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id) if agent_id else None,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "message_id": str(message_id) if message_id else None,
            "event_type": "user_message",
            "sequence": sequence,
            "timestamp": _now_iso(),
            "content": content[:3000],
            "conversation_name": conversation_name,
            "conversation_status": conversation_status,
        }
    )


def fire_llm_call(
    *,
    tenant_id: UUID,
    agent_id: UUID | None,
    conversation_id: UUID | None,
    model: str,
    call_index: int,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: int,
    response_preview: str | None,
    status: str,
    error: str | None,
    sequence: int,
    system_prompt: str | None = None,
    messages_json: str | None = None,
    tools_json: str | None = None,
    # Prompt cache metrics (Anthropic and compatible providers)
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    # Context window pressure (0–100 pct)
    context_utilization_pct: float | None = None,
) -> None:
    """Fire-and-forget: index an llm_call event."""
    from src.config.settings import settings

    if not settings.agent_trace_enabled:
        return

    _fire_index_event(
        {
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id) if agent_id else None,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "event_type": "llm_call",
            "sequence": sequence,
            "timestamp": _now_iso(),
            "model": model,
            "call_index": call_index,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "latency_ms": latency_ms,
            "response_preview": (response_preview or "")[:3000],
            "llm_status": status,
            "llm_error": error,
            # LLM input inspection — stored as text fields to avoid ES mapping explosion
            "system_prompt": (system_prompt or "")[:2000] if system_prompt else None,
            "messages_json": messages_json[:16000] if messages_json else None,
            "tools_json": tools_json[:32000] if tools_json else None,
            # Prompt cache
            "cache_read_tokens": cache_read_tokens or 0,
            "cache_creation_tokens": cache_creation_tokens or 0,
            # Context pressure (percent of model context window used)
            "context_utilization_pct": context_utilization_pct,
        }
    )


def fire_tool_pruning(
    *,
    tenant_id: UUID,
    agent_id: UUID | None,
    conversation_id: UUID | None,
    sequence: int,
    turn_index: int,
    tool_results_count: int,
    tool_results_pruned: int,
    data_bearing_pruned: int,
    chars_saved: int,
    estimated_tokens_saved: int,
    original_chars: int,
    pruned_chars: int,
) -> None:
    """Fire-and-forget: index a tool_pruning event."""
    from src.config.settings import settings

    if not settings.agent_trace_enabled:
        return

    _fire_index_event(
        {
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id) if agent_id else None,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "event_type": "tool_pruning",
            "sequence": sequence,
            "timestamp": _now_iso(),
            "turn_index": turn_index,
            "tool_results_count": tool_results_count,
            "tool_results_pruned": tool_results_pruned,
            "data_bearing_pruned": data_bearing_pruned,
            "chars_saved": chars_saved,
            "estimated_tokens_saved": estimated_tokens_saved,
            "original_chars": original_chars,
            "pruned_chars": pruned_chars,
        }
    )


def fire_tool_call(
    *,
    tenant_id: UUID,
    agent_id: UUID | None,
    conversation_id: UUID | None,
    tool_name: str,
    success: bool,
    duration_ms: int,
    retry_count: int,
    args: dict | None,
    result,
    error_message: str | None,
    sequence: int,
) -> None:
    """Fire-and-forget: index a tool_call event.

    Failed calls store full args + result for debugging.
    Successful calls store 500-char previews only.
    """
    from src.config.settings import settings

    if not settings.agent_trace_enabled:
        return

    # args: serialised as JSON text (avoids ES flattened/object mapping issues)
    if args is not None:
        try:
            stored_args = json.dumps(args, default=str)[:2048]
        except Exception:
            stored_args = str(args)[:2048]
    else:
        stored_args = None

    # result: stored as a JSON string (text field) to avoid ES mapping explosion.
    # Always produce *valid* JSON — raw [:N] slicing breaks mid-string and causes
    # JSON.parse to fail on the frontend, showing a raw unformatted blob instead.
    _FAILED_MAX = 8000  # failed calls need more context for debugging
    _SUCCESS_MAX = 2000
    if result is not None:
        try:
            encoded = json.dumps(result, default=str)
            limit = _FAILED_MAX if not success else _SUCCESS_MAX
            if len(encoded) > limit:
                # Wrap in a truncation envelope so the string stays valid JSON
                result_preview = json.dumps(
                    {"_truncated": True, "preview": encoded[:limit], "total_chars": len(encoded)},
                    default=str,
                )
            else:
                result_preview = encoded
        except Exception:
            result_preview = json.dumps({"_error": str(result)[:_FAILED_MAX]})
    else:
        result_preview = None

    _fire_index_event(
        {
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id) if agent_id else None,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "event_type": "tool_call",
            "sequence": sequence,
            "timestamp": _now_iso(),
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms,
            "retry_count": retry_count,
            "args": stored_args,
            "result": result_preview,
            "error_message": error_message,
        }
    )


def fire_assistant_message(
    *,
    tenant_id: UUID,
    agent_id: UUID | None,
    conversation_id: UUID | None,
    message_id: UUID | None,
    content_preview: str,
    total_input_tokens: int,
    total_output_tokens: int,
    total_cost_usd: float,
    total_latency_ms: int,
    sequence: int,
) -> None:
    """Fire-and-forget: index an assistant_message event."""
    from src.config.settings import settings

    if not settings.agent_trace_enabled:
        return

    _fire_index_event(
        {
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id) if agent_id else None,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "message_id": str(message_id) if message_id else None,
            "event_type": "assistant_message",
            "sequence": sequence,
            "timestamp": _now_iso(),
            "content_preview": content_preview[:3000],
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cost_usd": total_cost_usd,
            "total_latency_ms": total_latency_ms,
        }
    )


# ---------------------------------------------------------------------------
# Read path — ES aggregation queries (replace agent_lens_service.py)
# ---------------------------------------------------------------------------


def _base_filter(tenant_id: UUID, agent_id: UUID, start: datetime, end: datetime) -> list:
    return [
        {"term": {"tenant_id": str(tenant_id)}},
        {"term": {"agent_id": str(agent_id)}},
        {"range": {"timestamp": {"gte": start.isoformat(), "lte": end.isoformat()}}},
    ]


async def get_overview(
    tenant_id: UUID,
    agent_id: UUID,
    start: datetime,
    end: datetime,
) -> dict:
    """Return stat card values computed from ES aggregations."""
    es = await _get_es_client()
    from src.config.settings import settings

    body = {
        "size": 0,
        "query": {"bool": {"filter": _base_filter(tenant_id, agent_id, start, end)}},
        "aggs": {
            "total_sessions": {"cardinality": {"field": "conversation_id"}},
            "llm_stats": {
                "filter": {"term": {"event_type": "llm_call"}},
                "aggs": {
                    "count": {"value_count": {"field": "event_type"}},
                    "input_tokens": {"sum": {"field": "input_tokens"}},
                    "output_tokens": {"sum": {"field": "output_tokens"}},
                    "cost": {"sum": {"field": "cost_usd"}},
                    "avg_latency": {"avg": {"field": "latency_ms"}},
                },
            },
            "tool_stats": {
                "filter": {"term": {"event_type": "tool_call"}},
                "aggs": {
                    "total": {"value_count": {"field": "event_type"}},
                    "failed": {
                        "filter": {"term": {"success": False}},
                        "aggs": {"count": {"value_count": {"field": "event_type"}}},
                    },
                    "avg_duration": {"avg": {"field": "duration_ms"}},
                },
            },
        },
    }

    resp = await _safe_es_search(es, index=settings.agent_trace_index, body=body)
    aggs = resp["aggregations"]
    llm = aggs["llm_stats"]
    tool = aggs["tool_stats"]

    total_sessions = int(aggs["total_sessions"]["value"])
    total_requests = int(llm["count"]["value"])
    input_tokens = int(llm["input_tokens"]["value"] or 0)
    output_tokens = int(llm["output_tokens"]["value"] or 0)
    total_tokens = input_tokens + output_tokens
    total_cost = float(llm["cost"]["value"] or 0)
    avg_latency = int(llm["avg_latency"]["value"] or 0)
    total_tool_calls = int(tool["total"]["value"])
    failed_tool_calls = int(tool["failed"]["count"]["value"])
    avg_tool_duration = int(tool["avg_duration"]["value"] or 0)

    avg_cost_per_session = (total_cost / total_sessions) if total_sessions > 0 else 0.0
    failure_rate = (failed_tool_calls / total_tool_calls) if total_tool_calls > 0 else 0.0

    return {
        "total_sessions": total_sessions,
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "avg_latency_ms": avg_latency,
        "total_cost_usd": total_cost,
        "avg_cost_per_session": avg_cost_per_session,
        "failure_rate": failure_rate,
        "total_tool_calls": total_tool_calls,
        "failed_tool_calls": failed_tool_calls,
        "avg_tool_duration_ms": avg_tool_duration,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
    }


async def get_sessions(
    tenant_id: UUID,
    agent_id: UUID,
    start: datetime,
    end: datetime,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Return paginated list of sessions via terms aggregation on conversation_id."""
    es = await _get_es_client()
    from src.config.settings import settings

    body = {
        "size": 0,
        "query": {"bool": {"filter": _base_filter(tenant_id, agent_id, start, end)}},
        "aggs": {
            "total_sessions": {"cardinality": {"field": "conversation_id"}},
            "by_conversation": {
                "terms": {
                    "field": "conversation_id",
                    "size": 10000,
                    "order": {"first_ts": "desc"},
                },
                "aggs": {
                    "first_ts": {"min": {"field": "timestamp"}},
                    "total_input": {"sum": {"field": "input_tokens"}},
                    "total_output": {"sum": {"field": "output_tokens"}},
                    "total_cost": {"sum": {"field": "cost_usd"}},
                    "msg_count": {
                        "filter": {"term": {"event_type": "user_message"}},
                        "aggs": {"c": {"value_count": {"field": "event_type"}}},
                    },
                    "meta": {
                        "filter": {"term": {"event_type": "user_message"}},
                        "aggs": {
                            "top": {
                                "top_hits": {
                                    "size": 1,
                                    "_source": ["conversation_name", "conversation_status"],
                                    "sort": [{"sequence": {"order": "asc"}}],
                                }
                            }
                        },
                    },
                    "model_hit": {
                        "filter": {"term": {"event_type": "llm_call"}},
                        "aggs": {
                            "top": {
                                "top_hits": {
                                    "size": 1,
                                    "_source": ["model"],
                                    "sort": [{"sequence": {"order": "asc"}}],
                                }
                            }
                        },
                    },
                },
            },
        },
    }

    resp = await _safe_es_search(es, index=settings.agent_trace_index, body=body)
    aggs = resp["aggregations"]
    total = int(aggs["total_sessions"]["value"])
    buckets = aggs["by_conversation"]["buckets"]

    offset = (page - 1) * page_size
    page_buckets = buckets[offset : offset + page_size]

    sessions = []
    for b in page_buckets:
        conv_id = b["key"]
        meta_hits = b["meta"]["top"]["hits"]["hits"]
        model_hits = b["model_hit"]["top"]["hits"]["hits"]

        conv_name = "Conversation"
        conv_status = "ACTIVE"
        if meta_hits:
            src = meta_hits[0]["_source"]
            conv_name = src.get("conversation_name", "Conversation")
            conv_status = src.get("conversation_status", "ACTIVE")

        model_name = None
        if model_hits:
            model_name = model_hits[0]["_source"].get("model")

        total_tokens = int((b["total_input"]["value"] or 0) + (b["total_output"]["value"] or 0))
        cost_usd = float(b["total_cost"]["value"] or 0)
        message_count = int(b["msg_count"]["c"]["value"])
        created_at = b["first_ts"]["value_as_string"] if b["first_ts"]["value"] else None

        sessions.append(
            {
                "id": conv_id,
                "name": conv_name,
                "status": conv_status,
                "model_name": model_name,
                "total_tokens": total_tokens,
                "cost_usd": cost_usd,
                "message_count": message_count,
                "created_at": created_at,
            }
        )

    total_pages = max(1, -(-total // page_size))  # ceiling division
    return {
        "sessions": sessions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def get_token_distribution(
    tenant_id: UUID,
    agent_id: UUID,
    start: datetime,
    end: datetime,
) -> dict:
    """Return token/cost breakdown by model and prompt vs completion."""
    es = await _get_es_client()
    from src.config.settings import settings

    body = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    *_base_filter(tenant_id, agent_id, start, end),
                    {"term": {"event_type": "llm_call"}},
                ]
            }
        },
        "aggs": {
            "by_model": {
                "terms": {"field": "model", "size": 20},
                "aggs": {
                    "input_tokens": {"sum": {"field": "input_tokens"}},
                    "output_tokens": {"sum": {"field": "output_tokens"}},
                    "cost": {"sum": {"field": "cost_usd"}},
                    "calls": {"value_count": {"field": "event_type"}},
                },
            },
            "total_input": {"sum": {"field": "input_tokens"}},
            "total_output": {"sum": {"field": "output_tokens"}},
        },
    }

    resp = await _safe_es_search(es, index=settings.agent_trace_index, body=body)
    aggs = resp["aggregations"]

    by_model = []
    for b in aggs["by_model"]["buckets"]:
        inp = int(b["input_tokens"]["value"] or 0)
        out = int(b["output_tokens"]["value"] or 0)
        by_model.append(
            {
                "model_name": b["key"],
                "tokens": inp + out,
                "cost_usd": float(b["cost"]["value"] or 0),
                "calls": int(b["calls"]["value"]),
            }
        )

    return {
        "by_model": by_model,
        "prompt_vs_completion": {
            "input_tokens": int(aggs["total_input"]["value"] or 0),
            "output_tokens": int(aggs["total_output"]["value"] or 0),
        },
    }


async def get_tool_analytics(
    tenant_id: UUID,
    agent_id: UUID,
    start: datetime,
    end: datetime,
) -> dict:
    """Return per-tool call counts, success rates, and duration stats."""
    es = await _get_es_client()
    from src.config.settings import settings

    body = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    *_base_filter(tenant_id, agent_id, start, end),
                    {"term": {"event_type": "tool_call"}},
                ]
            }
        },
        "aggs": {
            "by_tool": {
                "terms": {"field": "tool_name", "size": 20, "order": {"_count": "desc"}},
                "aggs": {
                    "success_count": {
                        "filter": {"term": {"success": True}},
                        "aggs": {"c": {"value_count": {"field": "event_type"}}},
                    },
                    "failure_count": {
                        "filter": {"term": {"success": False}},
                        "aggs": {"c": {"value_count": {"field": "event_type"}}},
                    },
                    "avg_duration": {"avg": {"field": "duration_ms"}},
                    "max_duration": {"max": {"field": "duration_ms"}},
                    "total_retries": {"sum": {"field": "retry_count"}},
                },
            },
            "total_failures": {
                "filter": {"term": {"success": False}},
                "aggs": {"count": {"value_count": {"field": "event_type"}}},
            },
        },
    }

    resp = await _safe_es_search(es, index=settings.agent_trace_index, body=body)
    aggs = resp["aggregations"]

    tools = []
    total_calls = 0
    for b in aggs["by_tool"]["buckets"]:
        tc = int(b["doc_count"])
        sc = int(b["success_count"]["c"]["value"])
        fc = int(b["failure_count"]["c"]["value"])
        total_calls += tc
        tools.append(
            {
                "tool_name": b["key"],
                "total_calls": tc,
                "success_count": sc,
                "failure_count": fc,
                "success_rate": (sc / tc) if tc > 0 else 1.0,
                "avg_duration_ms": int(b["avg_duration"]["value"] or 0),
                "max_duration_ms": int(b["max_duration"]["value"] or 0),
                "total_retries": int(b["total_retries"]["value"] or 0),
            }
        )

    total_failures = int(aggs["total_failures"]["count"]["value"])
    overall_success_rate = ((total_calls - total_failures) / total_calls) if total_calls > 0 else 1.0

    return {
        "tools": tools,
        "total_calls": total_calls,
        "total_failures": total_failures,
        "overall_success_rate": overall_success_rate,
    }


async def get_session_detail(
    tenant_id: UUID,
    agent_id: UUID,
    conversation_id: UUID,
) -> dict | None:
    """Return all events for a session sorted by sequence."""
    es = await _get_es_client()
    from src.config.settings import settings

    body = {
        "size": 500,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tenant_id": str(tenant_id)}},
                    {"term": {"agent_id": str(agent_id)}},
                    {"term": {"conversation_id": str(conversation_id)}},
                ]
            }
        },
        # Sort by timestamp so multi-turn conversations render in chronological order.
        # Sequence resets to 1 for each user turn, so sorting by sequence alone would
        # interleave events from different turns.
        "sort": [{"timestamp": {"order": "asc"}}, {"sequence": {"order": "asc"}}],
    }

    resp = await _safe_es_search(es, index=settings.agent_trace_index, body=body)
    hits = resp["hits"]["hits"]
    if not hits:
        return None

    # Attach ES _id so the frontend can deduplicate true duplicates (fire-and-forget
    # can occasionally index the same event twice with different _id values).
    events = [{**h["_source"], "_es_id": h["_id"]} for h in hits]

    # Derive session-level totals from events
    total_input = sum(e.get("input_tokens") or 0 for e in events if e.get("event_type") == "llm_call")
    total_output = sum(e.get("output_tokens") or 0 for e in events if e.get("event_type") == "llm_call")
    total_cost = sum(e.get("cost_usd") or 0 for e in events if e.get("event_type") == "llm_call")
    total_tool_calls = sum(1 for e in events if e.get("event_type") == "tool_call")
    failed_tool_calls = sum(1 for e in events if e.get("event_type") == "tool_call" and not e.get("success", True))
    message_count = sum(1 for e in events if e.get("event_type") == "user_message")

    # Session name from first user_message
    session_name = "Session"
    session_status = "ACTIVE"
    created_at = None
    for e in events:
        if e.get("event_type") == "user_message":
            session_name = e.get("conversation_name", "Session")
            session_status = e.get("conversation_status", "ACTIVE")
            created_at = e.get("timestamp")
            break

    # Build timeline — normalise field names to match LensTimelineEvent schema
    timeline = []
    for e in events:
        evt_type = e.get("event_type")
        # Use ES document _id for uniqueness; fallback to message_id for message events
        unique_id = e.get("_es_id") or e.get("message_id") or f"{evt_type}-{e.get('sequence', 0)}"
        base = {
            "id": unique_id,
            "event_type": evt_type,
            "timestamp": e.get("timestamp"),
            "sequence": e.get("sequence", 0),
        }
        if evt_type == "user_message":
            base.update(
                {
                    "role": "USER",
                    "content": e.get("content"),
                }
            )
        elif evt_type == "llm_call":
            base.update(
                {
                    "model": e.get("model"),
                    "call_index": e.get("call_index", 0),
                    "input_tokens": e.get("input_tokens"),
                    "output_tokens": e.get("output_tokens"),
                    "cost_usd": e.get("cost_usd"),
                    "latency_ms": e.get("latency_ms"),
                    "response_preview": e.get("response_preview"),
                    "status": e.get("llm_status"),
                    "error": e.get("llm_error"),
                    # LLM input inspection fields
                    "system_prompt_preview": e.get("system_prompt"),
                    "messages_json": e.get("messages_json"),
                    "tools_json": e.get("tools_json"),
                    # Prompt cache
                    "cache_read_tokens": e.get("cache_read_tokens"),
                    "cache_creation_tokens": e.get("cache_creation_tokens"),
                    # Context pressure
                    "context_utilization_pct": e.get("context_utilization_pct"),
                }
            )
        elif evt_type == "tool_call":
            base.update(
                {
                    "tool_name": e.get("tool_name"),
                    "success": e.get("success", True),
                    "duration_ms": e.get("duration_ms"),
                    "retry_count": e.get("retry_count", 0),
                    "tool_args": e.get("args"),
                    "tool_result": e.get("result"),
                    "error_message": e.get("error_message"),
                }
            )
        elif evt_type == "assistant_message":
            base.update(
                {
                    "role": "ASSISTANT",
                    "content": e.get("content_preview"),
                    "input_tokens": e.get("total_input_tokens"),
                    "output_tokens": e.get("total_output_tokens"),
                    "latency_ms": e.get("total_latency_ms"),
                }
            )
        elif evt_type == "tool_pruning":
            base.update(
                {
                    "turn_index": e.get("turn_index"),
                    "tool_results_count": e.get("tool_results_count"),
                    "tool_results_pruned": e.get("tool_results_pruned"),
                    "data_bearing_pruned": e.get("data_bearing_pruned"),
                    "chars_saved": e.get("chars_saved"),
                    "estimated_tokens_saved": e.get("estimated_tokens_saved"),
                    "original_chars": e.get("original_chars"),
                    "pruned_chars": e.get("pruned_chars"),
                }
            )
        timeline.append(base)

    return {
        "conversation_id": str(conversation_id),
        "name": session_name,
        "status": session_status,
        "created_at": created_at,
        "timeline": timeline,
        "total_tokens": total_input + total_output,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_cost_usd": total_cost,
        "total_tool_calls": total_tool_calls,
        "failed_tool_calls": failed_tool_calls,
        "message_count": message_count,
    }


# ---------------------------------------------------------------------------
# Compaction / pruning analytics
# ---------------------------------------------------------------------------


async def get_compaction_analytics(
    tenant_id: UUID,
    agent_id: UUID,
    start: datetime,
    end: datetime,
) -> dict:
    """Return context-pruning / compaction analytics aggregated from tool_pruning events."""
    es = await _get_es_client()
    from src.config.settings import settings

    base = _base_filter(tenant_id, agent_id, start, end)

    body = {
        "size": 0,
        "query": {"bool": {"filter": base}},
        "aggs": {
            # Total sessions (cardinality across all events)
            "total_sessions": {"cardinality": {"field": "conversation_id"}},
            # Pruning-specific aggregations
            "pruning_events": {
                "filter": {"term": {"event_type": "tool_pruning"}},
                "aggs": {
                    "count": {"value_count": {"field": "event_type"}},
                    "sessions_with_pruning": {"cardinality": {"field": "conversation_id"}},
                    "total_tokens_saved": {"sum": {"field": "estimated_tokens_saved"}},
                    "total_chars_saved": {"sum": {"field": "chars_saved"}},
                    "total_data_bearing_pruned": {"sum": {"field": "data_bearing_pruned"}},
                    "avg_tokens_saved": {"avg": {"field": "estimated_tokens_saved"}},
                    "total_results_pruned": {"sum": {"field": "tool_results_pruned"}},
                    "total_results_evaluated": {"sum": {"field": "tool_results_count"}},
                    # Daily trend buckets
                    "trend": {
                        "date_histogram": {
                            "field": "timestamp",
                            "calendar_interval": "day",
                            "min_doc_count": 0,
                            "extended_bounds": {
                                "min": start.isoformat(),
                                "max": end.isoformat(),
                            },
                        },
                        "aggs": {
                            "pruning_events": {"value_count": {"field": "event_type"}},
                            "tokens_saved": {"sum": {"field": "estimated_tokens_saved"}},
                            "data_bearing_pruned": {"sum": {"field": "data_bearing_pruned"}},
                        },
                    },
                },
            },
        },
    }

    resp = await _safe_es_search(es, index=settings.agent_trace_index, body=body)
    aggs = resp["aggregations"]
    pr = aggs["pruning_events"]

    total_sessions = int(aggs["total_sessions"]["value"])
    sessions_with_pruning = int(pr["sessions_with_pruning"]["value"])
    pruning_rate = (sessions_with_pruning / total_sessions) if total_sessions > 0 else 0.0
    total_tokens_saved = int(pr["total_tokens_saved"]["value"] or 0)
    avg_tokens_saved = float(pr["avg_tokens_saved"]["value"] or 0)
    data_bearing_pruned_total = int(pr["total_data_bearing_pruned"]["value"] or 0)
    total_results_pruned = int(pr["total_results_pruned"]["value"] or 0)
    total_results_evaluated = int(pr["total_results_evaluated"]["value"] or 0)
    pruning_ratio = (total_results_pruned / total_results_evaluated) if total_results_evaluated > 0 else 0.0
    pruning_events_count = int(pr["count"]["value"])

    trend = []
    for b in pr["trend"]["buckets"]:
        trend.append(
            {
                "date": b["key_as_string"][:10],
                "pruning_events": int(b["pruning_events"]["value"]),
                "tokens_saved": int(b["tokens_saved"]["value"] or 0),
                "data_bearing_pruned": int(b["data_bearing_pruned"]["value"] or 0),
            }
        )

    return {
        "total_sessions": total_sessions,
        "sessions_with_pruning": sessions_with_pruning,
        "pruning_rate": round(pruning_rate, 4),
        "pruning_events_count": pruning_events_count,
        "total_tokens_saved": total_tokens_saved,
        "avg_tokens_saved_per_session": round(avg_tokens_saved, 1),
        "data_bearing_pruned_total": data_bearing_pruned_total,
        "total_results_pruned": total_results_pruned,
        "total_results_evaluated": total_results_evaluated,
        "avg_pruning_ratio": round(pruning_ratio, 4),
        "trend": trend,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
    }


# ---------------------------------------------------------------------------
# Prompt cache analytics
# ---------------------------------------------------------------------------


async def get_cache_analytics(
    tenant_id: UUID,
    agent_id: UUID,
    start: datetime,
    end: datetime,
) -> dict:
    """Return prompt-cache hit metrics aggregated from llm_call events."""
    es = await _get_es_client()
    from src.config.settings import settings

    body = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    *_base_filter(tenant_id, agent_id, start, end),
                    {"term": {"event_type": "llm_call"}},
                ]
            }
        },
        "aggs": {
            "total_llm_calls": {"value_count": {"field": "event_type"}},
            "total_input_tokens": {"sum": {"field": "input_tokens"}},
            "total_cache_read": {"sum": {"field": "cache_read_tokens"}},
            "total_cache_creation": {"sum": {"field": "cache_creation_tokens"}},
            # Calls that had at least one cache-read token
            "calls_with_cache_hit": {
                "filter": {"range": {"cache_read_tokens": {"gt": 0}}},
                "aggs": {"count": {"value_count": {"field": "event_type"}}},
            },
            # Daily trend
            "trend": {
                "date_histogram": {
                    "field": "timestamp",
                    "calendar_interval": "day",
                    "min_doc_count": 0,
                    "extended_bounds": {
                        "min": start.isoformat(),
                        "max": end.isoformat(),
                    },
                },
                "aggs": {
                    "cache_read": {"sum": {"field": "cache_read_tokens"}},
                    "cache_creation": {"sum": {"field": "cache_creation_tokens"}},
                    "input_tokens": {"sum": {"field": "input_tokens"}},
                },
            },
            # Context utilization distribution
            "context_pressure": {
                "filter": {"exists": {"field": "context_utilization_pct"}},
                "aggs": {
                    "avg_utilization": {"avg": {"field": "context_utilization_pct"}},
                    "max_utilization": {"max": {"field": "context_utilization_pct"}},
                    "high_pressure": {
                        "filter": {"range": {"context_utilization_pct": {"gte": 80}}},
                        "aggs": {"count": {"value_count": {"field": "event_type"}}},
                    },
                },
            },
        },
    }

    resp = await _safe_es_search(es, index=settings.agent_trace_index, body=body)
    aggs = resp["aggregations"]

    total_calls = int(aggs["total_llm_calls"]["value"])
    total_input = int(aggs["total_input_tokens"]["value"] or 0)
    total_cache_read = int(aggs["total_cache_read"]["value"] or 0)
    total_cache_creation = int(aggs["total_cache_creation"]["value"] or 0)
    calls_with_hit = int(aggs["calls_with_cache_hit"]["count"]["value"])
    cache_hit_rate = (calls_with_hit / total_calls) if total_calls > 0 else 0.0

    # Anthropic cached reads cost ~10% of regular input — rough savings estimate
    # $3 per 1M input tokens → $0.30 per 1M cached = $0.0000027 per cached token
    _CACHE_SAVINGS_PER_TOKEN = 0.0000027
    estimated_savings_usd = total_cache_read * _CACHE_SAVINGS_PER_TOKEN

    ctx = aggs["context_pressure"]
    avg_utilization = float(ctx["avg_utilization"]["value"] or 0)
    max_utilization = float(ctx["max_utilization"]["value"] or 0)
    high_pressure_calls = int(ctx["high_pressure"]["count"]["value"])

    trend = []
    for b in aggs["trend"]["buckets"]:
        inp = int(b["input_tokens"]["value"] or 0)
        cr = int(b["cache_read"]["value"] or 0)
        trend.append(
            {
                "date": b["key_as_string"][:10],
                "input_tokens": inp,
                "cache_read_tokens": cr,
                "cache_creation_tokens": int(b["cache_creation"]["value"] or 0),
                "cache_hit_rate": round((cr / inp) if inp > 0 else 0.0, 4),
            }
        )

    return {
        "total_llm_calls": total_calls,
        "total_input_tokens": total_input,
        "total_cache_read_tokens": total_cache_read,
        "total_cache_creation_tokens": total_cache_creation,
        "cache_hit_rate": round(cache_hit_rate, 4),
        "estimated_savings_usd": round(estimated_savings_usd, 6),
        "avg_context_utilization_pct": round(avg_utilization, 2),
        "max_context_utilization_pct": round(max_utilization, 2),
        "high_pressure_calls": high_pressure_calls,
        "trend": trend,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
    }


# ---------------------------------------------------------------------------
# Session interaction graph
# ---------------------------------------------------------------------------


def _build_session_graph(timeline: list[dict]) -> dict:
    """Transform a flat timeline into nodes + directed edges for visualisation."""
    nodes = []
    edges = []

    # Track last node of each logical "track" to connect edges
    last_node_id: str | None = None

    for event in timeline:
        evt_type = event.get("event_type")
        node_id = event.get("id") or f"{evt_type}-{event.get('sequence', 0)}"

        # Build label
        if evt_type == "user_message":
            content = event.get("content") or ""
            label = content[:60] + ("..." if len(content) > 60 else "")
            status = "normal"
        elif evt_type == "llm_call":
            model = event.get("model") or "LLM"
            inp = event.get("input_tokens") or 0
            out = event.get("output_tokens") or 0
            cache_read = event.get("cache_read_tokens") or 0
            ctx_pct = event.get("context_utilization_pct")
            label = f"{model} · {inp}in/{out}out tok"
            if cache_read:
                label += f" · {cache_read} cached"
            status = (
                "error" if event.get("status") == "error" else ("warning" if ctx_pct and ctx_pct >= 80 else "normal")
            )
        elif evt_type == "tool_call":
            tool_name = event.get("tool_name") or "tool"
            duration = event.get("duration_ms") or 0
            label = f"{tool_name} ({duration}ms)"
            status = "error" if not event.get("success", True) else "normal"
        elif evt_type == "tool_pruning":
            tokens_saved = event.get("estimated_tokens_saved") or 0
            pruned = event.get("tool_results_pruned") or 0
            data_pruned = event.get("data_bearing_pruned") or 0
            label = f"Pruned {pruned} results · ~{tokens_saved} tok saved"
            status = "warning" if data_pruned > 0 else "info"
        elif evt_type == "assistant_message":
            content = event.get("content") or ""
            label = content[:60] + ("..." if len(content) > 60 else "")
            status = "normal"
        else:
            label = evt_type or "unknown"
            status = "normal"

        # Build metadata (subset of fields for the graph tooltip)
        meta: dict = {"timestamp": event.get("timestamp"), "sequence": event.get("sequence")}
        if evt_type == "llm_call":
            meta.update(
                {
                    "input_tokens": event.get("input_tokens"),
                    "output_tokens": event.get("output_tokens"),
                    "cost_usd": event.get("cost_usd"),
                    "latency_ms": event.get("latency_ms"),
                    "cache_read_tokens": event.get("cache_read_tokens"),
                    "cache_creation_tokens": event.get("cache_creation_tokens"),
                    "context_utilization_pct": event.get("context_utilization_pct"),
                }
            )
        elif evt_type == "tool_call":
            meta.update(
                {
                    "success": event.get("success"),
                    "duration_ms": event.get("duration_ms"),
                    "retry_count": event.get("retry_count"),
                    "error_message": event.get("error_message"),
                }
            )
        elif evt_type == "tool_pruning":
            meta.update(
                {
                    "tool_results_count": event.get("tool_results_count"),
                    "tool_results_pruned": event.get("tool_results_pruned"),
                    "data_bearing_pruned": event.get("data_bearing_pruned"),
                    "chars_saved": event.get("chars_saved"),
                    "estimated_tokens_saved": event.get("estimated_tokens_saved"),
                }
            )

        nodes.append(
            {
                "id": node_id,
                "event_type": evt_type,
                "label": label,
                "status": status,
                "metadata": meta,
            }
        )

        if last_node_id is not None:
            edges.append({"source": last_node_id, "target": node_id})

        last_node_id = node_id

    return {"nodes": nodes, "edges": edges}


async def get_session_graph(
    tenant_id: UUID,
    agent_id: UUID,
    conversation_id: UUID,
) -> dict | None:
    """Return session timeline as a graph (nodes + edges) for visualisation."""
    detail = await get_session_detail(tenant_id, agent_id, conversation_id)
    if not detail:
        return None

    graph = _build_session_graph(detail["timeline"])
    return {
        "conversation_id": str(conversation_id),
        "nodes": graph["nodes"],
        "edges": graph["edges"],
    }


# ---------------------------------------------------------------------------
# Tool ROI analysis
# ---------------------------------------------------------------------------


async def get_tool_roi(
    tenant_id: UUID,
    agent_id: UUID,
    start: datetime,
    end: datetime,
) -> dict:
    """
    For each tool, compare sessions that used it vs sessions that did not.

    Metrics:
    - completion_lift: difference in assistant-message resolution rate (with vs without tool)
    - cost_impact_pct: relative cost increase/decrease in sessions that used the tool
    - avg_llm_calls_with/without: LLM call count as an efficiency proxy
    - verdict: keep | review | remove | neutral (based on lift + error rate)

    Two parallel ES queries + pure Python set arithmetic — no Postgres needed.
    """
    es = await _get_es_client()
    from src.config.settings import settings

    base = _base_filter(tenant_id, agent_id, start, end)

    # ── Q1: per-session summary (LLM calls, cost, has assistant response) ─────
    q1 = {
        "size": 0,
        "query": {"bool": {"filter": base}},
        "aggs": {
            "total_sessions": {"cardinality": {"field": "conversation_id"}},
            "by_session": {
                "terms": {"field": "conversation_id", "size": 10000},
                "aggs": {
                    "llm": {
                        "filter": {"term": {"event_type": "llm_call"}},
                        "aggs": {
                            "count": {"value_count": {"field": "event_type"}},
                            "cost": {"sum": {"field": "cost_usd"}},
                        },
                    },
                    "resolved": {
                        "filter": {"term": {"event_type": "assistant_message"}},
                        "aggs": {"count": {"value_count": {"field": "event_type"}}},
                    },
                },
            },
        },
    }

    # ── Q2: per-tool, which sessions used it and error rate ───────────────────
    q2 = {
        "size": 0,
        "query": {"bool": {"filter": [*base, {"term": {"event_type": "tool_call"}}]}},
        "aggs": {
            "by_tool": {
                "terms": {"field": "tool_name", "size": 20, "order": {"_count": "desc"}},
                "aggs": {
                    "sessions": {"terms": {"field": "conversation_id", "size": 10000}},
                    "error_count": {
                        "filter": {"term": {"success": False}},
                        "aggs": {"count": {"value_count": {"field": "event_type"}}},
                    },
                },
            }
        },
    }

    resp1, resp2 = await asyncio.gather(
        es.search(index=settings.agent_trace_index, body=q1),
        es.search(index=settings.agent_trace_index, body=q2),
    )

    # ── Build per-session data dict ───────────────────────────────────────────
    total_sessions = int(resp1["aggregations"]["total_sessions"]["value"])
    session_data: dict[str, dict] = {}
    for b in resp1["aggregations"]["by_session"]["buckets"]:
        cid = b["key"]
        session_data[cid] = {
            "llm_calls": int(b["llm"]["count"]["value"]),
            "cost": float(b["llm"]["cost"]["value"] or 0),
            "resolved": int(b["resolved"]["count"]["value"]) > 0,
        }

    all_ids = set(session_data.keys())

    def _avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    # ── Compute per-tool ROI stats ────────────────────────────────────────────
    tools = []
    for b in resp2["aggregations"]["by_tool"]["buckets"]:
        tool_name = b["key"]
        total_calls = int(b["doc_count"])
        error_count = int(b["error_count"]["count"]["value"])
        error_rate = (error_count / total_calls) if total_calls > 0 else 0.0

        with_ids = {s["key"] for s in b["sessions"]["buckets"]}
        without_ids = all_ids - with_ids
        sessions_with = len(with_ids)
        sessions_without = len(without_ids)
        calls_per_session = (total_calls / sessions_with) if sessions_with > 0 else 0.0

        # With-tool metrics
        with_data = [session_data[cid] for cid in with_ids if cid in session_data]
        avg_cost_with = _avg([d["cost"] for d in with_data])
        avg_llm_with = _avg([float(d["llm_calls"]) for d in with_data])
        completion_with = _avg([1.0 if d["resolved"] else 0.0 for d in with_data])

        # Without-tool metrics
        without_data = [session_data[cid] for cid in without_ids if cid in session_data]
        avg_cost_without = _avg([d["cost"] for d in without_data])
        avg_llm_without = _avg([float(d["llm_calls"]) for d in without_data])
        completion_without = _avg([1.0 if d["resolved"] else 0.0 for d in without_data])

        completion_lift = completion_with - completion_without
        cost_impact_pct = (avg_cost_with - avg_cost_without) / avg_cost_without if avg_cost_without > 0 else 0.0

        # Verdict — requires minimum 3 sessions to have statistical meaning
        if sessions_with < 3:
            verdict = "neutral"
        elif completion_lift < -0.15 or error_rate > 0.5:
            verdict = "remove"
        elif completion_lift < -0.05 or error_rate > 0.15 or (calls_per_session > 5 and completion_lift < 0.02):
            verdict = "review"
        elif completion_lift >= 0.05 or (error_rate < 0.05 and completion_lift >= 0):
            verdict = "keep"
        else:
            verdict = "neutral"

        tools.append(
            {
                "tool_name": tool_name,
                "total_calls": total_calls,
                "calls_per_session": round(calls_per_session, 2),
                "sessions_with": sessions_with,
                "sessions_without": sessions_without,
                "error_rate": round(error_rate, 4),
                "avg_cost_with": round(avg_cost_with, 6),
                "avg_cost_without": round(avg_cost_without, 6),
                "cost_impact_pct": round(cost_impact_pct, 4),
                "avg_llm_calls_with": round(avg_llm_with, 2),
                "avg_llm_calls_without": round(avg_llm_without, 2),
                "completion_rate_with": round(completion_with, 4),
                "completion_rate_without": round(completion_without, 4),
                "completion_lift": round(completion_lift, 4),
                "verdict": verdict,
            }
        )

    return {
        "tools": tools,
        "total_sessions": total_sessions,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
    }


# ---------------------------------------------------------------------------
# Alert CRUD (stays in Postgres — re-exported here for controller convenience)
# ---------------------------------------------------------------------------


async def get_alerts(db, tenant_id: UUID, agent_id: UUID) -> list[dict]:
    from sqlalchemy import select

    from src.models.agent_lens_alert import AgentLensAlert

    result = await db.execute(
        select(AgentLensAlert).where(
            AgentLensAlert.tenant_id == tenant_id,
            AgentLensAlert.agent_id == agent_id,
        )
    )
    alerts = result.scalars().all()
    return [_alert_to_dict(a) for a in alerts]


async def create_alert(db, tenant_id: UUID, agent_id: UUID, data: dict) -> dict:
    from src.models.agent_lens_alert import AgentLensAlert

    alert = AgentLensAlert(tenant_id=tenant_id, agent_id=agent_id, **data)
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return _alert_to_dict(alert)


async def update_alert(db, tenant_id: UUID, alert_id: UUID, data: dict) -> dict | None:
    from sqlalchemy import select

    from src.models.agent_lens_alert import AgentLensAlert

    result = await db.execute(
        select(AgentLensAlert).where(
            AgentLensAlert.id == alert_id,
            AgentLensAlert.tenant_id == tenant_id,
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        return None
    for k, v in data.items():
        setattr(alert, k, v)
    await db.commit()
    await db.refresh(alert)
    return _alert_to_dict(alert)


async def delete_alert(db, tenant_id: UUID, alert_id: UUID) -> bool:
    from sqlalchemy import select

    from src.models.agent_lens_alert import AgentLensAlert

    result = await db.execute(
        select(AgentLensAlert).where(
            AgentLensAlert.id == alert_id,
            AgentLensAlert.tenant_id == tenant_id,
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        return False
    await db.delete(alert)
    await db.commit()
    return True


def _alert_to_dict(alert) -> dict:
    return {
        "id": str(alert.id),
        "agent_id": str(alert.agent_id),
        "name": alert.name,
        "metric": alert.metric,
        "condition": alert.condition,
        "threshold": float(alert.threshold),
        "window_minutes": alert.window_minutes,
        "notify_method": alert.notify_method,
        "notify_config": alert.notify_config,
        "is_active": alert.is_active,
        "last_triggered_at": alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }
