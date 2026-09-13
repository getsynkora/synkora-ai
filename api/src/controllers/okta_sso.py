"""
Okta SSO Controllers.

Handles Okta SSO authentication flows for enterprise tenants.
"""

import hashlib
import json
import logging
import secrets
import uuid
from typing import Any
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.config_helper import get_app_base_url

from ..core.database import get_async_db
from ..middleware.auth_middleware import get_current_tenant_id, require_role
from ..models import AccountRole
from ..models.okta_tenant import OktaTenant
from ..services.agents.security import decrypt_value, encrypt_value
from ..services.sso import OktaSSOService
from ..services.sso.okta_sso import validate_okta_domain

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sso/okta", tags=["okta-sso"])

_STATE_TTL = 600  # 10 minutes


def _validate_idp(domain: str, issuer: str) -> None:
    try:
        domain = validate_okta_domain(domain)
        parsed = urlparse(issuer)
        if (
            parsed.scheme != "https"
            or parsed.hostname != domain
            or parsed.port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or "\\" in issuer
        ):
            raise ValueError("Invalid issuer")
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Issuer must be an HTTPS URL on the configured Okta domain"
        ) from exc


def _config_fingerprint(config: OktaTenant) -> str:
    fields = [config.domain, config.issuer_url, config.client_id, config.client_secret, config.authorization_server_id]
    return hashlib.sha256(json.dumps(fields).encode()).hexdigest()


def _fmt_dt(val: Any) -> str | None:
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)


def _get_redis():
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        if redis is None:
            raise RuntimeError("Redis returned None")
        return redis
    except Exception as e:
        logger.error(f"Redis unavailable for Okta SSO state: {e}")
        raise RuntimeError("SSO service temporarily unavailable")


def _validate_redirect_url(url: str | None, base_url: str) -> str:
    """Validate redirect_url is same origin as app base URL to prevent open redirect."""
    if not url:
        return f"{base_url}/dashboard"
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        return f"{base_url}/dashboard"
    # Must match scheme+host of the app base URL
    if (parsed.scheme, parsed.netloc) != (base_parsed.scheme, base_parsed.netloc):
        logger.warning(f"Rejected open redirect attempt to: {url}")
        return f"{base_url}/dashboard"
    return url


async def _store_okta_state(state: str, data: dict) -> None:
    await _get_redis().setex(f"okta_sso_state:{state}", _STATE_TTL, json.dumps(data))


async def _consume_okta_state(state: str) -> dict | None:
    try:
        redis = _get_redis()
        raw = await redis.getdel(f"okta_sso_state:{state}")
        if raw:
            return json.loads(raw)
        return None
    except RuntimeError:
        return None


# Pydantic models
class OktaTenantCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    domain: str
    client_id: str
    client_secret: str
    issuer_url: str
    authorization_server_id: str | None = None
    jit_provisioning_enabled: bool = True
    enabled: bool = True

    @field_validator("domain")
    @classmethod
    def valid_domain(cls, value: str) -> str:
        return validate_okta_domain(value)


class OktaTenantUpdate(BaseModel):
    model_config = ConfigDict(strict=True)

    domain: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    issuer_url: str | None = None
    authorization_server_id: str | None = None
    jit_provisioning_enabled: bool | None = None
    enabled: bool | None = None

    @field_validator("domain")
    @classmethod
    def valid_domain(cls, value: str | None) -> str | None:
        return validate_okta_domain(value) if value is not None else None


# Okta SSO Endpoints


