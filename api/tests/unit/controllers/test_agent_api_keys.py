"""Tests for agent API keys controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.agent_api_keys import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id


def setup_db_execute_mock(mock_db, return_value, return_list=False):
    """Helper to mock async db.execute() pattern."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    if return_list:
        mock_result.scalars.return_value.all.return_value = return_value if return_value else []
    else:
        mock_result.scalars.return_value.all.return_value = [return_value] if return_value else []
    mock_result.scalars.return_value.first.return_value = return_value
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_result


@pytest.fixture
def mock_api_key_service():
    with patch("src.controllers.agent_api_keys.AgentApiKeyService") as mock:
        # AgentApiKeyService uses class methods, so we mock them directly on the class
        mock.create_api_key = AsyncMock()
        mock.generate_api_key = MagicMock()  # This is sync
        yield mock


@pytest.fixture
def mock_db_session():
    db = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def client(mock_api_key_service, mock_db_session):
    app = FastAPI()
    app.include_router(router)

    # Mock dependencies
    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db

    # Mock current account
    mock_account = MagicMock()
    mock_account.id = uuid.uuid4()
    app.dependency_overrides[get_current_account] = lambda: mock_account

    # Mock tenant ID
    tenant_id = uuid.uuid4()
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    return TestClient(app), tenant_id, mock_account, mock_db_session, mock_api_key_service


def _create_mock_api_key(key_id, tenant_id, agent_id=None, **kwargs):
    """Helper to create mock API key."""
    mock_api_key = MagicMock()
    mock_api_key.id = key_id
    mock_api_key.tenant_id = tenant_id
    mock_api_key.key_name = kwargs.get("key_name", "Test Key")
    mock_api_key.key_prefix = kwargs.get("key_prefix", "sk_test_1234")
    mock_api_key.agent_id = agent_id or uuid.uuid4()
    mock_api_key.permissions = kwargs.get("permissions", ["chat"])
    mock_api_key.rate_limit_per_minute = kwargs.get("rate_limit_per_minute", 60)
    mock_api_key.rate_limit_per_hour = kwargs.get("rate_limit_per_hour", 1000)
    mock_api_key.rate_limit_per_day = kwargs.get("rate_limit_per_day", 10000)
    mock_api_key.is_active = kwargs.get("is_active", True)
    mock_api_key.allowed_ips = kwargs.get("allowed_ips", [])
    mock_api_key.allowed_origins = kwargs.get("allowed_origins", [])
    mock_api_key.expires_at = kwargs.get("expires_at")
    mock_api_key.last_used_at = kwargs.get("last_used_at")
    mock_api_key.created_at = datetime.now(UTC)
    mock_api_key.updated_at = datetime.now(UTC)
    return mock_api_key


