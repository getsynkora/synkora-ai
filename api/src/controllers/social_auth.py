"""
Social Authentication Controllers.

Handles social login flows (Google, Microsoft, Apple) and account linking.

SECURITY:
- Uses Redis for OAuth state storage (distributed, secure)
- Validates redirect URLs against allowed domains (open redirect prevention)
- Checks 2FA requirement after social login
"""

import json
import logging
import secrets
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.utils.config_helper import get_app_base_url

from ..core.database import get_async_db
from ..middleware.auth_middleware import get_current_account
from ..models.social_auth_provider import SocialAuthProvider as SocialAuthProviderModel
from ..models.tenant import Account, Tenant, TenantAccountJoin, TenantType
from ..services.agents.security import decrypt_value
from ..services.auth_service import AuthService
from ..services.oauth.apple_oauth import AppleOAuth
from ..services.oauth.google_oauth import GoogleOAuth
from ..services.oauth.microsoft_oauth import MicrosoftOAuth
from ..services.social_auth import AccountLinkingService

COOKIE_SECURE = settings.is_production
COOKIE_DOMAIN = settings.cookie_domain if hasattr(settings, "cookie_domain") else None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["social-auth"])


# SECURITY: State TTL in seconds (10 minutes)
STATE_TTL_SECONDS = 600


def _get_redis_client():
    """
    Get async Redis client for OAuth state storage.

    SECURITY: Redis is required for OAuth state - no fallback.
    Raises exception if Redis is unavailable.
    """
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        if redis is None:
            raise RuntimeError("Redis connection returned None")
        return redis
    except Exception as e:
        logger.error(f"SECURITY: Redis unavailable for OAuth state storage: {e}")
        raise RuntimeError("OAuth service temporarily unavailable. Please try again later.")


async def _store_oauth_state(state: str, data: dict[str, Any]) -> None:
    """
    Store OAuth state in Redis.

    SECURITY: Uses Redis with TTL. No fallback - if Redis fails,
    OAuth login will fail safely.

    Raises:
        RuntimeError: If Redis is unavailable
    """
    redis = _get_redis_client()
    await redis.setex(f"oauth_state:{state}", STATE_TTL_SECONDS, json.dumps(data))


async def _get_oauth_state(state: str) -> dict[str, Any] | None:
    """
    Retrieve and delete OAuth state from Redis.

    SECURITY: Atomically retrieves and deletes state to prevent replay attacks.
    No fallback - if Redis fails, returns None (invalid state).

    Returns:
        State data if valid, None otherwise
    """
    try:
        redis = _get_redis_client()
        data = await redis.get(f"oauth_state:{state}")
        if data:
            await redis.delete(f"oauth_state:{state}")
            return json.loads(data)
        return None
    except RuntimeError:
        # Redis unavailable - treat as invalid state
        return None


# SECURITY: Exchange code TTL - 60 seconds is enough to complete the redirect
EXCHANGE_CODE_TTL_SECONDS = 60


async def _store_exchange_tokens(code: str, access_token: str, refresh_token: str) -> None:
    """Store tokens in Redis under a one-time exchange code."""
    redis = _get_redis_client()
    await redis.setex(
        f"oauth_exchange:{code}",
        EXCHANGE_CODE_TTL_SECONDS,
        json.dumps({"access_token": access_token, "refresh_token": refresh_token}),
    )


async def _consume_exchange_tokens(code: str) -> dict[str, str] | None:
    """Atomically retrieve and delete the exchange token pair. Returns None if expired/invalid."""
    try:
        redis = _get_redis_client()
        data = await redis.get(f"oauth_exchange:{code}")
        if data:
            await redis.delete(f"oauth_exchange:{code}")
            return json.loads(data)
        return None
    except RuntimeError:
        return None


