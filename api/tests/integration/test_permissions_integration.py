"""
Integration tests for Permissions endpoints.

Tests permission listing, role permissions, user permissions, and permission checks.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Account, AccountStatus


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, async_db_session: AsyncSession):
    """Create authenticated user and return headers with tenant info."""
    email = f"permissions_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Permissions Test User",
            "tenant_name": "Permissions Test Org",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    tenant_id = data["data"]["tenant"]["id"]

    # Activate account
    result = await async_db_session.execute(select(Account).filter_by(email=email))
    account = result.scalar_one_or_none()
    account.status = AccountStatus.ACTIVE
    await async_db_session.commit()

    # Login
    login_response = await async_client.post(
        "/console/api/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}, tenant_id, account


class TestPermissionsListIntegration:
    """Test Permissions listing operations."""

    @pytest.mark.asyncio
    async def test_list_permissions(self, async_client: AsyncClient, auth_headers):
        """Test listing all permissions."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/permissions", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_permissions_with_pagination(self, async_client: AsyncClient, auth_headers):
        """Test listing permissions with pagination."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/permissions?skip=0&limit=10", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10

    @pytest.mark.asyncio
    async def test_list_permissions_with_resource_filter(self, async_client: AsyncClient, auth_headers):
        """Test listing permissions filtered by resource."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/permissions?resource=agents", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # All returned permissions should be for the specified resource
        for perm in data:
            assert perm["name"].startswith("agents.")

    @pytest.mark.asyncio
    async def test_list_permissions_platform_wide_filter(self, async_client: AsyncClient, auth_headers):
        """Test listing permissions filtered by platform-wide flag."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/permissions?is_platform_wide=true", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)


class TestRolePermissionsIntegration:
    """Test role permissions operations."""

    @pytest.mark.asyncio
    async def test_get_role_permissions_owner(self, async_client: AsyncClient, auth_headers):
        """Test getting permissions for OWNER role."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/permissions/roles/OWNER", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["role"] == "OWNER"
        assert "permissions" in data
        assert isinstance(data["permissions"], list)

    @pytest.mark.asyncio
    async def test_get_role_permissions_admin(self, async_client: AsyncClient, auth_headers):
        """Test getting permissions for ADMIN role."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/permissions/roles/ADMIN", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["role"] == "ADMIN"
        assert "permissions" in data

    @pytest.mark.asyncio
    async def test_get_role_permissions_editor(self, async_client: AsyncClient, auth_headers):
        """Test getting permissions for EDITOR role."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/permissions/roles/EDITOR", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["role"] == "EDITOR"
        assert "permissions" in data

    @pytest.mark.asyncio
    async def test_get_role_permissions_normal(self, async_client: AsyncClient, auth_headers):
        """Test getting permissions for NORMAL role."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/permissions/roles/NORMAL", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["role"] == "NORMAL"
        assert "permissions" in data

    @pytest.mark.asyncio
    async def test_get_role_permissions_invalid_role(self, async_client: AsyncClient, auth_headers):
        """Test getting permissions for invalid role returns 400."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/permissions/roles/INVALID_ROLE", headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestUserPermissionsIntegration:
    """Test user permissions operations."""

    @pytest.mark.asyncio
    async def test_get_my_permissions(self, async_client: AsyncClient, auth_headers):
        """Test getting current user's permissions."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/permissions/me", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "account_id" in data
        assert "role" in data
        assert "role_permissions" in data
        assert "custom_permissions" in data
        assert "effective_permissions" in data
        assert data["account_id"] == str(account.id)

    @pytest.mark.asyncio
    async def test_get_user_permissions(self, async_client: AsyncClient, auth_headers):
        """Test getting another user's permissions."""
        headers, tenant_id, account = auth_headers

        # Get permissions for the current user by ID
        response = await async_client.get(f"/api/v1/permissions/users/{account.id}", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "account_id" in data
        assert "role" in data
        assert "role_permissions" in data
        assert "effective_permissions" in data


class TestCheckPermissionIntegration:
    """Test permission checking operations."""

    @pytest.mark.asyncio
    async def test_check_permission_valid_format(self, async_client: AsyncClient, auth_headers):
        """Test checking a permission with valid format."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/permissions/check",
            json={"permission": "agents.read"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "has_permission" in data
        assert isinstance(data["has_permission"], bool)

    @pytest.mark.asyncio
    async def test_check_permission_another_resource(self, async_client: AsyncClient, auth_headers):
        """Test checking permission for another resource."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/permissions/check",
            json={"permission": "team.manage"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "has_permission" in data

    @pytest.mark.asyncio
    async def test_check_permission_invalid_format(self, async_client: AsyncClient, auth_headers):
        """Test checking permission with invalid format fails validation."""
        headers, tenant_id, account = auth_headers

        # Missing the dot separator
        response = await async_client.post(
            "/api/v1/permissions/check",
            json={"permission": "invalid"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_check_permission_missing_permission(self, async_client: AsyncClient, auth_headers):
        """Test checking permission without permission field fails."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/permissions/check",
            json={},
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestGrantRevokePermissionsIntegration:
    """Test granting and revoking permissions."""

    @pytest.mark.asyncio
    async def test_grant_permission(self, async_client: AsyncClient, auth_headers):
        """Test granting a permission to a user."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            f"/api/v1/permissions/users/{account.id}/grant",
            json={"permission": "agents.delete"},
            headers=headers,
        )

        # May succeed (200) or fail due to insufficient permissions (403)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "account_id" in data
            assert "effective_permissions" in data

    @pytest.mark.asyncio
    async def test_grant_permission_invalid_format(self, async_client: AsyncClient, auth_headers):
        """Test granting permission with invalid format fails validation."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            f"/api/v1/permissions/users/{account.id}/grant",
            json={"permission": "invalid_permission"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_revoke_permission(self, async_client: AsyncClient, auth_headers):
        """Test revoking a permission from a user."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            f"/api/v1/permissions/users/{account.id}/revoke",
            json={"permission": "agents.delete"},
            headers=headers,
        )

        # May succeed (200) or fail due to insufficient permissions (403)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "account_id" in data
            assert "effective_permissions" in data

    @pytest.mark.asyncio
    async def test_revoke_permission_invalid_format(self, async_client: AsyncClient, auth_headers):
        """Test revoking permission with invalid format fails validation."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            f"/api/v1/permissions/users/{account.id}/revoke",
            json={"permission": "invalid_permission"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestPermissionsAuthorization:
    """Test Permissions authorization."""

    @pytest.mark.asyncio
    async def test_list_permissions_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to list are rejected."""
        response = await async_client.get("/api/v1/permissions")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_get_my_permissions_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to get my permissions are rejected."""
        response = await async_client.get("/api/v1/permissions/me")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_get_role_permissions_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to get role permissions are rejected."""
        response = await async_client.get("/api/v1/permissions/roles/OWNER")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_check_permission_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to check permission are rejected."""
        response = await async_client.post(
            "/api/v1/permissions/check",
            json={"permission": "agents.read"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_grant_permission_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to grant permission are rejected."""
        response = await async_client.post(
            f"/api/v1/permissions/users/{uuid.uuid4()}/grant",
            json={"permission": "agents.read"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_revoke_permission_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to revoke permission are rejected."""
        response = await async_client.post(
            f"/api/v1/permissions/users/{uuid.uuid4()}/revoke",
            json={"permission": "agents.read"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
