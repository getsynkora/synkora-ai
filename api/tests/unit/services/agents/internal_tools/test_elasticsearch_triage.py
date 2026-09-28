"""Unit tests for TypeSafe triage in Elasticsearch search tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.internal_tools.issue_triage import MIN_ISSUES_TO_TRIAGE


def _make_es_results(n: int) -> list[dict]:
    return [
        {
            "index": "test_*",
            "id": f"doc{i}",
            "score": 1.0 - i * 0.1,
            "source": {"title": f"Result {i}", "content": f"Content {i}"},
        }
        for i in range(n)
    ]


class TestElasticsearchTriage:
    @pytest.mark.asyncio
    async def test_triage_note_in_result_when_client_none(self):
        """triage field appears in result when TypeSafe client is None."""
        es_results = _make_es_results(MIN_ISSUES_TO_TRIAGE - 1)
        mock_es_response = {
            "success": True,
            "total": len(es_results),
            "results": es_results,
            "took_ms": 5,
        }

        mock_runtime = MagicMock()
        mock_runtime.tenant_id = "tenant-1"
        mock_db = AsyncMock()
        mock_runtime.db_session = mock_db

        with (
            patch(
                "src.services.agents.internal_tools.elasticsearch_tools._get_typesafe_client",
                AsyncMock(return_value=None),
            ),
            patch(
                "src.services.search.elasticsearch_service.ElasticsearchService",
            ) as MockES,
        ):
            # Mock the connection lookup
            mock_connection = MagicMock()
            mock_connection.status = "active"
            mock_connection.host = "localhost"
            mock_connection.port = 9200
            mock_connection.username = None
            mock_connection.password_encrypted = None
            mock_connection.connection_params = {}

            mock_db.execute = AsyncMock(
                return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_connection))
            )

            mock_es_instance = AsyncMock()
            mock_es_instance.search = AsyncMock(return_value=mock_es_response)
            mock_es_instance.close = AsyncMock()
            MockES.return_value = mock_es_instance

            from src.services.agents.internal_tools.elasticsearch_tools import internal_elasticsearch_search

            result = await internal_elasticsearch_search(
                connection_name="Main ES",
                index_pattern="logs_*",
                query="error crash",
                runtime_context=mock_runtime,
            )

        assert result["success"] is True
        assert "triage" in result
        assert result["triage"]["applied"] is False  # too few results

    @pytest.mark.asyncio
    async def test_triage_not_in_result_on_failure(self):
        """triage field NOT added when ES search fails."""
        mock_runtime = MagicMock()
        mock_runtime.tenant_id = "tenant-1"
        mock_db = AsyncMock()
        mock_runtime.db_session = mock_db
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

        with patch(
            "src.services.agents.internal_tools.elasticsearch_tools._get_typesafe_client",
            AsyncMock(return_value=None),
        ):
            from src.services.agents.internal_tools.elasticsearch_tools import internal_elasticsearch_search

            result = await internal_elasticsearch_search(
                connection_name="Missing",
                index_pattern="logs_*",
                query="error",
                runtime_context=mock_runtime,
            )

        assert result["success"] is False
        assert "triage" not in result
