"""Unit tests for context_relevance_pruner — the optional TypeSafe pre-pass
before conversation summarization. Every failure mode must return None
(never an empty list, never raise) so callers fall back to unpruned messages."""

from unittest.mock import AsyncMock

import pytest

from src.services.agents.context_relevance_pruner import (
    prune_irrelevant_messages,
    resolve_typesafe_client_for_pruning,
)


def _msgs(*pairs):
    return [{"role": r, "content": c} for r, c in pairs]


def _noul_answers(values: list[float]) -> dict:
    return {f"m{i}_relevant": {"type": "noul", "noul": v} for i, v in enumerate(values)}


@pytest.mark.unit
class TestPruneIrrelevantMessages:
    async def test_empty_messages_returns_none(self):
        client = AsyncMock()
        result = await prune_irrelevant_messages([], [], client)
        assert result is None
        client.evaluate.assert_not_called()

    async def test_no_client_returns_none(self):
        result = await prune_irrelevant_messages(_msgs(("user", "hi")), [], None)
        assert result is None

    async def test_too_many_candidates_skips_pruning(self):
        messages = _msgs(*[("user", f"msg {i}") for i in range(61)])
        client = AsyncMock()
        result = await prune_irrelevant_messages(messages, [], client)
        assert result is None
        client.evaluate.assert_not_called()

    async def test_drops_irrelevant_keeps_relevant(self):
        messages = _msgs(("user", "what's the weather"), ("assistant", "sunny"), ("user", "please book a flight"))
        client = AsyncMock()
        client.evaluate.return_value = {"answers": _noul_answers([0.1, 0.1, 0.9])}
        result = await prune_irrelevant_messages(messages, [], client)
        assert result == [messages[2]]

    async def test_all_relevant_returns_all(self):
        messages = _msgs(("user", "a"), ("assistant", "b"))
        client = AsyncMock()
        client.evaluate.return_value = {"answers": _noul_answers([0.8, 0.9])}
        result = await prune_irrelevant_messages(messages, [], client)
        assert result == messages

    async def test_all_irrelevant_returns_none_not_empty_list(self):
        messages = _msgs(("user", "a"), ("assistant", "b"))
        client = AsyncMock()
        client.evaluate.return_value = {"answers": _noul_answers([0.05, 0.1])}
        result = await prune_irrelevant_messages(messages, [], client)
        assert result is None

    async def test_ambiguous_score_keeps_the_message(self):
        """Anything not confidently irrelevant (>= _DROP_ONLY_BELOW) must be kept —
        biased toward retaining conversation history over dropping it."""
        messages = _msgs(("user", "maybe relevant"))
        client = AsyncMock()
        client.evaluate.return_value = {"answers": _noul_answers([0.5])}
        result = await prune_irrelevant_messages(messages, [], client)
        assert result == messages

    async def test_typesafe_error_response_returns_none(self):
        messages = _msgs(("user", "a"))
        client = AsyncMock()
        client.evaluate.return_value = {"error": "not configured", "answers": {}}
        result = await prune_irrelevant_messages(messages, [], client)
        assert result is None

    async def test_malformed_answer_fails_closed_to_none(self):
        messages = _msgs(("user", "a"), ("assistant", "b"))
        client = AsyncMock()
        # Missing the second answer entirely — must not partially prune.
        client.evaluate.return_value = {"answers": {"m0_relevant": {"type": "noul", "noul": 0.9}}}
        result = await prune_irrelevant_messages(messages, [], client)
        assert result is None

    async def test_client_raises_returns_none(self):
        messages = _msgs(("user", "a"))
        client = AsyncMock()
        client.evaluate.side_effect = RuntimeError("network error")
        result = await prune_irrelevant_messages(messages, [], client)
        assert result is None

    async def test_preserves_original_order(self):
        messages = _msgs(("user", "keep1"), ("assistant", "drop"), ("user", "keep2"))
        client = AsyncMock()
        client.evaluate.return_value = {"answers": _noul_answers([0.9, 0.1, 0.9])}
        result = await prune_irrelevant_messages(messages, [], client)
        assert result == [messages[0], messages[2]]

    async def test_sends_recent_context_and_candidates_in_state(self):
        messages = _msgs(("user", "old topic"))
        recent = _msgs(("user", "new topic"))
        client = AsyncMock()
        client.evaluate.return_value = {"answers": _noul_answers([0.9])}
        await prune_irrelevant_messages(messages, recent, client)

        _, kwargs = client.evaluate.call_args
        state = kwargs["state"]
        assert "new topic" in state["current_context"]
        assert state["candidate_messages"]["m0"]["content"] == "old topic"
        assert "m0_relevant" in kwargs["questions"]


@pytest.mark.unit
class TestResolveTypesafeClientForPruning:
    async def test_no_tenant_id_returns_none(self):
        result = await resolve_typesafe_client_for_pruning(None, object())
        assert result is None

    async def test_no_db_returns_none(self):
        result = await resolve_typesafe_client_for_pruning("11111111-1111-1111-1111-111111111111", None)
        assert result is None

    async def test_invalid_tenant_id_returns_none_not_raise(self):
        result = await resolve_typesafe_client_for_pruning("not-a-uuid", object())
        assert result is None
