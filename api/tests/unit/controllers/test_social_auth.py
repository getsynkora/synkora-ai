"""Tests for social auth controller."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.config import settings
from src.controllers.social_auth import _validate_redirect_url, router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account


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
def client(mock_db_session):
    app = FastAPI()
    app.include_router(router)

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db

    yield TestClient(app), mock_db_session


@pytest.fixture
def authenticated_client(mock_db_session, mock_account):
    app = FastAPI()
    app.include_router(router)

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_account] = lambda: mock_account

    yield TestClient(app), mock_db_session, mock_account


def _create_mock_provider_config(enabled=True):
    """Helper to create mock provider config."""
    config = MagicMock()
    config.client_id = "test_client_id"
    config.client_secret = "encrypted_secret"
    config.redirect_uri = "https://example.com/callback"
    config.enabled = enabled
    config.config = {}
    return config


def _create_mock_platform_tenant():
    """Helper to create mock platform tenant."""
    from src.models.tenant import TenantType

    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.name = "Platform Tenant"
    tenant.tenant_type = TenantType.PLATFORM
    return tenant


class TestGoogleLogin:
    """Tests for Google OAuth login."""

    def test_google_login_no_platform_tenant(self, client):
        """Test error when platform tenant doesn't exist."""
        test_client, mock_db = client

        # Mock execute to return None for platform tenant
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.get("/api/v1/auth/google/login")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Platform tenant not found" in response.json()["detail"]


class TestMicrosoftLogin:
    """Tests for Microsoft OAuth login."""

    def test_microsoft_login_no_platform_tenant(self, client):
        """Test error when platform tenant doesn't exist."""
        test_client, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.get("/api/v1/auth/microsoft/login")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestAppleLogin:
    """Tests for Apple OAuth login."""

    def test_apple_login_no_platform_tenant(self, client):
        """Test error when platform tenant doesn't exist."""
        test_client, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.get("/api/v1/auth/apple/login")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestGoogleCallback:
    """Tests for Google OAuth callback."""

    def test_google_callback_invalid_state(self, client):
        """Test callback with invalid state."""
        test_client, mock_db = client

        # Mock _get_oauth_state to return None (invalid/expired state)
        with patch("src.controllers.social_auth._get_oauth_state", return_value=None):
            response = test_client.get("/api/v1/auth/google/callback?code=auth_code&state=invalid_state")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid or expired state" in response.json()["detail"]


class TestMicrosoftCallback:
    """Tests for Microsoft OAuth callback."""

    def test_microsoft_callback_invalid_state(self, client):
        """Test callback with invalid state."""
        test_client, mock_db = client

        # Mock _get_oauth_state to return None (invalid/expired state)
        with patch("src.controllers.social_auth._get_oauth_state", return_value=None):
            response = test_client.get("/api/v1/auth/microsoft/callback?code=auth_code&state=invalid_state")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid or expired state" in response.json()["detail"]


class TestAppleCallback:
    """Tests for Apple OAuth callback."""

    def test_apple_callback_invalid_state(self, client):
        """Test callback with invalid state via POST."""
        test_client, mock_db = client

        # Mock _get_oauth_state to return None (invalid/expired state)
        with patch("src.controllers.social_auth._get_oauth_state", return_value=None):
            response = test_client.post(
                "/api/v1/auth/apple/callback", data={"code": "auth_code", "state": "invalid_state"}
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestValidateRedirectUrl:
    """Tests for the redirect URL validator (open-redirect protection + mobile deep link support)."""

    def test_allows_mobile_custom_scheme(self):
        """The native mobile app's registered callback scheme must be allowed through untouched."""
        redirect = f"{settings.mobile_oauth_redirect_scheme}://auth-callback"

        result = _validate_redirect_url(redirect, "https://app.example.com/signin")

        assert result == redirect

    def test_rejects_unrecognized_custom_scheme(self):
        """Any other custom scheme is not the mobile app and must fall back to the safe default."""
        result = _validate_redirect_url("evilapp://steal-tokens", "https://app.example.com/signin")

        assert result == "https://app.example.com/signin"

    def test_allows_same_host_web_redirect(self):
        """Existing web same-host redirect behavior must be unaffected."""
        result = _validate_redirect_url("https://app.example.com/dashboard", "https://app.example.com/signin")

        assert result == "https://app.example.com/dashboard"


class TestTokenExchange:
    """Tests for the OAuth token-exchange endpoint."""

    def test_returns_refresh_token_in_body(self, client):
        """
        Mobile clients cannot rely on the HttpOnly refresh_token cookie (no cookie jar
        wired up), so the refresh token must also be available in the JSON body — matching
        how the regular email/password /console/api/auth/signin endpoint already behaves.
        """
        test_client, _mock_db = client

        with patch(
            "src.controllers.social_auth._consume_exchange_tokens",
            new=AsyncMock(return_value={"access_token": "at123", "refresh_token": "rt456"}),
        ):
            response = test_client.get("/api/v1/auth/token-exchange?code=abc")

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["access_token"] == "at123"
        assert body["refresh_token"] == "rt456"
