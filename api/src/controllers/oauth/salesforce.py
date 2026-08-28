"""
Salesforce OAuth Controller.

Handles Salesforce OAuth 2.0 authorization and callback.
The instance_url returned in the token response is stored in OAuthApp.config
so the credential resolver can build correct API URLs per tenant.

Supports production (login.salesforce.com) and sandbox (test.salesforce.com)
via config.is_sandbox = true.
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
from ...services.oauth.salesforce_oauth import SalesforceOAuth
from ...services.security.oauth_state_service import create_oauth_state, get_oauth_state
from .base import (
    _get_oauth_app_secure,
    _safe_error_redirect,
    _safe_success_redirect,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/salesforce/authorize")
async def salesforce_authorize(
    oauth_app_id: int = Query(...),
    redirect_url: str = Query(None),
    user_level: bool = Query(False),
    current_account: Account | None = Depends(get_optional_account),
    tenant_id: uuid.UUID | None = Depends(get_optional_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Initiate Salesforce OAuth authorization."""
    try:
        if user_level and not current_account:
            raise HTTPException(status_code=401, detail="Authentication required for user-level OAuth")

        oauth_app = await _get_oauth_app_secure(db, oauth_app_id, tenant_id=tenant_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        base_url = await get_app_base_url(db, oauth_app.tenant_id)
        redirect_url = redirect_url or f"{base_url}/oauth-apps"

        config = oauth_app.config or {}
        is_sandbox = bool(config.get("is_sandbox", False))

        client_id = oauth_app.client_id
        try:
            client_secret = decrypt_value(oauth_app.client_secret)
        except Exception as e:
            logger.error("Failed to decrypt Salesforce client secret: %s", e)
            raise HTTPException(status_code=500, detail="Failed to decrypt OAuth credentials")

        state = create_oauth_state(
            {
                "oauth_app_id": oauth_app_id,
                "redirect_url": redirect_url,
                "user_level": user_level,
                "is_sandbox": is_sandbox,
                "account_id": str(current_account.id) if current_account and user_level else None,
            }
        )
        if not state:
            raise HTTPException(status_code=500, detail="Failed to create OAuth state")

        oauth = SalesforceOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=oauth_app.redirect_uri,
            is_sandbox=is_sandbox,
        )
        auth_url = oauth.get_authorization_url(state=state, scopes=oauth_app.scopes or None)

        logger.info(
            "Initiating Salesforce OAuth for app %s (user_level=%s, sandbox=%s)",
            oauth_app_id,
            user_level,
            is_sandbox,
        )
        return RedirectResponse(url=auth_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Salesforce OAuth authorization error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/salesforce/callback")
async def salesforce_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_async_db),
):
    """Handle Salesforce OAuth callback and store token + instance_url."""
    try:
        state_data = get_oauth_state(state)
        if state_data is None:
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

        oauth_app_id = state_data["oauth_app_id"]
        redirect_url = state_data["redirect_url"]
        user_level = state_data.get("user_level", False)
        account_id = state_data.get("account_id")
        is_sandbox = state_data.get("is_sandbox", False)

        oauth_app = await _get_oauth_app_secure(db, oauth_app_id)
        if not oauth_app:
            raise HTTPException(status_code=404, detail="OAuth app not found")

        client_id = oauth_app.client_id
        client_secret = decrypt_value(oauth_app.client_secret)

        oauth = SalesforceOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=oauth_app.redirect_uri,
            is_sandbox=is_sandbox,
        )

        token_data = await oauth.get_access_token(code)
        if not token_data or not token_data.get("access_token"):
            raise HTTPException(status_code=400, detail="Failed to get access token")

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        instance_url = token_data.get("instance_url", "")
        expires_in = token_data.get("expires_in")
        token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in) if expires_in else None

        # Persist the instance_url in config — required for all API calls
        config = oauth_app.config or {}
        config["instance_url"] = instance_url
        config["is_sandbox"] = is_sandbox
        oauth_app.config = config

        user_info = await oauth.get_user_info(access_token, instance_url=instance_url)
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
            logger.info(
                "Salesforce OAuth successful (user-level) for app %s, user %s, instance %s",
                oauth_app_id,
                user_email,
                instance_url,
            )
        else:
            oauth_app.access_token = encrypt_value(access_token)
            if refresh_token:
                oauth_app.refresh_token = encrypt_value(refresh_token)
            oauth_app.token_expires_at = token_expires_at
            logger.info(
                "Salesforce OAuth successful (app-level) for app %s, user %s, instance %s",
                oauth_app_id,
                user_email,
                instance_url,
            )

        await db.commit()

        base_url = await get_app_base_url(db, oauth_app.tenant_id)
        return _safe_success_redirect(
            redirect_url=redirect_url,
            default_path="/oauth-apps",
            base_url=base_url,
            provider="salesforce",
            email=user_email,
            user_level=str(user_level),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Salesforce OAuth callback error: %s", e, exc_info=True)
        error_state_data = get_oauth_state(state, delete=False) if state else None
        redirect_url = error_state_data.get("redirect_url") if error_state_data else None
        oauth_app_id = error_state_data.get("oauth_app_id") if error_state_data else None
        base_url = "/"
        if oauth_app_id:
            oauth_app = await _get_oauth_app_secure(db, oauth_app_id)
            if oauth_app:
                base_url = await get_app_base_url(db, oauth_app.tenant_id)
        return _safe_error_redirect(redirect_url, "/oauth-apps", base_url, "salesforce", e)
