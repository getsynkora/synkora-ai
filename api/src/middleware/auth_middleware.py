"""
Authentication middleware for FastAPI.

Provides dependency injection functions for protecting routes and checking permissions.
"""

import hashlib
import logging
import uuid

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.redis import get_redis_async
from src.core.database import get_async_db
from src.models import Account, AccountRole, AccountStatus
from src.services import AuthService
from src.services.security.token_blacklist import ACCOUNT_TOKENS_PREFIX, TOKEN_BLACKLIST_PREFIX

logger = logging.getLogger(__name__)


def extract_token(authorization: str | None = Header(None)) -> str | None:
    """
    Extract JWT token from Authorization header.

    Args:
        authorization: Authorization header value

    Returns:
        Token string if found, None otherwise
    """
    if not authorization:
        return None

    # Support both "Bearer <token>" and just "<token>"
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    elif len(parts) == 1:
        return parts[0]

    return None


def _get_token(authorization: str | None = Header(None)) -> str:
    """Extract and validate presence of Bearer token. Cached by FastAPI per request."""
    token = extract_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def _decode_token(token: str = Depends(_get_token)) -> dict:
    """
    Decode JWT payload. FastAPI caches this per request, so routes that compose
    multiple auth dependencies (get_current_account + get_current_tenant_id + ...)
    only decode the JWT once.
    """
    try:
        payload = AuthService.decode_token(token)
        if payload.get("type") != "access" or type(payload.get("ver", 0)) is not int:
            raise ValueError("An access token is required")
        return payload
    except (jwt.InvalidTokenError, KeyError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def _check_token_revocation(token: str, account_id: uuid.UUID, token_version: int) -> None:
    """
    SECURITY + PERFORMANCE: Single async Redis pipeline round-trip to check both
    the token blacklist and the account token version. Uses redis.asyncio to avoid
    blocking a thread-pool slot on every authenticated request.

    Raises HTTPException if the token is revoked.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    blacklist_key = f"{TOKEN_BLACKLIST_PREFIX}{token_hash}"
    version_key = f"{ACCOUNT_TOKENS_PREFIX}{account_id}:version"

    try:
        aio_redis = get_redis_async()
        pipe = aio_redis.pipeline()
        pipe.exists(blacklist_key)
        pipe.get(version_key)
        results = await pipe.execute()
        is_blacklisted = bool(results[0])
        current_version = int(results[1]) if results[1] else 0
    except Exception as exc:
        # Fail closed on Redis errors — treat token as revoked.
        logger.warning(f"Redis pipeline auth check failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_version < current_version:
        logger.warning(f"Stale token version for account {account_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_account(
    token: str = Depends(_get_token),
    payload: dict = Depends(_decode_token),
    db: AsyncSession = Depends(get_async_db),
) -> Account:
    """
    Get the current authenticated account from JWT token.

    SECURITY: Validates token against blacklist and checks token version.
    PERFORMANCE: Uses async Redis pipeline (no thread-pool blocking). JWT is decoded
    at most once per request via FastAPI's dependency cache (_decode_token).

    Args:
        token: Raw JWT string (from _get_token dependency)
        payload: Decoded JWT payload (from _decode_token dependency, cached per request)
        db: Async database session

    Returns:
        Account object

    Raises:
        HTTPException: If authentication fails
    """
    try:
        account_id = uuid.UUID(payload["sub"])
        token_version = payload.get("ver", 0)
    except (KeyError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    await _check_token_revocation(token, account_id, token_version)

    # DB query runs after Redis validation passes.
    result = await db.execute(select(Account).filter_by(id=account_id))
    account = result.scalar_one_or_none()
    if not account or account.status != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive account",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        AuthService.validate_account_auth_version(payload, account)
    except ValueError as exc:
        raise HTTPException(401, "Session has been revoked", headers={"WWW-Authenticate": "Bearer"}) from exc

    return account


async def get_current_tenant_id(
    payload: dict = Depends(_decode_token),
    _current_account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
) -> uuid.UUID:
    """
    Get the current tenant ID from JWT token.

    This is a FastAPI dependency for extracting tenant context.
    SECURITY: Also depends on get_current_account so tenant-scoped routes enforce
    token revocation, token-version checks, and active account status. FastAPI
    caches dependencies per request, so routes that already request
    get_current_account do not perform duplicate JWT/Redis/DB work.

    Usage:
        @router.get("/tenant-resource")
        async def get_resource(
            tenant_id: UUID = Depends(get_current_tenant_id)
        ):
            return {"tenant_id": str(tenant_id)}

    Args:
        payload: Decoded JWT payload (cached per request)

    Returns:
        Tenant UUID

    Raises:
        HTTPException: If tenant context is missing
    """
    if "tenant_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )
    try:
        tenant_id = uuid.UUID(payload["tenant_id"])
    except (KeyError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    # Check Redis cache for membership before hitting the DB.
    account_id = _current_account.id
    cache_key = f"membership:{account_id}:{tenant_id}"
    try:
        aio_redis = get_redis_async()
        cached = await aio_redis.get(cache_key)
        if cached:
            return tenant_id
    except Exception:
        # Redis down — fall through to DB query
        pass

    from src.models import TenantAccountJoin

    result = await db.execute(
        select(TenantAccountJoin).where(
            TenantAccountJoin.tenant_id == tenant_id,
            TenantAccountJoin.account_id == account_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Tenant access is no longer available")

    # Cache the successful membership check (60s TTL)
    try:
        aio_redis = get_redis_async()
        await aio_redis.setex(cache_key, 60, "1")
    except Exception:
        pass  # Redis down — non-critical, next request will re-query DB

    return tenant_id


async def get_current_tenant_id_optional(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
) -> uuid.UUID | None:
    """
    Optional tenant extraction — returns None instead of raising when unauthenticated.

    Use this for endpoints that serve both public and authenticated callers
    (e.g., chat-config GET: public agents need no auth, tenant agents do).
    """
    token = extract_token(authorization)
    if not token:
        return None
    try:
        payload = AuthService.decode_token(token)
        if payload.get("type") != "access" or type(payload.get("ver", 0)) is not int:
            return None
        tid = payload.get("tenant_id")
        if not tid:
            return None
        return uuid.UUID(tid)
    except Exception:
        return None


async def authenticate_tenant_token(token: str, db: AsyncSession) -> tuple[Account, uuid.UUID]:
    """Shared account and tenant checks for non-dependency entry points."""
    payload = _decode_token(token)
    account = await get_current_account(token=token, payload=payload, db=db)
    tenant_id = await get_current_tenant_id(payload=payload, _current_account=account, db=db)
    return account, tenant_id


def get_current_role(
    payload: dict = Depends(_decode_token),
) -> AccountRole:
    """
    Get the current user's role from JWT token.

    Uses the cached _decode_token dependency — no extra JWT decode if
    get_current_account is also a dependency on the same route.

    Args:
        payload: Decoded JWT payload (cached per request)

    Returns:
        AccountRole

    Raises:
        HTTPException: If role is missing
    """
    if "role" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role context required",
        )
    try:
        return AccountRole(payload["role"])
    except (KeyError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def require_role(required_role: AccountRole):
    """
    Dependency factory for requiring a specific role.

    Usage:
        @router.get("/admin")
        async def admin_route(
            current_account: Account = Depends(get_current_account),
            _: None = Depends(require_role(AccountRole.ADMIN))
        ):
            return {"message": "Admin access granted"}

    Args:
        required_role: Minimum required role

    Returns:
        Dependency function

    Raises:
        HTTPException: If role is insufficient
    """

    async def check_role(
        current_account: Account = Depends(get_current_account),
        tenant_id: uuid.UUID = Depends(get_current_tenant_id),
        db: AsyncSession = Depends(get_async_db),
    ) -> None:
        """Check if user has required role."""
        has_permission = await AuthService.check_permission(db, current_account.id, tenant_id, required_role)

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {required_role.value}",
            )

    return check_role


async def require_platform_admin(current_account: Account = Depends(get_current_account)) -> None:
    """Authorize global configuration using the current account record."""
    if str(current_account.is_platform_admin).lower() != "true":
        raise HTTPException(status_code=403, detail="Platform administrator access required")


async def get_optional_account(
    request: Request,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
) -> Account | None:
    """
    Get the current account if authenticated, None otherwise.

    SECURITY: Validates token against blacklist and checks token version.

    This is useful for endpoints that work for both authenticated and
    unauthenticated users.

    Checks for auth token in order:
    1. Authorization header (Bearer token)
    2. Cookie (access_token)

    SECURITY NOTE: Query parameter authentication has been removed as it can
    leak tokens via referrer headers, browser history, and server logs.
    Use the secure POST /oauth/initiate endpoint for OAuth flows instead.

    Usage:
        @router.get("/public")
        async def public_route(
            current_account: Account | None = Depends(get_optional_account)
        ):
            if current_account:
                return {"message": f"Hello {current_account.name}"}
            return {"message": "Hello guest"}

    Args:
        authorization: Authorization header
        db: Async database session
        request: FastAPI request object

    Returns:
        Account object if authenticated, None otherwise
    """
    token = extract_token(authorization)

    # If no token from header, try cookie
    if not token:
        token = request.cookies.get("access_token")

    # SECURITY: Query parameter authentication removed - tokens in URLs can leak
    # via referrer headers, browser history, and server logs

    if not token:
        return None

    try:
        payload = AuthService.decode_token(token)
        account_id = uuid.UUID(payload["sub"])
        token_version = payload.get("ver", 0)

        # Async Redis pipeline: blacklist check + version lookup (no thread-pool blocking)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        blacklist_key = f"{TOKEN_BLACKLIST_PREFIX}{token_hash}"
        version_key = f"{ACCOUNT_TOKENS_PREFIX}{account_id}:version"
        try:
            aio_redis = get_redis_async()
            pipe = aio_redis.pipeline()
            pipe.exists(blacklist_key)
            pipe.get(version_key)
            results = await pipe.execute()
            is_blacklisted = bool(results[0])
            current_version = int(results[1]) if results[1] else 0
        except Exception as exc:
            logger.error(f"Redis pipeline check failed in get_optional_account: {exc}")
            return None  # Fail closed

        if is_blacklisted or token_version < current_version:
            return None

        result = await db.execute(select(Account).filter_by(id=account_id))
        account = result.scalar_one_or_none()
        if account and account.status == AccountStatus.ACTIVE:
            AuthService.validate_account_auth_version(payload, account)
            return account
    except (jwt.InvalidTokenError, KeyError, ValueError):
        pass

    return None


async def get_optional_tenant_id(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_async_db),
) -> uuid.UUID | None:
    """Return a tenant only after current account and membership validation."""
    token = extract_token(authorization)
    if not token:
        return None
    try:
        _, tenant_id = await authenticate_tenant_token(token, db)
        return tenant_id
    except HTTPException:
        return None
