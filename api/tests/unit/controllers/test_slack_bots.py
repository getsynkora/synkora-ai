"""Tests for slack bots controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.slack_bots import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def mock_account():
    account = MagicMock()
    account.id = uuid.uuid4()
    account.email = "test@example.com"
    account.name = "Test User"
    return account


@pytest.fixture
def client(mock_db_session, mock_account):
    app = FastAPI()
    app.include_router(router)

    tenant_id = uuid.uuid4()

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[get_current_account] = lambda: mock_account

    with patch("src.controllers.slack_bots.SlackBotManager") as mock_manager:
        mock_manager.return_value = AsyncMock()
        yield TestClient(app), tenant_id, mock_account, mock_db_session, mock_manager


def _create_mock_slack_bot(tenant_id, agent_id):
    """Helper to create a mock Slack bot."""
    bot = MagicMock()
    bot.id = uuid.uuid4()
    bot.agent_id = agent_id
    bot.tenant_id = tenant_id
    bot.bot_name = "Test Slack Bot"
    bot.slack_app_id = "A12345678"
    bot.slack_workspace_id = "T12345678"
    bot.slack_workspace_name = "Test Workspace"
    bot.is_active = True
    bot.allow_external_shared_channels = False
    bot.connection_status = "connected"
    bot.connection_mode = "socket"
    bot.webhook_url = None
    bot.last_connected_at = datetime.now(UTC)
    bot.created_at = datetime.now(UTC)
    bot.updated_at = datetime.now(UTC)
    return bot


class TestCreateSlackBot:
    """Tests for creating Slack bots."""

    def test_create_slack_bot_success(self, client):
        """Test successfully creating a Slack bot."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        agent_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(tenant_id, agent_id)
        manager_instance.create_bot = AsyncMock(return_value=mock_bot)

        response = test_client.post(
            "/slack-bots",
            json={
                "agent_id": str(agent_id),
                "bot_name": "Test Slack Bot",
                "slack_app_id": "A12345678",
                "slack_bot_token": "xoxb-test-token",
                "slack_app_token": "xapp-test-token",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["bot_name"] == "Test Slack Bot"
        assert data["slack_app_id"] == "A12345678"

    def test_create_slack_bot_invalid_agent(self, client):
        """Test creating bot with invalid agent."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        manager_instance.create_bot = AsyncMock(side_effect=Exception("Agent not found"))

        response = test_client.post(
            "/slack-bots",
            json={
                "agent_id": str(uuid.uuid4()),
                "bot_name": "Test Bot",
                "slack_app_id": "A12345678",
                "slack_bot_token": "xoxb-test-token",
                "slack_app_token": "xapp-test-token",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_slack_bot_allow_external_shared_channels(self, client):
        """Test creating a bot with allow_external_shared_channels=True."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        agent_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(tenant_id, agent_id)
        mock_bot.allow_external_shared_channels = True
        manager_instance.create_bot = AsyncMock(return_value=mock_bot)

        response = test_client.post(
            "/slack-bots",
            json={
                "agent_id": str(agent_id),
                "bot_name": "Test Slack Bot",
                "slack_app_id": "A12345678",
                "slack_bot_token": "xoxb-test-token",
                "slack_app_token": "xapp-test-token",
                "allow_external_shared_channels": True,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["allow_external_shared_channels"] is True
        manager_instance.create_bot.assert_called_once()
        assert manager_instance.create_bot.call_args.kwargs["allow_external_shared_channels"] is True

    def test_create_slack_bot_default_allow_external_shared_channels_false(self, client):
        """Test that omitting the field defaults to False."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        agent_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(tenant_id, agent_id)
        manager_instance.create_bot = AsyncMock(return_value=mock_bot)

        response = test_client.post(
            "/slack-bots",
            json={
                "agent_id": str(agent_id),
                "bot_name": "Test Slack Bot",
                "slack_app_id": "A12345678",
                "slack_bot_token": "xoxb-test-token",
                "slack_app_token": "xapp-test-token",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert manager_instance.create_bot.call_args.kwargs["allow_external_shared_channels"] is False


class TestListSlackBots:
    """Tests for listing Slack bots."""

    def test_list_slack_bots_success(self, client):
        """Test successfully listing Slack bots."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        manager_instance.list_bots = AsyncMock(return_value=[mock_bot])

        response = test_client.get("/slack-bots")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_list_slack_bots_with_agent_filter(self, client):
        """Test listing bots filtered by agent."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        agent_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(tenant_id, agent_id)
        manager_instance.list_bots = AsyncMock(return_value=[mock_bot])

        response = test_client.get(f"/slack-bots?agent_id={agent_id}")

        assert response.status_code == status.HTTP_200_OK
        manager_instance.list_bots.assert_called_once()

    def test_list_slack_bots_empty(self, client):
        """Test listing bots when none exist."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        manager_instance.list_bots = AsyncMock(return_value=[])

        response = test_client.get("/slack-bots")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0


class TestGetSlackBot:
    """Tests for getting a Slack bot."""

    def test_get_slack_bot_success(self, client):
        """Test successfully getting a Slack bot."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        bot_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        mock_bot.id = bot_id
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)

        response = test_client.get(f"/slack-bots/{bot_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(bot_id)

    def test_get_slack_bot_not_found(self, client):
        """Test getting non-existent bot."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        manager_instance.get_bot = AsyncMock(return_value=None)

        response = test_client.get(f"/slack-bots/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_slack_bot_different_tenant(self, client):
        """Test getting bot from different tenant."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        other_tenant_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(other_tenant_id, uuid.uuid4())
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)

        response = test_client.get(f"/slack-bots/{mock_bot.id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateSlackBot:
    """Tests for updating Slack bots."""

    def test_update_slack_bot_success(self, client):
        """Test successfully updating a Slack bot."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        bot_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        mock_bot.id = bot_id
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)
        manager_instance.update_bot = AsyncMock(return_value=mock_bot)

        response = test_client.put(f"/slack-bots/{bot_id}", json={"bot_name": "Updated Bot Name"})

        assert response.status_code == status.HTTP_200_OK

    def test_update_slack_bot_not_found(self, client):
        """Test updating non-existent bot."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        manager_instance.get_bot = AsyncMock(return_value=None)

        response = test_client.put(f"/slack-bots/{uuid.uuid4()}", json={"bot_name": "Updated"})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_slack_bot_allow_external_shared_channels(self, client):
        """Test updating allow_external_shared_channels."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        bot_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        mock_bot.id = bot_id
        mock_bot.allow_external_shared_channels = True
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)
        manager_instance.update_bot = AsyncMock(return_value=mock_bot)

        response = test_client.put(f"/slack-bots/{bot_id}", json={"allow_external_shared_channels": True})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["allow_external_shared_channels"] is True
        assert manager_instance.update_bot.call_args.kwargs["allow_external_shared_channels"] is True


class TestDeleteSlackBot:
    """Tests for deleting Slack bots."""

    def test_delete_slack_bot_success(self, client):
        """Test successfully deleting a Slack bot."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)
        manager_instance.delete_bot = AsyncMock(return_value=True)

        response = test_client.delete(f"/slack-bots/{mock_bot.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_slack_bot_not_found(self, client):
        """Test deleting non-existent bot."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        manager_instance.get_bot = AsyncMock(return_value=None)

        response = test_client.delete(f"/slack-bots/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_slack_bot_failure(self, client):
        """Test delete failure."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)
        manager_instance.delete_bot = AsyncMock(return_value=False)

        response = test_client.delete(f"/slack-bots/{mock_bot.id}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestStartSlackBot:
    """Tests for starting Slack bots."""

    def test_start_slack_bot_success(self, client):
        """Test successfully starting a Slack bot."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)
        manager_instance.start_bot = AsyncMock(return_value=True)

        response = test_client.post(f"/slack-bots/{mock_bot.id}/start")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "started successfully" in data["message"]

    def test_start_slack_bot_failure(self, client):
        """Test start failure."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)
        manager_instance.start_bot = AsyncMock(return_value=False)

        response = test_client.post(f"/slack-bots/{mock_bot.id}/start")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestStopSlackBot:
    """Tests for stopping Slack bots."""

    def test_stop_slack_bot_success(self, client):
        """Test successfully stopping a Slack bot."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)
        manager_instance.stop_bot = AsyncMock(return_value=True)

        response = test_client.post(f"/slack-bots/{mock_bot.id}/stop")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "stopped successfully" in data["message"]


class TestRestartSlackBot:
    """Tests for restarting Slack bots."""

    def test_restart_slack_bot_success(self, client):
        """Test successfully restarting a Slack bot."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)
        manager_instance.restart_bot = AsyncMock(return_value=True)

        response = test_client.post(f"/slack-bots/{mock_bot.id}/restart")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "restarted successfully" in data["message"]


class TestGetSlackBotStatus:
    """Tests for getting Slack bot status."""

    def test_get_slack_bot_status_success(self, client):
        """Test successfully getting bot status."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        bot_id = uuid.uuid4()
        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        mock_bot.id = bot_id
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)
        manager_instance.get_bot_status = AsyncMock(
            return_value={
                "bot_id": str(bot_id),
                "bot_name": "Test Bot",
                "agent_id": str(uuid.uuid4()),
                "agent_name": "Test Agent",
                "workspace_id": "T12345678",
                "workspace_name": "Test Workspace",
                "is_active": True,
                "connection_status": "connected",
                "connection_mode": "socket",
                "webhook_url": None,
                "is_running": True,
                "assigned_worker": "worker-1",
                "worker_healthy": True,
                "last_connected_at": datetime.now(UTC).isoformat(),
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )

        response = test_client.get(f"/slack-bots/{bot_id}/status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["connection_status"] == "connected"

    def test_get_slack_bot_status_error(self, client):
        """Test getting status with error."""
        test_client, tenant_id, mock_account, mock_db, mock_manager = client
        manager_instance = mock_manager.return_value

        mock_bot = _create_mock_slack_bot(tenant_id, uuid.uuid4())
        manager_instance.get_bot = AsyncMock(return_value=mock_bot)
        manager_instance.get_bot_status = AsyncMock(return_value={"error": "Bot not found"})

        response = test_client.get(f"/slack-bots/{mock_bot.id}/status")

        assert response.status_code == status.HTTP_404_NOT_FOUND
