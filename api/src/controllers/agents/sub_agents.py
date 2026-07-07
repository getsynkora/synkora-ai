"""
Sub-Agents Controller

Manages parent-child relationships between agents for multi-agent systems.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.models.agent_sub_agent import AgentSubAgent

router = APIRouter(prefix="/agents/{agent_slug}/sub-agents", tags=["Sub-Agents"])


# Schemas
class SubAgentCreate(BaseModel):
    """Schema for creating a sub-agent relationship."""

    sub_agent_id: UUID = Field(..., description="ID of the agent to add as sub-agent")
    execution_order: int = Field(default=0, description="Order in which this agent executes")
    config: dict | None = Field(default=None, description="Optional configuration for this relationship")


class SubAgentUpdate(BaseModel):
    """Schema for updating a sub-agent relationship."""

    execution_order: int | None = Field(default=None, description="New execution order")
    is_active: bool | None = Field(default=None, description="Whether this relationship is active")
    config: dict | None = Field(default=None, description="Updated configuration")


class SubAgentResponse(BaseModel):
    """Schema for sub-agent relationship response."""

    id: UUID
    parent_agent_id: UUID
    sub_agent_id: UUID
    sub_agent_name: str
    sub_agent_slug: str | None
    sub_agent_description: str | None
    execution_order: int
    is_active: bool
    config: dict | None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


@router.get("")
async def list_sub_agents(
    agent_slug: str,
    active_only: bool = True,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all sub-agents for a parent agent.

    Args:
        agent_slug: Parent agent slug
        active_only: Only return active relationships (default: True)
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        List of sub-agent relationships
    """
    # Get parent agent
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")

    # Query sub-agent relationships with eager loading to prevent N+1
    query = (
        select(AgentSubAgent)
        .options(selectinload(AgentSubAgent.sub_agent))
        .filter(AgentSubAgent.parent_agent_id == agent.id)
    )

    if active_only:
        query = query.filter(AgentSubAgent.is_active)

    result = await db.execute(query.order_by(AgentSubAgent.execution_order))
    relationships = result.scalars().all()

    # Build response using eager-loaded sub-agent details
    sub_agents_data = []
    for rel in relationships:
        sub_agent = rel.sub_agent  # Already loaded via selectinload
        if sub_agent:
            sub_agents_data.append(
                {
                    "id": str(rel.id),
                    "parent_agent_id": str(rel.parent_agent_id),
                    "sub_agent_id": str(rel.sub_agent_id),
                    "sub_agent_name": sub_agent.agent_name,
                    "sub_agent_slug": sub_agent.slug,
                    "sub_agent_description": sub_agent.description,
                    "execution_order": rel.execution_order,
                    "is_active": rel.is_active,
                    "config": rel.config,
                    "created_at": rel.created_at.isoformat() if rel.created_at else None,
                    "updated_at": rel.updated_at.isoformat() if rel.updated_at else None,
                }
            )

    return {
        "success": True,
        "message": f"Retrieved {len(sub_agents_data)} sub-agents",
        "data": {
            "parent_agent": agent_slug,
            "parent_agent_id": str(agent.id),
            "allow_transfer": agent.allow_transfer,
            "transfer_scope": agent.transfer_scope,
            "sub_agents": sub_agents_data,
        },
    }


