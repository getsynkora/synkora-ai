"""
Agent API authentication middleware.

Validates agent API keys and enforces rate limiting, permissions, and usage tracking.
"""

import asyncio
import hmac
import logging
import time
import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.models.agent_api_key import AgentApiKey
from src.services.agent_api.api_key_service import AgentApiKeyService
from src.services.agents.security import decrypt_value

logger = logging.getLogger(__name__)


class AgentApiAuthMiddleware:
    """Middleware for agent API authentication and authorization."""

    @staticmethod
    def extract_bearer_token(authorization: str | None) -> str | None:
        """
        Extract Bearer token from Authorization header.

        Args:
            authorization: Authorization header value

        Returns:
            API key if valid Bearer token, None otherwise
        """
        if not authorization:
            return None

        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        return parts[1]

    @staticmethod
    async def validate_api_key(api_key: str, db: AsyncSession) -> AgentApiKey | None:
        """
        Validate an API key and return the associated record.

        SECURITY: Uses constant-time comparison to prevent timing attacks.
        SECURITY FIX: Uses key_prefix index to prevent N+1 query DoS attacks.

        Args:
            db: Async database session
            api_key: Plain text API key

        Returns:
            AgentApiKey if valid, None otherwise
        """
        # SECURITY: Never log API keys, even partially - they can be used to narrow brute-force attacks
        if not api_key or not api_key.startswith("sk_"):
            logger.warning("[AUTH] Invalid API key format")
            return None

        # SECURITY FIX: Extract key prefix for indexed lookup instead of scanning all keys
        # This prevents DoS via N+1 query attack
        key_prefix = api_key[:20] if len(api_key) >= 20 else api_key

        # Query candidates matching the key prefix (indexed lookup)
        # This significantly reduces the number of decryption operations
        result = await db.execute(
            select(AgentApiKey)
            .where(
                AgentApiKey.is_active == True,  # noqa: E712
                AgentApiKey.key_prefix == key_prefix,
            )
            .limit(10)  # SECURITY: Limit results to prevent memory exhaustion
        )
        candidate_keys = result.scalars().all()

        # SECURITY: Check candidates with constant-time comparison
        matched_record = None

        for key_record in candidate_keys:
            try:
                # Decrypt and compare
                stored_key = decrypt_value(key_record.api_key)

                # SECURITY: Use constant-time comparison to prevent timing attacks
                # hmac.compare_digest prevents attackers from determining correct
                # characters by measuring response time differences
                if hmac.compare_digest(stored_key.encode(), api_key.encode()):
                    matched_record = key_record
                    break  # Found match, no need to continue

            except Exception as e:
                logger.warning(f"[AUTH] Error validating API key record: {e}")
                continue

        if matched_record is None:
            logger.warning("[AUTH] No matching API key found")
            return None

        # Check expiration
        from datetime import UTC, datetime

        if matched_record.expires_at and matched_record.expires_at < datetime.now(UTC):
            logger.warning(f"[AUTH] API key {matched_record.id} has expired")
            return None

        # Update last used timestamp
        matched_record.last_used_at = datetime.now(UTC)
        await db.commit()
        logger.debug(f"[AUTH] API key {matched_record.id} validated")

        return matched_record

    @staticmethod
    async def enforce_request_controls(request: Request, api_key: AgentApiKey) -> None:
        """Apply stored key policy consistently to every API-key entry point."""
        client_ip = request.client.host if request.client else ""
        if not AgentApiKeyService.validate_ip_address(api_key, client_ip):
            raise HTTPException(403, "IP address not allowed for this API key")
        if not AgentApiKeyService.validate_origin(api_key, request.headers.get("Origin")):
            raise HTTPException(403, "Origin not allowed for this API key")
        try:
            allowed, error = await asyncio.to_thread(AgentApiKeyService.check_rate_limit, api_key)
        except Exception as exc:
            logger.warning("API key rate-limit service unavailable", exc_info=True)
            raise HTTPException(503, "API key rate-limit service unavailable") from exc
        if not allowed:
            raise HTTPException(429, error or "Rate limit exceeded", headers={"Retry-After": "60"})

    @staticmethod
    async def authenticate_request(
        request: Request,
        required_permission: str | None = None,
    ) -> AgentApiKey:
        """
        Authenticate agent API request.

        Args:
            request: FastAPI request object
            required_permission: Optional permission required for this endpoint

        Returns:
            Authenticated API key

        Raises:
            HTTPException: If authentication or authorization fails
        """
        # Get Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header is required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract Bearer token
        api_key = AgentApiAuthMiddleware.extract_bearer_token(authorization)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization format. Use: Bearer <api_key>",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get database session
        async for db in get_async_db():
            try:
                # Validate API key
                api_key_record = await AgentApiAuthMiddleware.validate_api_key(api_key, db)
                if not api_key_record:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or expired API key",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

                await AgentApiAuthMiddleware.enforce_request_controls(request, api_key_record)

                # Check permission
                if required_permission and not AgentApiKeyService.check_permission(api_key_record, required_permission):
                    logger.warning(f"Permission {required_permission} denied for API key {api_key_record.id}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"API key does not have required permission: {required_permission}",
                    )

                # Store API key in request state for later use
                request.state.api_key = api_key_record
                request.state.start_time = time.time()

                return api_key_record

            finally:
                await db.close()

    @staticmethod
    async def track_request_usage(
        request: Request,
        status_code: int,
        tokens_used: int | None = None,
        error_message: str | None = None,
    ):
        """
        Track API usage after request completion.

        Args:
            request: FastAPI request object
            status_code: HTTP status code
            tokens_used: Number of tokens used (for LLM calls)
            error_message: Error message if request failed
        """
        # Check if API key was authenticated
        if not hasattr(request.state, "api_key"):
            return

        api_key = request.state.api_key
        start_time = getattr(request.state, "start_time", time.time())

        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)

        # Get endpoint and method
        endpoint = request.url.path
        method = request.method

        # Track usage with database session
        async for db in get_async_db():
            try:
                await AgentApiKeyService.track_usage(
                    db=db,
                    api_key_id=api_key.id,
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    response_time_ms=response_time_ms,
                    tokens_used=tokens_used,
                    error_message=error_message,
                )
            except Exception as e:
                logger.error(f"Failed to track API usage: {e}")
            finally:
                await db.close()


