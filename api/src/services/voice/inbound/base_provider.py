"""
Base class for inbound call providers.

Each provider (Vapi, Retell, Twilio) implements this interface so the
webhook controller stays provider-agnostic.
"""

import hmac
from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession


class BaseInboundCallProvider(ABC):
    """Abstract base for inbound call webhook handlers."""

    @abstractmethod
    async def handle_webhook(
        self,
        payload: dict,
        headers: dict,
        db: AsyncSession,
    ) -> dict:
        """
        Handle an incoming webhook event from the provider.

        Returns a response dict that is sent back to the provider.
        """

    @abstractmethod
    def verify_signature(self, raw_body: bytes, headers: dict, secret: str) -> bool:
        """
        Verify webhook authenticity using the provider's signing mechanism.
        Must use constant-time comparison to prevent timing attacks.
        """

    @abstractmethod
    def get_webhook_url(self, base_url: str) -> str:
        """Return the full URL to register with this provider."""

    @staticmethod
    def _constant_time_compare(val1: str, val2: str) -> bool:
        """Constant-time string comparison to prevent timing attacks."""
        return hmac.compare_digest(val1.encode(), val2.encode())
