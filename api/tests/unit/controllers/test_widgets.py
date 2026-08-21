"""Tests for widgets controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.widgets import widgets_router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id


@pytest.fixture
def mock_db_session():
    mock_db = AsyncMock()
    mock_db.add = MagicMock()  # add is synchronous
    return mock_db


@pytest.fixture
def client(mock_db_session):
    app = FastAPI()
    app.include_router(widgets_router)

    tenant_id = uuid.uuid4()

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    return TestClient(app), tenant_id, mock_db_session


def _create_mock_agent(agent_id, tenant_id):
    """Helper to create a mock agent."""
    agent = MagicMock()
    agent.id = agent_id
    agent.tenant_id = tenant_id
    agent.agent_name = "Test Agent"
    return agent


def _create_mock_widget(widget_id, agent_id, tenant_id):
    """Helper to create a mock widget."""
    widget = MagicMock()
    widget.id = widget_id
    widget.agent_id = agent_id
    widget.tenant_id = tenant_id
    widget.widget_name = "Test Widget"
    widget.api_key = "widget_test_api_key_12345"
    widget.allowed_domains = ["example.com"]
    widget.theme_config = {"primary_color": "#000000"}
    widget.rate_limit = 100
    widget.is_active = True
    widget.created_at = datetime.now(UTC)
    widget.updated_at = datetime.now(UTC)

    mock_agent = MagicMock()
    mock_agent.agent_name = "Test Agent"
    widget.agent = mock_agent

    return widget


class TestCreateWidget:
    """Tests for creating widgets."""

    def test_create_widget_success(self, client):
        """Test successfully creating a widget."""
        test_client, tenant_id, mock_db = client

        agent_id = uuid.uuid4()
        widget_id = uuid.uuid4()

        mock_agent = _create_mock_agent(agent_id, tenant_id)

        # Mock db.execute -> result.scalar_one_or_none() for agent lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        def mock_add(widget):
            widget.id = widget_id
            widget.created_at = datetime.now(UTC)

        mock_db.add.side_effect = mock_add
        mock_db.refresh = AsyncMock()

        response = test_client.post(
            "/widgets",
            json={
                "agent_id": str(agent_id),
                "widget_name": "My Widget",
                "allowed_domains": ["example.com"],
                "rate_limit": 50,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["success"] is True
        assert "api_key" in data["data"]

    def test_create_widget_invalid_agent_id(self, client):
        """Test creating widget with invalid agent ID format."""
        test_client, tenant_id, mock_db = client

        response = test_client.post("/widgets", json={"agent_id": "not-a-uuid", "widget_name": "My Widget"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_widget_agent_not_found(self, client):
        """Test creating widget for non-existent agent."""
        test_client, tenant_id, mock_db = client

        # Mock db.execute -> result.scalar_one_or_none() returns None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.post("/widgets", json={"agent_id": str(uuid.uuid4()), "widget_name": "My Widget"})

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestListWidgets:
    """Tests for listing widgets."""

    def test_list_widgets_success(self, client):
        """Test successfully listing widgets."""
        test_client, tenant_id, mock_db = client

        widget_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        mock_widget = _create_mock_widget(widget_id, agent_id, tenant_id)

        # First call for main query, second for count
        mock_result_widgets = MagicMock()
        mock_result_widgets.scalars.return_value.unique.return_value.all.return_value = [mock_widget]

        mock_result_count = MagicMock()
        mock_result_count.scalar.return_value = 1

        mock_db.execute = AsyncMock(side_effect=[mock_result_count, mock_result_widgets])

        response = test_client.get("/widgets")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["widgets"]) == 1

    def test_list_widgets_by_agent(self, client):
        """Test listing widgets filtered by agent."""
        test_client, tenant_id, mock_db = client

        agent_id = uuid.uuid4()
        mock_agent = _create_mock_agent(agent_id, tenant_id)

        # First call for agent lookup returns agent
        mock_result_agent = MagicMock()
        mock_result_agent.scalar_one_or_none.return_value = mock_agent

        # Second call for count
        mock_result_count = MagicMock()
        mock_result_count.scalar.return_value = 0

        # Third call for widget listing
        mock_result_widgets = MagicMock()
        mock_result_widgets.scalars.return_value.unique.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_result_agent, mock_result_count, mock_result_widgets])

        response = test_client.get(f"/widgets?agent_id={agent_id}")

        assert response.status_code == status.HTTP_200_OK


class TestGetWidget:
    """Tests for getting a specific widget."""

    def test_get_widget_success(self, client):
        """Test successfully getting a widget."""
        test_client, tenant_id, mock_db = client

        widget_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        mock_widget = _create_mock_widget(widget_id, agent_id, tenant_id)

        # Mock db.execute -> result.scalar_one_or_none()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_widget
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get(f"/widgets/{widget_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["widget_id"] == str(widget_id)

    def test_get_widget_not_found(self, client):
        """Test getting non-existent widget."""
        test_client, tenant_id, mock_db = client

        # Mock db.execute -> result.scalar_one_or_none() returns None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get(f"/widgets/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_widget_invalid_id(self, client):
        """Test getting widget with invalid ID format."""
        test_client, tenant_id, mock_db = client

        response = test_client.get("/widgets/not-a-uuid")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestUpdateWidget:
    """Tests for updating widgets."""

    def test_update_widget_success(self, client):
        """Test successfully updating a widget."""
        test_client, tenant_id, mock_db = client

        widget_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        mock_widget = _create_mock_widget(widget_id, agent_id, tenant_id)

        # Mock db.execute -> result.scalar_one_or_none()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_widget
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        response = test_client.put(
            f"/widgets/{widget_id}", json={"widget_name": "Updated Widget Name", "rate_limit": 200}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_update_widget_not_found(self, client):
        """Test updating non-existent widget."""
        test_client, tenant_id, mock_db = client

        # Mock db.execute -> result.scalar_one_or_none() returns None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.put(f"/widgets/{uuid.uuid4()}", json={"widget_name": "Updated"})

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteWidget:
    """Tests for deleting widgets."""

    def test_delete_widget_success(self, client):
        """Test successfully deleting a widget."""
        test_client, tenant_id, mock_db = client

        widget_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        mock_widget = _create_mock_widget(widget_id, agent_id, tenant_id)

        # Mock db.execute -> result.scalar_one_or_none()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_widget
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        response = test_client.delete(f"/widgets/{widget_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_delete_widget_not_found(self, client):
        """Test deleting non-existent widget."""
        test_client, tenant_id, mock_db = client

        # Mock db.execute -> result.scalar_one_or_none() returns None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.delete(f"/widgets/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestRegenerateApiKey:
    """Tests for regenerating widget API key."""

    def test_regenerate_api_key_success(self, client):
        """Test successfully regenerating API key."""
        test_client, tenant_id, mock_db = client

        widget_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        mock_widget = _create_mock_widget(widget_id, agent_id, tenant_id)

        # Mock db.execute -> result.scalar_one_or_none()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_widget
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        response = test_client.post(f"/widgets/{widget_id}/regenerate-key")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "api_key" in data["data"]


class TestGetEmbedCode:
    """Tests for getting widget embed code."""

    def test_get_embed_code_success(self, client):
        """Test successfully getting embed code."""
        test_client, tenant_id, mock_db = client

        widget_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        mock_widget = _create_mock_widget(widget_id, agent_id, tenant_id)

        # Mock db.execute -> result.scalar_one_or_none()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_widget
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get(f"/widgets/{widget_id}/embed-code")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "embed_code" in data["data"]
        assert "SynkoraWidget" in data["data"]["embed_code"]


class TestGetWidgetAnalytics:
    """Tests for getting widget analytics."""

    def test_get_widget_analytics_success(self, client):
        """Test successfully getting widget analytics."""
        test_client, tenant_id, mock_db = client

        widget_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        mock_widget = _create_mock_widget(widget_id, agent_id, tenant_id)

        mock_analytics = MagicMock()
        mock_analytics.session_id = "session_123"
        mock_analytics.messages_count = 5
        mock_analytics.domain = "example.com"
        mock_analytics.user_agent = "Mozilla/5.0"
        mock_analytics.created_at = datetime.now(UTC)

        # First call for widget lookup
        mock_result_widget = MagicMock()
        mock_result_widget.scalar_one_or_none.return_value = mock_widget

        # Second call for analytics
        mock_result_analytics = MagicMock()
        mock_result_analytics.scalars.return_value.all.return_value = [mock_analytics]

        mock_db.execute = AsyncMock(side_effect=[mock_result_widget, mock_result_analytics])

        response = test_client.get(f"/widgets/{widget_id}/analytics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "summary" in data["data"]


class TestWidgetChatRequestPageContext:
    """Tests for WidgetChatRequest.page_context field."""

    def test_page_context_defaults_to_none(self):
        from src.controllers.widgets import WidgetChatRequest

        request = WidgetChatRequest(message="hello")
        assert request.page_context is None

    def test_page_context_accepts_arbitrary_dict(self):
        from src.controllers.widgets import WidgetChatRequest

        request = WidgetChatRequest(message="hello", page_context={"entity_id": "usr_123", "type": "user_detail"})
        assert request.page_context == {"entity_id": "usr_123", "type": "user_detail"}


class TestCapPageContext:
    """Tests for _cap_page_context."""

    def test_none_returns_none(self):
        from src.controllers.widgets import _cap_page_context

        assert _cap_page_context(None) is None

    def test_small_dict_returned_unchanged(self):
        from src.controllers.widgets import _cap_page_context

        pc = {"entity_id": "usr_123"}
        assert _cap_page_context(pc) == pc

    def test_oversized_dict_returns_none(self):
        from src.controllers.widgets import _cap_page_context

        pc = {"blob": "x" * 1000}
        assert _cap_page_context(pc) is None

    def test_non_json_serializable_returns_none(self):
        from src.controllers.widgets import _cap_page_context

        pc = {"bad": object()}
        assert _cap_page_context(pc) is None


class TestWidgetChatTenantId:
    """Regression test: /widgets/chat must pass tenant_id to stream_agent_response
    so Agent Lens can record the real session name instead of falling back to
    the "Conversation" placeholder.
    """

    def test_widget_chat_passes_tenant_id_to_stream_agent_response(self, client, monkeypatch):
        test_client, tenant_id, mock_db = client

        agent_id = uuid.uuid4()
        widget_id = uuid.uuid4()
        mock_widget = _create_mock_widget(widget_id, agent_id, tenant_id)
        mock_widget.enable_agent_routing = False
        mock_widget.identity_verification_required = False
        mock_widget.identity_secret = None
        mock_widget.mobile_allowed = False

        mock_agent = _create_mock_agent(agent_id, tenant_id)
        mock_agent.slug = "test-agent"

        from src.middleware.widget_auth import WidgetAuthMiddleware

        monkeypatch.setattr(WidgetAuthMiddleware, "validate_api_key", AsyncMock(return_value=mock_widget))
        monkeypatch.setattr(WidgetAuthMiddleware, "validate_domain", MagicMock(return_value=True))
        monkeypatch.setattr(WidgetAuthMiddleware, "check_rate_limit_async", AsyncMock(return_value=True))

        from src.services.security.advanced_prompt_scanner import advanced_prompt_scanner

        monkeypatch.setattr(
            advanced_prompt_scanner,
            "scan_comprehensive_async",
            AsyncMock(return_value={"is_safe": True, "risk_score": 0}),
        )

        agent_result = MagicMock()
        agent_result.scalar_one_or_none.return_value = mock_agent

        analytics_result = MagicMock()
        analytics_result.scalar_one_or_none.return_value = None

        hc_result = MagicMock()
        hc_result.scalar_one_or_none.return_value = None

        mock_db.execute = AsyncMock(side_effect=[agent_result, analytics_result, hc_result])
        mock_db.commit = AsyncMock()
        mock_db.close = AsyncMock()

        def mock_add(obj):
            if not getattr(obj, "id", None):
                obj.id = uuid.uuid4()

        mock_db.add.side_effect = mock_add
        mock_db.refresh = AsyncMock()

        from src.services.conversation_service import ConversationService

        monkeypatch.setattr(ConversationService, "get_conversation_history_cached", AsyncMock(return_value=[]))

        async def _empty_stream(*args, **kwargs):
            return
            yield  # pragma: no cover

        captured = {}

        def fake_stream_agent_response(*args, **kwargs):
            captured["kwargs"] = kwargs
            captured["args"] = args
            return _empty_stream()

        from src.services.agents.chat_stream_service import ChatStreamService

        monkeypatch.setattr(ChatStreamService, "stream_agent_response", fake_stream_agent_response)

        response = test_client.post(
            "/widgets/chat",
            headers={"X-Widget-API-Key": "widget_test_api_key_12345"},
            json={"message": "Hello there"},
        )

        assert response.status_code == 200
        assert captured["kwargs"].get("tenant_id") == mock_widget.tenant_id
