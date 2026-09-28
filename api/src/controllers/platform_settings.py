"""
Platform Settings Controller - Admin endpoints for platform configuration
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import require_platform_admin
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
