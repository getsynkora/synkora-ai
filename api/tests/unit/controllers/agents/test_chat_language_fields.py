"""The language field on every client-facing chat request."""

import inspect

import pytest

from src.controllers.agents.chat import _ws_chat_pipeline
from src.controllers.agents.models import ChatRequest
from src.schemas.agent_api import ChatRequest as PublicChatRequest


@pytest.mark.unit
def test_app_chat_request_language_is_optional():
    assert ChatRequest(agent_slug="muse", message="hi").language is None
    assert ChatRequest(agent_slug="muse", message="hi", language="de").language == "de"


@pytest.mark.unit
def test_app_chat_request_rejects_an_oversized_language():
    with pytest.raises(ValueError):
        ChatRequest(agent_slug="muse", message="hi", language="x" * 21)


@pytest.mark.unit
def test_public_api_chat_request_language_is_optional():
    assert PublicChatRequest(message="hi").language is None
    assert PublicChatRequest(message="hi", language="de").language == "de"


@pytest.mark.unit
def test_public_api_chat_request_rejects_an_oversized_language():
    with pytest.raises(ValueError):
        PublicChatRequest(message="hi", language="x" * 21)


@pytest.mark.unit
def test_websocket_pipeline_accepts_a_language():
    parameter = inspect.signature(_ws_chat_pipeline).parameters["language"]

    assert parameter.default is None
