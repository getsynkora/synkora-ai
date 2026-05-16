"""Tests for permissions controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.permissions import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.tenant import AccountRole


@pytest.fixture
def mock_permission_service():
    with patch("src.controllers.permissions.PermissionService") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def client(mock_permission_service, mock_db_session):
    app = FastAPI()
    app.include_router(router)

    # Mock dependencies
    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db

    # Mock current account
    mock_account = MagicMock()
    mock_account.id = uuid.uuid4()
    app.dependency_overrides[get_current_account] = lambda: mock_account

    # Mock tenant ID
    tenant_id = uuid.uuid4()
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    return TestClient(app), tenant_id, mock_account, mock_db_session, mock_permission_service


def _create_mock_permission(perm_id, **kwargs):
    """Helper to create mock permission."""
    mock_perm = MagicMock()
    mock_perm.id = perm_id
    mock_perm.name = kwargs.get("name", "agents.read")
    mock_perm.resource = kwargs.get("resource", "agents")
    mock_perm.action = kwargs.get("action", "read")
    mock_perm.description = kwargs.get("description", "Read agents")
    mock_perm.is_platform_wide = kwargs.get("is_platform_wide", False)
    mock_perm.created_at = datetime.now(UTC).isoformat()
    return mock_perm


class TestListPermissions:
    """Tests for listing permissions."""

    def test_list_permissions_success(self, client):
        """Test listing all permissions."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        mock_perm = _create_mock_permission(1)
        mock_service.return_value.get_all_permissions.return_value = [mock_perm]

        response = test_client.get("/permissions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_list_permissions_filter_by_resource(self, client):
        """Test listing permissions filtered by resource."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        mock_perm = _create_mock_permission(1, name="agents.read")
        mock_service.return_value.get_all_permissions.return_value = [mock_perm]

        response = test_client.get("/permissions?resource=agents")

        assert response.status_code == status.HTTP_200_OK

    def test_list_permissions_platform_wide_filter(self, client):
        """Test listing platform-wide permissions."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        mock_service.return_value.get_all_permissions.return_value = []

        response = test_client.get("/permissions?is_platform_wide=true")

        assert response.status_code == status.HTTP_200_OK

    def test_list_permissions_with_pagination(self, client):
        """Test listing permissions with pagination."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        perms = [_create_mock_permission(i) for i in range(10)]
        mock_service.return_value.get_all_permissions.return_value = perms

        response = test_client.get("/permissions?skip=5&limit=3")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) <= 3


class TestGetRolePermissions:
    """Tests for getting role permissions."""

    def test_get_role_permissions_success(self, client):
        """Test getting permissions for a role."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        # Mock the async service method to return a list directly
        mock_service.return_value.get_role_permissions = AsyncMock(return_value=["agents.read", "agents.write"])

        # Mock db.execute to return a role object
        mock_role = MagicMock()
        mock_role.id = uuid.uuid4()
        mock_role.name = AccountRole.ADMIN.value
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_role
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get(f"/permissions/roles/{AccountRole.ADMIN.value}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["role"] == AccountRole.ADMIN.value
        assert len(data["permissions"]) == 2

    def test_get_role_permissions_invalid_role(self, client):
        """Test getting permissions for invalid role."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        response = test_client.get("/permissions/roles/INVALID_ROLE")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGetUserPermissions:
    """Tests for getting user permissions."""

    def test_get_user_permissions_success(self, client):
        """Test getting permissions for a user."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        user_id = uuid.uuid4()
        mock_service.return_value.get_user_permissions = AsyncMock(return_value=["agents.read"])

        # Mock membership query using async db.execute pattern
        mock_membership = MagicMock()
        mock_membership.role = AccountRole.ADMIN
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_membership
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get(f"/permissions/users/{user_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["account_id"] == str(user_id)


class TestGetMyPermissions:
    """Tests for getting current user's permissions."""

    def test_get_my_permissions_success(self, client):
        """Test getting current user's permissions."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        mock_service.return_value.get_user_permissions = AsyncMock(return_value=["agents.read", "agents.write"])

        # Mock membership query using async db.execute pattern
        mock_membership = MagicMock()
        mock_membership.role = AccountRole.OWNER
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_membership
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/permissions/me")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["account_id"] == str(mock_account.id)
        assert data["role"] == AccountRole.OWNER.value


class TestCheckPermission:
    """Tests for checking permissions."""

    def test_check_permission_granted(self, client):
        """Test checking permission that is granted."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        mock_service.return_value.check_permission.return_value = True

        response = test_client.post("/permissions/check", json={"permission": "agents.read"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["has_permission"] is True

    def test_check_permission_denied(self, client):
        """Test checking permission that is denied."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        mock_service.return_value.check_permission.return_value = False

        response = test_client.post("/permissions/check", json={"permission": "platform.delete"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["has_permission"] is False
        assert data["reason"] == "Permission denied"

    def test_check_permission_invalid_format(self, client):
        """Test checking permission with invalid format."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        response = test_client.post("/permissions/check", json={"permission": "invalid"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestGrantPermission:
    """Tests for granting permissions."""

    def test_grant_permission_success(self, client):
        """Test granting a permission."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        user_id = uuid.uuid4()
        mock_service.return_value.check_permission = AsyncMock(return_value=True)
        mock_service.return_value.grant_permission = AsyncMock(return_value=True)
        mock_service.return_value.get_user_permissions = AsyncMock(return_value=["agents.read", "agents.delete"])

        # Mock membership query using async db.execute pattern
        mock_membership = MagicMock()
        mock_membership.role = AccountRole.NORMAL
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_membership
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.post(f"/permissions/users/{user_id}/grant", json={"permission": "agents.delete"})

        assert response.status_code == status.HTTP_200_OK

    def test_grant_permission_no_permission(self, client):
        """Test granting permission without proper access."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        user_id = uuid.uuid4()
        mock_service.return_value.check_permission.return_value = False

        response = test_client.post(f"/permissions/users/{user_id}/grant", json={"permission": "agents.delete"})

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_grant_permission_user_not_found(self, client):
        """Test granting permission to non-existent user."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        user_id = uuid.uuid4()
        mock_service.return_value.check_permission.return_value = True
        mock_service.return_value.grant_permission.return_value = False

        response = test_client.post(f"/permissions/users/{user_id}/grant", json={"permission": "agents.delete"})

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestRevokePermission:
    """Tests for revoking permissions."""

    def test_revoke_permission_success(self, client):
        """Test revoking a permission."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        user_id = uuid.uuid4()
        mock_service.return_value.check_permission = AsyncMock(return_value=True)
        mock_service.return_value.revoke_permission = AsyncMock(return_value=True)
        mock_service.return_value.get_user_permissions = AsyncMock(return_value=["agents.read"])

        # Mock membership query using async db.execute pattern
        mock_membership = MagicMock()
        mock_membership.role = AccountRole.NORMAL
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_membership
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.post(f"/permissions/users/{user_id}/revoke", json={"permission": "agents.delete"})

        assert response.status_code == status.HTTP_200_OK

    def test_revoke_permission_no_permission(self, client):
        """Test revoking permission without proper access."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        user_id = uuid.uuid4()
        mock_service.return_value.check_permission.return_value = False

        response = test_client.post(f"/permissions/users/{user_id}/revoke", json={"permission": "agents.delete"})

        assert response.status_code == status.HTTP_403_FORBIDDEN
