"""Tests for profiles controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.profiles import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account


@pytest.fixture
def mock_profile_service():
    with patch("src.controllers.profiles.ProfileService") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_db_session():
    db = AsyncMock()
    # Use a plain MagicMock for execute() return so scalar_one_or_none() is NOT
    # an async coroutine (coroutines are truthy and cause attribute errors).
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)
    return db


@pytest.fixture
def client(mock_profile_service, mock_db_session):
    app = FastAPI()
    app.include_router(router)

    # Mock dependencies
    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db

    # Mock current account
    mock_account = MagicMock()
    mock_account.id = uuid.uuid4()
    mock_account.email = "test@example.com"
    app.dependency_overrides[get_current_account] = lambda: mock_account

    return TestClient(app), mock_account, mock_db_session, mock_profile_service


def _create_mock_profile(account_id, **kwargs):
    """Helper to create mock profile."""
    mock_profile = MagicMock()
    mock_profile.id = account_id
    mock_profile.name = kwargs.get("name", "Test User")
    mock_profile.email = kwargs.get("email", "test@example.com")
    mock_profile.phone = kwargs.get("phone")
    mock_profile.bio = kwargs.get("bio")
    mock_profile.company = kwargs.get("company")
    mock_profile.job_title = kwargs.get("job_title")
    mock_profile.location = kwargs.get("location")
    mock_profile.website = kwargs.get("website")
    mock_profile.avatar_url = kwargs.get("avatar_url")
    mock_profile.two_factor_enabled = kwargs.get("two_factor_enabled", False)
    mock_profile.is_platform_admin = kwargs.get("is_platform_admin", False)
    mock_profile.notification_preferences = kwargs.get("notification_preferences", {})
    mock_profile.last_login_at = kwargs.get("last_login_at", datetime.now(UTC))
    mock_profile.created_at = datetime.now(UTC)
    mock_profile.updated_at = datetime.now(UTC)
    return mock_profile


class TestGetMyProfile:
    """Tests for getting current user's profile."""

    def test_get_profile_success(self, client):
        """Test getting current user's profile."""
        test_client, mock_account, mock_db, mock_service = client

        mock_profile = _create_mock_profile(mock_account.id)
        mock_service.return_value.get_profile.return_value = mock_profile

        response = test_client.get("/profile/me")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(mock_account.id)
        assert data["name"] == "Test User"

    def test_get_profile_not_found(self, client):
        """Test getting profile when not found."""
        test_client, mock_account, mock_db, mock_service = client

        mock_service.return_value.get_profile.return_value = None

        response = test_client.get("/profile/me")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateMyProfile:
    """Tests for updating current user's profile."""

    def test_update_profile_success(self, client):
        """Test updating profile."""
        test_client, mock_account, mock_db, mock_service = client

        mock_profile = _create_mock_profile(mock_account.id, name="Updated Name")
        mock_service.return_value.update_profile.return_value = mock_profile

        response = test_client.put("/profile/me", json={"name": "Updated Name"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_update_profile_multiple_fields(self, client):
        """Test updating multiple profile fields."""
        test_client, mock_account, mock_db, mock_service = client

        mock_profile = _create_mock_profile(mock_account.id, name="Updated Name", bio="New bio", company="Acme Corp")
        mock_service.return_value.update_profile.return_value = mock_profile

        response = test_client.put(
            "/profile/me", json={"name": "Updated Name", "bio": "New bio", "company": "Acme Corp"}
        )

        assert response.status_code == status.HTTP_200_OK

    def test_update_profile_invalid_email(self, client):
        """Test updating profile with invalid email."""
        test_client, mock_account, mock_db, mock_service = client

        response = test_client.put("/profile/me", json={"email": "invalid-email"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_update_profile_error(self, client):
        """Test updating profile with error."""
        test_client, mock_account, mock_db, mock_service = client

        mock_service.return_value.update_profile.side_effect = ValueError("Email already exists")

        response = test_client.put("/profile/me", json={"email": "existing@example.com"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestUploadAvatar:
    """Tests for uploading profile avatar."""

    def test_upload_avatar_success(self, client):
        """Test uploading avatar."""
        test_client, mock_account, mock_db, mock_service = client

        mock_profile = _create_mock_profile(mock_account.id, avatar_url="https://s3.example.com/avatar.png")
        mock_service.return_value.upload_avatar.return_value = mock_profile

        # Create test PNG file with valid magic bytes (PNG signature)
        png_magic = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # PNG header + padding
        files = {"file": ("avatar.png", png_magic, "image/png")}

        response = test_client.post("/profile/me/avatar", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["avatar_url"] is not None

    def test_upload_avatar_non_image(self, client):
        """Test uploading non-image file as avatar."""
        test_client, mock_account, mock_db, mock_service = client

        files = {"file": ("doc.pdf", b"PDF content", "application/pdf")}

        response = test_client.post("/profile/me/avatar", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_avatar_too_large(self, client):
        """Test uploading avatar that exceeds size limit."""
        test_client, mock_account, mock_db, mock_service = client

        # Create large content (>5MB)
        large_content = b"x" * (6 * 1024 * 1024)
        files = {"file": ("avatar.png", large_content, "image/png")}

        response = test_client.post("/profile/me/avatar", files=files)

        # 413 Request Entity Too Large is the correct HTTP status for oversized files
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_413_CONTENT_TOO_LARGE]


class TestDeleteAvatar:
    """Tests for deleting profile avatar."""

    def test_delete_avatar_success(self, client):
        """Test deleting avatar."""
        test_client, mock_account, mock_db, mock_service = client

        mock_profile = _create_mock_profile(mock_account.id, avatar_url=None)
        mock_service.return_value.delete_avatar.return_value = mock_profile

        response = test_client.delete("/profile/me/avatar")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["avatar_url"] is None


class TestChangePassword:
    """Tests for changing password."""

    def test_change_password_success(self, client):
        """Test changing password."""
        test_client, mock_account, mock_db, mock_service = client

        response = test_client.post(
            "/profile/me/password", json={"current_password": "OldSecurePass123!", "new_password": "NewSecurePass456!"}
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_service.return_value.change_password.assert_called_once()

    def test_change_password_wrong_current(self, client):
        """Test changing password with wrong current password."""
        test_client, mock_account, mock_db, mock_service = client

        mock_service.return_value.change_password.side_effect = ValueError("Current password is incorrect")

        response = test_client.post(
            "/profile/me/password", json={"current_password": "WrongSecurePass1!", "new_password": "NewSecurePass456!"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_too_short(self, client):
        """Test changing password with too short password."""
        test_client, mock_account, mock_db, mock_service = client

        response = test_client.post("/profile/me/password", json={"current_password": "old", "new_password": "new"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestEnableTwoFactor:
    """Tests for enabling two-factor authentication."""

    def test_enable_2fa_success(self, client):
        """Test enabling 2FA."""
        test_client, mock_account, mock_db, mock_service = client

        mock_pyotp = MagicMock()
        mock_pyotp.random_base32.return_value = "JBSWY3DPEHPK3PXP"
        mock_totp = MagicMock()
        mock_totp.provisioning_uri.return_value = "otpauth://totp/App:test@example.com?secret=JBSWY3DPEHPK3PXP"
        mock_pyotp.TOTP.return_value = mock_totp

        with patch.dict("sys.modules", {"pyotp": mock_pyotp}):
            with patch("src.services.auth_service.AuthService.verify_password", return_value=True):
                response = test_client.post("/profile/me/2fa/enable", json={"password": "SecureTestPass123!"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "secret" in data
        assert "qr_code_url" in data

    def test_enable_2fa_wrong_password(self, client):
        """Test enabling 2FA with wrong password."""
        test_client, mock_account, mock_db, mock_service = client

        mock_pyotp = MagicMock()
        mock_pyotp.random_base32.return_value = "JBSWY3DPEHPK3PXP"

        with patch.dict("sys.modules", {"pyotp": mock_pyotp}):
            with patch("src.services.auth_service.AuthService.verify_password", return_value=False):
                response = test_client.post("/profile/me/2fa/enable", json={"password": "wrong_password"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestVerifyTwoFactor:
    """Tests for verifying two-factor authentication setup."""

    def test_verify_2fa_success(self, client):
        """Test verifying 2FA setup."""
        test_client, mock_account, mock_db, mock_service = client

        mock_profile = _create_mock_profile(mock_account.id, two_factor_enabled=True)
        # Controller uses is_valid = await profile_service.verify_two_factor(...) as a bool check
        mock_service.return_value.verify_two_factor.return_value = True

        # Controller re-queries DB for updated_profile; provide it via mock_db
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_profile
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.services.auth_service.AuthService.generate_backup_codes", new_callable=AsyncMock
        ) as mock_backup:
            mock_backup.return_value = ["BACKUP1", "BACKUP2"]
            response = test_client.post("/profile/me/2fa/verify", json={"token": "123456"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["two_factor_enabled"] is True

    def test_verify_2fa_invalid_token(self, client):
        """Test verifying 2FA with invalid token."""
        test_client, mock_account, mock_db, mock_service = client

        mock_service.return_value.verify_two_factor.side_effect = ValueError("Invalid token")

        response = test_client.post("/profile/me/2fa/verify", json={"token": "000000"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestDisableTwoFactor:
    """Tests for disabling two-factor authentication."""

    def test_disable_2fa_success(self, client):
        """Test disabling 2FA."""
        test_client, mock_account, mock_db, mock_service = client

        mock_profile = _create_mock_profile(mock_account.id, two_factor_enabled=False)
        mock_service.return_value.disable_two_factor.return_value = mock_profile

        response = test_client.post("/profile/me/2fa/disable")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["two_factor_enabled"] is False
