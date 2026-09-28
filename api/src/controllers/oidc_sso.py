"""
Generic OIDC SSO controller.

Authenticated admin endpoints:
  GET    /api/v1/sso/oidc/config   — read OIDC config for current tenant (ADMIN+)
  POST   /api/v1/sso/oidc/config   — create/update OIDC config (ADMIN+)
  DELETE /api/v1/sso/oidc/config   — delete OIDC config (OWNER only)

Public SSO flow endpoints:
  GET  /api/v1/sso/oidc/login      — initiate SSO redirect to IdP
  GET  /api/v1/sso/oidc/callback   — handle IdP callback and issue session
"""

from __future__ import annotations

import json
import logging
import secrets
import uuid
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel as PydanticModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id, require_role
from src.models import AccountRole
from src.models.oidc_config import OIDCConfig
from src.services.agents.security import decrypt_value, encrypt_value
from src.services.session_service import SessionService
from src.services.sso.oidc_sso import OIDCSSOService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sso/oidc", tags=["oidc-sso"])

# ---------------------------------------------------------------------------
# Cookie / session constants (mirror saml_sso.py)
# ---------------------------------------------------------------------------
try:
    from src.config import settings as _settings

    _COOKIE_SECURE = _settings.is_production
    _COOKIE_DOMAIN = _settings.cookie_domain if hasattr(_settings, "cookie_domain") else None
except Exception:
    _COOKIE_SECURE = False
    _COOKIE_DOMAIN = None

# ---------------------------------------------------------------------------
# Redis state helpers (mirrors okta_sso.py pattern)
# ---------------------------------------------------------------------------
_STATE_TTL = 600  # 10 minutes
_STATE_KEY_PREFIX = "oidc_sso_state:"


def _get_redis():
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        if redis is None:
            raise RuntimeError("Redis returned None")
        return redis
    except Exception as exc:
        logger.error("Redis unavailable for OIDC SSO state: %s", exc)
        raise RuntimeError("SSO service temporarily unavailable") from exc


async def _store_oidc_state(state: str, data: dict) -> None:
    await _get_redis().setex(f"{_STATE_KEY_PREFIX}{state}", _STATE_TTL, json.dumps(data))


async def _consume_oidc_state(state: str) -> dict | None:
    try:
        redis = _get_redis()
        raw = await redis.getdel(f"{_STATE_KEY_PREFIX}{state}")
        if raw:
            return json.loads(raw)
        return None
    except RuntimeError:
        return None


# ---------------------------------------------------------------------------
# Open-redirect guard (same pattern as okta_sso.py)
# ---------------------------------------------------------------------------


def _validate_redirect_url(url: str | None, base_url: str) -> str:
    if not url:
        return f"{base_url}/dashboard"
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        return f"{base_url}/dashboard"
    if (parsed.scheme, parsed.netloc) != (base_parsed.scheme, base_parsed.netloc):
        logger.warning("OIDC SSO: rejected open redirect attempt to: %s", url)
        return f"{base_url}/dashboard"
    return url


# ---------------------------------------------------------------------------
# Frontend base URL helper
# ---------------------------------------------------------------------------


def _get_frontend_base() -> str:
    try:
        from src.config import settings as app_settings

        return (app_settings.app_base_url or "http://localhost:3005").rstrip("/")
    except Exception:
        return "http://localhost:3005"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class OIDCConfigCreateRequest(PydanticModel):
    """Payload for creating or updating an OIDC config."""

    provider_name: str
    client_id: str
    client_secret: str
    discovery_url: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    userinfo_endpoint: str | None = None
    jwks_uri: str | None = None
    email_claim: str = "email"
    name_claim: str = "name"
    is_enabled: bool = True
    auto_provision: bool = True
    scopes: str = "openid email profile"


class OIDCConfigUpdateRequest(PydanticModel):
    """Payload for updating an OIDC config (all fields optional)."""

    provider_name: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    discovery_url: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    userinfo_endpoint: str | None = None
    jwks_uri: str | None = None
    email_claim: str | None = None
    name_claim: str | None = None
    is_enabled: bool | None = None
    auto_provision: bool | None = None
    scopes: str | None = None


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------


async def _get_oidc_config(db: AsyncSession, tenant_id: uuid.UUID) -> OIDCConfig | None:
    result = await db.execute(select(OIDCConfig).where(OIDCConfig.tenant_id == tenant_id))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------


