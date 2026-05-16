from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.agents.function_calling import FunctionCallingHandler, _compact_schema


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.provider = "OPENAI"
    client.config.model_name = "gpt-4"
    client.config.api_key = "test-key"
    client.config.api_base = None
    # Mock inner client
    client._client = MagicMock()
    client._client.chat.completions.create = AsyncMock()
    return client


@pytest.fixture
def mock_tool_registry():
    mock = MagicMock()
    mock.list_tools.return_value = [
        {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {"type": "object", "properties": {"arg": {"type": "string"}}},
        },
        {"name": "other_tool", "description": "Another tool", "parameters": {}},
    ]
    mock.execute_tool = AsyncMock()

    fake_adk_tools = SimpleNamespace(tool_registry=mock)
    with patch.dict("sys.modules", {"src.services.agents.adk_tools": fake_adk_tools}):
        yield mock


@pytest.fixture
def mock_langfuse():
    with patch("src.services.agents.function_calling.LangfuseService") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.should_trace.return_value = False
        mock_cls.for_agent.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def handler(mock_llm_client, mock_tool_registry, mock_langfuse):
    return FunctionCallingHandler(llm_client=mock_llm_client, tools=["test_tool"])


class TestFunctionCallingHandler:
    def test_init(self, handler):
        assert len(handler.available_tools) == 1
        assert handler.available_tools[0]["name"] == "test_tool"
        assert handler.provider == "openai"  # Provider is normalized to lowercase

    def test_convert_to_openai_format(self, handler):
        tools = handler._convert_to_openai_format()
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "test_tool"

    def test_convert_to_anthropic_format(self, handler):
        handler.provider = "anthropic"
        tools = handler._convert_to_anthropic_format()
        assert len(tools) == 1
        assert tools[0]["name"] == "test_tool"
        assert "input_schema" in tools[0]

    def test_convert_to_google_format(self, handler):
        handler.provider = "google"
        # Import google.genai.types and patch at the source where it's used
        from google.genai import types

        with patch.object(types, "FunctionDeclaration") as MockFuncDecl, patch.object(types, "Tool") as MockTool:
            tools = handler._convert_to_google_format()
            assert len(tools) == 1
            MockFuncDecl.assert_called()
            MockTool.assert_called()

    @pytest.mark.asyncio
    async def test_generate_with_functions_no_tools(self, mock_llm_client, mock_tool_registry):
        # Initialize handler with NO tools found
        mock_tool_registry.list_tools.return_value = []
        handler = FunctionCallingHandler(mock_llm_client)

        mock_llm_client.generate_content = AsyncMock(return_value="Response without tools")

        result = await handler.generate_with_functions("Hello")

        assert result == "Response without tools"
        mock_llm_client.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_functions_simple_response(self, handler, mock_llm_client):
        # Mock LLM response with no function calls
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].message.content = "Simple response"

        mock_llm_client._client.chat.completions.create.return_value = mock_response

        result = await handler.generate_with_functions("Hello")

        assert result == "Simple response"
        mock_llm_client._client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_functions_execution_loop(self, handler, mock_llm_client, mock_tool_registry):
        # 1st call: Returns tool call
        response1 = MagicMock()
        tool_call = MagicMock()
        tool_call.function.name = "test_tool"
        tool_call.function.arguments = '{"arg": "value"}'
        response1.choices = [MagicMock()]
        response1.choices[0].message.tool_calls = [tool_call]
        response1.choices[0].message.content = None

        # 2nd call: Returns final answer
        response2 = MagicMock()
        response2.choices = [MagicMock()]
        response2.choices[0].message.tool_calls = None
        response2.choices[0].message.content = "Final answer"

        mock_llm_client._client.chat.completions.create.side_effect = [response1, response2]

        mock_tool_registry.execute_tool.return_value = {"status": "ok"}

        result = await handler.generate_with_functions("Use tool")

        assert result == "Final answer"
        assert mock_llm_client._client.chat.completions.create.call_count == 2
        mock_tool_registry.execute_tool.assert_called_once_with("test_tool", {"arg": "value"}, config={})

    @pytest.mark.asyncio
    async def test_execute_functions_error(self, handler, mock_tool_registry):
        mock_tool_registry.execute_tool.side_effect = ValueError("Execution failed")

        function_calls = [{"name": "test_tool", "arguments": {}}]
        results = await handler._execute_functions(function_calls)

        assert len(results) == 1
        assert results[0].name == "test_tool"
        assert results[0].success is False
        assert results[0].error == "Execution failed"

    @pytest.mark.asyncio
    async def test_execute_functions_with_runtime_context(self, handler, mock_tool_registry):
        class RuntimeContextStub:
            tenant_id = uuid4()
            agent_id = uuid4()
            conversation_id = uuid4()
            event_sequence = 0

            @asynccontextmanager
            async def scoped_db_context(self):
                yield self

        mock_context = RuntimeContextStub()
        handler.runtime_context = mock_context

        function_calls = [{"name": "test_tool", "arguments": {"arg": "val"}}]
        mock_tool_registry.execute_tool.return_value = "Success"

        fake_trace_service = SimpleNamespace(fire_tool_call=MagicMock())
        with patch.dict("sys.modules", {"src.services.agents.agent_trace_service": fake_trace_service}):
            await handler._execute_functions(function_calls)

        # Should call with runtime_context instead of config
        mock_tool_registry.execute_tool.assert_called_with("test_tool", {"arg": "val"}, runtime_context=mock_context)
        fake_trace_service.fire_tool_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_functions_stream(self, handler, mock_llm_client, mock_tool_registry):
        # Mock generator for final response
        async def mock_generator(*args, **kwargs):
            yield "Final"
            yield " "
            yield "Answer"

        mock_llm_client.generate_content_stream_with_messages = mock_generator

        # Mock generate_with_tools (non-streaming internally for logic)
        with patch.object(handler, "_generate_with_tools", new_callable=AsyncMock) as mock_gen_tools:
            # 1st iteration: tool call
            response1 = MagicMock()
            tool_call = MagicMock()
            tool_call.function.name = "test_tool"
            tool_call.function.arguments = "{}"
            response1.choices = [MagicMock()]
            response1.choices[0].message.tool_calls = [tool_call]

            # 2nd iteration: no tool calls (final text response)
            response2 = MagicMock()
            response2.choices = [MagicMock()]
            response2.choices[0].message.tool_calls = None
            response2.choices[0].message.content = "Final"

            mock_gen_tools.side_effect = [response1, response2]

            mock_tool_registry.execute_tool.return_value = "Success"

            chunks = []
            async for chunk in handler.generate_with_functions_stream("Use tool"):
                chunks.append(chunk)

            # Verify stream events
            # 1. Function call event
            assert any(c["type"] == "function_call" and c["name"] == "test_tool" for c in chunks)
            # 2. Function result event
            assert any(c["type"] == "function_result" and c["result"] == "Success" for c in chunks)
            # 3. Text content (final answer)
            assert any(c["type"] == "text" and c["content"] == "Final" for c in chunks)

    def test_extract_text_response(self, handler):
        # OpenAI style
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Text"
        assert handler._extract_text_response(response) == "Text"

        # Anthropic style
        handler.provider = "anthropic"
        response = MagicMock()
        block = MagicMock()
        block.text = "Text"
        response.content = [block]
        assert handler._extract_text_response(response) == "Text"

        # Google style
        handler.provider = "google"
        response = MagicMock()
        response.text = "Text"
        assert handler._extract_text_response(response) == "Text"

    def test_convert_history_to_openai_format(self, handler):
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi", "tool_calls": []},  # Regular assistant msg
            {"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]},  # Tool call msg
            {"role": "tool", "tool_call_id": "1", "content": "Result"},
        ]

        converted = handler._convert_history_to_openai_format(history)
        assert len(converted) == 4
        assert converted[0]["role"] == "user"
        assert converted[2]["tool_calls"] == [{"id": "1"}]
        assert converted[3]["role"] == "tool"

    def test_extract_function_calls_google(self, handler):
        handler.provider = "google"
        response = MagicMock()
        part = MagicMock()
        part.function_call.name = "test_tool"
        part.function_call.args = {"arg": "val"}

        # Correct mocking for Google response structure
        # response.candidates[0].content.parts[0]
        candidate = MagicMock()
        candidate.content.parts = [part]
        # Attach attribute 'function_call' to part to make hasattr(part, 'function_call') True
        # It's already done by creating MagicMock part and accessing part.function_call

        response.candidates = [candidate]

        calls = handler._extract_function_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "test_tool"
        assert calls[0]["arguments"]["arg"] == "val"

    def test_extract_function_calls_anthropic(self, handler):
        handler.provider = "anthropic"
        response = MagicMock()
        block = MagicMock()
        block.type = "tool_use"
        block.name = "test_tool"
        block.input = {"arg": "val"}
        response.content = [block]

        calls = handler._extract_function_calls(response)
        assert len(calls) == 1
        assert calls[0]["name"] == "test_tool"
        assert calls[0]["arguments"]["arg"] == "val"

    @pytest.mark.asyncio
    async def test_generate_google_with_tools(self, handler, mock_llm_client):
        handler.provider = "google"
        handler.llm_client._client.models.generate_content.return_value = "response"

        with (
            patch("google.genai.types.GenerateContentConfig"),
            patch("google.genai.types.FunctionDeclaration"),
            patch("google.genai.types.Tool"),
        ):
            result = await handler._generate_google_with_tools([], 0.7, 100)
            assert result == "response"
            handler.llm_client._client.models.generate_content.assert_called()

    @pytest.mark.asyncio
    async def test_generate_openai_with_litellm(self, handler):
        handler.provider = "litellm"  # Lowercase to match actual implementation
        with patch.dict("sys.modules", {"litellm": MagicMock()}):
            import litellm

            # The implementation streams chunks and reassembles via stream_chunk_builder.
            # Mock acompletion to return an async iterable of one chunk.
            mock_chunk = MagicMock()

            async def _fake_stream(*args, **kwargs):
                yield mock_chunk

            litellm.acompletion = AsyncMock(return_value=_fake_stream())

            mock_built = MagicMock()
            litellm.stream_chunk_builder = MagicMock(return_value=mock_built)

            result = await handler._generate_openai_with_tools([], 0.7, 100)

            # Verify litellm.acompletion was called with stream=True
            litellm.acompletion.assert_called_once()
            call_kwargs = litellm.acompletion.call_args[1]
            assert call_kwargs.get("stream") is True
            # Result should be the stream_chunk_builder output
            assert result == mock_built

    @pytest.mark.asyncio
    async def test_tracing(self, handler, mock_llm_client, mock_langfuse):
        mock_langfuse.should_trace.return_value = True
        handler.observability_config = {"enabled": True}
        handler.trace_id = "trace-123"

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].message.content = "Response"
        mock_llm_client._client.chat.completions.create.return_value = mock_response

        await handler._generate_openai_with_tools([], 0.7, 100)

        mock_langfuse.create_generation.assert_called_once()


