"""
Higgsfield Tools — AI image and video generation via the Higgsfield API.

Auth: api_token stored in OAuthApp (provider='higgsfield', auth_method='api_token').
The token is "<API_KEY_ID>:<API_KEY_SECRET>" (sent as `Authorization: Key <id>:<secret>`).
Optional OAuthApp.config keys: image_model, video_model, image_to_video_model,
timeout_seconds (max wait per generation, default 300).

API flow: POST /{model_path} -> {request_id, status_url, cancel_url}; poll status_url until a
terminal status (completed | failed | nsfw | canceled). Docs: https://docs.higgsfield.ai
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.higgsfield.ai"

DEFAULT_IMAGE_MODEL = "higgsfield-ai/soul/v2/standard"
DEFAULT_VIDEO_MODEL = "bytedance/seedance-2.0/text-to-video"
DEFAULT_IMAGE_TO_VIDEO_MODEL = "bytedance/seedance-2.0/image-to-video"

_TERMINAL = {"completed", "failed", "nsfw", "canceled"}
_POLL_INTERVAL_S = 3.0


async def _get_higgsfield_config(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    """Resolve Higgsfield credentials from the OAuthApp linked to this agent's tool."""
    from sqlalchemy import select

    from src.core.database import get_async_session_factory
    from src.models.agent_tool import AgentTool
    from src.models.oauth_app import OAuthApp
    from src.services.agents.security import decrypt_value

    async with get_async_session_factory()() as db:
        result = await db.execute(
            select(AgentTool).filter(
                AgentTool.agent_id == runtime_context.agent_id,
                AgentTool.tool_name == tool_name,
                AgentTool.enabled,
            )
        )
        agent_tool = result.scalar_one_or_none()
        if not agent_tool or not agent_tool.oauth_app_id:
            raise ValueError(
                f"No integration configured for tool '{tool_name}'. "
                "Please connect a Higgsfield integration in Agent Tools settings."
            )

        result = await db.execute(
            select(OAuthApp).filter(
                OAuthApp.id == agent_tool.oauth_app_id,
                OAuthApp.provider.ilike("higgsfield"),
                OAuthApp.is_active,
            )
        )
        oauth_app = result.scalar_one_or_none()
        if not oauth_app:
            raise ValueError("No active Higgsfield integration found. Check your integrations.")
        if not oauth_app.api_token:
            raise ValueError("Higgsfield API key is missing. Edit the integration and add 'KEY_ID:KEY_SECRET'.")

        token = decrypt_value(oauth_app.api_token).strip()
        if ":" not in token:
            raise ValueError("Higgsfield API key must be in the form 'KEY_ID:KEY_SECRET'.")

        config = oauth_app.config or {}
        return {
            "token": token,
            "tenant_id": str(oauth_app.tenant_id) if getattr(oauth_app, "tenant_id", None) else "shared",
            "image_model": config.get("image_model") or DEFAULT_IMAGE_MODEL,
            "video_model": config.get("video_model") or DEFAULT_VIDEO_MODEL,
            "image_to_video_model": config.get("image_to_video_model") or DEFAULT_IMAGE_TO_VIDEO_MODEL,
            "timeout": float(config.get("timeout_seconds", 300)),
        }


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Key {token}", "Content-Type": "application/json", "Accept": "application/json"}


