"""
Eval API endpoints.

Mounts at /api/v1/agents and provides:
- POST /{slug}/feedback         — per-message thumbs up/down
- POST /{slug}/outcome          — explicit session outcome ("Did this help?")
- GET/POST /{slug}/eval/datasets
- GET/PUT/DELETE /{slug}/eval/datasets/{dataset_id}
- POST /{slug}/eval/datasets/{dataset_id}/cases
- DELETE /{slug}/eval/datasets/{dataset_id}/cases/{case_id}
- POST /{slug}/eval/datasets/{dataset_id}/run
- GET /{slug}/eval/runs
- GET /{slug}/eval/runs/{run_id}
- GET /{slug}/eval/runs/{run_id}/results
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_agent(agent_slug: str, tenant_id, db: AsyncSession) -> Agent:
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class FeedbackRequest(BaseModel):
    message_id: str
    channel: str = Field(default="console", description="widget/slack/whatsapp/teams/console")
    rating: int = Field(..., description="1 for thumbs up, -1 for thumbs down")
    comment: str | None = None
    trace_id: str | None = None


class OutcomeRequest(BaseModel):
    conversation_id: str
    helpful: bool
    trace_id: str | None = None


class DatasetCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""


class DatasetUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class CaseCreateRequest(BaseModel):
    input: str = Field(..., min_length=1)
    expected_criteria: str = Field(..., min_length=1)
    tags: list[str] = []


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


@router.post("/{agent_slug}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_feedback(
    agent_slug: str,
    body: FeedbackRequest,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Record per-message user feedback (thumbs up/down)."""
    agent = await _get_agent(agent_slug, tenant_id, db)

    from src.services.eval.feedback_service import record_feedback

    record_feedback(
        message_id=body.message_id,
        agent_id=agent.id,
        tenant_id=tenant_id,
        channel=body.channel,
        rating=body.rating,
        comment=body.comment,
        trace_id=body.trace_id,
    )


# ---------------------------------------------------------------------------
# Outcome
# ---------------------------------------------------------------------------


