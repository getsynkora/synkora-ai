"""
TypeSafe AI Playground — lets an agent publish a standalone, public, interactive
web page that judges whatever text a visitor pastes in, live, using TypeSafe's
Jev model (Noul/Choice/Score). Built for shareable "try it yourself" demos.

Unlike internal_generate_dashboard, this page is NOT static — it embeds a
"Judge Me" button that calls back to a public evaluate endpoint
(POST /api/v1/public/typesafe-playground/{page_id}/evaluate), which resolves
the tenant's TypeSafe credentials server-side and runs the judgment live. The
API key never reaches the browser.

The spec (questions, labels, tenant_id) is stored as JSON in S3 next to the
HTML shell; the public endpoint reads it back by page_id at request time.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from src.services.storage.s3_storage import get_s3_storage

logger = logging.getLogger(__name__)

_VALID_TYPES = {"noul", "choice", "score"}
_MAX_QUESTIONS = 6
_MAX_TITLE_LEN = 100
_MAX_DESCRIPTION_LEN = 300
_MAX_INPUT_LABEL_LEN = 100

_S3_SPEC_PREFIX = "typesafe_playgrounds/pages"
_S3_HTML_PREFIX = "typesafe_playgrounds/pages"


def spec_key(page_id: str) -> str:
    return f"{_S3_SPEC_PREFIX}/{page_id}.json"


def _html_key(page_id: str) -> str:
    return f"{_S3_HTML_PREFIX}/{page_id}.html"


def _validate_questions(questions: dict[str, dict[str, Any]]) -> str | None:
    """Return an error string, or None if valid."""
    if not questions:
        return "questions cannot be empty"
    if len(questions) > _MAX_QUESTIONS:
        return f"Too many questions ({len(questions)}) — max {_MAX_QUESTIONS} for a playground page"
    for key, q in questions.items():
        q_type = q.get("type", "noul")
        if q_type not in _VALID_TYPES:
            return f"Invalid question type '{q_type}' for key '{key}'. Must be one of: {sorted(_VALID_TYPES)}"
        if not (q.get("question") or "").strip():
            return f"Question '{key}' is missing 'question' text"
        if q_type == "choice" and not q.get("options"):
            return f"Choice question '{key}' must include 'options'"
        if q_type == "score" and not q.get("levels"):
            return f"Score question '{key}' must include 'levels'"
    return None


async def internal_create_typesafe_playground(
    title: str,
    description: str,
    input_label: str,
    questions: dict[str, dict[str, Any]],
    theme_emoji: str = "🔮",
    visibility: str = "presigned",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish a public, interactive TypeSafe AI judgment page and return its URL.

    Visitors paste text into the page and get a live judgment back — the
    questions this tool defines run against whatever they submit. No two
    playgrounds need share a use case: define any noul/choice/score questions
    for any judgment (red-flag checker, resume rater, vibe check, etc.).

    Args:
        title:        Page heading (e.g. "Red Flag Checker")
        description:  One or two sentences explaining what it judges
        input_label:  Label above the textarea (e.g. "Paste a dating bio")
        questions:    Dict of {answer_key: question_definition}, same format as
                      internal_typesafe_evaluate:
                        Noul:   {"type": "noul",   "question": "Is this X?"}
                        Choice: {"type": "choice", "question": "Which?", "options": [...]}
                        Score:  {"type": "score",  "question": "How?",   "levels": [...]}
                      Max 6 questions.
        theme_emoji:  Single emoji shown in the header (default 🔮)
        visibility:   "presigned" (default, 7-day private URL) or "public" (permanent)
        config:       Runtime config injected by adk_tools.py (contains tenant_id)

    Returns:
        {"success": True, "url": ..., "visibility": ..., "expires_at"?: ...}
        or {"success": False, "error": ...}
    """
    title = (title or "").strip()
    description = (description or "").strip()
    input_label = (input_label or "").strip()

    if not title:
        return {"success": False, "error": "title is required"}
    if len(title) > _MAX_TITLE_LEN:
        return {"success": False, "error": f"title exceeds {_MAX_TITLE_LEN} characters"}
    if not description:
        return {"success": False, "error": "description is required"}
    if len(description) > _MAX_DESCRIPTION_LEN:
        return {"success": False, "error": f"description exceeds {_MAX_DESCRIPTION_LEN} characters"}
    if not input_label:
        return {"success": False, "error": "input_label is required"}
    if len(input_label) > _MAX_INPUT_LABEL_LEN:
        return {"success": False, "error": f"input_label exceeds {_MAX_INPUT_LABEL_LEN} characters"}
    if visibility not in ("presigned", "public"):
        return {"success": False, "error": "visibility must be 'presigned' or 'public'"}

    q_error = _validate_questions(questions)
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
        "input_label": input_label,
        "questions": questions,
        "theme_emoji": (theme_emoji or "🔮").strip()[:8] or "🔮",
        "created_at": datetime.now(UTC).isoformat(),
    }

    try:
        from src.config.settings import settings
        from src.services.agents.internal_tools.typesafe_playground_renderer import render_playground_html

        api_base_url = settings.api_base_url.rstrip("/")
        html_doc = render_playground_html(page_id=page_id, spec=spec, api_base_url=api_base_url)
    except Exception as exc:
        logger.exception("Playground render failed")
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
            key=_html_key(page_id),
            content_type="text/html",
        )
    except Exception as exc:
        logger.exception("Playground S3 upload failed")
        return {"success": False, "error": f"Upload failed: {exc}"}

    try:
        if visibility == "presigned":
            url = s3.generate_presigned_url(key=_html_key(page_id), expiration=604800)
            expires_at = (datetime.now(UTC) + timedelta(days=7)).isoformat()
            result: dict[str, Any] = {
                "success": True,
                "url": url,
                "expires_at": expires_at,
                "visibility": "presigned",
            }
        else:
            # internal_endpoint_url is the S3 API endpoint used for signed requests, NOT a
            # publicly-readable file host — using it for an unsigned URL 403s unless the
            # bucket has a public-read policy. Only public_endpoint_url is safe to assume
            # is actually anonymous-readable; otherwise fall back to a long-lived signed URL.
            if s3.public_endpoint_url:
                url = f"{s3.public_endpoint_url.rstrip('/')}/{s3.bucket_name}/{_html_key(page_id)}"
                result = {"success": True, "url": url, "visibility": "public"}
            else:
                url = s3.generate_presigned_url(key=_html_key(page_id), expiration=86400 * 365)
                result = {
                    "success": True,
                    "url": url,
                    "visibility": "public",
                    "expires_at": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
                    "note": "No public S3 endpoint configured — returned a 1-year signed URL instead of a permanent one.",
                }
    except Exception as exc:
        return {"success": False, "error": f"URL generation failed: {exc}"}

    return result
