"""Minimax Hailuo video generation client.

API base: https://api.minimaxi.com/v1
Auth: Bearer {api_key}, group_id in request body.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://api.minimaxi.com/v1"
_DEFAULT_MODEL = "video-01"


async def submit_text_to_video(
    prompt: str,
    duration: int,
    group_id: str,
    api_key: str,
    model: str = _DEFAULT_MODEL,
) -> str:
    """Submit a text-to-video job. Returns the Minimax task_id."""
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_BASE}/video_generation",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            params={"GroupId": group_id},
            json=payload,
        )
    resp.raise_for_status()
    data = resp.json()
    task_id = data.get("task_id")
    if not task_id:
        raise ValueError(f"Minimax submit: no task_id in response: {data}")
    logger.info("Minimax task submitted: %s", task_id)
    return task_id


async def poll_task(task_id: str, group_id: str, api_key: str) -> dict[str, Any]:
    """Poll a Minimax task. Returns dict with 'status' and 'video_url'."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE}/query/video_generation",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"task_id": task_id, "GroupId": group_id},
        )
    resp.raise_for_status()
    data = resp.json()
    status = data.get("status", "")  # Queueing | Processing | Success | Fail

    video_url = None
    if status == "Success":
        video_url = data.get("file_id") or data.get("video_url")
        # file_id needs a separate fetch; store as-is and resolve in task
        file_id = data.get("file_id")
        if file_id and not video_url:
            video_url = await _fetch_file_url(file_id, group_id, api_key)

    return {
        "status": status,
        "video_url": video_url,
        "raw": data,
    }


async def _fetch_file_url(file_id: str, group_id: str, api_key: str) -> str | None:
    """Resolve a Minimax file_id to a download URL."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{_BASE}/files/retrieve",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"file_id": file_id, "GroupId": group_id},
            )
        resp.raise_for_status()
        return resp.json().get("file", {}).get("download_url")
    except Exception as exc:
        logger.warning("Minimax file fetch failed for %s: %s", file_id, exc)
        return None
