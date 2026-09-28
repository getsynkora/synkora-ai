"""Unit tests for slack_message_triage.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agents.internal_tools.slack_message_triage import (
    MAX_MESSAGES_TO_SCORE,
    MIN_MESSAGES_TO_TRIAGE,
    SlackTriageNote,
    triage_slack_messages,
)


def _make_messages(n: int) -> list[dict]:
    return [{"text": f"message {i}", "user_name": "alice"} for i in range(n)]


def _make_client(answers: dict) -> MagicMock:
    client = MagicMock()
    client.evaluate = AsyncMock(return_value={"answers": answers, "model": "jev-latest"})
    return client


@pytest.mark.asyncio
async def test_too_few_messages_skips_triage():
    msgs = _make_messages(MIN_MESSAGES_TO_TRIAGE - 1)
    kept, note = await triage_slack_messages(client=MagicMock(), messages=msgs, source="channel")
    assert kept == msgs
    assert note.applied is False
    assert note.reason == "too_few_messages"


@pytest.mark.asyncio
async def test_too_many_messages_skips_triage():
    msgs = _make_messages(MAX_MESSAGES_TO_SCORE + 1)
    kept, note = await triage_slack_messages(client=MagicMock(), messages=msgs, source="channel")
    assert kept == msgs
    assert note.applied is False
    assert note.reason == "too_many_messages"


@pytest.mark.asyncio
async def test_no_client_skips_triage():
    msgs = _make_messages(MIN_MESSAGES_TO_TRIAGE)
    kept, note = await triage_slack_messages(client=None, messages=msgs, source="channel")
    assert kept == msgs
    assert note.applied is False
    assert note.reason == "no_typesafe_credentials"


@pytest.mark.asyncio
async def test_filters_low_score_messages():
    msgs = _make_messages(MIN_MESSAGES_TO_TRIAGE)
    # Only messages 0 and 5 score above 0.3
    answers = {f"m{i}": {"noul": 0.1} for i in range(MIN_MESSAGES_TO_TRIAGE)}
    answers["m0"] = {"noul": 0.9}
    answers["m5"] = {"noul": 0.7}
    client = _make_client(answers)

    kept, note = await triage_slack_messages(client=client, messages=msgs, source="channel")

    assert note.applied is True
    assert note.kept == 2
    assert note.total == MIN_MESSAGES_TO_TRIAGE
    assert kept == [msgs[0], msgs[5]]


@pytest.mark.asyncio
async def test_never_returns_empty_keeps_best():
    msgs = _make_messages(MIN_MESSAGES_TO_TRIAGE)
    # All scores below threshold, but m3 is highest
    answers = {f"m{i}": {"noul": 0.05} for i in range(MIN_MESSAGES_TO_TRIAGE)}
    answers["m3"] = {"noul": 0.15}
    client = _make_client(answers)

    kept, note = await triage_slack_messages(client=client, messages=msgs, source="channel")

    assert note.applied is True
    assert kept == [msgs[3]]


@pytest.mark.asyncio
async def test_timeout_fails_open():
    import asyncio

    msgs = _make_messages(MIN_MESSAGES_TO_TRIAGE)
    client = MagicMock()
    client.evaluate = AsyncMock(side_effect=asyncio.TimeoutError)

    kept, note = await triage_slack_messages(client=client, messages=msgs, source="channel", timeout=0.001)
    assert kept == msgs
    assert note.applied is False
    assert note.reason == "timeout"


@pytest.mark.asyncio
async def test_api_error_fails_open():
    msgs = _make_messages(MIN_MESSAGES_TO_TRIAGE)
    client = MagicMock()
    client.evaluate = AsyncMock(return_value={"error": "upstream error", "answers": {}})

    kept, note = await triage_slack_messages(client=client, messages=msgs, source="channel")
    assert kept == msgs
    assert note.applied is False
    assert note.reason == "api_error"


@pytest.mark.asyncio
async def test_malformed_answer_fails_open():
    msgs = _make_messages(MIN_MESSAGES_TO_TRIAGE)
    # m2 has a boolean noul — invalid per log_triage contract
    answers = {f"m{i}": {"noul": 0.8} for i in range(MIN_MESSAGES_TO_TRIAGE)}
    answers["m2"] = {"noul": True}
    client = _make_client(answers)

    kept, note = await triage_slack_messages(client=client, messages=msgs, source="channel")
    assert kept == msgs
    assert note.applied is False
    assert note.reason == "malformed_answer"


def test_triage_note_to_dict():
    note = SlackTriageNote(applied=True, total=20, scored=20, kept=8, reason="")
    d = note.to_dict()
    assert d == {"applied": True, "total": 20, "scored": 20, "kept": 8, "reason": ""}
