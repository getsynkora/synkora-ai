from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.slack_bot import SlackBot
from src.services.slack.slack_socket_service import SlackSocketService


class TestSlackSocketService:
    @pytest.fixture
    def mock_db_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        session.flush = AsyncMock()
        session.get = AsyncMock()
        # Setup execute to return proper result mock (sync scalars().all())
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = []
        mock_execute_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_execute_result)
        return session

    @pytest.fixture
    def service(self, mock_db_session):
        # Reset class-level handlers for isolation
        SlackSocketService._active_handlers = {}
        return SlackSocketService(mock_db_session)

    @pytest.fixture
    def mock_slack_bot(self):
        bot = MagicMock(spec=SlackBot)
        bot.id = uuid4()
        bot.agent_id = uuid4()
        bot.bot_name = "TestBot"
        bot.slack_app_id = "APP123"
        bot.slack_bot_token = "encrypted_bot_token"
        bot.slack_app_token = "encrypted_app_token"
        bot.slack_workspace_id = None
        bot.slack_workspace_name = None
        bot.connection_status = "disconnected"
        return bot

    @pytest.mark.asyncio
    async def test_start_bot_success(self, service, mock_slack_bot, mock_db_session):
        with (
            patch("src.services.slack.slack_socket_service.decrypt_value", side_effect=lambda x: f"dec_{x}"),
            patch("src.services.slack.slack_socket_service.AsyncApp") as MockApp,
            patch("src.services.slack.slack_socket_service.AsyncWebClient") as MockClient,
            patch("src.services.slack.slack_socket_service.AsyncSocketModeHandler") as MockHandler,
        ):
            # Setup mocks
            mock_client_instance = MockClient.return_value
            mock_client_instance.auth_test = AsyncMock(return_value={"team_id": "T1", "team": "Team"})

            mock_handler_instance = MockHandler.return_value
            mock_handler_instance.start_async = AsyncMock()

            # Call method
            result = await service.start_bot(mock_slack_bot)

            assert result is True
            assert str(mock_slack_bot.id) in service.active_handlers
            assert mock_slack_bot.connection_status == "connected"
            assert mock_slack_bot.slack_workspace_id == "T1"

            MockApp.assert_called_once_with(token="dec_encrypted_bot_token")
            MockHandler.assert_called_once()
            # Verify handler started in background - trickier with create_task but valid here

            mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_start_bot_error(self, service, mock_slack_bot, mock_db_session):
        with patch("src.services.slack.slack_socket_service.decrypt_value", side_effect=Exception("Decrypt Error")):
            result = await service.start_bot(mock_slack_bot)

            assert result is False
            assert mock_slack_bot.connection_status == "error"
            mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_stop_bot(self, service, mock_db_session):
        bot_id = uuid4()
        mock_handler = MagicMock()
        mock_handler.close_async = AsyncMock()
        service.active_handlers[str(bot_id)] = mock_handler

        mock_slack_bot = MagicMock(spec=SlackBot)
        mock_db_session.get.return_value = mock_slack_bot

        result = await service.stop_bot(bot_id)

        assert result is True
        assert str(bot_id) not in service.active_handlers
        mock_handler.close_async.assert_called_once()
        assert mock_slack_bot.connection_status == "disconnected"
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_stop_bot_not_running(self, service, mock_db_session):
        bot_id = uuid4()
        mock_slack_bot = MagicMock(spec=SlackBot)
        mock_db_session.get.return_value = mock_slack_bot

        result = await service.stop_bot(bot_id)

        assert result is True
        assert mock_slack_bot.connection_status == "disconnected"

    def test_register_event_handlers(self, service, mock_slack_bot):
        mock_app = MagicMock()
        service._register_event_handlers(mock_app, mock_slack_bot)

        # All five event types must be registered
        registered = [c.args[0] for c in mock_app.event.call_args_list]
        assert "app_mention" in registered
        assert "message" in registered
        assert "app_home_opened" in registered
        assert "assistant_thread_started" in registered
        assert "assistant_thread_context_changed" in registered

        # HITL approval buttons must be registered too
        registered_actions = [c.args[0] for c in mock_app.action.call_args_list]
        assert "hitl_approve" in registered_actions
        assert "hitl_reject" in registered_actions

    @pytest.mark.asyncio
    async def test_handle_message_delegates_to_handler(self, service, mock_slack_bot, mock_db_session):
        """_handle_message must delegate fully to SlackMessageHandler.handle_message."""
        mock_client = MagicMock()
        mock_say = AsyncMock()

        with patch("src.services.slack.slack_socket_service.SlackMessageHandler") as MockHandler:
            mock_handler_instance = AsyncMock()
            MockHandler.return_value = mock_handler_instance

            await service._handle_message(
                slack_bot=mock_slack_bot,
                channel_id="C1",
                user_id="U1",
                text="hello",
                message_ts="123456.789",
                thread_ts="ts1",
                say=mock_say,
                client=mock_client,
            )

            MockHandler.assert_called_once_with(mock_db_session, service.agent_manager)
            mock_handler_instance.handle_message.assert_awaited_once_with(
                slack_bot=mock_slack_bot,
                channel_id="C1",
                user_id="U1",
                text="hello",
                message_ts="123456.789",
                thread_ts="ts1",
                client=mock_client,
                say=mock_say,
                is_bot_sender=False,
            )

    @pytest.mark.asyncio
    async def test_handle_message_forwards_is_bot_sender_flag(self, service, mock_slack_bot, mock_db_session):
        """_handle_message must forward an explicit is_bot_sender=True through to the handler."""
        mock_client = MagicMock()
        mock_say = AsyncMock()

        with patch("src.services.slack.slack_socket_service.SlackMessageHandler") as MockHandler:
            mock_handler_instance = AsyncMock()
            MockHandler.return_value = mock_handler_instance

            await service._handle_message(
                slack_bot=mock_slack_bot,
                channel_id="C1",
                user_id="U1",
                text="hello",
                message_ts="123456.789",
                thread_ts="ts1",
                say=mock_say,
                client=mock_client,
                is_bot_sender=True,
            )

            mock_handler_instance.handle_message.assert_awaited_once_with(
                slack_bot=mock_slack_bot,
                channel_id="C1",
                user_id="U1",
                text="hello",
                message_ts="123456.789",
                thread_ts="ts1",
                client=mock_client,
                say=mock_say,
                is_bot_sender=True,
            )

    @pytest.mark.asyncio
    async def test_app_mention_sets_is_bot_sender_from_event_bot_id(self, service, mock_slack_bot):
        """The registered app_mention handler must derive is_bot_sender from event['bot_id']."""
        captured = {}

        class FakeApp:
            def event(self, name):
                def decorator(fn):
                    captured[name] = fn
                    return fn

                return decorator

            def action(self, name):
                def decorator(fn):
                    return fn

                return decorator

        with patch.object(service, "_handle_message", new=AsyncMock()) as mock_handle_message:
            service._register_event_handlers(FakeApp(), mock_slack_bot)

            # A human mention (no bot_id) -> is_bot_sender=False
            await captured["app_mention"](
                event={"channel": "C1", "user": "U1", "text": "hi", "ts": "1.1"},
                say=AsyncMock(),
                client=MagicMock(),
            )
            assert mock_handle_message.await_args.kwargs["is_bot_sender"] is False

            # A mention forwarded from another bot's message -> is_bot_sender=True
            await captured["app_mention"](
                event={"channel": "C1", "user": "U-BOT", "text": "<@U2> hi", "ts": "1.2", "bot_id": "B999"},
                say=AsyncMock(),
                client=MagicMock(),
            )
            assert mock_handle_message.await_args.kwargs["is_bot_sender"] is True

    @pytest.mark.asyncio
    async def test_handle_message_error_propagates(self, service, mock_slack_bot, mock_db_session):
        """Errors from SlackMessageHandler should propagate (handler owns error handling)."""
        with patch("src.services.slack.slack_socket_service.SlackMessageHandler") as MockHandler:
            mock_handler_instance = AsyncMock()
            mock_handler_instance.handle_message.side_effect = Exception("Handler error")
            MockHandler.return_value = mock_handler_instance

            with pytest.raises(Exception, match="Handler error"):
                await service._handle_message(
                    slack_bot=mock_slack_bot,
                    channel_id="C1",
                    user_id="U1",
                    text="hello",
                    message_ts="123456.789",
                    thread_ts=None,
                    say=AsyncMock(),
                    client=MagicMock(),
                )

    @pytest.mark.asyncio
    async def test_handle_app_home_opened(self, service, mock_slack_bot, mock_db_session):
        """App Home handler publishes a view with agent name and how-to instructions."""
        mock_client = AsyncMock()

        mock_agent = MagicMock(spec=Agent)
        mock_agent.agent_name = "My Agent"
        mock_agent.description = "A helpful agent."
        mock_agent.suggestion_prompts = [
            {"title": "Hello", "description": "Say hello"},
        ]
        mock_db_session.get.return_value = mock_agent

        await service._handle_app_home_opened(
            slack_bot=mock_slack_bot,
            event={"user": "U1"},
            client=mock_client,
        )

        mock_client.views_publish.assert_awaited_once()
        call_kwargs = mock_client.views_publish.call_args[1]
        assert call_kwargs["user_id"] == "U1"
        view = call_kwargs["view"]
        assert view["type"] == "home"
        # Header block must contain agent name
        header_text = view["blocks"][0]["text"]["text"]
        assert "My Agent" in header_text

    @pytest.mark.asyncio
    async def test_handle_app_home_opened_no_user(self, service, mock_slack_bot):
        """App Home handler should silently skip if event has no user field."""
        mock_client = AsyncMock()
        await service._handle_app_home_opened(
            slack_bot=mock_slack_bot,
            event={},
            client=mock_client,
        )
        mock_client.views_publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_assistant_thread_started(self, service, mock_slack_bot, mock_db_session):
        """Assistant panel handler sets suggested prompts from agent config."""
        mock_client = AsyncMock()

        mock_agent = MagicMock(spec=Agent)
        mock_agent.suggestion_prompts = [
            {"title": "Search", "prompt": "Search Slack for..."},
            {"title": "Summarize", "description": "Summarize this channel"},
        ]
        mock_db_session.get.return_value = mock_agent

        await service._handle_assistant_thread_started(
            slack_bot=mock_slack_bot,
            event={"assistant_thread": {"channel_id": "C1", "thread_ts": "ts1"}},
            client=mock_client,
        )

        mock_client.assistant_threads_setSuggestedPrompts.assert_awaited_once()
        call_kwargs = mock_client.assistant_threads_setSuggestedPrompts.call_args[1]
        assert call_kwargs["channel_id"] == "C1"
        assert call_kwargs["thread_ts"] == "ts1"
        prompts = call_kwargs["prompts"]
        assert len(prompts) == 2
        assert prompts[0]["title"] == "Search"
        assert prompts[0]["message"] == "Search Slack for..."

    @pytest.mark.asyncio
    async def test_handle_assistant_thread_started_default_prompts(self, service, mock_slack_bot, mock_db_session):
        """Falls back to default prompts when agent has no suggestion_prompts."""
        mock_client = AsyncMock()

        mock_agent = MagicMock(spec=Agent)
        mock_agent.suggestion_prompts = None
        mock_db_session.get.return_value = mock_agent

        await service._handle_assistant_thread_started(
            slack_bot=mock_slack_bot,
            event={"assistant_thread": {"channel_id": "C1", "thread_ts": "ts1"}},
            client=mock_client,
        )

        mock_client.assistant_threads_setSuggestedPrompts.assert_awaited_once()
        prompts = mock_client.assistant_threads_setSuggestedPrompts.call_args[1]["prompts"]
        assert len(prompts) >= 2  # at least the default fallbacks

    @pytest.mark.asyncio
    async def test_handle_assistant_thread_started_missing_fields(self, service, mock_slack_bot):
        """Silently skips if channel_id or thread_ts is missing."""
        mock_client = AsyncMock()
        await service._handle_assistant_thread_started(
            slack_bot=mock_slack_bot,
            event={"assistant_thread": {}},
            client=mock_client,
        )
        mock_client.assistant_threads_setSuggestedPrompts.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_bot_status(self, service, mock_db_session, mock_slack_bot):
        bot_id = uuid4()
        mock_slack_bot.last_connected_at = datetime.now(UTC)
        mock_db_session.get.return_value = mock_slack_bot

        # Mock active handler
        service.active_handlers[str(bot_id)] = MagicMock()

        status = await service.get_bot_status(bot_id)

        assert status["bot_id"] == str(bot_id)
        assert status["is_running"] is True
        assert status["connection_status"] == "disconnected"  # mock default
        assert status["last_connected_at"] is not None


