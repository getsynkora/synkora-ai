"""
Wiring tests: query_docker_logs / query_datadog_logs call into log_triage and never
change behavior when triage doesn't apply (no credentials, too few lines, etc.).
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.internal_tools.log_triage import MIN_LINES_TO_TRIAGE
from src.services.agents.tool_registrations.data_analysis_tool_functions import (
    query_datadog_logs,
    query_docker_logs,
)

PRUNING_RESOLVER = "src.services.agents.context_relevance_pruner.resolve_typesafe_client_for_pruning"


def _runtime_context():
    return SimpleNamespace(db_session=MagicMock(), tenant_id=uuid.uuid4())


def _jev_client(scores: list[float]):
    from src.services.agents.internal_tools.log_triage import ANSWER_PREFIX

    client = MagicMock()
    answers = {f"{ANSWER_PREFIX}{i}": {"noul": s} for i, s in enumerate(scores)}
    client.evaluate = AsyncMock(return_value={"answers": answers})
    return client


class TestQueryDatadogLogs:
    async def _run(self, rows, *, resolver_return=None):
        service = MagicMock()
        service.query_datadog_connection = AsyncMock(
            return_value={"success": True, "rows": rows, "row_count": len(rows)}
        )
        with (
            patch(
                "src.services.data_analysis_service.DataAnalysisService",
                return_value=service,
            ),
            patch(PRUNING_RESOLVER, AsyncMock(return_value=resolver_return)) as resolver,
        ):
            result = await query_datadog_logs(
                connection_id=str(uuid.uuid4()),
                query="service:api status:error",
                from_time="now-1h",
                to_time="now",
                config={"_runtime_context": _runtime_context()},
            )
        return result, resolver

    @pytest.mark.asyncio
    async def test_no_typesafe_credentials_returns_rows_unchanged(self):
        rows = [{"message": f"m{i}"} for i in range(MIN_LINES_TO_TRIAGE + 5)]
        result, resolver = await self._run(rows, resolver_return=None)
        resolver.assert_awaited_once()
        assert result["success"] is True
        assert result["rows"] == rows
        assert "triage" not in result

    @pytest.mark.asyncio
    async def test_few_rows_are_left_unchanged_even_with_credentials(self):
        rows = [{"message": f"m{i}"} for i in range(3)]
        client = _jev_client([0.9, 0.9, 0.9])
        result, _ = await self._run(rows, resolver_return=client)
        assert result["rows"] == rows
        client.evaluate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_triage_applied_narrows_rows_and_adds_note(self):
        n = MIN_LINES_TO_TRIAGE + 5
        rows = [{"message": f"m{i}", "status": "info"} for i in range(n)]
        scores = [0.9 if i % 6 == 0 else 0.05 for i in range(n)]
        client = _jev_client(scores)

        result, _ = await self._run(rows, resolver_return=client)

        expected_kept = [rows[i] for i in range(n) if i % 6 == 0]
        assert result["rows"] == expected_kept
        assert result["returned_count"] == len(expected_kept)
        assert result["row_count"] == n  # original total is preserved
        assert result["triage"]["applied"] is True
        assert result["triage"]["total"] == n

    @pytest.mark.asyncio
    async def test_failed_query_result_is_never_touched(self):
        service = MagicMock()
        service.query_datadog_connection = AsyncMock(return_value={"success": False, "error": "boom"})
        with (
            patch("src.services.data_analysis_service.DataAnalysisService", return_value=service),
            patch(PRUNING_RESOLVER, AsyncMock()) as resolver,
        ):
            result = await query_datadog_logs(
                connection_id=str(uuid.uuid4()),
                query="q",
                from_time="now-1h",
                to_time="now",
                config={"_runtime_context": _runtime_context()},
            )
        assert result == {"success": False, "error": "boom"}
        resolver.assert_not_awaited()


class TestQueryDockerLogs:
    async def _run(self, log_blob: str, *, resolver_return=None):
        service = MagicMock()
        service.query_docker_connection = AsyncMock(
            return_value={"success": True, "data": {"container_id": "abc123", "logs": log_blob}}
        )
        with (
            patch("src.services.data_analysis_service.DataAnalysisService", return_value=service),
            patch(PRUNING_RESOLVER, AsyncMock(return_value=resolver_return)) as resolver,
        ):
            result = await query_docker_logs(
                connection_id=str(uuid.uuid4()),
                container_id="abc123",
                config={"_runtime_context": _runtime_context()},
            )
        return result, resolver

    @pytest.mark.asyncio
    async def test_no_credentials_leaves_log_blob_unchanged(self):
        blob = "\n".join(f"line {i}" for i in range(MIN_LINES_TO_TRIAGE + 5))
        result, resolver = await self._run(blob, resolver_return=None)
        resolver.assert_awaited_once()
        assert result["data"]["logs"] == blob
        assert "triage" not in result["data"]

    @pytest.mark.asyncio
    async def test_triage_applied_rewrites_logs_blob(self):
        n = MIN_LINES_TO_TRIAGE + 5
        lines = [f"line {i}" for i in range(n)]
        blob = "\n".join(lines)
        scores = [0.9 if i % 6 == 0 else 0.05 for i in range(n)]
        client = _jev_client(scores)

        result, _ = await self._run(blob, resolver_return=client)

        expected = "\n".join(lines[i] for i in range(n) if i % 6 == 0)
        assert result["data"]["logs"] == expected
        assert result["data"]["triage"]["applied"] is True

    @pytest.mark.asyncio
    async def test_blank_lines_are_dropped_before_scoring(self):
        n = MIN_LINES_TO_TRIAGE
        lines = [f"line {i}" for i in range(n)]
        blob = "\n\n".join(lines) + "\n\n"  # interleaved/trailing blank lines
        client = _jev_client([0.9] * n)

        result, _ = await self._run(blob, resolver_return=client)

        state = client.evaluate.call_args.kwargs["state"]
        assert len(state["lines"]) == n

    @pytest.mark.asyncio
    async def test_no_container_target_containers_list_result_is_untouched(self):
        service = MagicMock()
        service.query_docker_connection = AsyncMock(
            return_value={"success": True, "data": [{"id": "c1", "name": "web"}]}
        )
        with (
            patch("src.services.data_analysis_service.DataAnalysisService", return_value=service),
            patch(PRUNING_RESOLVER, AsyncMock()) as resolver,
        ):
            result = await query_docker_logs(
                connection_id=str(uuid.uuid4()),
                config={"_runtime_context": _runtime_context()},
            )
        assert result["data"] == [{"id": "c1", "name": "web"}]
        resolver.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_failed_query_result_is_never_touched(self):
        service = MagicMock()
        service.query_docker_connection = AsyncMock(return_value={"success": False, "error": "boom"})
        with (
            patch("src.services.data_analysis_service.DataAnalysisService", return_value=service),
            patch(PRUNING_RESOLVER, AsyncMock()) as resolver,
        ):
            result = await query_docker_logs(
                connection_id=str(uuid.uuid4()),
                container_id="abc123",
                config={"_runtime_context": _runtime_context()},
            )
        assert result == {"success": False, "error": "boom"}
        resolver.assert_not_awaited()
