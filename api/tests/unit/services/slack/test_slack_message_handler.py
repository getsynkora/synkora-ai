"""Tests for SlackMessageHandler externally-shared-channel blocking."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.slack_bot import SlackBot
from src.services.slack.slack_message_handler import SlackMessageHandler


@pytest.fixture
def mock_db_session():
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def handler(mock_db_session):
    return SlackMessageHandler(db_session=mock_db_session, agent_manager=MagicMock())


@pytest.fixture
def mock_slack_bot():
    bot = MagicMock(spec=SlackBot)
    bot.id = uuid4()
    bot.agent_id = uuid4()
    bot.tenant_id = uuid4()
    bot.slack_app_id = "A123"
    bot.created_by = None
    bot.allow_external_shared_channels = False
    return bot


@pytest.fixture
def mock_client():
    client = AsyncMock()
    return client


class TestExternalSharedChannelBlock:
    @pytest.mark.asyncio
    async def test_blocked_when_ext_shared_and_not_allowed(self, handler, mock_slack_bot, mock_client, mock_db_session):
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": True, "is_org_shared": False}}
        )
        say = AsyncMock()

        result = await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=say,
        )

        say.assert_called_once()
        assert "externally-shared channels" in say.call_args.args[0]
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()
        assert result is not None

    @pytest.mark.asyncio
    async def test_blocked_uses_chat_postmessage_when_no_say(
        self, handler, mock_slack_bot, mock_client, mock_db_session
    ):
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": True, "is_org_shared": False}}
        )
        mock_client.chat_postMessage = AsyncMock()

        await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts="100.000",
            client=mock_client,
            say=None,
        )

        mock_client.chat_postMessage.assert_called_once()
        assert mock_client.chat_postMessage.call_args.kwargs["thread_ts"] == "100.000"
        mock_db_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_allowed_when_flag_enabled(self, handler, mock_slack_bot, mock_client, mock_db_session):
        mock_slack_bot.allow_external_shared_channels = True
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": True, "is_org_shared": False}}
        )
        mock_client.users_info = AsyncMock(side_effect=Exception("no scope"))

        # Force the flow to bail out cleanly right after the top-of-handler check,
        # so we only assert the check was *skipped*, not the full downstream flow.
        handler._get_or_create_conversation = AsyncMock(side_effect=RuntimeError("stop-here"))
        say = AsyncMock()

        result = await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=say,
        )

        # The blocking decline message must NOT have been sent.
        for call in say.call_args_list:
            sent_text = call.args[0] if call.args else call.kwargs.get("text", "")
            assert "externally-shared channels" not in sent_text
        assert result is None  # generic error path returns None after RuntimeError

    @pytest.mark.asyncio
    async def test_allowed_when_not_externally_shared(self, handler, mock_slack_bot, mock_client, mock_db_session):
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": False, "is_org_shared": False}}
        )
        handler._get_or_create_conversation = AsyncMock(side_effect=RuntimeError("stop-here"))
        say = AsyncMock()

        await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=say,
        )

        for call in say.call_args_list:
            sent_text = call.args[0] if call.args else call.kwargs.get("text", "")
            assert "externally-shared channels" not in sent_text

    @pytest.mark.asyncio
    async def test_fails_open_when_conversations_info_raises(
        self, handler, mock_slack_bot, mock_client, mock_db_session
    ):
        mock_client.conversations_info = AsyncMock(side_effect=Exception("missing scope"))
        handler._get_or_create_conversation = AsyncMock(side_effect=RuntimeError("stop-here"))
        say = AsyncMock()

        await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=say,
        )

        # Fail-open: normal flow proceeds (reaches _get_or_create_conversation, which raises)
        handler._get_or_create_conversation.assert_called_once()
        for call in say.call_args_list:
            sent_text = call.args[0] if call.args else call.kwargs.get("text", "")
            assert "externally-shared channels" not in sent_text

    @pytest.mark.asyncio
    async def test_org_shared_is_not_blocked(self, handler, mock_slack_bot, mock_client, mock_db_session):
        """is_org_shared (same Enterprise Grid org) must NOT trigger the block."""
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": False, "is_org_shared": True}}
        )
        handler._get_or_create_conversation = AsyncMock(side_effect=RuntimeError("stop-here"))
        say = AsyncMock()

        await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=say,
        )

        handler._get_or_create_conversation.assert_called_once()


class TestUploadDiagrams:
    """internal_generate_diagram/internal_generate_quick_diagram render SVG for the web
    chat UI's inline preview, but Slack has no inline SVG rendering — _upload_diagrams
    must convert to PNG (like chart events already do) and upload as an image file."""

    _TINY_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="red"/></svg>'

    @pytest.mark.asyncio
    async def test_upload_diagram_with_svg_content(self, handler, mock_client):
        mock_client.files_upload_v2 = AsyncMock()
        diagrams = [{"title": "My Diagram", "svg_content": self._TINY_SVG}]

        await handler._upload_diagrams(client=mock_client, channel_id="C1", thread_ts="1.1", diagrams=diagrams)

        mock_client.files_upload_v2.assert_called_once()
        kwargs = mock_client.files_upload_v2.call_args.kwargs
        assert kwargs["channel"] == "C1"
        assert kwargs["thread_ts"] == "1.1"
        assert kwargs["title"] == "My Diagram"
        assert kwargs["content"].startswith(b"\x89PNG")

    @pytest.mark.asyncio
    async def test_upload_diagram_fetches_svg_url_when_content_missing(self, handler, mock_client, monkeypatch):
        import httpx

        class _FakeResponse:
            text = TestUploadDiagrams._TINY_SVG

            def raise_for_status(self):
                pass

        class _FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url):
                return _FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
        mock_client.files_upload_v2 = AsyncMock()
        diagrams = [{"title": "Remote Diagram", "svg_url": "https://example.com/d.svg"}]

        await handler._upload_diagrams(client=mock_client, channel_id="C1", thread_ts=None, diagrams=diagrams)

        mock_client.files_upload_v2.assert_called_once()
        assert mock_client.files_upload_v2.call_args.kwargs["content"].startswith(b"\x89PNG")

    @pytest.mark.asyncio
    async def test_upload_diagram_skips_when_no_content_or_url(self, handler, mock_client):
        mock_client.files_upload_v2 = AsyncMock()
        diagrams = [{"title": "Empty"}]

        await handler._upload_diagrams(client=mock_client, channel_id="C1", thread_ts=None, diagrams=diagrams)

        mock_client.files_upload_v2.assert_not_called()
