"""Team management service."""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...models import Account, TeamInvitation, Tenant, TenantAccountJoin
from ...models.team_invitation import InvitationStatus

logger = logging.getLogger(__name__)


def _normalize_role_for_response(role) -> str:
    """Convert database role to frontend-compatible lowercase format."""
    if role is None:
        return ""
    # Handle enum values (AccountRole) and plain strings
    role_str = role.value if hasattr(role, "value") else str(role)
    role_upper = role_str.upper()
    # Map NORMAL -> member for frontend compatibility
    if role_upper == "NORMAL":
        return "member"
    return role_upper.lower()


class TeamService:
    """Service for managing team members and invitations."""

    def __init__(self, db: AsyncSession):
        """Initialize the team service.

        Args:
            db: Async database session
        """
        self.db = db

    async def list_team_members(self, tenant_id: UUID, skip: int = 0, limit: int = 100) -> list[dict]:
        """List all team members for a tenant.

        Args:
            tenant_id: Tenant ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of team member dictionaries
        """
        stmt = (
            select(TenantAccountJoin)
            .where(TenantAccountJoin.tenant_id == tenant_id)
            .options(selectinload(TenantAccountJoin.account))
            .offset(skip)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        members = result.scalars().unique().all()

        return [
            {
                "id": str(m.id) if hasattr(m, "id") else f"{m.tenant_id}_{m.account_id}",
                "account_id": str(m.account_id),
                "account_name": m.account.name if m.account else "Unknown",
                "account_email": m.account.email if m.account else "",
                "account_avatar_url": m.account.avatar_url if m.account else None,
                "role": _normalize_role_for_response(m.role),
                "custom_permissions": m.custom_permissions,
                "invited_by": str(m.invited_by) if m.invited_by else None,
                "joined_at": m.joined_at if m.joined_at else "",
                "created_at": m.created_at.isoformat() if hasattr(m, "created_at") and m.created_at else "",
            }
            for m in members
        ]

    async def get_team_member(self, tenant_id: UUID, account_id: str) -> dict | None:
        """Get a specific team member.

        Args:
            tenant_id: Tenant ID
            account_id: Account ID

        Returns:
            Team member dictionary or None
        """
        stmt = (
            select(TenantAccountJoin)
            .where(and_(TenantAccountJoin.tenant_id == tenant_id, TenantAccountJoin.account_id == UUID(account_id)))
            .options(selectinload(TenantAccountJoin.account))
        )

        result = await self.db.execute(stmt)
        m = result.scalar_one_or_none()

        if not m:
            return None

        return {
            "id": str(m.id) if hasattr(m, "id") else f"{m.tenant_id}_{m.account_id}",
            "account_id": str(m.account_id),
            "account_name": m.account.name if m.account else "Unknown",
            "account_email": m.account.email if m.account else "",
            "account_avatar_url": m.account.avatar_url if m.account else None,
            "role": _normalize_role_for_response(m.role),
            "custom_permissions": m.custom_permissions,
            "invited_by": str(m.invited_by) if m.invited_by else None,
            "joined_at": m.joined_at if m.joined_at else "",
            "created_at": m.created_at.isoformat() if hasattr(m, "created_at") and m.created_at else "",
        }

    async def _authorize_member_change(
        self, tenant_id: UUID, account_id: str, actor_id: UUID, *, new_role: str | None = None, removing: bool = False
    ) -> None:
        # Serialize membership changes per tenant, including concurrent last-owner changes.
        await self.db.execute(select(Tenant.id).where(Tenant.id == tenant_id).with_for_update())
        result = await self.db.execute(
            select(TenantAccountJoin)
            .where(TenantAccountJoin.tenant_id == tenant_id)
            .execution_options(populate_existing=True)
        )
        members = list(result.scalars().all())
        actor = next((m for m in members if m.account_id == actor_id), None)
        target = next((m for m in members if m.account_id == UUID(account_id)), None)
        actor_role = _normalize_role_for_response(actor.role) if actor else ""
        if actor_role not in {"owner", "admin"}:
            raise PermissionError("Insufficient permissions to manage team members")
        if target is None:
            raise ValueError("Team member not found")
        target_role = _normalize_role_for_response(target.role)
        requested_role = _normalize_role_for_response(new_role) if new_role is not None else target_role
        if new_role is not None and requested_role not in {"owner", "admin", "editor", "member"}:
            raise ValueError("Invalid role")
        if (target_role == "owner" or requested_role == "owner") and actor_role != "owner":
            raise PermissionError("Only organization owners can manage owners")
        if removing and target.account_id == actor_id:
            raise ValueError("Cannot remove yourself from the team")
        if target_role == "owner" and (removing or requested_role != "owner"):
            if sum(_normalize_role_for_response(m.role) == "owner" for m in members) <= 1:
                raise ValueError("Cannot remove or demote the last owner")

    async def update_team_member(
        self,
        tenant_id: UUID,
        account_id: str,
        role: str | None = None,
        custom_permissions: list[str] | None = None,
        *,
        actor_id: UUID,
    ) -> dict:
        """Update a team member.

        Args:
            tenant_id: Tenant ID
            account_id: Account ID
            role: New role (optional)
            custom_permissions: New custom permissions (optional)

        Returns:
            Updated team member dictionary
        """
        await self._authorize_member_change(tenant_id, account_id, actor_id, new_role=role)
        stmt = (
            select(TenantAccountJoin)
            .where(and_(TenantAccountJoin.tenant_id == tenant_id, TenantAccountJoin.account_id == UUID(account_id)))
            .options(selectinload(TenantAccountJoin.account))
        )

        result = await self.db.execute(stmt)
        member = result.scalar_one_or_none()

        if not member:
            raise ValueError("Team member not found")

        if role is not None:
            member.role = role
        if custom_permissions is not None:
            member.custom_permissions = custom_permissions

        await self.db.commit()
        await self.db.refresh(member)

        return {
            "id": str(member.id) if hasattr(member, "id") else f"{member.tenant_id}_{member.account_id}",
            "account_id": str(member.account_id),
            "account_name": member.account.name if member.account else "Unknown",
            "account_email": member.account.email if member.account else "",
            "account_avatar_url": member.account.avatar_url if member.account else None,
            "role": _normalize_role_for_response(member.role),
            "custom_permissions": member.custom_permissions,
            "invited_by": str(member.invited_by) if member.invited_by else None,
            "joined_at": member.joined_at if member.joined_at else "",
            "created_at": member.created_at.isoformat() if hasattr(member, "created_at") and member.created_at else "",
        }

    async def remove_team_member(self, tenant_id: UUID, account_id: str, *, actor_id: UUID) -> None:
        """Remove a team member.

        Args:
            tenant_id: Tenant ID
            account_id: Account ID
        """
        await self._authorize_member_change(tenant_id, account_id, actor_id, removing=True)
        stmt = select(TenantAccountJoin).where(
            and_(TenantAccountJoin.tenant_id == tenant_id, TenantAccountJoin.account_id == UUID(account_id))
        )

        result = await self.db.execute(stmt)
        member = result.scalar_one_or_none()

        if not member:
            raise ValueError("Team member not found")

        await self.db.delete(member)
        await self.db.commit()

    async def get_pending_invitations(self, tenant_id: UUID) -> list[TeamInvitation]:
        """Get pending invitations for a tenant.

        Args:
            tenant_id: Tenant ID

        Returns:
            List of pending invitations
        """
        stmt = select(TeamInvitation).where(
            and_(
                TeamInvitation.tenant_id == tenant_id,
                TeamInvitation.status == InvitationStatus.PENDING,
                TeamInvitation.expires_at > datetime.now(UTC),
            )
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_invitation(
        self,
        tenant_id: UUID,
        email: str,
        role: str,
        invited_by: str,
        custom_permissions: list[str] | None = None,
        expires_in_days: int = 7,
    ) -> dict:
        """Create a team invitation.

        Args:
            tenant_id: Tenant ID
            email: Email address to invite
            role: Role to assign (owner, admin, editor, member)
            invited_by: Account ID of inviter
            custom_permissions: Custom permissions (optional)
            expires_in_days: Days until invitation expires

        Returns:
            Created invitation dictionary
        """
        # Check if user is already a member
        stmt = (
            select(TenantAccountJoin)
            .join(Account, TenantAccountJoin.account_id == Account.id)
            .where(and_(TenantAccountJoin.tenant_id == tenant_id, Account.email == email))
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("User is already a team member")

        # Check for existing pending invitation
        stmt = select(TeamInvitation).where(
            and_(
                TeamInvitation.tenant_id == tenant_id,
                TeamInvitation.email == email,
                TeamInvitation.status == InvitationStatus.PENDING,
                TeamInvitation.expires_at > datetime.now(UTC),
            )
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("Pending invitation already exists for this email")

        # Generate secure token
        token = secrets.token_urlsafe(32)

        # Create invitation
        invitation = TeamInvitation(
            tenant_id=tenant_id,
            email=email,
            role=role,
            token=token,
            invited_by=UUID(invited_by),
            expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
            status=InvitationStatus.PENDING,
        )

        self.db.add(invitation)
        await self.db.commit()
        await self.db.refresh(invitation)

        # Get inviter name and tenant name
        stmt = select(Account).where(Account.id == UUID(invited_by))
        result = await self.db.execute(stmt)
        inviter = result.scalar_one_or_none()

        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await self.db.execute(stmt)
        result.scalar_one_or_none()

        # Send invitation email via Celery task (async)
        try:
            from src.tasks.email_tasks import send_team_invitation_email_task
            from src.utils.config_helper import get_app_base_url

            base_url = await get_app_base_url(self.db)
            send_team_invitation_email_task.delay(
                tenant_id=str(tenant_id),
                to_email=email,
                inviter_name=inviter.name if inviter else "A team member",
                invitation_token=token,
                base_url=base_url,
            )
            logger.info(f"Queued invitation email task for {email}")
        except Exception as e:
            logger.error(f"Error queuing invitation email to {email}: {str(e)}")
            # Don't fail the invitation creation if email queuing fails

        return {
            "id": str(invitation.id),
            "tenant_id": str(invitation.tenant_id),
            "email": invitation.email,
            "role": _normalize_role_for_response(invitation.role),
            "custom_permissions": custom_permissions,
            "token": invitation.token,
            "invited_by": invited_by,
            "invited_by_name": inviter.name if inviter else "Unknown",
            "expires_at": invitation.expires_at.isoformat(),
            "accepted_at": invitation.accepted_at.isoformat() if invitation.accepted_at else None,
            "created_at": invitation.created_at.isoformat(),
            "updated_at": invitation.updated_at.isoformat()
            if invitation.updated_at
            else invitation.created_at.isoformat(),
        }

    async def list_invitations(self, tenant_id: UUID, skip: int = 0, limit: int = 100) -> list[dict]:
        """List pending invitations.

        Args:
            tenant_id: Tenant ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of invitation dictionaries
        """
        stmt = (
            select(TeamInvitation)
            .where(and_(TeamInvitation.tenant_id == tenant_id, TeamInvitation.status == InvitationStatus.PENDING))
            .offset(skip)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        invitations = result.scalars().all()

        # Get inviter names
        inviter_ids = [inv.invited_by for inv in invitations if inv.invited_by]
        inviters = {}
        if inviter_ids:
            stmt = select(Account).where(Account.id.in_(inviter_ids))
            result = await self.db.execute(stmt)
            inviters = {acc.id: acc.name for acc in result.scalars().all()}

        return [
            {
                "id": str(inv.id),
                "tenant_id": str(inv.tenant_id),
                "email": inv.email,
                "role": _normalize_role_for_response(inv.role),
                "custom_permissions": None,
                "token": inv.token,
                "invited_by": str(inv.invited_by) if inv.invited_by else None,
                "invited_by_name": inviters.get(inv.invited_by, "Unknown"),
                "expires_at": inv.expires_at.isoformat(),
                "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
                "created_at": inv.created_at.isoformat(),
                "updated_at": inv.updated_at.isoformat() if inv.updated_at else inv.created_at.isoformat(),
            }
            for inv in invitations
        ]

    async def cancel_invitation(self, invitation_id: str, tenant_id: UUID) -> None:
        """Cancel a pending invitation.

        Args:
            invitation_id: Invitation ID
            tenant_id: Tenant ID
        """
        stmt = select(TeamInvitation).where(
            and_(TeamInvitation.id == UUID(invitation_id), TeamInvitation.tenant_id == tenant_id)
        )
        result = await self.db.execute(stmt)
        invitation = result.scalar_one_or_none()

        if not invitation:
            raise ValueError("Invitation not found")

        invitation.status = InvitationStatus.REVOKED
        await self.db.commit()

    async def resend_invitation(self, invitation_id: str, tenant_id: UUID) -> dict:
        """Resend a team invitation.

        Args:
            invitation_id: Invitation ID
            tenant_id: Tenant ID

        Returns:
            Updated invitation dictionary
        """
        stmt = select(TeamInvitation).where(
            and_(TeamInvitation.id == UUID(invitation_id), TeamInvitation.tenant_id == tenant_id)
        )
        result = await self.db.execute(stmt)
        invitation = result.scalar_one_or_none()

        if not invitation:
            raise ValueError("Invitation not found")

        # Extend expiration
        invitation.expires_at = datetime.now(UTC) + timedelta(days=7)
        await self.db.commit()
        await self.db.refresh(invitation)

        # Get inviter name and tenant name
        stmt = select(Account).where(Account.id == invitation.invited_by)
        result = await self.db.execute(stmt)
        inviter = result.scalar_one_or_none()

        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await self.db.execute(stmt)
        result.scalar_one_or_none()

        # Send invitation email via Celery task (async)
        try:
            from src.tasks.email_tasks import send_team_invitation_email_task
            from src.utils.config_helper import get_app_base_url

            base_url = await get_app_base_url(self.db)
            send_team_invitation_email_task.delay(
                tenant_id=str(tenant_id),
                to_email=invitation.email,
                inviter_name=inviter.name if inviter else "A team member",
                invitation_token=invitation.token,
                base_url=base_url,
            )
            logger.info(f"Queued resend invitation email task for {invitation.email}")
        except Exception as e:
            logger.error(f"Error queuing resend invitation email to {invitation.email}: {str(e)}")

        return {
            "id": str(invitation.id),
            "tenant_id": str(invitation.tenant_id),
            "email": invitation.email,
            "role": _normalize_role_for_response(invitation.role),
            "custom_permissions": None,
            "token": invitation.token,
            "invited_by": str(invitation.invited_by) if invitation.invited_by else None,
            "invited_by_name": inviter.name if inviter else "Unknown",
            "expires_at": invitation.expires_at.isoformat(),
            "accepted_at": invitation.accepted_at.isoformat() if invitation.accepted_at else None,
            "created_at": invitation.created_at.isoformat(),
            "updated_at": invitation.updated_at.isoformat()
            if invitation.updated_at
            else invitation.created_at.isoformat(),
        }

    async def accept_invitation(self, token: str, account_id: str) -> dict | None:
        """Accept a team invitation.

        Args:
            token: Invitation token
            account_id: Account ID accepting the invitation

        Returns:
            Created team membership dict or None if invalid
        """
        # Find invitation
        stmt = select(TeamInvitation).where(
            and_(
                TeamInvitation.token == token,
                TeamInvitation.status == InvitationStatus.PENDING,
                TeamInvitation.expires_at > datetime.now(UTC),
            )
        )
        result = await self.db.execute(stmt)
        invitation = result.scalar_one_or_none()

        if not invitation:
            raise ValueError("Invalid or expired invitation token")

        # Verify email matches
        account_uuid = UUID(account_id)
        stmt = select(Account).where(Account.id == account_uuid)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account or account.email != invitation.email:
            raise ValueError("This invitation was sent to a different email address")

        # Check if already a member
        stmt = select(TenantAccountJoin).where(
            and_(TenantAccountJoin.tenant_id == invitation.tenant_id, TenantAccountJoin.account_id == account_uuid)
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("You are already a member of this team")

        # Create team membership
        joined_at = datetime.now(UTC)
        membership = TenantAccountJoin(
            tenant_id=invitation.tenant_id,
            account_id=account_uuid,
            role=invitation.role,
            invited_by=invitation.invited_by,
            joined_at=joined_at.isoformat(),
        )

        self.db.add(membership)

        # Update invitation status
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(membership)

        return {
            "id": str(membership.id)
            if hasattr(membership, "id")
            else f"{membership.tenant_id}_{membership.account_id}",
            "account_id": str(membership.account_id),
            "account_name": account.name,
            "account_email": account.email,
            "account_avatar_url": account.avatar_url,
            "role": _normalize_role_for_response(membership.role),
            "custom_permissions": membership.custom_permissions,
            "invited_by": str(membership.invited_by) if membership.invited_by else None,
            "joined_at": joined_at.isoformat() if joined_at else "",
            "created_at": membership.created_at.isoformat()
            if hasattr(membership, "created_at") and membership.created_at
            else "",
        }

    async def revoke_invitation(self, invitation_id: UUID, tenant_id: UUID | None = None) -> bool:
        """Revoke a pending invitation.

        Args:
            invitation_id: Invitation ID
            tenant_id: Tenant ID for access control (required for cross-tenant safety)

        Returns:
            True if revoked, False if not found
        """
        filters = [TeamInvitation.id == invitation_id]
        if tenant_id is not None:
            filters.append(TeamInvitation.tenant_id == tenant_id)
        stmt = select(TeamInvitation).where(*filters)
        result = await self.db.execute(stmt)
        invitation = result.scalar_one_or_none()

        if not invitation:
            return False

        invitation.status = InvitationStatus.REVOKED
        await self.db.commit()

        return True

    async def update_member_role(self, tenant_id: UUID, account_id: UUID, new_role: str) -> TenantAccountJoin | None:
        """Update a team member's role.

        Args:
            tenant_id: Tenant ID
            account_id: Account ID
            new_role: New role to assign

        Returns:
            Updated membership or None if not found
        """
        stmt = select(TenantAccountJoin).where(
            and_(TenantAccountJoin.tenant_id == tenant_id, TenantAccountJoin.account_id == account_id)
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if not membership:
            return None

        membership.role = new_role
        await self.db.commit()
        await self.db.refresh(membership)

        return membership

    async def remove_member(self, tenant_id: UUID, account_id: UUID) -> bool:
        """Remove a team member.

        Args:
            tenant_id: Tenant ID
            account_id: Account ID to remove

        Returns:
            True if removed, False if not found
        """
        stmt = select(TenantAccountJoin).where(
            and_(TenantAccountJoin.tenant_id == tenant_id, TenantAccountJoin.account_id == account_id)
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if not membership:
            return False

        await self.db.delete(membership)
        await self.db.commit()

        return True

    async def get_member_role(self, tenant_id: UUID, account_id: UUID) -> str | None:
        """Get a member's role in a tenant.

        Args:
            tenant_id: Tenant ID
            account_id: Account ID

        Returns:
            Role string or None if not a member
        """
        stmt = select(TenantAccountJoin).where(
            and_(TenantAccountJoin.tenant_id == tenant_id, TenantAccountJoin.account_id == account_id)
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        return membership.role if membership else None

    async def is_member(self, tenant_id: UUID, account_id: UUID) -> bool:
        """Check if an account is a member of a tenant.

        Args:
            tenant_id: Tenant ID
            account_id: Account ID

        Returns:
            True if member, False otherwise
        """
        role = await self.get_member_role(tenant_id, account_id)
        return role is not None

    async def get_user_tenants(self, account_id: UUID) -> list[dict]:
        """Get all tenants a user is a member of.

        Args:
            account_id: Account ID

        Returns:
            List of tenant info with roles
        """
        stmt = (
            select(TenantAccountJoin)
            .where(TenantAccountJoin.account_id == account_id)
            .options(selectinload(TenantAccountJoin.tenant))
        )

        result = await self.db.execute(stmt)
        memberships = result.scalars().unique().all()

        return [
            {
                "tenant_id": m.tenant_id,
                "tenant_name": m.tenant.name if m.tenant else None,
                "role": _normalize_role_for_response(m.role),
                "joined_at": m.joined_at,
            }
            for m in memberships
        ]

    async def update_custom_permissions(
        self, tenant_id: UUID, account_id: UUID, permissions: list[str]
    ) -> TenantAccountJoin | None:
        """Update custom permissions for a team member.

        Args:
            tenant_id: Tenant ID
            account_id: Account ID
            permissions: List of permission strings

        Returns:
            Updated membership or None if not found
        """
        stmt = select(TenantAccountJoin).where(
            and_(TenantAccountJoin.tenant_id == tenant_id, TenantAccountJoin.account_id == account_id)
        )
        result = await self.db.execute(stmt)
        membership = result.scalar_one_or_none()

        if not membership:
            return None

        membership.custom_permissions = permissions
        await self.db.commit()
        await self.db.refresh(membership)

        return membership

    async def get_invitation_by_token(self, token: str) -> TeamInvitation | None:
        """Get invitation by token.

        Args:
            token: Invitation token

        Returns:
            Invitation or None if not found
        """
        stmt = select(TeamInvitation).where(TeamInvitation.token == token)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
