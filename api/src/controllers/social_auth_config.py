"""
Social Auth Provider Configuration Controllers.

API endpoints for managing social login provider configurations.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id, require_role
from src.models import AccountRole, Tenant
from src.models.tenant import TenantType
from src.services.social_auth.provider_config_service import (
    SocialAuthProviderConfigService,
)

logger = logging.getLogger(__name__)


async def require_provider_admin(
    tenant_id: UUID = Depends(get_current_tenant_id),
    account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
    _role=Depends(require_role(AccountRole.ADMIN)),
):
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    if tenant.tenant_type == TenantType.PLATFORM and account.is_platform_admin not in (True, "true"):
        raise HTTPException(403, "Platform administrator required")


router = APIRouter(
    prefix="/api/v1/social-auth-config",
    tags=["social-auth-config"],
    dependencies=[Depends(require_provider_admin)],
)


# Request/Response Models
class ProviderConfigCreate(BaseModel):
    """Request model for creating a provider configuration."""

    provider_name: str = Field(..., description="Provider name (google, microsoft, apple)")
    client_id: str = Field(..., description="OAuth client ID")
    client_secret: str = Field(..., description="OAuth client secret")
    redirect_uri: str = Field(..., description="OAuth redirect URI")
    config: dict | None = Field(None, description="Additional configuration")
    enabled: str = Field(default="true", description="Whether the provider is enabled")


class ProviderConfigUpdate(BaseModel):
    """Request model for updating a provider configuration."""

    client_id: str | None = Field(None, description="OAuth client ID")
    client_secret: str | None = Field(None, description="OAuth client secret")
    redirect_uri: str | None = Field(None, description="OAuth redirect URI")
    config: dict | None = Field(None, description="Additional configuration")
    enabled: str | None = Field(None, description="Whether the provider is enabled")


@router.get("")
async def list_providers(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all social auth providers for the current tenant.

    Returns:
        List of provider configurations (with secrets masked)
    """
    try:
        service = SocialAuthProviderConfigService(db)
        providers = await service.list_providers(tenant_id)

        return {
            "success": True,
            "providers": providers,
        }
    except Exception as e:
        logger.exception("Error listing providers")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{provider_name}")
async def get_provider(
    provider_name: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get a specific provider configuration.

    Args:
        provider_name: Provider name (google, microsoft, apple)

    Returns:
        Provider configuration (with secret masked)
    """
    try:
        service = SocialAuthProviderConfigService(db)
        provider = await service.get_provider(tenant_id, provider_name)

        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider {provider_name} not found",
            )

        return {
            "success": True,
            "provider": provider,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error getting provider %s", provider_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.post("")
async def create_provider(
    config: ProviderConfigCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new provider configuration.

    Args:
        config: Provider configuration

    Returns:
        Created provider configuration
    """
    try:
        service = SocialAuthProviderConfigService(db)
        provider = await service.create_provider(
            tenant_id=tenant_id,
            provider_name=config.provider_name,
            client_id=config.client_id,
            client_secret=config.client_secret,
            redirect_uri=config.redirect_uri,
            config=config.config,
            enabled=config.enabled,
        )

        return {
            "success": True,
            "message": f"Provider {config.provider_name} created successfully",
            "provider": provider,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        logger.exception("Error creating provider")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.put("/{provider_name}")
async def update_provider(
    provider_name: str,
    config: ProviderConfigUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update an existing provider configuration.

    Args:
        provider_name: Provider name (google, microsoft, apple)
        config: Updated configuration

    Returns:
        Updated provider configuration
    """
    try:
        service = SocialAuthProviderConfigService(db)
        provider = await service.update_provider(
            tenant_id=tenant_id,
            provider_name=provider_name,
            client_id=config.client_id,
            client_secret=config.client_secret,
            redirect_uri=config.redirect_uri,
            config=config.config,
            enabled=config.enabled,
        )

        return {
            "success": True,
            "message": f"Provider {provider_name} updated successfully",
            "provider": provider,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception:
        logger.exception("Error updating provider %s", provider_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.delete("/{provider_name}")
async def delete_provider(
    provider_name: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a provider configuration.

    Args:
        provider_name: Provider name (google, microsoft, apple)

    Returns:
        Success message
    """
    try:
        service = SocialAuthProviderConfigService(db)
        deleted = await service.delete_provider(tenant_id, provider_name)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Provider {provider_name} not found",
            )

        return {
            "success": True,
            "message": f"Provider {provider_name} deleted successfully",
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error deleting provider %s", provider_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.post("/{provider_name}/test")
async def test_provider(
    provider_name: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Test a provider configuration.

    Args:
        provider_name: Provider name (google, microsoft, apple)

    Returns:
        Test result with status and message
    """
    try:
        service = SocialAuthProviderConfigService(db)
        result = await service.test_provider(tenant_id, provider_name)

        return result
    except Exception:
        logger.exception("Error testing provider %s", provider_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
