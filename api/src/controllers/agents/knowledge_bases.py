"""
Agent API endpoints.

Provides REST API endpoints for managing and executing Google Agent SDK agents.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.controllers.agents.models import AgentResponse, AttachKnowledgeBaseRequest
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id, require_role
from src.models import AccountRole
from src.models.agent import Agent
from src.services.agents.agent_manager import AgentManager

logger = logging.getLogger(__name__)

# Create router
agents_knowledge_bases_router = APIRouter()

# Global agent manager instance
agent_manager = AgentManager()

# Agent-Knowledge Base Management Endpoints


class AttachKnowledgeBaseRequest(BaseModel):
    """Request model for attaching a knowledge base to an agent."""

    knowledge_base_id: int = Field(..., description="ID of the knowledge base")
    retrieval_config: dict[str, Any] | None = Field(
        None, description="Retrieval configuration (max_results, min_score, max_context_tokens, etc.)"
    )


@agents_knowledge_bases_router.post("/{agent_id}/knowledge-bases", response_model=AgentResponse)
async def attach_knowledge_base(
    agent_id: str,
    request: AttachKnowledgeBaseRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_role(AccountRole.ADMIN)),
):
    """
    Attach a knowledge base to an agent.

    Args:
        agent_id: UUID of the agent
        request: Knowledge base attachment request
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Success confirmation
    """
    try:
        from src.models.agent_knowledge_base import AgentKnowledgeBase
        from src.models.knowledge_base import KnowledgeBase

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # SECURITY: Verify knowledge base exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(
            select(KnowledgeBase).filter(
                KnowledgeBase.id == request.knowledge_base_id, KnowledgeBase.tenant_id == tenant_id
            )
        )
        kb = result.scalar_one_or_none()
        if not kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge base with ID '{request.knowledge_base_id}' not found",
            )

        # Check if already attached
        result = await db.execute(
            select(AgentKnowledgeBase).filter(
                AgentKnowledgeBase.agent_id == agent_uuid,
                AgentKnowledgeBase.knowledge_base_id == request.knowledge_base_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing association
            existing.retrieval_config = request.retrieval_config or {}
            existing.is_active = True
            message = f"Knowledge base '{kb.name}' updated for agent"
        else:
            # Create new association
            agent_kb = AgentKnowledgeBase(
                agent_id=agent_uuid,
                knowledge_base_id=request.knowledge_base_id,
                retrieval_config=request.retrieval_config or {},
                is_active=True,
            )
            db.add(agent_kb)
            message = f"Knowledge base '{kb.name}' attached to agent"

        await db.commit()

        return AgentResponse(
            success=True,
            message=message,
            data={
                "agent_id": str(agent_uuid),
                "knowledge_base_id": request.knowledge_base_id,
                "knowledge_base_name": kb.name,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to attach knowledge base: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to attach knowledge base")


@agents_knowledge_bases_router.get("/{agent_id}/knowledge-bases", response_model=AgentResponse)
async def list_agent_knowledge_bases(
    agent_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all knowledge bases attached to an agent.

    Args:
        agent_id: UUID of the agent
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        List of attached knowledge bases
    """
    try:
        # Convert string to UUID
        from src.models.agent_knowledge_base import AgentKnowledgeBase

        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Single OR query to prevent timing attacks
        # Checks: (agent belongs to tenant) OR (agent is public)
        result = await db.execute(
            select(Agent).filter(Agent.id == agent_uuid, or_(Agent.tenant_id == tenant_id, Agent.is_public.is_(True)))
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Get all knowledge bases for this agent, eagerly loading the relationship
        # to avoid lazy-load in async context (greenlet_spawn error).
        result = await db.execute(
            select(AgentKnowledgeBase)
            .filter(AgentKnowledgeBase.agent_id == agent_uuid)
            .options(selectinload(AgentKnowledgeBase.knowledge_base))
        )
        agent_kbs = result.scalars().all()

        kb_list = []
        for agent_kb in agent_kbs:
            kb = agent_kb.knowledge_base
            kb_list.append(
                {
                    "id": kb.id,
                    "name": kb.name,
                    "description": kb.description,
                    "vector_db_provider": kb.vector_db_provider,
                    "total_documents": kb.total_documents,
                    "total_chunks": kb.total_chunks,
                    "is_active": agent_kb.is_active,
                    "retrieval_config": agent_kb.retrieval_config,
                    "created_at": agent_kb.created_at.isoformat(),
                    "updated_at": agent_kb.updated_at.isoformat(),
                }
            )

        return AgentResponse(
            success=True, message=f"Found {len(kb_list)} knowledge bases for agent", data={"knowledge_bases": kb_list}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list agent knowledge bases: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list knowledge bases")


@agents_knowledge_bases_router.put("/{agent_id}/knowledge-bases/{kb_id}/config", response_model=AgentResponse)
async def update_retrieval_config(
    agent_id: str,
    kb_id: int,
    config: dict[str, Any],
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_role(AccountRole.ADMIN)),
):
    """
    Update retrieval configuration for an agent-KB association.

    Args:
        agent_id: UUID of the agent
        kb_id: ID of the knowledge base
        config: New retrieval configuration
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Success confirmation
    """
    try:
        from src.models.agent_knowledge_base import AgentKnowledgeBase

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Find the association
        result = await db.execute(
            select(AgentKnowledgeBase).filter(
                AgentKnowledgeBase.agent_id == agent_uuid, AgentKnowledgeBase.knowledge_base_id == kb_id
            )
        )
        agent_kb = result.scalar_one_or_none()

        if not agent_kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not attached to this agent"
            )

        # Update configuration
        agent_kb.retrieval_config = config
        await db.commit()

        return AgentResponse(
            success=True, message="Retrieval configuration updated successfully", data={"retrieval_config": config}
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update retrieval config: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update configuration")


@agents_knowledge_bases_router.delete("/{agent_id}/knowledge-bases/{kb_id}", response_model=AgentResponse)
async def detach_knowledge_base(
    agent_id: str,
    kb_id: int,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_role(AccountRole.ADMIN)),
):
    """
    Detach a knowledge base from an agent.

    Args:
        agent_id: UUID of the agent
        kb_id: ID of the knowledge base
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Deletion confirmation
    """
    try:
        from src.models.agent_knowledge_base import AgentKnowledgeBase

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # SECURITY: Verify agent exists AND belongs to current tenant (prevents IDOR)
        result = await db.execute(select(Agent).filter(Agent.id == agent_uuid, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent with ID '{agent_id}' not found")

        # Find and delete the association — eagerly load knowledge_base to avoid lazy-load in async context
        result = await db.execute(
            select(AgentKnowledgeBase)
            .filter(AgentKnowledgeBase.agent_id == agent_uuid, AgentKnowledgeBase.knowledge_base_id == kb_id)
            .options(selectinload(AgentKnowledgeBase.knowledge_base))
        )
        agent_kb = result.scalar_one_or_none()

        if not agent_kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not attached to this agent"
            )

        kb_name = agent_kb.knowledge_base.name if agent_kb.knowledge_base else str(kb_id)
        await db.delete(agent_kb)
        await db.commit()

        return AgentResponse(success=True, message=f"Knowledge base '{kb_name}' detached from agent")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to detach knowledge base: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to detach knowledge base")
