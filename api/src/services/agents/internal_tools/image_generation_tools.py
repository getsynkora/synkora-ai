"""
AI image generation tool.

Loads the image-generation LLM config from agent_metadata.image_generation_llm_config_id.
The config must be one of the agent's AgentLLMConfig rows whose model is an image model:
  - OpenAI image models (gpt-image-2, dall-e-3, dall-e-2)
  - Google Imagen models (imagen-3.0-generate-002, imagen-3.0-fast-generate-001)
  - xAI / Grok image model (grok-2-image)
"""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_SIZE_MAP: dict[str, tuple[str, str]] = {
    # alias → (openai_size, google_aspect_ratio)
    "square": ("1024x1024", "1:1"),
    "portrait": ("1024x1536", "9:16"),
    "landscape": ("1536x1024", "16:9"),
}

# gpt-image-2 quality values: low | medium | high
_GPT_IMAGE_2_QUALITY_MAP: dict[str, str] = {
    "standard": "medium",
    "hd": "high",
    "low": "low",
    "medium": "medium",
    "high": "high",
}

# dall-e-3 / dall-e-2 quality values: standard | hd
_DALLE_QUALITY_MAP: dict[str, str] = {
    "standard": "standard",
    "hd": "hd",
    "high": "hd",
    "medium": "standard",
    "low": "standard",
}

_GPT_IMAGE_2 = "gpt-image-2"
_IMAGEN_3 = "imagen-3.0-generate-002"
_GROK_IMAGE = "grok-2-image"

_GOOGLE_IMAGE_MODELS = {"imagen-3.0-generate-002", "imagen-3.0-fast-generate-001"}
_OPENAI_IMAGE_MODELS = {"gpt-image-2", "dall-e-3", "dall-e-2"}
_GROK_IMAGE_MODELS = {"grok-2-image"}
_GROK_PROVIDERS = {"xai", "grok", "x-ai", "x_ai"}


