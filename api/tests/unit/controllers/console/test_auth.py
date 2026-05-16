"""Tests for console auth controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.console.auth import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account


@pytest.fixture
def mock_db_session():
    db = AsyncMock()
    # Use a plain MagicMock for execute() return so scalar_one_or_none() is NOT
    # an async coroutine (coroutines are truthy and would trigger SAML/MFA 403 checks).
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)
    return db


@pytest.fixture
def mock_account():
    account = MagicMock()
    account.id = uuid.uuid4()
    account.email = "test@example.com"
    account.name = "Test User"
    account.status = "active"
    account.created_at = datetime.now(UTC)
    account.tenant_id = uuid.uuid4()
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


class TestLogin:
    """Tests for login endpoint."""

    def test_login_success(self, client):
        """Test successful login."""
        test_client, mock_db = client

        mock_account = MagicMock()
        mock_account.id = uuid.uuid4()
        mock_account.email = "test@example.com"
        mock_account.name = "Test User"
        mock_account.status = "active"
        mock_account.two_factor_enabled = False
        mock_account.two_factor_secret = None

        mock_tenant = {"tenant_id": str(uuid.uuid4()), "name": "Test Tenant"}

        with (
            patch("src.controllers.console.auth.AuthService") as MockAuthService,
            patch("src.controllers.console.auth.SessionService") as MockSessionService,
        ):
            MockAuthService.authenticate = AsyncMock(return_value=mock_account)
            MockAuthService.get_account_tenants = AsyncMock(return_value=[mock_tenant])
            MockSessionService.create_session = AsyncMock(
                return_value={
                    "access_token": "test_token",
                    "refresh_token": "refresh_token",
                    "expires_in": 3600,
                }
            )

            response = test_client.post("/login", json={"email": "test@example.com", "password": "SecureTestPass123!"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        test_client, mock_db = client

        with patch("src.controllers.console.auth.AuthService") as MockAuthService:
            MockAuthService.authenticate = AsyncMock(return_value=None)

            response = test_client.post("/login", json={"email": "test@example.com", "password": "WrongTestPass123!"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_invalid_email(self, client):
        """Test login with invalid email format."""
        test_client, mock_db = client

        response = test_client.post("/login", json={"email": "invalid-email", "password": "SecureTestPass123!"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_login_short_password(self, client):
        """Test login with password too short."""
        test_client, mock_db = client

        response = test_client.post("/login", json={"email": "test@example.com", "password": "short"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestRegister:
    """Tests for registration endpoint."""

    def test_register_success(self, client):
        """Test successful registration."""
        test_client, mock_db = client

        mock_account = MagicMock()
        mock_account.id = uuid.uuid4()
        mock_account.email = "new@example.com"
        mock_account.name = "New User"
        mock_account.status = "pending"

        mock_tenant = MagicMock()
        mock_tenant.id = uuid.uuid4()
        mock_tenant.name = "New Tenant"
        mock_tenant.plan = "free"
        mock_tenant.status = "active"

        with (
            patch("src.controllers.console.auth.AuthService") as MockAuthService,
            patch(
                "src.controllers.console.auth.get_app_base_url",
                new_callable=AsyncMock,
                return_value="https://example.com",
            ),
            patch("src.tasks.email_tasks.send_verification_email_task") as mock_email,
        ):
            MockAuthService.register = AsyncMock(return_value=(mock_account, mock_tenant))
            mock_email.delay = MagicMock()

            response = test_client.post(
                "/register", json={"email": "new@example.com", "password": "SecureTestPass123!", "name": "New User"}
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["success"] is True
        assert "verify your account" in data["message"]

    def test_register_with_tenant_name(self, client):
        """Test registration with custom tenant name."""
        test_client, mock_db = client

        mock_account = MagicMock()
        mock_account.id = uuid.uuid4()
        mock_account.email = "new@example.com"
        mock_account.name = "New User"
        mock_account.status = "pending"

        mock_tenant = MagicMock()
        mock_tenant.id = uuid.uuid4()
        mock_tenant.name = "My Company"
        mock_tenant.plan = "free"
        mock_tenant.status = "active"

        with (
            patch("src.controllers.console.auth.AuthService") as MockAuthService,
            patch(
                "src.controllers.console.auth.get_app_base_url",
                new_callable=AsyncMock,
                return_value="https://example.com",
            ),
            patch("src.tasks.email_tasks.send_verification_email_task") as mock_email,
        ):
            MockAuthService.register = AsyncMock(return_value=(mock_account, mock_tenant))
            mock_email.delay = MagicMock()

            response = test_client.post(
                "/register",
                json={
                    "email": "new@example.com",
                    "password": "SecureTestPass123!",
                    "name": "New User",
                    "tenant_name": "My Company",
                },
            )

        assert response.status_code == status.HTTP_201_CREATED

    def test_register_existing_email(self, client):
        """Test registration with existing email."""
        test_client, mock_db = client

        with patch("src.controllers.console.auth.AuthService") as MockAuthService:
            MockAuthService.register = AsyncMock(side_effect=ValueError("Email already registered"))

            response = test_client.post(
                "/register",
                json={"email": "existing@example.com", "password": "SecureTestPass123!", "name": "Existing User"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestRefresh:
    """Tests for token refresh endpoint."""

    def test_refresh_success(self, client):
        """Test successful token refresh."""
        test_client, mock_db = client

        with patch("src.controllers.console.auth.SessionService") as MockSessionService:
            MockSessionService.refresh_session = AsyncMock(
                return_value={
                    "access_token": "new_token",
                    "refresh_token": "new_refresh",
                    "expires_in": 3600,
                }
            )

            response = test_client.post("/refresh", json={"refresh_token": "valid_refresh_token"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]

    def test_refresh_invalid_token(self, client):
        """Test refresh with invalid token."""
        test_client, mock_db = client

        with patch("src.controllers.console.auth.SessionService") as MockSessionService:
            MockSessionService.refresh_session = AsyncMock(side_effect=ValueError("Invalid refresh token"))

            response = test_client.post("/refresh", json={"refresh_token": "invalid_token"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_with_tenant_id(self, client):
        """Test refresh with tenant ID preserved."""
        test_client, mock_db = client

        tenant_id = str(uuid.uuid4())

        with patch("src.controllers.console.auth.SessionService") as MockSessionService:
            MockSessionService.refresh_session = AsyncMock(
                return_value={
                    "access_token": "new_token",
                    "refresh_token": "new_refresh",
                }
            )

            response = test_client.post("/refresh", json={"refresh_token": "valid_token", "tenant_id": tenant_id})

        assert response.status_code == status.HTTP_200_OK


class TestLogout:
    """Tests for logout endpoint."""

    def test_logout_success(self, authenticated_client):
        """Test successful logout."""
        test_client, mock_db, mock_account = authenticated_client

        with patch("src.controllers.console.auth.SessionService") as MockSessionService:
            MockSessionService.revoke_session = AsyncMock()

            response = test_client.post("/logout")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Logout successful"


class TestGetCurrentUser:
    """Tests for getting current user."""

    def test_get_current_user_success(self, authenticated_client):
        """Test getting current user info."""
        test_client, mock_db, mock_account = authenticated_client

        mock_tenant = {"tenant_id": str(uuid.uuid4()), "name": "Test Tenant"}

        with patch("src.controllers.console.auth.AuthService") as MockAuthService:
            MockAuthService.get_account_tenants = AsyncMock(return_value=[mock_tenant])

            response = test_client.get("/me")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "account" in data["data"]
        assert "tenants" in data["data"]


class TestForgotPassword:
    """Tests for forgot password endpoint."""

    def test_forgot_password_success(self, client):
        """Test forgot password with valid email."""
        test_client, mock_db = client

        mock_account = MagicMock()
        mock_account.email = "test@example.com"
        mock_account.tenant_id = uuid.uuid4()

        with (
            patch("src.controllers.console.auth.AuthService") as MockAuthService,
            patch(
                "src.controllers.console.auth.get_app_base_url",
                new_callable=AsyncMock,
                return_value="https://example.com",
            ),
            patch("src.tasks.email_tasks.send_password_reset_email_task") as mock_email,
        ):
            MockAuthService.request_password_reset = AsyncMock(return_value=(mock_account, "reset_token"))
            mock_email.delay = MagicMock()

            response = test_client.post("/forgot-password", json={"email": "test@example.com"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_forgot_password_nonexistent_email(self, client):
        """Test forgot password with non-existent email."""
        test_client, mock_db = client

        with patch("src.controllers.console.auth.AuthService") as MockAuthService:
            MockAuthService.request_password_reset = AsyncMock(return_value=None)

            response = test_client.post("/forgot-password", json={"email": "nonexistent@example.com"})

        # Should still return success to prevent email enumeration
        assert response.status_code == status.HTTP_200_OK


class TestResetPassword:
    """Tests for reset password endpoint."""

    def test_reset_password_success(self, client):
        """Test successful password reset."""
        test_client, mock_db = client

        mock_account = MagicMock()
        mock_account.id = uuid.uuid4()

        with patch("src.controllers.console.auth.AuthService") as MockAuthService:
            MockAuthService.reset_password = AsyncMock(return_value=mock_account)

            response = test_client.post(
                "/reset-password", json={"token": "valid_reset_token", "new_password": "NewSecurePass123!!"}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_reset_password_invalid_token(self, client):
        """Test reset with invalid token."""
        test_client, mock_db = client

        with patch("src.controllers.console.auth.AuthService") as MockAuthService:
            MockAuthService.reset_password = AsyncMock(return_value=None)

            response = test_client.post(
                "/reset-password", json={"token": "invalid_token", "new_password": "NewSecurePass123!!"}
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestVerifyEmail:
    """Tests for email verification endpoint."""

    def test_verify_email_success(self, client):
        """Test successful email verification."""
        test_client, mock_db = client

        mock_account = MagicMock()
        mock_account.id = uuid.uuid4()
        mock_account.email = "test@example.com"
        mock_account.name = "Test User"

        with patch("src.controllers.console.auth.AuthService") as MockAuthService:
            MockAuthService.verify_email = AsyncMock(return_value=mock_account)

            response = test_client.post("/verify-email", json={"token": "valid_verification_token"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "account" in data["data"]

    def test_verify_email_invalid_token(self, client):
        """Test verification with invalid token."""
        test_client, mock_db = client

        with patch("src.controllers.console.auth.AuthService") as MockAuthService:
            MockAuthService.verify_email = AsyncMock(return_value=None)

            response = test_client.post("/verify-email", json={"token": "invalid_token"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestResendVerification:
    """Tests for resend verification email endpoint."""

    def test_resend_verification_success(self, client):
        """Test successful resend of verification email."""
        test_client, mock_db = client

        mock_account = MagicMock()
        mock_account.id = uuid.uuid4()
        mock_account.tenant_id = uuid.uuid4()

        # The controller does: result = await db.execute(select(Account).filter_by(email=data.email))
        # then: account = result.scalar_one_or_none()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_account
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "src.controllers.console.auth.get_app_base_url",
                new_callable=AsyncMock,
                return_value="https://example.com",
            ),
            patch("src.tasks.email_tasks.send_verification_email_task") as mock_email,
        ):
            mock_email.delay = MagicMock()

            response = test_client.post("/resend-verification", json={"email": "test@example.com"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_resend_verification_nonexistent_email(self, client):
        """Test resend for non-existent email."""
        test_client, mock_db = client

        # The controller does: result = await db.execute(select(Account).filter_by(email=data.email))
        # then: account = result.scalar_one_or_none()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.post("/resend-verification", json={"email": "nonexistent@example.com"})

        # Should still return success to prevent email enumeration
        assert response.status_code == status.HTTP_200_OK


class TestAliasRoutes:
    """Tests for alias routes."""

    def test_signup_alias(self, client):
        """Test that /signup is alias for /register."""
        test_client, mock_db = client

        mock_account = MagicMock()
        mock_account.id = uuid.uuid4()
        mock_account.email = "new@example.com"
        mock_account.name = "New User"
        mock_account.status = "pending"

        mock_tenant = MagicMock()
        mock_tenant.id = uuid.uuid4()
        mock_tenant.name = "Test Tenant"
        mock_tenant.plan = "free"
        mock_tenant.status = "active"

        with (
            patch("src.controllers.console.auth.AuthService") as MockAuthService,
            patch(
                "src.controllers.console.auth.get_app_base_url",
                new_callable=AsyncMock,
                return_value="https://example.com",
            ),
            patch("src.tasks.email_tasks.send_verification_email_task") as mock_email,
        ):
            MockAuthService.register = AsyncMock(return_value=(mock_account, mock_tenant))
            mock_email.delay = MagicMock()

            response = test_client.post(
                "/signup", json={"email": "new@example.com", "password": "SecureTestPass123!", "name": "New User"}
            )

        assert response.status_code == status.HTTP_201_CREATED

    def test_signin_alias(self, client):
        """Test that /signin is alias for /login."""
        test_client, mock_db = client

        mock_account = MagicMock()
        mock_account.id = uuid.uuid4()
        mock_account.email = "test@example.com"
        mock_account.name = "Test User"
        mock_account.status = "active"
        mock_account.two_factor_enabled = False
        mock_account.two_factor_secret = None

        with (
            patch("src.controllers.console.auth.AuthService") as MockAuthService,
            patch("src.controllers.console.auth.SessionService") as MockSessionService,
        ):
            MockAuthService.authenticate = AsyncMock(return_value=mock_account)
            MockAuthService.get_account_tenants = AsyncMock(return_value=[])
            MockSessionService.create_session = AsyncMock(
                return_value={"access_token": "token", "refresh_token": "refresh"}
            )

            response = test_client.post("/signin", json={"email": "test@example.com", "password": "SecureTestPass123!"})

        assert response.status_code == status.HTTP_200_OK
