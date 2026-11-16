"""Short texts the backend itself shows to end users (push notifications and the like).

Anything longer, and everything on screen, belongs to the client apps. Add a text
here as ``{"key": {"en": "...", "de": "..."}}``; a language without one falls back
to English.
"""

from __future__ import annotations

from src.services.i18n.languages import DEFAULT_LANGUAGE, normalize_interface_language

_MESSAGES: dict[str, dict[str, str]] = {
    "answer_ready": {
        "en": "Your answer is ready.",
        "de": "Ihre Antwort ist fertig.",
    },
}


def translate(key: str, language: str | None) -> str:
    """The text for [key] in [language] ("de", "de-AT"), English if there is none."""
    texts = _MESSAGES[key]
    return texts.get(normalize_interface_language(language) or DEFAULT_LANGUAGE, texts[DEFAULT_LANGUAGE])
