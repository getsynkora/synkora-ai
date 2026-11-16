"""Short backend texts shown to end users."""

import pytest

from src.services.i18n import translate
from src.services.i18n.messages import _MESSAGES


@pytest.mark.unit
@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("de", "Ihre Antwort ist fertig."),
        ("de-AT", "Ihre Antwort ist fertig."),
        ("en", "Your answer is ready."),
        (None, "Your answer is ready."),
        ("fr", "Your answer is ready."),
        ("de; x", "Your answer is ready."),
    ],
)
def test_translate_falls_back_to_english(language, expected):
    assert translate("answer_ready", language) == expected


@pytest.mark.unit
def test_every_text_has_every_supported_language():
    from src.services.i18n import SUPPORTED_LANGUAGES

    for key, texts in _MESSAGES.items():
        assert set(texts) == set(SUPPORTED_LANGUAGES), key
