"""Registers internal_create_typesafe_story_game for agents."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.services.agents.adk_tools import ToolRegistry

logger = logging.getLogger(__name__)


def register_typesafe_story_game_tools(registry: ToolRegistry) -> None:
    from src.services.agents.internal_tools.typesafe_story_game_tools import (
        internal_create_typesafe_story_game,
    )

    async def internal_create_typesafe_story_game_wrapper(
        config: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        return await internal_create_typesafe_story_game(**kwargs, config=config)

    registry.register_tool(
        name="internal_create_typesafe_story_game",
        description=(
            "Publish a public, free-text branching mini-game and return a shareable URL. "
            "Unlike internal_create_typesafe_reflex_game (which judges a fixed scenario bank — "
            "visitors guess the AI's verdict on pre-written content), this game has the visitor "
            "TYPE their own response each turn. TypeSafe judges whatever they wrote live — several "
            "questions in parallel against the same message — and a meter (tension, trust, "
            "patience, whatever fits) shifts toward a win or loss based on the judgment. This is "
            "the best demo of TypeSafe actually understanding novel text, not matching a fixed "
            "answer key.\n\n"
            "Generic over any scenario: a tense traffic stop, a job interview going sideways, "
            "talking down an angry customer, defusing an argument — write your own setup, stakes, "
            "and judge questions to fit what the user wants.\n\n"
            "HOW THE METER WORKS:\n"
            "- meter_start/success_threshold/failure_threshold are 0-100. success_threshold must "
            "be ABOVE meter_start, failure_threshold must be BELOW it — the meter always means "
            "'how well it's going', high = winning.\n"
            "- meter_question_key points at one of your judge_questions (must be type noul or "
            "score — choice has no inherent direction) whose value drives the meter each turn.\n"
            "- meter_direction: 'positive' if a high judged value should push the meter UP (e.g. "
            "an is_effective question), 'negative' if it should push it DOWN (e.g. an "
            "is_aggressive question).\n"
            "- You can include up to 4 judge_questions total — the others are shown as feedback "
            "after each turn but don't move the meter.\n\n"
            "WORKFLOW:\n"
            "1. Write a punchy scenario_intro (the opening situation) and pick real stakes.\n"
            "2. Design judge_questions: one that drives the meter, plus 1-3 flavor questions "
            "(e.g. a 'tone' choice) shown as per-turn feedback.\n"
            "3. Write success_ending, failure_ending, and stalemate_ending — each should feel "
            "like a real payoff for how the conversation went.\n"
            "4. Call this tool. ALWAYS copy the exact 'url' from the result and share it as a "
            "clickable link — never omit it.\n\n"
            "The tenant must have a TypeSafe API key configured under Settings → Integrations → "
            "AI Evaluation, or turns will fail to judge at request time (the page itself will "
            "still load)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Page heading, e.g. 'Talk Your Way Out'"},
                "description": {"type": "string", "description": "One or two sentences setting expectations"},
                "scenario_intro": {
                    "type": "string",
                    "description": "The opening situation shown once at the top (max 600 chars)",
                },
                "input_label": {
                    "type": "string",
                    "description": "Label above the textarea, e.g. 'What do you say?'",
                },
                "meter_label": {
                    "type": "string",
                    "description": "Name of the meter, e.g. 'Tension' or 'Trust' — high value always means winning",
                },
                "judge_questions": {
                    "type": "object",
                    "description": "Map of up to 4 {key: question_def} (noul/choice/score) — every turn is judged against all of these in one call.",
                },
                "meter_question_key": {
                    "type": "string",
                    "description": "Which key in judge_questions drives the meter (must be type noul or score)",
                },
                "meter_direction": {
                    "type": "string",
                    "enum": ["positive", "negative"],
                    "description": "'positive' = high judged value pushes meter up. 'negative' = high judged value pushes meter down.",
                },
                "success_ending": {
                    "type": "string",
                    "description": "Shown when the meter hits success_threshold (max 300 chars)",
                },
                "failure_ending": {
                    "type": "string",
                    "description": "Shown when the meter hits failure_threshold (max 300 chars)",
                },
                "stalemate_ending": {
                    "type": "string",
                    "description": "Shown if max_turns is reached with neither threshold hit",
                },
                "meter_start": {"type": "integer", "description": "Starting meter value, 0-100 (default 50)"},
                "success_threshold": {
                    "type": "integer",
                    "description": "Win value, must be > meter_start (default 85)",
                },
                "failure_threshold": {
                    "type": "integer",
                    "description": "Lose value, must be < meter_start (default 15)",
                },
                "meter_swing": {"type": "integer", "description": "Max meter change per turn, 5-40 (default 20)"},
                "max_turns": {"type": "integer", "description": "Turn cap before a stalemate ending, 3-15 (default 8)"},
                "theme_emoji": {"type": "string", "description": "One emoji shown in the page header (default 🎭)"},
                "visibility": {
                    "type": "string",
                    "enum": ["presigned", "public"],
                    "description": "public (default) = shareable link, valid up to 7 days. presigned = same, framed as private/temporary.",
                },
            },
            "required": [
                "title",
                "description",
                "scenario_intro",
                "input_label",
                "meter_label",
                "judge_questions",
                "meter_question_key",
                "meter_direction",
                "success_ending",
                "failure_ending",
                "stalemate_ending",
            ],
        },
        function=internal_create_typesafe_story_game_wrapper,
        tool_category="typesafe",
    )

    logger.info("Registered internal_create_typesafe_story_game tool")
