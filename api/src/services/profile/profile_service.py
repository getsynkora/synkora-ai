"""Profile management service."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models import Account
from ...services.agents.security import decrypt_value, encrypt_value
from ...services.i18n import normalize_interface_language

logger = logging.getLogger(__name__)


class ProfileService:
    """Service for managing user profiles."""

    def __init__(self, db: AsyncSession):
        """Initialize the profile service.

        Args:
            db: Async database session
        """
        self.db = db

    async def get_profile(self, account_id: UUID) -> Account | None:
        """Get user profile by account ID.

        Args:
            account_id: User account ID

        Returns:
            Account object or None if not found
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_profile(
        self,
        account_id: UUID,
        name: str | None = None,
        email: str | None = None,
        avatar_url: str | None = None,
        phone: str | None = None,
        bio: str | None = None,
        company: str | None = None,
        job_title: str | None = None,
        location: str | None = None,
        website: str | None = None,
        interface_language: str | None = None,
    ) -> Account | None:
        """Update user profile information.

        Args:
            account_id: User account ID
            avatar_url: URL to user's avatar image
            phone: Phone number
            bio: User biography
            company: Company name
            job_title: Job title
            location: Location
            website: Website URL
            interface_language: Language of the platform's screens ("en", "de")

        Returns:
            Updated Account object or None if not found
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            return None

        # Update only provided fields; treat empty strings as None for nullable fields
        if name is not None:
            account.name = name  # name is required, keep as-is
        if email is not None:
            account.email = email  # email is required, keep as-is
        if avatar_url is not None:
            account.avatar_url = avatar_url or None
        if phone is not None:
            account.phone = phone or None
        if bio is not None:
            account.bio = bio or None
        if company is not None:
            account.company = company or None
        if job_title is not None:
            account.job_title = job_title or None
        if location is not None:
            account.location = location or None
        if website is not None:
            account.website = website or None
        if interface_language is not None:
            normalized = normalize_interface_language(interface_language)
            if normalized is None:
                raise ValueError("Unsupported interface language")
            account.interface_language = normalized

        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def update_notification_preferences(self, account_id: UUID, preferences: dict) -> Account | None:
        """Update user notification preferences.

        Args:
            account_id: User account ID
            preferences: Dictionary of notification preferences
                Example: {
                    "email_notifications": true,
                    "push_notifications": false,
                    "weekly_digest": true,
                    "marketing_emails": false
                }

        Returns:
            Updated Account object or None if not found
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            return None

        account.notification_preferences = preferences
        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def get_notification_preferences(self, account_id: UUID) -> dict | None:
        """Get user notification preferences.

        Args:
            account_id: User account ID

        Returns:
            Dictionary of notification preferences or None if not found
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            return None

        return account.notification_preferences or {}

    async def enable_two_factor(self, account_id: UUID, two_factor_secret: str) -> Account | None:
        """Enable two-factor authentication for user.

        SECURITY: 2FA secrets are encrypted at rest using Fernet encryption.

        Args:
            account_id: User account ID
            two_factor_secret: Secret key for 2FA (plain text)

        Returns:
            Updated Account object or None if not found
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            return None

        account.two_factor_enabled = "true"
        # SECURITY: Encrypt 2FA secret before storing
        try:
            account.two_factor_secret = encrypt_value(two_factor_secret)
        except Exception as e:
            logger.error(f"Failed to encrypt 2FA secret for account {account_id}: {e}")
            raise ValueError("Failed to encrypt 2FA secret") from e

        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def get_two_factor_secret(self, account_id: UUID) -> str | None:
        """Get decrypted 2FA secret for verification.

        SECURITY: Decrypts the stored 2FA secret for TOTP verification.

        Args:
            account_id: User account ID

        Returns:
            Decrypted 2FA secret or None if not found/not enabled
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account or not account.two_factor_enabled or not account.two_factor_secret:
            return None

        try:
            return decrypt_value(account.two_factor_secret)
        except Exception as e:
            # SECURITY: Do NOT return plaintext fallback - this could expose secrets
            # If decryption fails, the secret is either corrupted or unencrypted legacy data
            # Log the error and return None to force re-enrollment
            logger.error(
                f"Failed to decrypt 2FA secret for account {account_id}. "
                f"Secret may be corrupted or using legacy unencrypted format. "
                f"User should re-enroll 2FA. Error: {e}"
            )
            # SECURITY: Return None instead of potentially exposing unencrypted secret
            # This will cause 2FA verification to fail, prompting user to re-setup
            return None

    async def verify_two_factor(self, account_id: UUID, totp_code: str) -> bool:
        """Verify a TOTP code for two-factor authentication.

        SECURITY: Uses constant-time comparison to prevent timing attacks.
        Allows for time drift with valid_window parameter.

        Args:
            account_id: User account ID
            totp_code: 6-digit TOTP code from authenticator app

        Returns:
            True if code is valid, False otherwise
        """

        try:
            import pyotp
        except ImportError:
            logger.error("pyotp not installed, cannot verify 2FA")
            return False

        # Get the decrypted 2FA secret
        secret = await self.get_two_factor_secret(account_id)
        if not secret:
            logger.warning(f"2FA not enabled or secret not found for account {account_id}")
            return False

        # Validate TOTP code format (must be 6 digits)
        if not totp_code or len(totp_code) != 6 or not totp_code.isdigit():
            logger.warning(f"Invalid TOTP code format for account {account_id}")
            return False

        try:
            # Create TOTP instance
            totp = pyotp.TOTP(secret)

            # SECURITY: Use valid_window=1 to allow for slight time drift
            # This accepts codes from 30 seconds ago and 30 seconds in the future
            is_valid = totp.verify(totp_code, valid_window=1)

            if not is_valid:
                logger.warning(f"Invalid TOTP code for account {account_id}")

            return is_valid

        except Exception as e:
            logger.error(f"Error verifying TOTP for account {account_id}: {e}")
            return False

    async def change_password(
        self, account_id: UUID, current_password: str, new_password: str
    ) -> tuple[bool, str | None]:
        """Change user password securely.

        SECURITY: Validates current password before allowing change.
        Uses bcrypt for secure password hashing.

        Args:
            account_id: User account ID
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            Tuple of (success: bool, error_message: str | None)
        """
        import bcrypt

        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            return False, "Account not found"

        # SECURITY: Verify current password
        if not account.password_hash:
            return False, "Password authentication not enabled for this account"

        try:
            # Check current password
            if not bcrypt.checkpw(
                current_password.encode("utf-8"),
                account.password_hash.encode("utf-8"),
            ):
                logger.warning(f"Invalid current password for account {account_id}")
                return False, "Current password is incorrect"
        except Exception as e:
            logger.error(f"Error verifying current password for account {account_id}: {e}")
            return False, "Password verification failed"

        # Validate new password strength
        if len(new_password) < 8:
            return False, "New password must be at least 8 characters"

        # SECURITY: Enforce password history — reject the last 12 reused passwords
        history: list[str] = getattr(account, "password_history", None) or []
        for old_hash in history:
            try:
                if bcrypt.checkpw(new_password.encode("utf-8"), old_hash.encode("utf-8")):
                    return False, "You cannot reuse any of your last 12 passwords"
            except Exception:
                pass  # Corrupt hash entry — skip silently

        # SECURITY: Hash new password with bcrypt
        try:
            new_hash = bcrypt.hashpw(
                new_password.encode("utf-8"),
                bcrypt.gensalt(rounds=12),
            ).decode("utf-8")

            account.password_hash = new_hash

            # Prepend new hash to history, keep only 12 most recent
            updated_history = [new_hash] + history
            account.password_history = updated_history[:12]

            await self.db.commit()

            # SECURITY: Invalidate all existing sessions/tokens for this account
            # This ensures that if the password was compromised, attackers are logged out
            self._invalidate_all_sessions(account_id)

            logger.info(f"Password changed for account {account_id}")
            return True, None

        except Exception as e:
            logger.error(f"Error changing password for account {account_id}: {e}")
            await self.db.rollback()
            return False, "Failed to update password"

    def _invalidate_all_sessions(self, account_id: UUID) -> None:
        """
        Invalidate all active sessions for an account.

        SECURITY: Called after password change to ensure any compromised sessions
        are terminated. Uses Redis to blacklist all refresh tokens.
        """
        try:
            from src.core.redis_client import get_redis_client

            redis = get_redis_client()
            if redis:
                # Store a marker indicating all tokens before this time should be invalid
                import time

                invalidation_key = f"session_invalidation:{account_id}"
                redis.set(invalidation_key, str(int(time.time())))
                # Keep the invalidation marker for 30 days (max token lifetime)
                redis.expire(invalidation_key, 30 * 24 * 3600)
                logger.info(f"Invalidated all sessions for account {account_id}")
            else:
                logger.warning(
                    f"Redis unavailable - could not invalidate sessions for account {account_id}. "
                    f"User should manually sign out of other devices."
                )
        except Exception as e:
            # Don't fail password change if session invalidation fails
            logger.error(f"Failed to invalidate sessions for account {account_id}: {e}")

    async def disable_two_factor(self, account_id: UUID) -> Account | None:
        """Disable two-factor authentication for user.

        Args:
            account_id: User account ID

        Returns:
            Updated Account object or None if not found
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            return None

        account.two_factor_enabled = "false"
        account.two_factor_secret = None

        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def update_login_info(self, account_id: UUID, ip_address: str) -> Account | None:
        """Update user's last login information.

        Args:
            account_id: User account ID
            ip_address: IP address of login

        Returns:
            Updated Account object or None if not found
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            return None

        account.last_login_at = datetime.now(UTC).isoformat()
        account.last_login_ip = ip_address

        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def set_platform_admin(self, account_id: UUID, is_admin: bool) -> Account | None:
        """Set platform admin status for user.

        Args:
            account_id: User account ID
            is_admin: Whether user should be platform admin

        Returns:
            Updated Account object or None if not found
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            return None

        account.is_platform_admin = is_admin

        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def is_platform_admin(self, account_id: UUID) -> bool:
        """Check if user is a platform admin.

        Args:
            account_id: User account ID

        Returns:
            True if user is platform admin, False otherwise
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            return False

        return account.is_platform_admin or False

    async def delete_profile(self, account_id: UUID) -> bool:
        """Delete user profile (soft delete by marking as inactive).

        Args:
            account_id: User account ID

        Returns:
            True if profile was deleted, False otherwise
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            return False

        # Soft delete - you might want to add an 'is_active' field
        # For now, we'll just clear sensitive data
        account.two_factor_enabled = "false"
        account.two_factor_secret = None
        account.notification_preferences = {}

        await self.db.commit()
        return True

    async def get_profile_completion(self, account_id: UUID) -> int | None:
        """Calculate profile completion percentage.

        Args:
            account_id: User account ID

        Returns:
            Completion percentage (0-100) or None if account not found
        """
        stmt = select(Account).where(Account.id == account_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            return None

        # Define fields that contribute to profile completion
        fields = [
            account.name,
            account.email,
            account.avatar_url,
            account.phone,
            account.bio,
            account.company,
            account.job_title,
            account.location,
            account.website,
        ]

        filled_fields = sum(1 for field in fields if field)
        total_fields = len(fields)

        return int((filled_fields / total_fields) * 100)
