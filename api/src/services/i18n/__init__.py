"""Interface language for people using the platform (dashboard, mobile app, emails)."""

from src.services.i18n.languages import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    language_from_accept_header,
    normalize_interface_language,
)
from src.services.i18n.messages import translate

__all__ = [
    "DEFAULT_LANGUAGE",
    "SUPPORTED_LANGUAGES",
    "language_from_accept_header",
    "normalize_interface_language",
    "translate",
]
