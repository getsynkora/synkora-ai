"""
Unit tests for Team Service.

Tests team member management, invitations, and role operations.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.team_invitation import InvitationStatus


class TestNormalizeRoleForResponse:
    """Test role normalization helper."""

    def test_normalize_enum_role(self):
        """Test normalizing enum role values."""
        from src.services.team.team_service import _normalize_role_for_response

        # Mock enum with value attribute
        mock_role = MagicMock()
        mock_role.value = "ADMIN"

        result = _normalize_role_for_response(mock_role)
        assert result == "admin"

    def test_normalize_string_role(self):
        """Test normalizing string role values."""
        from src.services.team.team_service import _normalize_role_for_response

        result = _normalize_role_for_response("EDITOR")
        assert result == "editor"

    def test_normalize_normal_to_member(self):
        """Test that NORMAL role maps to member."""
        from src.services.team.team_service import _normalize_role_for_response

        result = _normalize_role_for_response("NORMAL")
        assert result == "member"

    def test_normalize_none_role(self):
        """Test normalizing None role."""
        from src.services.team.team_service import _normalize_role_for_response

        result = _normalize_role_for_response(None)
        assert result == ""


class TestTeamServiceInit:
    """Test TeamService initialization."""

    def test_init_with_db(self):
        """Test service initialization with database session."""
        from src.services.team.team_service import TeamService

        mock_db = AsyncMock(spec=AsyncSession)
        service = TeamService(mock_db)

        assert service.db == mock_db


class TestListTeamMembers:
    """Test listing team members."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    async def test_list_team_members_success(self, team_service, mock_db):
        """Test successful team member listing."""
        tenant_id = uuid.uuid4()
        account_id = uuid.uuid4()

        member = MagicMock()
        member.id = uuid.uuid4()
        member.tenant_id = tenant_id
        member.account_id = account_id
        member.account = MagicMock()
        member.account.name = "Test User"
        member.account.email = "test@example.com"
        member.account.avatar_url = None
        member.role = MagicMock(value="ADMIN")
        member.custom_permissions = None
        member.invited_by = None
        member.joined_at = "2024-01-01T00:00:00"
        member.created_at = datetime(2024, 1, 1)

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [member]
        mock_db.execute.return_value = mock_result

        result = await team_service.list_team_members(tenant_id)

        assert len(result) == 1
        assert result[0]["account_name"] == "Test User"
        assert result[0]["account_email"] == "test@example.com"
        assert result[0]["role"] == "admin"

    async def test_list_team_members_empty(self, team_service, mock_db):
        """Test listing when no members exist."""
        tenant_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await team_service.list_team_members(tenant_id)

        assert result == []

    async def test_list_team_members_pagination(self, team_service, mock_db):
        """Test pagination parameters are passed correctly."""
        tenant_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        await team_service.list_team_members(tenant_id, skip=10, limit=50)

        # Verify execute was called
        mock_db.execute.assert_called_once()


class TestGetTeamMember:
    """Test getting a specific team member."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    async def test_get_team_member_found(self, team_service, mock_db):
        """Test getting existing team member."""
        tenant_id = uuid.uuid4()
        account_id = uuid.uuid4()

        member = MagicMock()
        member.id = uuid.uuid4()
        member.tenant_id = tenant_id
        member.account_id = account_id
        member.account = MagicMock()
        member.account.name = "Test User"
        member.account.email = "test@example.com"
        member.account.avatar_url = None
        member.role = MagicMock(value="EDITOR")
        member.custom_permissions = ["read", "write"]
        member.invited_by = None
        member.joined_at = None
        member.created_at = datetime(2024, 1, 1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = member
        mock_db.execute.return_value = mock_result

        result = await team_service.get_team_member(tenant_id, str(account_id))

        assert result is not None
        assert result["account_name"] == "Test User"
        assert result["role"] == "editor"

    async def test_get_team_member_not_found(self, team_service, mock_db):
        """Test getting non-existent team member."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await team_service.get_team_member(uuid.uuid4(), str(uuid.uuid4()))

        assert result is None


