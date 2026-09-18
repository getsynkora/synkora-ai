"""Registers internal_create_typesafe_reflex_game for agents."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.services.agents.adk_tools import ToolRegistry

logger = logging.getLogger(__name__)


def register_typesafe_reflex_game_tools(registry: ToolRegistry) -> None:
    from src.services.agents.internal_tools.typesafe_reflex_game_tools import (
        internal_create_typesafe_reflex_game,
    )

    async def internal_create_typesafe_reflex_game_wrapper(
        config: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        return await internal_create_typesafe_reflex_game(**kwargs, config=config)

    registry.register_tool(
        name="internal_create_typesafe_reflex_game",
        description=(
            "Publish a public, timed 'guess the AI's verdict' reflex game, upload to S3, and "
            "return a shareable URL. A scenario flashes, the visitor has a few seconds to guess "
            "how TypeSafe's Jev model will judge it, then the real verdict reveals live and their "
            "score updates. Cycles through a shuffled playthrough, then shows a shareable final "
            "score. This is generic — invent any guessing game by writing your own scenario bank "
            "and question: 'ick or no ick' dating moments, 'red flag or not' texts, 'villain "
            "monologue or LinkedIn post', 'AI-generated or human', whatever fits what the user "
            "wants. Not hardcoded to one topic.\n\n"
            "YOU WRITE THE SCENARIOS: this is a fixed, curated content bank (5-20 short punchy "
            "strings, under 240 chars each) — not visitor-submitted text. Write them yourself, "
            "specific and funny/interesting, in the spirit of what the user asked for.\n\n"
            "GUESS QUESTION (what both the visitor and the AI answer about each scenario):\n"
            '  noul:   {"type": "noul", "question": "Is this X?"} — 2-button yes/no game\n'
            '  choice: {"type": "choice", "question": "Which?", "options": ["a","b"]} — '
            "2-4 option game\n\n"
            "REVEAL QUESTIONS (optional, max 3): extra noul/choice/score questions shown only "
            "after the guess, for flavor (e.g. a severity score or category) — same format as "
            "internal_typesafe_evaluate.\n\n"
            "For a noul guess question, set yes_label/no_label to match the game's theme (e.g. "
            "'Ick 😬' / 'No Ick 😌' instead of the generic 'Yes'/'No').\n\n"
            "WORKFLOW:\n"
            "1. Pick a topic and a guess question that fits what the user wants.\n"
            "2. Write 5-20 scenarios yourself — the content IS the game, make them good.\n"
            "3. Call this tool with visibility='public' (default) for a permanent, shareable link.\n"
            "4. ALWAYS copy the exact 'url' from the result and share it as a clickable link — "
            "never omit it.\n\n"
            "The tenant must have a TypeSafe API key configured under Settings → Integrations → "
            "AI Evaluation, or rounds will fail to reveal at request time (the page itself will "
            "still load)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Page heading, e.g. 'Ick or No Ick?'",
                },
                "description": {
                    "type": "string",
                    "description": "One or two sentences explaining the game",
                },
                "scenarios": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "5-20 short scenario strings (max 240 chars each) you write yourself.",
                },
                "guess_question": {
                    "type": "object",
                    "description": "The noul or choice question both visitor and AI answer per scenario.",
                },
                "reveal_questions": {
                    "type": "object",
                    "description": "Optional map of up to 3 extra noul/choice/score questions shown after each guess.",
                },
                "yes_label": {
                    "type": "string",
                    "description": "Button label for 'yes' when guess_question is noul type (default 'Yes')",
                },
                "no_label": {
                    "type": "string",
                    "description": "Button label for 'no' when guess_question is noul type (default 'No')",
                },
                "theme_emoji": {
                    "type": "string",
                    "description": "One emoji shown in the page header (default ⚡)",
                },
                "round_seconds": {
                    "type": "integer",
                    "description": "Seconds per round before auto-lock, 3-15 (default 6)",
                },
                "visibility": {
                    "type": "string",
                    "enum": ["presigned", "public"],
                    "description": "public (default) = permanent shareable link. presigned = private 7-day URL.",
                },
            },
            "required": ["title", "description", "scenarios", "guess_question"],
        },
        function=internal_create_typesafe_reflex_game_wrapper,
        tool_category="typesafe",
    )

    logger.info("Registered internal_create_typesafe_reflex_game tool")
