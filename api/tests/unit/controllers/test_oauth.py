"""Tests for OAuth controller."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.oauth import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import (
    get_current_account,
    get_current_tenant_id,
    get_optional_account,
    get_optional_tenant_id,
)


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def mock_tenant_id():
    return uuid.uuid4()


@pytest.fixture
def mock_account():
    account = MagicMock()
    account.id = uuid.uuid4()
    account.name = "Test User"
    account.email = "test@example.com"
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
def authenticated_client(mock_db_session, mock_tenant_id, mock_account):
    """Client with both account and tenant mocked — required for endpoints using get_current_account."""
    app = FastAPI()
    app.include_router(router)

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id
    app.dependency_overrides[get_current_account] = lambda: mock_account
    app.dependency_overrides[get_optional_account] = lambda: mock_account
    app.dependency_overrides[get_optional_tenant_id] = lambda: mock_tenant_id

    yield TestClient(app), mock_db_session, mock_tenant_id, mock_account


def _setup_mock_db_result(mock_db, value):
    """Helper to set up mock db.execute result for scalar_one_or_none."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value
    mock_db.execute = AsyncMock(return_value=mock_result)


def _setup_mock_db_result_list(mock_db, values):
    """Helper to set up mock db.execute result for scalars().all()."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = values
    mock_db.execute = AsyncMock(return_value=mock_result)


def _create_mock_oauth_app(provider="github", auth_method="oauth"):
    """Helper to create mock OAuth app."""
    app = MagicMock()
    app.id = 1
    app.tenant_id = uuid.uuid4()
    app.provider = provider
    app.app_name = f"Test {provider.title()} App"
    app.auth_method = auth_method
    app.client_id = "test_client_id"
    app.client_secret = "encrypted_secret"
    app.redirect_uri = "https://example.com/callback"
    app.scopes = ["repo", "user"]
    app.api_token = "encrypted_token" if auth_method == "api_token" else None
    app.access_token = None
    app.refresh_token = None
    app.is_active = True
    app.is_default = True
    app.description = "Test description"
    app.tags = ["test"]
    app.is_internal_tool = False
    app.to_dict = MagicMock(
        return_value={
            "id": 1,
            "provider": provider,
            "app_name": f"Test {provider.title()} App",
            "auth_method": auth_method,
            "is_active": True,
            "is_default": True,
        }
    )
    return app


class TestGitHubAuthorize:
    """Tests for GitHub OAuth authorize endpoint."""

    def test_github_authorize_app_not_found(self, client):
        """Test authorization with nonexistent app returns error."""
        test_client, mock_db = client

        _setup_mock_db_result(mock_db, None)

        response = test_client.get(
            "/api/v1/oauth/github/authorize", params={"oauth_app_id": 999}, follow_redirects=False
        )

        # The endpoint catches all exceptions and returns 500
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_github_authorize_api_token_method(self, client):
        """Test authorization with API token method redirects immediately."""
        test_client, mock_db = client

        mock_app = _create_mock_oauth_app(auth_method="api_token")

        _setup_mock_db_result(mock_db, mock_app)

        with patch("src.controllers.oauth.github.get_app_base_url") as mock_get_url:
            mock_get_url.return_value = "https://example.com"

            response = test_client.get(
                "/api/v1/oauth/github/authorize", params={"oauth_app_id": 1}, follow_redirects=False
            )

            assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
            assert "oauth=success" in response.headers["location"]
            assert "method=api_token" in response.headers["location"]

    def test_github_authorize_oauth_method(self, client):
        """Test OAuth authorization redirects to GitHub."""
        test_client, mock_db = client

        mock_app = _create_mock_oauth_app()

        _setup_mock_db_result(mock_db, mock_app)

        with (
            patch("src.controllers.oauth.github.get_app_base_url") as mock_get_url,
            patch("src.controllers.oauth.github.decrypt_value") as mock_decrypt,
            patch("src.controllers.oauth.github.GitHubOAuth") as MockGitHub,
            patch("src.controllers.oauth.github.create_oauth_state") as mock_create_state,
        ):
            mock_get_url.return_value = "https://example.com"
            mock_decrypt.return_value = "decrypted_secret"
            mock_create_state.return_value = "test_state_token"

            mock_oauth = MagicMock()
            mock_oauth.get_authorization_url.return_value = "https://github.com/login/oauth/authorize?client_id=test"
            MockGitHub.return_value = mock_oauth

            response = test_client.get(
                "/api/v1/oauth/github/authorize", params={"oauth_app_id": 1}, follow_redirects=False
            )

            assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
            assert "github.com" in response.headers["location"]


class TestGitHubCallback:
    """Tests for GitHub OAuth callback endpoint."""

    def test_github_callback_invalid_state(self, client):
        """Test callback with invalid state."""
        test_client, mock_db = client

        response = test_client.get(
            "/api/v1/oauth/github/callback", params={"code": "test_code", "state": "invalid_state"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid" in response.json()["detail"] or "expired" in response.json()["detail"]

    def test_github_callback_app_not_found(self, client):
        """Test callback when app is deleted during flow."""
        test_client, mock_db = client

        _setup_mock_db_result(mock_db, None)

        # Mock the get_oauth_state to return valid state data
        with patch("src.controllers.oauth.github.get_oauth_state") as mock_get_state:
            mock_get_state.return_value = {"oauth_app_id": 1, "redirect_url": "https://example.com/oauth-apps"}

            response = test_client.get(
                "/api/v1/oauth/github/callback", params={"code": "test_code", "state": "valid_state"}
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGitHubDisconnect:
    """Tests for GitHub OAuth disconnect endpoint."""

    def test_github_disconnect_tool_not_found(self, authenticated_client):
        """Test disconnect when tool not found."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        # Mock db.execute -> result.scalar_one_or_none() for tool lookup
        _setup_mock_db_result(mock_db, None)

        response = test_client.post(
            "/api/v1/oauth/github/disconnect", json={"agent_id": str(uuid.uuid4()), "tool_name": "github_tool"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Tool configuration not found" in response.json()["detail"]

    def test_github_disconnect_success(self, authenticated_client):
        """Test successful disconnect."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_tool = MagicMock()
        mock_tool.config = {"GITHUB_OAUTH_TOKEN": "encrypted_token", "GITHUB_USER": "testuser"}
        _setup_mock_db_result(mock_db, mock_tool)

        with (
            patch("src.controllers.oauth.github.decrypt_value") as mock_decrypt,
            patch("src.controllers.oauth.github.get_oauth_app_from_db") as mock_get_app,
            patch("src.controllers.oauth.github.GitHubOAuth") as MockGitHub,
        ):
            mock_decrypt.return_value = "decrypted_token"
            mock_app = _create_mock_oauth_app()
            mock_get_app.return_value = mock_app

            mock_oauth = MagicMock()
            mock_oauth.revoke_token = AsyncMock()
            MockGitHub.return_value = mock_oauth

            response = test_client.post(
                "/api/v1/oauth/github/disconnect", json={"agent_id": str(uuid.uuid4()), "tool_name": "github_tool"}
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.json()["success"] is True


class TestGitHubStatus:
    """Tests for GitHub OAuth status endpoint."""

    def test_github_status_not_connected(self, authenticated_client):
        """Test status when tool not configured."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        # Mock db.execute -> result.scalar_one_or_none() for tool lookup
        _setup_mock_db_result(mock_db, None)

        response = test_client.get(
            "/api/v1/oauth/github/status", params={"agent_id": str(uuid.uuid4()), "tool_name": "github_tool"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["connected"] is False

    def test_github_status_connected(self, authenticated_client):
        """Test status when connected."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_tool = MagicMock()
        mock_tool.config = {
            "GITHUB_OAUTH_TOKEN": "encrypted_token",
            "GITHUB_USER": "testuser",
            "GITHUB_USER_NAME": "Test User",
        }

        # Mock db.execute -> result.scalar_one_or_none() for tool lookup
        _setup_mock_db_result(mock_db, mock_tool)

        response = test_client.get(
            "/api/v1/oauth/github/status", params={"agent_id": str(uuid.uuid4()), "tool_name": "github_tool"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["connected"] is True
        assert data["user"] == "testuser"


class TestGitHubRepositories:
    """Tests for GitHub repositories endpoint."""

    def test_list_repositories_app_not_found(self, authenticated_client):
        """Test listing repos when app not found."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        _setup_mock_db_result(mock_db, None)

        response = test_client.get("/api/v1/oauth/github/repositories", params={"oauth_app_id": 999})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_repositories_no_token(self, authenticated_client):
        """Test listing repos without token."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app()
        mock_app.access_token = None
        _setup_mock_db_result(mock_db, mock_app)

        response = test_client.get("/api/v1/oauth/github/repositories", params={"oauth_app_id": 1})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "No OAuth access token" in response.json()["detail"]


class TestOAuthAppsManagement:
    """Tests for OAuth apps CRUD endpoints."""

    def test_list_oauth_apps_success(self, authenticated_client):
        """Test listing OAuth apps."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_apps = [_create_mock_oauth_app(), _create_mock_oauth_app(provider="slack")]

        _setup_mock_db_result_list(mock_db, mock_apps)

        response = test_client.get("/api/v1/oauth/apps")

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)

    def test_list_oauth_apps_with_provider_filter(self, authenticated_client):
        """Test listing OAuth apps filtered by provider."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_apps = [_create_mock_oauth_app()]

        _setup_mock_db_result_list(mock_db, mock_apps)

        response = test_client.get("/api/v1/oauth/apps", params={"provider": "github"})

        assert response.status_code == status.HTTP_200_OK

    def test_get_oauth_app_success(self, authenticated_client):
        """Test getting a specific OAuth app."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app()
        _setup_mock_db_result(mock_db, mock_app)

        response = test_client.get("/api/v1/oauth/apps/1")

        assert response.status_code == status.HTTP_200_OK

    def test_get_oauth_app_not_found(self, authenticated_client):
        """Test getting nonexistent OAuth app."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        _setup_mock_db_result(mock_db, None)

        response = test_client.get("/api/v1/oauth/apps/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_oauth_app_success(self, authenticated_client):
        """Test creating an OAuth app."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        # Mock db.execute -> result.scalar_one_or_none() for duplicate check (returns None = no duplicate)
        _setup_mock_db_result(mock_db, None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch("src.controllers.oauth.apps.encrypt_value") as mock_encrypt:
            mock_encrypt.return_value = "encrypted_value"

            response = test_client.post(
                "/api/v1/oauth/apps",
                json={
                    "provider": "github",
                    "app_name": "My GitHub App",
                    "auth_method": "oauth",
                    "client_id": "test_client_id",
                    "client_secret": "test_secret",
                    "redirect_uri": "https://example.com/callback",
                },
            )

            assert response.status_code == status.HTTP_200_OK

    def test_create_oauth_app_invalid_auth_method(self, authenticated_client):
        """Test creating app with invalid auth method."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        response = test_client.post(
            "/api/v1/oauth/apps",
            json={
                "provider": "github",
                "app_name": "My GitHub App",
                "auth_method": "invalid",
                "client_id": "test_client_id",
                "client_secret": "test_secret",
                "redirect_uri": "https://example.com/callback",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "auth_method must be" in response.json()["detail"]

    def test_create_oauth_app_missing_oauth_fields(self, authenticated_client):
        """Test creating OAuth app without required OAuth fields."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        response = test_client.post(
            "/api/v1/oauth/apps",
            json={
                "provider": "github",
                "app_name": "My GitHub App",
                "auth_method": "oauth",
                # Missing client_id, client_secret, redirect_uri
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "client_id, client_secret, and redirect_uri are required" in response.json()["detail"]

    def test_create_oauth_app_api_token_missing_token(self, authenticated_client):
        """Test creating API token app without token."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        response = test_client.post(
            "/api/v1/oauth/apps",
            json={
                "provider": "github",
                "app_name": "My GitHub App",
                "auth_method": "api_token",
                # Missing api_token
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "api_token is required" in response.json()["detail"]

    def test_create_mailisk_oauth_app_requires_namespace(self, authenticated_client):
        """Mailisk tenant integrations must include config.namespace."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        response = test_client.post(
            "/api/v1/oauth/apps",
            json={
                "provider": "mailisk",
                "app_name": "Tenant Mailisk",
                "auth_method": "api_token",
                "api_token": "mailisk_test_key",
                "config": {},
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Mailisk integrations require config.namespace"

    def test_create_oauth_app_duplicate(self, authenticated_client):
        """Test creating duplicate app."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        existing_app = _create_mock_oauth_app()

        # Mock db.execute -> result.scalar_one_or_none() for duplicate check (returns existing app)
        _setup_mock_db_result(mock_db, existing_app)

        response = test_client.post(
            "/api/v1/oauth/apps",
            json={
                "provider": "github",
                "app_name": "Test Github App",
                "auth_method": "oauth",
                "client_id": "test_client_id",
                "client_secret": "test_secret",
                "redirect_uri": "https://example.com/callback",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"]

    def test_update_oauth_app_success(self, authenticated_client):
        """Test updating an OAuth app."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app()
        _setup_mock_db_result(mock_db, mock_app)

        response = test_client.put("/api/v1/oauth/apps/1", json={"app_name": "Updated Name"})

        assert response.status_code == status.HTTP_200_OK

    def test_update_oauth_app_not_found(self, authenticated_client):
        """Test updating nonexistent app."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        _setup_mock_db_result(mock_db, None)

        response = test_client.put("/api/v1/oauth/apps/999", json={"app_name": "Updated Name"})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_oauth_app_invalid_auth_method(self, authenticated_client):
        """Test updating with invalid auth method."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app()
        _setup_mock_db_result(mock_db, mock_app)

        response = test_client.put("/api/v1/oauth/apps/1", json={"auth_method": "invalid"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_oauth_app_success(self, authenticated_client):
        """Test deleting an OAuth app."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app()
        _setup_mock_db_result(mock_db, mock_app)

        response = test_client.delete("/api/v1/oauth/apps/1")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True

    def test_delete_oauth_app_not_found(self, authenticated_client):
        """Test deleting nonexistent app."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        _setup_mock_db_result(mock_db, None)

        response = test_client.delete("/api/v1/oauth/apps/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSlackAuthorize:
    """Tests for Slack OAuth authorize endpoint."""

    def test_slack_authorize_app_not_found(self, client):
        """Test authorization with nonexistent app returns error."""
        test_client, mock_db = client

        _setup_mock_db_result(mock_db, None)

        response = test_client.get(
            "/api/v1/oauth/slack/authorize", params={"oauth_app_id": 999}, follow_redirects=False
        )

        # The endpoint catches all exceptions and returns 500
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_slack_authorize_api_token_method(self, client):
        """Test Slack authorization with API token method."""
        test_client, mock_db = client

        mock_app = _create_mock_oauth_app(provider="slack", auth_method="api_token")
        _setup_mock_db_result(mock_db, mock_app)

        with patch("src.controllers.oauth.slack.get_app_base_url") as mock_get_url:
            mock_get_url.return_value = "https://example.com"

            response = test_client.get(
                "/api/v1/oauth/slack/authorize", params={"oauth_app_id": 1}, follow_redirects=False
            )

            assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
            assert "provider=slack" in response.headers["location"]


class TestSlackCallback:
    """Tests for Slack OAuth callback endpoint."""

    def test_slack_callback_invalid_state(self, client):
        """Test callback with invalid state."""
        test_client, mock_db = client

        response = test_client.get(
            "/api/v1/oauth/slack/callback", params={"code": "test_code", "state": "invalid_state"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestZoomAuthorize:
    """Tests for Zoom OAuth authorize endpoint."""

    def test_zoom_authorize_app_not_found(self, client):
        """Test authorization with nonexistent app returns error."""
        test_client, mock_db = client

        _setup_mock_db_result(mock_db, None)

        response = test_client.get("/api/v1/oauth/zoom/authorize", params={"oauth_app_id": 999}, follow_redirects=False)

        # The endpoint catches all exceptions and returns 500
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestZoomCallback:
    """Tests for Zoom OAuth callback endpoint."""

    def test_zoom_callback_invalid_state(self, client):
        """Test callback with invalid state."""
        test_client, mock_db = client

        response = test_client.get(
            "/api/v1/oauth/zoom/callback", params={"code": "test_code", "state": "invalid_state"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGmailAuthorize:
    """Tests for Gmail OAuth authorize endpoint."""

    def test_gmail_authorize_app_not_found(self, client):
        """Test authorization with nonexistent app returns error."""
        test_client, mock_db = client

        _setup_mock_db_result(mock_db, None)

        response = test_client.get(
            "/api/v1/oauth/gmail/authorize", params={"oauth_app_id": 999}, follow_redirects=False
        )

        # The endpoint catches all exceptions and returns 500
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_gmail_authorize_api_token_method(self, client):
        """Test Gmail authorization with API token method."""
        test_client, mock_db = client

        mock_app = _create_mock_oauth_app(provider="gmail", auth_method="api_token")
        _setup_mock_db_result(mock_db, mock_app)

        with patch("src.controllers.oauth.google.get_app_base_url") as mock_get_url:
            mock_get_url.return_value = "https://example.com"

            response = test_client.get(
                "/api/v1/oauth/gmail/authorize", params={"oauth_app_id": 1}, follow_redirects=False
            )

            assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
            assert "provider=gmail" in response.headers["location"]


class TestGmailCallback:
    """Tests for Gmail OAuth callback endpoint."""

    def test_gmail_callback_invalid_state(self, client):
        """Test callback with invalid state."""
        test_client, mock_db = client

        response = test_client.get(
            "/api/v1/oauth/gmail/callback", params={"code": "test_code", "state": "invalid_state"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGoogleCalendarAuthorize:
    """Tests for Google Calendar OAuth authorize endpoint."""

    def test_google_calendar_authorize_app_not_found(self, client):
        """Test authorization with nonexistent app returns error."""
        test_client, mock_db = client

        _setup_mock_db_result(mock_db, None)

        response = test_client.get(
            "/api/v1/oauth/google_calendar/authorize", params={"oauth_app_id": 999}, follow_redirects=False
        )

        # The endpoint catches all exceptions and returns 500
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestGoogleCalendarCallback:
    """Tests for Google Calendar OAuth callback endpoint."""

    def test_google_calendar_callback_invalid_state(self, client):
        """Test callback with invalid state."""
        test_client, mock_db = client

        response = test_client.get(
            "/api/v1/oauth/google_calendar/callback", params={"code": "test_code", "state": "invalid_state"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGoogleDriveAuthorize:
    """Tests for Google Drive OAuth authorize endpoint."""

    def test_google_drive_authorize_app_not_found(self, client):
        """Test authorization with nonexistent app returns error."""
        test_client, mock_db = client

        _setup_mock_db_result(mock_db, None)

        response = test_client.get(
            "/api/v1/oauth/google_drive/authorize", params={"oauth_app_id": 999}, follow_redirects=False
        )

        # The endpoint catches all exceptions and returns 500
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestGoogleDriveCallback:
    """Tests for Google Drive OAuth callback endpoint."""

    def test_google_drive_callback_invalid_state(self, client):
        """Test callback with invalid state."""
        test_client, mock_db = client

        response = test_client.get(
            "/api/v1/oauth/google_drive/callback", params={"code": "test_code", "state": "invalid_state"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGetOAuthAppFromDb:
    """Tests for get_oauth_app_from_db helper function."""

    @pytest.mark.asyncio
    async def test_get_oauth_app_by_id(self, mock_db_session):
        """Test getting OAuth app by specific ID."""
        from src.controllers.oauth import get_oauth_app_from_db

        mock_app = _create_mock_oauth_app()
        _setup_mock_db_result(mock_db_session, mock_app)

        result = await get_oauth_app_from_db(mock_db_session, "github", app_id=1)

        assert result == mock_app

    @pytest.mark.asyncio
    async def test_get_oauth_app_not_found_raises(self, mock_db_session):
        """Test that missing OAuth app raises HTTPException."""
        from fastapi import HTTPException

        from src.controllers.oauth import get_oauth_app_from_db

        _setup_mock_db_result(mock_db_session, None)

        with pytest.raises(HTTPException) as exc_info:
            await get_oauth_app_from_db(mock_db_session, "github")

        assert exc_info.value.status_code == 404
        assert "Github OAuth not configured" in exc_info.value.detail


class TestUserTokens:
    """
    Tests for user OAuth token endpoints.

    These tests cover the bug where Account.tenant_id was accessed directly,
    but tenant_id lives in the JWT payload, not on the Account model.
    All three endpoints must work when the user is authenticated.
    """

    def test_list_user_tokens_authenticated(self, authenticated_client):
        """GET /user-tokens — must not crash with 'Account has no attribute tenant_id'."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        _setup_mock_db_result_list(mock_db, [])

        response = test_client.get("/api/v1/oauth/user-tokens")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_user_tokens_with_tokens(self, authenticated_client):
        """GET /user-tokens returns token list with provider info."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app(provider="github")
        mock_app.tenant_id = None  # platform app — passes the tenant security check

        mock_token = MagicMock()
        mock_token.oauth_app_id = 1
        mock_token.oauth_app = mock_app  # selectinload populates relationship directly
        mock_token.to_dict.return_value = {"id": str(uuid.uuid4()), "provider": "github"}

        # Single execute call — selectinload means no second query for oauth_app
        _setup_mock_db_result_list(mock_db, [mock_token])

        response = test_client.get("/api/v1/oauth/user-tokens")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_delete_user_token_not_found(self, authenticated_client):
        """DELETE /user-tokens/{id} — 404 when token not found."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        _setup_mock_db_result(mock_db, None)

        response = test_client.delete(f"/api/v1/oauth/user-tokens/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_user_token_success(self, authenticated_client):
        """DELETE /user-tokens/{id} — must not crash with 'Account has no attribute tenant_id'."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_token = MagicMock()
        mock_token.oauth_app_id = 1
        mock_app = _create_mock_oauth_app(provider="github")

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            r = MagicMock()
            r.scalar_one_or_none.return_value = mock_token if call_count == 1 else mock_app
            return r

        mock_db.execute = multi_execute
        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        response = test_client.delete(f"/api/v1/oauth/user-tokens/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True

    def test_save_api_token_not_found(self, authenticated_client):
        """POST /user-tokens/api-token — 404 when OAuth app not found."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        _setup_mock_db_result(mock_db, None)

        response = test_client.post(
            "/api/v1/oauth/user-tokens/api-token",
            json={"oauth_app_id": 999, "api_token": "mytoken"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_save_api_token_wrong_auth_method(self, authenticated_client):
        """POST /user-tokens/api-token — 400 when app uses OAuth, not api_token."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app(auth_method="oauth")
        _setup_mock_db_result(mock_db, mock_app)

        response = test_client.post(
            "/api/v1/oauth/user-tokens/api-token",
            json={"oauth_app_id": 1, "api_token": "mytoken"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "api token" in response.json()["detail"].lower()

    def test_save_api_token_create_success(self, authenticated_client):
        """POST /user-tokens/api-token — creates new token; must not crash with tenant_id error.

        UserOAuthToken.access_token is an auto-encrypting property (see
        src/models/user_oauth_token.py) — the endpoint must assign the raw plaintext
        token directly and let the property encrypt it. Calling encrypt_value() first
        (the original bug across every OAuth provider callback in this codebase) would
        double-encrypt it, producing a token that never decrypts back to the original.
        """
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app(auth_method="api_token")

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            r = MagicMock()
            # First call: _get_oauth_app_secure returns the app
            # Second call: check existing token — returns None (no existing token)
            r.scalar_one_or_none.return_value = mock_app if call_count == 1 else None
            return r

        mock_db.execute = multi_execute
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        response = test_client.post(
            "/api/v1/oauth/user-tokens/api-token",
            json={"oauth_app_id": 1, "api_token": "mytoken"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        # The UserOAuthToken passed to db.add() must carry the raw plaintext token —
        # not something pre-encrypted by the endpoint itself.
        added_token = mock_db.add.call_args.args[0]
        assert added_token.access_token == "mytoken"

    def test_save_api_token_update_existing(self, authenticated_client):
        """POST /user-tokens/api-token — updates existing token.

        See test_save_api_token_create_success for why the assigned value must be the
        raw plaintext, not an encrypt_value()-wrapped one.
        """
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app(auth_method="api_token")
        mock_existing_token = MagicMock()

        call_count = 0

        async def multi_execute(stmt):
            nonlocal call_count
            call_count += 1
            r = MagicMock()
            r.scalar_one_or_none.return_value = mock_app if call_count == 1 else mock_existing_token
            return r

        mock_db.execute = multi_execute
        mock_db.commit = AsyncMock()

        response = test_client.post(
            "/api/v1/oauth/user-tokens/api-token",
            json={"oauth_app_id": 1, "api_token": "newtoken"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        assert mock_existing_token.access_token == "newtoken"


class TestAuthorizeWithAuthenticatedUser:
    """
    Tests that authorize endpoints work when the user IS authenticated.

    The bug only fired when current_account was not None — unauthenticated
    tests always took the 'else None' branch and never hit the crash.
    """

    def test_github_authorize_authenticated_api_token(self, authenticated_client):
        """GitHub authorize with authenticated user must not crash on tenant_id."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app(auth_method="api_token")
        _setup_mock_db_result(mock_db, mock_app)

        with patch("src.controllers.oauth.github.get_app_base_url") as mock_get_url:
            mock_get_url.return_value = "https://example.com"

            response = test_client.get(
                "/api/v1/oauth/github/authorize", params={"oauth_app_id": 1}, follow_redirects=False
            )

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert "oauth=success" in response.headers["location"]

    def test_slack_authorize_authenticated_api_token(self, authenticated_client):
        """Slack authorize with authenticated user must not crash on tenant_id."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app(provider="slack", auth_method="api_token")
        _setup_mock_db_result(mock_db, mock_app)

        with patch("src.controllers.oauth.slack.get_app_base_url") as mock_get_url:
            mock_get_url.return_value = "https://example.com"

            response = test_client.get(
                "/api/v1/oauth/slack/authorize", params={"oauth_app_id": 1}, follow_redirects=False
            )

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT

    def test_gmail_authorize_authenticated_api_token(self, authenticated_client):
        """Gmail authorize with authenticated user must not crash on tenant_id."""
        test_client, mock_db, tenant_id, mock_account = authenticated_client

        mock_app = _create_mock_oauth_app(provider="gmail", auth_method="api_token")
        _setup_mock_db_result(mock_db, mock_app)

        with patch("src.controllers.oauth.google.get_app_base_url") as mock_get_url:
            mock_get_url.return_value = "https://example.com"

            response = test_client.get(
                "/api/v1/oauth/gmail/authorize", params={"oauth_app_id": 1}, follow_redirects=False
            )

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
