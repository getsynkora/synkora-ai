"""Background task: generate AI video via Kling or Minimax and post result to conversation."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from src.celery_app import celery_app
from src.core.database import get_db
from src.models.video_generation_job import VideoGenerationJob, VideoJobStatus

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 15  # seconds between polls
_MAX_POLLS = 80  # 80 × 15s = 20 minutes max


def _load_job(job_id: str, db: Session) -> VideoGenerationJob | None:
    return db.query(VideoGenerationJob).filter(VideoGenerationJob.id == job_id).first()


async def _get_credentials(provider: str, tenant_id: Any) -> dict[str, str] | None:
    """Load OAuthApp credentials for the given provider."""
    from sqlalchemy import select

    from src.core.database import create_celery_async_session
    from src.models.oauth_app import OAuthApp
    from src.services.agents.security import decrypt_value

    factory = create_celery_async_session()
    async with factory() as db:
        # Prefer tenant-specific app, fall back to platform app
        for tid in [tenant_id, None]:
            stmt = (
                select(OAuthApp)
                .where(
                    OAuthApp.provider == provider,
                    OAuthApp.is_active.is_(True),
                    OAuthApp.tenant_id == tid if tid is not None else OAuthApp.tenant_id.is_(None),
                )
                .limit(1)
            )
            result = await db.execute(stmt)
            app = result.scalar_one_or_none()
            if app and app.api_token:
                creds: dict[str, str] = {"api_token": decrypt_value(app.api_token)}
                if app.config:
                    creds.update({k: str(v) for k, v in app.config.items()})
                return creds
    return None


async def _run_kling(job: VideoGenerationJob, creds: dict[str, str]) -> str:
    """Submit to Kling and poll until done. Returns video URL."""
    from src.services.video.kling_client import poll_task, submit_text_to_video

    access_key = creds["api_token"]
    secret_key = creds["secret_key"]

    task_id = await submit_text_to_video(
        prompt=job.prompt,
        duration=job.duration,
        access_key=access_key,
        secret_key=secret_key,
    )

    # Store external task ID
    await _update_external_task_id(str(job.id), task_id)

    for _ in range(_MAX_POLLS):
        await asyncio.sleep(_POLL_INTERVAL)
        result = await poll_task(task_id, access_key, secret_key)
        status = result["status"]
        if status == "succeed":
            url = result.get("video_url")
            if url:
                return url
            raise ValueError("Kling succeeded but no video URL returned")
        if status == "failed":
            raise ValueError(f"Kling task failed: {result.get('raw', {})}")

    raise TimeoutError("Kling video generation timed out after 20 minutes")


async def _run_minimax(job: VideoGenerationJob, creds: dict[str, str]) -> str:
    """Submit to Minimax Hailuo and poll until done. Returns video URL."""
    from src.services.video.minimax_client import poll_task, submit_text_to_video

    api_key = creds["api_token"]
    group_id = creds["group_id"]

    task_id = await submit_text_to_video(
        prompt=job.prompt,
        duration=job.duration,
        group_id=group_id,
        api_key=api_key,
    )

    await _update_external_task_id(str(job.id), task_id)

    for _ in range(_MAX_POLLS):
        await asyncio.sleep(_POLL_INTERVAL)
        result = await poll_task(task_id, group_id, api_key)
        status = result["status"]
        if status == "Success":
            url = result.get("video_url")
            if url:
                return url
            raise ValueError("Minimax succeeded but no video URL returned")
        if status == "Fail":
            raise ValueError(f"Minimax task failed: {result.get('raw', {})}")

    raise TimeoutError("Minimax video generation timed out after 20 minutes")


async def _update_external_task_id(job_id: str, external_task_id: str) -> None:
    import uuid as _uuid

    from sqlalchemy import select

    from src.core.database import create_celery_async_session
    from src.models.video_generation_job import VideoGenerationJob as VGJ

    factory = create_celery_async_session()
    async with factory() as db:
        result = await db.execute(select(VGJ).where(VGJ.id == _uuid.UUID(job_id)))
        job = result.scalar_one_or_none()
        if job:
            job.external_task_id = external_task_id
            await db.commit()


async def _upload_to_s3(video_url: str, tenant_id: str) -> str:
    """Download video from provider URL and upload to S3. Returns presigned URL or original URL."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(video_url, follow_redirects=True)
        resp.raise_for_status()
        video_bytes = resp.content

        date_path = datetime.now(UTC).strftime("%Y-%m-%d")
        file_id = uuid.uuid4().hex[:12]
        s3_key = f"generated-videos/{tenant_id}/{date_path}/{file_id}.mp4"

        from src.services.storage.s3_storage import get_s3_storage

        s3 = get_s3_storage()
        s3.upload_file(file_content=video_bytes, key=s3_key, content_type="video/mp4")
        return s3.generate_presigned_url(key=s3_key, expiration=86400 * 7)
    except Exception as exc:
        logger.warning("S3 upload failed, returning provider URL: %s", exc)
        return video_url


