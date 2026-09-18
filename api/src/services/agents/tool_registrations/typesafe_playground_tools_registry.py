"""Registers internal_create_typesafe_playground for agents."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.services.agents.adk_tools import ToolRegistry

logger = logging.getLogger(__name__)


def register_typesafe_playground_tools(registry: ToolRegistry) -> None:
    from src.services.agents.internal_tools.typesafe_playground_tools import (
        internal_create_typesafe_playground,
    )

    async def internal_create_typesafe_playground_wrapper(
        config: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        return await internal_create_typesafe_playground(**kwargs, config=config)

    registry.register_tool(
        name="internal_create_typesafe_playground",
        description=(
            "Publish a public, standalone web page where anyone can paste in text and get a "
            "live AI judgment back, powered by TypeSafe's Jev model. Upload to S3, return a "
            "shareable URL. This is generic — define ANY judgment use case by writing your own "
            "questions (a red-flag checker, a resume rater, a vibe check, a lead scorer, "
            "whatever the user wants), not just the built-in profiles.\n\n"
            "Unlike internal_generate_dashboard, this page is interactive: visitors submit their "
            "own text and TypeSafe evaluates it live in the browser, every time — the page is not "
            "a static snapshot of one result.\n\n"
            "QUESTION TYPES (same format as internal_typesafe_evaluate):\n"
            '  noul:   {"type": "noul", "question": "Is this X?"} — yes/no probability\n'
            '  choice: {"type": "choice", "question": "Which?", "options": ["a","b"]} — pick one\n'
            '  score:  {"type": "score", "question": "How?", "levels": ["low","high"]} — graded score\n'
            "Max 6 questions per page — keep it focused for a good demo.\n\n"
            "WORKFLOW:\n"
            "1. Design 2-4 questions for the judgment the user wants (e.g. a 'red flag checker' "
            "might have: is_red_flag [noul], severity [score], category [choice]).\n"
            "2. Write a short, punchy title, description, and input_label.\n"
            "3. Call this tool. ALWAYS copy the exact 'url' from the result and share it as a "
            "clickable link — never omit it.\n\n"
            "VISIBILITY: use visibility='public' for anything meant to be shared/go viral (the whole "
            "point of a playground) — it gives a permanent link. Only use the default 'presigned' "
            "(7-day expiry) if the user explicitly wants a temporary/private link.\n\n"
            "The tenant must have a TypeSafe API key configured under Settings → Integrations → "
            "AI Evaluation, or the page's judgments will fail at request time (the page itself "
            "will still load)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Page heading, e.g. 'Red Flag Checker'",
                },
                "description": {
                    "type": "string",
                    "description": "One or two sentences explaining what the page judges",
                },
                "input_label": {
                    "type": "string",
                    "description": "Label shown above the textarea, e.g. 'Paste a dating bio'",
                },
                "questions": {
                    "type": "object",
                    "description": ("Map of answer_key -> question definition (noul/choice/score). Max 6 keys."),
                },
                "theme_emoji": {
                    "type": "string",
                    "description": "One emoji shown in the page header (default 🔮)",
                },
                "visibility": {
                    "type": "string",
                    "enum": ["presigned", "public"],
                    "description": "presigned = private 7-day URL (default). public = permanent direct URL.",
                },
            },
            "required": ["title", "description", "input_label", "questions"],
        },
        function=internal_create_typesafe_playground_wrapper,
        tool_category="typesafe",
    )

    logger.info("Registered internal_create_typesafe_playground tool")
