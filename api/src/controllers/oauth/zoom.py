"""
Zoom OAuth Controller.

Handles Zoom OAuth authorization and callback.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

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
from ...services.security.oauth_state_service import create_oauth_state, get_oauth_state
from .base import (
    _get_oauth_app_secure,
    _get_or_create_tenant_clone,
    _safe_error_redirect,
    _safe_success_redirect,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/zoom/authorize")
async def zoom_authorize(
    oauth_app_id: int = Query(..., description="OAuth app ID to authorize"),
    redirect_url: str = Query(None, description="Frontend redirect URL after OAuth"),
    user_level: bool = Query(False, description="Store token at user level instead of app level"),
    current_account: Account | None = Depends(get_optional_account),
    tenant_id: uuid.UUID | None = Depends(get_optional_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initiate Zoom OAuth authorization for an OAuth app.

    If user_level=True and user is authenticated, the token will be stored
    in the UserOAuthToken table for the current user.
    """
    try:
        # Validate user_level requires authentication
        if user_level and not current_account:
            raise HTTPException(status_code=401, detail="Authentication required for user-level OAuth")

        # SECURITY: Validate OAuth app belongs to current tenant when authenticated (prevents IDOR)
        # tenant_id comes from JWT via get_optional_tenant_id dependency
        oauth_app = await _get_oauth_app_secure(db, oauth_app_id, tenant_id=tenant_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        base_url = await get_app_base_url(db, oauth_app.tenant_id)
        redirect_url = redirect_url or f"{base_url}/oauth-apps"

        # If using API token, no OAuth flow needed
        if oauth_app.auth_method == "api_token":
            return _safe_success_redirect(redirect_url, "/oauth-apps", base_url, "zoom", method="api_token")

        # Decrypt credentials
        client_id = oauth_app.client_id
        try:
            client_secret = decrypt_value(oauth_app.client_secret)
        except Exception as e:
            logger.error(f"Failed to decrypt client secret: {e}")
            raise HTTPException(status_code=500, detail="Failed to decrypt OAuth credentials")

        redirect_uri = oauth_app.redirect_uri

        # Initialize OAuth client
        from ...services.oauth.zoom_oauth import ZoomOAuth

        oauth = ZoomOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

        # SECURITY: Generate state for CSRF protection (Redis-backed)
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

        # Get authorization URL
        auth_url = oauth.get_authorization_url(state=state)

        logger.info(f"Initiating Zoom OAuth for app {oauth_app_id} (user_level={user_level}), state={state[:16]}...")
        return RedirectResponse(url=auth_url)

    except Exception as e:
        logger.error(f"Zoom OAuth authorization error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/zoom/callback")
async def zoom_callback(
    code: str = Query(..., description="Authorization code from Zoom"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle Zoom OAuth callback and store token.

    If user_level was set in the authorize request, stores in UserOAuthToken.
    Otherwise stores in OAuthApp (legacy behavior).
    """
    try:
        logger.info(f"Zoom OAuth callback received: state={state[:16]}...")

        # SECURITY: Retrieve and delete state (single-use, Redis-backed)
        state_data = get_oauth_state(state)
        if state_data is None:
            logger.error(f"Zoom OAuth state not found or expired: {state[:16]}...")
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

        oauth_app_id = state_data["oauth_app_id"]
        redirect_url = state_data["redirect_url"]
        user_level = state_data.get("user_level", False)
        account_id = state_data.get("account_id")

        # SECURITY: Get OAuth app (state is already validated from Redis)
        oauth_app = await _get_oauth_app_secure(db, oauth_app_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        # Decrypt credentials
        client_id = oauth_app.client_id
        client_secret = decrypt_value(oauth_app.client_secret)
        redirect_uri = oauth_app.redirect_uri

        # Initialize OAuth client
        from ...services.oauth.zoom_oauth import ZoomOAuth

        oauth = ZoomOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

        # Exchange code for token
        token_data = await oauth.exchange_code(code)
        if not token_data.get("access_token"):
            raise HTTPException(status_code=400, detail="Failed to get access token")

        # Get user info
        user_info = await oauth.get_user_info(token_data["access_token"])
        user_email = user_info.get("email", "")

        # Calculate token expiration
        token_expires_at = None
        if token_data.get("expires_in"):
            token_expires_at = datetime.now(UTC) + timedelta(seconds=token_data["expires_in"])

        # Store token based on user_level flag
        if user_level and account_id:
            # Store in UserOAuthToken (per-user)
            result = await db.execute(
                select(UserOAuthToken).filter(
                    UserOAuthToken.account_id == uuid.UUID(account_id), UserOAuthToken.oauth_app_id == oauth_app_id
                )
            )
            existing_token = result.scalar_one_or_none()

            if existing_token:
                # Update existing token
                existing_token.access_token = encrypt_value(token_data["access_token"])
                if token_data.get("refresh_token"):
                    existing_token.refresh_token = encrypt_value(token_data["refresh_token"])
                existing_token.token_expires_at = token_expires_at
                existing_token.provider_user_id = user_info.get("id")
                existing_token.provider_email = user_email
                existing_token.provider_display_name = (
                    user_info.get("display_name")
                    or f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
                )
            else:
                # Create new user token
                user_token = UserOAuthToken(
                    account_id=uuid.UUID(account_id),
                    oauth_app_id=oauth_app_id,
                    access_token=encrypt_value(token_data["access_token"]),
                    refresh_token=encrypt_value(token_data["refresh_token"])
                    if token_data.get("refresh_token")
                    else None,
                    token_expires_at=token_expires_at,
                    provider_user_id=user_info.get("id"),
                    provider_email=user_email,
                    provider_display_name=user_info.get("display_name")
                    or f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip(),
                )
                db.add(user_token)

            logger.info(f"Zoom OAuth successful (user-level) for app {oauth_app_id}, user {user_email}")
        else:
            # Store on a tenant-owned clone for platform apps to prevent cross-tenant leakage
            if oauth_app.is_platform_app:
                _tenant_id_str = state_data.get("tenant_id")
                if _tenant_id_str:
                    import uuid as _uuid
                    oauth_app = await _get_or_create_tenant_clone(db, oauth_app, _uuid.UUID(_tenant_id_str))
            oauth_app.access_token = encrypt_value(token_data["access_token"])
            if token_data.get("refresh_token"):
                oauth_app.refresh_token = encrypt_value(token_data["refresh_token"])
            oauth_app.token_expires_at = token_expires_at.replace(tzinfo=None) if token_expires_at else None
            logger.info(f"Zoom OAuth successful (app-level) for app {oauth_app_id}, user {user_email}")

        await db.commit()

        # SECURITY: Use safe redirect with URL-encoded parameters
        base_url = await get_app_base_url(db, oauth_app.tenant_id)
        return _safe_success_redirect(
            redirect_url=redirect_url,
            default_path="/oauth-apps",
            base_url=base_url,
            provider="zoom",
            email=user_email,
            user_level=str(user_level),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Zoom OAuth callback error: {e}", exc_info=True)
        # SECURITY: Get redirect URL from state and validate it
        error_state_data = get_oauth_state(state, delete=False) if state else None
        redirect_url = error_state_data.get("redirect_url") if error_state_data else None
        oauth_app_id = error_state_data.get("oauth_app_id") if error_state_data else None

        # Get base URL for validation
        base_url = "/"
        if oauth_app_id:
            oauth_app = await _get_oauth_app_secure(db, oauth_app_id)
            if oauth_app:
                base_url = await get_app_base_url(db, oauth_app.tenant_id)

        return _safe_error_redirect(redirect_url, "/oauth-apps", base_url, "zoom", e)