@router.post("/{agent_slug}/outcome", status_code=status.HTTP_204_NO_CONTENT)
async def submit_outcome(
    agent_slug: str,
    body: OutcomeRequest,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Record explicit session outcome from 'Did this help?' prompt."""
    agent = await _get_agent(agent_slug, tenant_id, db)

    from src.services.eval.outcome_service import record_explicit_outcome

    record_explicit_outcome(
        conversation_id=uuid.UUID(body.conversation_id),
        agent_id=agent.id,
        tenant_id=tenant_id,
        helpful=body.helpful,
        trace_id=body.trace_id,
    )


# ---------------------------------------------------------------------------
# Eval datasets
# ---------------------------------------------------------------------------


@router.get("/{agent_slug}/eval/datasets")
async def list_datasets(
    agent_slug: str,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    agent = await _get_agent(agent_slug, tenant_id, db)
    from src.services.eval.dataset_service import list_datasets as svc_list

    datasets = await svc_list(agent_id=agent.id, tenant_id=tenant_id)
    return {"datasets": datasets, "total": len(datasets)}


@router.post("/{agent_slug}/eval/datasets", status_code=status.HTTP_201_CREATED)
async def create_dataset(
    agent_slug: str,
    body: DatasetCreateRequest,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    agent = await _get_agent(agent_slug, tenant_id, db)
    from src.services.eval.dataset_service import create_dataset as svc_create

    return await svc_create(agent_id=agent.id, tenant_id=tenant_id, name=body.name, description=body.description)


@router.get("/{agent_slug}/eval/datasets/{dataset_id}")
async def get_dataset(
    agent_slug: str,
    dataset_id: str,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    await _get_agent(agent_slug, tenant_id, db)
    from src.services.eval.dataset_service import get_dataset as svc_get

    doc = await svc_get(dataset_id=dataset_id, tenant_id=tenant_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return doc


@router.put("/{agent_slug}/eval/datasets/{dataset_id}")
async def update_dataset(
    agent_slug: str,
    dataset_id: str,
    body: DatasetUpdateRequest,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    await _get_agent(agent_slug, tenant_id, db)
    from src.services.eval.dataset_service import update_dataset as svc_update

    doc = await svc_update(dataset_id=dataset_id, tenant_id=tenant_id, name=body.name, description=body.description)
    if not doc:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return doc


@router.delete("/{agent_slug}/eval/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    agent_slug: str,
    dataset_id: str,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    await _get_agent(agent_slug, tenant_id, db)
    from src.services.eval.dataset_service import delete_dataset as svc_delete

    deleted = await svc_delete(dataset_id=dataset_id, tenant_id=tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


@router.post("/{agent_slug}/eval/datasets/{dataset_id}/cases", status_code=status.HTTP_201_CREATED)
async def create_case(
    agent_slug: str,
    dataset_id: str,
    body: CaseCreateRequest,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    agent = await _get_agent(agent_slug, tenant_id, db)
    from src.services.eval.dataset_service import create_case as svc_create

    return await svc_create(
        dataset_id=dataset_id,
        agent_id=agent.id,
        tenant_id=tenant_id,
        input=body.input,
        expected_criteria=body.expected_criteria,
        tags=body.tags,
    )


@router.get("/{agent_slug}/eval/datasets/{dataset_id}/cases")
async def list_cases(
    agent_slug: str,
    dataset_id: str,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    await _get_agent(agent_slug, tenant_id, db)
    from src.services.eval.dataset_service import list_cases as svc_list

    cases = await svc_list(dataset_id=dataset_id, tenant_id=tenant_id)
    return {"cases": cases, "total": len(cases)}


@router.delete("/{agent_slug}/eval/datasets/{dataset_id}/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    agent_slug: str,
    dataset_id: str,
    case_id: str,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    await _get_agent(agent_slug, tenant_id, db)
    from src.services.eval.dataset_service import delete_case as svc_delete

    deleted = await svc_delete(case_id=case_id, tenant_id=tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case not found")


# ---------------------------------------------------------------------------
# Eval runs
# ---------------------------------------------------------------------------


@router.post("/{agent_slug}/eval/datasets/{dataset_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_eval_run(
    agent_slug: str,
    dataset_id: str,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Trigger an on-demand eval run. Returns run_id immediately; run executes in background."""
    agent = await _get_agent(agent_slug, tenant_id, db)

    # Verify dataset exists and belongs to this tenant
    from src.services.eval.dataset_service import get_dataset

    dataset = await get_dataset(dataset_id=dataset_id, tenant_id=tenant_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    run_id = str(uuid.uuid4())

    from src.tasks.eval_tasks import run_eval_dataset_task

    run_eval_dataset_task.delay(
        run_id=run_id,
        dataset_id=dataset_id,
        agent_id=str(agent.id),
        tenant_id=str(tenant_id),
    )

    return {"run_id": run_id, "status": "pending", "dataset_id": dataset_id}


@router.get("/{agent_slug}/eval/runs")
async def list_runs(
    agent_slug: str,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    agent = await _get_agent(agent_slug, tenant_id, db)
    from src.services.eval.judge_service import list_runs as svc_list

    runs = await svc_list(agent_id=agent.id, tenant_id=tenant_id)
    return {"runs": runs, "total": len(runs)}


@router.get("/{agent_slug}/eval/runs/{run_id}")
async def get_run(
    agent_slug: str,
    run_id: str,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    await _get_agent(agent_slug, tenant_id, db)
    from src.services.eval.judge_service import get_run as svc_get

    run = await svc_get(run_id=run_id, tenant_id=tenant_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{agent_slug}/eval/runs/{run_id}/results")
async def get_run_results(
    agent_slug: str,
    run_id: str,
    tenant_id=Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    await _get_agent(agent_slug, tenant_id, db)
    from src.services.eval.judge_service import get_run_results as svc_get

    results = await svc_get(run_id=run_id, tenant_id=tenant_id)
    return {"results": results, "total": len(results)}
