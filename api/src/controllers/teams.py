"""
Team management controller
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models import Tenant
from src.services.team.team_service import TeamService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teams", tags=["teams"])


# Pydantic models for request/response
class TeamMemberResponse(BaseModel):
    id: str
    account_id: str
    account_name: str
    account_email: str
    account_avatar_url: str | None
    role: str
    custom_permissions: list[str] | None
    invited_by: str | None
    joined_at: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class TeamInvitationCreate(BaseModel):
    email: str = Field(..., pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    role: str = Field(..., pattern="^(owner|admin|editor|member|OWNER|ADMIN|EDITOR|NORMAL)$")
    custom_permissions: list[str] | None = None

    def get_normalized_role(self) -> str:
        """Convert role to uppercase and handle member->NORMAL mapping."""
        role_upper = self.role.upper()
        return "NORMAL" if role_upper == "MEMBER" else role_upper


class TeamInvitationResponse(BaseModel):
    id: str
    tenant_id: str
    email: str
    role: str
    custom_permissions: list[str] | None
    token: str
    invited_by: str | None
    invited_by_name: str
    expires_at: str
    accepted_at: str | None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class TeamMemberUpdate(BaseModel):
    role: str | None = Field(None, pattern="^(owner|admin|editor|member|OWNER|ADMIN|EDITOR|NORMAL)$")
    custom_permissions: list[str] | None = None

    def get_normalized_role(self) -> str | None:
        """Convert role to uppercase and handle member->NORMAL mapping."""
        if self.role is None:
            return None
        role_upper = self.role.upper()
        return "NORMAL" if role_upper == "MEMBER" else role_upper


class AcceptInvitationRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=64)


@router.get("/members", response_model=list[TeamMemberResponse])
async def list_team_members(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """List all team members for the current tenant"""
    try:
        team_service = TeamService(db)
        members = await team_service.list_team_members(tenant_id=tenant_id, skip=skip, limit=limit)
        return members

    except Exception as e:
        logger.error(f"Error listing team members: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list team members")


@router.get("/members/{account_id}", response_model=TeamMemberResponse)
async def get_team_member(
    account_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Get a specific team member"""
    try:
        team_service = TeamService(db)
        member = await team_service.get_team_member(tenant_id, account_id)

        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")

        return member

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting team member: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get team member")


@router.put("/members/{account_id}", response_model=TeamMemberResponse)
async def update_team_member(
    account_id: str,
    member_data: TeamMemberUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Update a team member's role or permissions"""
    try:
        team_service = TeamService(db)

        # Check if current user has permission to update members
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))
        if not current_member or current_member["role"] not in ["owner", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to update team members"
            )

        update_data = member_data.model_dump(exclude_unset=True)
        # Normalize role if provided
        if "role" in update_data:
            update_data["role"] = member_data.get_normalized_role()

        # SECURITY: Only an existing owner can promote another member to owner
        if update_data.get("role", "").lower() == "owner":
            if not current_member or current_member["role"].lower() != "owner":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only organization owners can transfer ownership",
                )

        updated_member = await team_service.update_team_member(tenant_id, account_id, **update_data)

        return updated_member

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating team member: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update team member")


