"""
Platform OAuth Apps Admin Controller.

CRUD endpoints for managing Synkora-owned OAuth apps that tenants can use
without configuring their own credentials.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import require_role
from src.models import AccountRole
from src.models.oauth_app import OAuthApp
from src.services.agents.security import encrypt_value

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/platform-oauth-apps", tags=["admin-platform-oauth-apps"])


class PlatformOAuthAppCreate(BaseModel):
    provider: str = Field(..., description="Provider identifier (gmail, slack, github, …)")
    app_name: str = Field(..., description="Display name for this app")
    auth_method: str = Field("oauth", description="Authentication method: oauth, api_token, or github_app")
    client_id: str = Field(..., description="OAuth client ID / GitHub App ID")
    client_secret: str = Field(..., description="OAuth client secret / GitHub App private key (stored encrypted)")
    redirect_uri: str | None = Field(None, description="OAuth redirect URI (not required for github_app or api_token)")
    scopes: list[str] = Field(default_factory=list, description="OAuth scopes")
    description: str | None = Field(None, description="Optional description")
    config: dict | None = Field(None, description="Provider-specific extra config")


class PlatformOAuthAppUpdate(BaseModel):
    app_name: str | None = None
    auth_method: str | None = None
    client_id: str | None = None
    client_secret: str | None = Field(None, description="Omit to keep existing secret")
    redirect_uri: str | None = None
    scopes: list[str] | None = None
    description: str | None = None
    config: dict | None = None


def _serialize(app: OAuthApp) -> dict:
    return {
        "id": app.id,
        "provider": app.provider,
        "app_name": app.app_name,
        "auth_method": app.auth_method,
        "client_id": app.client_id,
        "redirect_uri": app.redirect_uri,
        "scopes": app.scopes or [],
        "is_active": app.is_active,
        "description": app.description,
        "config": app.config,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "updated_at": app.updated_at.isoformat() if app.updated_at else None,
    }


async def _get_platform_app(app_id: int, db: AsyncSession) -> OAuthApp:
    result = await db.execute(
        select(OAuthApp).where(
            OAuthApp.id == app_id,
            OAuthApp.is_platform_app.is_(True),
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform OAuth app not found")
    return app


@router.get("")
async def list_platform_apps(
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_role(AccountRole.ADMIN)),
):
    """List all platform OAuth apps. client_secret is never returned."""
    try:
        result = await db.execute(
            select(OAuthApp)
            .where(OAuthApp.is_platform_app.is_(True))
            .order_by(OAuthApp.provider, OAuthApp.app_name)
        )
        apps = result.scalars().all()
        return [_serialize(a) for a in apps]
    except Exception:
        logger.exception("Failed to list platform OAuth apps")
        raise HTTPException(status_code=500, detail="Failed to list platform OAuth apps")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_platform_app(
    data: PlatformOAuthAppCreate,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_role(AccountRole.ADMIN)),
):
    """Create a new platform OAuth app."""
    try:
        app = OAuthApp(
            tenant_id=None,
            is_platform_app=True,
            provider=data.provider.lower(),
            app_name=data.app_name,
            auth_method=data.auth_method,
            client_id=data.client_id,
            client_secret=encrypt_value(data.client_secret),
            redirect_uri=data.redirect_uri,
            scopes=data.scopes,
            description=data.description,
            config=data.config,
            is_active=True,
        )
        db.add(app)
        await db.commit()
        await db.refresh(app)
        logger.info("Platform OAuth app created: provider=%s id=%s", app.provider, app.id)
        return _serialize(app)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to create platform OAuth app")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create platform OAuth app")


@router.put("/{app_id}")
async def update_platform_app(
    app_id: int,
    data: PlatformOAuthAppUpdate,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_role(AccountRole.ADMIN)),
):
    """Update a platform OAuth app. Omit client_secret to keep the existing value.

    Credential fields (client_id, client_secret, redirect_uri, scopes) are cascaded
    to all tenant clones that reference this platform app via config['platform_app_id'].
    """
    try:
        app = await _get_platform_app(app_id, db)
        if data.app_name is not None:
            app.app_name = data.app_name
        if data.auth_method is not None:
            app.auth_method = data.auth_method
        if data.client_id is not None:
            app.client_id = data.client_id
        if data.client_secret is not None and data.client_secret.strip():
            app.client_secret = encrypt_value(data.client_secret)
        if data.redirect_uri is not None:
            app.redirect_uri = data.redirect_uri
        if data.scopes is not None:
            app.scopes = data.scopes
        if data.description is not None:
            app.description = data.description
        if data.config is not None:
            app.config = data.config

        # Cascade credential changes to all tenant clones of this platform app.
        # Clones are identified by config->>'platform_app_id' == str(app_id).
        credential_changed = any([
            data.client_id is not None,
            data.client_secret is not None and data.client_secret.strip(),
            data.redirect_uri is not None,
            data.scopes is not None,
        ])
        if credential_changed:
            clones_result = await db.execute(
                select(OAuthApp).where(
                    OAuthApp.is_platform_app.is_(False),
                    OAuthApp.config["platform_app_id"].as_string() == str(app_id),
                )
            )
            clones = clones_result.scalars().all()
            for clone in clones:
                if data.client_id is not None:
                    clone.client_id = data.client_id
                if data.client_secret is not None and data.client_secret.strip():
                    clone.client_secret = encrypt_value(data.client_secret)
                if data.redirect_uri is not None:
                    clone.redirect_uri = data.redirect_uri
                if data.scopes is not None:
                    clone.scopes = data.scopes
            if clones:
                logger.info(
                    "Cascaded credential update to %d clone(s) of platform app id=%s",
                    len(clones),
                    app_id,
                )

        await db.commit()
        await db.refresh(app)
        return _serialize(app)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update platform OAuth app id=%s", app_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update platform OAuth app")


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform_app(
    app_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_role(AccountRole.ADMIN)),
):
    """Delete a platform OAuth app."""
    try:
        app = await _get_platform_app(app_id, db)
        await db.delete(app)
        await db.commit()
        logger.info("Platform OAuth app deleted: id=%s", app_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete platform OAuth app id=%s", app_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete platform OAuth app")


@router.patch("/{app_id}/toggle")
async def toggle_platform_app(
    app_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_role(AccountRole.ADMIN)),
):
    """Enable or disable a platform OAuth app."""
    try:
        app = await _get_platform_app(app_id, db)
        app.is_active = not app.is_active
        await db.commit()
        await db.refresh(app)
        return _serialize(app)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to toggle platform OAuth app id=%s", app_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to toggle platform OAuth app")
