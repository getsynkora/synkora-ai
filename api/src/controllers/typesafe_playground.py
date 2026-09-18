"""
Public endpoints for TypeSafe AI playground pages and reflex games.

Fully unauthenticated by design — pages published by
internal_create_typesafe_playground / internal_create_typesafe_reflex_game
call these from the browser, from whatever origin S3/MinIO serves them
from. Security boundary is rate limiting (per-page and per-IP) plus the
tenant's own TypeSafe credentials never leaving the server.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.core.database import get_async_session_factory
from src.services.agents.internal_tools.typesafe_playground_renderer import MAX_PLAYGROUND_TEXT_LEN
from src.services.agents.internal_tools.typesafe_playground_tools import html_key as playground_html_key
from src.services.agents.internal_tools.typesafe_playground_tools import spec_key as playground_spec_key
from src.services.agents.internal_tools.typesafe_reflex_game_tools import html_key as reflex_game_html_key
from src.services.agents.internal_tools.typesafe_reflex_game_tools import spec_key as reflex_game_spec_key
from src.services.agents.runtime_context import RuntimeContext
from src.utils.ip_utils import get_client_ip

logger = logging.getLogger(__name__)

public_router = APIRouter()

# One atomic operation across all workers; distinct request IDs avoid timestamp collisions.
_RATE_LIMIT_SCRIPT = """
local timestamp = redis.call('TIME')
local now = tonumber(timestamp[1]) + tonumber(timestamp[2]) / 1000000
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 3600)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('EXPIRE', KEYS[1], 3660)
return 1
"""

_PAGE_HOURLY_LIMIT = 120  # total judgments per page per hour, across all visitors
_IP_HOURLY_LIMIT = 20  # judgments per visitor IP per page per hour


_MAX_SCENARIO_INDEX = 100  # generous upper bound; actual bank is capped much lower at creation time


class EvaluateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PLAYGROUND_TEXT_LEN)


class ReflexEvaluateRequest(BaseModel):
    scenario_index: int = Field(..., ge=0, le=_MAX_SCENARIO_INDEX)


async def _check_rate_limit(key: str, limit: int) -> bool:
    from src.config.redis import get_redis_async

    redis = get_redis_async()
    if redis is None:
        # Fail closed on judgments if Redis is down — this is a public, keyless
        # endpoint that calls a billed third-party API, unlike normal request paths.
        raise HTTPException(status_code=503, detail="Rate limiting temporarily unavailable")
    allowed = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, limit, uuid.uuid4().hex)
    return bool(allowed)


def _client_ip(request: Request) -> str:
    return get_client_ip(
        direct_ip=request.client.host if request.client else "unknown",
        forwarded_for=request.headers.get("x-forwarded-for"),
        real_ip=request.headers.get("x-real-ip"),
    )


async def _enforce_rate_limits(namespace: str, page_id: str, client_ip: str) -> None:
    if not await _check_rate_limit(f"{namespace}:page:{page_id}", _PAGE_HOURLY_LIMIT):
        raise HTTPException(status_code=429, detail="This page has hit its hourly limit. Try again later.")
    if not await _check_rate_limit(f"{namespace}:ip:{page_id}:{client_ip}", _IP_HOURLY_LIMIT):
        raise HTTPException(status_code=429, detail="You've hit the rate limit for this page. Try again later.")


def _load_spec(s3: Any, key: str) -> dict[str, Any]:
    spec_bytes = s3.download_file(key)
    return json.loads(spec_bytes)


async def _evaluate_for_tenant(
    tenant_id_str: str, state: str, questions: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    """Returns (answers, error). error is a user-facing message, or None on success."""
    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except ValueError:
        return None, "not_found"

    session_factory = get_async_session_factory()
    async with session_factory() as db:
        runtime_context = RuntimeContext(tenant_id=tenant_id, agent_id=uuid.uuid4(), db_session=db)

        from src.core.typesafe_client import make_typesafe_client
        from src.services.agents.credential_resolver import CredentialResolver

        resolver = CredentialResolver(runtime_context)
        credentials = await resolver.get_typesafe_credentials()
        if not credentials:
            return None, "not_configured"

        client = make_typesafe_client(credentials)
        result = await client.evaluate(state=state, questions=questions)

    if "error" in result:
        logger.warning("TypeSafe evaluate error: %s", result.get("error"))
        return None, "judgment_failed"

    return result.get("answers", {}), None


@public_router.post("/typesafe-playground/{page_id}/evaluate")
async def evaluate_playground(page_id: str, body: EvaluateRequest, request: Request):
    if not page_id.isalnum() or len(page_id) > 64:
        raise HTTPException(status_code=404, detail="Playground not found")

    await _enforce_rate_limits("tsp", page_id, _client_ip(request))

    from src.services.storage.s3_storage import get_s3_storage

    try:
        spec = _load_spec(get_s3_storage(), playground_spec_key(page_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Playground not found") from None

    questions = spec.get("questions") or {}
    if not questions:
        raise HTTPException(status_code=500, detail="This playground has no questions configured")

    answers, error = await _evaluate_for_tenant(spec.get("tenant_id", ""), body.text, questions)
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Playground not found")
    if error == "not_configured":
        raise HTTPException(status_code=503, detail="This playground's TypeSafe AI integration isn't configured yet.")
    if error:
        return {"success": False, "error": "Judgment failed. Please try again."}

    return {"success": True, "answers": answers}


@public_router.post("/typesafe-playground/{page_id}/reflex-evaluate")
async def evaluate_reflex_game(page_id: str, body: ReflexEvaluateRequest, request: Request):
    if not page_id.isalnum() or len(page_id) > 64:
        raise HTTPException(status_code=404, detail="Game not found")

    await _enforce_rate_limits("tsrg", page_id, _client_ip(request))

    from src.services.storage.s3_storage import get_s3_storage

    try:
        spec = _load_spec(get_s3_storage(), reflex_game_spec_key(page_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Game not found") from None

    scenarios = spec.get("scenarios") or []
    if body.scenario_index >= len(scenarios):
        raise HTTPException(status_code=400, detail="Invalid scenario index")

    guess_question = spec.get("guess_question")
    if not guess_question:
        raise HTTPException(status_code=500, detail="This game has no guess question configured")

    reveal_questions = spec.get("reveal_questions") or {}
    questions = {"_guess": guess_question, **reveal_questions}

    answers, error = await _evaluate_for_tenant(spec.get("tenant_id", ""), scenarios[body.scenario_index], questions)
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Game not found")
    if error == "not_configured":
        raise HTTPException(status_code=503, detail="This game's TypeSafe AI integration isn't configured yet.")
    if error:
        return {"success": False, "error": "Judgment failed. Please try again."}

    guess_answer = answers.pop("_guess", None) if answers else None
    return {"success": True, "guess_answer": guess_answer, "reveal_answers": answers or {}}


def _serve_page(key: str, not_found_detail: str) -> Response:
    """Fetch a page's HTML from S3 server-side and return it directly.

    This is the "public"/permanent link target — it never expires and doesn't
    depend on any S3 bucket ACL or presigned-URL time limit (AWS caps those at
    7 days), unlike trying to hand out a raw S3 URL.
    """
    from src.services.storage.s3_storage import get_s3_storage

    try:
        html_bytes = get_s3_storage().download_file(key)
    except Exception:
        raise HTTPException(status_code=404, detail=not_found_detail) from None

    return Response(content=html_bytes, media_type="text/html")


@public_router.get("/typesafe-playground/{page_id}/page")
async def serve_playground_page(page_id: str):
    if not page_id.isalnum() or len(page_id) > 64:
        raise HTTPException(status_code=404, detail="Playground not found")
    return _serve_page(playground_html_key(page_id), "Playground not found")


@public_router.get("/typesafe-playground/{page_id}/reflex-page")
async def serve_reflex_game_page(page_id: str):
    if not page_id.isalnum() or len(page_id) > 64:
        raise HTTPException(status_code=404, detail="Game not found")
    return _serve_page(reflex_game_html_key(page_id), "Game not found")
