"""
Authentication service.

Handles user authentication, password hashing, and JWT token management.
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import (
    Account,
    AccountRole,
    AccountStatus,
    Tenant,
    TenantAccountJoin,
    TenantPlan,
    TenantStatus,
)
from src.models.role import Role
from src.models.subscription_plan import PlanTier
from src.services.billing.subscription_service import SubscriptionService
from src.services.integrations.email_service import EmailService

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication operations."""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.

        Args:
            password: Plain text password to verify
            hashed_password: Hashed password to compare against

        Returns:
            True if password matches, False otherwise
        """
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))

    # JWT issuer and audience — read from settings so operators can override them.
    # Access via AuthService.jwt_issuer / AuthService.jwt_audience (properties).
    @staticmethod
    def _jwt_issuer() -> str:
        return settings.jwt_issuer

    @staticmethod
    def _jwt_audience() -> str:
        return settings.jwt_audience

    # Keep these as class-level shortcuts for backward compatibility in tests.
    JWT_ISSUER = "synkora-api"  # default; real value comes from settings
    JWT_AUDIENCE = "synkora-app"  # default; real value comes from settings

    @staticmethod
    def generate_access_token(
        account_id: uuid.UUID,
        tenant_id: uuid.UUID | None = None,
        role: AccountRole | None = None,
        token_version: int = 0,
    ) -> str:
        """
        Generate a JWT access token.

        Args:
            account_id: Account UUID
            tenant_id: Optional tenant UUID for multi-tenancy
            role: Optional role for the account in the tenant
            token_version: Token version for revocation tracking

        Returns:
            JWT access token string
        """
        now = datetime.now(UTC)
        payload = {
            "sub": str(account_id),
            "iat": now,
            "exp": now + timedelta(seconds=settings.jwt_access_token_expires),
            "type": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "ver": token_version,  # Token version for revocation
        }

        if tenant_id:
            payload["tenant_id"] = str(tenant_id)
        if role:
            payload["role"] = role.value

        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def generate_refresh_token(
        account_id: uuid.UUID,
        family_id: str | None = None,
        token_version: int = 0,
    ) -> str:
        """
        Generate a JWT refresh token with rotation support.

        Args:
            account_id: Account UUID
            family_id: Token family ID for rotation tracking
            token_version: Token version for revocation tracking

        Returns:
            JWT refresh token string
        """
        now = datetime.now(UTC)
        payload = {
            "sub": str(account_id),
            "iat": now,
            "exp": now + timedelta(seconds=settings.jwt_refresh_token_expires),
            "type": "refresh",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "ver": token_version,  # Token version for revocation
        }

        # Add family_id for refresh token rotation
        if family_id:
            payload["fid"] = family_id

        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    @staticmethod
    def decode_token(token: str, verify_audience: bool = True) -> dict:
        """
        Decode and validate a JWT token.

        SECURITY: Validates issuer and audience claims to prevent
        token confusion attacks. No backwards compatibility for tokens
        without proper claims - they must re-authenticate.

        Args:
            token: JWT token string
            verify_audience: Whether to verify audience claim (default True)

        Returns:
            Decoded token payload

        Raises:
            jwt.InvalidTokenError: If token is invalid or expired
        """
        options = {}
        kwargs = {
            "algorithms": [settings.jwt_algorithm],
            "issuer": settings.jwt_issuer,
        }

        if verify_audience:
            kwargs["audience"] = settings.jwt_audience
        else:
            options["verify_aud"] = False

        return jwt.decode(
            token,
            settings.jwt_secret_key,
            options=options,
            **kwargs,
        )

    # SECURITY: Account lockout configuration
    _LOCKOUT_THRESHOLD = 5  # Lock after 5 failed attempts
    _LOCKOUT_WINDOW = 900  # 15 minutes window
    _LOCKOUT_DURATION = 1800  # 30 minutes lockout

    @staticmethod
    def _get_redis_client():
        """
        Get Redis client for account lockout tracking.

        Returns None if Redis is unavailable — callers must handle None gracefully.
        Lockout tracking degrades silently rather than blocking all logins.
        """
        try:
            from src.config.redis import get_redis

            redis = get_redis()
            return redis
        except Exception as e:
            logger.warning(f"SECURITY: Redis unavailable for account lockout tracking (degraded mode): {e}")
            return None

    @staticmethod
    def _check_account_lockout(email: str) -> tuple[bool, str | None]:
        """
        Check if account is locked due to too many failed attempts.

        SECURITY: Uses Redis for distributed tracking. If Redis is unavailable,
        fails open (allows login) with a warning — lockout is a security enhancement,
        not a hard gate. A Redis outage must not prevent all logins (denial-of-service).

        Returns:
            Tuple of (is_locked, message)
        """
        import time

        redis_client = AuthService._get_redis_client()
        if redis_client is None:
            # Redis unavailable — skip lockout check, allow login
            return False, None

        try:
            now = time.time()
            key = email.lower()
            redis_key = f"auth:lockout:{key}"

            # Use Redis sorted set for sliding window tracking
            hour_ago = now - AuthService._LOCKOUT_WINDOW

            # Remove old attempts
            redis_client.zremrangebyscore(redis_key, 0, hour_ago)

            # Get current attempt count
            attempt_count = redis_client.zcard(redis_key)

            if attempt_count >= AuthService._LOCKOUT_THRESHOLD:
                # Get most recent attempt timestamp
                recent = redis_client.zrange(redis_key, -1, -1, withscores=True)
                if recent:
                    last_attempt = recent[0][1]
                    if (now - last_attempt) < AuthService._LOCKOUT_DURATION:
                        remaining = int(AuthService._LOCKOUT_DURATION - (now - last_attempt))
                        # Emit audit log on the first lockout tick (attempt_count == threshold)
                        if attempt_count == AuthService._LOCKOUT_THRESHOLD:
                            AuthService._notify_lockout(account_id=None, ip=None)
                        return (
                            True,
                            f"Account locked due to too many failed attempts. Try again in {remaining // 60} minutes.",
                        )
                    else:
                        # Lockout expired, clear attempts
                        redis_client.delete(redis_key)

            return False, None

        except Exception as e:
            logger.error(f"SECURITY DEGRADED: Account lockout Redis unavailable — brute force protection disabled: {e}")
            try:
                from src.services.performance.metrics import SECURITY_DEGRADED_TOTAL

                SECURITY_DEGRADED_TOTAL.labels(feature="account_lockout").inc()
            except Exception:
                pass
            return False, None

    @staticmethod
    def _record_failed_attempt(email: str) -> None:
        """
        Record a failed login attempt.

        SECURITY: Uses Redis for distributed tracking. Fails silently if Redis
        is unavailable — a Redis outage must not break the auth flow.
        """
        import time

        redis_client = AuthService._get_redis_client()
        if redis_client is None:
            return

        try:
            now = time.time()
            key = email.lower()
            redis_key = f"auth:lockout:{key}"

            # Add attempt with timestamp as score
            redis_client.zadd(redis_key, {str(now): now})
            # Set expiry on the key (lockout window + buffer)
            redis_client.expire(redis_key, AuthService._LOCKOUT_WINDOW + 60)

            # Emit lockout alert when threshold is crossed
            attempt_count = redis_client.zcard(redis_key)
            if attempt_count >= AuthService._LOCKOUT_THRESHOLD:
                AuthService._notify_lockout(account_id=key, ip=None)

        except Exception as e:
            logger.error(f"SECURITY DEGRADED: Account lockout Redis unavailable — brute force protection disabled: {e}")
            try:
                from src.services.performance.metrics import SECURITY_DEGRADED_TOTAL

                SECURITY_DEGRADED_TOTAL.labels(feature="account_lockout").inc()
            except Exception:
                pass

    @staticmethod
    def _notify_lockout(account_id: str | None, ip: str | None) -> None:
        """
        Emit a warning-level audit log when an account is locked out.

        This is a stub; extend to send email/Slack alerts in production.
        """
        logger.warning("Account locked: account_id=%s ip=%s", account_id, ip)

    @staticmethod
    def _clear_failed_attempts(email: str) -> None:
        """Clear failed attempts on successful login."""
        key = email.lower()
        redis_key = f"auth:lockout:{key}"

        try:
            redis_client = AuthService._get_redis_client()
            redis_client.delete(redis_key)
        except Exception as e:
            # Non-critical operation - log but don't fail login
            logger.warning(f"Failed to clear login attempts: {e}")

    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str) -> Account | None:
        """
        Authenticate a user with email and password.

        Args:
            db: Async database session
            email: User email
            password: Plain text password

        Returns:
            Account object if authentication successful, None otherwise

        Raises:
            ValueError: If account is locked due to too many failed attempts
        """
        # SECURITY: Check if account is locked
        is_locked, lock_message = AuthService._check_account_lockout(email)
        if is_locked:
            raise ValueError(lock_message)

        result = await db.execute(select(Account).filter_by(email=email))
        account = result.scalar_one_or_none()

        if not account:
            AuthService._record_failed_attempt(email)
            return None

        if not account.password_hash:
            AuthService._record_failed_attempt(email)
            return None

        if not AuthService.verify_password(password, account.password_hash):
            AuthService._record_failed_attempt(email)
            return None

        # Check if account is active
        if account.status != AccountStatus.ACTIVE:
            return None

        # Clear failed attempts on successful login
        AuthService._clear_failed_attempts(email)
        return account

    @staticmethod
    async def register(
        db: AsyncSession,
        email: str,
        password: str,
        name: str,
        tenant_name: str | None = None,
    ) -> tuple[Account, Tenant]:
        """
        Register a new user and optionally create a tenant.

        Args:
            db: Async database session
            email: User email
            password: Plain text password
            name: User name
            tenant_name: Optional tenant name (creates new tenant if provided)

        Returns:
            Tuple of (Account, Tenant)

        Raises:
            ValueError: If email already exists
        """
        # Check if email already exists
        result = await db.execute(select(Account).filter_by(email=email))
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError("Email already registered")

        # Create account as INACTIVE - user needs to verify email first
        account = Account(
            name=name,
            email=email,
            password_hash=AuthService.hash_password(password),
            status=AccountStatus.INACTIVE,
        )
        db.add(account)
        await db.flush()

        # Extract email domain for auto-assignment
        email_domain = email.split("@")[-1].lower() if "@" in email else None

        # Create tenant if name provided
        if tenant_name:
            logger.info(f"Creating tenant with name: {tenant_name}")
            tenant = Tenant(
                name=tenant_name,
                plan=TenantPlan.FREE,
                status=TenantStatus.ACTIVE,
            )
            db.add(tenant)
            await db.flush()
            logger.info(f"Tenant created with ID: {tenant.id}")

            # Get the owner role - try different name variations
            logger.info("Looking for owner role...")

            # First try "Owner" (capitalized - as per seed script)
            result = await db.execute(select(Role).filter_by(name="Owner", tenant_id=None, is_system=True))
            owner_role = result.scalar_one_or_none()

            if owner_role:
                logger.info(f"Found platform-wide 'Owner' role: {owner_role.id}")
            else:
                # Try lowercase "owner"
                result = await db.execute(select(Role).filter_by(name="owner", tenant_id=None, is_system=True))
                owner_role = result.scalar_one_or_none()

                if owner_role:
                    logger.info(f"Found platform-wide 'owner' role: {owner_role.id}")
                else:
                    # List all available roles for debugging
                    result = await db.execute(select(Role).filter_by(tenant_id=None, is_system=True))
                    all_roles = list(result.scalars().all())
                    logger.warning(
                        f"No owner role found! Available system roles: {[(r.name, r.id) for r in all_roles]}"
                    )

            # Add account as owner of tenant with role_id
            logger.info(f"Creating tenant membership for account {account.id} in tenant {tenant.id}")
            membership = TenantAccountJoin(
                tenant_id=tenant.id,
                account_id=account.id,
                role=AccountRole.OWNER,  # Keep for backward compatibility
                role_id=owner_role.id if owner_role else None,
            )
            db.add(membership)
            logger.info(f"Tenant membership created with role_id: {membership.role_id}")

            # Permissions are automatically available through the role_id relationship
            if owner_role:
                logger.info(f"Owner role assigned - permissions will be available through role_id: {owner_role.id}")
            else:
                logger.error("Cannot assign permissions - no owner role found!")
        else:
            # Create a default personal tenant
            logger.info(f"Creating default personal tenant for user: {name}")
            tenant = Tenant(
                name=f"{name}'s Workspace",
                plan=TenantPlan.FREE,
                status=TenantStatus.ACTIVE,
            )
            db.add(tenant)
            await db.flush()
            logger.info(f"Default tenant created with ID: {tenant.id}")

            # Get the owner role - try different name variations
            logger.info("Looking for owner role...")

            # First try "Owner" (capitalized - as per seed script)
            result = await db.execute(select(Role).filter_by(name="Owner", tenant_id=None, is_system=True))
            owner_role = result.scalar_one_or_none()

            if owner_role:
                logger.info(f"Found platform-wide 'Owner' role: {owner_role.id}")
            else:
                # Try lowercase "owner"
                result = await db.execute(select(Role).filter_by(name="owner", tenant_id=None, is_system=True))
                owner_role = result.scalar_one_or_none()

                if owner_role:
                    logger.info(f"Found platform-wide 'owner' role: {owner_role.id}")
                else:
                    # List all available roles for debugging
                    result = await db.execute(select(Role).filter_by(tenant_id=None, is_system=True))
                    all_roles = list(result.scalars().all())
                    logger.warning(
                        f"No owner role found! Available system roles: {[(r.name, r.id) for r in all_roles]}"
                    )

            # Add account as owner of tenant with role_id
            logger.info(f"Creating tenant membership for account {account.id} in tenant {tenant.id}")
            membership = TenantAccountJoin(
                tenant_id=tenant.id,
                account_id=account.id,
                role=AccountRole.OWNER,  # Keep for backward compatibility
                role_id=owner_role.id if owner_role else None,
            )
            db.add(membership)
            logger.info(f"Tenant membership created with role_id: {membership.role_id}")

            # Permissions are automatically available through the role_id relationship
            if owner_role:
                logger.info(f"Owner role assigned - permissions will be available through role_id: {owner_role.id}")
            else:
                logger.error("Cannot assign permissions - no owner role found!")

        await db.commit()
        await db.refresh(account)
        await db.refresh(tenant)

        # Create free subscription for the new tenant
        try:
            subscription_service = SubscriptionService(db)
            free_plan = await subscription_service.get_plan_by_tier(PlanTier.FREE)
            if free_plan:
                await subscription_service.create_subscription(tenant_id=tenant.id, plan_id=free_plan.id)
        except Exception as e:
            # Log error but don't fail registration if subscription creation fails
            logger.error(f"Failed to create free subscription for tenant {tenant.id}: {e}")

        # Auto-assign user to company tenant if domain matches
        if email_domain:
            try:
                # Find tenant with matching domain that has auto-assign enabled
                result = await db.execute(
                    select(Tenant).filter(
                        Tenant.domain == email_domain,
                        Tenant.auto_assign_domain_users == "true",
                        Tenant.status == TenantStatus.ACTIVE,
                    )
                )
                company_tenant = result.scalar_one_or_none()

                if company_tenant and company_tenant.id != tenant.id:
                    logger.info(f"Found company tenant {company_tenant.name} for domain {email_domain}")

                    # Check if user is not already a member
                    result = await db.execute(
                        select(TenantAccountJoin).filter_by(tenant_id=company_tenant.id, account_id=account.id)
                    )
                    existing_membership = result.scalar_one_or_none()

                    if not existing_membership:
                        # Get member role for company tenant
                        result = await db.execute(select(Role).filter_by(name="Member", tenant_id=None, is_system=True))
                        member_role = result.scalar_one_or_none()

                        if not member_role:
                            result = await db.execute(
                                select(Role).filter_by(name="member", tenant_id=None, is_system=True)
                            )
                            member_role = result.scalar_one_or_none()

                        # Add user as member of company tenant
                        company_membership = TenantAccountJoin(
                            tenant_id=company_tenant.id,
                            account_id=account.id,
                            role=AccountRole.NORMAL,
                            role_id=member_role.id if member_role else None,
                            joined_at=datetime.now(UTC).isoformat(),
                        )
                        db.add(company_membership)
                        await db.commit()
                        logger.info(f"Auto-assigned user {email} to company tenant {company_tenant.name}")
            except Exception as e:
                logger.error(f"Error auto-assigning user to company tenant: {e}")
                # Don't fail registration if auto-assignment fails

        return account, tenant

    @staticmethod
    async def get_account_tenants(db: AsyncSession, account_id: uuid.UUID) -> list[dict]:
        """
        Get all tenants for an account with their roles.

        Args:
            db: Async database session
            account_id: Account UUID

        Returns:
            List of dicts with tenant info and role
        """
        from sqlalchemy.orm import selectinload

        result = await db.execute(
            select(TenantAccountJoin).filter_by(account_id=account_id).options(selectinload(TenantAccountJoin.tenant))
        )
        memberships = list(result.scalars().all())

        return [
            {
                "tenant_id": str(membership.tenant_id),
                "tenant_name": membership.tenant.name,
                "role": membership.role.value,
                "is_owner": membership.is_owner,
                "is_admin": membership.is_admin,
                "can_edit": membership.can_edit,
            }
            for membership in memberships
        ]

    @staticmethod
    async def check_permission(
        db: AsyncSession,
        account_id: uuid.UUID,
        tenant_id: uuid.UUID,
        required_role: AccountRole,
    ) -> bool:
        """
        Check if an account has the required role in a tenant.

        Args:
            db: Async database session
            account_id: Account UUID
            tenant_id: Tenant UUID
            required_role: Minimum required role

        Returns:
            True if account has permission, False otherwise
        """
        # Platform admins bypass all tenant role checks
        account_result = await db.execute(select(Account).filter_by(id=account_id))
        account = account_result.scalar_one_or_none()
        if account and str(account.is_platform_admin).lower() == "true":
            return True

        result = await db.execute(select(TenantAccountJoin).filter_by(account_id=account_id, tenant_id=tenant_id))
        membership = result.scalar_one_or_none()

        if not membership:
            return False

        # Role hierarchy: OWNER > ADMIN > EDITOR > NORMAL
        role_hierarchy = {
            AccountRole.OWNER: 4,
            AccountRole.ADMIN: 3,
            AccountRole.EDITOR: 2,
            AccountRole.NORMAL: 1,
        }

        return role_hierarchy.get(membership.role, 0) >= role_hierarchy.get(required_role, 0)

    @staticmethod
    def generate_reset_token() -> str:
        """
        Generate a secure random token for password reset.

        Returns:
            Random token string
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_token(token: str) -> str:
        """
        Hash a token for secure storage.

        SECURITY: Tokens should be hashed before storage to prevent
        database-level attacks. Uses SHA-256 since tokens are already
        high-entropy random values (no need for bcrypt's computational cost).

        Args:
            token: The plaintext token

        Returns:
            Hashed token string
        """
        import hashlib

        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def generate_verification_token() -> str:
        """
        Generate a secure random token for email verification.

        Returns:
            Random token string
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    async def request_password_reset(db: AsyncSession, email: str) -> tuple["Account", str] | None:
        """
        Generate a password reset token for an account.

        Args:
            db: Async database session
            email: User email

        Returns:
            (account, reset_token) tuple if account exists, None otherwise
        """
        result = await db.execute(select(Account).filter_by(email=email))
        account = result.scalar_one_or_none()

        if not account:
            return None

        # Generate reset token
        reset_token = AuthService.generate_reset_token()

        # Set token expiration (1 hour from now)
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        # SECURITY: Store hashed token to prevent database-level attacks
        account.reset_token = AuthService.hash_token(reset_token)
        account.reset_token_expires_at = expires_at.isoformat()

        await db.commit()
        await db.refresh(account)

        return account, reset_token

    @staticmethod
    async def reset_password(db: AsyncSession, token: str, new_password: str) -> Account | None:
        """
        Reset password using a reset token.

        Args:
            db: Async database session
            token: Password reset token
            new_password: New password to set

        Returns:
            Account if successful, None if token invalid or expired
        """
        # SECURITY: Hash the incoming token and compare with stored hash
        token_hash = AuthService.hash_token(token)
        result = await db.execute(select(Account).filter_by(reset_token=token_hash))
        account = result.scalar_one_or_none()

        if not account:
            return None

        # Check if token is expired
        if account.reset_token_expires_at:
            expires_at = datetime.fromisoformat(account.reset_token_expires_at)
            if datetime.now(UTC) > expires_at:
                return None

        # SECURITY: Enforce password history — reject the last 12 reused passwords
        history: list[str] = getattr(account, "password_history", None) or []
        for old_hash in history:
            try:
                if bcrypt.checkpw(new_password.encode("utf-8"), old_hash.encode("utf-8")):
                    raise ValueError("You cannot reuse any of your last 12 passwords")
            except ValueError:
                raise
            except Exception:
                pass  # Corrupt hash entry — skip silently

        # Update password and clear reset token
        new_hash = AuthService.hash_password(new_password)
        account.password_hash = new_hash
        account.reset_token = None
        account.reset_token_expires_at = None

        # Prepend new hash to history, keep only 12 most recent
        updated_history = [new_hash] + history
        account.password_history = updated_history[:12]

        await db.commit()
        await db.refresh(account)

        # SECURITY: Invalidate all existing sessions after password reset
        # This ensures any stolen tokens become invalid after password change
        try:
            from src.services.security.token_blacklist import TokenBlacklistService

            blacklist_service = TokenBlacklistService()
            blacklist_service.blacklist_all_account_tokens(account.id)
            logger.info(f"Invalidated all sessions for account {account.id} after password reset")
        except Exception as e:
            # Log but don't fail the password reset if blacklist fails
            logger.warning(f"Failed to invalidate sessions after password reset: {e}")

        return account

    @staticmethod
    async def send_verification_email(
        db: AsyncSession, account_id: uuid.UUID, base_url: str = "https://synkora.ai"
    ) -> dict:
        """
        Generate verification token and send verification email.

        Args:
            db: Async database session
            account_id: Account UUID
            base_url: Base URL for verification link

        Returns:
            Dict with success status and message
        """
        result = await db.execute(select(Account).filter_by(id=account_id))
        account = result.scalar_one_or_none()

        if not account:
            return {"success": False, "message": "Account not found."}

        # Generate verification token
        verification_token = AuthService.generate_verification_token()

        # SECURITY: Store hashed token to prevent database-level attacks
        account.email_verification_token = AuthService.hash_token(verification_token)
        account.email_verification_sent_at = datetime.now(UTC).isoformat()

        await db.commit()
        await db.refresh(account)

        # Send verification email (with the UNHASHED token - user needs this)
        email_service = EmailService(db)

        # Get tenant_id from account's first tenant membership
        tenant_id = None
        result = await db.execute(select(TenantAccountJoin).filter_by(account_id=account.id))
        membership = result.scalar_one_or_none()
        if membership:
            tenant_id = membership.tenant_id

        result = await email_service.send_verification_email(
            to_email=account.email, verification_token=verification_token, tenant_id=tenant_id, base_url=base_url
        )

        if result["success"]:
            return {"success": True, "message": "Verification email sent successfully."}
        else:
            logger.error(f"Failed to send verification email: {result['message']}")
            return {"success": False, "message": "Failed to send verification email. Please try again later."}

    @staticmethod
    async def verify_email(db: AsyncSession, token: str) -> Account | None:
        """
        Verify email using a verification token.

        Args:
            db: Async database session
            token: Email verification token

        Returns:
            Account if successful, None if token invalid
        """
        # SECURITY: Hash the incoming token and compare with stored hash
        token_hash = AuthService.hash_token(token)
        result = await db.execute(select(Account).filter_by(email_verification_token=token_hash))
        account = result.scalar_one_or_none()

        if not account:
            return None

        # SECURITY: Check verification link expiry (72 hours)
        if account.email_verification_sent_at:
            sent_at = (
                datetime.fromisoformat(account.email_verification_sent_at)
                if isinstance(account.email_verification_sent_at, str)
                else account.email_verification_sent_at
            )
            if hasattr(sent_at, "tzinfo") and sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=UTC)
            if datetime.now(UTC) > sent_at + timedelta(hours=72):
                return {
                    "error": "verification_link_expired",
                    "message": "This verification link has expired. Please request a new one.",
                }

        # Mark email as verified and activate account
        account.email_verification_token = None

        # Activate account
        account.status = AccountStatus.ACTIVE

        await db.commit()
        await db.refresh(account)

        # Queue welcome email
        try:
            from src.tasks.email_tasks import send_welcome_email_task
            from src.utils.config_helper import get_app_base_url

            base_url = await get_app_base_url(db)
            send_welcome_email_task.delay(account_id=str(account.id), base_url=base_url)
            logger.info(f"Welcome email task queued for account {account.id}")
        except Exception as e:
            logger.error(f"Failed to queue welcome email: {e}")

        return account

    @staticmethod
    async def generate_backup_codes(account_id: uuid.UUID, db: AsyncSession) -> list[str]:
        """
        Generate 8 single-use 2FA backup/recovery codes.

        SECURITY: Only the SHA-256 hashes are stored; plaintext codes are returned
        exactly once and must be saved by the user.

        Args:
            account_id: Account UUID
            db: Async database session

        Returns:
            List of 8 plaintext backup codes (shown to user once)
        """
        import hashlib as _hashlib

        result = await db.execute(select(Account).filter_by(id=account_id))
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError("Account not found")

        codes = [secrets.token_hex(5).upper() for _ in range(8)]
        hashed = [_hashlib.sha256(c.encode()).hexdigest() for c in codes]

        account.two_factor_backup_codes = hashed
        await db.commit()

        return codes

    @staticmethod
    async def consume_backup_code(account_id: uuid.UUID, code: str, db: AsyncSession) -> bool:
        """
        Check and consume a 2FA backup code.

        SECURITY: Uses constant-time hash comparison; removes code after first use
        to prevent replay.

        Args:
            account_id: Account UUID
            code: Plaintext backup code supplied by the user
            db: Async database session

        Returns:
            True if code was valid and has been consumed, False otherwise
        """
        import hashlib as _hashlib

        result = await db.execute(select(Account).filter_by(id=account_id))
        account = result.scalar_one_or_none()
        if not account or not account.two_factor_backup_codes:
            return False

        stored: list[str] = account.two_factor_backup_codes if isinstance(account.two_factor_backup_codes, list) else []

        code_hash = _hashlib.sha256(code.upper().encode()).hexdigest()

        # Constant-time check across all stored hashes to prevent timing oracle
        matched_index = None
        for i, h in enumerate(stored):
            if secrets.compare_digest(h, code_hash):
                matched_index = i
                break

        if matched_index is None:
            return False

        # Consume the code (remove it so it cannot be reused)
        stored.pop(matched_index)
        account.two_factor_backup_codes = stored
        await db.commit()

        logger.info(f"2FA backup code consumed for account {account_id}")

        # SECURITY AUDIT: log every backup-code use so operators can detect abuse
        try:
            from src.models import TenantAccountJoin
            from src.services.activity.activity_log_service import ActivityLogService

            tenant_id = None
            result = await db.execute(select(TenantAccountJoin).filter_by(account_id=account_id))
            membership = result.scalar_one_or_none()
            if membership:
                tenant_id = membership.tenant_id

            ActivityLogService.queue_activity(
                tenant_id=tenant_id,
                account_id=account_id,
                action="mfa_backup_code_used",
                resource_type="account",
                resource_id=account_id,
            )
        except Exception as _audit_exc:
            logger.warning(f"Failed to write mfa_backup_code_used audit log: {_audit_exc}")

        return True