async def _save_result_as_message(job: VideoGenerationJob, content: str) -> None:
    from src.core.database import create_celery_async_session
    from src.services.agents.chat_service import ChatService

    factory = create_celery_async_session()
    async with factory() as db:
        await ChatService.save_assistant_message(
            conversation_id=job.conversation_id,
            content=content,
            db=db,
        )


async def _notify_conversation(job: VideoGenerationJob) -> None:
    try:
        from src.core.websocket import connection_manager

        await connection_manager.send_to_room(
            f"conversation:{job.conversation_id}",
            {
                "type": "video_job_completed",
                "data": {
                    "job_id": str(job.id),
                    "conversation_id": str(job.conversation_id),
                    "status": job.status.value,
                    "video_url": job.video_url,
                },
            },
        )
    except Exception as exc:
        logger.warning("WebSocket notify failed for video job %s: %s", job.id, exc)


@celery_app.task(
    bind=True,
    name="tasks.run_video_job",
    max_retries=0,
    soft_time_limit=1260,  # 21 minutes
    time_limit=1320,
)
def run_video_job(self, job_id: str) -> dict[str, Any]:
    """
    Generate an AI video for a VideoGenerationJob.

    Loads credentials from OAuthApp, submits to provider, polls until done,
    uploads to S3, saves result as assistant message, pushes WebSocket event.
    """
    db: Session = next(get_db())
    job = _load_job(job_id, db)

    if not job:
        logger.error("VideoGenerationJob %s not found", job_id)
        db.close()
        return {"status": "error", "reason": "job not found"}

    job.status = VideoJobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    db.add(job)
    db.commit()

    async def _run() -> None:
        try:
            creds = await _get_credentials(job.provider, job.tenant_id)
            if not creds:
                raise ValueError(f"No active {job.provider} integration found. Configure it at /oauth-apps.")

            if job.provider == "kling":
                raw_url = await _run_kling(job, creds)
            elif job.provider == "minimax_video":
                raw_url = await _run_minimax(job, creds)
            else:
                raise ValueError(f"Unsupported video provider: {job.provider}")

            video_url = await _upload_to_s3(raw_url, str(job.tenant_id))

            job.status = VideoJobStatus.COMPLETED
            job.video_url = video_url
            job.completed_at = datetime.now(UTC)

            provider_name = "Kling AI" if job.provider == "kling" else "Minimax Video"
            content = f"Your video is ready! Generated by {provider_name}.\n\n[Download Video]({video_url})"
            await _save_result_as_message(job, content)
            await _notify_conversation(job)

        except Exception as exc:
            logger.exception("VideoGenerationJob %s failed: %s", job_id, exc)
            job.status = VideoJobStatus.FAILED
            job.error = str(exc)
            job.completed_at = datetime.now(UTC)

            error_content = f"Video generation failed: {exc}"
            try:
                await _save_result_as_message(job, error_content)
                await _notify_conversation(job)
            except Exception:
                pass

    asyncio.run(_run())

    db.add(job)
    db.commit()
    db.close()

    return {"status": job.status.value, "job_id": job_id}
