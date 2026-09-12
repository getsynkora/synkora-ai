import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.controllers.agents.llm_configs import router
from src.models.agent import Agent


def setup_db_execute_mock(mock_db, return_value):
    """Helper to mock async db.execute() pattern."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    mock_result.scalars.return_value.all.return_value = [return_value] if return_value else []
    mock_result.scalars.return_value.first.return_value = return_value
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_result


# Mock LLMConfigService
@pytest.fixture
def mock_llm_config_service():
    with patch("src.controllers.agents.llm_configs.LLMConfigService") as mock:
        # LLMConfigService uses class methods, so we mock them directly on the class
        mock.create_config = AsyncMock()
        mock.get_agent_configs = AsyncMock()
        mock.get_config = AsyncMock()
        mock.update_config = AsyncMock()
        mock.delete_config = AsyncMock()
        mock.set_default_config = AsyncMock()
        yield mock


@pytest.fixture
def client(monkeypatch):
    from fastapi import FastAPI

    from src.middleware.auth_middleware import get_current_account
    from src.services.auth_service import AuthService

    app = FastAPI()
    app.include_router(router)
    # These tests exercise successful administrator operations; denial is covered separately.
    app.dependency_overrides[get_current_account] = lambda: MagicMock(id=uuid.uuid4())
    monkeypatch.setattr(AuthService, "check_permission", AsyncMock(return_value=True))
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    db = AsyncMock()
    return db


@pytest.fixture
def mock_tenant_id():
    return uuid.uuid4()


class TestLLMConfigsController:
    """Test cases for LLM configs controller."""

    @pytest.fixture
    def mock_agent(self, mock_db_session, mock_tenant_id):
        agent = MagicMock(spec=Agent)
        agent.id = uuid.uuid4()
        agent.agent_name = "test-agent"
        agent.tenant_id = mock_tenant_id

        # Setup db.execute mock
        setup_db_execute_mock(mock_db_session, agent)
        return agent

    def _setup_mock_config(self, config_id, agent_id, tenant_id, name="Test Config"):
        mock_config = MagicMock()
        mock_config.id = config_id
        mock_config.agent_id = agent_id
        mock_config.tenant_id = tenant_id
        mock_config.name = name
        mock_config.provider = "openai"
        mock_config.model_name = "gpt-4"
        mock_config.api_base = "https://api.openai.com"
        mock_config.temperature = 0.7
        mock_config.max_tokens = 1000
        mock_config.top_p = 1.0
        mock_config.additional_params = {}
        mock_config.is_default = False
        mock_config.display_order = 0
        mock_config.enabled = True
        mock_config.routing_rules = None
        mock_config.routing_weight = None
        mock_config.created_at = datetime.now()
        mock_config.updated_at = datetime.now()
        return mock_config

    def test_create_llm_config_success(
        self, client, mock_llm_config_service, mock_db_session, mock_tenant_id, mock_agent
    ):
        """Test successful LLM config creation."""
        config_id = uuid.uuid4()
        mock_config = self._setup_mock_config(config_id, mock_agent.id, mock_tenant_id)

        mock_llm_config_service.create_config.return_value = mock_config

        from src.core.database import get_async_db
        from src.middleware.auth_middleware import get_current_tenant_id

        async def mock_db():
            yield mock_db_session

        client.app.dependency_overrides[get_async_db] = mock_db
        client.app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id

        response = client.post(
            f"/{mock_agent.agent_name}/llm-configs",
            json={"name": "Test Config", "provider": "openai", "model_name": "gpt-4", "api_key": "sk-test-key"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Test Config"
        assert data["id"] == str(config_id)

    def test_list_llm_configs(self, client, mock_llm_config_service, mock_db_session, mock_tenant_id, mock_agent):
        """Test listing LLM configs."""
        config_id = uuid.uuid4()
        mock_config = self._setup_mock_config(config_id, mock_agent.id, mock_tenant_id, name="Config 1")

        mock_llm_config_service.get_agent_configs.return_value = [mock_config]

        from src.core.database import get_async_db
        from src.middleware.auth_middleware import get_current_tenant_id

        async def mock_db():
            yield mock_db_session

        client.app.dependency_overrides[get_async_db] = mock_db
        client.app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id

        response = client.get(f"/{mock_agent.agent_name}/llm-configs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Config 1"

    def test_get_llm_config(self, client, mock_llm_config_service, mock_db_session, mock_tenant_id, mock_agent):
        """Test getting specific LLM config."""
        config_id = uuid.uuid4()
        mock_config = self._setup_mock_config(config_id, mock_agent.id, mock_tenant_id)

        mock_llm_config_service.get_config.return_value = mock_config

        from src.core.database import get_async_db
        from src.middleware.auth_middleware import get_current_tenant_id

        async def mock_db():
            yield mock_db_session

        client.app.dependency_overrides[get_async_db] = mock_db
        client.app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id

        response = client.get(f"/{mock_agent.agent_name}/llm-configs/{config_id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(config_id)

    def test_update_llm_config(self, client, mock_llm_config_service, mock_db_session, mock_tenant_id, mock_agent):
        """Test updating LLM config."""
        config_id = uuid.uuid4()
        mock_config = self._setup_mock_config(config_id, mock_agent.id, mock_tenant_id, name="Updated Config")

        # Mock both get (for verification) and update
        mock_llm_config_service.get_config.return_value = mock_config
        mock_llm_config_service.update_config.return_value = mock_config

        from src.core.database import get_async_db
        from src.middleware.auth_middleware import get_current_tenant_id

        async def mock_db():
            yield mock_db_session

        client.app.dependency_overrides[get_async_db] = mock_db
        client.app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id

        response = client.patch(f"/{mock_agent.agent_name}/llm-configs/{config_id}", json={"name": "Updated Config"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Updated Config"

    def test_delete_llm_config(self, client, mock_llm_config_service, mock_db_session, mock_tenant_id, mock_agent):
        """Test deleting LLM config."""
        config_id = uuid.uuid4()
        mock_config = self._setup_mock_config(config_id, mock_agent.id, mock_tenant_id)

        mock_llm_config_service.get_config.return_value = mock_config

        from src.core.database import get_async_db
        from src.middleware.auth_middleware import get_current_tenant_id

        async def mock_db():
            yield mock_db_session

        client.app.dependency_overrides[get_async_db] = mock_db
        client.app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id

        response = client.delete(f"/{mock_agent.agent_name}/llm-configs/{config_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_set_default_config(self, client, mock_llm_config_service, mock_db_session, mock_tenant_id, mock_agent):
        """Test setting default config."""
        config_id = uuid.uuid4()
        mock_config = self._setup_mock_config(config_id, mock_agent.id, mock_tenant_id)
        mock_config.is_default = True

        mock_llm_config_service.get_config.return_value = mock_config
        mock_llm_config_service.set_default_config.return_value = mock_config

        from src.core.database import get_async_db
        from src.middleware.auth_middleware import get_current_tenant_id

        async def mock_db():
            yield mock_db_session

        client.app.dependency_overrides[get_async_db] = mock_db
        client.app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id

        response = client.post(f"/{mock_agent.agent_name}/llm-configs/{config_id}/set-default")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_default"] is True
