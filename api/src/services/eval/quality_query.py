"""
Quality Query Service

ES aggregation queries backing the Agent Lens quality dashboard endpoints.
Reads from agent_feedback_* and agent_outcomes_* indices.
"""

import logging
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)

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
        request_timeout=10,
    )
    return _es_client


async def get_quality_stats(
    tenant_id: UUID,
    agent_id: UUID,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """
    Aggregate satisfaction + outcome stats for the quality dashboard.

    Returns a dict matching LensQualityResponse shape.
    """
    from src.config.settings import settings

    es = await _get_es_client()

    date_filter = {"range": {"@timestamp": {"gte": start_date.isoformat(), "lte": end_date.isoformat()}}}
    base_filter = [
        {"term": {"agent_id.keyword": str(agent_id)}},
        {"term": {"tenant_id.keyword": str(tenant_id)}},
        date_filter,
    ]

    # ---- Feedback aggregations ----
    feedback_body = {
        "query": {"bool": {"filter": base_filter}},
        "size": 0,
        "aggs": {
            "thumbs_up": {"filter": {"term": {"rating": 1}}},
            "thumbs_down": {"filter": {"term": {"rating": -1}}},
            "by_channel": {
                "terms": {"field": "channel.keyword", "size": 10},
                "aggs": {
                    "up": {"filter": {"term": {"rating": 1}}},
                    "down": {"filter": {"term": {"rating": -1}}},
                },
            },
        },
    }

    # ---- Outcome aggregations ----
    outcome_body = {
        "query": {"bool": {"filter": base_filter}},
        "size": 0,
        "aggs": {
            "by_outcome": {"terms": {"field": "outcome.keyword", "size": 10}},
            "explicit": {"filter": {"term": {"source.keyword": "explicit"}}},
            "implicit": {"filter": {"term": {"source.keyword": "implicit"}}},
        },
    }

    try:
        fb_resp, oc_resp = await _safe_multi_search(
            es,
            [
                (settings.agent_feedback_index, feedback_body),
                (settings.agent_outcomes_index, outcome_body),
            ],
        )
    except Exception as e:
        logger.warning("quality_query ES search failed: %s", e)
        return _empty_quality_response(start_date, end_date)

    # ---- Parse feedback ----
    fb_aggs = fb_resp.get("aggregations", {})
    thumbs_up = fb_aggs.get("thumbs_up", {}).get("doc_count", 0)
    thumbs_down = fb_aggs.get("thumbs_down", {}).get("doc_count", 0)
    total_rated = thumbs_up + thumbs_down
    satisfaction_rate = round(thumbs_up / total_rated, 3) if total_rated else 0.0

    by_channel = []
    for bucket in fb_aggs.get("by_channel", {}).get("buckets", []):
        ch_up = bucket.get("up", {}).get("doc_count", 0)
        ch_down = bucket.get("down", {}).get("doc_count", 0)
        ch_total = ch_up + ch_down
        by_channel.append(
            {
                "channel": bucket["key"],
                "satisfaction_rate": round(ch_up / ch_total, 3) if ch_total else 0.0,
                "rated_count": ch_total,
            }
        )

    # ---- Parse outcomes ----
    oc_aggs = oc_resp.get("aggregations", {})
    outcome_counts: dict[str, int] = {}
    total_sessions = 0
    for bucket in oc_aggs.get("by_outcome", {}).get("buckets", []):
        outcome_counts[bucket["key"]] = bucket["doc_count"]
        total_sessions += bucket["doc_count"]

    success = outcome_counts.get("success", 0)
    partial = outcome_counts.get("partial", 0)
    failure = outcome_counts.get("failure", 0)
    unknown = outcome_counts.get("unknown", 0)
    success_rate = round(success / total_sessions, 3) if total_sessions else 0.0

    explicit_total = oc_aggs.get("explicit", {}).get("doc_count", 0)
    implicit_total = oc_aggs.get("implicit", {}).get("doc_count", 0)

    # Sessions with explicit positive outcome
    explicit_positive = await _count_explicit_positive(es, settings, base_filter)
    explicit_rate = round(explicit_positive / explicit_total, 3) if explicit_total else 0.0

    # Sessions with implicit success outcome
    implicit_success = await _count_implicit_success(es, settings, base_filter)
    implicit_rate = round(implicit_success / implicit_total, 3) if implicit_total else 0.0

    # ---- Top disliked tools (join feedback with tool calls via conversation) ----
    top_disliked = await _get_top_disliked_tools(es, settings, base_filter)

    return {
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "satisfaction": {
            "total_rated": total_rated,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "satisfaction_rate": satisfaction_rate,
            "by_channel": by_channel,
        },
        "outcomes": {
            "total_sessions": total_sessions,
            "success": success,
            "partial": partial,
            "failure": failure,
            "unknown": unknown,
            "success_rate": success_rate,
            "explicit_rate": explicit_rate,
            "implicit_rate": implicit_rate,
        },
        "top_disliked_tools": top_disliked,
    }


async def _safe_multi_search(es, queries: list[tuple]) -> list[dict]:
    """Run multiple ES searches concurrently."""
    import asyncio

    results = await asyncio.gather(*[es.search(index=idx, body=body) for idx, body in queries], return_exceptions=True)
    return [dict(r) if not isinstance(r, Exception) else {} for r in results]


async def _count_explicit_positive(es, settings, base_filter: list) -> int:
    try:
        resp = await es.count(
            index=settings.agent_outcomes_index,
            body={
                "query": {
                    "bool": {
                        "filter": [
                            *base_filter,
                            {"term": {"source.keyword": "explicit"}},
                            {"term": {"outcome.keyword": "success"}},
                        ]
                    }
                }
            },
        )
        return resp.get("count", 0)
    except Exception:
        return 0


async def _count_implicit_success(es, settings, base_filter: list) -> int:
    try:
        resp = await es.count(
            index=settings.agent_outcomes_index,
            body={
                "query": {
                    "bool": {
                        "filter": [
                            *base_filter,
                            {"term": {"source.keyword": "implicit"}},
                            {"term": {"outcome.keyword": "success"}},
                        ]
                    }
                }
            },
        )
        return resp.get("count", 0)
    except Exception:
        return 0


async def _get_top_disliked_tools(es, settings, base_filter: list) -> list[dict]:
    """Find tools most associated with negative feedback via conversation_id join."""
    try:
        # Can't easily join without conversation_id stored on feedback docs.
        # Returns empty until feedback_service stores conversation_id.
        return []
    except Exception:
        return []


def _empty_quality_response(start_date: datetime, end_date: datetime) -> dict:
    return {
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "satisfaction": {
            "total_rated": 0,
            "thumbs_up": 0,
            "thumbs_down": 0,
            "satisfaction_rate": 0.0,
            "by_channel": [],
        },
        "outcomes": {
            "total_sessions": 0,
            "success": 0,
            "partial": 0,
            "failure": 0,
            "unknown": 0,
            "success_rate": 0.0,
            "explicit_rate": 0.0,
            "implicit_rate": 0.0,
        },
        "top_disliked_tools": [],
    }