def get_api_key_from_request(request: Request) -> AgentApiKey:
    """
    Dependency to get authenticated API key from request.

    Args:
        request: FastAPI request object

    Returns:
        Authenticated API key

    Raises:
        HTTPException: If API key not found in request state
    """
    if not hasattr(request.state, "api_key"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return request.state.api_key


def require_permission(permission: str):
    """
    Dependency factory to require specific permission.

    Args:
        permission: Required permission

    Returns:
        Dependency function that authenticates and checks permission

    Example:
        @router.post("/agent/execute")
        async def execute(api_key: AgentApiKey = Depends(require_permission("agent:execute"))):
            ...
    """

    async def check_permission(request: Request):
        # First authenticate the request
        api_key = await AgentApiAuthMiddleware.authenticate_request(request, permission)
        return api_key

    return check_permission


@dataclass(frozen=True)
class HandoffAccess:
    tenant_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    permissions: frozenset[str] | None = None  # None denotes an authenticated account.

    def require(self, permission: str) -> None:
        if self.permissions is not None and permission not in self.permissions and "*" not in self.permissions:
            raise HTTPException(403, f"API key requires {permission} permission")


async def get_handoff_access(
    request: Request,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
) -> HandoffAccess:
    """Retain the key's agent and permissions throughout handoff authorization."""
    parts = (authorization or "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    token = parts[1]
    if token.startswith("sk_"):
        key = await AgentApiAuthMiddleware.validate_api_key(token, db)
        if key is None:
            raise HTTPException(401, "Invalid or expired API key")
        if key.agent_id is None:
            raise HTTPException(403, "Handoff API keys must be scoped to an agent")
        await AgentApiAuthMiddleware.enforce_request_controls(request, key)
        return HandoffAccess(key.tenant_id, key.agent_id, frozenset(key.permissions or []))
    from src.middleware.auth_middleware import authenticate_tenant_token

    _, tenant_id = await authenticate_tenant_token(token, db)
    return HandoffAccess(tenant_id)


async def require_handoff_read(access: HandoffAccess = Depends(get_handoff_access)) -> HandoffAccess:
    access.require("handoff:read")
    return access


async def require_handoff_write(access: HandoffAccess = Depends(get_handoff_access)) -> HandoffAccess:
    access.require("handoff:write")
    return access
