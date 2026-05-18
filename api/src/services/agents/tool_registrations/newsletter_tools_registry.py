"""Newsletter Tools Registry

Registers the internal_render_newsletter tool with the ADK tool registry.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_newsletter_tools(registry) -> None:
    """Register newsletter rendering tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.newsletter_tools import (
        internal_render_newsletter,
    )

    async def internal_render_newsletter_wrapper(config: dict[str, Any] | None = None, **kwargs):
        return await internal_render_newsletter(
            newsletter_json=kwargs.get("newsletter_json", "{}"),
            edition=kwargs.get("edition", 1),
            template=kwargs.get("template", "editorial"),
            config=config,
        )

    registry.register_tool(
        name="internal_render_newsletter",
        description=(
            "Render a newsletter from structured JSON data into production-quality HTML using "
            "built-in newsletter templates such as editorial, minimal, or micromobility. "
            "The tool automatically enriches items with OG "
            "images, generates a PDF and a 1200\u00d7630 share image, uploads them to S3, and "
            "returns the final email HTML plus a subject line. "
            "Call this BEFORE internal_send_email. Pass the HTML and subject returned here "
            "directly to internal_send_email(html=true)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "newsletter_json": {
                    "type": "string",
                    "description": (
                        "JSON string of the structured newsletter payload. Must contain 'date' "
                        "(YYYY-MM-DD) and any combination of: hackernews, rss_news, "
                        "github_trending, papers, producthunt, youtube, twitter, "
                        "lead_why_it_matters, editors_take."
                    ),
                },
                "edition": {
                    "type": "integer",
                    "description": "Edition/volume number shown in the masthead (default: 1).",
                    "default": 1,
                },
                "template": {
                    "type": "string",
                    "description": (
                        "Template to use: 'editorial' (default, magazine-style), 'minimal' "
                        "(clean digest), or 'micromobility' (urban mobility / fleet style). "
                        "Tenants may also pass an S3 key for a custom template."
                    ),
                    "default": "editorial",
                },
            },
            "required": ["newsletter_json"],
        },
        function=internal_render_newsletter_wrapper,
    )

    logger.info("Registered 1 newsletter tool")
