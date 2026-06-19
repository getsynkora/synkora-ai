"""Register video pipeline tools: website scraper + AI video generator."""

from __future__ import annotations


def register_video_tools(registry) -> None:
    """Register video pipeline tools."""
    from src.services.agents.internal_tools.video_generate_tool import internal_generate_video
    from src.services.agents.internal_tools.video_scraper_tools import internal_scrape_website_for_video

    registry.register_tool(
        name="internal_scrape_website_for_video",
        description=(
            "Scrape a website URL and extract structured marketing content "
            "(headline, product benefits, CTA, brand color) to use as a video prompt.\n\n"
            "Call this first when the user provides a URL, then pass the result to "
            "internal_generate_video as the prompt."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL of the website to scrape (must start with https://)",
                },
            },
            "required": ["url"],
        },
        function=internal_scrape_website_for_video,
        tool_category="video",
    )

    registry.register_tool(
        name="internal_generate_video",
        description=(
            "Generate an AI video from a text prompt using Kling AI or Minimax Hailuo.\n\n"
            "Submits the job in the background — the finished video download link is "
            "delivered as a message when ready (usually 1–3 minutes).\n\n"
            "Requires a configured OAuth app for the chosen provider at /oauth-apps.\n\n"
            "Use internal_scrape_website_for_video first if the user provides a URL."
        ),
        parameters={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Detailed description of the video to generate",
                },
                "provider": {
                    "type": "string",
                    "enum": ["kling", "minimax_video"],
                    "default": "kling",
                    "description": "Video generation provider",
                },
                "duration": {
                    "type": "integer",
                    "default": 5,
                    "description": "Video duration in seconds (1–10)",
                },
            },
            "required": ["prompt"],
        },
        function=internal_generate_video,
        tool_category="video",
    )
