"""
Tenant security settings endpoints.

GET  /console/api/tenant/security  — read security settings (OWNER or ADMIN)
PATCH /console/api/tenant/security — update console_ip_allowlist / mfa_required (OWNER only)
"""

from __future__ import annotations

import ipaddress
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id, require_role
from src.models import Account
from src.models.tenant import AccountRole, Tenant, TenantAccountJoin

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class TenantSecuritySettings(BaseModel):
    """Request body for PATCH /console/api/tenant/security."""

    console_ip_allowlist: list[str] | None = None  # null = disable allowlist
    mfa_required: bool | None = None

    @field_validator("console_ip_allowlist", mode="before")
    @classmethod
    def validate_ip_entries(cls, v: list[str] | None) -> list[str] | None:
        """Validate each entry is a valid IP address or CIDR range (or '*')."""
        if v is None:
            return None
        cleaned: list[str] = []
        for raw in v:
            entry = raw.strip()
            if not entry:
                continue
            if entry == "*":
                cleaned.append(entry)
                continue
            try:
                if "/" in entry:
                    ipaddress.ip_network(entry, strict=False)
                else:
                    ipaddress.ip_address(entry)
                cleaned.append(entry)
            except ValueError:
                raise ValueError(f"Invalid IP address or CIDR range: {entry!r}")
        return cleaned or None  # empty list treated as "disable"


class TenantSecurityResponse(BaseModel):
    """Response for GET and PATCH /console/api/tenant/security."""

    tenant_id: str
    mfa_required: bool
    console_ip_allowlist: list[str] | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_tenant(tenant_id, db: AsyncSession) -> Tenant:
    result = await db.execute(select(Tenant).filter(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def _mfa_bool(tenant: Tenant) -> bool:
    return getattr(tenant, "mfa_required", "false") == "true"


# ---------------------------------------------------------------------------
# GET  /console/api/tenant/security
# ---------------------------------------------------------------------------


@router.get("/security", response_model=TenantSecurityResponse)
async def get_security_settings(
    current_account: Account = Depends(get_current_account),
    tenant_id=Depends(get_current_tenant_id),
    _role_check=Depends(require_role(AccountRole.ADMIN)),
    db: AsyncSession = Depends(get_async_db),
) -> TenantSecurityResponse:
    """
    Return current security settings for the authenticated tenant.

    Requires ADMIN or OWNER role.
    """
    tenant = await _get_tenant(tenant_id, db)
    return TenantSecurityResponse(
        tenant_id=str(tenant.id),
        mfa_required=_mfa_bool(tenant),
        console_ip_allowlist=tenant.console_ip_allowlist,
    )


# ---------------------------------------------------------------------------
# PATCH /console/api/tenant/security
# ---------------------------------------------------------------------------


@router.patch("/security", response_model=TenantSecurityResponse)
async def update_security_settings(
    data: TenantSecuritySettings,
    current_account: Account = Depends(get_current_account),
    tenant_id=Depends(get_current_tenant_id),
    _role_check=Depends(require_role(AccountRole.OWNER)),
    db: AsyncSession = Depends(get_async_db),
) -> TenantSecurityResponse:
    """
    Update security settings for the authenticated tenant.

    Requires OWNER role.

    - ``console_ip_allowlist``: list of IPs / CIDR ranges allowed to log in.
      Pass ``null`` to disable the allowlist (allow all IPs).
    - ``mfa_required``: whether all tenant members must have 2FA configured.
    """
    tenant = await _get_tenant(tenant_id, db)

    changed = False

    if data.console_ip_allowlist is not None:
        tenant.console_ip_allowlist = data.console_ip_allowlist if data.console_ip_allowlist else None
        changed = True
    elif "console_ip_allowlist" in data.model_fields_set:
        # Explicitly passed null — disable the allowlist
        tenant.console_ip_allowlist = None
        changed = True

    if data.mfa_required is not None:
        tenant.mfa_required = "true" if data.mfa_required else "false"
        changed = True

    if changed:
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        logger.info(
            "Tenant security settings updated by account %s for tenant %s",
            current_account.id,
            tenant_id,
        )

    return TenantSecurityResponse(
        tenant_id=str(tenant.id),
        mfa_required=_mfa_bool(tenant),
        console_ip_allowlist=tenant.console_ip_allowlist,
    )
