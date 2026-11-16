"""Language selection for chat clients (widgets, mobile).

A client can say which language its UI is in. That does two things:

* the agent is told, through its system prompt, to answer in that language;
* the widget config endpoint returns the widget text written for it.

The code comes straight from an untrusted request and ends up inside a system
prompt, so it is validated strictly and never echoed back as free text.
"""

from __future__ import annotations

import re
from typing import Any

# BCP-47 shaped: language[-script/region/variant...], e.g. "de", "de-AT", "zh-Hans-CN".
_LANGUAGE_CODE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}$")
_MAX_LANGUAGE_CODE_LENGTH = 20

# English names for common languages, used so the model gets "German", not "de".
LANGUAGE_NAMES: dict[str, str] = {
    "ar": "Arabic",
    "bn": "Bengali",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ms": "Malay",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sv": "Swedish",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "zh": "Chinese",
}

# Widget text that can be translated per language, and how each one is shaped.
TRANSLATABLE_THEME_FIELDS = ("title", "welcome_message", "placeholder", "privacy_policy_text")


def normalize_language(value: Any) -> str | None:
    """Return a clean BCP-47 style code ("de", "pt-BR"), or None if it is not one."""
    if not isinstance(value, str):
        return None
    code = value.strip().replace("_", "-")
    if not code or len(code) > _MAX_LANGUAGE_CODE_LENGTH or not _LANGUAGE_CODE.match(code):
        return None
    primary, *rest = code.split("-")
    return "-".join([primary.lower(), *rest])


def language_from_accept_header(header: str | None) -> str | None:
    """Pick the most preferred valid language from an Accept-Language header."""
    if not header:
        return None
    ranked: list[tuple[float, int, str]] = []
    for position, part in enumerate(header.split(",")[:10]):
        tag, _, params = part.partition(";")
        code = normalize_language(tag)
        if code is None:
            continue
        quality = 1.0
        params = params.strip()
        if params.startswith("q="):
            try:
                quality = float(params[2:])
            except ValueError:
                continue
        if quality > 0:
            ranked.append((-quality, position, code))
    return min(ranked)[2] if ranked else None


def language_instruction(value: Any) -> str | None:
    """System prompt text that makes the agent answer in the client's language."""
    code = normalize_language(value)
    if code is None:
        return None
    name = LANGUAGE_NAMES.get(code.split("-")[0])
    label = f"{name} ({code})" if name else code
    return (
        "# Response Language\n"
        f"The user's app is set to {label}. Reply in that language by default, including greetings "
        "and clarifying questions. Keep code, tool names, URLs and identifiers unchanged. "
        "If the user clearly writes to you in a different language, reply in the language they use."
    )


def translations_for(theme: dict[str, Any], language: str | None) -> dict[str, Any]:
    """The widget's saved text for [language]: the exact variant first, then its base language.

    Translations live in the widget's ``theme_config["translations"]`` as
    ``{"de": {"title": "...", "suggestion_prompts": [...]}, "de-AT": {...}}``.
    """
    code = normalize_language(language)
    table = theme.get("translations")
    if code is None or not isinstance(table, dict):
        return {}
    lowered = {str(key).lower(): value for key, value in table.items() if isinstance(value, dict)}
    merged: dict[str, Any] = {}
    # Base language first so a regional variant only has to override what differs.
    for candidate in dict.fromkeys([code.split("-")[0], code.lower()]):
        merged.update(lowered.get(candidate.lower(), {}))
    return merged
