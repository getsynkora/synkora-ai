"""
Agent API Key Management Service.

Handles API key generation, validation, rate limiting, and usage tracking.
"""

import hmac
import ipaddress
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_api_key import AgentApiKey
from src.models.agent_api_usage import AgentApiUsage
from src.services.agents.security import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)


# Existing key names are retained so deployment does not reset active quotas.
_QUOTA_SCRIPT = """
local now = tonumber(ARGV[1])
local windows = {60, 3600, 86400}
for i = 1, 3 do
    redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', now - windows[i])
    if redis.call('ZCARD', KEYS[i]) >= tonumber(ARGV[i + 2]) then
        return i
    end
end
for i = 1, 3 do
    redis.call('ZADD', KEYS[i], now, ARGV[2])
    redis.call('EXPIRE', KEYS[i], windows[i] + 60)
end
return 0
"""


def _get_redis_client():
    """
    Get Redis client for rate limiting.

    SECURITY: Redis is required for API rate limiting - no fallback.
    Raises exception if Redis is unavailable.
    """
    try:
        from src.config.redis import get_redis

        redis = get_redis()
        if redis is None:
            raise RuntimeError("Redis connection returned None")
        return redis
    except Exception as e:
        logger.error(f"SECURITY: Redis unavailable for API rate limiting: {e}")
        raise RuntimeError("API rate limiting service temporarily unavailable. Please try again later.")