class TestUpdateTeamMember:
    """Test updating team members."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    async def test_update_team_member_role(self, team_service, mock_db):
        """Test updating team member role."""
        tenant_id = uuid.uuid4()
        account_id = uuid.uuid4()

        member = MagicMock()
        member.id = uuid.uuid4()
        member.tenant_id = tenant_id
        member.account_id = account_id
        member.account = MagicMock()
        member.account.name = "Test User"
        member.account.email = "test@example.com"
        member.account.avatar_url = None
        member.role = "NORMAL"
        member.custom_permissions = None
        member.invited_by = None
        member.joined_at = None
        member.created_at = datetime(2024, 1, 1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = member
        mock_db.execute.return_value = mock_result

        team_service._authorize_member_change = AsyncMock()
        await team_service.update_team_member(tenant_id, str(account_id), role="ADMIN", actor_id=uuid.uuid4())

        assert member.role == "ADMIN"
        mock_db.commit.assert_called_once()

    async def test_update_team_member_not_found(self, team_service, mock_db):
        """Test updating non-existent member raises error."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        team_service._authorize_member_change = AsyncMock()
        with pytest.raises(ValueError) as exc_info:
            await team_service.update_team_member(uuid.uuid4(), str(uuid.uuid4()), role="ADMIN", actor_id=uuid.uuid4())

        assert "not found" in str(exc_info.value).lower()


class TestRemoveTeamMember:
    """Test removing team members."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    async def test_remove_team_member_success(self, team_service, mock_db):
        """Test successful member removal."""
        member = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = member
        mock_db.execute.return_value = mock_result

        team_service._authorize_member_change = AsyncMock()
        await team_service.remove_team_member(uuid.uuid4(), str(uuid.uuid4()), actor_id=uuid.uuid4())

        mock_db.delete.assert_called_once_with(member)
        mock_db.commit.assert_called_once()

    async def test_remove_team_member_not_found(self, team_service, mock_db):
        """Test removing non-existent member raises error."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        team_service._authorize_member_change = AsyncMock()
        with pytest.raises(ValueError) as exc_info:
            await team_service.remove_team_member(uuid.uuid4(), str(uuid.uuid4()), actor_id=uuid.uuid4())

        assert "not found" in str(exc_info.value).lower()


class TestCreateInvitation:
    """Test creating team invitations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    @patch("src.tasks.email_tasks.send_team_invitation_email_task")
    async def test_create_invitation_success(self, mock_email_task, team_service, mock_db):
        """Test successful invitation creation."""
        tenant_id = uuid.uuid4()
        inviter_id = uuid.uuid4()

        # Capture the invitation object when it's added
        added_invitation = None

        def capture_add(obj):
            nonlocal added_invitation
            added_invitation = obj
            # Set id and created_at as they would be after commit
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(UTC)

        mock_db.add.side_effect = capture_add

        # Mock no existing membership
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = None

        # Mock no existing invitation
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = None

        # Mock inviter lookup
        inviter = MagicMock()
        inviter.name = "Inviter Name"
        mock_result3 = MagicMock()
        mock_result3.scalar_one_or_none.return_value = inviter

        # Mock tenant lookup
        tenant = MagicMock()
        tenant.name = "Test Tenant"
        mock_result4 = MagicMock()
        mock_result4.scalar_one_or_none.return_value = tenant

        mock_db.execute.side_effect = [mock_result1, mock_result2, mock_result3, mock_result4]

        result = await team_service.create_invitation(
            tenant_id=tenant_id,
            email="newuser@example.com",
            role="member",
            invited_by=str(inviter_id),
        )

        # Verify the invitation was created with correct details
        assert added_invitation is not None
        assert added_invitation.email == "newuser@example.com"
        assert added_invitation.tenant_id == tenant_id
        assert result["email"] == "newuser@example.com"
        assert "token" in result
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()

    async def test_create_invitation_user_already_member(self, team_service, mock_db):
        """Test invitation fails when user is already a member."""
        # Mock existing membership
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError) as exc_info:
            await team_service.create_invitation(
                tenant_id=uuid.uuid4(),
                email="existing@example.com",
                role="member",
                invited_by=str(uuid.uuid4()),
            )

        assert "already a team member" in str(exc_info.value).lower()

    async def test_create_invitation_pending_exists(self, team_service, mock_db):
        """Test invitation fails when pending invitation exists."""
        # Mock no existing membership
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = None

        # Mock existing pending invitation
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = MagicMock()

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        with pytest.raises(ValueError) as exc_info:
            await team_service.create_invitation(
                tenant_id=uuid.uuid4(),
                email="pending@example.com",
                role="member",
                invited_by=str(uuid.uuid4()),
            )

        assert "pending invitation already exists" in str(exc_info.value).lower()


class TestListInvitations:
    """Test listing invitations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    async def test_list_invitations_success(self, team_service, mock_db):
        """Test successful invitation listing."""
        tenant_id = uuid.uuid4()
        inviter_id = uuid.uuid4()

        invitation = MagicMock()
        invitation.id = uuid.uuid4()
        invitation.tenant_id = tenant_id
        invitation.email = "invited@example.com"
        invitation.role = "member"
        invitation.token = "token123"
        invitation.invited_by = inviter_id
        invitation.expires_at = datetime.now(UTC) + timedelta(days=7)
        invitation.accepted_at = None
        invitation.created_at = datetime.now(UTC)
        invitation.updated_at = None

        # Mock invitations query
        mock_result1 = MagicMock()
        mock_result1.scalars.return_value.all.return_value = [invitation]

        # Mock inviters query
        inviter = MagicMock()
        inviter.id = inviter_id
        inviter.name = "Inviter Name"
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [inviter]

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        result = await team_service.list_invitations(tenant_id)

        assert len(result) == 1
        assert result[0]["email"] == "invited@example.com"
        assert result[0]["invited_by_name"] == "Inviter Name"