async def internal_generate_image(
    prompt: str,
    size: str = "square",
    quality: str = "standard",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate an AI image from a text prompt.

    Uses the image LLM config assigned to this agent via the Vision tab
    (agent_metadata.image_generation_llm_config_id).

    Args:
        prompt:  Detailed description of the image to generate.
        size:    "square" | "portrait" | "landscape".  Defaults to "square".
        quality: "standard" | "hd" | "low" | "medium" | "high".
        config:  Injected runtime config (contains _runtime_context).
    """
    config = config or {}
    runtime_context = config.get("_runtime_context")

    if not runtime_context:
        return {"success": False, "error": "No runtime context available."}

    # ------------------------------------------------------------------
    # Load the image-generation LLM config from agent_metadata
    # ------------------------------------------------------------------
    image_llm_config = await _load_image_llm_config(runtime_context)
    if "success" in image_llm_config:
        # _load_image_llm_config only sets "success" on error
        return image_llm_config

    model_name: str = image_llm_config["model_name"]
    provider: str = image_llm_config["provider"].lower()
    api_key: str = image_llm_config["api_key"]
    api_base: str | None = image_llm_config.get("api_base")

    size_key = size.lower().strip() if size.lower().strip() in _SIZE_MAP else "square"
    openai_size, google_ratio = _SIZE_MAP[size_key]
    quality_key = quality.lower().strip()
    # gpt-image-2 uses low/medium/high; dall-e-3/dall-e-2 use standard/hd
    if model_name == _GPT_IMAGE_2:
        mapped_quality = _GPT_IMAGE_2_QUALITY_MAP.get(quality_key, "medium")
    else:
        mapped_quality = _DALLE_QUALITY_MAP.get(quality_key, "standard")

    tenant_id = str(runtime_context.tenant_id)
    date_path = datetime.now(UTC).strftime("%Y-%m-%d")
    file_id = uuid.uuid4().hex[:12]

    if model_name in _GOOGLE_IMAGE_MODELS:
        return await _generate_google(
            prompt=prompt,
            api_key=api_key,
            aspect_ratio=google_ratio,
            model=model_name,
            tenant_id=tenant_id,
            date_path=date_path,
            file_id=file_id,
        )

    if model_name in _GROK_IMAGE_MODELS or provider in _GROK_PROVIDERS:
        return await _generate_openai_compat(
            prompt=prompt,
            api_key=api_key,
            api_base=api_base or "https://api.x.ai/v1",
            model=_GROK_IMAGE,
            size=openai_size,
            quality=None,
            tenant_id=tenant_id,
            date_path=date_path,
            file_id=file_id,
            provider_label="xai",
        )

    if model_name in _OPENAI_IMAGE_MODELS:
        return await _generate_openai_compat(
            prompt=prompt,
            api_key=api_key,
            api_base=api_base,
            model=model_name,
            size=openai_size,
            quality=mapped_quality,
            tenant_id=tenant_id,
            date_path=date_path,
            file_id=file_id,
            provider_label=provider,
        )

    return {
        "success": False,
        "error": (
            f"Model '{model_name}' is not a supported image generation model. "
            "Please assign a valid image model in the agent's Vision tab "
            "(e.g. gpt-image-2, dall-e-3, imagen-3.0-generate-002)."
        ),
    }


async def _load_image_llm_config(runtime_context: Any) -> dict[str, Any]:
    """Return a plain dict with model_name, provider, api_key, api_base.

    Queries the database for agent_metadata.image_generation_llm_config_id,
    then fetches the AgentLLMConfig row and decrypts the API key.
    Returns an error dict on failure.
    """
    agent_id = runtime_context.agent_id
    db_session = runtime_context.db_session

    if not agent_id or not db_session:
        return {"success": False, "error": "No agent context available for image generation."}

    try:
        from sqlalchemy import select

        from src.models.agent import Agent
        from src.models.agent_llm_config import AgentLLMConfig
        from src.services.agents.security import decrypt_value

        # Fetch agent metadata to get the assigned image LLM config ID
        result = await db_session.execute(select(Agent.agent_metadata).where(Agent.id == agent_id))
        agent_metadata: dict | None = result.scalar_one_or_none()

        if not agent_metadata:
            return {
                "success": False,
                "error": (
                    "No image generation model configured for this agent. Please assign one in the agent's Vision tab."
                ),
            }

        image_config_id = agent_metadata.get("image_generation_llm_config_id")
        if not image_config_id:
            return {
                "success": False,
                "error": (
                    "No image generation model configured for this agent. Please assign one in the agent's Vision tab."
                ),
            }

        # Fetch the AgentLLMConfig row
        cfg_result = await db_session.execute(
            select(AgentLLMConfig).where(
                AgentLLMConfig.id == image_config_id,
                AgentLLMConfig.agent_id == agent_id,
            )
        )
        llm_cfg = cfg_result.scalar_one_or_none()

        if not llm_cfg:
            return {
                "success": False,
                "error": (
                    f"Image generation LLM config '{image_config_id}' not found. "
                    "Please reassign it in the agent's Vision tab."
                ),
            }

        if not llm_cfg.enabled:
            return {
                "success": False,
                "error": f"Image generation LLM config '{llm_cfg.name}' is disabled.",
            }

        decrypted_key = decrypt_value(llm_cfg.api_key)
        if not decrypted_key:
            return {"success": False, "error": "Image generation LLM config has no API key."}

        return {
            "model_name": llm_cfg.model_name,
            "provider": llm_cfg.provider,
            "api_key": decrypted_key,
            "api_base": llm_cfg.api_base,
        }

    except Exception as exc:
        logger.error(f"Failed to load image LLM config: {exc}")
        return {"success": False, "error": f"Failed to load image generation config: {exc}"}


async def _generate_openai_compat(
    prompt: str,
    api_key: str,
    api_base: str | None,
    model: str,
    size: str,
    quality: str | None,
    tenant_id: str,
    date_path: str,
    file_id: str,
    provider_label: str = "openai",
) -> dict[str, Any]:
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=api_key,
            **({"base_url": api_base} if api_base else {}),
        )
        kwargs: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
        # gpt-image-2 does not accept response_format — it always returns b64_json.
        # dall-e-2 and dall-e-3 require it to receive base64 instead of a URL.
        if model != _GPT_IMAGE_2:
            kwargs["response_format"] = "b64_json"
        if quality is not None:
            kwargs["quality"] = quality

        response = await client.images.generate(**kwargs)  # type: ignore[arg-type]
        img = response.data[0]
        image_bytes = base64.b64decode(img.b64_json or "")
        revised_prompt: str = getattr(img, "revised_prompt", None) or prompt
    except Exception as exc:
        logger.error(f"Image generation failed ({provider_label}/{model}): {exc}")
        return {"success": False, "error": f"Image generation failed: {exc}"}

    url = _upload_to_s3(image_bytes, tenant_id, date_path, file_id, "png")
    return {
        "success": True,
        "url": url,
        "prompt": prompt,
        "revised_prompt": revised_prompt,
        "model": model,
        "provider": provider_label,
        "size": size,
    }


async def _generate_google(
    prompt: str,
    api_key: str,
    aspect_ratio: str,
    tenant_id: str,
    date_path: str,
    file_id: str,
    model: str = _IMAGEN_3,
) -> dict[str, Any]:
    try:
        import asyncio

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_images(
                model=model,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    safety_filter_level="block_only_high",
                ),
            ),
        )
        if not response.generated_images:
            return {"success": False, "error": "Google Imagen returned no images (prompt may have been filtered)"}
        image_bytes = response.generated_images[0].image.image_bytes
    except Exception as exc:
        logger.error(f"Google Imagen generation failed: {exc}")
        return {"success": False, "error": f"Google Imagen generation failed: {exc}"}

    url = _upload_to_s3(image_bytes, tenant_id, date_path, file_id, "png")
    return {
        "success": True,
        "url": url,
        "prompt": prompt,
        "revised_prompt": prompt,
        "model": model,
        "provider": "google",
        "size": aspect_ratio,
    }


def _upload_to_s3(image_bytes: bytes, tenant_id: str, date_path: str, file_id: str, ext: str) -> str | None:
    s3_key = f"generated-images/{tenant_id}/{date_path}/{file_id}.{ext}"
    try:
        from src.services.storage.s3_storage import get_s3_storage

        s3 = get_s3_storage()
        s3.upload_file(file_content=image_bytes, key=s3_key, content_type=f"image/{ext}")
        return s3.generate_presigned_url(key=s3_key, expiration=86400 * 7)
    except Exception:
        logger.debug("S3 upload skipped (not configured); returning None URL")
        return None
