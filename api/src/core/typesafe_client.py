"""
TypeSafe AI client — thin async HTTP wrapper for the /v1/systemone endpoint.

Handles authentication, question-format normalization (LLM-friendly → wire format),
and error surfacing. All callers get a structured dict back; exceptions never escape.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Supported question types
_VALID_TYPES = {"noul", "choice", "score"}


def _normalize_question(q: dict[str, Any]) -> dict[str, Any]:
    """
    Convert the simplified LLM-friendly question format to TypeSafe wire format.

    LLM-friendly:
        noul   -> {"type": "noul",   "question": "Is this X?"}
        choice -> {"type": "choice", "question": "Which?",  "options": ["a","b","c"]}
        score  -> {"type": "score",  "question": "How?",    "levels": ["low","mid","high"]}

    Wire format:
        noul   -> {"type": "noul",   "instructions": "Is this X?"}
        choice -> {"type": "choice", "instructions": "Which?",  "criteria": {"a": null, "b": null, "c": null}}
        score  -> {"type": "score",  "instructions": "How?",    "criteria": ["low","mid","high"]}
    """
    q_type = q.get("type", "noul")
    instructions = q.get("question") or q.get("instructions") or ""

    wire: dict[str, Any] = {"type": q_type, "instructions": instructions}

    if q_type == "choice":
        options = q.get("options") or q.get("criteria") or []
        if isinstance(options, list):
            wire["criteria"] = dict.fromkeys(options)
        else:
            wire["criteria"] = options  # already a dict — pass through
    elif q_type == "score":
        levels = q.get("levels") or q.get("criteria") or []
        wire["criteria"] = list(levels) if not isinstance(levels, list) else levels

    return wire


class TypeSafeClient:
    """
    Async HTTP client for the TypeSafe AI evaluation API.

    Usage:
        client = TypeSafeClient(api_key="ts-...", base_url="https://api.typesafe.ai/v1")
        result = await client.evaluate(
            state="resume text here",
            questions={
                "meets_min": {"type": "noul",   "question": "Does this candidate meet minimum requirements?"},
                "fit":       {"type": "choice", "question": "Experience level?", "options": ["exceeds","meets","partial"]},
                "score":     {"type": "score",  "question": "Overall quality?",  "levels": ["weak","fair","strong"]},
            },
        )
    """

    def __init__(self, api_key: str, base_url: str = "https://api.typesafe.ai/v1", model: str = "jev-latest"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_model = model

    async def evaluate(
        self,
        state: str,
        questions: dict[str, dict[str, Any]],
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate `state` against `questions` using TypeSafe Jev.

        All questions execute in parallel in a single API call.

        Args:
            state:     The text content to evaluate (resume, ticket, lead profile, …)
            questions: Mapping of answer_key → question definition (LLM-friendly format)
            model:     Override the default model (default: jev-latest)

        Returns:
            TypeSafe response dict: {"model": "...", "answers": {...}, "usage": {...}}
            On error: {"error": "<message>", "status_code": <int or None>}
        """
        if not questions:
            return {"error": "No questions provided", "answers": {}}

        # Validate types before making a network call
        for key, q in questions.items():
            q_type = q.get("type", "noul")
            if q_type not in _VALID_TYPES:
                return {
                    "error": f"Invalid question type '{q_type}' for key '{key}'. Must be one of: {sorted(_VALID_TYPES)}",
                    "answers": {},
                }

        wire_questions = {k: _normalize_question(v) for k, v in questions.items()}
        payload = {
            "state": state,
            "model": model or self._default_model,
            "questions": wire_questions,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._base_url}/systemone",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                return resp.json()

        except httpx.HTTPStatusError as exc:
            logger.warning("TypeSafe API HTTP error %s: %s", exc.response.status_code, exc.response.text[:200])
            return {
                "error": f"TypeSafe API returned {exc.response.status_code}: {exc.response.text[:200]}",
                "status_code": exc.response.status_code,
                "answers": {},
            }
        except httpx.RequestError as exc:
            logger.warning("TypeSafe API connection error: %s", exc)
            return {
                "error": f"TypeSafe API connection error: {exc}",
                "answers": {},
            }
        except Exception as exc:
            logger.exception("Unexpected error calling TypeSafe API")
            return {
                "error": f"Unexpected error: {exc}",
                "answers": {},
            }


def make_typesafe_client(credentials: dict) -> TypeSafeClient:
    """
    Build a TypeSafeClient from a credentials dict returned by CredentialResolver.

    Expected keys:
        api_key  (required)
        base_url (optional, defaults to https://api.typesafe.ai/v1)
        model    (optional, defaults to jev-latest)
    """
    return TypeSafeClient(
        api_key=credentials["api_key"],
        base_url=credentials.get("base_url", "https://api.typesafe.ai/v1"),
        model=credentials.get("model", "jev-latest"),
    )