def _serialize_config(cfg: OIDCConfig) -> dict:
    return {
        "id": str(cfg.id),
        "tenant_id": str(cfg.tenant_id),
        "provider_name": cfg.provider_name,
        "client_id": cfg.client_id,
        # Never expose client_secret — only signal whether one is stored
        "has_client_secret": bool(cfg.client_secret),
        "discovery_url": cfg.discovery_url,
        "authorization_endpoint": cfg.authorization_endpoint,
        "token_endpoint": cfg.token_endpoint,
        "userinfo_endpoint": cfg.userinfo_endpoint,
        "jwks_uri": cfg.jwks_uri,
        "email_claim": cfg.email_claim,
        "name_claim": cfg.name_claim,
        "is_enabled": cfg.is_enabled,
        "auto_provision": cfg.auto_provision,
        "scopes": cfg.scopes,
        "created_at": cfg.created_at.isoformat() if cfg.created_at else None,
        "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Authenticated: GET config
# ---------------------------------------------------------------------------


@router.get("/config", dependencies=[Depends(require_role(AccountRole.ADMIN))])
async def get_oidc_config(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Return the OIDC config for the calling account's tenant. Requires ADMIN or OWNER."""
    cfg = await _get_oidc_config(db, tenant_id)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No OIDC configuration found for this tenant",
        )
    return _serialize_config(cfg)


# ---------------------------------------------------------------------------
# Authenticated: POST config (create or update)
# ---------------------------------------------------------------------------


@router.post("/config", status_code=status.HTTP_200_OK, dependencies=[Depends(require_role(AccountRole.ADMIN))])
async def upsert_oidc_config(
    data: OIDCConfigCreateRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """
    Create or update the OIDC configuration for the calling account's tenant.

    Either discovery_url or all of authorization_endpoint + token_endpoint +
    userinfo_endpoint must be provided.
    """
    if not data.discovery_url and not (data.authorization_endpoint and data.token_endpoint and data.userinfo_endpoint):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Provide either discovery_url or all of: authorization_endpoint, token_endpoint, userinfo_endpoint"
            ),
        )

    if not data.client_secret.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A client_secret is required",
        )

    try:
        encrypted_secret = encrypt_value(data.client_secret)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encrypt client secret",
        ) from exc

    cfg = await _get_oidc_config(db, tenant_id)
    if cfg is None:
        cfg = OIDCConfig(tenant_id=tenant_id)
        db.add(cfg)

    cfg.provider_name = data.provider_name
    cfg.client_id = data.client_id
    cfg.client_secret = encrypted_secret
    cfg.discovery_url = data.discovery_url
    cfg.authorization_endpoint = data.authorization_endpoint
    cfg.token_endpoint = data.token_endpoint
    cfg.userinfo_endpoint = data.userinfo_endpoint
    cfg.jwks_uri = data.jwks_uri
    cfg.email_claim = data.email_claim
    cfg.name_claim = data.name_claim
    cfg.is_enabled = data.is_enabled
    cfg.auto_provision = data.auto_provision
    cfg.scopes = data.scopes

    await db.commit()
    await db.refresh(cfg)

    logger.info("OIDC config upserted for tenant %s (provider: %s)", tenant_id, cfg.provider_name)
    return _serialize_config(cfg)


# ---------------------------------------------------------------------------
# Authenticated: DELETE config (OWNER only)
# ---------------------------------------------------------------------------


@router.delete("/config", status_code=status.HTTP_200_OK, dependencies=[Depends(require_role(AccountRole.OWNER))])
async def delete_oidc_config(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Delete the OIDC configuration for the calling account's tenant. Requires OWNER."""
    cfg = await _get_oidc_config(db, tenant_id)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No OIDC configuration found for this tenant",
        )

    await db.delete(cfg)
    await db.commit()

    logger.info("OIDC config deleted for tenant %s", tenant_id)
    return {"success": True, "message": "OIDC configuration deleted"}


# ---------------------------------------------------------------------------
# Public: initiate SSO
# ---------------------------------------------------------------------------


