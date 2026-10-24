"""Higgsfield Tools Registry — AI image and video generation."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_higgsfield_tools(registry) -> None:
    from src.services.agents.internal_tools.higgsfield_tools import (
        internal_higgsfield_check_request,
        internal_higgsfield_generate_image,
        internal_higgsfield_generate_video,
    )

    async def _image_wrapper(config: dict[str, Any] | None = None, **kwargs):
        return await internal_higgsfield_generate_image(
            prompt=kwargs.get("prompt", ""),
            aspect_ratio=kwargs.get("aspect_ratio"),
            model=kwargs.get("model"),
            config=config,
            runtime_context=config.get("_runtime_context") if config else None,
        )

    async def _video_wrapper(config: dict[str, Any] | None = None, **kwargs):
        return await internal_higgsfield_generate_video(
            prompt=kwargs.get("prompt", ""),
            image_url=kwargs.get("image_url"),
            duration=int(kwargs.get("duration", 5)),
            resolution=kwargs.get("resolution", "720p"),
            aspect_ratio=kwargs.get("aspect_ratio"),
            generate_audio=bool(kwargs.get("generate_audio", True)),
            model=kwargs.get("model"),
            config=config,
            runtime_context=config.get("_runtime_context") if config else None,
        )

    async def _check_wrapper(config: dict[str, Any] | None = None, **kwargs):
        return await internal_higgsfield_check_request(
            request_id=kwargs.get("request_id", ""),
            config=config,
            runtime_context=config.get("_runtime_context") if config else None,
        )

    registry.register_tool(
        name="internal_higgsfield_generate_image",
        description=(
            "Generate an AI image from a text prompt using Higgsfield (Soul and other image models). "
            "The image is rendered inline in the chat — do NOT embed the URL or markdown image syntax "
            "in your response; just describe what you generated. Be specific about subject, style, "
            "lighting and composition."
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Detailed description of the image."},
                "aspect_ratio": {
                    "type": "string",
                    "description": "Optional aspect ratio, e.g. '1:1', '16:9', '9:16', '3:4'.",
                },
                "model": {
                    "type": "string",
                    "description": "Optional Higgsfield model endpoint path. Omit to use the integration default.",
                },
            },
            "required": ["prompt"],
        },
        function=_image_wrapper,
        tool_category="image_generation",
    )

    registry.register_tool(
        name="internal_higgsfield_generate_video",
        description=(
            "Generate an AI video with Higgsfield (Seedance 2.0). Text-to-video from a prompt, or "
            "image-to-video when image_url (a publicly accessible URL) is provided. Takes 1-5 minutes. "
            "The video is rendered inline in the chat with a player — do NOT include the URL in your response; "
            "just describe what you generated. If the result says the generation is still running, call internal_higgsfield_check_request with the request_id."
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Describe the scene, motion and camera."},
                "image_url": {
                    "type": "string",
                    "description": "Optional public URL of a starting image to animate (image-to-video).",
                },
                "duration": {"type": "integer", "description": "Seconds, 4-15 (default 5)."},
                "resolution": {
                    "type": "string",
                    "enum": ["480p", "720p", "1080p", "4k"],
                    "description": "Output resolution (default 720p). Higher costs more.",
                },
                "aspect_ratio": {
                    "type": "string",
                    "enum": ["16:9", "4:3", "1:1", "3:4", "9:16", "21:9"],
                    "description": "Text-to-video only (default 16:9). Ignored when image_url is set.",
                },
                "generate_audio": {"type": "boolean", "description": "Generate audio track (default true)."},
                "model": {
                    "type": "string",
                    "description": "Optional Higgsfield model endpoint path. Omit to use the integration default.",
                },
            },
            "required": ["prompt"],
        },
        function=_video_wrapper,
        tool_category="video_generation",
    )

    registry.register_tool(
        name="internal_higgsfield_check_request",
        description=(
            "Check the status of a Higgsfield generation by request_id and return the image/video URLs "
            "once completed. Use after a generation reported it was still running."
        ),
        parameters={
            "type": "object",
            "properties": {"request_id": {"type": "string", "description": "request_id from an earlier call."}},
            "required": ["request_id"],
        },
        function=_check_wrapper,
    )

    logger.info("Registered 3 Higgsfield tools")
