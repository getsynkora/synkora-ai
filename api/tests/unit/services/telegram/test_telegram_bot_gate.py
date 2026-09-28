"""Unit tests for TypeSafe gate integration in Telegram polling and webhook services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.telegram.telegram_polling_service import TelegramPollingService
from src.services.telegram.telegram_webhook_service import TelegramWebhookService


def _make_telegram_bot():
    bot = MagicMock()
    bot.id = uuid4()
    bot.agent_id = uuid4()
    bot.tenant_id = uuid4()
    bot.bot_name = "TestBot"
    bot.bot_username = "testbot"
    bot.bot_token = "encrypted_token"
    return bot


def _make_agent():
    agent = MagicMock()
    agent.agent_name = "test-agent"
    agent.description = "A test agent"
    agent.tools_config = {}
    agent.slug = "test-agent"
    return agent


def _make_mock_db(agent=None):
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.get = AsyncMock(return_value=agent or _make_agent())
    db.execute = AsyncMock()
    return db


def _skip_decision():
    d = MagicMock()
    d.action = "skip"
    d.reason = "actionable 0.05 < 0.25"
    d.actionable = 0.05
    d.latency_ms = 3
    return d


def _run_decision():
    d = MagicMock()
    d.action = "run"
    d.reason = "actionable 0.90 >= 0.25"
    d.actionable = 0.90
    d.latency_ms = 3
    return d


class TestPollingGate:
    @pytest.mark.asyncio
    async def test_skip_decision_returns_before_saving_message(self):
        """When gate returns skip, _handle_message returns before flushing user message."""
        mock_db = _make_mock_db()
        service = TelegramPollingService(db_session=mock_db)

        mock_conv = MagicMock()
        mock_conv.id = uuid4()
        mock_conv.increment_message_count = MagicMock()
        service._get_or_create_conversation = AsyncMock(return_value=mock_conv)

        telegram_bot = _make_telegram_bot()
        mock_context = MagicMock()
        mock_context.bot = AsyncMock()

        with patch(
            "src.services.agents.context_relevance_pruner.resolve_typesafe_client_for_pruning",
            AsyncMock(return_value=None),
        ), patch(
            "src.services.slack.slack_bot_gate.evaluate_slack_message",
            AsyncMock(return_value=_skip_decision()),
        ):
            await service._handle_message(
                telegram_bot=telegram_bot,
                chat_id=123,
                chat_type="private",
                chat_title=None,
                user_id=456,
                user_name="testuser",
                user_first_name="Test",
                user_last_name=None,
                text="routine noise",
                message_id=789,
                context=mock_context,
            )

        # Gate returned skip — message should NOT have been flushed
        mock_db.flush.assert_not_called()
        # No message sent to Telegram
        mock_context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_fail_open_when_client_none(self):
        """When TypeSafe client is None, gate fails open (run decision)."""
        mock_db = _make_mock_db()
        service = TelegramPollingService(db_session=mock_db)

        mock_conv = MagicMock()
        mock_conv.id = uuid4()
        mock_conv.increment_message_count = MagicMock()
        service._get_or_create_conversation = AsyncMock(return_value=mock_conv)

        telegram_bot = _make_telegram_bot()
        mock_context = MagicMock()
        mock_context.bot = AsyncMock()

        # Patch evaluate_slack_message to return run (fail-open path when client=None)
        with patch(
            "src.services.agents.context_relevance_pruner.resolve_typesafe_client_for_pruning",
            AsyncMock(return_value=None),
        ), patch(
            "src.services.slack.slack_bot_gate.evaluate_slack_message",
            AsyncMock(return_value=_run_decision()),
        ), patch(
            "src.services.agents.chat_stream_service.ChatStreamService",
            MagicMock(return_value=MagicMock(stream_agent_response=AsyncMock(return_value=_empty_aiter()))),
        ):
            # This will fail when trying to stream, but we only care that flush was called (gate passed)
            try:
                await service._handle_message(
                    telegram_bot=telegram_bot,
                    chat_id=123,
                    chat_type="private",
                    chat_title=None,
                    user_id=456,
                    user_name="testuser",
                    user_first_name="Test",
                    user_last_name=None,
                    text="help me with something",
                    message_id=789,
                    context=mock_context,
                )
            except Exception:
                pass  # Expected — agent infrastructure not fully mocked

        # Gate passed — message WAS flushed before stream attempt
        mock_db.flush.assert_called()


class TestWebhookGate:
    @pytest.mark.asyncio
    async def test_skip_decision_returns_before_saving_message(self):
        """When gate returns skip, webhook _handle_message returns before commit."""
        mock_db = _make_mock_db()
        service = TelegramWebhookService(db_session=mock_db)

        mock_conv = MagicMock()
        mock_conv.id = uuid4()
        mock_conv.increment_message_count = MagicMock()
        service._get_or_create_conversation = AsyncMock(return_value=mock_conv)

        telegram_bot = _make_telegram_bot()
        mock_bot_api = AsyncMock()

        with patch(
            "src.services.agents.context_relevance_pruner.resolve_typesafe_client_for_pruning",
            AsyncMock(return_value=None),
        ), patch(
            "src.services.slack.slack_bot_gate.evaluate_slack_message",
            AsyncMock(return_value=_skip_decision()),
        ):
            await service._handle_message(
                telegram_bot=telegram_bot,
                bot=mock_bot_api,
                chat_id=123,
                chat_type="private",
                chat_title=None,
                user_id=456,
                user_name="testuser",
                user_first_name="Test",
                user_last_name=None,
                text="routine noise",
                message_id=789,
            )

        # Gate returned skip — message should NOT have been committed
        mock_db.commit.assert_not_called()
        # No message sent via bot API
        mock_bot_api.send_message.assert_not_called()


def _empty_aiter():
    """Return an async iterator that yields nothing."""
    async def _gen():
        return
        yield  # noqa: unreachable

    return _gen()
