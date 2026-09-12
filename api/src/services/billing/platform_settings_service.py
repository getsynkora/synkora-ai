"""
Platform Settings Service - Manages platform-wide Stripe configuration
"""

import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.platform_settings import PlatformSettings
from src.services.agents.security import decrypt_value, encrypt_value

# Process-local cache for the singleton PlatformSettings row.
# Avoids a DB round-trip on every call to get_settings() (called by most
# billing/Stripe helper methods, often multiple times per request).
_settings_cache: dict[str, object] = {"data": None, "expires": 0.0}
_CACHE_TTL = 60  # seconds


def invalidate_platform_settings_cache() -> None:
    """Invalidate the process-local PlatformSettings cache.

    Call this from any write endpoint that mutates PlatformSettings so that
    subsequent reads within the same process pick up the change immediately.
    """
    _settings_cache["data"] = None
    _settings_cache["expires"] = 0.0


class PlatformSettingsService:
    """Service for managing platform settings"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_settings(self) -> PlatformSettings:
        """
        Get platform settings (singleton pattern)
        Creates default settings if none exist.

        Uses a process-local cache with a 60-second TTL to avoid hitting
        the database on every call.
        """
        now = time.monotonic()
        cached = _settings_cache["data"]
        if cached is not None and _settings_cache["expires"] > now:
            return cached  # type: ignore[return-value]

        result = await self.db.execute(select(PlatformSettings))
        settings = result.scalar_one_or_none()

        if not settings:
            # Create default settings
            settings = PlatformSettings()
            self.db.add(settings)
            await self.db.commit()
            await self.db.refresh(settings)

        _settings_cache["data"] = settings
        _settings_cache["expires"] = now + _CACHE_TTL

        return settings

    async def update_stripe_keys(
        self, secret_key: str | None = None, publishable_key: str | None = None, webhook_secret: str | None = None
    ) -> PlatformSettings:
        """
        Update Stripe API keys

        Args:
            secret_key: Stripe secret key (will be encrypted)
            publishable_key: Stripe publishable key (not encrypted)
            webhook_secret: Stripe webhook secret (will be encrypted)

        Returns:
            Updated platform settings
        """
        settings = await self.get_settings()

        if secret_key is not None:
            settings.stripe_secret_key = encrypt_value(secret_key)

        if publishable_key is not None:
            settings.stripe_publishable_key = publishable_key

        if webhook_secret is not None:
            settings.stripe_webhook_secret = encrypt_value(webhook_secret)

        await self.db.commit()
        await self.db.refresh(settings)
        invalidate_platform_settings_cache()

        return settings

    async def enable_stripe(self) -> PlatformSettings:
        """
        Enable Stripe integration

        Returns:
            Updated platform settings

        Raises:
            ValueError: If Stripe keys are not configured
        """
        settings = await self.get_settings()

        if not settings.stripe_secret_key or not settings.stripe_publishable_key:
            raise ValueError("Stripe keys must be configured before enabling")

        settings.stripe_enabled = "true"

        await self.db.commit()
        await self.db.refresh(settings)
        invalidate_platform_settings_cache()

        return settings

    async def disable_stripe(self) -> PlatformSettings:
        """
        Disable Stripe integration

        Returns:
            Updated platform settings
        """
        settings = await self.get_settings()
        settings.stripe_enabled = "false"

        await self.db.commit()
        await self.db.refresh(settings)
        invalidate_platform_settings_cache()

        return settings

    async def get_stripe_secret_key(self) -> str | None:
        """
        Get decrypted Stripe secret key

        Returns:
            Decrypted secret key or None if not set
        """
        settings = await self.get_settings()

        if not settings.stripe_secret_key:
            return None

        return decrypt_value(settings.stripe_secret_key)

    async def get_stripe_publishable_key(self) -> str | None:
        """
        Get Stripe publishable key

        Returns:
            Publishable key or None if not set
        """
        settings = await self.get_settings()
        return settings.stripe_publishable_key

    async def get_stripe_webhook_secret(self) -> str | None:
        """
        Get decrypted Stripe webhook secret

        Returns:
            Decrypted webhook secret or None if not set
        """
        settings = await self.get_settings()

        if not settings.stripe_webhook_secret:
            return None

        return decrypt_value(settings.stripe_webhook_secret)

    async def is_stripe_configured(self) -> bool:
        """
        Check if Stripe is properly configured

        Returns:
            True if all required Stripe keys are set
        """
        settings = await self.get_settings()
        return bool(settings.stripe_secret_key and settings.stripe_publishable_key and settings.stripe_webhook_secret)

    async def is_stripe_enabled(self) -> bool:
        """
        Check if Stripe integration is enabled

        Returns:
            True if Stripe is enabled and configured
        """
        settings = await self.get_settings()
        return settings.stripe_enabled == "true" and await self.is_stripe_configured()

    async def clear_stripe_keys(self) -> PlatformSettings:
        """
        Clear all Stripe keys (useful for testing or reconfiguration)

        Returns:
            Updated platform settings
        """
        settings = await self.get_settings()

        settings.stripe_secret_key = None
        settings.stripe_publishable_key = None
        settings.stripe_webhook_secret = None
        settings.stripe_enabled = "false"

        await self.db.commit()
        await self.db.refresh(settings)
        invalidate_platform_settings_cache()

        return settings

    async def test_stripe_connection(self) -> dict:
        """
        Test Stripe connection with current keys

        Returns:
            Dictionary with connection test results

        Raises:
            ValueError: If Stripe is not configured
        """
        if not await self.is_stripe_configured():
            raise ValueError("Stripe is not configured")

        try:
            import asyncio

            import stripe

            secret_key = await self.get_stripe_secret_key()
            stripe.api_key = secret_key

            # Test the connection by retrieving account info
            # Note: stripe.Account.retrieve() without ID retrieves the platform account itself
            account = await asyncio.to_thread(stripe.Account.retrieve)

            return {
                "success": True,
                "account_id": account.id,
                "account_name": account.business_profile.name if account.business_profile else None,
                "country": account.country,
                "currency": account.default_currency,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
