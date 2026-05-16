"""
Integration tests for Authentication endpoints.

Tests login, registration, token refresh, and logout functionality.
"""

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TestAuthRegistration:
    """Test user registration."""

    @pytest.mark.asyncio
    async def test_register_new_user(self, async_client: AsyncClient):
        """Test successful user registration."""
        email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"

        response = await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email,
                "password": "SecureTestPass123!",
                "name": "New Test User",
                "tenant_name": "New Test Org",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["success"] is True
        assert "account" in data["data"]
        assert "tenant" in data["data"]
        assert data["data"]["account"]["email"] == email
        assert data["data"]["account"]["name"] == "New Test User"
        assert data["data"]["tenant"]["name"] == "New Test Org"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, async_client: AsyncClient):
        """Test that registering with duplicate email fails."""
        email = f"duplicate_{uuid.uuid4().hex[:8]}@example.com"

        # First registration
        response1 = await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email,
                "password": "SecureTestPass123!",
                "name": "First User",
                "tenant_name": "First Org",
            },
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # Second registration with same email
        response2 = await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email,
                "password": "SecureTestPass456!",
                "name": "Second User",
                "tenant_name": "Second Org",
            },
        )
        assert response2.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, async_client: AsyncClient):
        """Test that registration with invalid email fails."""
        response = await async_client.post(
            "/console/api/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecureTestPass123!",
                "name": "Test User",
                "tenant_name": "Test Org",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_register_short_password(self, async_client: AsyncClient):
        """Test that registration with short password fails."""
        response = await async_client.post(
            "/console/api/auth/register",
            json={
                "email": f"shortpw_{uuid.uuid4().hex[:8]}@example.com",
                "password": "123",  # Too short
                "name": "Test User",
                "tenant_name": "Test Org",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestAuthLogin:
    """Test user login."""

    @pytest.mark.asyncio
    async def test_login_success(self, async_client: AsyncClient, async_db_session: AsyncSession):
        """Test successful login."""
        from src.models import Account, AccountStatus

        email = f"login_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecureTestPass123!"

        # Register first
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email,
                "password": password,
                "name": "Login Test User",
                "tenant_name": "Login Test Org",
            },
        )

        # Activate account
        result = await async_db_session.execute(select(Account).filter_by(email=email))
        account = result.scalar_one()
        account.status = AccountStatus.ACTIVE
        await async_db_session.commit()

        # Login
        response = await async_client.post(
            "/console/api/auth/login",
            json={"email": email, "password": password},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]
        assert data["data"]["account"]["email"] == email

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, async_client: AsyncClient, async_db_session: AsyncSession):
        """Test login with wrong password fails."""
        from src.models import Account, AccountStatus

        email = f"wrongpw_{uuid.uuid4().hex[:8]}@example.com"
        # Password must meet security requirements: 8+ chars, uppercase, lowercase, number, special char
        correct_password = "CorrectTestPass123!"

        # Register first
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email,
                "password": correct_password,
                "name": "Wrong PW Test User",
                "tenant_name": "Test Org",
            },
        )

        # Activate account
        result = await async_db_session.execute(select(Account).filter_by(email=email))
        account = result.scalar_one()
        account.status = AccountStatus.ACTIVE
        await async_db_session.commit()

        # Login with wrong password
        response = await async_client.post(
            "/console/api/auth/login",
            json={"email": email, "password": "WrongTestPass123!"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, async_client: AsyncClient):
        """Test login with nonexistent user fails."""
        response = await async_client.post(
            "/console/api/auth/login",
            json={
                "email": f"nonexistent_{uuid.uuid4().hex[:8]}@example.com",
                "password": "anypassword",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_inactive_account(self, async_client: AsyncClient):
        """Test login with inactive account fails."""
        email = f"inactive_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecureTestPass123!"

        # Register (account starts as PENDING, not activated)
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email,
                "password": password,
                "name": "Inactive Test User",
                "tenant_name": "Test Org",
            },
        )

        # Don't activate - try to login with pending account
        response = await async_client.post(
            "/console/api/auth/login",
            json={"email": email, "password": password},
        )

        # Should fail because account is not active
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


class TestAuthTokenRefresh:
    """Test token refresh."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, async_client: AsyncClient, async_db_session: AsyncSession):
        """Test successful token refresh."""
        from src.models import Account, AccountStatus

        email = f"refresh_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecureTestPass123!"

        # Register and activate
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email,
                "password": password,
                "name": "Refresh Test User",
                "tenant_name": "Test Org",
            },
        )
        result = await async_db_session.execute(select(Account).filter_by(email=email))
        account = result.scalar_one()
        account.status = AccountStatus.ACTIVE
        await async_db_session.commit()

        # Login to get tokens
        login_response = await async_client.post(
            "/console/api/auth/login",
            json={"email": email, "password": password},
        )
        refresh_token = login_response.json()["data"]["refresh_token"]

        # Refresh token
        refresh_response = await async_client.post(
            "/console/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert refresh_response.status_code == status.HTTP_200_OK
        data = refresh_response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, async_client: AsyncClient):
        """Test refresh with invalid token fails."""
        response = await async_client.post(
            "/console/api/auth/refresh",
            json={"refresh_token": "invalid-refresh-token"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_400_BAD_REQUEST]


class TestAuthLogout:
    """Test logout functionality."""

    @pytest.mark.asyncio
    async def test_logout_success(self, async_client: AsyncClient, async_db_session: AsyncSession):
        """Test successful logout."""
        from src.models import Account, AccountStatus

        email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecureTestPass123!"

        # Register and activate
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email,
                "password": password,
                "name": "Logout Test User",
                "tenant_name": "Test Org",
            },
        )
        result = await async_db_session.execute(select(Account).filter_by(email=email))
        account = result.scalar_one()
        account.status = AccountStatus.ACTIVE
        await async_db_session.commit()

        # Login
        login_response = await async_client.post(
            "/console/api/auth/login",
            json={"email": email, "password": password},
        )
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Logout
        logout_response = await async_client.post("/console/api/auth/logout", headers=headers)

        # Logout should succeed (200) or return 204
        assert logout_response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]