def _extract_media(status: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (image_urls, video_urls) from a completed status payload."""
    images = [i["url"] for i in status.get("images") or [] if isinstance(i, dict) and i.get("url")]
    video = status.get("video")
    videos = [video["url"]] if isinstance(video, dict) and video.get("url") else []
    return images, videos


async def _submit_and_wait(cfg: dict[str, Any], model_path: str, body: dict[str, Any]) -> dict[str, Any]:
    """Submit a generation request and poll until terminal or timeout."""
    model_path = model_path.strip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{API_BASE}/{model_path}", json=body, headers=_headers(cfg["token"]))
        if resp.status_code >= 400:
            return {
                "success": False,
                "error": f"Higgsfield rejected the request ({resp.status_code}): {resp.text[:500]}",
            }
        submitted = resp.json()
        request_id = submitted.get("request_id")
        status_url = submitted.get("status_url") or f"{API_BASE}/requests/{request_id}/status"

        deadline = time.monotonic() + cfg["timeout"]
        status: dict[str, Any] = submitted
        while time.monotonic() < deadline:
            await asyncio.sleep(_POLL_INTERVAL_S)
            poll = await client.get(status_url, headers=_headers(cfg["token"]))
            if poll.status_code >= 400:
                return {
                    "success": False,
                    "request_id": request_id,
                    "error": f"Status check failed ({poll.status_code})",
                }
            status = poll.json()
            if status.get("status") in _TERMINAL:
                break
        else:
            return {
                "success": False,
                "pending": True,
                "request_id": request_id,
                "error": (
                    "Generation is still running. Use internal_higgsfield_check_request with this "
                    "request_id to fetch the result later."
                ),
            }

    state = status.get("status")
    if state == "completed":
        return {"success": True, "request_id": request_id, "status": status}
    if state == "nsfw":
        return {"success": False, "request_id": request_id, "error": "Rejected by content moderation (nsfw)."}
    if state == "canceled":
        return {"success": False, "request_id": request_id, "error": "Generation was canceled."}
    return {
        "success": False,
        "request_id": request_id,
        "error": f"Generation failed: {status.get('error') or 'unknown'}",
    }


async def _persist(url: str, tenant_id: str, ext: str, content_type: str) -> str:
    """Copy generated media into our storage (Higgsfield URLs expire after ~7 days).

    Falls back to the original Higgsfield URL if storage isn't configured or the copy fails.
    """
    try:
        from src.services.storage.s3_storage import get_s3_storage

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        key = f"generated-media/{tenant_id}/{datetime.now(UTC):%Y-%m-%d}/{uuid.uuid4().hex[:12]}.{ext}"
        s3 = get_s3_storage()
        s3.upload_file(file_content=resp.content, key=key, content_type=content_type)
        return s3.generate_presigned_url(key=key, expiration=86400 * 7)
    except Exception as exc:
        logger.debug(f"Higgsfield media copy skipped: {exc}")
        return url


async def internal_higgsfield_generate_image(
    prompt: str,
    aspect_ratio: str | None = None,
    model: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """Generate an image from a text prompt with Higgsfield."""
    runtime_context = runtime_context or (config or {}).get("_runtime_context")
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    if not prompt or not prompt.strip():
        return {"success": False, "error": "prompt is required."}
    try:
        cfg = await _get_higgsfield_config(runtime_context, "internal_higgsfield_generate_image")
        body: dict[str, Any] = {"prompt": prompt}
        if aspect_ratio:
            body["aspect_ratio"] = aspect_ratio
        model_path = model or cfg["image_model"]
        result = await _submit_and_wait(cfg, model_path, body)
        if not result["success"]:
            return result
        images, _ = _extract_media(result["status"])
        if not images:
            return {"success": False, "request_id": result["request_id"], "error": "No image in the result."}
        url = await _persist(images[0], cfg["tenant_id"], "png", "image/png")
        return {
            "success": True,
            "url": url,
            "prompt": prompt,
            "revised_prompt": prompt,
            "model": model_path,
            "provider": "higgsfield",
            "size": aspect_ratio or "",
            "request_id": result["request_id"],
        }
    except Exception as e:
        logger.error(f"internal_higgsfield_generate_image failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_higgsfield_generate_video(
    prompt: str,
    image_url: str | None = None,
    duration: int = 5,
    resolution: str = "720p",
    aspect_ratio: str | None = None,
    generate_audio: bool = True,
    model: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """Generate a video from text, or animate an image when image_url is given."""
    runtime_context = runtime_context or (config or {}).get("_runtime_context")
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    if not (prompt and prompt.strip()) and not image_url:
        return {"success": False, "error": "prompt or image_url is required."}
    try:
        cfg = await _get_higgsfield_config(runtime_context, "internal_higgsfield_generate_video")
        body: dict[str, Any] = {
            "duration": max(4, min(15, int(duration))),
            "resolution": resolution,
            "generate_audio": generate_audio,
        }
        if prompt and prompt.strip():
            body["prompt"] = prompt
        if image_url:
            body["image_url"] = image_url  # image-to-video has no aspect_ratio field
            model_path = model or cfg["image_to_video_model"]
        else:
            if aspect_ratio:
                body["aspect_ratio"] = aspect_ratio
            model_path = model or cfg["video_model"]

        result = await _submit_and_wait(cfg, model_path, body)
        if not result["success"]:
            return result
        _, videos = _extract_media(result["status"])
        if not videos:
            return {"success": False, "request_id": result["request_id"], "error": "No video in the result."}
        url = await _persist(videos[0], cfg["tenant_id"], "mp4", "video/mp4")
        return {
            "success": True,
            "video_url": url,
            "prompt": prompt,
            "model": model_path,
            "provider": "higgsfield",
            "duration": body["duration"],
            "resolution": resolution,
            "request_id": result["request_id"],
        }
    except Exception as e:
        logger.error(f"internal_higgsfield_generate_video failed: {e}")
        return {"success": False, "error": str(e)}


async def internal_higgsfield_check_request(
    request_id: str,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """Check a previously submitted Higgsfield request and return its media if complete."""
    runtime_context = runtime_context or (config or {}).get("_runtime_context")
    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}
    try:
        cfg = await _get_higgsfield_config(runtime_context, "internal_higgsfield_check_request")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{API_BASE}/requests/{request_id}/status", headers=_headers(cfg["token"]))
        if resp.status_code >= 400:
            return {"success": False, "error": f"Status check failed ({resp.status_code})"}
        status = resp.json()
        state = status.get("status")
        if state in ("queued", "in_progress"):
            return {"success": True, "status": state, "request_id": request_id}
        if state != "completed":
            return {
                "success": False,
                "status": state,
                "request_id": request_id,
                "error": str(status.get("error") or state),
            }
        images, videos = _extract_media(status)
        return {"success": True, "status": state, "request_id": request_id, "image_urls": images, "video_urls": videos}
    except Exception as e:
        logger.error(f"internal_higgsfield_check_request failed: {e}")
        return {"success": False, "error": str(e)}
