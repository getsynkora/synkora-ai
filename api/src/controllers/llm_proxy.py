"""LLM Proxy API endpoints.

Provides mock LLM endpoints for load testing without incurring real API costs.
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.services.load_testing.proxy_router import LLMProxyRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proxy/v1", tags=["llm-proxy"])


def _extract_api_key(authorization: str | None = Header(None)) -> str:
    """
    Extract API key from Authorization header.

    Args:
        authorization: Authorization header value

    Returns:
        str: Extracted API key

    Raises:
        HTTPException: If no valid API key found
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if authorization.startswith("Bearer "):
        return authorization[7:]
    elif authorization.startswith("sk-proxy-"):
        return authorization
    else:
        raise HTTPException(status_code=401, detail="Invalid Authorization format")


# ============================================================================
# OpenAI-Compatible Endpoints
# ============================================================================


@router.post("/chat/completions")
async def openai_chat_completions(
    request: Request,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
):
    """
    OpenAI-compatible chat completions endpoint.

    Returns mock responses for load testing.
    """
    try:
        api_key = _extract_api_key(authorization)
        request_body = await request.json()

        proxy_router = LLMProxyRouter(db)
        stream = request_body.get("stream", False)

        if stream:
            response_generator = await proxy_router.handle_chat_completion(api_key, request_body, stream=True)
            return StreamingResponse(
                response_generator,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            response = await proxy_router.handle_chat_completion(api_key, request_body, stream=False)
            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat completions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/models")
async def openai_models(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
):
    """
    OpenAI-compatible models list endpoint.

    Returns available mock models.
    """
    try:
        api_key = _extract_api_key(authorization)
        proxy_router = LLMProxyRouter(db)
        return await proxy_router.get_models(api_key)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing models: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/completions")
async def openai_completions(
    request: Request,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
):
    """
    OpenAI-compatible completions endpoint (legacy).

    Converts to chat format and returns mock response.
    """
    try:
        api_key = _extract_api_key(authorization)
        request_body = await request.json()

        # Convert legacy format to chat format
        prompt = request_body.get("prompt", "")
        chat_request = {
            "model": request_body.get("model", "gpt-3.5-turbo-instruct"),
            "messages": [{"role": "user", "content": prompt}],
            "stream": request_body.get("stream", False),
            "max_tokens": request_body.get("max_tokens", 150),
            "temperature": request_body.get("temperature", 1.0),
        }

        proxy_router = LLMProxyRouter(db)
        stream = chat_request.get("stream", False)

        if stream:
            response_generator = await proxy_router.handle_chat_completion(api_key, chat_request, stream=True)
            return StreamingResponse(
                response_generator,
                media_type="text/event-stream",
            )
        else:
            chat_response = await proxy_router.handle_chat_completion(api_key, chat_request, stream=False)

            # Convert back to legacy format
            return {
                "id": chat_response["id"],
                "object": "text_completion",
                "created": chat_response["created"],
                "model": chat_response["model"],
                "choices": [
                    {
                        "text": chat_response["choices"][0]["message"]["content"],
                        "index": 0,
                        "logprobs": None,
                        "finish_reason": "stop",
                    }
                ],
                "usage": chat_response["usage"],
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in completions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Anthropic-Compatible Endpoints
# ============================================================================


@router.post("/messages")
async def anthropic_messages(
    request: Request,
    x_api_key: str | None = Header(None, alias="x-api-key"),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Anthropic-compatible messages endpoint.

    Returns mock responses for load testing.
    """
    try:
        # Anthropic uses x-api-key header
        api_key = x_api_key or _extract_api_key(authorization)
        request_body = await request.json()

        proxy_router = LLMProxyRouter(db)
        stream = request_body.get("stream", False)

        if stream:
            response_generator = await proxy_router.handle_anthropic_messages(api_key, request_body, stream=True)
            return StreamingResponse(
                response_generator,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        else:
            response = await proxy_router.handle_anthropic_messages(api_key, request_body, stream=False)
            return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Google-Compatible Endpoints
# ============================================================================


@router.post("/models/{model}:generateContent")
async def google_generate_content(
    model: str,
    request: Request,
    x_goog_api_key: str | None = Header(None, alias="x-goog-api-key"),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Google Generative AI-compatible generateContent endpoint.

    Returns mock responses for load testing.
    """
    try:
        api_key = x_goog_api_key or _extract_api_key(authorization)
        request_body = await request.json()

        proxy_router = LLMProxyRouter(db)
        response = await proxy_router.handle_google_generate(api_key, model, request_body, stream=False)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generateContent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/models/{model}:streamGenerateContent")
async def google_stream_generate_content(
    model: str,
    request: Request,
    x_goog_api_key: str | None = Header(None, alias="x-goog-api-key"),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Google Generative AI-compatible streamGenerateContent endpoint.

    Returns streaming mock responses for load testing.
    """
    try:
        api_key = x_goog_api_key or _extract_api_key(authorization)
        request_body = await request.json()

        proxy_router = LLMProxyRouter(db)
        response_generator = await proxy_router.handle_google_generate(api_key, model, request_body, stream=True)

        return StreamingResponse(
            response_generator,
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in streamGenerateContent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health")
async def proxy_health():
    """Health check endpoint for the proxy."""
    return {"status": "healthy", "service": "llm-proxy"}
