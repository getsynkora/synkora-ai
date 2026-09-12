import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai.types.chat import ChatCompletionChunk

from src.services.agents.function_calling import FunctionCallingHandler


def handler(provider):
    client = MagicMock(provider=provider)
    client.config.model_name = "test-model"
    client.config.api_base = None
    client._build_openai_params.return_value = {}
    traces = MagicMock()
    traces.should_trace.return_value = False
    return FunctionCallingHandler(client, tools=[], langfuse_service=traces)


@pytest.mark.asyncio
async def test_native_openai_stream_preserves_usage_and_delivers_early():
    run = handler("openai")
    release = asyncio.Event()

    async def chunks():
        yield ChatCompletionChunk(
            id="one",
            created=0,
            model="test-model",
            object="chat.completion.chunk",
            choices=[{"index": 0, "delta": {"content": "hello"}, "finish_reason": None}],
        )
        await release.wait()
        yield ChatCompletionChunk(
            id="one",
            created=0,
            model="test-model",
            object="chat.completion.chunk",
            choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}],
            usage={"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9},
        )

    run.llm_client._client.chat.completions.create = AsyncMock(return_value=chunks())
    events = run._generate_model_events([], 0, 20)
    assert await asyncio.wait_for(anext(events), 1) == ("text", "hello")
    release.set()
    kind, response = await anext(events)
    assert kind == "response"
    assert response.choices[0].message.content == "hello"
    assert response.usage.total_tokens == 9
    await events.aclose()


@pytest.mark.asyncio
async def test_openai_tool_arguments_are_assembled_before_dispatch():
    async def chunks():
        for delta, finish in [
            (
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call-one",
                            "type": "function",
                            "function": {"name": "lookup", "arguments": '{"id":'},
                        }
                    ]
                },
                None,
            ),
            ({"tool_calls": [{"index": 0, "function": {"arguments": "1}"}}]}, "tool_calls"),
        ]:
            yield ChatCompletionChunk(
                id="one",
                created=0,
                model="test-model",
                object="chat.completion.chunk",
                choices=[{"index": 0, "delta": delta, "finish_reason": finish}],
            )

    on_text = AsyncMock()
    response = await FunctionCallingHandler._collect_openai_stream(chunks(), [], on_text)
    calls = handler("openai")._extract_function_calls(response)
    assert calls[0]["name"] == "lookup"
    assert calls[0]["arguments"] == {"id": 1}
    assert calls[0]["id"] == "call-one"
    on_text.assert_not_called()


@pytest.mark.asyncio
async def test_anthropic_stream_delivers_early_and_keeps_final_message():
    run = handler("anthropic")
    release = asyncio.Event()
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="hello")], usage={"input_tokens": 7})

    async def text():
        yield "hello"
        await release.wait()

    @asynccontextmanager
    async def stream(**_kwargs):
        yield SimpleNamespace(text_stream=text(), get_final_message=AsyncMock(return_value=response))

    run.llm_client._client.messages.stream = stream
    events = run._generate_model_events([], 0, 20)
    assert await asyncio.wait_for(anext(events), 1) == ("text", "hello")
    release.set()
    assert await anext(events) == ("response", response)
    await events.aclose()


def test_incomplete_arguments_are_not_repaired_into_an_action():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=[
                        SimpleNamespace(id="call", function=SimpleNamespace(name="write", arguments='{"amount":1'))
                    ]
                )
            )
        ]
    )
    with pytest.raises(ValueError, match="incomplete or malformed"):
        handler("openai")._extract_function_calls(response)


@pytest.mark.asyncio
async def test_google_stream_preserves_tool_signature_and_usage():
    from google.genai import types

    run = handler("google")
    signature = b"signature"

    async def chunks():
        yield types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    index=0,
                    content=types.Content(
                        parts=[types.Part(text="private thought", thought=True), types.Part(text="hello")]
                    ),
                )
            ]
        )
        yield types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    index=0,
                    content=types.Content(
                        parts=[
                            types.Part(
                                function_call=types.FunctionCall(name="lookup", args={"id": 1}),
                                thought_signature=signature,
                            )
                        ]
                    ),
                )
            ],
            usage_metadata=types.GenerateContentResponseUsageMetadata(total_token_count=9),
        )

    run.llm_client._client.aio.models.generate_content_stream = AsyncMock(return_value=chunks())
    events = run._generate_model_events([], 0, 20)
    assert await anext(events) == ("text", "hello")
    _, response = await anext(events)
    assert response.usage_metadata.total_token_count == 9
    assert response.candidates[0].content.parts[-1].thought_signature == signature
    assert run._extract_function_calls(response)[0]["name"] == "lookup"
    await events.aclose()
