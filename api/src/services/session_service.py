"""
Session management service.

Handles user sessions, refresh tokens, and session tracking.
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import Account
from src.services.auth_service import AuthService
from src.services.security.token_blacklist import get_token_blacklist_service

logger = logging.getLogger(__name__)


class SessionService:
    """Service for managing user sessions."""

    @staticmethod
    async def create_session(
        db: AsyncSession,
        account: Account,
        tenant_id: uuid.UUID | None = None,
        family_id: str | None = None,
    ) -> dict:
        """
        Create a new session for an account.

        Args:
            db: Async database session
            account: Account object
            tenant_id: Optional tenant ID for multi-tenancy
            family_id: Optional refresh token family ID for rotation

        Returns:
            Dict with access_token, refresh_token, and expiry info
        """
        # Get account's role in tenant if tenant_id provided
        role = None
        if tenant_id:
            from src.models import TenantAccountJoin

            stmt = select(TenantAccountJoin).filter_by(account_id=account.id, tenant_id=tenant_id)
            result = await db.execute(stmt)
            membership = result.scalar_one_or_none()
            if membership:
                role = membership.role

        # Get current token version for the account
        blacklist_service = get_token_blacklist_service()
        token_version = blacklist_service.get_account_token_version(account.id)

        # Generate new family_id if not provided (new login)
        if family_id is None:
            family_id = secrets.token_urlsafe(16)

        # Generate tokens with version and family
        access_token = AuthService.generate_access_token(account.id, tenant_id, role, token_version=token_version)
        refresh_token = AuthService.generate_refresh_token(account.id, family_id=family_id, token_version=token_version)

        # Store refresh token in family for rotation tracking.
        # Also persist session_created_at so refresh_session() can enforce
        # the absolute maximum session lifetime (JWT_MAX_SESSION_AGE_HOURS).
        refresh_token_hash = blacklist_service._hash_token(refresh_token)
        blacklist_service.store_refresh_token_family(account.id, family_id, refresh_token_hash)

        # Store session creation timestamp in Redis (keyed by family_id)
        _now_ts = datetime.now(UTC).timestamp()
        blacklist_service.store_session_created_at(account.id, family_id, _now_ts)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": settings.jwt_access_token_expires,
            "account_id": str(account.id),
            "tenant_id": str(tenant_id) if tenant_id else None,
        }

    @staticmethod
    async def refresh_session(db: AsyncSession, refresh_token: str, tenant_id: uuid.UUID | None = None) -> dict:
        """
        Refresh a session using a refresh token with rotation.

        SECURITY: Implements refresh token rotation. Each refresh token can only
        be used once. If a token is reused, the entire family is invalidated
        (indicating potential token theft).

        Args:
            db: Async database session
            refresh_token: Refresh token string
            tenant_id: Optional tenant ID to preserve context (recommended)

        Returns:
            Dict with new access_token and refresh_token

        Raises:
            ValueError: If refresh token is invalid, expired, or reused
        """
        blacklist_service = get_token_blacklist_service()

        try:
            # Check if token is blacklisted
            if blacklist_service.is_blacklisted(refresh_token):
                raise ValueError("Token has been revoked")

            # Decode refresh token
            payload = AuthService.decode_token(refresh_token)

            # Verify it's a refresh token
            if payload.get("type") != "refresh":
                raise ValueError("Invalid token type")

            # Get account
            account_id = uuid.UUID(payload["sub"])
            stmt = select(Account).filter_by(id=account_id)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()

            if not account or account.status != "ACTIVE":
                raise ValueError("Invalid or inactive account")

            # SECURITY: Validate token version
            token_version = payload.get("ver", 0)
            current_version = blacklist_service.get_account_token_version(account_id)
            if token_version < current_version:
                logger.warning(f"Stale token version for account {account_id}")
                raise ValueError("Token has been revoked")

            # SECURITY: Validate refresh token family (rotation check)
            family_id = payload.get("fid")
            if family_id:
                refresh_token_hash = blacklist_service._hash_token(refresh_token)
                if not blacklist_service.validate_refresh_token_family(account_id, family_id, refresh_token_hash):
                    # Token reuse detected - potential theft!
                    # Invalidate the entire family
                    logger.warning(
                        f"SECURITY: Refresh token reuse detected for account {account_id}, "
                        f"family {family_id}. Invalidating family."
                    )
                    blacklist_service.invalidate_refresh_token_family(account_id, family_id)
                    raise ValueError("Refresh token reuse detected. Please log in again.")

                # SECURITY: Enforce absolute maximum session lifetime.
                # Even with a valid refresh token, a session that started more than
                # JWT_MAX_SESSION_AGE_HOURS ago must require re-login.
                session_created_at_ts = blacklist_service.get_session_created_at(account_id, family_id)
                if session_created_at_ts is not None:
                    max_age_hours = settings.jwt_max_session_age_hours
                    session_age = datetime.now(UTC) - datetime.fromtimestamp(session_created_at_ts, tz=UTC)
                    if session_age > timedelta(hours=max_age_hours):
                        logger.warning(
                            f"SECURITY: Session age {session_age} exceeds max allowed "
                            f"{max_age_hours}h for account {account_id}. Forcing re-login."
                        )
                        blacklist_service.invalidate_refresh_token_family(account_id, family_id)
                        raise ValueError(
                            f"Session has exceeded the maximum lifetime of {max_age_hours} hours. Please log in again."
                        )

            # Use provided tenant_id or try to extract from payload
            if tenant_id is None and "tenant_id" in payload:
                tenant_id = uuid.UUID(payload["tenant_id"])

            if tenant_id is None:
                from src.models import TenantAccountJoin

                stmt = select(TenantAccountJoin).filter_by(account_id=account_id)
                result = await db.execute(stmt)
                membership = result.scalar_one_or_none()
                if membership:
                    tenant_id = membership.tenant_id

            # Blacklist the old refresh token (single use)
            blacklist_service.blacklist_token(refresh_token, settings.jwt_refresh_token_expires)

            # Create new session with same family (rotation)
            return await SessionService.create_session(db, account, tenant_id, family_id=family_id)

        except ValueError:
            raise
        except jwt.ExpiredSignatureError:
            # Expected when a user's refresh token has naturally expired — not an error.
            raise ValueError("Session expired. Please log in again.")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid refresh token: {e}")
            raise ValueError("Invalid session token. Please log in again.")
        except Exception as e:
            logger.error(f"Failed to refresh session: {e}")
            raise ValueError(f"Failed to refresh session: {str(e)}") from e

    @staticmethod
    async def revoke_session(db: AsyncSession, account_id: uuid.UUID, access_token: str | None = None) -> bool:
        """
        Revoke sessions for an account.

        If access_token is provided, only that specific token is blacklisted.
        Otherwise, all tokens for the account are invalidated by incrementing
        the account's token version.

        Args:
            db: Async database session
            account_id: Account UUID
            access_token: Optional specific token to revoke

        Returns:
            True if successful
        """
        blacklist_service = get_token_blacklist_service()

        try:
            # Verify account exists
            stmt = select(Account).filter_by(id=account_id)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()
            if not account:
                return False

            if access_token:
                # Blacklist the specific token
                blacklist_service.blacklist_token(access_token)
                logger.info(f"Session revoked for account {account_id}")
            else:
                # Revoke ALL tokens by incrementing version
                blacklist_service.blacklist_all_account_tokens(account_id)
                logger.info(f"All sessions revoked for account {account_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to revoke session: {e}")
            return False

    @staticmethod
    async def validate_session(db: AsyncSession, access_token: str) -> dict | None:
        """
        Validate an access token and return session info.

        SECURITY: Checks token blacklist and version before accepting.

        Args:
            db: Async database session
            access_token: Access token string

        Returns:
            Dict with session info if valid, None otherwise
        """
        blacklist_service = get_token_blacklist_service()

        try:
            # SECURITY: Check if token is blacklisted
            if blacklist_service.is_blacklisted(access_token):
                logger.debug("Token is blacklisted")
                return None

            payload = AuthService.decode_token(access_token)

            # Verify it's an access token
            if payload.get("type") != "access":
                return None

            # Get account
            account_id = uuid.UUID(payload["sub"])
            stmt = select(Account).filter_by(id=account_id)
            result = await db.execute(stmt)
            account = result.scalar_one_or_none()

            if not account or account.status != "ACTIVE":
                return None

            # SECURITY: Validate token version
            token_version = payload.get("ver", 0)
            current_version = blacklist_service.get_account_token_version(account_id)
            if token_version < current_version:
                logger.debug(f"Token version {token_version} < current {current_version}")
                return None

            return {
                "account_id": str(account.id),
                "account_email": account.email,
                "account_name": account.name,
                "tenant_id": payload.get("tenant_id"),
                "role": payload.get("role"),
                "expires_at": datetime.fromtimestamp(payload["exp"]),
            }

        except Exception:
            return None

    @staticmethod
    async def switch_tenant(db: AsyncSession, account_id: uuid.UUID, tenant_id: uuid.UUID) -> dict:
        """
        Switch the active tenant for a session.

        Args:
            db: Async database session
            account_id: Account UUID
            tenant_id: New tenant UUID

        Returns:
            Dict with new access_token for the tenant

        Raises:
            ValueError: If account doesn't have access to tenant
        """
        from src.models import TenantAccountJoin

        # Verify account has access to tenant
        stmt = select(TenantAccountJoin).filter_by(account_id=account_id, tenant_id=tenant_id)
        result = await db.execute(stmt)
        membership = result.scalar_one_or_none()

        if not membership:
            raise ValueError("Account does not have access to this tenant")

        # Get account
        stmt = select(Account).filter_by(id=account_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        if not account or account.status != "ACTIVE":
            raise ValueError("Invalid or inactive account")

        # Generate new access token with tenant context
        access_token = AuthService.generate_access_token(account.id, tenant_id, membership.role)

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": settings.jwt_access_token_expires,
            "tenant_id": str(tenant_id),
            "role": membership.role.value,
        }

    @staticmethod
    async def get_active_sessions_count(db: AsyncSession, account_id: uuid.UUID) -> int:
        """
        Get count of active sessions for an account.

        In a production system, this would query Redis for active tokens.
        For now, this is a placeholder.

        Args:
            db: Async database session
            account_id: Account UUID

        Returns:
            Number of active sessions
        """
        # Session tracking in Redis can be added for distributed deployments
        # For now, just verify account exists
        stmt = select(Account).filter_by(id=account_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()
        return 1 if account else 0
