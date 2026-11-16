"""Widget config text per language, and the language field on widget chat."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.controllers.widgets import WidgetChatRequest, get_widget_config

THEME = {
    "chat_title": "Help",
    "chat_welcome_message": "Hello!",
    "chat_placeholder": "Ask a question",
    "privacy_policy_text": "Privacy",
    "translations": {
        "de": {
            "title": "Hilfe",
            "welcome_message": "Hallo!",
            "placeholder": "Stelle eine Frage",
            "agent_description": "Dein Assistent",
            "suggestion_prompts": [
                {"title": "Preise", "description": "Was kostet es?", "icon": "💶", "prompt": "Preise?"}
            ],
        },
        "de-AT": {"welcome_message": "Servus!"},
    },
}


async def _config(lang=None, accept_language=None, theme=THEME):
    widget = SimpleNamespace(id="w1", widget_name="Site", agent_id="a1", tenant_id="t1", theme_config=theme)
    agent = SimpleNamespace(
        agent_name="Muse",
        description="Your assistant",
        avatar="",
        tenant_id="t1",
        suggestion_prompts=[{"title": "Pricing", "description": "Cost?", "icon": "$", "prompt": "Pricing?"}],
    )
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=agent))
    headers = {"X-Widget-API-Key": "wk_test"}
    if accept_language:
        headers["Accept-Language"] = accept_language
    request = SimpleNamespace(headers=headers)
    with (
        patch("src.controllers.widgets.WidgetAuthMiddleware.validate_api_key", AsyncMock(return_value=widget)),
        patch("src.controllers.widgets.convert_s3_uri_to_presigned_url", lambda uri, _tenant: uri),
    ):
        return await get_widget_config(request, lang=lang, db=db)


@pytest.mark.unit
async def test_config_defaults_to_the_untranslated_text():
    body = await _config()

    assert body["language"] is None
    assert body["theme"]["title"] == "Help"
    assert body["theme"]["welcome_message"] == "Hello!"
    assert body["agent_description"] == "Your assistant"
    assert body["suggestion_prompts"][0]["title"] == "Pricing"


@pytest.mark.unit
async def test_config_returns_german_text_for_lang_param():
    body = await _config(lang="de")

    assert body["language"] == "de"
    assert body["theme"]["title"] == "Hilfe"
    assert body["theme"]["welcome_message"] == "Hallo!"
    assert body["theme"]["placeholder"] == "Stelle eine Frage"
    assert body["agent_description"] == "Dein Assistent"
    assert body["suggestion_prompts"][0]["title"] == "Preise"


@pytest.mark.unit
async def test_config_falls_back_to_default_for_untranslated_fields():
    body = await _config(lang="de")

    assert body["theme"]["privacy_policy_text"] == "Privacy"


@pytest.mark.unit
async def test_config_regional_variant_overrides_only_what_differs():
    body = await _config(lang="de-AT")

    assert body["theme"]["welcome_message"] == "Servus!"
    assert body["theme"]["title"] == "Hilfe"


@pytest.mark.unit
async def test_config_uses_accept_language_when_no_lang_param():
    body = await _config(accept_language="de-DE,de;q=0.9,en;q=0.8")

    assert body["language"] == "de-DE"
    assert body["theme"]["title"] == "Hilfe"


@pytest.mark.unit
async def test_config_lang_param_wins_over_accept_language():
    body = await _config(lang="en", accept_language="de")

    assert body["language"] == "en"
    assert body["theme"]["title"] == "Help"


@pytest.mark.unit
async def test_config_ignores_invalid_language_and_blank_translations():
    theme = {**THEME, "translations": {"de": {"title": "   ", "suggestion_prompts": []}}}

    invalid = await _config(lang="de; drop")
    blank = await _config(lang="de", theme=theme)

    assert invalid["language"] is None
    assert invalid["theme"]["title"] == "Help"
    assert blank["theme"]["title"] == "Help"
    assert blank["suggestion_prompts"][0]["title"] == "Pricing"


@pytest.mark.unit
async def test_config_sanitizes_translated_suggestion_prompts():
    theme = {
        "translations": {
            "de": {"suggestion_prompts": [{"title": "<script>alert(1)</script>Hi", "prompt": "x"}, "junk"]},
        }
    }

    body = await _config(lang="de", theme=theme)

    assert len(body["suggestion_prompts"]) == 1
    assert "<script>" not in body["suggestion_prompts"][0]["title"]


@pytest.mark.unit
def test_widget_chat_request_language_is_optional():
    assert WidgetChatRequest(message="hi").language is None
    assert WidgetChatRequest(message="hi", language="de").language == "de"


@pytest.mark.unit
def test_widget_chat_request_rejects_oversized_language():
    with pytest.raises(ValueError):
        WidgetChatRequest(message="hi", language="x" * 21)
