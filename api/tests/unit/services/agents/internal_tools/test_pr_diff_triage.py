"""Unit tests for pr_diff_triage.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agents.internal_tools.pr_diff_triage import (
    ANSWER_PREFIX,
    MAX_FILES_TO_SCORE,
    MIN_FILES_TO_TRIAGE,
    PrDiffTriageNote,
    _split_diff,
    triage_pr_diff,
)


def _make_diff(file_paths: list[str]) -> str:
    """Build a minimal but structurally valid unified diff with given file paths."""
    parts = []
    for path in file_paths:
        parts.append(
            f"diff --git a/{path} b/{path}\n"
            f"index 000000..111111 100644\n"
            f"--- a/{path}\n"
            f"+++ b/{path}\n"
            f"@@ -1,1 +1,2 @@\n"
            f" existing line\n"
            f"+new line in {path}\n"
        )
    return "".join(parts)


def _make_client(scores: list[float] | None = None, *, result: dict | None = None) -> MagicMock:
    client = MagicMock()
    if result is not None:
        payload = result
    else:
        answers = {f"{ANSWER_PREFIX}{i}": {"type": "noul", "noul": s} for i, s in enumerate(scores or [])}
        payload = {"answers": answers}
    client.evaluate = AsyncMock(return_value=payload)
    return client


class TestSplitDiff:
    def test_splits_into_per_file_hunks(self):
        diff = _make_diff(["src/a.py", "src/b.py", "README.md"])
        hunks = _split_diff(diff)
        assert len(hunks) == 3
        assert hunks[0][0] == "src/a.py"
        assert hunks[1][0] == "src/b.py"
        assert hunks[2][0] == "README.md"

    def test_empty_diff_returns_empty(self):
        assert _split_diff("") == []

    def test_diff_without_git_header_returns_empty(self):
        assert _split_diff("some random text\nno diff headers") == []


class TestSkipConditions:
    @pytest.mark.asyncio
    async def test_no_client_fails_open(self):
        diff = _make_diff([f"file{i}.py" for i in range(MIN_FILES_TO_TRIAGE + 1)])
        kept_diff, note = await triage_pr_diff(None, diff, pr_title="Fix memory leak")
        assert kept_diff == diff
        assert note.reason == "no_typesafe_credentials"
        assert note.applied is False

    @pytest.mark.asyncio
    async def test_too_few_files_skips(self):
        diff = _make_diff([f"file{i}.py" for i in range(MIN_FILES_TO_TRIAGE - 1)])
        client = _make_client([0.9] * (MIN_FILES_TO_TRIAGE - 1))
        kept_diff, note = await triage_pr_diff(client, diff, pr_title="Fix")
        assert kept_diff == diff
        assert note.reason == "too_few_files"
        client.evaluate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_too_many_files_skips(self):
        diff = _make_diff([f"file{i}.py" for i in range(MAX_FILES_TO_SCORE + 1)])
        client = _make_client([0.9] * (MAX_FILES_TO_SCORE + 1))
        kept_diff, note = await triage_pr_diff(client, diff, pr_title="Fix")
        assert kept_diff == diff
        assert note.reason == "too_many_files"
        client.evaluate.assert_not_awaited()


class TestFailOpen:
    @pytest.mark.asyncio
    async def test_timeout_returns_original_diff(self):
        diff = _make_diff([f"file{i}.py" for i in range(MIN_FILES_TO_TRIAGE + 1)])
        client = MagicMock()
        client.evaluate = AsyncMock(side_effect=TimeoutError())
        kept_diff, note = await triage_pr_diff(client, diff, pr_title="Fix")
        assert kept_diff == diff
        assert note.reason == "timeout"

    @pytest.mark.asyncio
    async def test_api_error_returns_original_diff(self):
        diff = _make_diff([f"file{i}.py" for i in range(MIN_FILES_TO_TRIAGE + 1)])
        client = _make_client(result={"error": "server_error"})
        kept_diff, note = await triage_pr_diff(client, diff, pr_title="Fix")
        assert kept_diff == diff
        assert note.reason == "api_error"

    @pytest.mark.asyncio
    async def test_exception_returns_original_diff(self):
        diff = _make_diff([f"file{i}.py" for i in range(MIN_FILES_TO_TRIAGE + 1)])
        client = MagicMock()
        client.evaluate = AsyncMock(side_effect=RuntimeError("connection reset"))
        kept_diff, note = await triage_pr_diff(client, diff, pr_title="Fix")
        assert kept_diff == diff
        assert note.reason == "error"
        assert note.applied is False


class TestTriageApplied:
    @pytest.mark.asyncio
    async def test_filters_low_score_files(self):
        files = [f"src/module_{i}.py" for i in range(8)]
        diff = _make_diff(files)
        # Only files 0 and 3 score above threshold
        scores = [0.9 if i in (0, 3) else 0.05 for i in range(8)]
        client = _make_client(scores)
        kept_diff, note = await triage_pr_diff(client, diff, pr_title="Fix memory leak")
        assert note.applied is True
        assert note.total_files == 8
        assert note.kept_files == 2
        assert "src/module_0.py" in kept_diff
        assert "src/module_3.py" in kept_diff
        assert "src/module_1.py" not in kept_diff

    @pytest.mark.asyncio
    async def test_floor_guarantee_keeps_at_least_one_file(self):
        files = [f"src/file_{i}.py" for i in range(7)]
        diff = _make_diff(files)
        scores = [0.01] * 7
        scores[2] = 0.05  # highest but still below threshold
        client = _make_client(scores)
        kept_diff, note = await triage_pr_diff(client, diff, pr_title="Refactor")
        assert note.kept_files == 1
        assert "src/file_2.py" in kept_diff

    @pytest.mark.asyncio
    async def test_note_to_dict_has_expected_keys(self):
        files = [f"file{i}.py" for i in range(7)]
        diff = _make_diff(files)
        client = _make_client([0.9] * 7)
        _, note = await triage_pr_diff(client, diff, pr_title="Test")
        d = note.to_dict()
        assert set(d.keys()) == {"applied", "total_files", "kept_files", "reason"}