class TestCreateApiKey:
    """Tests for creating API keys."""

    def test_create_api_key_success(self, client):
        """Test successful API key creation."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        key_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        plain_key = "sk_test_1234567890abcdef"

        mock_api_key = _create_mock_api_key(
            key_id,
            tenant_id,
            agent_id,
            key_name="Test Key",
            key_prefix=plain_key[:12],
            permissions=["chat", "read"],
        )

        mock_service.create_api_key.return_value = (mock_api_key, plain_key)

        # Mock agent exists
        mock_agent = MagicMock()
        mock_agent.id = agent_id
        setup_db_execute_mock(mock_db, mock_agent)

        response = test_client.post(
            "/api/v1/agent-api-keys",
            json={
                "key_name": "Test Key",
                "agent_id": str(agent_id),
                "permissions": ["chat", "read"],
                "rate_limit_per_minute": 60,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["key_name"] == "Test Key"
        assert data["api_key"] == plain_key
        assert data["id"] == str(key_id)

    def test_create_api_key_agent_not_found(self, client):
        """Test API key creation with non-existent agent."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        # Mock agent not found
        setup_db_execute_mock(mock_db, None)

        response = test_client.post(
            "/api/v1/agent-api-keys",
            json={"key_name": "Test Key", "agent_id": str(uuid.uuid4()), "permissions": ["chat"]},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_api_key_without_agent_id(self, client):
        """Test API key creation without agent_id is rejected — agent_id is required."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        response = test_client.post("/api/v1/agent-api-keys", json={"key_name": "Tenant Key", "permissions": ["chat"]})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestListApiKeys:
    """Tests for listing API keys."""

    def test_list_api_keys_success(self, client):
        """Test listing all API keys."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        key_id = uuid.uuid4()
        mock_api_key = _create_mock_api_key(key_id, tenant_id)

        setup_db_execute_mock(mock_db, [mock_api_key], return_list=True)

        response = test_client.get("/api/v1/agent-api-keys")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert len(data["keys"]) == 1

    def test_list_api_keys_filter_by_agent_id(self, client):
        """Test listing API keys filtered by agent ID."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        agent_id = uuid.uuid4()
        setup_db_execute_mock(mock_db, [], return_list=True)

        response = test_client.get(f"/api/v1/agent-api-keys?agent_id={agent_id}")

        assert response.status_code == status.HTTP_200_OK

    def test_list_api_keys_filter_by_agent_name(self, client):
        """Test listing API keys filtered by agent name."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        # Mock agent lookup by name, then empty list of keys
        mock_agent = MagicMock()
        mock_agent.id = uuid.uuid4()

        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                # Agent lookup
                mock_result.scalar_one_or_none.return_value = mock_agent
            else:
                # Keys list
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        response = test_client.get("/api/v1/agent-api-keys?agent_id=my-agent")

        assert response.status_code == status.HTTP_200_OK


class TestGetApiKey:
    """Tests for getting a specific API key."""

    def test_get_api_key_success(self, client):
        """Test getting a specific API key."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        key_id = uuid.uuid4()
        mock_api_key = _create_mock_api_key(key_id, tenant_id)

        setup_db_execute_mock(mock_db, mock_api_key)

        response = test_client.get(f"/api/v1/agent-api-keys/{key_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(key_id)

    def test_get_api_key_not_found(self, client):
        """Test getting non-existent API key."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.get(f"/api/v1/agent-api-keys/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateApiKey:
    """Tests for updating API keys."""

    def test_update_api_key_success(self, client):
        """Test updating an API key."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        key_id = uuid.uuid4()
        mock_api_key = _create_mock_api_key(
            key_id,
            tenant_id,
            key_name="Updated Key",
            permissions=["chat", "write"],
            rate_limit_per_minute=120,
        )

        setup_db_execute_mock(mock_db, mock_api_key)

        response = test_client.put(
            f"/api/v1/agent-api-keys/{key_id}",
            json={"key_name": "Updated Key", "permissions": ["chat", "write"], "rate_limit_per_minute": 120},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["key_name"] == "Updated Key"

    def test_update_api_key_not_found(self, client):
        """Test updating non-existent API key."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.put(f"/api/v1/agent-api-keys/{uuid.uuid4()}", json={"key_name": "Updated"})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_api_key_deactivate(self, client):
        """Test deactivating an API key."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        key_id = uuid.uuid4()
        mock_api_key = _create_mock_api_key(key_id, tenant_id, is_active=False)

        setup_db_execute_mock(mock_db, mock_api_key)

        response = test_client.put(f"/api/v1/agent-api-keys/{key_id}", json={"is_active": False})

        assert response.status_code == status.HTTP_200_OK


class TestDeleteApiKey:
    """Tests for deleting API keys."""

    def test_delete_api_key_success(self, client):
        """Test deleting an API key."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        key_id = uuid.uuid4()
        mock_api_key = _create_mock_api_key(key_id, tenant_id)

        setup_db_execute_mock(mock_db, mock_api_key)

        response = test_client.delete(f"/api/v1/agent-api-keys/{key_id}")

        assert response.status_code == status.HTTP_200_OK

    def test_delete_api_key_not_found(self, client):
        """Test deleting non-existent API key."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.delete(f"/api/v1/agent-api-keys/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestRegenerateApiKey:
    """Tests for regenerating API keys."""

    def test_regenerate_api_key_success(self, client):
        """Test regenerating an API key."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        key_id = uuid.uuid4()
        plain_key = "sk_new_9876543210fedcba"

        mock_api_key = _create_mock_api_key(key_id, tenant_id, key_prefix=plain_key[:12])

        setup_db_execute_mock(mock_db, mock_api_key)
        mock_service.generate_api_key.return_value = (plain_key, "hashed_key")

        response = test_client.post(f"/api/v1/agent-api-keys/{key_id}/regenerate")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "api_key" in data

    def test_regenerate_api_key_not_found(self, client):
        """Test regenerating non-existent API key."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.post(f"/api/v1/agent-api-keys/{uuid.uuid4()}/regenerate")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetApiKeyUsage:
    """Tests for getting API key usage statistics."""

    def test_get_api_key_usage_not_found(self, client):
        """Test getting usage for non-existent API key."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.get(f"/api/v1/agent-api-keys/{uuid.uuid4()}/usage")

        assert response.status_code == status.HTTP_404_NOT_FOUND
