"""
OAuth Apps CRUD Controller.

Handles OAuth app creation, listing, updating, and deletion.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_async_db
from ...middleware.auth_middleware import get_current_tenant_id, get_optional_account
from ...models.oauth_app import OAuthApp
from ...models.tenant import Account
from ...models.user_oauth_token import UserOAuthToken
from ...services.agents.security import encrypt_value
from .base import (
    OAuthAppCreate,
    OAuthAppUpdate,
    _get_oauth_app_secure,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_mailisk_config(provider: str, auth_method: str, config: dict | None) -> None:
    """Validate Mailisk-specific configuration requirements."""
    if str(provider).lower() != "mailisk" or auth_method != "api_token":
        return

    namespace = ""
    if isinstance(config, dict):
        namespace = str(config.get("namespace") or "").strip()

    if not namespace:
        raise HTTPException(status_code=400, detail="Mailisk integrations require config.namespace")


@router.get("/apps")
async def list_oauth_apps(
    provider: str = Query(None, description="Filter by provider"),
    include_user_status: bool = Query(False, description="Include current user's connection status"),
    include_platform_apps: bool = Query(True, description="Include platform-provided OAuth apps"),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account: Account | None = Depends(get_optional_account),
    db: AsyncSession = Depends(get_async_db),
):
    """List all OAuth apps available to the current tenant (tenant's own + enabled platform apps)."""
    try:
        from ...models.tenant import Tenant

        result = []

        # Get tenant's own apps
        query = select(OAuthApp).filter(OAuthApp.tenant_id == tenant_id)

        if provider:
            # Case-insensitive provider matching
            query = query.filter(OAuthApp.provider.ilike(provider))

        tenant_apps_result = await db.execute(query)
        tenant_apps = tenant_apps_result.scalars().all()

        for app in tenant_apps:
            app_data = app.to_dict(include_tokens=True)
            app_data["source"] = "tenant"

            # Include user connection status if requested and user is authenticated
            if include_user_status and current_account:
                user_token_result = await db.execute(
                    select(UserOAuthToken).filter(
                        UserOAuthToken.account_id == current_account.id,
                        UserOAuthToken.oauth_app_id == app.id,
                    )
                )
                user_token = user_token_result.scalar_one_or_none()
                app_data["user_connected"] = user_token is not None
                if user_token:
                    app_data["user_provider_email"] = user_token.provider_email
                    app_data["user_provider_username"] = user_token.provider_username

            result.append(app_data)

        # Include platform apps if requested
        if include_platform_apps:
            # Get disabled providers for this tenant
            tenant_result = await db.execute(select(Tenant).filter(Tenant.id == tenant_id))
            tenant = tenant_result.scalar_one_or_none()
            disabled_providers = []
            if tenant and tenant.disabled_platform_oauth_providers:
                disabled_providers = [p.lower() for p in tenant.disabled_platform_oauth_providers]

            # Query platform apps
            platform_query = select(OAuthApp).filter(
                OAuthApp.is_platform_app.is_(True),
                OAuthApp.tenant_id.is_(None),
                OAuthApp.is_active.is_(True),
            )

            if provider:
                platform_query = platform_query.filter(OAuthApp.provider.ilike(provider))

            platform_apps_result = await db.execute(platform_query)
            platform_apps = platform_apps_result.scalars().all()

            for app in platform_apps:
                # Skip if this provider is disabled for the tenant
                if app.provider.lower() in disabled_providers:
                    continue

                app_data = app.to_dict(include_tokens=True)
                app_data["source"] = "platform"

                # Include user connection status if requested
                if include_user_status and current_account:
                    user_token_result = await db.execute(
                        select(UserOAuthToken).filter(
                            UserOAuthToken.account_id == current_account.id,
                            UserOAuthToken.oauth_app_id == app.id,
                        )
                    )
                    user_token = user_token_result.scalar_one_or_none()
                    app_data["user_connected"] = user_token is not None
                    if user_token:
                        app_data["user_provider_email"] = user_token.provider_email
                        app_data["user_provider_username"] = user_token.provider_username

                result.append(app_data)

        return result

    except Exception as e:
        logger.error(f"List OAuth apps error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/apps/{app_id}")
async def get_oauth_app(
    app_id: int,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific OAuth app (tenant or platform).

    SECURITY: Requires authentication and verifies app belongs to tenant or is a platform app.
    """
    try:
        # SECURITY: Use secure helper that handles both tenant and platform apps
        app = await _get_oauth_app_secure(db, app_id, tenant_id=tenant_id, allow_platform_apps=True)

        if not app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        app_data = app.to_dict()
        app_data["source"] = "platform" if app.is_platform_app else "tenant"

        return app_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get OAuth app error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apps")
async def create_oauth_app(
    data: OAuthAppCreate,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new OAuth app."""
    try:
        # Validate authentication method and required fields
        if data.auth_method not in ["oauth", "api_token", "basic_auth"]:
            raise HTTPException(status_code=400, detail="auth_method must be 'oauth', 'api_token', or 'basic_auth'")

        if data.auth_method == "oauth":
            if not all([data.client_id, data.client_secret, data.redirect_uri]):
                raise HTTPException(
                    status_code=400, detail="client_id, client_secret, and redirect_uri are required for OAuth method"
                )
        elif data.auth_method == "api_token":
            if not data.api_token:
                raise HTTPException(status_code=400, detail="api_token is required for API token method")
        elif data.auth_method == "basic_auth":
            if not data.api_token:
                raise HTTPException(
                    status_code=400, detail="password (api_token field) is required for basic_auth method"
                )

        _validate_mailisk_config(data.provider, data.auth_method, data.config)

        # Check if app with same provider and name exists for this tenant
        existing_result = await db.execute(
            select(OAuthApp).filter(
                OAuthApp.tenant_id == tenant_id, OAuthApp.provider == data.provider, OAuthApp.app_name == data.app_name
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=400, detail=f"OAuth app '{data.app_name}' for provider '{data.provider}' already exists"
            )

        # If this is set as default, unset other defaults for this provider and tenant
        if data.is_default:
            await db.execute(
                update(OAuthApp)
                .where(OAuthApp.tenant_id == tenant_id, OAuthApp.provider == data.provider, OAuthApp.is_default)
                .values(is_default=False)
            )

        # Prepare encrypted credentials based on auth method
        encrypted_secret = None
        encrypted_api_token = None

        if data.auth_method == "oauth" and data.client_secret:
            encrypted_secret = encrypt_value(data.client_secret)
        elif data.auth_method in ("api_token", "basic_auth") and data.api_token:
            encrypted_api_token = encrypt_value(data.api_token)

        # Create new OAuth app
        new_app = OAuthApp(
            tenant_id=tenant_id,
            provider=data.provider,
            app_name=data.app_name,
            auth_method=data.auth_method,
            client_id=data.client_id,
            client_secret=encrypted_secret,
            redirect_uri=data.redirect_uri,
            scopes=data.scopes,
            api_token=encrypted_api_token,
            config=data.config,
            is_default=data.is_default,
            description=data.description,
            tags=data.tags or [],
            is_internal_tool=data.is_internal_tool,
        )

        db.add(new_app)
        await db.commit()
        await db.refresh(new_app)

        logger.info(f"Created OAuth app: {data.provider}/{data.app_name} (method: {data.auth_method})")

        return new_app.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create OAuth app error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/apps/{app_id}")
async def update_oauth_app(
    app_id: int,
    data: OAuthAppUpdate,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update an OAuth app.

    SECURITY: Requires authentication and verifies app belongs to tenant.
    """
    try:
        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        app_result = await db.execute(select(OAuthApp).filter(OAuthApp.id == app_id, OAuthApp.tenant_id == tenant_id))
        app = app_result.scalar_one_or_none()

        if not app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        # Validate auth method if changing
        if data.auth_method is not None and data.auth_method not in ["oauth", "api_token", "basic_auth"]:
            raise HTTPException(status_code=400, detail="auth_method must be 'oauth', 'api_token', or 'basic_auth'")

        _validate_mailisk_config(
            app.provider,
            data.auth_method or app.auth_method,
            data.config if data.config is not None else app.config,
        )

        # Update fields if provided
        if data.app_name is not None:
            app.app_name = data.app_name

        if data.auth_method is not None:
            app.auth_method = data.auth_method

        # OAuth fields
        if data.client_id is not None:
            app.client_id = data.client_id
        if data.client_secret is not None:
            app.client_secret = encrypt_value(data.client_secret)
        if data.redirect_uri is not None:
            app.redirect_uri = data.redirect_uri
        if data.scopes is not None:
            app.scopes = data.scopes

        # API Token field
        if data.api_token is not None:
            app.api_token = encrypt_value(data.api_token)

        # Provider-specific config
        if data.config is not None:
            app.config = data.config

        # Common fields
        if data.is_active is not None:
            app.is_active = data.is_active
        if data.description is not None:
            app.description = data.description
        if data.tags is not None:
            app.tags = data.tags
        if data.is_internal_tool is not None:
            app.is_internal_tool = data.is_internal_tool

        # Handle default flag
        if data.is_default is not None and data.is_default:
            # Unset other defaults for this provider within same tenant
            # SECURITY: Filter by tenant_id to prevent affecting other tenants' apps
            await db.execute(
                update(OAuthApp)
                .where(
                    OAuthApp.tenant_id == tenant_id,
                    OAuthApp.provider == app.provider,
                    OAuthApp.id != app_id,
                    OAuthApp.is_default,
                )
                .values(is_default=False)
            )
            app.is_default = True
        elif data.is_default is not None:
            app.is_default = False

        await db.commit()
        await db.refresh(app)

        logger.info(f"Updated OAuth app: {app.provider}/{app.app_name} (method: {app.auth_method})")

        return app.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update OAuth app error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/apps/{app_id}")
async def delete_oauth_app(
    app_id: int,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete an OAuth app.

    SECURITY: Requires authentication and verifies app belongs to tenant.
    """
    try:
        # SECURITY: Filter by tenant_id to prevent IDOR attacks
        app_result = await db.execute(select(OAuthApp).filter(OAuthApp.id == app_id, OAuthApp.tenant_id == tenant_id))
        app = app_result.scalar_one_or_none()

        if not app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        provider = app.provider
        app_name = app.app_name

        # Delete associated user tokens first — oauth_app_id is NOT NULL so
        # SQLAlchemy cannot nullify the FK before deleting the parent row.
        tokens_result = await db.execute(select(UserOAuthToken).filter(UserOAuthToken.oauth_app_id == app_id))
        tokens = tokens_result.scalars().all()
        for token in tokens:
            await db.delete(token)

        await db.delete(app)
        await db.commit()

        logger.info(f"Deleted OAuth app: {provider}/{app_name} (removed {len(tokens)} user token(s))")

        return {"success": True, "message": f"OAuth app '{app_name}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete OAuth app error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete OAuth app. Please disconnect all connected accounts before deleting.",
        )