@router.delete("/members/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    account_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Remove a team member from the tenant"""
    try:
        team_service = TeamService(db)

        # Check if current user has permission to remove members
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))
        if not current_member or current_member["role"] not in ["owner", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to remove team members"
            )

        # Prevent removing yourself
        if account_id == str(current_account.id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself from the team")

        await team_service.remove_team_member(tenant_id, account_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing team member: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to remove team member")


@router.post("/invitations", response_model=TeamInvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    invitation_data: TeamInvitationCreate,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Create a team invitation"""
    try:
        # Check team member limit before creating invitation
        from src.services.billing import PlanRestrictionError, PlanRestrictionService

        restriction_service = PlanRestrictionService(db)
        try:
            await restriction_service.enforce_team_member_limit(tenant_id)
        except PlanRestrictionError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        team_service = TeamService(db)

        # Check if current user has permission to invite
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))
        if not current_member or current_member["role"] not in ["owner", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to invite team members"
            )

        # SECURITY: Only an existing owner can invite a new member directly as owner
        normalized_invite_role = invitation_data.get_normalized_role()
        if normalized_invite_role.lower() == "owner":
            if not current_member or current_member["role"].lower() != "owner":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only organization owners can invite members with the owner role",
                )

        invitation = await team_service.create_invitation(
            tenant_id=tenant_id,
            email=invitation_data.email,
            role=invitation_data.get_normalized_role(),
            invited_by=str(current_account.id),
            custom_permissions=invitation_data.custom_permissions,
        )

        return invitation

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating invitation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create invitation")


@router.get("/invitations", response_model=list[TeamInvitationResponse])
async def list_invitations(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """List all pending invitations for the current tenant"""
    try:
        team_service = TeamService(db)

        # Check if current user has permission to view invitations
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))
        if not current_member or current_member["role"] not in ["owner", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to view invitations"
            )

        invitations = await team_service.list_invitations(tenant_id=tenant_id, skip=skip, limit=limit)
        return invitations

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing invitations: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list invitations")


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invitation(
    invitation_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Cancel a pending invitation"""
    try:
        team_service = TeamService(db)

        # Check if current user has permission to cancel invitations
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))
        if not current_member or current_member["role"] not in ["owner", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to cancel invitations"
            )

        await team_service.cancel_invitation(invitation_id, tenant_id)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error canceling invitation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to cancel invitation")


@router.post("/invitations/accept", response_model=TeamMemberResponse)
async def accept_invitation(
    request: AcceptInvitationRequest,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
):
    """Accept a team invitation"""
    try:
        team_service = TeamService(db)
        member = await team_service.accept_invitation(token=request.token, account_id=str(current_account.id))

        return member

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error accepting invitation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to accept invitation")


@router.post("/invitations/{invitation_id}/resend", response_model=TeamInvitationResponse)
async def resend_invitation(
    invitation_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Resend a team invitation"""
    try:
        team_service = TeamService(db)

        # Check if current user has permission to resend invitations
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))
        if not current_member or current_member["role"] not in ["owner", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to resend invitations"
            )

        invitation = await team_service.resend_invitation(invitation_id, tenant_id)

        return invitation

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error resending invitation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to resend invitation")


class PasswordResetLinkResponse(BaseModel):
    """Response from the admin-assisted password reset endpoint."""

    account_id: str
    account_email: str
    reset_link: str
    expires_at: str
    message: str


@router.post(
    "/members/{account_id}/reset-password-link",
    response_model=PasswordResetLinkResponse,
    summary="Generate a one-time password reset link for a team member (admin only)",
)
async def generate_member_reset_link(
    account_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """
    Generate a one-time password reset link for a team member.

    The link is returned to the calling admin — it is NOT emailed automatically.
    The admin is responsible for sending it to the user through a secure channel.

    Requires OWNER or ADMIN role.
    """
    from datetime import UTC, datetime, timedelta

    from src.models import Account
    from src.models.tenant import TenantAccountJoin
    from src.services.activity.activity_log_service import ActivityLogService
    from src.services.auth_service import AuthService

    team_service = TeamService(db)

    # --- Permission check ---
    current_member = await team_service.get_team_member(tenant_id, str(current_account.id))
    if not current_member or current_member["role"] not in ["owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can generate password reset links for team members.",
        )

    try:
        target_uuid = uuid.UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid account_id format.")

    # Verify the target account belongs to this tenant
    stmt = select(TenantAccountJoin).filter_by(account_id=target_uuid, tenant_id=tenant_id)
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found in this tenant.",
        )

    # Prevent an admin from generating a reset link for an owner (privilege escalation guard)
    if membership.role and hasattr(membership.role, "value"):
        target_role = membership.role.value.lower()
    else:
        target_role = str(membership.role).lower()

    requesting_role = current_member["role"].lower()
    if target_role in ("owner",) and requesting_role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can generate reset links for other owners.",
        )

    # Load the target account
    stmt = select(Account).filter_by(id=target_uuid)
    result = await db.execute(stmt)
    target_account = result.scalar_one_or_none()
    if not target_account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    # Generate reset token using the same mechanism as forgot-password
    reset_token = AuthService.generate_reset_token()
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    # Store hashed token on the account
    target_account.reset_token = AuthService.hash_token(reset_token)
    target_account.reset_token_expires_at = expires_at.isoformat()
    await db.commit()
    await db.refresh(target_account)

    # Build the reset link using APP_BASE_URL (falls back to api_base_url)
    from src.config.settings import settings as _settings
    from src.utils.config_helper import get_app_base_url

    try:
        base_url = await get_app_base_url(db)
    except Exception:
        base_url = _settings.app_base_url or _settings.api_base_url

    reset_link = f"{base_url}/reset-password?token={reset_token}"

    # Audit log — records the admin action for compliance
    try:
        ActivityLogService.queue_activity(
            tenant_id=tenant_id,
            account_id=current_account.id,
            action="admin_generated_password_reset_link",
            resource_type="account",
            resource_id=target_uuid,
            details={
                "target_account_id": str(target_uuid),
                "target_email": target_account.email,
                "generated_by": str(current_account.id),
            },
        )
    except Exception as audit_exc:
        logger.warning(f"Failed to write admin_generated_password_reset_link audit log: {audit_exc}")

    logger.info(
        f"Admin {current_account.id} generated password reset link for account {target_uuid} in tenant {tenant_id}"
    )

    return PasswordResetLinkResponse(
        account_id=str(target_uuid),
        account_email=target_account.email,
        reset_link=reset_link,
        expires_at=expires_at.isoformat(),
        message=(
            "A one-time password reset link has been generated. "
            "Send it to the user through a secure channel. "
            "It expires in 1 hour."
        ),
    )


# Domain configuration models and endpoints
class TenantDomainUpdate(BaseModel):
    domain: str | None = Field(None, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9\-\.]*\.[a-zA-Z]{2,}$")
    auto_assign_domain_users: bool = False


class TenantDomainResponse(BaseModel):
    domain: str | None
    auto_assign_domain_users: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("/settings/domain", response_model=TenantDomainResponse)
async def get_domain_settings(
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Get domain settings for the current tenant"""
    try:
        team_service = TeamService(db)

        # Check if current user has permission (owner/admin only)
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))
        if not current_member or current_member["role"] not in ["owner", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to view domain settings"
            )

        result = await db.execute(select(Tenant).filter(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        return {"domain": tenant.domain, "auto_assign_domain_users": tenant.auto_assign_domain_users == "true"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting domain settings: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get domain settings")


@router.put("/settings/domain", response_model=TenantDomainResponse)
async def update_domain_settings(
    domain_data: TenantDomainUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """Update domain settings for the current tenant (owner only)"""
    try:
        team_service = TeamService(db)

        # Check if current user has permission (owner only for domain settings)
        current_member = await team_service.get_team_member(tenant_id, str(current_account.id))
        if not current_member or current_member["role"] != "owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can configure domain settings"
            )

        result = await db.execute(select(Tenant).filter(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Check if domain is already used by another tenant
        if domain_data.domain:
            existing_result = await db.execute(
                select(Tenant).filter(Tenant.domain == domain_data.domain.lower(), Tenant.id != tenant_id)
            )
            existing_tenant = existing_result.scalar_one_or_none()
            if existing_tenant:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This domain is already configured for another organization",
                )

        # Update domain settings
        tenant.domain = domain_data.domain.lower() if domain_data.domain else None
        tenant.auto_assign_domain_users = "true" if domain_data.auto_assign_domain_users else "false"

        await db.commit()
        await db.refresh(tenant)

        return {"domain": tenant.domain, "auto_assign_domain_users": tenant.auto_assign_domain_users == "true"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating domain settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update domain settings"
        )
