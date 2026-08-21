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


class TestAckReactionAndThinkingStatus:
    """Every incoming message should get an immediate 'eyes' reaction and Slack's
    native 'is thinking...' status indicator, before the agent is invoked."""

    @pytest.mark.asyncio
    async def test_adds_eyes_reaction_and_sets_thinking_status_before_agent_call(
        self, handler, mock_slack_bot, mock_client, mock_db_session
    ):
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": False, "is_org_shared": False}}
        )
        mock_client.reactions_add = AsyncMock()
        mock_client.api_call = AsyncMock(return_value={"ok": True})
        handler._get_or_create_conversation = AsyncMock(return_value=MagicMock(handoff_status=None))
        mock_db_session.get = AsyncMock(return_value=None)  # short-circuit: triggers "Agent not found"

        await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=AsyncMock(),
        )

        mock_client.reactions_add.assert_called_once_with(channel="C123", timestamp="123.456", name="eyes")
        mock_client.api_call.assert_called_once()
        assert mock_client.api_call.call_args.kwargs["api_method"] == "assistant.threads.setStatus"
        assert mock_client.api_call.call_args.kwargs["json"]["status"] == "is thinking..."

    @pytest.mark.asyncio
    async def test_reaction_failure_does_not_block_message_handling(
        self, handler, mock_slack_bot, mock_client, mock_db_session
    ):
        mock_client.conversations_info = AsyncMock(
            return_value={"channel": {"is_ext_shared": False, "is_org_shared": False}}
        )
        from slack_sdk.errors import SlackApiError

        mock_client.reactions_add = AsyncMock(
            side_effect=SlackApiError("already_reacted", response={"error": "already_reacted"})
        )
        mock_client.api_call = AsyncMock(return_value={"ok": True})
        handler._get_or_create_conversation = AsyncMock(side_effect=RuntimeError("stop-here"))

        result = await handler.handle_message(
            slack_bot=mock_slack_bot,
            channel_id="C123",
            user_id="U123",
            text="hello",
            message_ts="123.456",
            thread_ts=None,
            client=mock_client,
            say=AsyncMock(),
        )

        handler._get_or_create_conversation.assert_called_once()
        assert result is None  # generic error path returns None after RuntimeError


class TestUploadDiagrams:
    """internal_generate_diagram/internal_generate_quick_diagram render SVG for the web
    chat UI's inline preview, but Slack has no inline SVG rendering — _upload_diagrams
    must convert to PNG (like chart events already do) and upload as an image file."""

    _TINY_SVG = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="red"/></svg>'
    )

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


def _bar_chart(title="Chart"):
    return {
        "chart_type": "bar",
        "library": "chartjs",
        "title": title,
        "data": {"labels": ["A", "B"], "datasets": [{"label": "S1", "data": [1, 2]}]},
    }


def _unsupported_chart(title="Weird Chart"):
    return {
        "chart_type": "doughnut",
        "library": "chartjs",
        "title": title,
        "data": {"labels": ["A"], "datasets": [{"data": [1]}]},
    }


class TestUploadCharts:
    """internal_generate_chart events should post native `data_visualization` blocks
    where the chart shape is supported (Slack allows at most 2 per message), and fall
    back to the existing rendered-PNG upload path for anything else."""

    @pytest.mark.asyncio
    async def test_supported_chart_posts_native_data_visualization_block(self, handler, mock_client):
        mock_client.chat_postMessage = AsyncMock()
        mock_client.files_upload_v2 = AsyncMock()
        charts = [_bar_chart(title="Sales")]

        await handler._upload_charts(client=mock_client, channel_id="C1", thread_ts="1.1", charts=charts)

        mock_client.chat_postMessage.assert_called_once()
        kwargs = mock_client.chat_postMessage.call_args.kwargs
        assert kwargs["channel"] == "C1"
        assert kwargs["thread_ts"] == "1.1"
        assert kwargs["blocks"][0]["type"] == "data_visualization"
        mock_client.files_upload_v2.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsupported_chart_falls_back_to_png_upload(self, handler, mock_client):
        mock_client.chat_postMessage = AsyncMock()
        mock_client.files_upload_v2 = AsyncMock()
        charts = [_unsupported_chart()]

        await handler._upload_charts(client=mock_client, channel_id="C1", thread_ts=None, charts=charts)

        mock_client.chat_postMessage.assert_not_called()
        mock_client.files_upload_v2.assert_called_once()
        assert mock_client.files_upload_v2.call_args.kwargs["title"] == "Weird Chart"

    @pytest.mark.asyncio
    async def test_at_most_two_native_blocks_third_falls_back_to_png(self, handler, mock_client):
        mock_client.chat_postMessage = AsyncMock()
        mock_client.files_upload_v2 = AsyncMock()
        charts = [_bar_chart("Chart 1"), _bar_chart("Chart 2"), _bar_chart("Chart 3")]

        await handler._upload_charts(client=mock_client, channel_id="C1", thread_ts=None, charts=charts)

        assert mock_client.chat_postMessage.call_count == 2
        mock_client.files_upload_v2.assert_called_once()
        assert mock_client.files_upload_v2.call_args.kwargs["title"] == "Chart 3"


