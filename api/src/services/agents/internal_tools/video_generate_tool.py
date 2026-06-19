"""
Video Generation Tool — submits an async AI video generation job via Kling AI
or Minimax Hailuo. Credentials are read from the OAuthApp integration.
Result is delivered as an assistant message + WebSocket event when done.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_PROVIDER_NAMES = {
    "kling": "Kling AI",
    "minimax_video": "Minimax Video",
}


async def internal_generate_video(
    prompt: str,
    provider: str = "kling",
    duration: int = 5,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Submit an AI video generation job in the background.

    Looks up the provider's OAuthApp credentials, creates a VideoGenerationJob,
    and dispatches a Celery task. Returns immediately with a job ID.
    The finished video is delivered as an assistant message when ready.

    Args:
        prompt:   Description of the video to generate.
        provider: "kling" (default) or "minimax_video".
        duration: Video length in seconds (1–10, default 5).
        config:   Runtime config dict containing _runtime_context.

    Returns:
        {"success": True, "job_id": str, "message": str}
        or {"success": False, "error": str}
    """
    config = config or {}
    runtime_context = config.get("_runtime_context")

    if not runtime_context:
        return {"success": False, "error": "No runtime context available"}

    if not runtime_context.conversation_id:
        return {"success": False, "error": "Video generation requires an active conversation"}

    if provider not in _PROVIDER_NAMES:
        return {
            "success": False,
            "error": f"Unknown provider '{provider}'. Supported: kling, minimax_video",
        }

    duration = max(1, min(duration, 10))

    # Verify credentials exist before creating the job
    creds = await _resolve_credentials(provider, runtime_context)
    if not creds:
        provider_name = _PROVIDER_NAMES[provider]
        return {
            "success": False,
            "error": (
                f"No active {provider_name} integration found. "
                f"Please configure it at /oauth-apps — add a new app with "
                f"provider '{provider}' and auth method 'api_token'."
            ),
        }

    job = await _create_job(prompt, provider, duration, runtime_context)

    # Dispatch Celery task
    from src.tasks.video_tasks import run_video_job

    run_video_job.delay(str(job.id))

    provider_name = _PROVIDER_NAMES[provider]
    return {
        "success": True,
        "job_id": str(job.id),
        "message": (
            f"Video generation started with {provider_name}. "
            f"I'll send you the download link when it's ready — usually 1–3 minutes."
        ),
    }


async def _resolve_credentials(provider: str, runtime_context: Any) -> dict | None:
    """Check that an active OAuthApp exists for the provider."""
    from sqlalchemy import select

    from src.models.oauth_app import OAuthApp

    db = runtime_context.db_session
    tenant_id = runtime_context.tenant_id

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
            return {"found": True}
    return None


async def _create_job(
    prompt: str,
    provider: str,
    duration: int,
    runtime_context: Any,
) -> Any:
    from src.models.video_generation_job import VideoGenerationJob, VideoJobStatus

    db = runtime_context.db_session
    job = VideoGenerationJob(
        tenant_id=runtime_context.tenant_id,
        agent_id=runtime_context.agent_id,
        conversation_id=runtime_context.conversation_id,
        provider=provider,
        prompt=prompt,
        duration=duration,
        status=VideoJobStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job
