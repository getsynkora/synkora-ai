"""
OAuth User Tokens and Platform Apps Controller.

Handles user OAuth tokens and platform app management.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.database import get_async_db
from ...middleware.auth_middleware import get_current_account, get_current_tenant_id, get_optional_account
from ...models.oauth_app import OAuthApp
from ...models.tenant import Account
from ...models.user_oauth_token import UserOAuthToken
from .base import (
    SaveUserApiTokenRequest,
    _get_oauth_app_secure,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# User OAuth Token Endpoints
# =============================================================================


@router.get("/user-tokens")
async def list_user_tokens(
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List current user's connected OAuth accounts.

    Returns all OAuth tokens the authenticated user has connected,
    including provider info and connection status.
    """
    try:
        # Load tokens and their oauth_app in a single query to avoid N+1.
        # The tenant-scoping check (via _get_oauth_app_secure) is replaced by a
        # direct tenant_id filter on the joined OAuthApp row.
        tokens_result = await db.execute(
            select(UserOAuthToken)
            .options(selectinload(UserOAuthToken.oauth_app))
            .filter(UserOAuthToken.account_id == current_account.id)
        )
        user_tokens = tokens_result.scalars().all()

        result = []
        for token in user_tokens:
            oauth_app = token.oauth_app
            # SECURITY: skip tokens whose OAuth app belongs to a different tenant
            if oauth_app and oauth_app.tenant_id and oauth_app.tenant_id != tenant_id:
                continue

            token_data = token.to_dict()
            if oauth_app:
                token_data["provider"] = oauth_app.provider
                token_data["app_name"] = oauth_app.app_name

            result.append(token_data)

        return result

    except Exception as e:
        logger.error(f"List user tokens error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/user-tokens/{token_id}")
