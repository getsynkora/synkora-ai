"""
Platform Settings Controller - Admin endpoints for platform configuration
"""

import logging
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, require_platform_admin
from src.models.tenant import Account, AccountRole, AccountStatus, Tenant, TenantAccountJoin, TenantStatus
from src.services.activity.activity_log_service import ActivityLogService
from src.services.billing.platform_settings_service import PlatformSettingsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/platform-settings", tags=["Platform Settings"])


# Request/Response Schemas
class StripeKeysUpdate(BaseModel):
    """Schema for updating Stripe API keys"""

    secret_key: str | None = Field(None, description="Stripe secret key (will be encrypted)")
    publishable_key: str | None = Field(None, description="Stripe publishable key")
    webhook_secret: str | None = Field(None, description="Stripe webhook secret (will be encrypted)")


class PlatformSettingsResponse(BaseModel):
    """Schema for platform settings response"""

    stripe_enabled: bool
    stripe_configured: bool
    stripe_publishable_key: str | None

    model_config = ConfigDict(from_attributes=True)


class StripeConnectionTest(BaseModel):
    """Schema for Stripe connection test response"""

    success: bool
    account_id: str | None = None
    account_name: str | None = None
    country: str | None = None
    currency: str | None = None
    error: str | None = None


@router.get("", response_model=PlatformSettingsResponse)
async def get_platform_settings(db: AsyncSession = Depends(get_async_db), _: None = Depends(require_platform_admin)):
    """
    Get current platform settings

    Requires: admin permission
    """
    service = PlatformSettingsService(db)
    settings = await service.get_settings()

    return PlatformSettingsResponse(
        stripe_enabled=settings.stripe_enabled == "true",
        stripe_configured=await service.is_stripe_configured(),
        stripe_publishable_key=settings.stripe_publishable_key,
    )


@router.put("/stripe-keys", response_model=PlatformSettingsResponse)
async def update_stripe_keys(
    data: StripeKeysUpdate, db: AsyncSession = Depends(get_async_db), _: None = Depends(require_platform_admin)
):
    """
    Update Stripe API keys

    Requires: admin permission
    """
    service = PlatformSettingsService(db)

    # Update keys
    settings = await service.update_stripe_keys(
        secret_key=data.secret_key, publishable_key=data.publishable_key, webhook_secret=data.webhook_secret
    )

    return PlatformSettingsResponse(
        stripe_enabled=settings.stripe_enabled == "true",
        stripe_configured=await service.is_stripe_configured(),
        stripe_publishable_key=settings.stripe_publishable_key,
    )


@router.post("/stripe/enable", response_model=PlatformSettingsResponse)
async def enable_stripe(db: AsyncSession = Depends(get_async_db), _: None = Depends(require_platform_admin)):
    """
    Enable Stripe integration

    Requires: admin permission
    Raises: 400 if Stripe keys are not configured
    """
    service = PlatformSettingsService(db)

    try:
        settings = await service.enable_stripe()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return PlatformSettingsResponse(
        stripe_enabled=settings.stripe_enabled == "true",
        stripe_configured=await service.is_stripe_configured(),
        stripe_publishable_key=settings.stripe_publishable_key,
    )


@router.post("/stripe/disable", response_model=PlatformSettingsResponse)
async def disable_stripe(db: AsyncSession = Depends(get_async_db), _: None = Depends(require_platform_admin)):
    """
    Disable Stripe integration

    Requires: admin permission
    """
    service = PlatformSettingsService(db)
    settings = await service.disable_stripe()

    return PlatformSettingsResponse(
        stripe_enabled=settings.stripe_enabled == "true",
        stripe_configured=await service.is_stripe_configured(),
        stripe_publishable_key=settings.stripe_publishable_key,
    )


