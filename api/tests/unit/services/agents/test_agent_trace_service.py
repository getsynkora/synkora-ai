"""Tests for agent_trace_service's _safe_es_search: a missing index must mean
"no trace data yet" (empty result), not a 503 service-unavailable error.

Regression for: production Agent Lens overview returned 503 "Analytics service
temporarily unavailable" when the real cause was elasticsearch.NotFoundError
(index_not_found_exception) on a brand-new agent/tenant with no events written
yet -- a normal state, not an outage.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.services.agents.agent_trace_service import (
    _empty_agg_result,
    _empty_search_response,
    _safe_es_search,
)

OVERVIEW_BODY = {
    "size": 0,
    "query": {"bool": {"filter": []}},
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

SESSIONS_BODY = {
    "size": 0,
    "aggs": {
        "total_sessions": {"cardinality": {"field": "conversation_id"}},
        "by_conversation": {
            "terms": {"field": "conversation_id", "size": 10000},
            "aggs": {
                "first_ts": {"min": {"field": "timestamp"}},
                "meta": {
                    "filter": {"term": {"event_type": "user_message"}},
                    "aggs": {"top": {"top_hits": {"size": 1}}},
                },
            },
        },
    },
}


class TestEmptySearchResponseShape:
    def test_matches_get_overview_access_pattern(self):
        """Every direct dict access get_overview() performs must succeed with no KeyError."""
        resp = _empty_search_response(OVERVIEW_BODY)
        aggs = resp["aggregations"]
        llm = aggs["llm_stats"]
        tool = aggs["tool_stats"]

        assert int(aggs["total_sessions"]["value"]) == 0
        assert int(llm["count"]["value"]) == 0
        assert int(llm["input_tokens"]["value"] or 0) == 0
        assert int(llm["output_tokens"]["value"] or 0) == 0
        assert int(llm["avg_latency"]["value"] or 0) == 0
        assert int(tool["total"]["value"]) == 0
        assert int(tool["failed"]["count"]["value"]) == 0
        assert int(tool["avg_duration"]["value"] or 0) == 0

    def test_matches_get_sessions_bucket_access_pattern(self):
        """terms + nested filter/top_hits sub-aggs resolve to an empty, sliceable bucket list."""
        resp = _empty_search_response(SESSIONS_BODY)
        aggs = resp["aggregations"]
        assert int(aggs["total_sessions"]["value"]) == 0
        buckets = aggs["by_conversation"]["buckets"]
        assert buckets == []
        assert buckets[0:20] == []

    def test_hits_shape_is_a_valid_empty_result(self):
        resp = _empty_search_response(OVERVIEW_BODY)
        assert resp["hits"]["total"]["value"] == 0
        assert resp["hits"]["hits"] == []
        assert resp["_shards"]["total"] == 0

    def test_unrecognized_agg_type_does_not_raise(self):
        """An agg type not in any known bucket shouldn't crash synthesis, just produce a minimal stub."""
        body = {"aggs": {"weird": {"some_future_agg_type": {"field": "x"}}}}
        result = _empty_agg_result(body["aggs"]["weird"])
        assert result == {}


class TestSafeEsSearch:
    @pytest.mark.asyncio
    async def test_not_found_error_returns_empty_result_not_503(self):
        """The actual production bug: NotFoundError (missing index) must not surface as 503."""
        from elasticsearch import NotFoundError

        es = AsyncMock()
        es.search = AsyncMock(
            side_effect=NotFoundError(404, "index_not_found_exception", "no such index [agent-session-events]")
        )

        result = await _safe_es_search(es, index="agent-session-events", body=OVERVIEW_BODY)

        assert result["hits"]["total"]["value"] == 0
        assert int(result["aggregations"]["total_sessions"]["value"]) == 0

    @pytest.mark.asyncio
    async def test_connection_error_still_raises_503(self):
        """A genuine outage must still surface as 503 -- only index-not-found is treated as empty."""
        from elasticsearch import ConnectionError as ESConnectionError

        es = AsyncMock()
        es.search = AsyncMock(side_effect=ESConnectionError("connection refused"))

        with pytest.raises(HTTPException) as exc_info:
            await _safe_es_search(es, index="agent-session-events", body=OVERVIEW_BODY)

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_successful_search_passes_through_unchanged(self):
        real_response = {"hits": {"total": {"value": 5}, "hits": []}, "aggregations": {"x": {"value": 5}}}
        es = AsyncMock()
        es.search = AsyncMock(return_value=real_response)

        result = await _safe_es_search(es, index="agent-session-events", body=OVERVIEW_BODY)

        assert result is real_response