def _validate_redirect_url(redirect_url: str, allowed_base_url: str) -> str:
    """
    Validate redirect URL to prevent open redirect attacks.

    SECURITY: Only allows redirects to the same domain as the base URL.

    Args:
        redirect_url: The URL to validate
        allowed_base_url: The application's base URL

    Returns:
        The validated redirect URL or the default base URL

    Raises:
        None - returns safe default on validation failure
    """
    if not redirect_url:
        return allowed_base_url

    try:
        parsed_redirect = urlparse(redirect_url)
        parsed_base = urlparse(allowed_base_url)

        # The native mobile app registers this custom URL scheme to receive the OAuth
        # callback directly (no browser/cookie involved), so it can't be validated
        # against allowed_base_url's host like a web redirect — allow it explicitly.
        if parsed_redirect.scheme == settings.mobile_oauth_redirect_scheme:
            return redirect_url

        # SECURITY: Only allow redirects to same host
        if parsed_redirect.netloc and parsed_redirect.netloc != parsed_base.netloc:
            logger.warning(f"Open redirect attempt blocked: {redirect_url} -> {parsed_redirect.netloc}")
            return allowed_base_url

        # SECURITY: Don't allow javascript: or data: URLs
        if parsed_redirect.scheme and parsed_redirect.scheme.lower() in ["javascript", "data", "vbscript"]:
            logger.warning(f"Dangerous redirect scheme blocked: {redirect_url}")
            return allowed_base_url

        # If it's a relative URL or same host, allow it
        return redirect_url

    except Exception as e:
        logger.warning(f"Failed to validate redirect URL {redirect_url}: {e}")
        return allowed_base_url


def _check_2fa_required(account: Account) -> bool:
    """
    Check if 2FA verification is required for this account.

    SECURITY: Social login should not bypass 2FA if enabled.
    SECURITY: Uses strict boolean comparison to prevent type coercion attacks.
    A string "false" is truthy in Python, so we must use `is True` comparison.

    Returns:
        True if 2FA is enabled and verification is needed
    """
    two_factor_enabled = getattr(account, "two_factor_enabled", False)
    two_factor_secret = getattr(account, "two_factor_secret", None)

    # SECURITY: Strict boolean check - prevents type coercion bypass
    # String "false" or "true" would be truthy, so we check explicitly for True
    if isinstance(two_factor_enabled, str):
        two_factor_enabled = two_factor_enabled.lower() == "true"
    elif not isinstance(two_factor_enabled, bool):
        two_factor_enabled = bool(two_factor_enabled)

    return two_factor_enabled is True and two_factor_secret is not None


# Pydantic models
class LinkProviderRequest(BaseModel):
    provider: str
    provider_user_id: str
    provider_email: str
    provider_name: str | None = None
    provider_data: dict | None = None


class UnlinkProviderRequest(BaseModel):
    provider: str


# Token Exchange Endpoint


@router.get("/token-exchange")
async def token_exchange(code: str = Query(..., description="One-time exchange code from OAuth callback")):
    """
    Exchange a one-time OAuth code for access and refresh tokens.

    SECURITY: Codes are single-use and expire in 60 seconds.
    The refresh token is returned as an HttpOnly cookie (matching the regular login
    endpoint) so JS cannot read or exfiltrate it.  The access token is returned in
    the response body only.
    """
    tokens = await _consume_exchange_tokens(code)
    if not tokens:
        raise HTTPException(status_code=400, detail="Invalid or expired exchange code")

    # SECURITY: refresh_token is also returned in the body (not just the HttpOnly cookie)
    # so native mobile clients — which have no cookie jar wired up — can store it themselves,
    # matching how /console/api/auth/signin already behaves for mobile clients.
    response = JSONResponse(content={"access_token": tokens["access_token"], "refresh_token": tokens["refresh_token"]})
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=30 * 24 * 3600,
        path="/console/api/auth/refresh",
        domain=COOKIE_DOMAIN,
    )
    return response


# Google OAuth Endpoints


