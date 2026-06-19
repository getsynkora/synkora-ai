"""Kling AI video generation client.

Auth: JWT signed with access_key (iss) + secret_key (HMAC-SHA256), 30s expiry.
API base: https://api.klingai.com
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://api.klingai.com"
_DEFAULT_MODEL = "kling-v1-5"


def _make_jwt(access_key: str, secret_key: str) -> str:
    """Generate a short-lived JWT for Kling API authentication."""
    import base64
    import hashlib
    import hmac
    import json

    now = int(time.time())
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = (
        base64.urlsafe_b64encode(json.dumps({"iss": access_key, "exp": now + 1800, "nbf": now - 5}).encode())
        .rstrip(b"=")
        .decode()
    )
    signing_input = f"{header}.{payload}"
    sig = (
        base64.urlsafe_b64encode(hmac.new(secret_key.encode(), signing_input.encode(), hashlib.sha256).digest())
        .rstrip(b"=")
        .decode()
    )
    return f"{signing_input}.{sig}"


async def submit_text_to_video(
    prompt: str,
    duration: int,
    access_key: str,
    secret_key: str,
    model: str = _DEFAULT_MODEL,
) -> str:
    """Submit a text-to-video job. Returns the Kling task_id."""
    token = _make_jwt(access_key, secret_key)
    payload: dict[str, Any] = {
        "model_name": model,
        "prompt": prompt,
        "duration": str(min(duration, 10)),
        "mode": "std",
        "aspect_ratio": "9:16",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_BASE}/v1/videos/text2video",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
    resp.raise_for_status()
    data = resp.json()
    task_id = data.get("data", {}).get("task_id") or data.get("task_id")
    if not task_id:
        raise ValueError(f"Kling submit: no task_id in response: {data}")
    logger.info("Kling task submitted: %s", task_id)
    return task_id


async def poll_task(task_id: str, access_key: str, secret_key: str) -> dict[str, Any]:
    """Poll a Kling task. Returns dict with 'status' and 'video_url'."""
    token = _make_jwt(access_key, secret_key)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE}/v1/videos/text2video/{task_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    resp.raise_for_status()
    data = resp.json().get("data", {})
    task_status = data.get("task_status", "")  # processing | succeed | failed

    video_url = None
    if task_status == "succeed":
        works = data.get("task_result", {}).get("videos", [])
        if works:
            video_url = works[0].get("url")

    return {
        "status": task_status,
        "video_url": video_url,
        "raw": data,
    }