class AgentApiKeyService:
    """Service for managing agent API keys."""

    @staticmethod
    def generate_api_key(prefix: str = "sk_live_") -> tuple[str, str]:
        """
        Generate a new API key with the specified prefix.

        Args:
            prefix: Key prefix (default: "sk_live_")

        Returns:
            Tuple of (full_key, hashed_key)
        """
        # Generate random key (32 bytes = 64 hex characters)
        random_key = secrets.token_hex(32)
        full_key = f"{prefix}{random_key}"

        # Hash the key for storage (using encryption for consistency)
        hashed_key = encrypt_value(full_key)

        return full_key, hashed_key

    @staticmethod
    async def create_api_key(
        db: AsyncSession,
        agent_id: UUID,
        tenant_id: UUID,
        name: str,
        permissions: list[str],
        rate_limit_per_minute: int = 60,
        rate_limit_per_hour: int = 1000,
        rate_limit_per_day: int = 10000,
        allowed_ips: list[str] | None = None,
        allowed_origins: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> tuple[AgentApiKey, str]:
        """
        Create a new API key for an agent.

        Args:
            db: Database session
            agent_id: Agent UUID
            tenant_id: Tenant UUID
            name: Key name/description
            permissions: List of permissions
            rate_limit_per_minute: Requests per minute limit
            rate_limit_per_hour: Requests per hour limit
            rate_limit_per_day: Requests per day limit
            allowed_ips: List of allowed IP addresses
            allowed_origins: List of allowed CORS origins
            expires_at: Optional expiration datetime

        Returns:
            Tuple of (AgentApiKey, plain_text_key)
        """
        # Generate API key
        plain_key, hashed_key = AgentApiKeyService.generate_api_key()

        # Extract key prefix for identification
        key_prefix = plain_key[:20]  # e.g., "sk_live_abc123..."

        # Create API key record
        api_key = AgentApiKey(
            agent_id=agent_id,
            tenant_id=tenant_id,
            key_name=name,
            api_key=hashed_key,
            key_prefix=key_prefix,
            permissions=permissions,
            rate_limit_per_minute=rate_limit_per_minute,
            rate_limit_per_hour=rate_limit_per_hour,
            rate_limit_per_day=rate_limit_per_day,
            allowed_ips=allowed_ips or [],
            allowed_origins=allowed_origins or [],
            expires_at=expires_at,
            is_active=True,
        )

        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)

        logger.info(f"Created API key '{name}' for agent {agent_id}")
        return api_key, plain_key

    @staticmethod
    async def validate_api_key(db: AsyncSession, api_key: str) -> AgentApiKey | None:
        """
        Validate an API key and return the associated record.

        SECURITY FIX: Uses key prefix index to prevent N+1 query DoS attacks.
        Instead of scanning all active keys, we use the key_prefix column
        for indexed lookup.

        Args:
            db: Database session
            api_key: Plain text API key

        Returns:
            AgentApiKey if valid, None otherwise
        """
        if not api_key or not api_key.startswith("sk_"):
            return None

        # SECURITY FIX: Extract key prefix for indexed lookup
        # key_prefix is stored during key creation (first 20 chars)
        key_prefix = api_key[:20] if len(api_key) >= 20 else api_key

        # Query keys matching the prefix (indexed lookup)
        # This prevents DoS via N+1 query attack
        stmt = (
            select(AgentApiKey)
            .filter(
                AgentApiKey.is_active == True,  # noqa: E712
                AgentApiKey.key_prefix == key_prefix,
            )
            .limit(10)  # SECURITY: Limit results to prevent memory exhaustion
        )
        result = await db.execute(stmt)
        candidate_keys = result.scalars().all()

        # SECURITY: Check candidates with constant-time comparison
        matched_record = None
        for key_record in candidate_keys:
            try:
                # Decrypt and compare
                stored_key = decrypt_value(key_record.api_key)
                # SECURITY: Use constant-time comparison to prevent timing attacks
                if hmac.compare_digest(stored_key.encode(), api_key.encode()):
                    matched_record = key_record
                    break  # Found match, no need to continue
            except Exception as e:
                logger.warning(f"Error validating API key: {e}")
                continue

        if matched_record:
            # Check expiration
            if matched_record.expires_at and matched_record.expires_at < datetime.now(UTC):
                logger.warning(f"API key {matched_record.id} has expired")
                return None

            # Update last used timestamp
            matched_record.last_used_at = datetime.now(UTC)
            await db.commit()

            return matched_record

        return None

    @staticmethod
    def _ip_matches_allowlist(client_ip: str, allowed_ips: list[str]) -> bool:
        """
        Check whether client_ip is covered by any entry in allowed_ips.

        Supports:
        - Exact IP match (IPv4 or IPv6)
        - CIDR notation (e.g. "10.0.0.0/8", "2001:db8::/32")
        - Wildcard "*" to allow all IPs

        Args:
            client_ip: The incoming request IP address string
            allowed_ips: List of allowed IP addresses / CIDR ranges

        Returns:
            True if the client IP is covered by at least one allowlist entry
        """
        try:
            client_addr = ipaddress.ip_address(client_ip)
        except ValueError:
            logger.warning(f"Invalid client IP address for allowlist check: {client_ip!r}")
            return False

        for entry in allowed_ips:
            entry = entry.strip()
            if entry == "*":
                return True
            try:
                if "/" in entry:
                    # CIDR range — strict=False allows host bits to be set
                    if client_addr in ipaddress.ip_network(entry, strict=False):
                        return True
                else:
                    if client_addr == ipaddress.ip_address(entry):
                        return True
            except ValueError:
                logger.warning(f"Invalid allowlist entry ignored: {entry!r}")
                continue

        return False

    @staticmethod
    def validate_ip_address(api_key: AgentApiKey, ip_address: str) -> bool:
        """
        Validate request IP against allowed IPs.

        Supports exact IPs, CIDR ranges (e.g. 10.0.0.0/8), and wildcard "*".

        Args:
            api_key: API key record
            ip_address: Request IP address

        Returns:
            True if IP is allowed, False otherwise
        """
        # If no IP restrictions, allow all
        if not api_key.allowed_ips:
            return True

        return AgentApiKeyService._ip_matches_allowlist(ip_address, api_key.allowed_ips)

    @staticmethod
    def validate_origin(api_key: AgentApiKey, origin: str | None) -> bool:
        """Match URL origins and legacy hostname patterns on DNS label boundaries.

        URL entries constrain scheme and effective port. Bare hostname entries
        retain their existing scheme/port-independent meaning.
        """
        import ipaddress
        import re
        from urllib.parse import urlsplit

        if not api_key.allowed_origins:
            return True

        def parse(value: str, *, pattern: bool = False):
            if (
                not isinstance(value, str)
                or not value
                or any(c.isspace() or ord(c) < 32 for c in value)
                or "\\" in value
            ):
                raise ValueError("Invalid origin")
            explicit_scheme = "://" in value
            if not pattern and not explicit_scheme:
                raise ValueError("Origin requires a scheme")
            parsed = urlsplit(value if explicit_scheme else "https://" + value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("Invalid origin scheme or host")
            if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
                raise ValueError("Origin cannot contain credentials, query or fragment")
            if parsed.path not in (("", "/") if pattern else ("",)):
                raise ValueError("Origin cannot contain a path")
            host = parsed.hostname
            wildcard = pattern and host.startswith("*.")
            if wildcard:
                host = host[2:]
            host = host.removesuffix(".").encode("idna").decode("ascii").lower()
            if ":" in host:
                host = str(ipaddress.IPv6Address(host))
                if wildcard:
                    raise ValueError("IP addresses cannot be wildcard origins")
            elif any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")):
                raise ValueError("Invalid hostname")
            port = parsed.port
            if explicit_scheme and port is None:
                port = 443 if parsed.scheme == "https" else 80
            return parsed.scheme if explicit_scheme else None, host, port, wildcard

        try:
            scheme, host, port, _ = parse(origin)
        except (ValueError, UnicodeError, TypeError):
            return False
        for allowed in api_key.allowed_origins:
            if allowed == "*":
                return True
            try:
                allowed_scheme, allowed_host, allowed_port, wildcard = parse(allowed, pattern=True)
            except (ValueError, UnicodeError, TypeError):
                continue
            if allowed_scheme is not None and allowed_scheme != scheme:
                continue
            if allowed_port is not None and allowed_port != port:
                continue
            if host.endswith("." + allowed_host) if wildcard else host == allowed_host:
                return True
        return False

    @staticmethod
    def check_permission(api_key: AgentApiKey, required_permission: str) -> bool:
        """
        Check if API key has required permission.

        Supports both simple ("chat") and namespaced ("agent:chat") styles.
        A namespaced permission satisfies the simple form of the same verb,
        e.g. "agent:chat" grants "chat", "agent:read" grants "read".

        Args:
            api_key: API key record
            required_permission: Permission to check

        Returns:
            True if permission granted, False otherwise
        """
        if not api_key.permissions:
            return False

        # Wildcard grants everything
        if "*" in api_key.permissions:
            return True

        # Exact match
        if required_permission in api_key.permissions:
            return True

        # Namespaced match: "scope:verb" satisfies "verb"
        # e.g. "agent:chat" satisfies required "chat"
        suffix = f":{required_permission}"
        return any(perm.endswith(suffix) for perm in api_key.permissions)

    @staticmethod
    def check_rate_limit(api_key: AgentApiKey) -> tuple[bool, str | None]:
        """
        Check if API key has exceeded rate limits.

        SECURITY: Uses Redis for distributed rate limiting. No fallback -
        if Redis is unavailable, the request will fail safely.

        Args:
            api_key: API key record

        Returns:
            Tuple of (is_allowed, error_message)

        Raises:
            RuntimeError: If Redis is unavailable
        """
        key_id = str(api_key.id)
        current_time = time.time()

        redis_client = _get_redis_client()
        return AgentApiKeyService._check_rate_limit_redis(redis_client, key_id, current_time, api_key)

    @staticmethod
    def _check_rate_limit_redis(
        redis_client, key_id: str, current_time: float, api_key: AgentApiKey
    ) -> tuple[bool, str | None]:
        """Atomically check and reserve all quota windows on Redis."""
        keys = [f"api_rate:{key_id}:{window}" for window in ("minute", "hour", "day")]
        limits = [api_key.rate_limit_per_minute, api_key.rate_limit_per_hour, api_key.rate_limit_per_day]
        rejected = int(redis_client.eval(_QUOTA_SCRIPT, 3, *keys, current_time, secrets.token_hex(16), *limits))
        if rejected:
            if rejected not in (1, 2, 3):
                raise RuntimeError("Invalid quota response")
            window = ("minute", "hour", "day")[rejected - 1]
            return False, f"Rate limit exceeded: {limits[rejected - 1]} requests per {window}"
        return True, None

    @staticmethod
    async def track_usage(
        db: AsyncSession,
        api_key_id: UUID,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: int,
        tokens_used: int | None = None,
        error_message: str | None = None,
    ) -> AgentApiUsage:
        """
        Track API usage for analytics and billing.

        Args:
            db: Database session
            api_key_id: API key UUID
            endpoint: API endpoint called
            method: HTTP method
            status_code: Response status code
            response_time_ms: Response time in milliseconds
            tokens_used: Number of tokens used (for LLM calls)
            error_message: Error message if request failed

        Returns:
            AgentApiUsage record
        """
        usage = AgentApiUsage(
            api_key_id=api_key_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            tokens_used=tokens_used,
            error_message=error_message,
        )

        db.add(usage)
        await db.commit()
        await db.refresh(usage)

        return usage

    @staticmethod
    async def get_usage_stats(
        db: AsyncSession,
        api_key_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """
        Get usage statistics for an API key.

        Args:
            db: Database session
            api_key_id: API key UUID
            start_date: Start date for stats (default: 30 days ago)
            end_date: End date for stats (default: now)

        Returns:
            Dictionary with usage statistics
        """
        if not start_date:
            start_date = datetime.now(UTC) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(UTC)

        # Query total requests
        stmt = select(func.count(AgentApiUsage.id)).filter(
            and_(
                AgentApiUsage.api_key_id == api_key_id,
                AgentApiUsage.created_at >= start_date,
                AgentApiUsage.created_at <= end_date,
            )
        )
        result = await db.execute(stmt)
        total_requests = result.scalar() or 0

        # Query successful requests
        stmt = select(func.count(AgentApiUsage.id)).filter(
            and_(
                AgentApiUsage.api_key_id == api_key_id,
                AgentApiUsage.created_at >= start_date,
                AgentApiUsage.created_at <= end_date,
                AgentApiUsage.status_code < 400,
            )
        )
        result = await db.execute(stmt)
        successful_requests = result.scalar() or 0
        failed_requests = total_requests - successful_requests

        # Average response time
        stmt = select(func.avg(AgentApiUsage.response_time_ms)).filter(
            and_(
                AgentApiUsage.api_key_id == api_key_id,
                AgentApiUsage.created_at >= start_date,
                AgentApiUsage.created_at <= end_date,
            )
        )
        result = await db.execute(stmt)
        avg_response_time = result.scalar() or 0

        # Total tokens used
        stmt = select(func.sum(AgentApiUsage.tokens_used)).filter(
            and_(
                AgentApiUsage.api_key_id == api_key_id,
                AgentApiUsage.created_at >= start_date,
                AgentApiUsage.created_at <= end_date,
            )
        )
        result = await db.execute(stmt)
        total_tokens = result.scalar() or 0

        # Requests by endpoint
        stmt = (
            select(
                AgentApiUsage.endpoint,
                func.count(AgentApiUsage.id).label("count"),
            )
            .filter(
                and_(
                    AgentApiUsage.api_key_id == api_key_id,
                    AgentApiUsage.created_at >= start_date,
                    AgentApiUsage.created_at <= end_date,
                )
            )
            .group_by(AgentApiUsage.endpoint)
        )
        result = await db.execute(stmt)
        endpoint_stats = result.all()

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            "avg_response_time_ms": round(avg_response_time, 2),
            "total_tokens_used": int(total_tokens),
            "endpoint_stats": [{"endpoint": endpoint, "count": count} for endpoint, count in endpoint_stats],
        }

    @staticmethod
    async def revoke_api_key(db: AsyncSession, api_key_id: UUID) -> bool:
        """
        Revoke (deactivate) an API key.

        Args:
            db: Database session
            api_key_id: API key UUID

        Returns:
            True if revoked successfully, False otherwise
        """
        stmt = select(AgentApiKey).filter(AgentApiKey.id == api_key_id)
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()
        if not api_key:
            return False

        api_key.is_active = False
        await db.commit()

        logger.info(f"Revoked API key {api_key_id}")
        return True

    @staticmethod
    async def update_api_key(
        db: AsyncSession,
        api_key_id: UUID,
        name: str | None = None,
        permissions: list[str] | None = None,
        rate_limit_per_minute: int | None = None,
        rate_limit_per_hour: int | None = None,
        rate_limit_per_day: int | None = None,
        allowed_ips: list[str] | None = None,
        allowed_origins: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> AgentApiKey | None:
        """
        Update an existing API key.

        Args:
            db: Database session
            api_key_id: API key UUID
            name: New name (optional)
            permissions: New permissions (optional)
            rate_limit_per_minute: New per-minute limit (optional)
            rate_limit_per_hour: New per-hour limit (optional)
            rate_limit_per_day: New per-day limit (optional)
            allowed_ips: New allowed IPs (optional)
            allowed_origins: New allowed origins (optional)
            expires_at: New expiration date (optional)

        Returns:
            Updated AgentApiKey or None if not found
        """
        stmt = select(AgentApiKey).filter(AgentApiKey.id == api_key_id)
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()
        if not api_key:
            return None

        if name is not None:
            api_key.key_name = name
        if permissions is not None:
            api_key.permissions = permissions
        if rate_limit_per_minute is not None:
            api_key.rate_limit_per_minute = rate_limit_per_minute
        if rate_limit_per_hour is not None:
            api_key.rate_limit_per_hour = rate_limit_per_hour
        if rate_limit_per_day is not None:
            api_key.rate_limit_per_day = rate_limit_per_day
        if allowed_ips is not None:
            api_key.allowed_ips = allowed_ips
        if allowed_origins is not None:
            api_key.allowed_origins = allowed_origins
        if expires_at is not None:
            api_key.expires_at = expires_at

        await db.commit()
        await db.refresh(api_key)

        logger.info(f"Updated API key {api_key_id}")
        return api_key

    @staticmethod
    async def list_api_keys(
        db: AsyncSession,
        agent_id: UUID,
        include_inactive: bool = False,
    ) -> list[AgentApiKey]:
        """
        List all API keys for an agent.

        Args:
            db: Database session
            agent_id: Agent UUID
            include_inactive: Include inactive keys

        Returns:
            List of AgentApiKey records
        """
        stmt = select(AgentApiKey).filter(AgentApiKey.agent_id == agent_id)

        if not include_inactive:
            stmt = stmt.filter(AgentApiKey.is_active == True)  # noqa: E712

        stmt = stmt.order_by(AgentApiKey.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())
