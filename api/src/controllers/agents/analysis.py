"""
Analysis Job endpoints.

GET /agents/{agent_slug}/analysis-jobs               — list jobs for a conversation
GET /agents/{agent_slug}/analysis-jobs/{job_id}      — job detail + result
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.analysis_job import AnalysisJob
from src.schemas.analysis_job import AnalysisJobDetail, AnalysisJobListItem

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_JOBS = 50


async def _get_agent(agent_slug: str, tenant_id: UUID, db: AsyncSession) -> Agent:
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


async def _list_jobs(
    tenant_id: UUID, agent_id: UUID, conversation_id: UUID | None, db: AsyncSession
) -> list[AnalysisJob]:
    stmt = (
        select(AnalysisJob)
        .where(AnalysisJob.tenant_id == tenant_id, AnalysisJob.agent_id == agent_id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(_MAX_JOBS)
    )
    if conversation_id:
        stmt = stmt.where(AnalysisJob.conversation_id == conversation_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{agent_slug}/analysis-jobs", response_model=list[AnalysisJobListItem])
async def list_analysis_jobs(
    agent_slug: str,
    conversation_id: UUID | None = Query(default=None),
    tenant_id: UUID = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    agent = await _get_agent(agent_slug, tenant_id, db)
    jobs = await _list_jobs(tenant_id, agent.id, conversation_id, db)
    return [AnalysisJobListItem.model_validate(j) for j in jobs]


@router.get("/{agent_slug}/analysis-jobs/{job_id}", response_model=AnalysisJobDetail)
async def get_analysis_job(
    agent_slug: str,
    job_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    agent = await _get_agent(agent_slug, tenant_id, db)
    result = await db.execute(
        select(AnalysisJob).where(
            AnalysisJob.id == job_id,
            AnalysisJob.tenant_id == tenant_id,
            AnalysisJob.agent_id == agent.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found")
    return AnalysisJobDetail.model_validate(job)