@router.get("/login")
async def oidc_login(
    tenant_id: str = Query(..., description="Tenant ID for OIDC SSO"),
    redirect_url: str = Query(None, description="Frontend URL to redirect to after login"),
    db: AsyncSession = Depends(get_async_db),
) -> RedirectResponse:
    """
    Redirect the browser to the configured IdP authorization endpoint.

    Stores a CSRF state token in Redis keyed to the tenant, so the callback
    can verify the response belongs to this login attempt.
    """
    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant_id")

    cfg = await _get_oidc_config(db, tenant_uuid)
    if not cfg or not cfg.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OIDC SSO is not configured or not enabled for this tenant",
        )

    frontend_base = _get_frontend_base()
    safe_redirect = _validate_redirect_url(redirect_url, frontend_base)

    # The callback URI must match what's registered in the IdP
    from src.utils.config_helper import get_app_base_url

    api_base = await get_app_base_url(db, tenant_uuid)
    callback_uri = f"{api_base}/api/v1/sso/oidc/callback"

    state = secrets.token_urlsafe(32)
    await _store_oidc_state(state, {"tenant_id": tenant_id, "redirect_url": safe_redirect})

    svc = OIDCSSOService(cfg)
    try:
        auth_url = await svc.get_authorization_url(redirect_uri=callback_uri, state=state)
    except Exception as exc:
        logger.error("OIDC SSO login: failed to build authorization URL for tenant %s: %s", tenant_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate SSO login",
        ) from exc

    logger.info("OIDC SSO: initiating login for tenant %s", tenant_id)
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


# ---------------------------------------------------------------------------
# Public: callback
# ---------------------------------------------------------------------------


@router.get("/callback")
async def oidc_callback(
    code: str = Query(..., description="Authorization code from IdP"),
    state: str = Query(..., description="CSRF state token"),
    db: AsyncSession = Depends(get_async_db),
) -> RedirectResponse:
    """
    Handle the IdP callback after a successful user authentication.

    1. Validates the state token (CSRF protection).
    2. Exchanges the code for tokens.
    3. Fetches userinfo from the IdP.
    4. JIT-provisions the account if needed.
    5. Creates a session and sets the refresh-token cookie.
    6. Redirects to the frontend with the access token in the URL fragment.
    """
    state_data = await _consume_oidc_state(state)
    frontend_base = _get_frontend_base()

    try:
        if not state_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired SSO state parameter",
            )

        tenant_uuid = uuid.UUID(state_data["tenant_id"])
        redirect_url = state_data["redirect_url"]

        cfg = await _get_oidc_config(db, tenant_uuid)
        if not cfg or not cfg.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="OIDC SSO is not configured or not enabled for this tenant",
            )

        from src.utils.config_helper import get_app_base_url

        api_base = await get_app_base_url(db, tenant_uuid)
        callback_uri = f"{api_base}/api/v1/sso/oidc/callback"

        svc = OIDCSSOService(cfg)

        # 1. Exchange code for tokens
        try:
            token_data = await svc.exchange_code(code=code, redirect_uri=callback_uri)
        except Exception as exc:
            logger.warning("OIDC callback: token exchange failed for tenant %s: %s", tenant_uuid, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token exchange with IdP failed",
            ) from exc

        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IdP did not return an access token",
            )

        # 2. Fetch userinfo
        try:
            userinfo = await svc.get_user_info(access_token)
        except Exception as exc:
            logger.warning("OIDC callback: userinfo fetch failed for tenant %s: %s", tenant_uuid, exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve user information from IdP",
            ) from exc

        # 3. Extract claims
        try:
            attrs = svc.extract_user_attributes(userinfo)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        # 4. JIT provision / look up account
        try:
            account = await svc.provision_or_get_account(
                db, tenant_id=tenant_uuid, email=attrs["email"], name=attrs["name"]
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc

        # 5. Commit JIT changes, then create session
        await db.commit()
        session_data = await SessionService.create_session(db, account, tenant_uuid)
        await db.commit()

        # 6. Redirect to frontend — pass access token in fragment so it stays JS-only
        oidc_access_token = session_data["access_token"]
        final_url = f"{redirect_url}#oidc_token={oidc_access_token}"

        logger.info("OIDC SSO: login successful for account %s (tenant %s)", account.id, tenant_uuid)

        response = RedirectResponse(url=final_url, status_code=status.HTTP_302_FOUND)
        response.set_cookie(
            key="refresh_token",
            value=session_data["refresh_token"],
            httponly=True,
            secure=_COOKIE_SECURE,
            samesite="strict",
            max_age=30 * 24 * 3600,
            path="/console/api/auth/refresh",
            domain=_COOKIE_DOMAIN,
        )
        return response

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("OIDC SSO callback: unexpected error: %s", exc, exc_info=True)
        fallback = (state_data or {}).get("redirect_url", f"{frontend_base}/signin")
        return RedirectResponse(
            url=f"{fallback}?login=error&message={quote('SSO sign-in failed. Please try again.', safe='')}",
            status_code=status.HTTP_302_FOUND,
        )
