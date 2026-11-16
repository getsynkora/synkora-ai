"""Which interface language an account or request means."""

import pytest

from src.services.i18n import language_from_accept_header, normalize_interface_language


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("en", "en"),
        ("en-US", "en"),
        ("de", "de"),
        ("DE", "de"),
        ("de-AT", "de"),
        ("de_CH", "de"),
        (" de ", "de"),
    ],
)
def test_supported_languages_normalize_to_their_language(value, expected):
    assert normalize_interface_language(value) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [None, "", "  ", 3, "fr", "zh-Hans", "german", "de; x", "de\nx", "x" * 30, "../de", "d"],
)
def test_other_values_are_not_a_supported_language(value):
    assert normalize_interface_language(value) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("de-DE,de;q=0.9,en;q=0.8", "de"),
        ("fr,de;q=0.7,en;q=0.5", "de"),
        ("en;q=0.4, de;q=0.9", "de"),
        ("fr, es", None),
        ("*", None),
        ("", None),
        (None, None),
        ("de;q=0", None),
        ("de;q=abc,en", "en"),
    ],
)
def test_accept_language_picks_the_best_supported_language(header, expected):
    assert language_from_accept_header(header) == expected
