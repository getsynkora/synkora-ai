"""Celery tasks for data source synchronization."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from src.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="sync_data_source_task", bind=True, max_retries=3, default_retry_delay=300)
def sync_data_source_task(
    self,
    data_source_id: int,
    sync_job_id: int,
    full_sync: bool = False,
) -> dict[str, Any]:
    """
    Synchronize a data source with its external provider.

    The sync job row is created by the API before dispatching this task so
    the frontend can poll status immediately. This task runs the actual sync
    and updates the job row with the result.
    """
    logger.info(f"Starting sync for data source {data_source_id} (job={sync_job_id}, full={full_sync})")
    try:
        return asyncio.run(_run_sync(data_source_id, sync_job_id, full_sync))
    except Exception as exc:
        logger.error(f"Sync task failed for data source {data_source_id}: {exc}", exc_info=True)
        asyncio.run(_mark_sync_job_failed(sync_job_id, str(exc)))
        raise self.retry(exc=exc, countdown=300 * (2**self.request.retries))


@celery_app.task(name="sync_all_data_sources_task")
def sync_all_data_sources_task(tenant_id: str | None = None) -> dict[str, Any]:
    """Dispatch sync tasks for all active data sources."""
    return asyncio.run(_dispatch_all_syncs(tenant_id))


# ---------------------------------------------------------------------------
# Async implementations
# ---------------------------------------------------------------------------


async def _run_sync(data_source_id: int, sync_job_id: int, full_sync: bool) -> dict[str, Any]:
    from sqlalchemy import select

    from src.controllers.data_sources import get_connector
    from src.core.database import create_celery_async_session
    from src.models.data_source import DataSource, DataSourceStatus, DataSourceSyncJob, SyncStatus

    async with create_celery_async_session()() as db:
        from sqlalchemy.orm import selectinload

        result_ds = await db.execute(
            select(DataSource).options(selectinload(DataSource.oauth_app)).where(DataSource.id == data_source_id)
        )
        ds = result_ds.scalar_one_or_none()
        if not ds:
            raise ValueError(f"DataSource {data_source_id} not found")

        result_sj = await db.execute(select(DataSourceSyncJob).where(DataSourceSyncJob.id == sync_job_id))
        sync_job = result_sj.scalar_one_or_none()
        if not sync_job:
            raise ValueError(f"SyncJob {sync_job_id} not found")

        try:
            connector = get_connector(ds, db)
            result = await connector.sync(incremental=not full_sync)

            sync_job.status = SyncStatus.COMPLETED if result.get("status") != "failed" else SyncStatus.FAILED
            sync_job.completed_at = datetime.now(UTC)
            sync_job.documents_processed = result.get("documents_processed", 0)
            sync_job.documents_added = result.get("documents_added", 0)
            sync_job.documents_updated = result.get("documents_updated", 0)
            sync_job.documents_failed = result.get("documents_failed", 0)
            sync_job.error_message = "; ".join(result.get("errors", [])) or None

            ds.last_sync_at = datetime.now(UTC)
            ds.last_error = sync_job.error_message
            if sync_job.status == SyncStatus.COMPLETED:
                ds.status = DataSourceStatus.ACTIVE
            await db.commit()

            logger.info(f"Sync completed for data source {data_source_id}: {result.get('status')}")
            return {"success": True, "data_source_id": data_source_id, **result}

        except Exception as exc:
            sync_job.status = SyncStatus.FAILED
            sync_job.completed_at = datetime.now(UTC)
            sync_job.error_message = str(exc)[:500]
            ds.last_error = str(exc)[:500]
            await db.commit()
            raise


async def _mark_sync_job_failed(sync_job_id: int, error: str) -> None:
    """Best-effort update of sync job to FAILED when the task itself errors before _run_sync can."""
    try:
        from src.core.database import create_celery_async_session
        from src.models.data_source import DataSourceSyncJob, SyncStatus

        async with create_celery_async_session()() as db:
            sync_job = await db.get(DataSourceSyncJob, sync_job_id)
            if sync_job and sync_job.status == SyncStatus.IN_PROGRESS:
                sync_job.status = SyncStatus.FAILED
                sync_job.completed_at = datetime.now(UTC)
                sync_job.error_message = error[:500]
                await db.commit()
    except Exception as e:
        logger.error(f"Failed to mark sync job {sync_job_id} as failed: {e}")


async def _dispatch_all_syncs(tenant_id: str | None) -> dict[str, Any]:
    from sqlalchemy import select

    from src.core.database import create_celery_async_session
    from src.models.data_source import DataSource, DataSourceStatus, DataSourceSyncJob, SyncStatus

    async with create_celery_async_session()() as db:
        q = select(DataSource).where(DataSource.status == DataSourceStatus.ACTIVE)
        if tenant_id:
            from uuid import UUID

            q = q.where(DataSource.tenant_id == UUID(tenant_id))
        result = await db.execute(q)
        data_sources = result.scalars().all()

        queued, failed = 0, 0
        for ds in data_sources:
            try:
                sync_job = DataSourceSyncJob(
                    data_source_id=ds.id,
                    tenant_id=ds.tenant_id,
                    status=SyncStatus.IN_PROGRESS,
                    started_at=datetime.now(UTC),
                )
                db.add(sync_job)
                await db.flush()
                sync_data_source_task.delay(data_source_id=ds.id, sync_job_id=sync_job.id, full_sync=False)
                queued += 1
            except Exception as e:
                logger.error(f"Failed to queue sync for {ds.id}: {e}")
                failed += 1

        await db.commit()

    logger.info(f"Queued {queued} data source syncs")
    return {"queued": queued, "failed": failed}
