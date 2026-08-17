"""Tests for HumanApprovalService: Slack button building, message updates, and respond_to_approval."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_approval import AgentApprovalRequest, ApprovalStatus
from src.services.human_approval_service import HumanApprovalService


@pytest.fixture
def mock_db_session():
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def service(mock_db_session):
    return HumanApprovalService(mock_db_session)


def make_approval(**overrides) -> AgentApprovalRequest:
    approval = MagicMock(spec=AgentApprovalRequest)
    approval.id = overrides.get("id", uuid4())
    approval.agent_id = overrides.get("agent_id", uuid4())
    approval.agent_name = overrides.get("agent_name", "TestAgent")
    approval.tool_name = overrides.get("tool_name", "send_email")
    approval.tool_args = overrides.get("tool_args", {"to": "a@example.com"})
    approval.tool_args_hash = "hash123"
    approval.task_id = overrides.get("task_id", uuid4())
    approval.status = overrides.get("status", ApprovalStatus.PENDING)
    approval.notification_channel = overrides.get("notification_channel", "slack")
    approval.notification_ref = overrides.get(
        "notification_ref", {"slack_bot_id": str(uuid4()), "channel_id": "C1", "message_ts": "123.456"}
    )
    approval.expires_at = overrides.get("expires_at", datetime.now(UTC) + timedelta(minutes=30))
    approval.responded_at = None
    approval.responded_by = overrides.get("responded_by", None)
    return approval


class TestBuildApprovalBlocks:
    def test_blocks_contain_approve_and_reject_buttons(self, service):
        approval = make_approval()
        blocks = HumanApprovalService._build_approval_blocks(approval, "some text")

        actions_block = next(b for b in blocks if b["type"] == "actions")
        elements = actions_block["elements"]
        assert len(elements) == 2

        approve = next(e for e in elements if e["action_id"] == "hitl_approve")
        reject = next(e for e in elements if e["action_id"] == "hitl_reject")

        assert approve["value"] == str(approval.id)
        assert approve["style"] == "primary"
        assert reject["value"] == str(approval.id)
        assert reject["style"] == "danger"

    def test_blocks_mention_free_text_fallback(self, service):
        approval = make_approval()
        blocks = HumanApprovalService._build_approval_blocks(approval, "some text")
        context_block = next(b for b in blocks if b["type"] == "context")
        assert "feedback" in context_block["elements"][0]["text"]


class TestRespondToApprovalSlackUpdate:
    @pytest.mark.asyncio
    async def test_approved_persists_responded_by_and_updates_message(self, service, mock_db_session):
        approval = make_approval(status=ApprovalStatus.PENDING)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = approval
        mock_db_session.execute.return_value = mock_result

        service._store_execution_token = AsyncMock()
        service._fire_approved_run = AsyncMock()
        service._update_slack_message = AsyncMock()

        result = await service.respond_to_approval(
            approval.id, "approved", feedback_text=None, db=mock_db_session, responded_by="U123"
        )

        assert approval.responded_by == "U123"
        assert approval.status == ApprovalStatus.APPROVED
        service._update_slack_message.assert_awaited_once_with(approval)
        assert result["status"] == "approved"

    @pytest.mark.asyncio
    async def test_slack_message_update_failure_does_not_affect_result(self, service, mock_db_session):
        approval = make_approval(status=ApprovalStatus.PENDING)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = approval
        mock_db_session.execute.return_value = mock_result

        service._store_execution_token = AsyncMock()
        service._fire_approved_run = AsyncMock()
        service._update_slack_message = AsyncMock(side_effect=Exception("chat_update failed"))

        result = await service.respond_to_approval(
            approval.id, "approved", feedback_text=None, db=mock_db_session, responded_by="U123"
        )

        assert result["status"] == "approved"

    @pytest.mark.asyncio
    async def test_already_handled_returns_flag_and_responded_by(self, service, mock_db_session):
        approval = make_approval(status=ApprovalStatus.APPROVED, responded_by="U111")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = approval
        mock_db_session.execute.return_value = mock_result

        result = await service.respond_to_approval(
            approval.id, "rejected", feedback_text=None, db=mock_db_session, responded_by="U999"
        )

        assert result["already_handled"] is True
        assert result["responded_by"] == "U111"
        # Status/responded_by must not be overwritten by the second responder
        assert approval.responded_by == "U111"

    @pytest.mark.asyncio
    async def test_expired_returns_expired_status(self, service, mock_db_session):
        approval = make_approval(status=ApprovalStatus.PENDING, expires_at=datetime.now(UTC) - timedelta(minutes=1))
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = approval
        mock_db_session.execute.return_value = mock_result

        result = await service.respond_to_approval(
            approval.id, "approved", feedback_text=None, db=mock_db_session, responded_by="U123"
        )

        assert result["status"] == "expired"
        assert approval.status == ApprovalStatus.EXPIRED


class TestUpdateSlackMessage:
    @pytest.mark.asyncio
    async def test_update_slack_message_calls_chat_update(self, service, mock_db_session):
        approval = make_approval(status=ApprovalStatus.APPROVED, responded_by="U123")
        mock_bot = MagicMock()
        mock_bot.slack_bot_token = "encrypted_token"
        mock_db_session.get.return_value = mock_bot

        mock_client = AsyncMock()
        with (
            patch("src.services.agents.security.decrypt_value", return_value="plain_token"),
            patch("slack_sdk.web.async_client.AsyncWebClient", return_value=mock_client),
        ):
            await service._update_slack_message(approval)

        mock_client.chat_update.assert_awaited_once()
        call_kwargs = mock_client.chat_update.call_args.kwargs
        assert call_kwargs["channel"] == "C1"
        assert call_kwargs["ts"] == "123.456"
        assert "Approved" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_update_slack_message_noop_when_ref_incomplete(self, service, mock_db_session):
        approval = make_approval(status=ApprovalStatus.APPROVED, notification_ref={})
        await service._update_slack_message(approval)
        mock_db_session.get.assert_not_called()


class TestHandleReplyUpdatesSlackMessage:
    @pytest.mark.asyncio
    async def test_handle_reply_approve_updates_slack_message(self, service, mock_db_session):
        approval = make_approval(status=ApprovalStatus.PENDING)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = approval
        mock_db_session.execute.return_value = mock_result

        service._store_execution_token = AsyncMock()
        service._fire_approved_run = AsyncMock()
        service._update_slack_message = AsyncMock()

        status = await service.handle_reply(approval.id, "yes", mock_db_session)

        assert status == "approved"
        service._update_slack_message.assert_awaited_once_with(approval)
