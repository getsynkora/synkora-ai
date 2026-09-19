"""
TypeSafe AI Story Game — a free-text branching mini-game. Unlike the reflex
game (which judges a fixed scenario bank), the player types their own
response each turn, and TypeSafe judges it live — multiple questions in
parallel against the same state — driving a visible meter (tension, trust,
patience, whatever the agent names it) toward a win or loss.

This is the demo that actually shows TypeSafe understanding novel text, not
matching against a fixed answer key. Generic over any scenario: a traffic
stop, a job interview, a breakup conversation, a hostage negotiation —
whatever the agent is asked to build.

Like the other two TypeSafe tools, the spec is stored as JSON in S3 and the
public evaluate endpoint reads it back by page_id at request time. The meter
math (delta, clamping, win/loss detection) is computed server-side per turn
so there's one source of truth — the client only ever renders what the
server returns.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from src.services.storage.s3_storage import get_s3_storage

logger = logging.getLogger(__name__)

_METER_DRIVER_TYPES = {"noul", "score"}
_VALID_QUESTION_TYPES = {"noul", "choice", "score"}
_VALID_DIRECTIONS = {"positive", "negative"}

_MAX_JUDGE_QUESTIONS = 4
_MIN_TURNS = 3
_MAX_TURNS_CAP = 15
_DEFAULT_MAX_TURNS = 8
_MIN_METER_SWING = 5
_MAX_METER_SWING = 40
_DEFAULT_METER_SWING = 20

_MAX_TITLE_LEN = 100
_MAX_DESCRIPTION_LEN = 300
_MAX_SCENARIO_INTRO_LEN = 600
_MAX_INPUT_LABEL_LEN = 80
_MAX_METER_LABEL_LEN = 40
_MAX_ENDING_LEN = 300
MAX_STORY_MESSAGE_LEN = 500  # per-turn player message, shared with the public endpoint

_S3_PREFIX = "typesafe_story_games/pages"


def spec_key(page_id: str) -> str:
    return f"{_S3_PREFIX}/{page_id}.json"


def html_key(page_id: str) -> str:
    return f"{_S3_PREFIX}/{page_id}.html"


def _validate_judge_questions(questions: dict[str, dict[str, Any]], meter_question_key: str) -> str | None:
    if not questions:
        return "judge_questions cannot be empty"
    if len(questions) > _MAX_JUDGE_QUESTIONS:
        return f"Too many judge_questions ({len(questions)}) — max {_MAX_JUDGE_QUESTIONS}"
    for key, q in questions.items():
        q_type = q.get("type", "noul")
        if q_type not in _VALID_QUESTION_TYPES:
            return f"Invalid type '{q_type}' for judge_questions['{key}']"
        if not (q.get("question") or "").strip():
            return f"judge_questions['{key}'] is missing 'question' text"
        if q_type == "choice" and not q.get("options"):
            return f"judge_questions['{key}'] (choice) must include 'options'"
        if q_type == "score" and not q.get("levels"):
            return f"judge_questions['{key}'] (score) must include 'levels'"

    if meter_question_key not in questions:
        return f"meter_question_key '{meter_question_key}' must be a key in judge_questions"
    driver_type = questions[meter_question_key].get("type", "noul")
    if driver_type not in _METER_DRIVER_TYPES:
        return f"meter_question_key must point to a noul or score question, got '{driver_type}'"
    return None


async def internal_create_typesafe_story_game(
    title: str,
    description: str,
    scenario_intro: str,
    input_label: str,
    meter_label: str,
    judge_questions: dict[str, dict[str, Any]],
    meter_question_key: str,
    meter_direction: str,
    success_ending: str,
    failure_ending: str,
    stalemate_ending: str,
    meter_start: int = 50,
    success_threshold: int = 85,
    failure_threshold: int = 15,
    meter_swing: int = _DEFAULT_METER_SWING,
    max_turns: int = _DEFAULT_MAX_TURNS,
    theme_emoji: str = "🎭",
    visibility: str = "public",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish a public, free-text branching mini-game and return its URL.

    Unlike internal_create_typesafe_reflex_game (fixed scenario bank, guess
    the AI's verdict), the player TYPES their own response each turn, and
    TypeSafe judges it live — several questions in parallel — moving a
    meter toward success or failure. This is the demo that shows TypeSafe
    actually understanding novel text, not matching pre-written content.

    Generic over any scenario: write your own setup, stakes, meter, and
    judge questions — a traffic stop, a tense job interview, talking down
    an angry customer, whatever fits what the user asked for.

    Args:
        title:            Page heading, e.g. "Talk Your Way Out"
        description:      One or two sentences setting expectations
        scenario_intro:   The opening situation shown once at the top (max 600 chars)
        input_label:      Label above the textarea, e.g. "What do you say?"
        meter_label:      Name of the meter, e.g. "Tension" or "Trust" — always framed
                          so HIGH = winning, LOW = losing (success_threshold is always
                          above meter_start, failure_threshold always below it)
        judge_questions:  Dict of up to 4 {key: question_def}, same noul/choice/score
                          format as internal_typesafe_evaluate. Every turn's message is
                          judged against ALL of these in one TypeSafe call.
        meter_question_key: Which key in judge_questions drives the meter. Must be a
                          noul or score question (not choice — no inherent direction).
        meter_direction:  "positive" if a high judged value should push the meter UP
                          (e.g. is_effective), "negative" if it should push it DOWN
                          (e.g. is_aggressive).
        success_ending:   Shown when the meter reaches success_threshold (max 300 chars)
        failure_ending:   Shown when the meter drops to failure_threshold (max 300 chars)
        stalemate_ending: Shown if max_turns is reached with neither threshold hit
        meter_start:      Starting meter value, 0-100 (default 50)
        success_threshold: Meter value that wins, must be > meter_start (default 85)
        failure_threshold: Meter value that loses, must be < meter_start (default 15)
        meter_swing:      Max meter change per turn, 5-40 (default 20)
        max_turns:        Turn cap before a stalemate ending, 3-15 (default 8)
        theme_emoji:      Single emoji shown in the header (default 🎭)
        visibility:       "public" (default) or "presigned" — both currently return a
                          URL valid for up to 7 days (S3's signed-URL max)
        config:           Runtime config injected by adk_tools.py (contains tenant_id)

    Returns:
        {"success": True, "url": ..., "visibility": ..., "expires_at"?: ...}
        or {"success": False, "error": ...}
    """
    title = (title or "").strip()
    description = (description or "").strip()
    scenario_intro = (scenario_intro or "").strip()
    input_label = (input_label or "").strip()
    meter_label = (meter_label or "").strip()
    success_ending = (success_ending or "").strip()
    failure_ending = (failure_ending or "").strip()
    stalemate_ending = (stalemate_ending or "").strip()

    if not title:
        return {"success": False, "error": "title is required"}
    if len(title) > _MAX_TITLE_LEN:
        return {"success": False, "error": f"title exceeds {_MAX_TITLE_LEN} characters"}
    if not description:
        return {"success": False, "error": "description is required"}
    if len(description) > _MAX_DESCRIPTION_LEN:
        return {"success": False, "error": f"description exceeds {_MAX_DESCRIPTION_LEN} characters"}
    if not scenario_intro:
        return {"success": False, "error": "scenario_intro is required"}
    if len(scenario_intro) > _MAX_SCENARIO_INTRO_LEN:
        return {"success": False, "error": f"scenario_intro exceeds {_MAX_SCENARIO_INTRO_LEN} characters"}
    if not input_label:
        return {"success": False, "error": "input_label is required"}
    if len(input_label) > _MAX_INPUT_LABEL_LEN:
        return {"success": False, "error": f"input_label exceeds {_MAX_INPUT_LABEL_LEN} characters"}
    if not meter_label:
        return {"success": False, "error": "meter_label is required"}
    if len(meter_label) > _MAX_METER_LABEL_LEN:
        return {"success": False, "error": f"meter_label exceeds {_MAX_METER_LABEL_LEN} characters"}
    for name, val in (
        ("success_ending", success_ending),
        ("failure_ending", failure_ending),
        ("stalemate_ending", stalemate_ending),
    ):
        if not val:
            return {"success": False, "error": f"{name} is required"}
        if len(val) > _MAX_ENDING_LEN:
            return {"success": False, "error": f"{name} exceeds {_MAX_ENDING_LEN} characters"}

    if meter_direction not in _VALID_DIRECTIONS:
        return {"success": False, "error": "meter_direction must be 'positive' or 'negative'"}
    if not (0 <= meter_start <= 100):
        return {"success": False, "error": "meter_start must be between 0 and 100"}
    if not (success_threshold > meter_start):
        return {"success": False, "error": "success_threshold must be greater than meter_start"}
    if not (failure_threshold < meter_start):
        return {"success": False, "error": "failure_threshold must be less than meter_start"}
    meter_swing = max(_MIN_METER_SWING, min(_MAX_METER_SWING, int(meter_swing or _DEFAULT_METER_SWING)))
    max_turns = max(_MIN_TURNS, min(_MAX_TURNS_CAP, int(max_turns or _DEFAULT_MAX_TURNS)))
    if visibility not in ("presigned", "public"):
        return {"success": False, "error": "visibility must be 'presigned' or 'public'"}

    q_error = _validate_judge_questions(judge_questions, meter_question_key)
    if q_error:
        return {"success": False, "error": q_error}

    runtime_context = (config or {}).get("_runtime_context")
    tenant_id = getattr(runtime_context, "tenant_id", None) if runtime_context else None
    if not tenant_id:
        return {"success": False, "error": "No tenant context available"}

    page_id = uuid.uuid4().hex
    spec = {
        "tenant_id": str(tenant_id),
        "title": title,
        "description": description,
        "scenario_intro": scenario_intro,
        "input_label": input_label,
        "meter_label": meter_label,
        "meter_start": meter_start,
        "success_threshold": success_threshold,
        "failure_threshold": failure_threshold,
        "meter_question_key": meter_question_key,
        "meter_direction": meter_direction,
        "meter_swing": meter_swing,
        "max_turns": max_turns,
        "judge_questions": judge_questions,
        "success_ending": success_ending,
        "failure_ending": failure_ending,
        "stalemate_ending": stalemate_ending,
        "theme_emoji": (theme_emoji or "🎭").strip()[:8] or "🎭",
        "created_at": datetime.now(UTC).isoformat(),
    }

    try:
        from src.config.settings import settings
        from src.services.agents.internal_tools.typesafe_story_game_renderer import render_story_game_html

        api_base_url = settings.api_base_url.rstrip("/")
        html_doc = render_story_game_html(page_id=page_id, spec=spec, api_base_url=api_base_url)
    except Exception as exc:
        logger.exception("Story game render failed")
        return {"success": False, "error": f"Render failed: {exc}"}

    try:
        s3 = get_s3_storage()
        s3.upload_file(
            file_content=json.dumps(spec).encode("utf-8"),
            key=spec_key(page_id),
            content_type="application/json",
        )
        s3.upload_file(
            file_content=html_doc.encode("utf-8"),
            key=html_key(page_id),
            content_type="text/html",
        )
    except Exception as exc:
        logger.exception("Story game S3 upload failed")
        return {"success": False, "error": f"Upload failed: {exc}"}

    try:
        if visibility == "presigned":
            url = s3.generate_presigned_url(key=html_key(page_id), expiration=604800)
            expires_at = (datetime.now(UTC) + timedelta(days=7)).isoformat()
            result: dict[str, Any] = {
                "success": True,
                "url": url,
                "expires_at": expires_at,
                "visibility": "presigned",
            }
        else:
            if s3.public_endpoint_url:
                url = f"{s3.public_endpoint_url.rstrip('/')}/{s3.bucket_name}/{html_key(page_id)}"
                result = {"success": True, "url": url, "visibility": "public"}
            else:
                url = s3.generate_presigned_url(key=html_key(page_id), expiration=604800)
                result = {
                    "success": True,
                    "url": url,
                    "visibility": "public",
                    "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                }
    except Exception as exc:
        return {"success": False, "error": f"URL generation failed: {exc}"}

    return result
