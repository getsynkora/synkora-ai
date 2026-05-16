"""Tests for social auth config controller."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.social_auth_config import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def mock_tenant_id():
    return uuid.uuid4()


@pytest.fixture
def client(mock_db_session, mock_tenant_id):
    app = FastAPI()
    app.include_router(router)

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id

    yield TestClient(app), mock_db_session, mock_tenant_id


def _create_mock_provider():
    """Helper to create mock provider config."""
    return {
        "id": str(uuid.uuid4()),
        "provider_name": "google",
        "client_id": "test_client_id",
        "client_secret_masked": "***",
        "redirect_uri": "https://example.com/callback",
        "enabled": "true",
        "config": {},
    }


class TestListProviders:
    """Tests for list_providers endpoint."""

    def test_list_providers_success(self, client):
        """Test successful provider listing."""
        test_client, mock_db, tenant_id = client

        mock_providers = [_create_mock_provider()]

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.list_providers.return_value = mock_providers
            MockService.return_value = mock_service

            response = test_client.get("/api/v1/social-auth-config")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "providers" in data
            mock_service.list_providers.assert_called_once_with(tenant_id)

    def test_list_providers_empty(self, client):
        """Test listing when no providers configured."""
        test_client, mock_db, tenant_id = client

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.list_providers.return_value = []
            MockService.return_value = mock_service

            response = test_client.get("/api/v1/social-auth-config")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["providers"] == []

    def test_list_providers_service_error(self, client):
        """Test error handling when service fails."""
        test_client, mock_db, tenant_id = client

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.list_providers.side_effect = Exception("Database error")
            MockService.return_value = mock_service

            response = test_client.get("/api/v1/social-auth-config")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database error" in response.json()["detail"]


class TestGetProvider:
    """Tests for get_provider endpoint."""

    def test_get_provider_success(self, client):
        """Test successful provider retrieval."""
        test_client, mock_db, tenant_id = client

        mock_provider = _create_mock_provider()

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.get_provider.return_value = mock_provider
            MockService.return_value = mock_service

            response = test_client.get("/api/v1/social-auth-config/google")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["provider"]["provider_name"] == "google"
            mock_service.get_provider.assert_called_once_with(tenant_id, "google")

    def test_get_provider_not_found(self, client):
        """Test provider not found."""
        test_client, mock_db, tenant_id = client

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.get_provider.return_value = None
            MockService.return_value = mock_service

            response = test_client.get("/api/v1/social-auth-config/nonexistent")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "nonexistent not found" in response.json()["detail"]

    def test_get_provider_service_error(self, client):
        """Test error handling when service fails."""
        test_client, mock_db, tenant_id = client

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.get_provider.side_effect = Exception("Service error")
            MockService.return_value = mock_service

            response = test_client.get("/api/v1/social-auth-config/google")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestCreateProvider:
    """Tests for create_provider endpoint."""

    def test_create_provider_success(self, client):
        """Test successful provider creation."""
        test_client, mock_db, tenant_id = client

        mock_provider = _create_mock_provider()

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.create_provider.return_value = mock_provider
            MockService.return_value = mock_service

            response = test_client.post(
                "/api/v1/social-auth-config",
                json={
                    "provider_name": "google",
                    "client_id": "test_client_id",
                    "client_secret": "test_secret",
                    "redirect_uri": "https://example.com/callback",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "created successfully" in data["message"]
            mock_service.create_provider.assert_called_once()

    def test_create_provider_validation_error(self, client):
        """Test validation error on create."""
        test_client, mock_db, tenant_id = client

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.create_provider.side_effect = ValueError("Provider already exists")
            MockService.return_value = mock_service

            response = test_client.post(
                "/api/v1/social-auth-config",
                json={
                    "provider_name": "google",
                    "client_id": "test_client_id",
                    "client_secret": "test_secret",
                    "redirect_uri": "https://example.com/callback",
                },
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Provider already exists" in response.json()["detail"]

    def test_create_provider_missing_fields(self, client):
        """Test validation error when required fields are missing."""
        test_client, mock_db, tenant_id = client

        response = test_client.post(
            "/api/v1/social-auth-config",
            json={
                "provider_name": "google"
                # Missing client_id, client_secret, redirect_uri
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestUpdateProvider:
    """Tests for update_provider endpoint."""

    def test_update_provider_success(self, client):
        """Test successful provider update."""
        test_client, mock_db, tenant_id = client

        mock_provider = _create_mock_provider()
        mock_provider["enabled"] = "false"

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.update_provider.return_value = mock_provider
            MockService.return_value = mock_service

            response = test_client.put("/api/v1/social-auth-config/google", json={"enabled": "false"})

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "updated successfully" in data["message"]

    def test_update_provider_not_found(self, client):
        """Test update on nonexistent provider."""
        test_client, mock_db, tenant_id = client

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.update_provider.side_effect = ValueError("Provider not found")
            MockService.return_value = mock_service

            response = test_client.put("/api/v1/social-auth-config/nonexistent", json={"enabled": "false"})

            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_provider_partial(self, client):
        """Test partial update of provider."""
        test_client, mock_db, tenant_id = client

        mock_provider = _create_mock_provider()

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.update_provider.return_value = mock_provider
            MockService.return_value = mock_service

            response = test_client.put("/api/v1/social-auth-config/google", json={"client_id": "new_client_id"})

            assert response.status_code == status.HTTP_200_OK


class TestDeleteProvider:
    """Tests for delete_provider endpoint."""

    def test_delete_provider_success(self, client):
        """Test successful provider deletion."""
        test_client, mock_db, tenant_id = client

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.delete_provider.return_value = True
            MockService.return_value = mock_service

            response = test_client.delete("/api/v1/social-auth-config/google")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "deleted successfully" in data["message"]

    def test_delete_provider_not_found(self, client):
        """Test delete on nonexistent provider."""
        test_client, mock_db, tenant_id = client

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.delete_provider.return_value = False
            MockService.return_value = mock_service

            response = test_client.delete("/api/v1/social-auth-config/nonexistent")

            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_provider_service_error(self, client):
        """Test error handling on delete."""
        test_client, mock_db, tenant_id = client

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.delete_provider.side_effect = Exception("Database error")
            MockService.return_value = mock_service

            response = test_client.delete("/api/v1/social-auth-config/google")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestTestProvider:
    """Tests for test_provider endpoint."""

    def test_test_provider_success(self, client):
        """Test successful provider test."""
        test_client, mock_db, tenant_id = client

        mock_result = {"success": True, "message": "Provider configuration is valid"}

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.test_provider.return_value = mock_result
            MockService.return_value = mock_service

            response = test_client.post("/api/v1/social-auth-config/google/test")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True

    def test_test_provider_failure(self, client):
        """Test provider test with invalid configuration."""
        test_client, mock_db, tenant_id = client

        mock_result = {"success": False, "message": "Invalid client credentials"}

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.test_provider.return_value = mock_result
            MockService.return_value = mock_service

            response = test_client.post("/api/v1/social-auth-config/google/test")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is False

    def test_test_provider_service_error(self, client):
        """Test error handling when test fails."""
        test_client, mock_db, tenant_id = client

        with patch("src.controllers.social_auth_config.SocialAuthProviderConfigService") as MockService:
            mock_service = AsyncMock()
            mock_service.test_provider.side_effect = Exception("Connection error")
            MockService.return_value = mock_service

            response = test_client.post("/api/v1/social-auth-config/google/test")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
