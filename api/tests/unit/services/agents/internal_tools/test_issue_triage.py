"""Unit tests for issue_triage.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agents.internal_tools.issue_triage import (
    ANSWER_PREFIX,
    MAX_ISSUES_TO_SCORE,
    MIN_ISSUES_TO_TRIAGE,
    IssueTriageNote,
    triage_issues,
)


def _make_issues(n: int, title_prefix: str = "Bug") -> list[dict]:
    return [{"title": f"{title_prefix} #{i}", "summary": f"Description of {title_prefix} #{i}"} for i in range(n)]


def _make_client(scores: list[float] | None = None, *, result: dict | None = None) -> MagicMock:
    client = MagicMock()
    if result is not None:
        payload = result
    else:
        answers = {f"{ANSWER_PREFIX}{i}": {"type": "noul", "noul": s} for i, s in enumerate(scores or [])}
        payload = {"answers": answers}
    client.evaluate = AsyncMock(return_value=payload)
    return client


class TestSkipConditions:
    @pytest.mark.asyncio
    async def test_no_client_fails_open(self):
        issues = _make_issues(MIN_ISSUES_TO_TRIAGE + 1)
        kept, note = await triage_issues(None, issues, query_context="outage")
        assert kept == issues
        assert note.reason == "no_typesafe_credentials"
        assert note.applied is False

    @pytest.mark.asyncio
    async def test_too_few_issues_skips(self):
        issues = _make_issues(MIN_ISSUES_TO_TRIAGE - 1)
        client = _make_client([0.9] * len(issues))
        kept, note = await triage_issues(client, issues, query_context="outage")
        assert kept == issues
        assert note.reason == "too_few_issues"
        client.evaluate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_too_many_issues_skips(self):
        issues = _make_issues(MAX_ISSUES_TO_SCORE + 1)
        client = _make_client([0.9] * (MAX_ISSUES_TO_SCORE + 1))
        kept, note = await triage_issues(client, issues, query_context="outage")
        assert kept == issues
        assert note.reason == "too_many_issues"
        client.evaluate.assert_not_awaited()


class TestFailOpen:
    @pytest.mark.asyncio
    async def test_timeout_returns_all_issues(self):
        issues = _make_issues(MIN_ISSUES_TO_TRIAGE + 1)
        client = MagicMock()
        client.evaluate = AsyncMock(side_effect=TimeoutError())
        kept, note = await triage_issues(client, issues, query_context="crash")
        assert kept == issues
        assert note.reason == "timeout"
        assert note.applied is False

    @pytest.mark.asyncio
    async def test_api_error_returns_all_issues(self):
        issues = _make_issues(MIN_ISSUES_TO_TRIAGE + 1)
        client = _make_client(result={"error": "server_error"})
        kept, note = await triage_issues(client, issues, query_context="crash")
        assert kept == issues
        assert note.reason == "api_error"

    @pytest.mark.asyncio
    async def test_malformed_answer_returns_all_issues(self):
        issues = _make_issues(MIN_ISSUES_TO_TRIAGE + 1)
        client = _make_client(result={"answers": {f"{ANSWER_PREFIX}0": {"noul": "bad"}}})
        kept, note = await triage_issues(client, issues, query_context="crash")
        assert kept == issues
        assert note.reason == "malformed_answer"


class TestTriageApplied:
    @pytest.mark.asyncio
    async def test_filters_low_score_issues(self):
        n = 8
        issues = _make_issues(n)
        # Only issues 0 and 4 score above threshold
        scores = [0.9 if i in (0, 4) else 0.05 for i in range(n)]
        client = _make_client(scores)
        kept, note = await triage_issues(client, issues, query_context="memory leak")
        assert note.applied is True
        assert note.total == n
        assert note.kept == 2
        assert kept == [issues[0], issues[4]]

    @pytest.mark.asyncio
    async def test_floor_guarantee_keeps_at_least_one(self):
        """Never returns empty list even if all scores below threshold."""
        n = 7
        issues = _make_issues(n)
        scores = [0.01] * n
        scores[3] = 0.05  # highest score, but still below 0.3
        client = _make_client(scores)
        kept, note = await triage_issues(client, issues, query_context="crash")
        assert len(kept) == 1
        assert kept[0] == issues[3]
        assert note.applied is True

    @pytest.mark.asyncio
    async def test_note_to_dict_has_expected_keys(self):
        n = 7
        issues = _make_issues(n)
        scores = [0.9] * n
        client = _make_client(scores)
        _, note = await triage_issues(client, issues, query_context="test")
        d = note.to_dict()
        assert set(d.keys()) == {"applied", "total", "scored", "kept", "reason"}
