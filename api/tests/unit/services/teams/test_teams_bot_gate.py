"""Unit tests for TypeSafe gate in Teams webhook service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.teams.teams_webhook_service import TeamsWebhookService


def _make_teams_bot():
    bot = MagicMock()
    bot.id = uuid4()
    bot.agent_id = uuid4()
    bot.tenant_id = uuid4()
    bot.bot_id = "bot123"
    bot.is_active = True
    bot.welcome_message = None
    bot.last_message_at = None
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


class TestTeamsGate:
    @pytest.mark.asyncio
    async def test_skip_decision_returns_before_saving_message(self):
        """When gate returns skip, _handle_message returns without saving user message."""
        mock_db = _make_mock_db()
        service = TeamsWebhookService(db_session=mock_db)

        mock_conv = MagicMock()
        mock_conv.id = uuid4()
        mock_conv.increment_message_count = MagicMock()
        mock_conv.handoff_status = None
        service._get_or_create_conversation = AsyncMock(return_value=mock_conv)

        bot = _make_teams_bot()
        activity = {
            "type": "message",
            "text": "routine noise",
            "from": {"id": "user1", "name": "Test User"},
            "conversation": {"id": "conv1"},
            "serviceUrl": "https://smba.trafficmanager.net/",
            "id": "act123",
        }

        with (
            patch(
                "src.services.agents.context_relevance_pruner.resolve_typesafe_client_for_pruning",
                AsyncMock(return_value=None),
            ),
            patch(
                "src.services.slack.slack_bot_gate.evaluate_slack_message",
                AsyncMock(return_value=_skip_decision()),
            ),
        ):
            await service._handle_message(bot, activity)

        # Gate returned skip — user message was NOT saved
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_shadow_mode_does_not_skip(self):
        """In shadow mode (default), even low scores pass through."""
        mock_db = _make_mock_db()
        service = TeamsWebhookService(db_session=mock_db)

        mock_conv = MagicMock()
        mock_conv.id = uuid4()
        mock_conv.increment_message_count = MagicMock()
        mock_conv.handoff_status = None
        service._get_or_create_conversation = AsyncMock(return_value=mock_conv)
        service._send_typing = AsyncMock()
        service._send_message = AsyncMock()

        bot = _make_teams_bot()
        activity = {
            "type": "message",
            "text": "hello agent",
            "from": {"id": "user1", "name": "Test User"},
            "conversation": {"id": "conv1"},
            "serviceUrl": "https://smba.trafficmanager.net/",
            "id": "act123",
        }

        # Shadow mode run decision → handler proceeds
        with (
            patch(
                "src.services.agents.context_relevance_pruner.resolve_typesafe_client_for_pruning",
                AsyncMock(return_value=None),
            ),
            patch(
                "src.services.slack.slack_bot_gate.evaluate_slack_message",
                AsyncMock(return_value=_run_decision()),
            ),
            patch(
                "src.controllers.agents.chat.stream_agent_response",
                AsyncMock(return_value=_empty_aiter()),
                create=True,
            ),
        ):
            await service._handle_message(bot, activity)

        # Message was saved (gate passed)
        mock_db.add.assert_called()

    @pytest.mark.asyncio
    async def test_fail_open_when_gate_agent_not_found(self):
        """If agent not found for gate, skip the gate and proceed."""
        mock_db = _make_mock_db(agent=None)  # db.get returns None
        service = TeamsWebhookService(db_session=mock_db)

        mock_conv = MagicMock()
        mock_conv.id = uuid4()
        mock_conv.increment_message_count = MagicMock()
        mock_conv.handoff_status = None
        service._get_or_create_conversation = AsyncMock(return_value=mock_conv)
        service._send_typing = AsyncMock()
        service._send_message = AsyncMock()

        bot = _make_teams_bot()
        activity = {
            "type": "message",
            "text": "hello agent",
            "from": {"id": "user1", "name": "Test User"},
            "conversation": {"id": "conv1"},
            "serviceUrl": "https://smba.trafficmanager.net/",
            "id": "act123",
        }

        with (
            patch(
                "src.services.agents.context_relevance_pruner.resolve_typesafe_client_for_pruning",
                AsyncMock(return_value=None),
            ),
            patch(
                "src.controllers.agents.chat.stream_agent_response",
                AsyncMock(return_value=_empty_aiter()),
                create=True,
            ),
        ):
            # Should not raise even with no agent found
            await service._handle_message(bot, activity)


def _empty_aiter():
    async def _gen():
        return
        yield

    return _gen()
