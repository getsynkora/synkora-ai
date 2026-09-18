"""
TypeSafe AI Reflex Game — lets an agent publish a standalone, public, timed
guessing game: a scenario flashes, the visitor guesses TypeSafe's verdict
before a countdown runs out, then the real judgment is revealed live.

Generic over any use case: an agent defines its own scenario bank and its
own guess question (noul or choice) — "ick or no ick", "red flag or not",
"AI-generated or human", "villain or LinkedIn post", whatever. Nothing here
is specific to one topic.

Like internal_create_typesafe_playground, this stores a JSON spec in S3 and
renders a self-contained HTML page; the public evaluate endpoint reads the
spec back by page_id and looks up scenario text by index server-side (the
client only ever sends an index, never arbitrary text — the scenario bank
is fixed by the agent, not visitor-submitted).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from src.services.storage.s3_storage import get_s3_storage

logger = logging.getLogger(__name__)

_VALID_GUESS_TYPES = {"noul", "choice"}
_VALID_REVEAL_TYPES = {"noul", "choice", "score"}
_GUESS_KEY = "_guess"  # reserved answer key — reveal_questions may not use it

_MIN_SCENARIOS = 5
_MAX_SCENARIOS = 20
_MAX_SCENARIO_LEN = 240
_MAX_REVEAL_QUESTIONS = 3
_MAX_TITLE_LEN = 100
_MAX_DESCRIPTION_LEN = 300
_MIN_ROUND_SECONDS = 3
_MAX_ROUND_SECONDS = 15
_DEFAULT_ROUND_SECONDS = 6

_S3_PREFIX = "typesafe_reflex_games/pages"


def spec_key(page_id: str) -> str:
    return f"{_S3_PREFIX}/{page_id}.json"


def html_key(page_id: str) -> str:
    return f"{_S3_PREFIX}/{page_id}.html"


def _validate_guess_question(guess_question: dict[str, Any]) -> str | None:
    if not guess_question:
        return "guess_question is required"
    q_type = guess_question.get("type", "noul")
    if q_type not in _VALID_GUESS_TYPES:
        return f"guess_question.type must be 'noul' or 'choice', got '{q_type}'"
    if not (guess_question.get("question") or "").strip():
        return "guess_question.question is required"
    if q_type == "choice":
        options = guess_question.get("options")
        if not options or len(options) < 2:
            return "guess_question.options must have at least 2 entries for a choice question"
        if len(options) > 4:
            return "guess_question.options should have at most 4 entries for a fast reflex game"
    return None


def _validate_reveal_questions(reveal_questions: dict[str, dict[str, Any]] | None) -> str | None:
    if not reveal_questions:
        return None
    if _GUESS_KEY in reveal_questions:
        return f"reveal_questions may not use the reserved key '{_GUESS_KEY}'"
    if len(reveal_questions) > _MAX_REVEAL_QUESTIONS:
        return f"Too many reveal_questions ({len(reveal_questions)}) — max {_MAX_REVEAL_QUESTIONS}"
    for key, q in reveal_questions.items():
        q_type = q.get("type", "noul")
        if q_type not in _VALID_REVEAL_TYPES:
            return f"Invalid type '{q_type}' for reveal question '{key}'"
        if not (q.get("question") or "").strip():
            return f"Reveal question '{key}' is missing 'question' text"
        if q_type == "choice" and not q.get("options"):
            return f"Reveal question '{key}' (choice) must include 'options'"
        if q_type == "score" and not q.get("levels"):
            return f"Reveal question '{key}' (score) must include 'levels'"
    return None


async def internal_create_typesafe_reflex_game(
    title: str,
    description: str,
    scenarios: list[str],
    guess_question: dict[str, Any],
    reveal_questions: dict[str, dict[str, Any]] | None = None,
    yes_label: str = "Yes",
    no_label: str = "No",
    theme_emoji: str = "⚡",
    round_seconds: int = _DEFAULT_ROUND_SECONDS,
    visibility: str = "public",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish a public, timed guess-the-AI's-verdict reflex game and return its URL.

    A scenario from `scenarios` flashes on screen; the visitor has `round_seconds`
    to guess how TypeSafe will judge it (yes/no, or pick one of a few options),
    then the real judgment reveals live and their score updates. Cycles through
    a shuffled playthrough of all scenarios, then shows a final shareable score.

    This is generic — invent any guessing game by writing your own scenario bank
    and guess question: "ick or no ick" dating moments, "red flag or not" texts,
    "villain monologue or LinkedIn post", "AI-generated or human", etc.

    Args:
        title:            Page heading, e.g. "Ick or No Ick?"
        description:      One or two sentences explaining the game
        scenarios:        List of short scenario strings visitors judge (5-20 items,
                           each under 240 chars). Write these yourself — punchy,
                           specific, funny where appropriate. This is a fixed bank,
                           not visitor-submitted text.
        guess_question:    The question TypeSafe (and the visitor) answers about each
                           scenario. noul: {"type":"noul","question":"..."} or
                           choice: {"type":"choice","question":"...","options":[...]}
                           (2-4 options for a fast game).
        reveal_questions: Optional extra questions (max 3) shown only after the
                          guess, for flavor — e.g. a severity score or category.
                          Same noul/choice/score format as internal_typesafe_evaluate.
        yes_label:        Button label for the "yes" guess when guess_question is
                           noul type (default "Yes", e.g. "Ick 😬")
        no_label:         Button label for the "no" guess when guess_question is
                           noul type (default "No", e.g. "No Ick 😌")
        theme_emoji:      Single emoji shown in the header (default ⚡)
        round_seconds:    Seconds per round before auto-lock (3-15, default 6)
        visibility:       "public" (default, permanent link — the point of a game
                           people share) or "presigned" (7-day private URL)
        config:           Runtime config injected by adk_tools.py (contains tenant_id)

    Returns:
        {"success": True, "url": ..., "visibility": ..., "expires_at"?: ...}
        or {"success": False, "error": ...}
    """
    title = (title or "").strip()
    description = (description or "").strip()

    if not title:
        return {"success": False, "error": "title is required"}
    if len(title) > _MAX_TITLE_LEN:
        return {"success": False, "error": f"title exceeds {_MAX_TITLE_LEN} characters"}
    if not description:
        return {"success": False, "error": "description is required"}
    if len(description) > _MAX_DESCRIPTION_LEN:
        return {"success": False, "error": f"description exceeds {_MAX_DESCRIPTION_LEN} characters"}

    if not scenarios or len(scenarios) < _MIN_SCENARIOS:
        return {"success": False, "error": f"Need at least {_MIN_SCENARIOS} scenarios"}
    if len(scenarios) > _MAX_SCENARIOS:
        return {"success": False, "error": f"Too many scenarios ({len(scenarios)}) — max {_MAX_SCENARIOS}"}
    cleaned_scenarios = []
    for i, s in enumerate(scenarios):
        s = (s or "").strip()
        if not s:
            return {"success": False, "error": f"scenarios[{i}] is empty"}
        if len(s) > _MAX_SCENARIO_LEN:
            return {"success": False, "error": f"scenarios[{i}] exceeds {_MAX_SCENARIO_LEN} characters"}
        cleaned_scenarios.append(s)

    g_error = _validate_guess_question(guess_question)
    if g_error:
        return {"success": False, "error": g_error}
    r_error = _validate_reveal_questions(reveal_questions)
    if r_error:
        return {"success": False, "error": r_error}

    if visibility not in ("presigned", "public"):
        return {"success": False, "error": "visibility must be 'presigned' or 'public'"}

    round_seconds = max(_MIN_ROUND_SECONDS, min(_MAX_ROUND_SECONDS, int(round_seconds or _DEFAULT_ROUND_SECONDS)))

    runtime_context = (config or {}).get("_runtime_context")
    tenant_id = getattr(runtime_context, "tenant_id", None) if runtime_context else None
    if not tenant_id:
        return {"success": False, "error": "No tenant context available"}

    page_id = uuid.uuid4().hex
    spec = {
        "tenant_id": str(tenant_id),
        "title": title,
        "description": description,
        "scenarios": cleaned_scenarios,
        "guess_question": guess_question,
        "reveal_questions": reveal_questions or {},
        "yes_label": (yes_label or "Yes").strip()[:24] or "Yes",
        "no_label": (no_label or "No").strip()[:24] or "No",
        "theme_emoji": (theme_emoji or "⚡").strip()[:8] or "⚡",
        "round_seconds": round_seconds,
        "created_at": datetime.now(UTC).isoformat(),
    }

    try:
        from src.config.settings import settings
        from src.services.agents.internal_tools.typesafe_reflex_game_renderer import render_reflex_game_html

        api_base_url = settings.api_base_url.rstrip("/")
        html_doc = render_reflex_game_html(page_id=page_id, spec=spec, api_base_url=api_base_url)
    except Exception as exc:
        logger.exception("Reflex game render failed")
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
        logger.exception("Reflex game S3 upload failed")
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
            endpoint = s3.public_endpoint_url or s3.internal_endpoint_url or ""
            if endpoint:
                url = f"{endpoint.rstrip('/')}/{s3.bucket_name}/{html_key(page_id)}"
            else:
                url = s3.generate_presigned_url(key=html_key(page_id), expiration=86400 * 365)
            result = {"success": True, "url": url, "visibility": "public"}
    except Exception as exc:
        return {"success": False, "error": f"URL generation failed: {exc}"}

    return result