@router.get("/login")
async def okta_login(
    tenant_id: str = Query(..., description="Tenant ID for Okta SSO"),
    redirect_url: str = Query(None, description="Frontend redirect URL after login"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Initiate Okta SSO flow for a tenant.

    This endpoint redirects the user to Okta's authorization page.
    """
    try:
        # Get Okta tenant configuration
        tenant_uuid = uuid.UUID(tenant_id)
        result = await db.execute(
            select(OktaTenant).filter(OktaTenant.tenant_id == tenant_uuid, OktaTenant.enabled == "true")
        )
        okta_tenant = result.scalar_one_or_none()

        if not okta_tenant:
            raise HTTPException(status_code=404, detail="Okta SSO not configured for this tenant")

        base_url = await get_app_base_url(db, tenant_uuid)

        # Validate redirect_url to prevent open redirect
        safe_redirect_url = _validate_redirect_url(redirect_url, base_url)

        # Derive the OIDC callback URI from app base URL
        callback_uri = f"{base_url}/api/v1/sso/okta/callback"

        # Decrypt client_secret for use with OIDC service
        try:
            decrypted_secret = decrypt_value(okta_tenant.client_secret)
        except Exception:
            logger.error(f"Failed to decrypt Okta client_secret for tenant {tenant_id}")
            raise HTTPException(status_code=500, detail="SSO configuration error")

        # Initialize SSO service
        sso = OktaSSOService(
            domain=okta_tenant.domain,
            client_id=okta_tenant.client_id,
            client_secret=decrypted_secret,
            redirect_uri=callback_uri,
        )

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state in Redis
        await _store_okta_state(
            state,
            {
                "tenant_id": tenant_id,
                "redirect_url": safe_redirect_url,
                "flow_type": "okta_sso",
                "config_fingerprint": _config_fingerprint(okta_tenant),
            },
        )

        # Get authorization URL
        auth_url = sso.get_oidc_authorization_url(state=state)

        logger.info(f"Initiating Okta SSO for tenant {tenant_id}")

        return RedirectResponse(url=auth_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Okta SSO login error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="SSO login failed. Please try again.")


@router.get("/callback")
async def okta_callback(
    code: str = Query(..., description="Authorization code from Okta"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Handle Okta SSO callback.

    This endpoint receives the authorization code from Okta,
    exchanges it for an access token, gets user info, and creates/links account.
    """
    state_data = await _consume_okta_state(state)
    try:
        if not state_data:
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

        tenant_id = uuid.UUID(state_data["tenant_id"])
        redirect_url = state_data["redirect_url"]

        # Get Okta tenant configuration
        result = await db.execute(
            select(OktaTenant).filter(OktaTenant.tenant_id == tenant_id, OktaTenant.enabled == "true")
        )
        okta_tenant = result.scalar_one_or_none()

        if not okta_tenant:
            raise HTTPException(status_code=404, detail="Okta SSO not configured for this tenant")

        if state_data.get("config_fingerprint") != _config_fingerprint(okta_tenant):
            raise HTTPException(status_code=400, detail="SSO configuration changed; restart login")

        base_url = await get_app_base_url(db, tenant_id)
        callback_uri = f"{base_url}/api/v1/sso/okta/callback"

        # Decrypt client_secret for use with OIDC service
        try:
            decrypted_secret = decrypt_value(okta_tenant.client_secret)
        except Exception:
            logger.error(f"Failed to decrypt Okta client_secret for tenant {tenant_id}")
            raise HTTPException(status_code=500, detail="SSO configuration error")

        # Initialize SSO service
        sso = OktaSSOService(
            domain=okta_tenant.domain,
            client_id=okta_tenant.client_id,
            client_secret=decrypted_secret,
            redirect_uri=callback_uri,
        )

        # Exchange code for token
        token_data = await sso.get_oidc_access_token(code)

        if not token_data.get("access_token"):
            raise HTTPException(status_code=400, detail="Failed to get access token")

        # Get user info
        user_info = await sso.get_oidc_user_info(token_data["access_token"])

        # Extract user details
        user_email = user_info.get("email")

        if not user_email:
            raise HTTPException(status_code=400, detail="Failed to get user information from Okta")

        logger.info(f"Okta SSO successful for tenant {tenant_id}, user {user_email}")

        # SECURITY: Do not include email in the redirect URL — the frontend
        # should obtain the user's email from the session/token, not the URL.
        return RedirectResponse(url=f"{redirect_url}?login=success&provider=okta")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Okta SSO callback error: {e}", exc_info=True)
        fallback = (state_data or {}).get("redirect_url", "/signin")
        return RedirectResponse(
            url=f"{fallback}?login=error&message={quote('SSO sign-in failed. Please try again.', safe='')}"
        )


# Okta Tenant Management Endpoints


@router.get("/config", dependencies=[Depends(require_role(AccountRole.ADMIN))])
async def get_okta_config(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """
    Get Okta SSO configuration for the current tenant.
    """
    try:
        result = await db.execute(select(OktaTenant).filter(OktaTenant.tenant_id == tenant_id))
        okta_tenant = result.scalar_one_or_none()

        if not okta_tenant:
            return {"configured": False}

        return {
            "configured": True,
            "domain": okta_tenant.domain,
            "client_id": okta_tenant.client_id,
            "issuer_url": okta_tenant.issuer_url,
            "authorization_server_id": okta_tenant.authorization_server_id,
            "jit_provisioning_enabled": okta_tenant.jit_provisioning_enabled,
            "enabled": okta_tenant.enabled,
            "created_at": _fmt_dt(okta_tenant.created_at),
        }

    except Exception as e:
        logger.error(f"Get Okta config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/config", dependencies=[Depends(require_role(AccountRole.ADMIN))])
async def create_okta_config(
    data: OktaTenantCreate,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create Okta SSO configuration for the current tenant.
    """
    try:
        # Check if configuration already exists
        result = await db.execute(select(OktaTenant).filter(OktaTenant.tenant_id == tenant_id))
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(status_code=400, detail="Okta SSO configuration already exists for this tenant")

        _validate_idp(data.domain, data.issuer_url)
        if not data.client_secret.strip():
            raise HTTPException(status_code=400, detail="A client secret is required")

        # Encrypt client_secret before storing
        try:
            encrypted_secret = encrypt_value(data.client_secret)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Failed to encrypt client secret") from exc

        # Create new configuration
        okta_tenant = OktaTenant(
            tenant_id=tenant_id,
            domain=data.domain,
            client_id=data.client_id,
            client_secret=encrypted_secret,
            issuer_url=data.issuer_url,
            authorization_server_id=data.authorization_server_id,
            jit_provisioning_enabled="true" if data.jit_provisioning_enabled else "false",
            enabled="true" if data.enabled else "false",
        )

        db.add(okta_tenant)
        await db.commit()
        await db.refresh(okta_tenant)

        logger.info(f"Created Okta SSO configuration for tenant {tenant_id}")

        return {
            "success": True,
            "message": "Okta SSO configuration created successfully",
            "domain": okta_tenant.domain,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create Okta config error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/config", dependencies=[Depends(require_role(AccountRole.ADMIN))])
async def update_okta_config(
    data: OktaTenantUpdate,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update Okta SSO configuration for the current tenant.
    """
    try:
        result = await db.execute(select(OktaTenant).filter(OktaTenant.tenant_id == tenant_id))
        okta_tenant = result.scalar_one_or_none()

        if not okta_tenant:
            raise HTTPException(status_code=404, detail="Okta SSO configuration not found for this tenant")

        next_domain = data.domain if data.domain is not None else okta_tenant.domain
        next_issuer = data.issuer_url if data.issuer_url is not None else okta_tenant.issuer_url
        _validate_idp(next_domain, next_issuer)
        identity_changed = any(
            value is not None and value != getattr(okta_tenant, name)
            for name, value in (
                ("domain", data.domain),
                ("issuer_url", data.issuer_url),
                ("client_id", data.client_id),
                ("authorization_server_id", data.authorization_server_id),
            )
        )
        if identity_changed and not (data.client_secret and data.client_secret.strip()):
            raise HTTPException(status_code=400, detail="Changing the identity provider requires a new client secret")
        if data.client_secret is not None and not data.client_secret.strip():
            raise HTTPException(status_code=400, detail="A client secret is required")

        # Update fields if provided
        if data.domain is not None:
            okta_tenant.domain = data.domain
        if data.client_id is not None:
            okta_tenant.client_id = data.client_id
        if data.client_secret is not None:
            try:
                okta_tenant.client_secret = encrypt_value(data.client_secret)
            except Exception as exc:
                raise HTTPException(status_code=500, detail="Failed to encrypt client secret") from exc
        if data.issuer_url is not None:
            okta_tenant.issuer_url = data.issuer_url
        if data.authorization_server_id is not None:
            okta_tenant.authorization_server_id = data.authorization_server_id
        if data.jit_provisioning_enabled is not None:
            okta_tenant.jit_provisioning_enabled = "true" if data.jit_provisioning_enabled else "false"
        if data.enabled is not None:
            okta_tenant.enabled = "true" if data.enabled else "false"

        await db.commit()
        await db.refresh(okta_tenant)

        logger.info(f"Updated Okta SSO configuration for tenant {tenant_id}")

        return {"success": True, "message": "Okta SSO configuration updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update Okta config error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/config", dependencies=[Depends(require_role(AccountRole.ADMIN))])
async def delete_okta_config(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """
    Delete Okta SSO configuration for the current tenant.
    """
    try:
        result = await db.execute(select(OktaTenant).filter(OktaTenant.tenant_id == tenant_id))
        okta_tenant = result.scalar_one_or_none()

        if not okta_tenant:
            raise HTTPException(status_code=404, detail="Okta SSO configuration not found for this tenant")

        await db.delete(okta_tenant)
        await db.commit()

        logger.info(f"Deleted Okta SSO configuration for tenant {tenant_id}")

        return {"success": True, "message": "Okta SSO configuration deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete Okta config error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")