class TestPostCardSet:
    """internal_youtube_search_videos/internal_web_search/GitHub issue tools emit a
    `card_set` SSE event (one `card` dict per result); _post_card_set posts them all
    as `card` blocks in a single Slack message."""

    @pytest.mark.asyncio
    async def test_posts_one_card_block_per_item(self, handler, mock_client):
        mock_client.chat_postMessage = AsyncMock()
        cards = [
            {"title": "Video A", "subtitle": "Channel 1", "hero_image_url": "https://x/a.jpg"},
            {"title": "Video B", "subtitle": "Channel 2", "hero_image_url": "https://x/b.jpg"},
        ]

        await handler._post_card_set(client=mock_client, channel_id="C1", thread_ts="1.1", cards=cards)

        mock_client.chat_postMessage.assert_called_once()
        kwargs = mock_client.chat_postMessage.call_args.kwargs
        assert kwargs["channel"] == "C1"
        assert kwargs["thread_ts"] == "1.1"
        blocks = kwargs["blocks"]
        assert len(blocks) == 2
        assert blocks[0]["type"] == "card"
        assert blocks[0]["title"]["text"] == "Video A"
        assert blocks[1]["title"]["text"] == "Video B"

    @pytest.mark.asyncio
    async def test_empty_card_list_does_not_call_slack(self, handler, mock_client):
        mock_client.chat_postMessage = AsyncMock()

        await handler._post_card_set(client=mock_client, channel_id="C1", thread_ts=None, cards=[])

        mock_client.chat_postMessage.assert_not_called()

    @pytest.mark.asyncio
    async def test_malformed_card_is_skipped_others_still_posted(self, handler, mock_client):
        mock_client.chat_postMessage = AsyncMock()
        cards = [{"not_a_valid_kwarg": "boom"}, {"title": "Video B"}]

        await handler._post_card_set(client=mock_client, channel_id="C1", thread_ts=None, cards=cards)

        mock_client.chat_postMessage.assert_called_once()
        blocks = mock_client.chat_postMessage.call_args.kwargs["blocks"]
        assert len(blocks) == 1
        assert blocks[0]["title"]["text"] == "Video B"


class TestPostVideo:
    """internal_youtube_get_transcript/internal_youtube_get_transcript_segment emit a
    `video` SSE event; _post_video posts it as a single `video` block."""

    @pytest.mark.asyncio
    async def test_posts_video_block(self, handler, mock_client):
        mock_client.chat_postMessage = AsyncMock()
        video = {
            "video_url": "https://www.youtube.com/embed/abc123",
            "thumbnail_url": "https://i.ytimg.com/vi/abc123/hqdefault.jpg",
            "title": "How Slack Works",
        }

        await handler._post_video(client=mock_client, channel_id="C1", thread_ts="1.1", video=video)

        mock_client.chat_postMessage.assert_called_once()
        kwargs = mock_client.chat_postMessage.call_args.kwargs
        assert kwargs["channel"] == "C1"
        assert kwargs["thread_ts"] == "1.1"
        assert kwargs["blocks"][0]["type"] == "video"
        assert kwargs["blocks"][0]["title"]["text"] == "How Slack Works"

    @pytest.mark.asyncio
    async def test_malformed_video_does_not_call_slack(self, handler, mock_client):
        mock_client.chat_postMessage = AsyncMock()

        await handler._post_video(client=mock_client, channel_id="C1", thread_ts=None, video={"bogus": "data"})

        mock_client.chat_postMessage.assert_not_called()