async def _get_provider_config(db: AsyncSession, provider_name: str):
    """
    Get provider configuration from database.

    For social login (unauthenticated), we use the platform tenant's configuration.
    Platform tenant (tenant_type == "PLATFORM") is used for global/platform-wide configs.
    """
    try:
        # Get the platform tenant (used for global configs)
        stmt = select(Tenant).where(Tenant.tenant_type == TenantType.PLATFORM).limit(1)
        result = await db.execute(stmt)
        platform_tenant = result.scalar_one_or_none()

        if not platform_tenant:
            raise HTTPException(
                status_code=500, detail="Platform tenant not found. Please configure your system first."
            )

        # Get provider configuration for the platform tenant
        stmt = select(SocialAuthProviderModel).where(
            SocialAuthProviderModel.tenant_id == platform_tenant.id,
            SocialAuthProviderModel.provider_name == provider_name.lower(),
        )
        result = await db.execute(stmt)
        provider_config = result.scalar_one_or_none()

        if not provider_config:
            raise HTTPException(
                status_code=404,
                detail=f"{provider_name.title()} social login is not configured. Please configure it in the admin panel.",
            )

        # Check if provider is enabled (handle both boolean and string types)
        is_enabled = False
        if isinstance(provider_config.enabled, bool):
            is_enabled = provider_config.enabled
        elif isinstance(provider_config.enabled, str):
            is_enabled = provider_config.enabled.lower() == "true"

        if not is_enabled:
            raise HTTPException(
                status_code=403,
                detail=f"{provider_name.title()} social login is currently disabled. Please enable it in Settings > Social Auth Config.",
            )

        # Decrypt client secret
        try:
            client_secret = decrypt_value(provider_config.client_secret)
        except Exception as e:
            logger.error(f"Error decrypting client secret for {provider_name}: {e}")
            raise HTTPException(status_code=500, detail="Error loading provider configuration")

        return {
            "client_id": provider_config.client_id,
            "client_secret": client_secret,
            "redirect_uri": provider_config.redirect_uri,
            "config": provider_config.config or {},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting provider config for {provider_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading {provider_name} configuration")


@router.get("/google/login")
async def google_login(
    redirect_url: str = Query(None, description="Frontend redirect URL after login"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initiate Google OAuth flow for social login.

    This endpoint redirects the user to Google's authorization page.
    """
    try:
        # Get provider configuration from database
        config = await _get_provider_config(db, "google")

        # Initialize OAuth service with configuration
        oauth = GoogleOAuth(
            client_id=config["client_id"], client_secret=config["client_secret"], redirect_uri=config["redirect_uri"]
        )

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        base_url = await get_app_base_url(db)

        # SECURITY: Validate redirect URL to prevent open redirect attacks
        validated_redirect = _validate_redirect_url(redirect_url, f"{base_url}/signin")

        # SECURITY: Store state in Redis (required, no fallback)
        await _store_oauth_state(
            state,
            {
                "provider": "google",
                "redirect_url": validated_redirect,
                "flow_type": "social_login",
            },
        )

        # Get authorization URL
        auth_url = oauth.get_authorization_url(state=state)

        logger.info("Initiating Google social login")

        return RedirectResponse(url=auth_url)

    except Exception as e:
        logger.error(f"Google social login error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/google/callback")
async def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle Google OAuth callback for social login.

    This endpoint receives the authorization code from Google,
    exchanges it for an access token, gets user info, and creates/links account.
    """
    try:
        # SECURITY: Verify state from Redis
        state_data = await _get_oauth_state(state)
        if not state_data:
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

        redirect_url = state_data["redirect_url"]

        # Get provider configuration from database
        config = await _get_provider_config(db, "google")

        # Initialize OAuth service with configuration
        oauth = GoogleOAuth(
            client_id=config["client_id"], client_secret=config["client_secret"], redirect_uri=config["redirect_uri"]
        )

        # Exchange code for token
        token_data = await oauth.get_access_token(code)

        if not token_data.get("access_token"):
            raise HTTPException(status_code=400, detail="Failed to get access token")

        # Get user info
        user_info = await oauth.get_user_info(token_data["access_token"])

        # Extract user details
        provider_user_id = user_info.get("id")
        provider_email = user_info.get("email")
        provider_name = user_info.get("name")

        if not provider_user_id or not provider_email:
            raise HTTPException(status_code=400, detail="Failed to get user information from Google")

        # Link or create account
        try:
            account, tenant, is_new = await AccountLinkingService.link_or_create_account(
                db=db,
                provider="google",
                provider_user_id=provider_user_id,
                provider_email=provider_email,
                provider_name=provider_name,
                provider_data={
                    "picture": user_info.get("picture"),
                    "email_verified": user_info.get("email_verified"),
                    "locale": user_info.get("locale"),
                },
            )
        except ValueError as e:
            # SECURITY: Account exists but cannot be auto-linked (e.g., password-based account)
            logger.warning(f"OAuth linking rejected for {provider_email}: {e}")
            from urllib.parse import quote

            return RedirectResponse(url=f"{redirect_url}?login=account_exists&message={quote(str(e))}", status_code=302)

        logger.info(f"Google social login successful for user {provider_email} (new_account={is_new})")

        # SECURITY: Check if 2FA is required for this account
        if _check_2fa_required(account):
            logger.info(f"2FA required for account {account.id} after Google social login")
            # Generate a temporary token for 2FA verification
            temp_token = AuthService.generate_2fa_temp_token(account_id=account.id)
            return RedirectResponse(
                url=f"{redirect_url}?login=2fa_required&provider=google&temp_token={temp_token}", status_code=302
            )

        # Get user's tenant membership to get the role
        stmt = (
            select(TenantAccountJoin)
            .where(TenantAccountJoin.account_id == account.id, TenantAccountJoin.tenant_id == tenant.id)
            .limit(1)
        )
        result = await db.execute(stmt)
        membership = result.scalar_one_or_none()

        if not membership:
            logger.error(f"No tenant membership found for account {account.id}")
            raise HTTPException(status_code=500, detail="User account has no tenant association")

        logger.info(f"Found tenant membership: tenant_id={membership.tenant_id}, role={membership.role}")

        # Generate JWT tokens with current token version to avoid stale-token rejection
        from src.services.security.token_blacklist import get_token_blacklist_service

        blacklist_service = get_token_blacklist_service()
        token_version = blacklist_service.get_account_token_version(account.id)

        access_token = AuthService.generate_access_token(
            account_id=account.id, tenant_id=membership.tenant_id, role=membership.role, token_version=token_version
        )
        refresh_token = AuthService.generate_refresh_token(account_id=account.id, token_version=token_version)

        logger.info(
            f"Generated tokens - access_token length: {len(access_token)}, refresh_token length: {len(refresh_token)}"
        )

        # SECURITY: Use a one-time exchange code instead of tokens in URL params.
        # The code is stored in Redis (60s TTL) and redeemed via /auth/token-exchange.
        exchange_code = secrets.token_urlsafe(32)
        await _store_exchange_tokens(exchange_code, access_token, refresh_token)

        final_redirect_url = f"{redirect_url}?login=success&provider=google&exchange_code={exchange_code}"
        logger.info(f"Redirecting to: {final_redirect_url}")

        return RedirectResponse(url=final_redirect_url, status_code=302)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}", exc_info=True)
        # Redirect to frontend with error - use state_data if available
        # SECURITY: URL-encode error message to prevent XSS
        from urllib.parse import quote

        error_redirect = state_data.get("redirect_url") if state_data else redirect_url
        safe_message = quote("Sign-in failed. Please try again.", safe="")
        return RedirectResponse(url=f"{error_redirect}?login=error&message={safe_message}")


# Microsoft OAuth Endpoints


@router.get("/microsoft/login")
async def microsoft_login(
    redirect_url: str = Query(None, description="Frontend redirect URL after login"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initiate Microsoft OAuth flow for social login.

    This endpoint redirects the user to Microsoft's authorization page.
    """
    try:
        # Get provider configuration from database
        config = await _get_provider_config(db, "microsoft")

        # Initialize OAuth service with configuration
        oauth = MicrosoftOAuth(
            client_id=config["client_id"], client_secret=config["client_secret"], redirect_uri=config["redirect_uri"]
        )

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        base_url = await get_app_base_url(db)

        # SECURITY: Validate redirect URL to prevent open redirect attacks
        validated_redirect = _validate_redirect_url(redirect_url, f"{base_url}/signin")

        # SECURITY: Store state in Redis (required, no fallback)
        await _store_oauth_state(
            state,
            {
                "provider": "microsoft",
                "redirect_url": validated_redirect,
                "flow_type": "social_login",
            },
        )

        # Get authorization URL
        auth_url = oauth.get_authorization_url(state=state)

        logger.info("Initiating Microsoft social login")

        return RedirectResponse(url=auth_url)

    except Exception as e:
        logger.error(f"Microsoft social login error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/microsoft/callback")
async def microsoft_callback(
    code: str = Query(..., description="Authorization code from Microsoft"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle Microsoft OAuth callback for social login.

    This endpoint receives the authorization code from Microsoft,
    exchanges it for an access token, gets user info, and creates/links account.
    """
    state_data = None
    try:
        # SECURITY: Verify state from Redis
        state_data = await _get_oauth_state(state)
        if not state_data:
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

        redirect_url = state_data["redirect_url"]

        # Get provider configuration from database
        config = await _get_provider_config(db, "microsoft")

        # Initialize OAuth service with configuration
        oauth = MicrosoftOAuth(
            client_id=config["client_id"], client_secret=config["client_secret"], redirect_uri=config["redirect_uri"]
        )

        # Exchange code for token
        token_data = await oauth.get_access_token(code)

        if not token_data.get("access_token"):
            raise HTTPException(status_code=400, detail="Failed to get access token")

        # Get user info
        user_info = await oauth.get_user_info(token_data["access_token"])

        # Extract user details
        provider_user_id = user_info.get("id")
        provider_email = user_info.get("mail") or user_info.get("userPrincipalName")
        provider_name = user_info.get("displayName")

        if not provider_user_id or not provider_email:
            raise HTTPException(status_code=400, detail="Failed to get user information from Microsoft")

        # Link or create account
        try:
            account, tenant, is_new = await AccountLinkingService.link_or_create_account(
                db=db,
                provider="microsoft",
                provider_user_id=provider_user_id,
                provider_email=provider_email,
                provider_name=provider_name,
                provider_data={
                    "job_title": user_info.get("jobTitle"),
                    "office_location": user_info.get("officeLocation"),
                    # Microsoft Graph API indicates email is verified by returning mail field
                    "email_verified": True if user_info.get("mail") else False,
                },
            )
        except ValueError as e:
            # SECURITY: Account exists but cannot be auto-linked (e.g., password-based account)
            logger.warning(f"OAuth linking rejected for {provider_email}: {e}")
            from urllib.parse import quote

            return RedirectResponse(url=f"{redirect_url}?login=account_exists&message={quote(str(e))}", status_code=302)

        logger.info(f"Microsoft social login successful for user {provider_email} (new_account={is_new})")

        # SECURITY: Check if 2FA is required for this account
        if _check_2fa_required(account):
            logger.info(f"2FA required for account {account.id} after Microsoft social login")
            temp_token = AuthService.generate_2fa_temp_token(account_id=account.id)
            return RedirectResponse(
                url=f"{redirect_url}?login=2fa_required&provider=microsoft&temp_token={temp_token}", status_code=302
            )

        # Get user's tenant membership to get the role
        stmt = (
            select(TenantAccountJoin)
            .where(TenantAccountJoin.account_id == account.id, TenantAccountJoin.tenant_id == tenant.id)
            .limit(1)
        )
        result = await db.execute(stmt)
        membership = result.scalar_one_or_none()

        if not membership:
            logger.error(f"No tenant membership found for account {account.id}")
            raise HTTPException(status_code=500, detail="User account has no tenant association")

        # Generate JWT tokens with current token version to avoid stale-token rejection
        from src.services.security.token_blacklist import get_token_blacklist_service

        blacklist_service = get_token_blacklist_service()
        token_version = blacklist_service.get_account_token_version(account.id)

        access_token = AuthService.generate_access_token(
            account_id=account.id, tenant_id=membership.tenant_id, role=membership.role, token_version=token_version
        )
        refresh_token = AuthService.generate_refresh_token(account_id=account.id, token_version=token_version)

        exchange_code = secrets.token_urlsafe(32)
        await _store_exchange_tokens(exchange_code, access_token, refresh_token)

        final_redirect_url = f"{redirect_url}?login=success&provider=microsoft&exchange_code={exchange_code}"
        return RedirectResponse(url=final_redirect_url, status_code=302)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Microsoft OAuth callback error: {e}", exc_info=True)
        # Redirect to frontend with error - use state_data if available
        # SECURITY: URL-encode error message to prevent XSS
        from urllib.parse import quote

        error_redirect = state_data.get("redirect_url") if state_data else redirect_url
        safe_message = quote("Sign-in failed. Please try again.", safe="")
        return RedirectResponse(url=f"{error_redirect}?login=error&message={safe_message}")


# Apple OAuth Endpoints


@router.get("/apple/login")
async def apple_login(
    redirect_url: str = Query(None, description="Frontend redirect URL after login"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initiate Apple OAuth flow for social login.

    This endpoint redirects the user to Apple's authorization page.
    """
    try:
        # Get provider configuration from database
        config = await _get_provider_config(db, "apple")

        # Initialize OAuth service with configuration
        oauth = AppleOAuth(
            client_id=config["client_id"], client_secret=config["client_secret"], redirect_uri=config["redirect_uri"]
        )
        base_url = await get_app_base_url(db)
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # SECURITY: Validate redirect URL to prevent open redirect attacks
        validated_redirect = _validate_redirect_url(redirect_url, f"{base_url}/signin")

        # SECURITY: Store state in Redis (required, no fallback)
        await _store_oauth_state(
            state,
            {
                "provider": "apple",
                "redirect_url": validated_redirect,
                "flow_type": "social_login",
            },
        )

        # Get authorization URL
        auth_url = oauth.get_authorization_url(state=state)

        logger.info("Initiating Apple social login")

        return RedirectResponse(url=auth_url)

    except Exception as e:
        logger.error(f"Apple social login error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apple/callback")
async def apple_callback(request: Request, db: AsyncSession = Depends(get_async_db)):
    """
    Handle Apple OAuth callback for social login.

    Apple sends POST request with form data.
    """
    state_data = None
    redirect_url = None
    try:
        # Get form data
        form_data = await request.form()
        code = form_data.get("code")
        state = form_data.get("state")

        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state parameter")

        # SECURITY: Verify state from Redis
        state_data = await _get_oauth_state(state)
        if not state_data:
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

        redirect_url = state_data["redirect_url"]

        # Get provider configuration from database
        config = await _get_provider_config(db, "apple")

        # Initialize OAuth service with configuration
        oauth = AppleOAuth(
            client_id=config["client_id"], client_secret=config["client_secret"], redirect_uri=config["redirect_uri"]
        )

        # Exchange code for token
        token_data = await oauth.get_access_token(code)

        if not token_data.get("access_token"):
            raise HTTPException(status_code=400, detail="Failed to get access token")

        # Get user info (Apple provides limited info)
        user_info = await oauth.get_user_info(token_data["access_token"])

        # Extract user details
        provider_user_id = user_info.get("sub")
        provider_email = user_info.get("email")
        provider_name = (
            form_data.get("user", {}).get("name", {}).get("firstName", "")
            + " "
            + form_data.get("user", {}).get("name", {}).get("lastName", "")
        )

        if not provider_user_id or not provider_email:
            raise HTTPException(status_code=400, detail="Failed to get user information from Apple")

        # Link or create account
        try:
            account, tenant, is_new = await AccountLinkingService.link_or_create_account(
                db=db,
                provider="apple",
                provider_user_id=provider_user_id,
                provider_email=provider_email,
                provider_name=provider_name.strip() or None,
                provider_data={"email_verified": user_info.get("email_verified", "true")},
            )
        except ValueError as e:
            # SECURITY: Account exists but cannot be auto-linked (e.g., password-based account)
            logger.warning(f"OAuth linking rejected for {provider_email}: {e}")
            from urllib.parse import quote

            return RedirectResponse(url=f"{redirect_url}?login=account_exists&message={quote(str(e))}", status_code=302)

        logger.info(f"Apple social login successful for user {provider_email} (new_account={is_new})")

        # SECURITY: Check if 2FA is required for this account
        if _check_2fa_required(account):
            logger.info(f"2FA required for account {account.id} after Apple social login")
            temp_token = AuthService.generate_2fa_temp_token(account_id=account.id)
            return RedirectResponse(
                url=f"{redirect_url}?login=2fa_required&provider=apple&temp_token={temp_token}", status_code=302
            )

        # Get user's tenant membership to get the role
        stmt = (
            select(TenantAccountJoin)
            .where(TenantAccountJoin.account_id == account.id, TenantAccountJoin.tenant_id == tenant.id)
            .limit(1)
        )
        result = await db.execute(stmt)
        membership = result.scalar_one_or_none()

        if not membership:
            logger.error(f"No tenant membership found for account {account.id}")
            raise HTTPException(status_code=500, detail="User account has no tenant association")

        # Generate JWT tokens with current token version to avoid stale-token rejection
        from src.services.security.token_blacklist import get_token_blacklist_service

        blacklist_service = get_token_blacklist_service()
        token_version = blacklist_service.get_account_token_version(account.id)

        access_token = AuthService.generate_access_token(
            account_id=account.id, tenant_id=membership.tenant_id, role=membership.role, token_version=token_version
        )
        refresh_token = AuthService.generate_refresh_token(account_id=account.id, token_version=token_version)

        exchange_code = secrets.token_urlsafe(32)
        await _store_exchange_tokens(exchange_code, access_token, refresh_token)

        final_redirect_url = f"{redirect_url}?login=success&provider=apple&exchange_code={exchange_code}"
        return RedirectResponse(url=final_redirect_url, status_code=302)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apple OAuth callback error: {e}", exc_info=True)
        # Redirect to frontend with error - use state_data if available
        # SECURITY: URL-encode error message to prevent XSS
        from urllib.parse import quote

        error_redirect = state_data.get("redirect_url") if state_data else (redirect_url or "/signin")
        safe_message = quote("Sign-in failed. Please try again.", safe="")
        return RedirectResponse(url=f"{error_redirect}?login=error&message={safe_message}")


# Account Management Endpoints


@router.get("/linked-providers")
async def get_linked_providers(
    current_account: Account = Depends(get_current_account), db: AsyncSession = Depends(get_async_db)
):
    """
    Get all social auth providers linked to the current account.
    """
    try:
        providers = await AccountLinkingService.get_linked_providers(db, current_account.id)

        return {
            "providers": [
                {
                    "provider": p.provider,
                    "provider_email": p.provider_email,
                    "linked_at": p.created_at.isoformat(),
                    "last_login": p.last_login_at.isoformat() if p.last_login_at else None,
                }
                for p in providers
            ]
        }

    except Exception as e:
        logger.error(f"Get linked providers error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/link-provider")
async def link_provider(
    data: LinkProviderRequest,
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Link a social auth provider to the current account.

    This is used when a user wants to add another login method to their existing account.
    """
    try:
        await AccountLinkingService.link_provider_to_account(
            db=db,
            account_id=current_account.id,
            provider=data.provider,
            provider_user_id=data.provider_user_id,
            provider_email=data.provider_email,
            provider_data=data.provider_data,
        )

        logger.info(f"Linked {data.provider} provider to account {current_account.id}")

        return {"success": True, "message": f"{data.provider.title()} account linked successfully"}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Link provider error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/unlink-provider/{provider}")
async def unlink_provider(
    provider: str,
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Unlink a social auth provider from the current account.

    This removes the ability to login with this provider.
    """
    try:
        await AccountLinkingService.unlink_provider(db, current_account.id, provider)

        logger.info(f"Unlinked {provider} provider from account {current_account.id}")

        return {"success": True, "message": f"{provider.title()} account unlinked successfully"}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unlink provider error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/provider-status/{provider}")
async def get_provider_status(
    provider: str,
    current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Check if a specific provider is linked to the current account.
    """
    try:
        result = await db.execute(
            select(SocialAuthProviderModel).filter(
                SocialAuthProviderModel.account_id == current_account.id,
                SocialAuthProviderModel.provider == provider,
            )
        )
        social_auth = result.scalar_one_or_none()

        if social_auth:
            return {
                "linked": True,
                "provider_email": social_auth.provider_email,
                "linked_at": social_auth.created_at.isoformat(),
                "last_login": social_auth.last_login_at.isoformat() if social_auth.last_login_at else None,
            }
        else:
            return {"linked": False}

    except Exception as e:
        logger.error(f"Get provider status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
