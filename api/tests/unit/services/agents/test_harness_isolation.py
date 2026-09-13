import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.agents.adk_tools import ADKToolRegistry
from src.services.agents.function_calling import FunctionCallingHandler
from src.services.agents.runtime_context import RuntimeContext
from src.services.mcp.mcp_client import MCPClient, MCPToolExecutionError


def registry():
    value = object.__new__(ADKToolRegistry)
    value.tools = {}
    return value


@pytest.mark.asyncio
async def test_interleaved_tenants_execute_only_their_own_bindings():
    base = registry()
    ready = asyncio.Event()
    release = asyncio.Event()

    async def run_a():
        local = base.fork()
        local.register_tool("lookup", "", {}, AsyncMock(return_value="tenant A"))
        context = RuntimeContext(uuid4(), uuid4(), None, tool_registry=local)
        ready.set()
        await release.wait()
        return await local.execute_tool("lookup", {}, runtime_context=context)

    task = asyncio.create_task(run_a())
    await ready.wait()
    other = base.fork()
    other.register_tool("lookup", "", {}, AsyncMock(return_value="tenant B"))
    assert await other.execute_tool("lookup", {}) == "tenant B"
    release.set()
    assert await task == "tenant A"
    assert base.get_tool("lookup") is None


@pytest.mark.asyncio
async def test_provider_delta_arrives_before_completion():
    client = MagicMock(provider="litellm")
    handler = FunctionCallingHandler(client, tools=[], langfuse_service=MagicMock())
    release = asyncio.Event()
    response = SimpleNamespace(choices=[])

    async def generate(*_args):
        await handler._on_answer_delta("first")
        await release.wait()
        return response

    handler._generate_with_tools = generate
    events = handler._generate_model_events([], 0, 20)
    assert await asyncio.wait_for(anext(events), 1) == ("text", "first")
    release.set()
    assert await anext(events) == ("response", response)
    await events.aclose()


@pytest.mark.asyncio
async def test_closing_stream_cancels_upstream():
    handler = FunctionCallingHandler(MagicMock(provider="litellm"), tools=[], langfuse_service=MagicMock())
    stopped = asyncio.Event()

    async def generate(*_args):
        try:
            await handler._on_answer_delta("first")
            await asyncio.Event().wait()
        finally:
            stopped.set()

    handler._generate_with_tools = generate
    events = handler._generate_model_events([], 0, 20)
    await anext(events)
    await events.aclose()
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_mcp_lost_response_does_not_repeat_remote_write():
    client = MCPClient([])
    client._client = MagicMock()
    client._client.call_tool = AsyncMock(side_effect=ConnectionError("response lost after commit"))
    with pytest.raises(MCPToolExecutionError):
        await client.execute_tool("create_ticket", {})
    assert client._client.call_tool.await_count == 1


@pytest.mark.asyncio
async def test_unknown_tool_is_not_retried_by_handler():
    local = registry()
    write = AsyncMock(side_effect=ConnectionError("response lost"))
    local.register_tool("create_ticket", "", {}, write)
    context = RuntimeContext(uuid4(), uuid4(), None, tool_registry=local)
    handler = FunctionCallingHandler(
        MagicMock(provider="openai"),
        tools=["create_ticket"],
        runtime_context=context,
        langfuse_service=MagicMock(),
    )
    result = await handler._execute_single_tool_with_retry("create_ticket", {}, should_trace=False)
    assert not result.success
    assert write.await_count == 1


@pytest.mark.asyncio
async def test_actual_litellm_collector_forwards_text_and_closes():
    release = asyncio.Event()
    first = asyncio.Event()
    closed = asyncio.Event()
    chunks = [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))])]

    async def stream():
        try:
            yield chunks[0]
            await release.wait()
        finally:
            closed.set()

    async def on_text(text):
        assert text == "hello"
        first.set()

    fake = SimpleNamespace(acompletion=AsyncMock(return_value=stream()), stream_chunk_builder=lambda **kw: kw["chunks"])
    with patch.dict("sys.modules", {"litellm": fake}):
        task = asyncio.create_task(FunctionCallingHandler._litellm_stream_and_collect({}, on_text))
        await asyncio.wait_for(first.wait(), 1)
        assert not task.done()
        release.set()
        assert await task == chunks
    assert closed.is_set()


@pytest.mark.asyncio
async def test_user_token_failure_never_calls_shared_connection():
    local = registry()
    static_client = SimpleNamespace(config_revision="rev1", execute_tool=AsyncMock())
    manager = SimpleNamespace(
        get_agent_client=AsyncMock(return_value=static_client),
        get_agent_client_with_user_token=AsyncMock(return_value=None),
    )
    cache = SimpleNamespace(
        get_mcp_tools=AsyncMock(
            return_value=[
                {
                    "server_name": "server",
                    "tool_name": "lookup",
                    "sanitized_tool_name": "lookup",
                    "description": "lookup",
                    "input_schema": {},
                }
            ]
        )
    )

    @asynccontextmanager
    async def session():
        yield AsyncMock()

    with (
        patch("src.services.mcp.mcp_client_manager", manager),
        patch("src.services.cache.get_agent_cache", return_value=cache),
        patch("src.core.database.get_async_session_factory", return_value=session),
    ):
        await local.load_agent_mcp_tools(str(uuid4()), AsyncMock(), {"mcp_user_token": "user-token"})
        result = await local.execute_tool("lookup", {})
    assert result["success"] is False
    static_client.execute_tool.assert_not_called()


@pytest.mark.asyncio
async def test_run_deadline_cancels_stalled_model():
    from src.services.agents.config import AgenticConfig

    handler = FunctionCallingHandler(
        MagicMock(provider="openai"),
        tools=["lookup"],
        langfuse_service=MagicMock(),
        agentic_config=AgenticConfig(run_timeout_seconds=0.02),
    )
    handler.available_tools = [{"name": "lookup", "description": "", "parameters": {}}]
    cancelled = asyncio.Event()

    async def stuck(*_args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    handler._generate_with_tools = stuck
    with pytest.raises(TimeoutError):
        async for _ in handler.generate_with_functions_stream("hello"):
            pass
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_read_fanout_is_bounded_and_keeps_result_order():
    from src.services.agents.config import AgenticConfig
    from src.services.agents.function_calling import ToolExecutionResult

    local = registry()
    local.register_tool("read", "", {}, AsyncMock(), tool_category="read")
    context = RuntimeContext(uuid4(), uuid4(), None, tool_registry=local)
    handler = FunctionCallingHandler(
        MagicMock(provider="openai"),
        tools=["read"],
        runtime_context=context,
        langfuse_service=MagicMock(),
        agentic_config=AgenticConfig(max_parallel_tools=2),
    )
    active = 0
    peak = 0

    async def read(_name, args, _trace):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return ToolExecutionResult("read", args["index"], True)

    handler._execute_single_tool_with_retry = read
    results = await handler._execute_functions([{"name": "read", "arguments": {"index": i}} for i in range(8)])
    assert peak == 2
    assert [result.result for result in results] == list(range(8))
