"""Inbound call provider registry."""

from src.services.voice.inbound.base_provider import BaseInboundCallProvider
from src.services.voice.inbound.vapi_provider import VapiProvider


def get_call_provider(provider: str) -> BaseInboundCallProvider:
    """Return the provider implementation for the given provider name."""
    if provider == "vapi":
        return VapiProvider()
    raise ValueError(f"Unsupported inbound call provider: {provider}")


__all__ = ["BaseInboundCallProvider", "VapiProvider", "get_call_provider"]
