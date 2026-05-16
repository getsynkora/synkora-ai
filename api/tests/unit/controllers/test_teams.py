"""Tests for teams controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.teams import router
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
    app.include_router(router)

    tenant_id = uuid.uuid4()

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[get_current_account] = lambda: mock_account

    with patch("src.controllers.teams.TeamService") as mock_team_service:
        mock_team_service.return_value = AsyncMock()
        yield TestClient(app), tenant_id, mock_account, mock_db_session, mock_team_service


def _create_mock_team_member(account_id, role="member"):
    """Helper to create a mock team member as dict (matching TeamService response)."""
    # Controller expects dict-like access: current_member["role"]
    return {
        "id": str(uuid.uuid4()),
        "account_id": str(account_id),
        "account_name": "Test Member",
        "account_email": "member@example.com",
        "account_avatar_url": None,
        "role": role,
        "custom_permissions": None,
        "invited_by": None,
        "joined_at": datetime.now(UTC).isoformat(),
        "created_at": datetime.now(UTC).isoformat(),
    }


class TestListTeamMembers:
    """Tests for listing team members."""

    def test_list_team_members_success(self, client):
        """Test successfully listing team members."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        mock_member = _create_mock_team_member(uuid.uuid4())
        mock_team.list_team_members.return_value = [mock_member]

        response = test_client.get("/teams/members")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_list_team_members_with_pagination(self, client):
        """Test listing team members with pagination."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        mock_team.list_team_members.return_value = []

        response = test_client.get("/teams/members?skip=10&limit=5")

        assert response.status_code == status.HTTP_200_OK
        mock_team.list_team_members.assert_called_once_with(tenant_id=tenant_id, skip=10, limit=5)


class TestGetTeamMember:
    """Tests for getting a specific team member."""

    def test_get_team_member_success(self, client):
        """Test successfully getting a team member."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        account_id = str(uuid.uuid4())
        mock_member = _create_mock_team_member(account_id)
        mock_team.get_team_member.return_value = mock_member

        response = test_client.get(f"/teams/members/{account_id}")

        assert response.status_code == status.HTTP_200_OK

    def test_get_team_member_not_found(self, client):
        """Test getting non-existent team member."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        mock_team.get_team_member.return_value = None

        response = test_client.get(f"/teams/members/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateTeamMember:
    """Tests for updating team members."""

    def test_update_team_member_success(self, client):
        """Test successfully updating a team member."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        account_id = str(uuid.uuid4())
        # Use lowercase "owner" to match controller's permission check
        current_member = _create_mock_team_member(mock_account.id, role="owner")
        mock_member = _create_mock_team_member(account_id, role="admin")

        mock_team.get_team_member.side_effect = [current_member, mock_member]
        mock_team.update_team_member.return_value = mock_member

        response = test_client.put(f"/teams/members/{account_id}", json={"role": "admin"})

        assert response.status_code == status.HTTP_200_OK

    def test_update_team_member_forbidden(self, client):
        """Test updating team member without permission."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        # Current user is a regular member (not owner/admin)
        current_member = _create_mock_team_member(mock_account.id, role="member")
        mock_team.get_team_member.return_value = current_member

        response = test_client.put(f"/teams/members/{uuid.uuid4()}", json={"role": "admin"})

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestRemoveTeamMember:
    """Tests for removing team members."""

    def test_remove_team_member_success(self, client):
        """Test successfully removing a team member."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        other_account_id = str(uuid.uuid4())
        current_member = _create_mock_team_member(mock_account.id, role="owner")
        mock_team.get_team_member.return_value = current_member

        response = test_client.delete(f"/teams/members/{other_account_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_remove_self_not_allowed(self, client):
        """Test that removing yourself is not allowed."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        current_member = _create_mock_team_member(mock_account.id, role="owner")
        mock_team.get_team_member.return_value = current_member

        response = test_client.delete(f"/teams/members/{mock_account.id}")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_remove_team_member_forbidden(self, client):
        """Test removing team member without permission."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        current_member = _create_mock_team_member(mock_account.id, role="member")
        mock_team.get_team_member.return_value = current_member

        response = test_client.delete(f"/teams/members/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCreateInvitation:
    """Tests for creating team invitations."""

    def test_create_invitation_success(self, client):
        """Test successfully creating an invitation."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        current_member = _create_mock_team_member(mock_account.id, role="owner")
        mock_team.get_team_member.return_value = current_member

        mock_invitation = MagicMock()
        mock_invitation.id = "1"  # Must be string for response model
        mock_invitation.tenant_id = str(tenant_id)
        mock_invitation.email = "invite@example.com"
        mock_invitation.role = "member"
        mock_invitation.custom_permissions = None
        mock_invitation.token = "a" * 32
        mock_invitation.invited_by = str(mock_account.id)
        mock_invitation.invited_by_name = "Test User"
        mock_invitation.expires_at = datetime.now(UTC).isoformat()
        mock_invitation.accepted_at = None
        mock_invitation.created_at = datetime.now(UTC).isoformat()
        mock_invitation.updated_at = datetime.now(UTC).isoformat()  # Required by response model

        mock_team.create_invitation.return_value = mock_invitation

        with (
            patch("src.services.billing.PlanRestrictionService") as mock_restriction,
            patch("src.services.billing.PlanRestrictionError", Exception),
        ):
            mock_restriction.return_value.enforce_team_member_limit = AsyncMock(return_value=None)

            response = test_client.post("/teams/invitations", json={"email": "invite@example.com", "role": "member"})

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_invitation_invalid_email(self, client):
        """Test creating invitation with invalid email."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        response = test_client.post("/teams/invitations", json={"email": "invalid-email", "role": "member"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_create_invitation_invalid_role(self, client):
        """Test creating invitation with invalid role."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client

        response = test_client.post("/teams/invitations", json={"email": "invite@example.com", "role": "superadmin"})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestListInvitations:
    """Tests for listing invitations."""

    def test_list_invitations_success(self, client):
        """Test successfully listing invitations."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        current_member = _create_mock_team_member(mock_account.id, role="admin")
        mock_team.get_team_member.return_value = current_member
        mock_team.list_invitations.return_value = []

        response = test_client.get("/teams/invitations")

        assert response.status_code == status.HTTP_200_OK

    def test_list_invitations_forbidden(self, client):
        """Test listing invitations without permission."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        current_member = _create_mock_team_member(mock_account.id, role="member")
        mock_team.get_team_member.return_value = current_member

        response = test_client.get("/teams/invitations")

        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCancelInvitation:
    """Tests for canceling invitations."""

    def test_cancel_invitation_success(self, client):
        """Test successfully canceling an invitation."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        current_member = _create_mock_team_member(mock_account.id, role="owner")
        mock_team.get_team_member.return_value = current_member

        response = test_client.delete("/teams/invitations/1")

        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestAcceptInvitation:
    """Tests for accepting invitations."""

    def test_accept_invitation_success(self, client):
        """Test successfully accepting an invitation."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        mock_member = _create_mock_team_member(mock_account.id)
        mock_team.accept_invitation.return_value = mock_member

        response = test_client.post("/teams/invitations/accept", json={"token": "a" * 32})

        assert response.status_code == status.HTTP_200_OK

    def test_accept_invitation_invalid_token(self, client):
        """Test accepting invitation with invalid token."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        mock_team.accept_invitation.side_effect = ValueError("Invalid or expired token")

        response = test_client.post("/teams/invitations/accept", json={"token": "a" * 32})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestResendInvitation:
    """Tests for resending invitations."""

    def test_resend_invitation_success(self, client):
        """Test successfully resending an invitation."""
        test_client, tenant_id, mock_account, mock_db, mock_service = client
        mock_team = mock_service.return_value

        current_member = _create_mock_team_member(mock_account.id, role="owner")
        mock_team.get_team_member.return_value = current_member

        mock_invitation = MagicMock()
        mock_invitation.id = "1"  # Must be string for response model
        mock_invitation.tenant_id = str(tenant_id)
        mock_invitation.email = "invite@example.com"
        mock_invitation.role = "member"
        mock_invitation.custom_permissions = None
        mock_invitation.token = "b" * 32
        mock_invitation.invited_by = str(mock_account.id)
        mock_invitation.invited_by_name = "Test User"
        mock_invitation.expires_at = datetime.now(UTC).isoformat()
        mock_invitation.accepted_at = None
        mock_invitation.created_at = datetime.now(UTC).isoformat()
        mock_invitation.updated_at = datetime.now(UTC).isoformat()  # Required by response model

        mock_team.resend_invitation.return_value = mock_invitation

        response = test_client.post("/teams/invitations/1/resend")

        assert response.status_code == status.HTTP_200_OK
