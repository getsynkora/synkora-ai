"""Celery tasks for on-demand eval runs."""

import asyncio
import logging
from uuid import UUID

from src.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.run_eval_dataset", soft_time_limit=1800, time_limit=2000)
def run_eval_dataset_task(self, *, run_id: str, dataset_id: str, agent_id: str, tenant_id: str) -> None:
    """Celery task wrapper for judge_service.run_eval_dataset."""
    from src.core.database import get_async_session_factory

    async def _run():
        session_factory = get_async_session_factory()
        async with session_factory() as db:
            from src.services.eval.judge_service import run_eval_dataset

            await run_eval_dataset(
                run_id=run_id,
                dataset_id=dataset_id,
                agent_id=UUID(agent_id),
                tenant_id=UUID(tenant_id),
                db=db,
            )

    try:
        asyncio.run(_run())
    except Exception as e:
        logger.error("run_eval_dataset_task failed: %s", e)

        # Mark the run as failed in ES (best-effort)
        async def _mark_failed():
            from src.config.settings import settings
            from src.services.eval.judge_service import _get_es_client

            es = await _get_es_client()
            await es.update(
                index=settings.agent_eval_runs_index,
                id=f"run:{run_id}",
                body={"doc": {"status": "failed"}},
            )

        try:
            asyncio.run(_mark_failed())
        except Exception:
            pass
        raise
