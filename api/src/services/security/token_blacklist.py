"""
Token blacklist service for session management.

Provides Redis-backed token blacklisting for secure session revocation.
When a user logs out, their tokens are blacklisted until they expire.
"""

import hashlib
import hmac
import logging
import uuid

from src.config import settings

logger = logging.getLogger(__name__)

# Redis key prefixes
TOKEN_BLACKLIST_PREFIX = "token:blacklist:"
ACCOUNT_TOKENS_PREFIX = "account:tokens:"
REFRESH_TOKEN_FAMILY_PREFIX = "refresh:family:"


class TokenBlacklistService:
    """
    Service for managing token blacklisting using Redis.

    SECURITY: Tokens are hashed before storage to prevent exposure
    if Redis data is compromised.
    """

    def __init__(self):
        """Initialize the token blacklist service."""
        self._redis = None

    @property
    def redis(self):
        """Lazy-load Redis connection."""
        if self._redis is None:
            from src.config.redis import get_redis

            self._redis = get_redis()
        return self._redis

    @staticmethod
    def _hash_token(token: str) -> str:
        """
        Hash a token for secure storage.

        SECURITY: We hash tokens before storing them in Redis so that
        even if Redis is compromised, the actual tokens aren't exposed.
        """
        return hashlib.sha256(token.encode()).hexdigest()

    def blacklist_token(self, token: str, expires_in: int | None = None) -> bool:
        """
        Add a token to the blacklist.

        Args:
            token: JWT token to blacklist
            expires_in: Seconds until the blacklist entry expires.
                       If None, uses the access token expiry time.

        Returns:
            True if successfully blacklisted
        """
        try:
            token_hash = self._hash_token(token)
            key = f"{TOKEN_BLACKLIST_PREFIX}{token_hash}"

            # Default to access token expiry plus a buffer
            if expires_in is None:
                expires_in = settings.jwt_access_token_expires + 60

            # Store with expiration (Redis will auto-cleanup)
            self.redis.setex(key, expires_in, "1")
            logger.debug(f"Token blacklisted, expires in {expires_in}s")
            return True

        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False

    def is_blacklisted(self, token: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            token: JWT token to check

        Returns:
            True if token is blacklisted
        """
        try:
            token_hash = self._hash_token(token)
            key = f"{TOKEN_BLACKLIST_PREFIX}{token_hash}"
            return self.redis.exists(key) > 0

        except Exception as e:
            # SECURITY: If Redis is unavailable, fail closed (treat as blacklisted)
            # This prevents bypassing security during Redis outages
            logger.error(f"Failed to check token blacklist: {e}")
            return True

    def blacklist_all_account_tokens(self, account_id: uuid.UUID) -> bool:
        """
        Blacklist all tokens for an account by incrementing their token version.

        This approach uses a version number instead of tracking individual tokens.
        Any token issued before the version increment is considered invalid.

        Args:
            account_id: Account UUID to revoke all tokens for

        Returns:
            True if successful
        """
        try:
            key = f"{ACCOUNT_TOKENS_PREFIX}{account_id}:version"
            # Increment version and set expiration to max token lifetime
            self.redis.incr(key)
            self.redis.expire(key, settings.jwt_refresh_token_expires + 3600)
            logger.info(f"All tokens revoked for account {account_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke account tokens: {e}")
            return False

    def get_account_token_version(self, account_id: uuid.UUID) -> int:
        """
        Get the current token version for an account.

        Args:
            account_id: Account UUID

        Returns:
            Current token version (0 if not set)
        """
        try:
            key = f"{ACCOUNT_TOKENS_PREFIX}{account_id}:version"
            version = self.redis.get(key)
            # Accounts that have never had their tokens revoked have no Redis key;
            # return 0 which matches the default "ver" claim in JWTs.
            return int(version) if version else 0

        except Exception as e:
            # SECURITY: Fail closed — return -1 which will never match any valid
            # token version (JWT "ver" claim starts at 0), so all tokens are
            # rejected when Redis is unavailable rather than silently restored.
            logger.error(f"Failed to get token version: {e}")
            return -1

    def store_refresh_token_family(self, account_id: uuid.UUID, family_id: str, refresh_token_hash: str) -> bool:
        """
        Store a refresh token in its family for rotation tracking.

        Refresh token rotation creates a "family" of tokens. When a refresh
        token is used, a new one is issued. If an old token from the family
        is reused, the entire family is invalidated (potential token theft).

        Args:
            account_id: Account UUID
            family_id: Unique identifier for this refresh token family
            refresh_token_hash: Hash of the current valid refresh token

        Returns:
            True if successful
        """
        try:
            key = f"{REFRESH_TOKEN_FAMILY_PREFIX}{account_id}:{family_id}"
            # Store with refresh token expiration
            self.redis.setex(key, settings.jwt_refresh_token_expires, refresh_token_hash)
            return True

        except Exception as e:
            logger.error(f"Failed to store refresh token family: {e}")
            return False

    def validate_refresh_token_family(self, account_id: uuid.UUID, family_id: str, refresh_token_hash: str) -> bool:
        """
        Validate a refresh token against its family.

        Args:
            account_id: Account UUID
            family_id: Refresh token family ID
            refresh_token_hash: Hash of the refresh token to validate

        Returns:
            True if the token is the current valid token in the family
        """
        try:
            key = f"{REFRESH_TOKEN_FAMILY_PREFIX}{account_id}:{family_id}"
            stored_hash = self.redis.get(key)
            if stored_hash is None:
                return False
            # SECURITY: Use constant-time comparison to prevent timing attacks
            if isinstance(stored_hash, bytes):
                stored_hash = stored_hash.decode()
            return hmac.compare_digest(stored_hash, refresh_token_hash)

        except Exception as e:
            logger.warning(f"Failed to validate refresh token family: {e}")
            return False

    def invalidate_refresh_token_family(self, account_id: uuid.UUID, family_id: str) -> bool:
        """
        Invalidate an entire refresh token family (e.g., on logout or theft detection).

        Args:
            account_id: Account UUID
            family_id: Refresh token family ID to invalidate

        Returns:
            True if successful
        """
        try:
            key = f"{REFRESH_TOKEN_FAMILY_PREFIX}{account_id}:{family_id}"
            self.redis.delete(key)
            # Also delete the session creation timestamp for this family
            ts_key = f"session:created:{account_id}:{family_id}"
            self.redis.delete(ts_key)
            logger.info(f"Refresh token family {family_id} invalidated for account {account_id}")
            return True

        except Exception as e:
            logger.warning(f"Failed to invalidate refresh token family: {e}")
            return False

    def store_session_created_at(self, account_id: uuid.UUID, family_id: str, created_at_ts: float) -> bool:
        """
        Store the original session creation timestamp for a refresh-token family.

        Used by refresh_session() to enforce the absolute maximum session lifetime
        (JWT_MAX_SESSION_AGE_HOURS) regardless of valid refresh tokens.

        Args:
            account_id: Account UUID
            family_id: Refresh token family ID
            created_at_ts: Unix timestamp of when the session was first created

        Returns:
            True if successful
        """
        try:
            key = f"session:created:{account_id}:{family_id}"
            # TTL matches the refresh token lifetime so it auto-expires
            self.redis.set(key, str(created_at_ts), ex=settings.jwt_refresh_token_expires, nx=True)
            return True
        except Exception as e:
            logger.warning(f"Failed to store session created_at: {e}")
            return False

    def get_session_created_at(self, account_id: uuid.UUID, family_id: str) -> float | None:
        """
        Retrieve the original session creation timestamp for a refresh-token family.

        Args:
            account_id: Account UUID
            family_id: Refresh token family ID

        Returns:
            Unix timestamp float, or None if not found
        """
        try:
            key = f"session:created:{account_id}:{family_id}"
            value = self.redis.get(key)
            return float(value) if value else None
        except Exception as e:
            logger.warning(f"Failed to get session created_at: {e}")
            return None


# Module-level singleton — initialized once at import time, which is inherently
# thread-safe in CPython (module imports are protected by the import lock).
# This avoids the race condition in a check-then-set pattern under concurrent load.
_token_blacklist_service = TokenBlacklistService()


def get_token_blacklist_service() -> TokenBlacklistService:
    """Get the token blacklist service singleton."""
    return _token_blacklist_service
