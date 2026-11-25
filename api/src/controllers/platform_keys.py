"""
Platform keys: tenant-level API keys for integrating another system with this tenant.

A platform key belongs to the tenant, not to an agent. It can manage the tenant's customer workspaces
(tenants:manage), read its plan and usage (billing:read) and manage its webhooks (webhooks:manage), and nothing that
acts on one agent (chat, conversations, knowledge, handoffs). Widget and agent keys stay on each agent's API keys page.

Only the tenant's owners and admins can see or change platform keys: one key can act for the whole tenant.

    GET    /api/v1/platform-keys
    POST   /api/v1/platform-keys                    {"name", "permissions": [...]}   -> the key, shown once
    POST   /api/v1/platform-keys/{key_id}/regenerate                                 -> the new key, shown once
    PATCH  /api/v1/platform-keys/{key_id}            {"name"?, "is_active"?}
    DELETE /api/v1/platform-keys/{key_id}
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id, require_role
from src.models import Account, AccountRole
from src.models.agent_api_key import AgentApiKey
from src.services.activity.activity_log_service import ActivityLogService
from src.services.agent_api.api_key_service import (
    PLATFORM_KEY_PERMISSIONS,
    AgentApiKeyService,
    validate_platform_permissions,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/platform-keys",
    tags=["Platform Keys"],
    dependencies=[Depends(require_role(AccountRole.ADMIN))],
)

MAX_PLATFORM_KEYS = 20

PERMISSION_DESCRIPTIONS = {
    "tenants:manage": "Create and manage customer workspaces: plans, usage, agents and their API keys",
    "billing:read": "Read this workspace's plan and usage",
    "billing:manage": "Set this workspace's plan when it is paid for in your system (a platform admin must allow it)",
    "webhooks:manage": "Register webhooks for usage alerts and plan changes",
}


class PlatformKeyInfo(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    permissions: list[str]
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime


class CreatedPlatformKey(PlatformKeyInfo):
    api_key: str = Field(..., description="The key. Shown once; store it now")


class PlatformKeyList(BaseModel):
    keys: list[PlatformKeyInfo]
    available_permissions: dict[str, str]


class CreatePlatformKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    permissions: list[str] = Field(..., min_length=1)

    @field_validator("permissions")
    @classmethod
    def _check_permissions(cls, value: list[str]) -> list[str]:
        return validate_platform_permissions(value)


class UpdatePlatformKeyRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None


def _info(key: AgentApiKey) -> PlatformKeyInfo:
    return PlatformKeyInfo(
        id=key.id,
        name=key.key_name,
        key_prefix=key.key_prefix,
        permissions=list(key.permissions or []),
        is_active=bool(key.is_active),
        last_used_at=key.last_used_at,
        created_at=key.created_at,
    )


async def _get(db: AsyncSession, tenant_id: UUID, key_id: UUID) -> AgentApiKey:
    key = await db.scalar(
        select(AgentApiKey).where(
            AgentApiKey.id == key_id,
            AgentApiKey.tenant_id == tenant_id,
            AgentApiKey.agent_id.is_(None),
        )
    )
    if key is None:
        raise HTTPException(status_code=404, detail="Platform key not found")
    return key


def _log(tenant_id, account, action: str, key: AgentApiKey, request: Request) -> None:
    """Record who changed which platform key in the tenant's activity log. Never raises."""
    try:
        ActivityLogService.queue_activity(
            tenant_id=tenant_id,
            account_id=account.id,
            action=action,
            resource_type="platform_key",
            resource_id=key.id,
            details={"name": key.key_name, "key_prefix": key.key_prefix, "permissions": list(key.permissions or [])},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent", "")[:255],
        )
    except Exception:
        logger.warning("Could not record audit event %s", action, exc_info=True)


@router.get("", response_model=PlatformKeyList)
async def list_platform_keys(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    rows = await db.scalars(
        select(AgentApiKey)
        .where(AgentApiKey.tenant_id == tenant_id, AgentApiKey.agent_id.is_(None))
        .order_by(AgentApiKey.created_at.desc())
    )
    return PlatformKeyList(
        keys=[_info(key) for key in rows.all()],
        available_permissions={p: PERMISSION_DESCRIPTIONS[p] for p in sorted(PLATFORM_KEY_PERMISSIONS)},
    )


@router.post("", response_model=CreatedPlatformKey, status_code=status.HTTP_201_CREATED)
async def create_platform_key(
    body: CreatePlatformKeyRequest,
    request: Request,
    account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    existing = await db.scalars(
        select(AgentApiKey.id).where(AgentApiKey.tenant_id == tenant_id, AgentApiKey.agent_id.is_(None))
    )
    if len(existing.all()) >= MAX_PLATFORM_KEYS:
        raise HTTPException(status_code=409, detail=f"At most {MAX_PLATFORM_KEYS} platform keys; delete an old one")
    key, plain = await AgentApiKeyService.create_api_key(
        db=db,
        agent_id=None,
        tenant_id=tenant_id,
        name=body.name,
        permissions=body.permissions,
    )
    _log(tenant_id, account, "platform_key.created", key, request)
    return CreatedPlatformKey(**_info(key).model_dump(), api_key=plain)


@router.post("/{key_id}/regenerate", response_model=CreatedPlatformKey)
async def regenerate_platform_key(
    key_id: UUID,
    request: Request,
    account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    key = await _get(db, tenant_id, key_id)
    plain, hashed = AgentApiKeyService.generate_api_key()
    key.api_key = hashed
    key.key_prefix = plain[:20]  # must match the 20-character prefix used when validating
    key.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(key)
    _log(tenant_id, account, "platform_key.regenerated", key, request)
    return CreatedPlatformKey(**_info(key).model_dump(), api_key=plain)


@router.patch("/{key_id}", response_model=PlatformKeyInfo)
async def update_platform_key(
    key_id: UUID,
    body: UpdatePlatformKeyRequest,
    request: Request,
    account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    key = await _get(db, tenant_id, key_id)
    if body.name is not None:
        key.key_name = body.name
    if body.is_active is not None:
        key.is_active = body.is_active
    key.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(key)
    _log(tenant_id, account, "platform_key.updated", key, request)
    return _info(key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform_key(
    key_id: UUID,
    request: Request,
    account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    key = await _get(db, tenant_id, key_id)
    _log(tenant_id, account, "platform_key.deleted", key, request)
    await db.delete(key)
    await db.commit()