# ---------------------------------------------------------------------------
# _compact_schema
# ---------------------------------------------------------------------------


class TestCompactSchema:
    def test_strips_property_descriptions(self):
        schema = {
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner username"},
                "repo": {"type": "string", "description": "Repository name"},
            },
            "required": ["owner", "repo"],
        }
        result = _compact_schema(schema)
        assert "description" not in result["properties"]["owner"]
        assert "description" not in result["properties"]["repo"]

    def test_preserves_types(self):
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Number of items"},
                "name": {"type": "string", "description": "Item name"},
            },
        }
        result = _compact_schema(schema)
        assert result["properties"]["count"]["type"] == "integer"
        assert result["properties"]["name"]["type"] == "string"

    def test_preserves_enums(self):
        schema = {
            "type": "object",
            "properties": {
                "event": {
                    "type": "string",
                    "enum": ["COMMENT", "APPROVE", "REQUEST_CHANGES"],
                    "description": "The review action to take",
                }
            },
        }
        result = _compact_schema(schema)
        assert result["properties"]["event"]["enum"] == ["COMMENT", "APPROVE", "REQUEST_CHANGES"]
        assert "description" not in result["properties"]["event"]

    def test_preserves_required_array(self):
        schema = {
            "type": "object",
            "properties": {
                "a": {"type": "string", "description": "A"},
                "b": {"type": "string", "description": "B"},
            },
            "required": ["a"],
        }
        result = _compact_schema(schema)
        assert result["required"] == ["a"]

    def test_preserves_default_values(self):
        schema = {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10, "description": "Max items"},
            },
        }
        result = _compact_schema(schema)
        assert result["properties"]["limit"]["default"] == 10

    def test_handles_nested_object_properties(self):
        schema = {
            "type": "object",
            "properties": {
                "comment": {
                    "type": "object",
                    "description": "A review comment object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "line": {"type": "integer", "description": "Line number"},
                    },
                }
            },
        }
        result = _compact_schema(schema)
        assert "description" not in result["properties"]["comment"]
        nested = result["properties"]["comment"]["properties"]
        assert "description" not in nested["path"]
        assert "description" not in nested["line"]
        assert nested["path"]["type"] == "string"

    def test_handles_array_items_with_descriptions(self):
        schema = {
            "type": "object",
            "properties": {
                "comments": {
                    "type": "array",
                    "description": "List of inline comments",
                    "items": {
                        "type": "object",
                        "properties": {
                            "body": {"type": "string", "description": "Comment text"},
                        },
                    },
                }
            },
        }
        result = _compact_schema(schema)
        assert "description" not in result["properties"]["comments"]
        assert "description" not in result["properties"]["comments"]["items"]["properties"]["body"]
        assert result["properties"]["comments"]["items"]["properties"]["body"]["type"] == "string"

    def test_empty_schema_unchanged(self):
        assert _compact_schema({}) == {}

    def test_schema_without_descriptions_unchanged(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        result = _compact_schema(schema)
        assert result == schema

    def test_anthropic_format_strips_parameter_descriptions(self, mock_tool_registry, mock_langfuse, mock_llm_client):
        """End-to-end: Anthropic format converter must use compact schemas."""
        verbose_tool = {
            "name": "verbose_tool",
            "description": "Does something important",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The full canonical name, as stored in the primary database",
                    }
                },
                "required": ["name"],
            },
        }
        mock_tool_registry.list_tools.return_value = [verbose_tool]
        mock_llm_client.provider = "ANTHROPIC"
        handler = FunctionCallingHandler(llm_client=mock_llm_client, tools=["verbose_tool"])
        handler.provider = "anthropic"

        result = handler._convert_to_anthropic_format()

        assert len(result) == 1
        # Tool-level description preserved
        assert result[0]["description"] == "Does something important"
        # Parameter description stripped
        prop = result[0]["input_schema"]["properties"]["name"]
        assert "description" not in prop
        assert prop["type"] == "string"
        # Required preserved
        assert result[0]["input_schema"]["required"] == ["name"]

    def test_openai_format_strips_parameter_descriptions(self, mock_tool_registry, mock_langfuse, mock_llm_client):
        """End-to-end: OpenAI format converter must use compact schemas."""
        verbose_tool = {
            "name": "verbose_tool",
            "description": "Does something",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The SQL query to execute"}},
                "required": ["query"],
            },
        }
        mock_tool_registry.list_tools.return_value = [verbose_tool]
        handler = FunctionCallingHandler(llm_client=mock_llm_client, tools=["verbose_tool"])

        result = handler._convert_to_openai_format()

        assert len(result) == 1
        prop = result[0]["function"]["parameters"]["properties"]["query"]
        assert "description" not in prop
        assert prop["type"] == "string"