class TestCancelInvitation:
    """Test canceling invitations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    async def test_cancel_invitation_success(self, team_service, mock_db):
        """Test successful invitation cancellation."""
        invitation = MagicMock()
        invitation.status = InvitationStatus.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = invitation
        mock_db.execute.return_value = mock_result

        await team_service.cancel_invitation(str(uuid.uuid4()), uuid.uuid4())

        assert invitation.status == InvitationStatus.REVOKED
        mock_db.commit.assert_called_once()

    async def test_cancel_invitation_not_found(self, team_service, mock_db):
        """Test canceling non-existent invitation raises error."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError) as exc_info:
            await team_service.cancel_invitation(str(uuid.uuid4()), uuid.uuid4())

        assert "not found" in str(exc_info.value).lower()


class TestAcceptInvitation:
    """Test accepting invitations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    async def test_accept_invitation_success(self, team_service, mock_db):
        """Test successful invitation acceptance."""
        tenant_id = uuid.uuid4()
        account_id = uuid.uuid4()

        invitation = MagicMock()
        invitation.tenant_id = tenant_id
        invitation.email = "user@example.com"
        invitation.role = "member"
        invitation.invited_by = uuid.uuid4()
        invitation.status = InvitationStatus.PENDING

        account = MagicMock()
        account.id = account_id
        account.email = "user@example.com"
        account.name = "Test User"
        account.avatar_url = None

        # Mock invitation lookup
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = invitation

        # Mock account lookup
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = account

        # Mock no existing membership
        mock_result3 = MagicMock()
        mock_result3.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_result1, mock_result2, mock_result3]

        result = await team_service.accept_invitation("token123", str(account_id))

        assert result is not None
        assert result["account_email"] == "user@example.com"
        assert invitation.status == InvitationStatus.ACCEPTED
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()

    async def test_accept_invitation_invalid_token(self, team_service, mock_db):
        """Test accepting with invalid token raises error."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError) as exc_info:
            await team_service.accept_invitation("invalid_token", str(uuid.uuid4()))

        assert "invalid or expired" in str(exc_info.value).lower()

    async def test_accept_invitation_email_mismatch(self, team_service, mock_db):
        """Test accepting with mismatched email raises error."""
        invitation = MagicMock()
        invitation.email = "original@example.com"
        invitation.status = InvitationStatus.PENDING

        account = MagicMock()
        account.email = "different@example.com"

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = invitation

        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = account

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        with pytest.raises(ValueError) as exc_info:
            await team_service.accept_invitation("token", str(uuid.uuid4()))

        assert "different email" in str(exc_info.value).lower()

    async def test_accept_invitation_already_member(self, team_service, mock_db):
        """Test accepting when already a member raises error."""
        invitation = MagicMock()
        invitation.tenant_id = uuid.uuid4()
        invitation.email = "user@example.com"
        invitation.status = InvitationStatus.PENDING

        account = MagicMock()
        account.email = "user@example.com"

        existing_membership = MagicMock()

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = invitation

        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = account

        mock_result3 = MagicMock()
        mock_result3.scalar_one_or_none.return_value = existing_membership

        mock_db.execute.side_effect = [mock_result1, mock_result2, mock_result3]

        with pytest.raises(ValueError) as exc_info:
            await team_service.accept_invitation("token", str(uuid.uuid4()))

        assert "already a member" in str(exc_info.value).lower()


