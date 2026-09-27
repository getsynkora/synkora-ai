"""Unit tests for Jev-based log-line triage."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agents.internal_tools.log_triage import (
    ANSWER_PREFIX,
    MAX_LINES_TO_SCORE,
    MIN_LINES_TO_TRIAGE,
    TriageNote,
    triage_log_lines,
)


def _client(scores: list[float] | None = None, *, result: dict | None = None):
    client = MagicMock()
    if result is not None:
        payload = result
    else:
        answers = {f"{ANSWER_PREFIX}{i}": {"type": "noul", "noul": s} for i, s in enumerate(scores or [])}
        payload = {"answers": answers}
    client.evaluate = AsyncMock(return_value=payload)
    return client


def _lines(n: int, noisy: str = "healthcheck ok") -> list[str]:
    return [noisy for _ in range(n)]


class TestSkipConditions:
    @pytest.mark.asyncio
    async def test_no_client_fails_open(self):
        lines = _lines(MIN_LINES_TO_TRIAGE + 1)
        kept, note = await triage_log_lines(None, lines, source="docker_logs")
        assert kept == lines
        assert note == TriageNote(applied=False, total=len(lines), reason="no_typesafe_credentials")

    @pytest.mark.asyncio
    async def test_too_few_lines_skips_without_calling_client(self):
        lines = _lines(MIN_LINES_TO_TRIAGE - 1)
        client = _client([0.9] * len(lines))
        kept, note = await triage_log_lines(client, lines, source="docker_logs")
        assert kept == lines
        assert note.reason == "too_few_lines"
        client.evaluate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_too_many_lines_skips_without_calling_client(self):
        lines = _lines(MAX_LINES_TO_SCORE + 1)
        client = _client([0.9] * len(lines))
        kept, note = await triage_log_lines(client, lines, source="docker_logs")
        assert kept == lines
        assert note.reason == "too_many_lines"
        client.evaluate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_lines_is_a_noop(self):
        client = _client([])
        kept, note = await triage_log_lines(client, [], source="docker_logs")
        assert kept == []
        assert note.reason == "too_few_lines"
        client.evaluate.assert_not_awaited()


class TestTriageApplied:
    @pytest.mark.asyncio
    async def test_keeps_only_significant_lines(self):
        n = 30
        lines = [f"line {i}" for i in range(n)]
        scores = [0.9 if i % 5 == 0 else 0.05 for i in range(n)]
        client = _client(scores)

        kept, note = await triage_log_lines(client, lines, source="docker_logs")

        assert note.applied is True
        assert note.total == n
        assert note.kept == len(kept) == 6
        assert kept == [lines[i] for i in range(n) if i % 5 == 0]

    @pytest.mark.asyncio
    async def test_never_returns_empty_keeps_top_scoring_line(self):
        n = 30
        lines = [f"line {i}" for i in range(n)]
        scores = [0.01] * n
        scores[7] = 0.2  # highest, still below the default threshold
        client = _client(scores)

        kept, note = await triage_log_lines(client, lines, source="docker_logs")

        assert note.applied is True
        assert kept == [lines[7]]

    @pytest.mark.asyncio
    async def test_dict_entries_use_message_field(self):
        n = MIN_LINES_TO_TRIAGE
        lines = [{"message": f"m{i}", "service": "api"} for i in range(n)]
        client = _client([0.9] * n)

        await triage_log_lines(client, lines, source="datadog_logs", query_context="service:api")

        state = client.evaluate.call_args.kwargs["state"]
        assert state["lines"][f"{ANSWER_PREFIX}0"] == "m0"
        assert state["source"] == "datadog_logs"
        assert state["query_context"] == "service:api"

    @pytest.mark.asyncio
    async def test_dict_entry_without_message_falls_back_to_kv(self):
        client = _client([0.9] * MIN_LINES_TO_TRIAGE)
        lines = [{"service": "api", "status": "error"} for _ in range(MIN_LINES_TO_TRIAGE)]
        await triage_log_lines(client, lines, source="datadog_logs")
        text = client.evaluate.call_args.kwargs["state"]["lines"][f"{ANSWER_PREFIX}0"]
        assert "service=api" in text and "status=error" in text

    @pytest.mark.asyncio
    async def test_untrusted_data_warning_in_question(self):
        client = _client([0.9] * MIN_LINES_TO_TRIAGE)
        await triage_log_lines(client, _lines(MIN_LINES_TO_TRIAGE), source="docker_logs")
        questions = client.evaluate.call_args.kwargs["questions"]
        assert all("untrusted" in q["question"] for q in questions.values())
        assert all(q["type"] == "noul" for q in questions.values())

    @pytest.mark.asyncio
    async def test_long_line_is_truncated_in_state(self):
        client = _client([0.9] * MIN_LINES_TO_TRIAGE)
        lines = ["x" * 5000] * MIN_LINES_TO_TRIAGE
        await triage_log_lines(client, lines, source="docker_logs")
        text = client.evaluate.call_args.kwargs["state"]["lines"][f"{ANSWER_PREFIX}0"]
        assert len(text) == 400


class TestFailOpen:
    @pytest.mark.asyncio
    async def test_timeout_fails_open(self):
        client = MagicMock()

        async def slow(**_):
            await asyncio.sleep(1)

        client.evaluate = slow
        lines = _lines(MIN_LINES_TO_TRIAGE)
        kept, note = await triage_log_lines(client, lines, source="docker_logs", timeout=0.01)
        assert kept == lines
        assert note.reason == "timeout"

    @pytest.mark.asyncio
    async def test_exception_fails_open(self):
        client = MagicMock()
        client.evaluate = AsyncMock(side_effect=RuntimeError("network"))
        lines = _lines(MIN_LINES_TO_TRIAGE)
        kept, note = await triage_log_lines(client, lines, source="docker_logs")
        assert kept == lines
        assert note.reason == "error"

    @pytest.mark.asyncio
    async def test_api_error_fails_open(self):
        client = _client(result={"error": "boom", "answers": {}})
        lines = _lines(MIN_LINES_TO_TRIAGE)
        kept, note = await triage_log_lines(client, lines, source="docker_logs")
        assert kept == lines
        assert note.reason == "api_error"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_result",
        [
            {"answers": {}},
            {"answers": {f"{ANSWER_PREFIX}0": "yes"}},
            {"answers": {f"{ANSWER_PREFIX}0": {"noul": "0.9"}}},
            {"answers": {f"{ANSWER_PREFIX}0": {"noul": 1.5}}},
            {"answers": {f"{ANSWER_PREFIX}0": {"noul": -0.1}}},
            {"answers": {f"{ANSWER_PREFIX}0": {"noul": True}}},
            {},
        ],
    )
    async def test_malformed_answer_fails_open_for_whole_batch(self, bad_result):
        n = MIN_LINES_TO_TRIAGE
        lines = _lines(n)
        client = _client(result=bad_result)
        kept, note = await triage_log_lines(client, lines, source="docker_logs")
        assert kept == lines
        assert note.reason == "malformed_answer"

    @pytest.mark.asyncio
    async def test_one_bad_answer_among_good_ones_fails_the_whole_batch(self):
        n = MIN_LINES_TO_TRIAGE
        answers = {f"{ANSWER_PREFIX}{i}": {"noul": 0.9} for i in range(n)}
        answers[f"{ANSWER_PREFIX}{n - 1}"] = {"noul": None}
        client = _client(result={"answers": answers})
        lines = _lines(n)
        kept, note = await triage_log_lines(client, lines, source="docker_logs")
        assert kept == lines
        assert note.reason == "malformed_answer"


class TestTriageNote:
    def test_to_dict_shape(self):
        note = TriageNote(applied=True, total=30, scored=30, kept=6, reason="")
        assert note.to_dict() == {"applied": True, "total": 30, "scored": 30, "kept": 6, "reason": ""}