async def delete_user_token(
    token_id: str,
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Disconnect user's OAuth account (delete their token).

    Only allows deletion of tokens belonging to the authenticated user.
    """
    try:
        # Find the token
        token_result = await db.execute(
            select(UserOAuthToken).filter(
                UserOAuthToken.id == uuid.UUID(token_id), UserOAuthToken.account_id == current_account.id
            )
        )
        user_token = token_result.scalar_one_or_none()

        if not user_token:
            raise HTTPException(status_code=404, detail="Token not found")

        # Get OAuth app for logging
        # SECURITY: Validate OAuth app belongs to user's tenant
        oauth_app = await _get_oauth_app_secure(db, user_token.oauth_app_id, tenant_id=tenant_id)
        provider_name = oauth_app.provider if oauth_app else "unknown"

        # Delete the token
        await db.delete(user_token)
        await db.commit()

        logger.info(f"User {current_account.id} disconnected {provider_name} OAuth token")

        return {"success": True, "message": f"Successfully disconnected {provider_name} account"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete user token error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user-tokens/api-token")
async def save_user_api_token(
    data: SaveUserApiTokenRequest,
    current_account: Account = Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Save user's personal API token for an OAuth app that uses API token auth method.

    This allows each user to use their own API token instead of a shared one.
    """
    try:
        # SECURITY: Validate OAuth app belongs to current tenant (prevents IDOR)
        oauth_app = await _get_oauth_app_secure(db, data.oauth_app_id, tenant_id=tenant_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        # Verify it's an API token app
        if oauth_app.auth_method != "api_token":
            raise HTTPException(status_code=400, detail="This endpoint is only for API token authentication apps")

        # Check if user already has a token for this app
        existing_result = await db.execute(
            select(UserOAuthToken).filter(
                UserOAuthToken.account_id == current_account.id, UserOAuthToken.oauth_app_id == data.oauth_app_id
            )
        )
        existing_token = existing_result.scalar_one_or_none()

        if existing_token:
            # Update existing token
            # UserOAuthToken.access_token is an auto-encrypting property —
            # assigning an already-encrypted value here would double-encrypt
            # it, producing a token that never decrypts back to something
            # usable.
            existing_token.access_token = data.api_token
            existing_token.refresh_token = None  # API tokens don't have refresh tokens
            await db.commit()
            logger.info(f"User {current_account.id} updated API token for {oauth_app.provider}")
        else:
            # Create new token
            new_token = UserOAuthToken(
                account_id=current_account.id,
                oauth_app_id=data.oauth_app_id,
                # See comment above — this property encrypts on assignment.
                access_token=data.api_token,
                refresh_token=None,
                provider_user_id=None,
                provider_email=current_account.email,  # Use account email as identifier
                provider_username=current_account.name,
            )
            db.add(new_token)
            await db.commit()
            logger.info(f"User {current_account.id} saved API token for {oauth_app.provider}")

        return {"success": True, "message": f"API token saved for {oauth_app.provider}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save user API token error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apps/{app_id}/connection-status")
async def get_user_connection_status(
    app_id: int,
    tenant_id: uuid.UUID | None = Depends(get_current_tenant_id),
    current_account: Account | None = Depends(get_optional_account),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Check if the current user has connected their account to an OAuth app.

    Returns connection status and provider user info if connected.
    """
    try:
        # SECURITY: Validate OAuth app belongs to current tenant when authenticated (prevents IDOR)
        oauth_app = await _get_oauth_app_secure(db, app_id, tenant_id=tenant_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        auth_method = oauth_app.auth_method or "oauth"
        app_has_credentials = bool(oauth_app.api_token)  # covers api_token + basic_auth (password)
        app_has_github_app_credentials = bool(oauth_app.client_id and oauth_app.client_secret)

        result = {
            "app_id": app_id,
            "provider": oauth_app.provider,
            "app_name": oauth_app.app_name,
            "auth_method": auth_method,
            "connected": False,
            "admin_connected": False,  # True when shared admin credentials are configured
            "user_token": None,
            "app_has_token": bool(oauth_app.access_token) or app_has_credentials or app_has_github_app_credentials,
        }

        # For api_token / basic_auth apps there is no per-user connection —
        # the admin-configured credentials are shared by all users automatically.
        if auth_method in ("api_token", "basic_auth"):
            if app_has_credentials:
                result["connected"] = True
                result["admin_connected"] = True
            return result

        # GitHub App credentials (App ID + private key) are also admin-configured and
        # shared by all users — no per-user OAuth token is ever created for this method.
        if auth_method == "github_app":
            if app_has_github_app_credentials:
                result["connected"] = True
                result["admin_connected"] = True
            return result

        # OAuth apps: check for the current user's personal token
        if current_account:
            token_result = await db.execute(
                select(UserOAuthToken).filter(
                    UserOAuthToken.account_id == current_account.id, UserOAuthToken.oauth_app_id == app_id
                )
            )
            user_token = token_result.scalar_one_or_none()

            if user_token:
                result["connected"] = True
                result["user_token"] = {
                    "id": str(user_token.id),
                    "provider_email": user_token.provider_email,
                    "provider_username": user_token.provider_username,
                    "provider_display_name": user_token.provider_display_name,
                    "created_at": user_token.created_at.isoformat() if user_token.created_at else None,
                }

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user connection status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Platform OAuth Apps Endpoints
# =============================================================================


@router.get("/platform-apps")
async def list_platform_apps(
    provider: str = Query(None, description="Filter by provider"),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all platform-provided OAuth apps with their status for the current tenant.

    Returns platform apps with enabled/disabled status based on tenant preferences.
    """
    try:
        from ...models.tenant import Tenant

        # Get disabled providers for this tenant
        tenant_result = await db.execute(select(Tenant).filter(Tenant.id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        disabled_providers = []
        if tenant and tenant.disabled_platform_oauth_providers:
            disabled_providers = [p.lower() for p in tenant.disabled_platform_oauth_providers]

        # Query platform apps
        query = select(OAuthApp).filter(
            OAuthApp.is_platform_app.is_(True),
            OAuthApp.tenant_id.is_(None),
            OAuthApp.is_active.is_(True),
        )

        if provider:
            query = query.filter(OAuthApp.provider.ilike(provider))

        apps_result = await db.execute(query)
        apps = apps_result.scalars().all()
        result = []

        for app in apps:
            app_data = app.to_dict()
            app_data["source"] = "platform"
            app_data["enabled_for_tenant"] = app.provider.lower() not in disabled_providers
            result.append(app_data)

        return result

    except Exception as e:
        logger.error(f"List platform apps error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/platform-apps/{provider}/toggle")
async def toggle_platform_app(
    provider: str,
    enabled: bool = Query(..., description="Enable or disable the platform app"),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Enable or disable a platform OAuth app for the current tenant.

    When disabled, the platform app won't appear in the tenant's available apps
    and won't be used as a fallback.
    """
    try:
        from ...models.tenant import Tenant

        provider = provider.lower()

        # Verify platform app exists for this provider
        platform_app_result = await db.execute(
            select(OAuthApp).filter(
                OAuthApp.is_platform_app.is_(True),
                OAuthApp.tenant_id.is_(None),
                OAuthApp.provider == provider,
                OAuthApp.is_active.is_(True),
            )
        )
        platform_app = platform_app_result.scalar_one_or_none()

        if not platform_app:
            raise HTTPException(
                status_code=404,
                detail=f"No platform OAuth app found for provider: {provider}",
            )

        # Update tenant preferences
        tenant_result = await db.execute(select(Tenant).filter(Tenant.id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        disabled_providers = tenant.disabled_platform_oauth_providers or []

        if enabled:
            # Remove from disabled list
            if provider in disabled_providers:
                disabled_providers.remove(provider)
        else:
            # Add to disabled list
            if provider not in disabled_providers:
                disabled_providers.append(provider)

        tenant.disabled_platform_oauth_providers = disabled_providers
        await db.commit()

        return {
            "provider": provider,
            "enabled": enabled,
            "message": f"Platform app for {provider} {'enabled' if enabled else 'disabled'} for this tenant",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toggle platform app error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/platform-apps/status")
async def get_platform_apps_status(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get the enabled/disabled status of all platform OAuth apps for the current tenant.

    Returns a dict mapping provider name to enabled status.
    """
    try:
        from ...models.tenant import Tenant

        # Get disabled providers for this tenant
        tenant_result = await db.execute(select(Tenant).filter(Tenant.id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        disabled_providers = []
        if tenant and tenant.disabled_platform_oauth_providers:
            disabled_providers = [p.lower() for p in tenant.disabled_platform_oauth_providers]

        # Query all platform apps
        platform_apps_result = await db.execute(
            select(OAuthApp).filter(
                OAuthApp.is_platform_app.is_(True),
                OAuthApp.tenant_id.is_(None),
                OAuthApp.is_active.is_(True),
            )
        )
        platform_apps = platform_apps_result.scalars().all()

        status = {}
        for app in platform_apps:
            status[app.provider] = {
                "id": app.id,
                "app_name": app.app_name,
                "enabled": app.provider.lower() not in disabled_providers,
            }

        return status

    except Exception as e:
        logger.error(f"Get platform apps status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
