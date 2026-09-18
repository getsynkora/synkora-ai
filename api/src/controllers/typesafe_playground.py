"""
Public endpoint for TypeSafe AI Playground pages.

Fully unauthenticated by design — the page published by
internal_create_typesafe_playground calls this from the browser, from
whatever origin S3/MinIO serves it from. Security boundary is rate limiting
(per-page and per-IP) plus the tenant's own TypeSafe credentials never
leaving the server.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.core.database import get_async_session_factory
from src.services.agents.internal_tools.typesafe_playground_renderer import MAX_PLAYGROUND_TEXT_LEN
from src.services.agents.internal_tools.typesafe_playground_tools import spec_key
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


class EvaluateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_PLAYGROUND_TEXT_LEN)


async def _check_rate_limit(key: str, limit: int) -> bool:
    from src.config.redis import get_redis_async

    redis = get_redis_async()
    if redis is None:
        # Fail closed on judgments if Redis is down — this is a public, keyless
        # endpoint that calls a billed third-party API, unlike normal request paths.
        raise HTTPException(status_code=503, detail="Rate limiting temporarily unavailable")
    allowed = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, limit, uuid.uuid4().hex)
    return bool(allowed)


@public_router.post("/typesafe-playground/{page_id}/evaluate")
async def evaluate_playground(page_id: str, body: EvaluateRequest, request: Request):
    if not page_id.isalnum() or len(page_id) > 64:
        raise HTTPException(status_code=404, detail="Playground not found")

    client_ip = get_client_ip(
        direct_ip=request.client.host if request.client else "unknown",
        forwarded_for=request.headers.get("x-forwarded-for"),
        real_ip=request.headers.get("x-real-ip"),
    )

    if not await _check_rate_limit(f"tsp:page:{page_id}", _PAGE_HOURLY_LIMIT):
        raise HTTPException(status_code=429, detail="This page has hit its hourly limit. Try again later.")
    if not await _check_rate_limit(f"tsp:ip:{page_id}:{client_ip}", _IP_HOURLY_LIMIT):
        raise HTTPException(status_code=429, detail="You've hit the rate limit for this page. Try again later.")

    from src.services.storage.s3_storage import get_s3_storage

    try:
        s3 = get_s3_storage()
        spec_bytes = s3.download_file(spec_key(page_id))
        spec = json.loads(spec_bytes)
    except Exception:
        raise HTTPException(status_code=404, detail="Playground not found") from None

    try:
        tenant_id = uuid.UUID(spec["tenant_id"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail="Playground not found") from None

    questions = spec.get("questions") or {}
    if not questions:
        raise HTTPException(status_code=500, detail="This playground has no questions configured")

    session_factory = get_async_session_factory()
    async with session_factory() as db:
        runtime_context = RuntimeContext(
            tenant_id=tenant_id,
            agent_id=uuid.uuid4(),
            db_session=db,
        )

        from src.core.typesafe_client import make_typesafe_client
        from src.services.agents.credential_resolver import CredentialResolver

        resolver = CredentialResolver(runtime_context)
        credentials = await resolver.get_typesafe_credentials()
        if not credentials:
            raise HTTPException(
                status_code=503,
                detail="This playground's TypeSafe AI integration isn't configured yet.",
            )

        client = make_typesafe_client(credentials)
        result = await client.evaluate(state=body.text, questions=questions)

    if "error" in result:
        logger.warning("TypeSafe playground %s evaluate error: %s", page_id, result.get("error"))
        return {"success": False, "error": "Judgment failed. Please try again."}

    return {"success": True, "answers": result.get("answers", {})}
