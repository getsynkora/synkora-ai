"""Endpoints for managing which database connections are attached to an agent."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models import Account
from src.models.agent import Agent
from src.models.database_connection import DatabaseConnection
from src.services.cache import get_agent_cache

logger = logging.getLogger(__name__)
router = APIRouter()


class AgentDatabaseConnectionsUpdate(BaseModel):
    connection_ids: list[str]


@router.get("/{agent_slug}/database-connections")
async def get_agent_database_connections(
    agent_slug: str,
    db: AsyncSession = Depends(get_async_db),
    account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """
    Get all tenant database connections with their attachment status for this agent.
    Returns all available connections and marks which ones are attached to the agent.
    """
    agent = await db.scalar(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    allowed_ids: list[str] = (agent.agent_metadata or {}).get("allowed_database_connections", [])

    connections = (
        (
            await db.execute(
                select(DatabaseConnection).where(
                    DatabaseConnection.tenant_id == tenant_id,
                    DatabaseConnection.status == "active",
                )
            )
        )
        .scalars()
        .all()
    )

    return [
        {
            "id": str(c.id),
            "name": c.name,
            "type": c.database_type,
            "host": c.host,
            "port": c.port,
            "database": c.database_name,
            "attached": str(c.id) in allowed_ids,
        }
        for c in connections
    ]


@router.put("/{agent_slug}/database-connections")
async def update_agent_database_connections(
    agent_slug: str,
    body: AgentDatabaseConnectionsUpdate,
    db: AsyncSession = Depends(get_async_db),
    account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """
    Set which database connections are attached to this agent.
    Replaces the entire list of allowed connection IDs.
    """
    agent = await db.scalar(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Validate all provided IDs belong to this tenant
    if body.connection_ids:
        count = len(
            (
                await db.execute(
                    select(DatabaseConnection.id).where(
                        DatabaseConnection.id.in_([UUID(cid) for cid in body.connection_ids]),
                        DatabaseConnection.tenant_id == tenant_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        if count != len(body.connection_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more connection IDs are invalid",
            )

    metadata = dict(agent.agent_metadata or {})
    metadata["allowed_database_connections"] = body.connection_ids
    agent.agent_metadata = metadata
    flag_modified(agent, "agent_metadata")
    await db.commit()

    cache = get_agent_cache()
    await cache.invalidate_agent(slug=agent.slug, agent_id=str(agent.id), tenant_id=str(tenant_id))

    return {"connection_ids": body.connection_ids}
