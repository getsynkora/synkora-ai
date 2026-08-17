"""Tests for SlackEventService.process_interaction (button-click handling, Event Mode)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.slack.slack_event_service import SlackEventService


@pytest.fixture
def mock_db_session():
    session = AsyncMock(spec=AsyncSession)
    session.get = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def service(mock_db_session):
    return SlackEventService(mock_db_session, agent_manager=MagicMock())


@pytest.fixture
def mock_slack_bot():
    bot = MagicMock()
    bot.id = uuid4()
    return bot


class TestProcessInteraction:
    @pytest.mark.asyncio
    async def test_approve_action_calls_respond_to_approval(self, service, mock_slack_bot):
        approval_id = str(uuid4())
        payload = {
            "type": "block_actions",
            "actions": [{"action_id": "hitl_approve", "value": approval_id}],
            "user": {"id": "U123"},
            "response_url": "https://hooks.slack.test/response",
        }

        mock_service_instance = AsyncMock()
        mock_service_instance.respond_to_approval = AsyncMock(return_value={"status": "approved"})

        with patch(
            "src.services.human_approval_service.HumanApprovalService", return_value=mock_service_instance
        ):
            result = await service.process_interaction(mock_slack_bot, payload)

        assert result == {"status": "ok"}
        mock_service_instance.respond_to_approval.assert_awaited_once()
        call_args = mock_service_instance.respond_to_approval.call_args
        assert call_args.args[0] == approval_id
        assert call_args.args[1] == "approved"
        assert call_args.kwargs["responded_by"] == "U123"

    @pytest.mark.asyncio
    async def test_reject_action_maps_to_rejected(self, service, mock_slack_bot):
        approval_id = str(uuid4())
        payload = {
            "type": "block_actions",
            "actions": [{"action_id": "hitl_reject", "value": approval_id}],
            "user": {"id": "U123"},
        }

        mock_service_instance = AsyncMock()
        mock_service_instance.respond_to_approval = AsyncMock(return_value={"status": "rejected"})

        with patch(
            "src.services.human_approval_service.HumanApprovalService", return_value=mock_service_instance
        ):
            await service.process_interaction(mock_slack_bot, payload)

        call_args = mock_service_instance.respond_to_approval.call_args
        assert call_args.args[1] == "rejected"

    @pytest.mark.asyncio
    async def test_already_handled_posts_ephemeral(self, service, mock_slack_bot):
        approval_id = str(uuid4())
        payload = {
            "type": "block_actions",
            "actions": [{"action_id": "hitl_approve", "value": approval_id}],
            "user": {"id": "U999"},
            "response_url": "https://hooks.slack.test/response",
        }

        mock_service_instance = AsyncMock()
        mock_service_instance.respond_to_approval = AsyncMock(
            return_value={"status": "rejected", "already_handled": True, "responded_by": "U111"}
        )

        with (
            patch("src.services.human_approval_service.HumanApprovalService", return_value=mock_service_instance),
            patch(
                "src.services.human_approval_service.HumanApprovalService.post_slack_ephemeral",
                new_callable=AsyncMock,
            ) as mock_post_ephemeral,
        ):
            await service.process_interaction(mock_slack_bot, payload)

        mock_post_ephemeral.assert_awaited_once()
        assert mock_post_ephemeral.call_args.args[0] == "https://hooks.slack.test/response"
        assert "U111" in mock_post_ephemeral.call_args.args[1]

    @pytest.mark.asyncio
    async def test_unknown_action_id_ignored(self, service, mock_slack_bot):
        payload = {
            "type": "block_actions",
            "actions": [{"action_id": "some_other_action", "value": "x"}],
            "user": {"id": "U1"},
        }
        result = await service.process_interaction(mock_slack_bot, payload)
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_non_block_actions_type_ignored(self, service, mock_slack_bot):
        payload = {"type": "view_submission"}
        result = await service.process_interaction(mock_slack_bot, payload)
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_missing_actions_is_noop(self, service, mock_slack_bot):
        payload = {"type": "block_actions", "actions": [], "user": {"id": "U1"}}
        result = await service.process_interaction(mock_slack_bot, payload)
        assert result == {"status": "ok"}
