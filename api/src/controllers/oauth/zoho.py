"""
Zoho CRM OAuth Controller.

Handles Zoho CRM OAuth 2.0 authorization and callback.
Requires 'data_center' in the OAuthApp.config field (default: 'com').
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
from ...services.oauth.zoho_crm_oauth import ZohoCRMOAuth
from ...services.security.oauth_state_service import create_oauth_state, get_oauth_state
from .base import (
    _get_oauth_app_secure,
    _get_or_create_tenant_clone,
    _safe_error_redirect,
    _safe_success_redirect,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/zoho/authorize")
async def zoho_authorize(
    oauth_app_id: int = Query(...),
    redirect_url: str = Query(None),
    user_level: bool = Query(False),
    current_account: Account | None = Depends(get_optional_account),
    tenant_id: uuid.UUID | None = Depends(get_optional_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Initiate Zoho CRM OAuth authorization."""
    try:
        if user_level and not current_account:
            raise HTTPException(status_code=401, detail="Authentication required for user-level OAuth")

        oauth_app = await _get_oauth_app_secure(db, oauth_app_id, tenant_id=tenant_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        base_url = await get_app_base_url(db, oauth_app.tenant_id)
        redirect_url = redirect_url or f"{base_url}/oauth-apps"

        data_center = (oauth_app.config or {}).get("data_center", "com").strip() or "com"

        client_id = oauth_app.client_id
        try:
            client_secret = decrypt_value(oauth_app.client_secret)
        except Exception as e:
            logger.error("Failed to decrypt Zoho CRM client secret: %s", e)
            raise HTTPException(status_code=500, detail="Failed to decrypt OAuth credentials")

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

        oauth = ZohoCRMOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=oauth_app.redirect_uri,
            data_center=data_center,
        )
        scopes = oauth_app.scopes or [
            "ZohoCRM.modules.ALL",
            "ZohoCRM.settings.ALL",
            "ZohoCRM.users.READ",
            "ZohoCRM.org.READ",
            "offline_access",
        ]
        auth_url = oauth.get_authorization_url(state=state, scopes=scopes)

        logger.info("Initiating Zoho CRM OAuth for app %s (user_level=%s)", oauth_app_id, user_level)
        return RedirectResponse(url=auth_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Zoho CRM OAuth authorization error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/zoho/callback")
async def zoho_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_async_db),
):
    """Handle Zoho CRM OAuth callback and store token."""
    try:
        state_data = get_oauth_state(state)
        if state_data is None:
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

        oauth_app_id = state_data["oauth_app_id"]
        redirect_url = state_data["redirect_url"]
        user_level = state_data.get("user_level", False)
        account_id = state_data.get("account_id")

        oauth_app = await _get_oauth_app_secure(db, oauth_app_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        data_center = (oauth_app.config or {}).get("data_center", "com").strip() or "com"

        client_id = oauth_app.client_id
        client_secret = decrypt_value(oauth_app.client_secret)

        oauth = ZohoCRMOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=oauth_app.redirect_uri,
            data_center=data_center,
        )

        token_data = await oauth.get_access_token(code)
        if not token_data or not token_data.get("access_token"):
            raise HTTPException(status_code=400, detail="Failed to get access token")

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")
        token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in else None

        user_info = await oauth.get_user_info(access_token)
        user_email = user_info.get("email", "")

        if user_level and account_id:
            result = await db.execute(
                select(UserOAuthToken).filter(
                    UserOAuthToken.account_id == uuid.UUID(account_id),
                    UserOAuthToken.oauth_app_id == oauth_app_id,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                # UserOAuthToken.access_token/.refresh_token are auto-encrypting
                # properties — assigning an already-encrypted value here would
                # double-encrypt it, producing a token that never decrypts back
                # to something usable.
                existing.access_token = access_token
                if refresh_token:
                    existing.refresh_token = refresh_token
                existing.token_expires_at = token_expires_at
                existing.provider_user_id = user_info.get("id")
                existing.provider_email = user_email
                existing.provider_display_name = user_info.get("name")
            else:
                db.add(
                    UserOAuthToken(
                        account_id=uuid.UUID(account_id),
                        oauth_app_id=oauth_app_id,
                        # See comment above — these properties encrypt on assignment.
                        access_token=access_token,
                        refresh_token=refresh_token,
                        token_expires_at=token_expires_at,
                        provider_user_id=user_info.get("id"),
                        provider_email=user_email,
                        provider_display_name=user_info.get("name"),
                    )
                )
            logger.info("Zoho CRM OAuth successful (user-level) for app %s, user %s", oauth_app_id, user_email)
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
            oauth_app.token_expires_at = token_expires_at
            logger.info("Zoho CRM OAuth successful (app-level) for app %s, user %s", oauth_app_id, user_email)

        await db.commit()

        base_url = await get_app_base_url(db, oauth_app.tenant_id)
        return _safe_success_redirect(
            redirect_url=redirect_url,
            default_path="/oauth-apps",
            base_url=base_url,
            provider="zoho_crm",
            email=user_email,
            user_level=str(user_level),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Zoho CRM OAuth callback error: %s", e, exc_info=True)
        error_state_data = get_oauth_state(state, delete=False) if state else None
        redirect_url = error_state_data.get("redirect_url") if error_state_data else None
        oauth_app_id = error_state_data.get("oauth_app_id") if error_state_data else None
        base_url = "/"
        if oauth_app_id:
            oauth_app = await _get_oauth_app_secure(db, oauth_app_id)
            if oauth_app:
                base_url = await get_app_base_url(db, oauth_app.tenant_id)
        return _safe_error_redirect(redirect_url, "/oauth-apps", base_url, "zoho_crm", e)