class TestHitlButtonHandling:
    @pytest.fixture
    def mock_db_session(self):
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.fixture
    def service(self, mock_db_session):
        SlackSocketService._active_handlers = {}
        return SlackSocketService(mock_db_session)

    @pytest.mark.asyncio
    async def test_handle_hitl_approve_calls_respond_to_approval(self, service):
        approval_id = str(uuid4())
        body = {
            "actions": [{"action_id": "hitl_approve", "value": approval_id}],
            "user": {"id": "U123"},
            "response_url": "https://hooks.slack.test/response",
        }

        mock_service_instance = AsyncMock()
        mock_service_instance.respond_to_approval = AsyncMock(return_value={"status": "approved"})

        with (
            patch("src.core.database.get_async_session_factory") as mock_factory,
            patch("src.services.human_approval_service.HumanApprovalService", return_value=mock_service_instance),
        ):
            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=AsyncMock(spec=AsyncSession))
            mock_session_cm.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = MagicMock(return_value=mock_session_cm)

            await service._handle_hitl_button(body, decision="approved")

            mock_service_instance.respond_to_approval.assert_awaited_once()
            call_args = mock_service_instance.respond_to_approval.call_args
            assert call_args.args[0] == approval_id
            assert call_args.args[1] == "approved"
            assert call_args.kwargs["responded_by"] == "U123"

    @pytest.mark.asyncio
    async def test_handle_hitl_button_already_handled_posts_ephemeral(self, service):
        approval_id = str(uuid4())
        body = {
            "actions": [{"action_id": "hitl_reject", "value": approval_id}],
            "user": {"id": "U999"},
            "response_url": "https://hooks.slack.test/response",
        }

        mock_service_instance = AsyncMock()
        mock_service_instance.respond_to_approval = AsyncMock(
            return_value={"status": "approved", "already_handled": True, "responded_by": "U111"}
        )

        with (
            patch("src.core.database.get_async_session_factory") as mock_factory,
            patch("src.services.human_approval_service.HumanApprovalService", return_value=mock_service_instance),
            patch(
                "src.services.human_approval_service.HumanApprovalService.post_slack_ephemeral",
                new_callable=AsyncMock,
            ) as mock_post_ephemeral,
        ):
            mock_session_cm = AsyncMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=AsyncMock(spec=AsyncSession))
            mock_session_cm.__aexit__ = AsyncMock(return_value=False)
            mock_factory.return_value = MagicMock(return_value=mock_session_cm)

            await service._handle_hitl_button(body, decision="rejected")

            mock_post_ephemeral.assert_awaited_once()
            args = mock_post_ephemeral.call_args.args
            assert args[0] == "https://hooks.slack.test/response"
            assert "U111" in args[1]

    @pytest.mark.asyncio
    async def test_handle_hitl_button_malformed_payload_is_noop(self, service):
        # Missing 'actions' entirely
        await service._handle_hitl_button({"user": {"id": "U1"}}, decision="approved")
        # Should not raise; nothing further to assert since it just logs and returns
