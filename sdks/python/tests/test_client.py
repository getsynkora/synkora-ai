"""Tests for SynkoraClient and AsyncSynkoraClient using respx mocks."""

import json

import httpx
import pytest
import respx

from synkora import AsyncSynkoraClient, SynkoraClient
from synkora.exceptions import AgentNotFoundError, AuthError, RateLimitError, StreamError
from synkora.models import AgentInfo, ChatResponse, ChunkEvent, DoneEvent

_BASE = "https://app.synkora.com"
_KEY = "sk-test-key"


def _sse(*events: dict) -> bytes:
    lines = "".join(f"data: {json.dumps(e)}\n\n" for e in events)
    return lines.encode()


# ---------------------------------------------------------------------------
# Sync client
# ---------------------------------------------------------------------------


class TestSynkoraClientInit:
    def test_requires_api_key(self):
        with pytest.raises(AuthError):
            SynkoraClient()

    def test_accepts_api_key_param(self):
        client = SynkoraClient(api_key=_KEY)
        client.close()

    def test_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("SYNKORA_API_KEY", _KEY)
        client = SynkoraClient()
        client.close()

    def test_context_manager(self):
        with SynkoraClient(api_key=_KEY):
            pass


@respx.mock
class TestSynkoraClientListAgents:
    def test_returns_agent_list(self):
        respx.get(f"{_BASE}/api/v1/public/agents").mock(
            return_value=httpx.Response(
                200,
                json=[{"id": "a1", "name": "Agent One", "capabilities": ["chat"]}],
            )
        )
        with SynkoraClient(api_key=_KEY) as client:
            agents = client.list_agents()
        assert len(agents) == 1
        assert isinstance(agents[0], AgentInfo)
        assert agents[0].name == "Agent One"

    def test_raises_auth_error_on_401(self):
        respx.get(f"{_BASE}/api/v1/public/agents").mock(
            return_value=httpx.Response(401, json={"detail": "Unauthorized"})
        )
        with pytest.raises(AuthError):
            with SynkoraClient(api_key=_KEY) as client:
                client.list_agents()

    def test_raises_rate_limit_on_429(self):
        respx.get(f"{_BASE}/api/v1/public/agents").mock(
            return_value=httpx.Response(429, json={"detail": "Too many requests"})
        )
        with pytest.raises(RateLimitError):
            with SynkoraClient(api_key=_KEY) as client:
                client.list_agents()


@respx.mock
class TestSynkoraClientGetAgent:
    def test_returns_agent(self):
        respx.get(f"{_BASE}/api/v1/public/agents/agent-uuid").mock(
            return_value=httpx.Response(
                200,
                json={"id": "agent-uuid", "name": "My Agent", "model": "gpt-4o", "capabilities": []},
            )
        )
        with SynkoraClient(api_key=_KEY) as client:
            agent = client.get_agent("agent-uuid")
        assert agent.id == "agent-uuid"
        assert agent.model == "gpt-4o"

    def test_raises_not_found_on_404(self):
        respx.get(f"{_BASE}/api/v1/public/agents/missing").mock(
            return_value=httpx.Response(404, json={"detail": "Not found"})
        )
        with pytest.raises(AgentNotFoundError):
            with SynkoraClient(api_key=_KEY) as client:
                client.get_agent("missing")


@respx.mock
class TestSynkoraClientChat:
    def test_chat_aggregates_chunks(self):
        body = _sse(
            {"type": "start", "agent": "bot", "start_time": 0.0},
            {"type": "chunk", "content": "Hello"},
            {"type": "chunk", "content": " world"},
            {"type": "done", "metadata": {"total_tokens": 10}, "sources": []},
        )
        respx.post(f"{_BASE}/api/v1/public/agents/agent-1/chat/stream").mock(
            return_value=httpx.Response(200, content=body)
        )
        with SynkoraClient(api_key=_KEY) as client:
            response = client.chat(agent_id="agent-1", message="Hi")
        assert isinstance(response, ChatResponse)
        assert response.message == "Hello world"
        assert response.tokens_used == 10

    def test_chat_stream_passes_conversation_id(self):
        body = _sse({"type": "done", "metadata": {}, "sources": []})
        route = respx.post(f"{_BASE}/api/v1/public/agents/agent-1/chat/stream").mock(
            return_value=httpx.Response(200, content=body)
        )
        with SynkoraClient(api_key=_KEY) as client:
            client.chat(agent_id="agent-1", message="Hi", conversation_id="conv-99")
        sent = json.loads(route.calls[0].request.content)
        assert sent["conversation_id"] == "conv-99"

    def test_chat_stream_yields_typed_events(self):
        body = _sse(
            {"type": "chunk", "content": "A"},
            {"type": "chunk", "content": "B"},
            {"type": "done", "metadata": {}, "sources": []},
        )
        respx.post(f"{_BASE}/api/v1/public/agents/agent-1/chat/stream").mock(
            return_value=httpx.Response(200, content=body)
        )
        events = []
        with SynkoraClient(api_key=_KEY) as client:
            for ev in client.chat_stream(agent_id="agent-1", message="Hello"):
                events.append(ev)
        chunks = [e for e in events if isinstance(e, ChunkEvent)]
        assert len(chunks) == 2
        assert chunks[0].content == "A"
        assert chunks[1].content == "B"
        assert isinstance(events[-1], DoneEvent)

    def test_chat_stream_raises_stream_error(self):
        body = _sse({"type": "error", "error": "Policy violation", "error_type": "policy"})
        respx.post(f"{_BASE}/api/v1/public/agents/agent-1/chat/stream").mock(
            return_value=httpx.Response(200, content=body)
        )
        with pytest.raises(StreamError) as exc_info:
            with SynkoraClient(api_key=_KEY) as client:
                list(client.chat_stream(agent_id="agent-1", message="Bad input"))
        assert exc_info.value.error_type == "policy"


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------


@respx.mock
class TestAsyncSynkoraClientChat:
    @pytest.mark.asyncio
    async def test_chat_aggregates_chunks(self):
        body = _sse(
            {"type": "chunk", "content": "Hi"},
            {"type": "done", "metadata": {"total_tokens": 5}, "sources": []},
        )
        respx.post(f"{_BASE}/api/v1/public/agents/agent-1/chat/stream").mock(
            return_value=httpx.Response(200, content=body)
        )
        async with AsyncSynkoraClient(api_key=_KEY) as client:
            response = await client.chat(agent_id="agent-1", message="Hello")
        assert response.message == "Hi"
        assert response.tokens_used == 5

    @pytest.mark.asyncio
    async def test_chat_stream_yields_events(self):
        body = _sse(
            {"type": "chunk", "content": "Hello"},
            {"type": "done", "metadata": {}, "sources": []},
        )
        respx.post(f"{_BASE}/api/v1/public/agents/agent-1/chat/stream").mock(
            return_value=httpx.Response(200, content=body)
        )
        events = []
        async with AsyncSynkoraClient(api_key=_KEY) as client:
            async for ev in client.chat_stream(agent_id="agent-1", message="Hello"):
                events.append(ev)
        assert isinstance(events[0], ChunkEvent)
        assert events[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_requires_api_key(self):
        with pytest.raises(AuthError):
            AsyncSynkoraClient()

    @pytest.mark.asyncio
    async def test_raises_not_found_on_404(self):
        respx.get(f"{_BASE}/api/v1/public/agents/missing").mock(
            return_value=httpx.Response(404)
        )
        async with AsyncSynkoraClient(api_key=_KEY) as client:
            with pytest.raises(AgentNotFoundError):
                await client.get_agent("missing")
