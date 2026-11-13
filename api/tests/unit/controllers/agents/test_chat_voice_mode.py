"""Voice-mode flag on the agent chat stream request."""

import pytest

from src.controllers.agents.models import ChatRequest
from src.services.agents.chat_stream_service import VOICE_MODE_PROMPT


@pytest.mark.unit
def test_chat_request_voice_mode_defaults_off():
    request = ChatRequest(agent_slug="muse", message="hello")

    assert request.voice_mode is False


@pytest.mark.unit
def test_chat_request_accepts_voice_mode():
    request = ChatRequest(agent_slug="muse", message="hello", voice_mode=True)

    assert request.voice_mode is True


@pytest.mark.unit
def test_voice_prompt_asks_for_speakable_replies():
    lowered = VOICE_MODE_PROMPT.lower()

    assert "read aloud" in lowered
    assert "markdown" in lowered
