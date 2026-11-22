"""
Knowledge API - let an API key list and create an agent's knowledge bases.

Documents are then managed with the existing knowledge-base document endpoints under
``/api/v1/knowledge-bases/{kb_id}/documents`` (upload, add text, list, view, delete, reprocess) and
``/api/v1/knowledge-bases/{kb_id}/search``. An API key can use those only for knowledge bases linked to
its own agent, with the ``knowledge:read`` or ``knowledge:write`` permission.

Authentication: ``Authorization: Bearer <agent api key>``.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.controllers.knowledge_bases import CreateKnowledgeBaseRequest, create_knowledge_base
from src.core.database import get_async_db
from src.middleware.agent_api_auth import require_permission
from src.models.agent import Agent
from src.models.agent_api_key import AgentApiKey
from src.models.agent_knowledge_base import AgentKnowledgeBase
from src.models.knowledge_base import KnowledgeBase, KnowledgeBaseStatus
from src.services.billing.plan_restriction_service import PlanRestrictionError, PlanRestrictionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public/agents/{agent_id}/knowledge-bases", tags=["Knowledge API"])


class KnowledgeBaseSummary(BaseModel):
    id: int
    name: str
    description: str | None
    document_count: int
    total_chunks: int
    is_active: bool


class CreateKnowledgeBaseBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


def _summary(kb: KnowledgeBase) -> KnowledgeBaseSummary:
    return KnowledgeBaseSummary(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        document_count=kb.total_documents or 0,
        total_chunks=kb.total_chunks or 0,
        is_active=kb.status == KnowledgeBaseStatus.ACTIVE,
    )


async def _own_agent(db: AsyncSession, api_key: AgentApiKey, agent_id: UUID) -> Agent:
    """The key's own agent. Another agent, even in the same tenant, is not reachable."""
    if api_key.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="API key not authorized for this agent")
    agent = await db.scalar(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == api_key.tenant_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("", response_model=list[KnowledgeBaseSummary])
async def list_agent_knowledge_bases(
    agent_id: UUID,
    api_key: AgentApiKey = Depends(require_permission("knowledge:read")),
    db: AsyncSession = Depends(get_async_db),
):
    """Knowledge bases linked to this agent. Requires permission: knowledge:read"""
    await _own_agent(db, api_key, agent_id)
    result = await db.execute(
        select(KnowledgeBase)
        .join(AgentKnowledgeBase, AgentKnowledgeBase.knowledge_base_id == KnowledgeBase.id)
        .where(AgentKnowledgeBase.agent_id == agent_id, KnowledgeBase.tenant_id == api_key.tenant_id)
        .order_by(KnowledgeBase.id)
    )
    return [_summary(kb) for kb in result.scalars().all()]


@router.post("", response_model=KnowledgeBaseSummary, status_code=201)
async def create_agent_knowledge_base(
    agent_id: UUID,
    body: CreateKnowledgeBaseBody,
    api_key: AgentApiKey = Depends(require_permission("knowledge:write")),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a knowledge base with the platform's default settings and link it to this agent.

    Upload documents to it afterwards. Requires permission: knowledge:write
    """
    await _own_agent(db, api_key, agent_id)
    try:
        await PlanRestrictionService(db).enforce_knowledge_base_limit(api_key.tenant_id)
    except PlanRestrictionError as err:
        raise HTTPException(status_code=403, detail=str(err)) from err

    created = await create_knowledge_base(
        CreateKnowledgeBaseRequest(name=body.name, description=body.description), api_key.tenant_id, db
    )
    db.add(AgentKnowledgeBase(agent_id=agent_id, knowledge_base_id=created.id))
    await db.commit()

    kb = await db.scalar(
        select(KnowledgeBase).where(KnowledgeBase.id == created.id, KnowledgeBase.tenant_id == api_key.tenant_id)
    )
    return _summary(kb)
