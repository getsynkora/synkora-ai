import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.agents.chat_stream_service import ChatStreamService, StreamState


@pytest.mark.asyncio
@pytest.mark.parametrize("saved", [True, False])
async def test_claude_completion_waits_for_successful_persistence(saved):
    operations = []

    async def persist(**kwargs):
        operations.append("save")
        assert kwargs["content"] == "answer"
        return SimpleNamespace(id=uuid4()) if saved else None

    async def provider(**kwargs):
        yield {"type": "text", "content": "answer"}
        yield {"type": "done", "metadata": {}}

    chat = MagicMock()
    chat.save_assistant_message = AsyncMock(side_effect=persist)
    chat.update_agent_stats = AsyncMock()
    sanitizer = MagicMock()
    sanitizer.sanitize.return_value = SimpleNamespace(sanitized_content="answer", detections=[])
    service = ChatStreamService(MagicMock(), chat, output_sanitizer=sanitizer)
    agent = SimpleNamespace(execute_stream=provider)
    db_agent = SimpleNamespace(agent_metadata={}, llm_config={}, system_prompt="test", id=uuid4(), agent_name="test")
    events = []
    with patch("src.services.agent_output_service.AgentOutputService") as output:
        output.return_value.send_outputs = AsyncMock()
        async for frame in service._stream_claude_code_agent(
            "test",
            "hello",
            "conversation",
            uuid4(),
            db_agent,
            agent,
            MagicMock(),
            StreamState(assistant_chunks=[], chart_data=[]),
        ):
            event = json.loads(frame.removeprefix("data:").strip())
            events.append(event["type"])
            if event["type"] == "done":
                assert operations == ["save"]
    assert ("done" in events) is saved
    assert ("error" in events) is not saved
    chat.save_assistant_message.assert_awaited_once()