class TestMemberRole:
    """Test member role operations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    async def test_get_member_role_found(self, team_service, mock_db):
        """Test getting member role when exists."""
        membership = MagicMock()
        membership.role = "ADMIN"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = membership
        mock_db.execute.return_value = mock_result

        result = await team_service.get_member_role(uuid.uuid4(), uuid.uuid4())

        assert result == "ADMIN"

    async def test_get_member_role_not_found(self, team_service, mock_db):
        """Test getting role when not a member."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await team_service.get_member_role(uuid.uuid4(), uuid.uuid4())

        assert result is None

    async def test_update_member_role(self, team_service, mock_db):
        """Test updating member role."""
        membership = MagicMock()
        membership.role = "NORMAL"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = membership
        mock_db.execute.return_value = mock_result

        result = await team_service.update_member_role(uuid.uuid4(), uuid.uuid4(), "ADMIN")

        assert membership.role == "ADMIN"
        assert result == membership
        mock_db.commit.assert_called_once()


class TestIsMember:
    """Test membership checking."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    async def test_is_member_true(self, team_service, mock_db):
        """Test is_member returns True when member exists."""
        membership = MagicMock()
        membership.role = "NORMAL"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = membership
        mock_db.execute.return_value = mock_result

        result = await team_service.is_member(uuid.uuid4(), uuid.uuid4())

        assert result is True

    async def test_is_member_false(self, team_service, mock_db):
        """Test is_member returns False when not a member."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await team_service.is_member(uuid.uuid4(), uuid.uuid4())

        assert result is False


class TestGetUserTenants:
    """Test getting user's tenants."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    async def test_get_user_tenants_success(self, team_service, mock_db):
        """Test getting user's tenants."""
        tenant_id = uuid.uuid4()

        membership = MagicMock()
        membership.tenant_id = tenant_id
        membership.tenant = MagicMock()
        membership.tenant.name = "Test Tenant"
        membership.role = MagicMock(value="OWNER")
        membership.joined_at = "2024-01-01"

        mock_result = MagicMock()
        mock_result.scalars.return_value.unique.return_value.all.return_value = [membership]
        mock_db.execute.return_value = mock_result

        result = await team_service.get_user_tenants(uuid.uuid4())

        assert len(result) == 1
        assert result[0]["tenant_id"] == tenant_id
        assert result[0]["tenant_name"] == "Test Tenant"
        assert result[0]["role"] == "owner"


class TestGetInvitationByToken:
    """Test getting invitation by token."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def team_service(self, mock_db):
        """Create team service instance."""
        from src.services.team.team_service import TeamService

        return TeamService(mock_db)

    async def test_get_invitation_by_token_found(self, team_service, mock_db):
        """Test getting invitation when token exists."""
        invitation = MagicMock()
        invitation.token = "valid_token"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = invitation
        mock_db.execute.return_value = mock_result

        result = await team_service.get_invitation_by_token("valid_token")

        assert result == invitation

    async def test_get_invitation_by_token_not_found(self, team_service, mock_db):
        """Test getting invitation when token doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await team_service.get_invitation_by_token("invalid_token")

        assert result is None
