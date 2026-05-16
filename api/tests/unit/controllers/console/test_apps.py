"""Tests for console apps controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.console.apps import router
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
    app.include_router(router, prefix="/apps")

    tenant_id = uuid.uuid4()

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[get_current_account] = lambda: mock_account

    with patch("src.controllers.console.apps.AppService") as mock_service:
        mock_service.return_value = AsyncMock()
        yield TestClient(app), tenant_id, mock_account, mock_db_session, mock_service


def _create_mock_app(tenant_id):
    """Helper to create a mock app."""
    mock_app = MagicMock()
    mock_app.id = uuid.uuid4()
    mock_app.tenant_id = tenant_id
    mock_app.name = "Test App"
    mock_app.description = "Test description"
    mock_app.mode = "chat"
    mock_app.icon = "🤖"
    mock_app.icon_background = "#6366F1"
    mock_app.status = "active"
    mock_app.created_at = datetime.now(UTC)
    mock_app.updated_at = datetime.now(UTC)
    return mock_app


class TestListApps:
    """Tests for listing apps."""

    def test_list_apps_success(self, client):
        """Test successfully listing apps."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        service_instance = mock_service.return_value

        mock_app = _create_mock_app(tenant_id)
        service_instance.get_paginate_apps.return_value = [mock_app]

        response = test_client.get("/apps")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 1

    def test_list_apps_with_pagination(self, client):
        """Test listing apps with pagination."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        service_instance = mock_service.return_value

        service_instance.get_paginate_apps.return_value = []

        response = test_client.get("/apps?page=2&limit=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 2
        assert data["limit"] == 10

    def test_list_apps_with_mode_filter(self, client):
        """Test listing apps with mode filter."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        service_instance = mock_service.return_value

        mock_app = _create_mock_app(tenant_id)
        service_instance.get_paginate_apps.return_value = [mock_app]

        response = test_client.get("/apps?mode=chat")

        assert response.status_code == status.HTTP_200_OK
        service_instance.get_paginate_apps.assert_called_once()

    def test_list_apps_with_name_filter(self, client):
        """Test listing apps with name filter."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        service_instance = mock_service.return_value

        mock_app = _create_mock_app(tenant_id)
        service_instance.get_paginate_apps.return_value = [mock_app]

        response = test_client.get("/apps?name=Test")

        assert response.status_code == status.HTTP_200_OK


class TestCreateApp:
    """Tests for creating apps."""

    def test_create_app_success(self, client):
        """Test successfully creating an app."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        service_instance = mock_service.return_value

        mock_app = _create_mock_app(tenant_id)
        service_instance.create_app.return_value = mock_app

        response = test_client.post(
            "/apps", json={"name": "Test App", "mode": "chat", "description": "Test description"}
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test App"

    def test_create_app_with_icon(self, client):
        """Test creating app with custom icon."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        service_instance = mock_service.return_value

        mock_app = _create_mock_app(tenant_id)
        mock_app.icon = "🚀"
        mock_app.icon_background = "#FF0000"
        service_instance.create_app.return_value = mock_app

        response = test_client.post(
            "/apps", json={"name": "Test App", "mode": "chat", "icon": "🚀", "icon_background": "#FF0000"}
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_app_empty_name(self, client):
        """Test creating app with empty name."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        response = test_client.post("/apps", json={"name": "", "mode": "chat"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestGetApp:
    """Tests for getting an app."""

    def test_get_app_success(self, client):
        """Test successfully getting an app."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        service_instance = mock_service.return_value

        app_id = uuid.uuid4()
        mock_app = _create_mock_app(tenant_id)
        mock_app.id = app_id
        service_instance.get_app.return_value = mock_app

        response = test_client.get(f"/apps/{app_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(app_id)

    def test_get_app_not_found(self, client):
        """Test getting non-existent app."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        service_instance = mock_service.return_value

        from fastapi import HTTPException

        service_instance.get_app.side_effect = HTTPException(status_code=404, detail="App not found")

        response = test_client.get(f"/apps/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateApp:
    """Tests for updating apps."""

    def test_update_app_success(self, client):
        """Test successfully updating an app."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        service_instance = mock_service.return_value

        app_id = uuid.uuid4()
        mock_app = _create_mock_app(tenant_id)
        mock_app.id = app_id
        mock_app.name = "Updated App"
        service_instance.get_app.return_value = mock_app
        service_instance.update_app.return_value = mock_app

        response = test_client.put(f"/apps/{app_id}", json={"name": "Updated App"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated App"

    def test_update_app_partial(self, client):
        """Test partial update of app."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        service_instance = mock_service.return_value

        app_id = uuid.uuid4()
        mock_app = _create_mock_app(tenant_id)
        mock_app.id = app_id
        service_instance.get_app.return_value = mock_app
        service_instance.update_app.return_value = mock_app

        response = test_client.put(f"/apps/{app_id}", json={"description": "New description"})

        assert response.status_code == status.HTTP_200_OK


class TestDeleteApp:
    """Tests for deleting apps."""

    def test_delete_app_success(self, client):
        """Test successfully deleting an app."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        service_instance = mock_service.return_value

        app_id = uuid.uuid4()
        mock_app = _create_mock_app(tenant_id)
        mock_app.id = app_id
        service_instance.get_app.return_value = mock_app

        response = test_client.delete(f"/apps/{app_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        service_instance.delete_app.assert_called_once_with(mock_app)
