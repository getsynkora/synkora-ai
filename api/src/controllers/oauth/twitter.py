"""
Twitter/X OAuth Controller.

Handles Twitter OAuth authorization and callback using OAuth 2.0 with PKCE.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.config_helper import get_app_base_url

from ...core.database import get_async_db
from ...middleware.auth_middleware import get_optional_account, get_optional_tenant_id
from ...models.tenant import Account
from ...models.user_oauth_token import UserOAuthToken
from ...services.agents.security import decrypt_value, encrypt_value
from ...services.security.oauth_state_service import create_oauth_state, get_oauth_state, update_oauth_state
from .base import (
    _get_oauth_app_secure,
    _get_or_create_tenant_clone,
    _safe_error_redirect,
    _safe_success_redirect,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/twitter/authorize")
async def twitter_authorize(
    oauth_app_id: int = Query(..., description="OAuth app ID to authorize"),
    redirect_url: str = Query(None, description="Frontend redirect URL after OAuth"),
    user_level: bool = Query(False, description="Store token at user level instead of app level"),
    current_account: Account | None = Depends(get_optional_account),
    tenant_id: uuid.UUID | None = Depends(get_optional_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initiate Twitter OAuth authorization.

    Twitter uses OAuth 2.0 with PKCE for enhanced security.
    """
    try:
        if user_level and not current_account:
            raise HTTPException(status_code=401, detail="Authentication required for user-level OAuth")

        # SECURITY: Validate OAuth app belongs to current tenant when authenticated (prevents IDOR)
        # tenant_id comes from JWT via get_optional_tenant_id dependency
        oauth_app = await _get_oauth_app_secure(db, oauth_app_id, tenant_id=tenant_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        base_url = await get_app_base_url(db, oauth_app.tenant_id)
        redirect_url = redirect_url or f"{base_url}/oauth-apps"

        if oauth_app.auth_method == "api_token":
            return _safe_success_redirect(redirect_url, "/oauth-apps", base_url, "twitter", method="api_token")

        client_id = oauth_app.client_id
        try:
            client_secret = decrypt_value(oauth_app.client_secret)
        except Exception as e:
            logger.error(f"Failed to decrypt client secret: {e}")
            raise HTTPException(status_code=500, detail="Failed to decrypt OAuth credentials")

        redirect_uri = oauth_app.redirect_uri

        from ...services.oauth.twitter_oauth import TwitterOAuth

        oauth = TwitterOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

        state = create_oauth_state(
            {
                "oauth_app_id": oauth_app_id,
                "redirect_url": redirect_url,
                "user_level": user_level,
                "account_id": str(current_account.id) if current_account and user_level else None,
                "tenant_id": str(tenant_id) if tenant_id else None,
            }
        )
        if not state:
            raise HTTPException(status_code=500, detail="Failed to create OAuth state")

        scopes = oauth_app.scopes or [
            "tweet.read",
            "tweet.write",
            "users.read",
            "follows.read",
            "follows.write",
            "like.read",
            "like.write",
            "bookmark.read",
            "offline.access",
        ]
        auth_url, code_verifier = oauth.get_authorization_url(state=state, scopes=scopes)

        # Store code_verifier in state for PKCE verification
        update_oauth_state(state, {"code_verifier": code_verifier})

        logger.info(f"Initiating Twitter OAuth for app {oauth_app_id} (user_level={user_level})")
        return RedirectResponse(url=auth_url)

    except Exception as e:
        logger.error(f"Twitter OAuth authorization error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/twitter/callback")
async def twitter_callback(
    code: str = Query(..., description="Authorization code from Twitter"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle Twitter OAuth callback and store token.

    Twitter uses PKCE, so we need to retrieve the code_verifier from state.
    """
    try:
        state_data = get_oauth_state(state)
        if state_data is None:
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

        oauth_app_id = state_data["oauth_app_id"]
        redirect_url = state_data["redirect_url"]
        user_level = state_data.get("user_level", False)
        account_id = state_data.get("account_id")
        code_verifier = state_data.get("code_verifier")

        if not code_verifier:
            raise HTTPException(status_code=400, detail="Missing code_verifier for PKCE")

        # SECURITY: Get OAuth app (state is already validated from Redis)
        oauth_app = await _get_oauth_app_secure(db, oauth_app_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        client_id = oauth_app.client_id
        client_secret = decrypt_value(oauth_app.client_secret)
        redirect_uri = oauth_app.redirect_uri

        from ...services.oauth.twitter_oauth import TwitterOAuth

        oauth = TwitterOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

        # Exchange code for token with PKCE verifier
        token_data = await oauth.get_access_token(code, code_verifier)
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")

        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to get access token")

        from datetime import datetime, timedelta

        token_expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in)) if expires_in else None

        # Get user info
        user_info = await oauth.get_user_info(access_token)
        username = user_info.get("username", "Unknown")

        if user_level and account_id:
            result = await db.execute(
                select(UserOAuthToken).filter(
                    UserOAuthToken.account_id == uuid.UUID(account_id), UserOAuthToken.oauth_app_id == oauth_app_id
                )
            )
            existing_token = result.scalar_one_or_none()

            if existing_token:
                existing_token.access_token = encrypt_value(access_token)
                if refresh_token:
                    existing_token.refresh_token = encrypt_value(refresh_token)
                existing_token.provider_user_id = user_info.get("id")
                existing_token.provider_display_name = f"@{username}"
            else:
                user_token = UserOAuthToken(
                    account_id=uuid.UUID(account_id),
                    oauth_app_id=oauth_app_id,
                    access_token=encrypt_value(access_token),
                    refresh_token=encrypt_value(refresh_token) if refresh_token else None,
                    provider_user_id=user_info.get("id"),
                    provider_display_name=f"@{username}",
                )
                db.add(user_token)

            logger.info(f"Twitter OAuth successful (user-level) for app {oauth_app_id}, user @{username}")
        else:
            # Store on a tenant-owned clone for platform apps to prevent cross-tenant leakage
            if oauth_app.is_platform_app:
                _tenant_id_str = state_data.get("tenant_id")
                if _tenant_id_str:
                    import uuid as _uuid
                    oauth_app = await _get_or_create_tenant_clone(db, oauth_app, _uuid.UUID(_tenant_id_str))
            oauth_app.access_token = encrypt_value(access_token)
            if refresh_token:
                oauth_app.refresh_token = encrypt_value(refresh_token)
            if token_expires_at:
                oauth_app.token_expires_at = token_expires_at
            logger.info(f"Twitter OAuth successful (app-level) for app {oauth_app_id}, user @{username}")

        await db.commit()

        # SECURITY: Use safe redirect with URL-encoded parameters
        base_url = await get_app_base_url(db, oauth_app.tenant_id)
        return _safe_success_redirect(
            redirect_url=redirect_url,
            default_path="/oauth-apps",
            base_url=base_url,
            provider="twitter",
            user=username,
            user_level=str(user_level),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Twitter OAuth callback error: {e}", exc_info=True)
        # SECURITY: Get redirect URL from state and validate it
        error_state_data = get_oauth_state(state, delete=False) if state else None
        redirect_url = error_state_data.get("redirect_url") if error_state_data else None
        oauth_app_id = error_state_data.get("oauth_app_id") if error_state_data else None

        # Rollback any broken transaction before querying
        try:
            await db.rollback()
        except Exception:
            pass

        # Get base URL — fall back to env var if DB is unavailable
        import os

        base_url = os.getenv("APP_BASE_URL", "").rstrip("/")
        if not base_url and oauth_app_id:
            try:
                oauth_app = await _get_oauth_app_secure(db, oauth_app_id)
                if oauth_app:
                    base_url = await get_app_base_url(db, oauth_app.tenant_id)
            except Exception:
                pass

        return _safe_error_redirect(redirect_url, "/oauth-apps", base_url, "twitter", e)