@router.post("/stripe/test", response_model=StripeConnectionTest)
async def test_stripe_connection(db: AsyncSession = Depends(get_async_db), _: None = Depends(require_platform_admin)):
    """
    Test Stripe connection with current keys

    Requires: admin permission
    Raises: 400 if Stripe is not configured
    """
    service = PlatformSettingsService(db)

    try:
        result = await service.test_stripe_connection()
        return StripeConnectionTest(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/stripe-keys", response_model=PlatformSettingsResponse)
async def clear_stripe_keys(db: AsyncSession = Depends(get_async_db), _: None = Depends(require_platform_admin)):
    """
    Clear all Stripe keys (useful for testing or reconfiguration)

    Requires: admin permission
    """
    service = PlatformSettingsService(db)
    settings = await service.clear_stripe_keys()

    return PlatformSettingsResponse(
        stripe_enabled=settings.stripe_enabled == "true",
        stripe_configured=await service.is_stripe_configured(),
        stripe_publishable_key=settings.stripe_publishable_key,
    )


# ---------------------------------------------------------------------------
# Encryption key rotation endpoints
# ---------------------------------------------------------------------------


class KeyRotationResponse(BaseModel):
    """Response schema for key-rotation endpoints."""

    task_id: str
    status: str
    message: str


@router.post("/key-rotation/start", response_model=KeyRotationResponse)
async def start_key_rotation(_: None = Depends(require_platform_admin)):
    """
    Trigger asynchronous encryption key rotation.

    Re-encrypts all sensitive database fields with the current primary key
    (the first key in the ENCRYPTION_KEY comma-separated list).

    Rotation workflow:
    1. Set ENCRYPTION_KEY=NEW_KEY,OLD_KEY and restart the API + workers.
    2. Call this endpoint to re-encrypt all rows.
    3. Verify the task completes without errors (check task result by task_id).
    4. Set ENCRYPTION_KEY=NEW_KEY and restart.

    Requires: platform admin permission
    """
    try:
        from src.tasks.key_rotation_task import rotate_encryption_keys

        task = rotate_encryption_keys.delay(dry_run=False)
        logger.info("Key rotation task enqueued: task_id=%s", task.id)
        return KeyRotationResponse(
            task_id=task.id,
            status="queued",
            message="Key rotation task enqueued. Poll the task result by task_id to track progress.",
        )
    except Exception as exc:
        logger.error("Failed to enqueue key rotation task: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue key rotation task: {exc}",
        ) from exc


@router.post("/key-rotation/dry-run", response_model=KeyRotationResponse)
async def dry_run_key_rotation(_: None = Depends(require_platform_admin)):
    """
    Trigger a dry-run of the encryption key rotation.

    Counts how many rows would be re-encrypted without writing any changes.
    Useful to verify the rotation scope before running the real rotation.

    Requires: platform admin permission
    """
    try:
        from src.tasks.key_rotation_task import rotate_encryption_keys

        task = rotate_encryption_keys.delay(dry_run=True)
        logger.info("Key rotation dry-run task enqueued: task_id=%s", task.id)
        return KeyRotationResponse(
            task_id=task.id,
            status="queued",
            message="Key rotation dry-run task enqueued. No data will be written.",
        )
    except Exception as exc:
        logger.error("Failed to enqueue key rotation dry-run task: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue key rotation dry-run task: {exc}",
        ) from exc


# ---- workspaces: status, owner and billing ---------------------------------------------------------


class WorkspaceOwner(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    # INACTIVE until the email address is verified; SUSPENDED when a platform admin stopped the account
    status: str


class WorkspaceInfo(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    external_billing: bool
    created_at: datetime
    owner: WorkspaceOwner | None


class WorkspaceUpdate(BaseModel):
    status: Literal["ACTIVE", "SUSPENDED"] | None = None
    external_billing: bool | None = None


class OwnerStatusUpdate(BaseModel):
    # ACTIVE also marks the email address verified, for an owner who never got the verification email
    status: Literal["ACTIVE", "SUSPENDED"]


async def _owners(db: AsyncSession, tenant_ids: list[uuid.UUID]) -> dict[uuid.UUID, Account]:
    """The first owner of each workspace."""
    if not tenant_ids:
        return {}
    rows = await db.execute(
        select(TenantAccountJoin.tenant_id, Account)
        .join(Account, Account.id == TenantAccountJoin.account_id)
        .where(TenantAccountJoin.tenant_id.in_(tenant_ids), TenantAccountJoin.role == AccountRole.OWNER)
        .order_by(TenantAccountJoin.created_at)
    )
    owners: dict[uuid.UUID, Account] = {}
    for tenant_id, owner in rows.all():
        owners.setdefault(tenant_id, owner)
    return owners


def _workspace_info(tenant: Tenant, owner: Account | None) -> WorkspaceInfo:
    return WorkspaceInfo(
        id=tenant.id,
        name=tenant.name,
        status=str(tenant.status),
        external_billing=bool(tenant.external_billing),
        created_at=tenant.created_at,
        owner=WorkspaceOwner(id=owner.id, name=owner.name, email=owner.email, status=str(owner.status))
        if owner
        else None,
    )


async def _workspace_or_404(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    tenant = await db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return tenant


@router.get("/workspaces", response_model=list[WorkspaceInfo])
async def list_workspaces(
    search: str | None = Query(
        None, max_length=255, description="Part of the name, the exact id, or the owner's email"
    ),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_platform_admin),
):
    """
    Workspaces matching ``search`` (at most 25), or, without it, every workspace billed in another system.
    Requires: platform admin
    """
    query = select(Tenant).order_by(Tenant.name).limit(25)
    term = (search or "").strip()
    if not term:
        query = query.where(Tenant.external_billing.is_(True))
    else:
        pattern = f"%{term.replace('%', '').replace('_', '')}%"
        owned_by_email = (
            select(TenantAccountJoin.tenant_id)
            .join(Account, Account.id == TenantAccountJoin.account_id)
            .where(TenantAccountJoin.role == AccountRole.OWNER, Account.email.ilike(pattern))
        )
        conditions = [Tenant.name.ilike(pattern), Tenant.id.in_(owned_by_email)]
        try:
            conditions.append(Tenant.id == uuid.UUID(term))
        except ValueError:
            pass
        query = query.where(or_(*conditions))
    tenants = (await db.execute(query)).scalars().all()
    owners = await _owners(db, [tenant.id for tenant in tenants])
    return [_workspace_info(tenant, owners.get(tenant.id)) for tenant in tenants]


@router.patch("/workspaces/{tenant_id}", response_model=WorkspaceInfo)
async def update_workspace(
    tenant_id: uuid.UUID,
    body: WorkspaceUpdate,
    db: AsyncSession = Depends(get_async_db),
    account: Account = Depends(get_current_account),
    _: None = Depends(require_platform_admin),
):
    """
    Suspend or reactivate a workspace (a suspended one cannot be used from the dashboard or with its API keys), or allow
    (or stop) its own platform key setting its plan because it is paid for in another system.
    Requires: platform admin
    """
    tenant = await _workspace_or_404(db, tenant_id)
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to change")
    if body.status == TenantStatus.SUSPENDED:
        own = await db.execute(
            select(TenantAccountJoin.id).where(
                TenantAccountJoin.tenant_id == tenant.id, TenantAccountJoin.account_id == account.id
            )
        )
        if own.first() is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot suspend your own workspace")
    if body.status is not None:
        tenant.status = TenantStatus(body.status)
    if body.external_billing is not None:
        tenant.external_billing = body.external_billing
    await db.commit()
    await db.refresh(tenant)
    ActivityLogService.queue_activity(
        tenant_id=tenant.id,
        account_id=account.id,
        action="workspace.updated_by_platform_admin",
        resource_type="tenant",
        resource_id=tenant.id,
        details=changes,
    )
    logger.info("Workspace %s changed by platform admin %s: %s", tenant.id, account.id, changes)
    owners = await _owners(db, [tenant.id])
    return _workspace_info(tenant, owners.get(tenant.id))


@router.patch("/workspaces/{tenant_id}/owner", response_model=WorkspaceInfo)
async def update_workspace_owner(
    tenant_id: uuid.UUID,
    body: OwnerStatusUpdate,
    db: AsyncSession = Depends(get_async_db),
    account: Account = Depends(get_current_account),
    _: None = Depends(require_platform_admin),
):
    """
    Activate the workspace owner's account (marking the email address verified) or suspend it. A suspended account
    cannot sign in, and its open sessions stop working at once.
    Requires: platform admin
    """
    tenant = await _workspace_or_404(db, tenant_id)
    owner = (await _owners(db, [tenant.id])).get(tenant.id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This workspace has no owner")
    if owner.id == account.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot change your own account")
    owner.status = AccountStatus(body.status)
    if body.status == AccountStatus.ACTIVE:
        owner.email_verification_token = None  # verified by a platform admin; an old link no longer applies
    await db.commit()
    await db.refresh(tenant)
    await db.refresh(owner)
    ActivityLogService.queue_activity(
        tenant_id=tenant.id,
        account_id=account.id,
        action="account.status_changed_by_platform_admin",
        resource_type="account",
        resource_id=owner.id,
        details={"status": body.status},
    )
    logger.info("Owner %s of workspace %s set to %s by platform admin %s", owner.id, tenant.id, body.status, account.id)
    return _workspace_info(tenant, owner)