@router.post("")
async def add_sub_agent(
    agent_slug: str,
    sub_agent_data: SubAgentCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Add a sub-agent to a parent agent.

    Args:
        agent_slug: Parent agent slug
        sub_agent_data: Sub-agent relationship data
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        Created sub-agent relationship
    """
    # Get parent agent
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    parent_agent = result.scalar_one_or_none()

    if not parent_agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parent agent '{agent_slug}' not found")

    # Get sub-agent
    result = await db.execute(
        select(Agent).filter(Agent.id == sub_agent_data.sub_agent_id, Agent.tenant_id == tenant_id)
    )
    sub_agent = result.scalar_one_or_none()

    if not sub_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Sub-agent with ID '{sub_agent_data.sub_agent_id}' not found"
        )

    # Check if agent is trying to add itself
    if parent_agent.id == sub_agent.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An agent cannot be its own sub-agent")

    # Check if relationship already exists
    result = await db.execute(
        select(AgentSubAgent).filter(
            AgentSubAgent.parent_agent_id == parent_agent.id, AgentSubAgent.sub_agent_id == sub_agent.id
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sub-agent '{sub_agent.agent_name}' is already linked to '{agent_slug}'",
        )

    # Check for circular dependencies
    if sub_agent.parent_agent_id == parent_agent.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Circular dependency: '{sub_agent.agent_name}' is already a parent of '{agent_slug}'",
        )

    # Create relationship
    relationship = AgentSubAgent(
        parent_agent_id=parent_agent.id,
        sub_agent_id=sub_agent.id,
        execution_order=sub_agent_data.execution_order,
        config=sub_agent_data.config,
    )

    db.add(relationship)
    await db.commit()
    await db.refresh(relationship)

    return {
        "success": True,
        "message": f"Sub-agent '{sub_agent.agent_name}' added to '{agent_slug}'",
        "data": {
            "id": str(relationship.id),
            "parent_agent_id": str(relationship.parent_agent_id),
            "sub_agent_id": str(relationship.sub_agent_id),
            "sub_agent_name": sub_agent.agent_name,
            "execution_order": relationship.execution_order,
            "is_active": relationship.is_active,
            "config": relationship.config,
        },
    }


@router.patch("/{sub_agent_relationship_id}")
async def update_sub_agent(
    agent_slug: str,
    sub_agent_relationship_id: UUID,
    update_data: SubAgentUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update a sub-agent relationship.

    Args:
        agent_slug: Parent agent slug
        sub_agent_relationship_id: ID of the relationship to update
        update_data: Updated relationship data
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        Updated sub-agent relationship
    """
    # Get parent agent
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    parent_agent = result.scalar_one_or_none()

    if not parent_agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parent agent '{agent_slug}' not found")

    # Get relationship
    result = await db.execute(
        select(AgentSubAgent).filter(
            AgentSubAgent.id == sub_agent_relationship_id, AgentSubAgent.parent_agent_id == parent_agent.id
        )
    )
    relationship = result.scalar_one_or_none()

    if not relationship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-agent relationship not found")

    # Update fields
    if update_data.execution_order is not None:
        relationship.execution_order = update_data.execution_order

    if update_data.is_active is not None:
        relationship.is_active = update_data.is_active

    if update_data.config is not None:
        relationship.config = update_data.config

    await db.commit()
    await db.refresh(relationship)

    # Get sub-agent details
    result = await db.execute(select(Agent).filter(Agent.id == relationship.sub_agent_id))
    sub_agent = result.scalar_one_or_none()

    return {
        "success": True,
        "message": "Sub-agent relationship updated",
        "data": {
            "id": str(relationship.id),
            "parent_agent_id": str(relationship.parent_agent_id),
            "sub_agent_id": str(relationship.sub_agent_id),
            "sub_agent_name": sub_agent.agent_name if sub_agent else None,
            "execution_order": relationship.execution_order,
            "is_active": relationship.is_active,
            "config": relationship.config,
        },
    }


@router.delete("/{sub_agent_relationship_id}")
async def remove_sub_agent(
    agent_slug: str,
    sub_agent_relationship_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Remove a sub-agent from a parent agent.

    Args:
        agent_slug: Parent agent slug
        sub_agent_relationship_id: ID of the relationship to remove
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        Success message
    """
    # Get parent agent
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    parent_agent = result.scalar_one_or_none()

    if not parent_agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parent agent '{agent_slug}' not found")

    # Get relationship
    result = await db.execute(
        select(AgentSubAgent).filter(
            AgentSubAgent.id == sub_agent_relationship_id, AgentSubAgent.parent_agent_id == parent_agent.id
        )
    )
    relationship = result.scalar_one_or_none()

    if not relationship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-agent relationship not found")

    # Get sub-agent name before deleting
    result = await db.execute(select(Agent).filter(Agent.id == relationship.sub_agent_id))
    sub_agent = result.scalar_one_or_none()
    sub_agent_name = sub_agent.agent_name if sub_agent else "Unknown"

    # Delete relationship
    await db.delete(relationship)
    await db.commit()

    return {
        "success": True,
        "message": f"Sub-agent '{sub_agent_name}' removed from '{agent_slug}'",
        "data": {"parent_agent": agent_slug, "removed_sub_agent": sub_agent_name},
    }


@router.get("/available")
async def list_available_agents(
    agent_slug: str, tenant_id: UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """
    List agents that can be added as sub-agents.

    Excludes:
    - The parent agent itself
    - Agents already linked as sub-agents
    - Agents that would create circular dependencies

    Args:
        agent_slug: Parent agent slug
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        List of available agents
    """
    # Get parent agent
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    parent_agent = result.scalar_one_or_none()

    if not parent_agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Parent agent '{agent_slug}' not found")

    # Get already linked sub-agent IDs
    result = await db.execute(
        select(AgentSubAgent.sub_agent_id).filter(AgentSubAgent.parent_agent_id == parent_agent.id)
    )
    linked_ids = [row[0] for row in result.all()]

    # Get all agents for this tenant, excluding parent and already linked
    query = select(Agent).filter(
        Agent.tenant_id == tenant_id,
        Agent.id != parent_agent.id,
    )
    if linked_ids:
        query = query.filter(Agent.id.notin_(linked_ids))

    result = await db.execute(query)
    available_agents = result.scalars().all()

    agents_data = [
        {
            "id": str(agent.id),
            "agent_name": agent.agent_name,
            "description": agent.description,
            "agent_type": agent.agent_type,
            "status": agent.status,
        }
        for agent in available_agents
    ]

    return {
        "success": True,
        "message": f"Retrieved {len(agents_data)} available agents",
        "data": {"parent_agent": agent_slug, "available_agents": agents_data},
    }
