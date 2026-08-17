from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.slack_bot import SlackBot
from src.services.slack.slack_bot_manager import SlackBotManager


class TestSlackBotManager:
    @pytest.fixture
    def mock_db_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        session.get = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def mock_deployment_service(self):
        """Mock the BotDeploymentService."""
        service = MagicMock()
        service.activate_slack_bot = AsyncMock(return_value={"success": True, "assigned_worker": "worker-1"})
        service.deactivate_slack_bot = AsyncMock(return_value={"success": True})
        service.get_bot_status = MagicMock(return_value={"is_deployed": False, "assigned_worker": None})
        service.restart_bot = MagicMock(return_value={"success": True})
        return service

    @pytest.fixture
    def manager(self, mock_db_session, mock_deployment_service):
        with (
            patch("src.services.slack.slack_bot_manager.get_redis") as mock_redis,
            patch("src.services.slack.slack_bot_manager.BotDeploymentService") as MockDeploymentService,
        ):
            mock_redis.return_value = MagicMock()
            MockDeploymentService.return_value = mock_deployment_service
            mgr = SlackBotManager(mock_db_session)
            mgr.deployment_service = mock_deployment_service
            return mgr

    @pytest.fixture
    def mock_slack_bot(self):
        bot = MagicMock(spec=SlackBot)
        bot.id = uuid4()
        bot.agent_id = uuid4()
        bot.tenant_id = uuid4()
        bot.bot_name = "TestBot"
        bot.slack_app_id = "APP123"
        bot.slack_bot_token = "encrypted_bot_token"
        bot.slack_app_token = "encrypted_app_token"
        bot.slack_workspace_id = "TEAM123"
        bot.slack_workspace_name = "Team Name"
        bot.is_active = True
        bot.allow_external_shared_channels = False
        bot.connection_status = "disconnected"
        bot.connection_mode = "socket"
        bot.signing_secret = None
        bot.webhook_url = None
        # Properties for connection mode checks
        bot.is_socket_mode = True
        bot.is_event_mode = False
        bot.created_at = datetime.now(UTC)
        bot.updated_at = datetime.now(UTC)
        bot.deleted_at = None
        bot.last_connected_at = None
        return bot

    @pytest.mark.asyncio
    async def test_create_bot(self, manager, mock_db_session):
        with patch("src.services.slack.slack_bot_manager.encrypt_value") as mock_encrypt:
            mock_encrypt.side_effect = lambda x: f"encrypted_{x}"

            result = await manager.create_bot(
                agent_id=uuid4(),
                tenant_id=uuid4(),
                bot_name="New Bot",
                slack_app_id="A123",
                slack_bot_token="xoxb-token",
                slack_app_token="xapp-token",
                slack_workspace_id="T123",
            )

            assert isinstance(result, SlackBot)
            assert result.bot_name == "New Bot"
            assert result.slack_bot_token == "encrypted_xoxb-token"
            assert result.slack_app_token == "encrypted_xapp-token"
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_bot_default_blocks_external_shared(self, manager, mock_db_session):
        with patch("src.services.slack.slack_bot_manager.encrypt_value", return_value="enc"):
            result = await manager.create_bot(
                agent_id=uuid4(),
                tenant_id=uuid4(),
                bot_name="New Bot",
                slack_app_id="A123",
                slack_bot_token="xoxb-token",
                slack_app_token="xapp-token",
            )

        assert result.allow_external_shared_channels is False

    @pytest.mark.asyncio
    async def test_create_bot_allow_external_shared_channels_true(self, manager, mock_db_session):
        with patch("src.services.slack.slack_bot_manager.encrypt_value", return_value="enc"):
            result = await manager.create_bot(
                agent_id=uuid4(),
                tenant_id=uuid4(),
                bot_name="New Bot",
                slack_app_id="A123",
                slack_bot_token="xoxb-token",
                slack_app_token="xapp-token",
                allow_external_shared_channels=True,
            )

        assert result.allow_external_shared_channels is True

    @pytest.mark.asyncio
    async def test_update_bot_allow_external_shared_channels(self, manager, mock_db_session, mock_slack_bot):
        mock_db_session.get.return_value = mock_slack_bot
        mock_slack_bot.allow_external_shared_channels = False

        await manager.update_bot(bot_id=mock_slack_bot.id, allow_external_shared_channels=True)

        assert mock_slack_bot.allow_external_shared_channels is True

    @pytest.mark.asyncio
    async def test_create_bot_error(self, manager, mock_db_session):
        mock_db_session.commit.side_effect = Exception("DB Error")

        with patch("src.services.slack.slack_bot_manager.encrypt_value", return_value="enc"):
            with pytest.raises(Exception, match="DB Error"):
                await manager.create_bot(
                    agent_id=uuid4(),
                    tenant_id=uuid4(),
                    bot_name="New Bot",
                    slack_app_id="A123",
                    slack_bot_token="xoxb-token",
                    slack_app_token="xapp-token",
                    slack_workspace_id="T123",
                )

        mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_bot_basic(self, manager, mock_db_session, mock_slack_bot):
        mock_db_session.get.return_value = mock_slack_bot

        await manager.update_bot(bot_id=mock_slack_bot.id, bot_name="Updated Name")

        assert mock_slack_bot.bot_name == "Updated Name"
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_bot_tokens_restarts(self, manager, mock_db_session, mock_slack_bot, mock_deployment_service):
        mock_db_session.get.return_value = mock_slack_bot
        mock_slack_bot.connection_status = "connected"
        mock_slack_bot.is_active = True

        with patch("src.services.slack.slack_bot_manager.encrypt_value", side_effect=lambda x: f"enc_{x}"):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await manager.update_bot(bot_id=mock_slack_bot.id, slack_bot_token="new_token")

        assert mock_slack_bot.slack_bot_token == "enc_new_token"
        # Should stop bot before token update
        mock_deployment_service.deactivate_slack_bot.assert_called()

    @pytest.mark.asyncio
    async def test_update_bot_deactivate(self, manager, mock_db_session, mock_slack_bot, mock_deployment_service):
        mock_db_session.get.return_value = mock_slack_bot
        mock_slack_bot.connection_status = "connected"

        await manager.update_bot(bot_id=mock_slack_bot.id, is_active=False)

        assert mock_slack_bot.is_active is False
        mock_deployment_service.deactivate_slack_bot.assert_called_with(mock_slack_bot.id)

    @pytest.mark.asyncio
    async def test_delete_bot(self, manager, mock_db_session, mock_slack_bot, mock_deployment_service):
        mock_db_session.get.return_value = mock_slack_bot

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await manager.delete_bot(mock_slack_bot.id)

        assert result is True
        mock_deployment_service.deactivate_slack_bot.assert_called_with(mock_slack_bot.id)
        assert mock_slack_bot.deleted_at is not None
        assert mock_slack_bot.is_active is False
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_bot_not_found(self, manager, mock_db_session):
        mock_db_session.get.return_value = None
        result = await manager.delete_bot(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_start_bot_success(self, manager, mock_db_session, mock_slack_bot, mock_deployment_service):
        mock_db_session.get.return_value = mock_slack_bot
        mock_deployment_service.activate_slack_bot.return_value = {"success": True, "assigned_worker": "worker-1"}

        result = await manager.start_bot(mock_slack_bot.id)

        assert result is True
        mock_deployment_service.activate_slack_bot.assert_called_with(mock_slack_bot.id)

    @pytest.mark.asyncio
    async def test_start_bot_not_found(self, manager, mock_db_session):
        mock_db_session.get.return_value = None

        # start_bot catches ValueError internally and returns False
        result = await manager.start_bot(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_start_bot_activation_failed(self, manager, mock_db_session, mock_slack_bot, mock_deployment_service):
        mock_db_session.get.return_value = mock_slack_bot
        mock_deployment_service.activate_slack_bot.return_value = {"success": False, "error": "No workers available"}

        result = await manager.start_bot(mock_slack_bot.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_stop_bot(self, manager, mock_db_session, mock_slack_bot, mock_deployment_service):
        mock_db_session.get.return_value = mock_slack_bot
        mock_deployment_service.deactivate_slack_bot.return_value = {"success": True}

        result = await manager.stop_bot(mock_slack_bot.id)

        assert result is True
        mock_deployment_service.deactivate_slack_bot.assert_called_with(mock_slack_bot.id)

    @pytest.mark.asyncio
    async def test_restart_bot(self, manager, mock_db_session, mock_slack_bot, mock_deployment_service):
        mock_db_session.get.return_value = mock_slack_bot
        mock_deployment_service.restart_bot.return_value = {"success": True}

        # BotType is imported inside the function from src.bot_worker.redis_state
        with patch("src.bot_worker.redis_state.BotType") as MockBotType:
            MockBotType.SLACK = "slack"
            result = await manager.restart_bot(mock_slack_bot.id)

        assert result is True
        mock_deployment_service.restart_bot.assert_called()

    @pytest.mark.asyncio
    async def test_list_bots(self, manager, mock_db_session, mock_slack_bot):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_slack_bot]
        mock_db_session.execute.return_value = mock_result

        bots = await manager.list_bots(tenant_id=uuid4(), is_active=True)

        assert len(bots) == 1
        assert bots[0] == mock_slack_bot

    @pytest.mark.asyncio
    async def test_get_bot_status(self, manager, mock_db_session, mock_slack_bot, mock_deployment_service):
        mock_agent = MagicMock(spec=Agent)
        mock_agent.agent_name = "Test Agent"
        mock_db_session.get.side_effect = [mock_slack_bot, mock_agent]
        mock_deployment_service.get_bot_status.return_value = {
            "is_deployed": True,
            "assigned_worker": "worker-1",
            "worker_healthy": True,
        }

        status = await manager.get_bot_status(mock_slack_bot.id)

        assert status["bot_id"] == str(mock_slack_bot.id)
        assert status["is_running"] is True
        assert status["connection_status"] == "disconnected"
        assert status["connection_mode"] == "socket"
        assert status["webhook_url"] is None  # Socket mode has no webhook URL
        assert status["agent_name"] == "Test Agent"
        assert status["assigned_worker"] == "worker-1"

    @pytest.mark.asyncio
    async def test_start_all_active_bots(self, manager, mock_db_session, mock_slack_bot):
        # Setup 2 bots, one connected, one disconnected
        bot1 = MagicMock(spec=SlackBot, id=uuid4(), connection_status="connected")
        bot2 = MagicMock(spec=SlackBot, id=uuid4(), connection_status="disconnected")

        manager.list_bots = AsyncMock(return_value=[bot1, bot2])
        manager.start_bot = AsyncMock(return_value=True)

        stats = await manager.start_all_active_bots()

        assert stats["total"] == 2
        assert stats["started"] == 1
        assert stats["already_running"] == 1

        manager.start_bot.assert_called_once_with(bot2.id)
