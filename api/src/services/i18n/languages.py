"""Which languages the platform's own screens are available in.

An account stores its choice in ``interface_language``. Older accounts hold
``en-US`` (the column default), newer ones a bare ``en`` or ``de``; both mean the
same thing here, so values are always compared by their language part.
"""

from __future__ import annotations

import re
from typing import Any

# Languages with a full translation. Add the code here and a messages file in
# the web app (web/messages) and mobile app to offer another one.
SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "de")
DEFAULT_LANGUAGE = "en"

_TAG = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8}){0,3}$")


def normalize_interface_language(value: Any) -> str | None:
    """The supported language for [value] ("de-AT" -> "de"), or None if there is none."""
    if not isinstance(value, str):
        return None
    tag = value.strip()
    if not tag or len(tag) > 20 or not _TAG.match(tag):
        return None
    language = re.split(r"[-_]", tag)[0].lower()
    return language if language in SUPPORTED_LANGUAGES else None


def language_from_accept_header(header: str | None) -> str | None:
    """The most preferred supported language in an Accept-Language header."""
    if not header:
        return None
    ranked: list[tuple[float, int, str]] = []
    for position, part in enumerate(header.split(",")[:20]):
        tag, _, params = part.partition(";")
        language = normalize_interface_language(tag)
        if language is None:
            continue
        quality = 1.0
        params = params.strip()
        if params.startswith("q="):
            try:
                quality = float(params[2:])
            except ValueError:
                continue
        if quality > 0:
            ranked.append((-quality, position, language))
    return min(ranked)[2] if ranked else None
