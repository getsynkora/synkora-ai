"""
Agent version history endpoints.

Provides snapshot listing, retrieval, and rollback for agent configurations.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.agent_version import AgentVersion
from src.services.agents.agent_version_service import create_version, list_versions, restore_version
from src.services.cache import get_agent_cache

logger = logging.getLogger(__name__)

versions_router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AgentVersionSummary(BaseModel):
    """Compact version row for list responses."""

    id: str
    version_number: int
    change_description: str | None
    created_by: str | None
    created_at: str
    changed_fields: list[str] | None


class AgentVersionDetail(AgentVersionSummary):
    """Full version including the configuration snapshot."""

    snapshot: dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _version_to_summary(v: AgentVersion) -> AgentVersionSummary:
    return AgentVersionSummary(
        id=str(v.id),
        version_number=v.version_number,
        change_description=v.change_description,
        created_by=str(v.created_by) if v.created_by else None,
        created_at=v.created_at.isoformat(),
        changed_fields=v.changed_fields if isinstance(v.changed_fields, list) else None,
    )


def _version_to_detail(v: AgentVersion) -> AgentVersionDetail:
    return AgentVersionDetail(
        id=str(v.id),
        version_number=v.version_number,
        change_description=v.change_description,
        created_by=str(v.created_by) if v.created_by else None,
        created_at=v.created_at.isoformat(),
        changed_fields=v.changed_fields if isinstance(v.changed_fields, list) else None,
        snapshot=v.snapshot or {},
    )


async def _get_agent_or_404(agent_slug: str, tenant_id: uuid.UUID, db: AsyncSession) -> Agent:
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")
    return agent


async def _get_version_or_404(agent: Agent, version_number: int, db: AsyncSession) -> AgentVersion:
    result = await db.execute(
        select(AgentVersion).filter(
            AgentVersion.agent_id == agent.id,
            AgentVersion.tenant_id == agent.tenant_id,
            AgentVersion.version_number == version_number,
        )
    )
    version = result.scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found for agent '{agent.slug}'",
        )
    return version


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@versions_router.get("/{agent_slug}/versions", response_model=list[AgentVersionSummary])
async def get_agent_versions(
    agent_slug: str,
    limit: int = Query(default=50, ge=1, le=200),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List version history for an agent, newest first.

    Returns summary rows (no snapshot payload) for efficient pagination.
    """
    agent = await _get_agent_or_404(agent_slug, tenant_id, db)
    versions = await list_versions(db, agent_id=agent.id, tenant_id=tenant_id, limit=limit)
    return [_version_to_summary(v) for v in versions]


@versions_router.get("/{agent_slug}/versions/{version_number}", response_model=AgentVersionDetail)
async def get_agent_version(
    agent_slug: str,
    version_number: int,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Retrieve a specific version snapshot by version number.
    """
    agent = await _get_agent_or_404(agent_slug, tenant_id, db)
    version = await _get_version_or_404(agent, version_number, db)
    return _version_to_detail(version)


@versions_router.post("/{agent_slug}/versions/{version_number}/restore")
async def restore_agent_version(
    agent_slug: str,
    version_number: int,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Restore an agent to a previous version.

    Creates a new version entry recording the restore operation; does not
    overwrite any existing version record.
    """
    agent = await _get_agent_or_404(agent_slug, tenant_id, db)
    version = await _get_version_or_404(agent, version_number, db)

    try:
        new_version = await restore_version(db, agent, version, account_id=current_account.id)
        await db.commit()
        await db.refresh(agent)
        await db.refresh(new_version)

        # Invalidate caches so the next request picks up the restored config
        cache = get_agent_cache()
        await cache.invalidate_agent(slug=agent.slug, agent_id=str(agent.id), tenant_id=str(tenant_id))
        await cache.invalidate_agents_list(str(tenant_id))

        return {
            "success": True,
            "message": f"Agent '{agent_slug}' restored to version {version_number}",
            "data": {
                "new_version_number": new_version.version_number,
                "restored_from": version_number,
            },
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to restore agent version: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore agent version",
        )
