"""Unit tests for ContextManager.maybe_summarize_old_messages, focused on the
optional TypeSafe pruning pre-pass: it must never change behavior unless a
working typesafe_client is explicitly passed in and successfully prunes."""

from unittest.mock import AsyncMock

import pytest

from src.services.agents.context_manager import ContextConfig, ContextManager


def _msgs(n: int, prefix: str = "msg") -> list[dict[str, str]]:
    return [{"role": "user", "content": f"{prefix} {i}"} for i in range(n)]


def _manager() -> ContextManager:
    config = ContextConfig(
        auto_summarize=True,
        summarize_threshold_messages=5,
        summarize_threshold_tokens=10_000_000,  # keep the token path out of play
        keep_recent_messages=2,
        incremental_threshold_messages=5,
    )
    return ContextManager(config)


@pytest.mark.unit
class TestMaybeSummarizeOldMessagesBaseline:
    """No typesafe_client passed — must behave exactly as before this feature existed."""

    async def test_no_typesafe_client_uses_all_old_messages(self):
        manager = _manager()
        llm_client = AsyncMock()
        llm_client.generate_content.return_value = "a summary"

        messages = _msgs(6)
        recent, summary = await manager.maybe_summarize_old_messages(messages, llm_client)

        assert recent == messages[-2:]
        assert summary == "a summary"
        # Every one of the 4 older messages must have reached the summarizer's prompt.
        prompt = llm_client.generate_content.call_args[0][0]
        for i in range(4):
            assert f"msg {i}" in prompt

    async def test_typesafe_client_none_is_identical_to_omitted(self):
        manager = _manager()
        llm_client = AsyncMock()
        llm_client.generate_content.return_value = "a summary"
        messages = _msgs(6)

        recent_a, summary_a = await manager.maybe_summarize_old_messages(messages, llm_client, typesafe_client=None)
        recent_b, summary_b = await manager.maybe_summarize_old_messages(messages, llm_client)

        assert recent_a == recent_b
        assert summary_a == summary_b


@pytest.mark.unit
class TestMaybeSummarizeOldMessagesWithPruning:
    async def test_successful_pruning_shrinks_what_gets_summarized(self, monkeypatch):
        manager = _manager()
        llm_client = AsyncMock()
        llm_client.generate_content.return_value = "a summary"
        messages = _msgs(6)  # 4 old + 2 recent
        old_messages = messages[:4]

        pruned = old_messages[:1]  # pretend only 1 of 4 was relevant

        async def fake_prune(to_summarize, recent, client):
            assert to_summarize == old_messages
            return pruned

        monkeypatch.setattr(
            "src.services.agents.context_relevance_pruner.prune_irrelevant_messages", fake_prune
        )

        fake_typesafe_client = object()
        recent, summary = await manager.maybe_summarize_old_messages(
            messages, llm_client, typesafe_client=fake_typesafe_client
        )

        assert recent == messages[-2:]
        prompt = llm_client.generate_content.call_args[0][0]
        assert "msg 0" in prompt
        assert "msg 1" not in prompt  # pruned out — never reached the summarizer

    async def test_pruning_failure_falls_back_to_all_old_messages(self, monkeypatch):
        manager = _manager()
        llm_client = AsyncMock()
        llm_client.generate_content.return_value = "a summary"
        messages = _msgs(6)

        async def fake_prune(to_summarize, recent, client):
            return None  # pruning couldn't run — must not change anything

        monkeypatch.setattr(
            "src.services.agents.context_relevance_pruner.prune_irrelevant_messages", fake_prune
        )

        recent, summary = await manager.maybe_summarize_old_messages(
            messages, llm_client, typesafe_client=object()
        )

        prompt = llm_client.generate_content.call_args[0][0]
        for i in range(4):
            assert f"msg {i}" in prompt

    async def test_pruning_exception_is_swallowed_and_falls_back(self, monkeypatch):
        manager = _manager()
        llm_client = AsyncMock()
        llm_client.generate_content.return_value = "a summary"
        messages = _msgs(6)

        async def raising_prune(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(
            "src.services.agents.context_relevance_pruner.prune_irrelevant_messages", raising_prune
        )

        # Must not raise, and must still summarize successfully with the original messages.
        recent, summary = await manager.maybe_summarize_old_messages(
            messages, llm_client, typesafe_client=object()
        )
        assert summary == "a summary"
        prompt = llm_client.generate_content.call_args[0][0]
        for i in range(4):
            assert f"msg {i}" in prompt
