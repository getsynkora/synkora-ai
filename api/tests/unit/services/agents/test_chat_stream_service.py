"""Tests for chat_stream_service.py."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.fixture
def mock_agent_loader():
    """Create mock agent loader service."""
    loader = Mock()
    loader.load_agent = AsyncMock()
    return loader


@pytest.fixture
def mock_chat_service():
    """Create mock chat service."""
    service = Mock()
    service.save_user_message = Mock()
    service.save_assistant_message = Mock()
    service.mark_message_failed = Mock()
    service.update_agent_stats = Mock()
    service.queue_credit_deduction = Mock()
    return service


@pytest.fixture
def mock_tool_registry():
    """Create mock tool registry."""
    registry = Mock()
    registry.load_agent_mcp_tools = AsyncMock()
    registry.load_agent_custom_tools = AsyncMock()
    registry.list_tools = Mock(return_value=[])
    return registry


@pytest.fixture
def mock_output_sanitizer():
    """Create mock output sanitizer."""
    sanitizer = Mock()
    result = Mock()
    result.sanitized_content = "test content"
    result.detections = []
    result.action_taken = "none"
    sanitizer.sanitize.return_value = result
    return sanitizer


@pytest.fixture
def sample_db_agent():
    """Create a sample database agent mock."""
    agent = Mock()
    agent.id = uuid4()
    agent.tenant_id = uuid4()
    agent.agent_name = "test-agent"
    agent.llm_config = {"provider": "openai", "model": "gpt-4"}
    agent.agent_metadata = {}
    agent.system_prompt = "You are helpful"
    agent.workflow_type = None
    return agent


@pytest.fixture
def sample_agent():
    """Create a sample runtime agent mock."""
    agent = Mock()
    agent.llm_client = Mock()
    agent.llm_client.generate_content_stream = AsyncMock()
    agent.langfuse_service = Mock()
    agent.langfuse_service.should_trace.return_value = False
    agent.config = Mock()
    agent.config.tools = []
    agent.observability_config = {}
    return agent


@pytest.fixture
def sample_load_result(sample_db_agent, sample_agent):
    """Create a sample agent load result."""
    result = Mock()
    result.error = None
    result.db_agent = sample_db_agent
    result.agent = sample_agent
    result.is_workflow = False
    result.cache_hit = True
    result.loading_time = 0.1
    return result


class TestChatStreamServiceInit:
    """Tests for ChatStreamService initialization."""

    def test_init_with_defaults(self, mock_agent_loader, mock_chat_service):
        """Test initialization with default values."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(
            agent_loader=mock_agent_loader,
            chat_service=mock_chat_service,
        )

        assert service.agent_loader is mock_agent_loader
        assert service.chat_service is mock_chat_service
        assert service.tool_registry is not None
        assert service.output_sanitizer is not None

    def test_init_with_custom_dependencies(
        self, mock_agent_loader, mock_chat_service, mock_tool_registry, mock_output_sanitizer
    ):
        """Test initialization with custom dependencies."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(
            agent_loader=mock_agent_loader,
            chat_service=mock_chat_service,
            tool_registry=mock_tool_registry,
            output_sanitizer=mock_output_sanitizer,
        )

        assert service.tool_registry is mock_tool_registry
        assert service.output_sanitizer is mock_output_sanitizer


class TestStreamState:
    """Tests for StreamState dataclass."""

    def test_stream_state_defaults(self):
        """Test StreamState default values."""
        from src.services.agents.chat_stream_service import StreamState

        state = StreamState(assistant_chunks=[], chart_data=[])

        assert state.assistant_chunks == []
        assert state.chart_data == []
        assert state.total_output_tokens == 0
        assert state.first_token_time is None

    def test_stream_state_with_values(self):
        """Test StreamState with custom values."""
        from src.services.agents.chat_stream_service import StreamState

        state = StreamState(
            assistant_chunks=["chunk1"],
            chart_data=[{"type": "bar"}],
            total_output_tokens=100,
            first_token_time=12345.0,
        )

        assert state.assistant_chunks == ["chunk1"]
        assert state.total_output_tokens == 100
        assert state.first_token_time == 12345.0


class TestSanitizeForJson:
    """Tests for _sanitize_for_json method."""

    def test_sanitize_dict(self, mock_agent_loader, mock_chat_service):
        """Test sanitizing a dictionary."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        data = {"key": "value", "nested": {"inner": "data"}}
        result = service._sanitize_for_json(data)

        assert result == {"key": "value", "nested": {"inner": "data"}}

    def test_sanitize_list(self, mock_agent_loader, mock_chat_service):
        """Test sanitizing a list."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        data = ["item1", "item2", {"key": "value"}]
        result = service._sanitize_for_json(data)

        assert result == ["item1", "item2", {"key": "value"}]

    def test_sanitize_tuple(self, mock_agent_loader, mock_chat_service):
        """Test sanitizing a tuple to list."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        data = ("item1", "item2")
        result = service._sanitize_for_json(data)

        assert result == ["item1", "item2"]

    def test_sanitize_uuid(self, mock_agent_loader, mock_chat_service):
        """Test sanitizing a UUID to string."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        test_uuid = uuid4()
        result = service._sanitize_for_json(test_uuid)

        assert result == str(test_uuid)

    def test_sanitize_nested_uuid(self, mock_agent_loader, mock_chat_service):
        """Test sanitizing nested UUIDs."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        test_uuid = uuid4()
        data = {"id": test_uuid, "items": [test_uuid]}
        result = service._sanitize_for_json(data)

        assert result["id"] == str(test_uuid)
        assert result["items"][0] == str(test_uuid)

    def test_sanitize_primitive(self, mock_agent_loader, mock_chat_service):
        """Test sanitizing primitive values."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        assert service._sanitize_for_json("string") == "string"
        assert service._sanitize_for_json(123) == 123
        assert service._sanitize_for_json(12.5) == 12.5
        assert service._sanitize_for_json(True) is True
        assert service._sanitize_for_json(None) is None


class TestSelectTools:
    """Tests for _select_tools method."""

    def test_select_tools_from_config(self, mock_agent_loader, mock_chat_service, mock_tool_registry):
        """Test selecting tools from agent config."""
        from src.services.agents.chat_stream_service import ChatStreamService

        mock_tool_registry.list_tools.return_value = [
            {"name": "tool1", "description": "Tool one", "parameters": {}},
            {"name": "tool2", "description": "Tool two", "parameters": {}},
            {"name": "internal_search_available_tools", "description": "Search tools", "parameters": {}},
            {"name": "internal_list_tool_categories", "description": "List tool categories", "parameters": {}},
        ]
        service = ChatStreamService(mock_agent_loader, mock_chat_service, tool_registry=mock_tool_registry)

        agent = Mock()
        tool1 = Mock()
        tool1.name = "tool1"
        tool2 = Mock()
        tool2.name = "tool2"
        agent.config.tools = [tool1, tool2]

        result = service._select_tools(agent, [])

        assert "tool1" in result
        assert "tool2" in result

    def test_select_tools_from_db(self, mock_agent_loader, mock_chat_service, mock_tool_registry):
        """Test selecting tools from database."""
        from src.services.agents.chat_stream_service import ChatStreamService

        mock_tool_registry.list_tools.return_value = [
            {"name": "db_tool1", "description": "Database tool one", "parameters": {}},
            {"name": "db_tool2", "description": "Database tool two", "parameters": {}},
            {"name": "internal_search_available_tools", "description": "Search tools", "parameters": {}},
            {"name": "internal_list_tool_categories", "description": "List tool categories", "parameters": {}},
        ]
        service = ChatStreamService(mock_agent_loader, mock_chat_service, tool_registry=mock_tool_registry)

        agent = Mock()
        agent.config.tools = []

        db_tool1 = Mock()
        db_tool1.tool_name = "db_tool1"
        db_tool2 = Mock()
        db_tool2.tool_name = "db_tool2"

        result = service._select_tools(agent, [db_tool1, db_tool2])

        assert "db_tool1" in result
        assert "db_tool2" in result

    def test_select_tools_combined(self, mock_agent_loader, mock_chat_service, mock_tool_registry):
        """Test combining tools from config and database."""
        from src.services.agents.chat_stream_service import ChatStreamService

        mock_tool_registry.list_tools.return_value = [
            {"name": "config_tool", "description": "Configuration tool", "parameters": {}},
            {"name": "db_tool", "description": "Database tool", "parameters": {}},
            {"name": "internal_search_available_tools", "description": "Search tools", "parameters": {}},
            {"name": "internal_list_tool_categories", "description": "List tool categories", "parameters": {}},
        ]
        service = ChatStreamService(mock_agent_loader, mock_chat_service, tool_registry=mock_tool_registry)

        agent = Mock()
        config_tool = Mock()
        config_tool.name = "config_tool"
        agent.config.tools = [config_tool]

        db_tool = Mock()
        db_tool.tool_name = "db_tool"

        result = service._select_tools(agent, [db_tool])

        assert "config_tool" in result
        assert "db_tool" in result

    def test_select_tools_deduplication(self, mock_agent_loader, mock_chat_service, mock_tool_registry):
        """Test deduplication of tool names."""
        from src.services.agents.chat_stream_service import ChatStreamService
        from src.services.agents.tool_filter import ALWAYS_INCLUDE_TOOLS

        mock_tool_registry.list_tools.return_value = [
            {"name": "same_tool", "description": "Deduplicated tool", "parameters": {}},
            {"name": "internal_search_available_tools", "description": "Search tools", "parameters": {}},
            {"name": "internal_list_tool_categories", "description": "List tool categories", "parameters": {}},
        ]
        service = ChatStreamService(mock_agent_loader, mock_chat_service, tool_registry=mock_tool_registry)

        agent = Mock()
        config_tool = Mock()
        config_tool.name = "same_tool"
        agent.config.tools = [config_tool]

        db_tool = Mock()
        db_tool.tool_name = "same_tool"

        result = service._select_tools(agent, [db_tool])

        # Should have: same_tool (deduplicated) + ALWAYS_INCLUDE_TOOLS
        assert "same_tool" in result
        assert result.count("same_tool") == 1  # Deduplicated
        # Discovery tools are always included
        for tool in ALWAYS_INCLUDE_TOOLS:
            assert tool in result

    def test_select_tools_no_tools(self, mock_agent_loader, mock_chat_service, mock_tool_registry):
        """Test selecting when no tools available - still includes discovery tools."""
        from src.services.agents.chat_stream_service import ChatStreamService
        from src.services.agents.tool_filter import ALWAYS_INCLUDE_TOOLS

        mock_tool_registry.list_tools.return_value = [
            {"name": "internal_search_available_tools", "description": "Search tools", "parameters": {}},
            {"name": "internal_list_tool_categories", "description": "List tool categories", "parameters": {}},
        ]
        service = ChatStreamService(mock_agent_loader, mock_chat_service, tool_registry=mock_tool_registry)

        agent = Mock()
        agent.config.tools = []

        result = service._select_tools(agent, [])

        # Even with no configured tools, discovery tools are always included
        assert len(result) == len(ALWAYS_INCLUDE_TOOLS)
        for tool in ALWAYS_INCLUDE_TOOLS:
            assert tool in result


class TestCreateTrace:
    """Tests for _create_trace method."""

    def test_create_trace_disabled(self, mock_agent_loader, mock_chat_service):
        """Test trace creation when disabled."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        agent = Mock()
        agent.langfuse_service = Mock()
        agent.langfuse_service.should_trace.return_value = False
        agent.observability_config = {}

        result = service._create_trace(agent, "test-agent", "Hello", ["tool1"])

        assert result is None
        agent.langfuse_service.create_trace.assert_not_called()

    def test_create_trace_enabled(self, mock_agent_loader, mock_chat_service):
        """Test trace creation when enabled."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        agent = Mock()
        agent.langfuse_service = Mock()
        agent.langfuse_service.should_trace.return_value = True
        agent.langfuse_service.create_trace.return_value = "trace-123"
        agent.observability_config = {"enabled": True}

        result = service._create_trace(agent, "test-agent", "Hello", ["tool1"])

        assert result == "trace-123"
        agent.langfuse_service.create_trace.assert_called_once()

    def test_create_trace_exception(self, mock_agent_loader, mock_chat_service):
        """Test trace creation handles exceptions."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        agent = Mock()
        agent.langfuse_service = Mock()
        agent.langfuse_service.should_trace.return_value = True
        agent.langfuse_service.create_trace.side_effect = Exception("Trace error")
        agent.observability_config = {"enabled": True}

        result = service._create_trace(agent, "test-agent", "Hello", [])

        assert result is None


class TestStreamAgentResponse:
    """Tests for stream_agent_response method."""

    @pytest.mark.asyncio
    async def test_stream_agent_response_error_on_load(self, mock_agent_loader, mock_chat_service, mock_db):
        """Test streaming handles agent load error."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        load_result = Mock()
        load_result.error = "Agent not found"
        mock_agent_loader.load_agent.return_value = load_result

        events = []
        async for event in service.stream_agent_response(
            agent_name="nonexistent",
            message="Hello",
            conversation_history=None,
            conversation_id=None,
            attachments=None,
            llm_config_id=None,
            db=mock_db,
        ):
            events.append(event)

        # Should have error event
        assert len(events) >= 1
        assert "error" in events[0].lower() or "Agent not found" in events[0]

    @pytest.mark.asyncio
    async def test_stream_agent_response_no_llm_client(
        self, mock_agent_loader, mock_chat_service, mock_db, sample_db_agent
    ):
        """Test streaming handles missing LLM client."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        load_result = Mock()
        load_result.error = None
        load_result.db_agent = sample_db_agent
        load_result.agent = Mock()
        load_result.agent.llm_client = None
        load_result.is_workflow = False
        load_result.cache_hit = False
        load_result.loading_time = 0.1
        mock_agent_loader.load_agent.return_value = load_result

        events = []
        async for event in service.stream_agent_response(
            agent_name="test-agent",
            message="Hello",
            conversation_history=None,
            conversation_id=None,
            attachments=None,
            llm_config_id=None,
            db=mock_db,
        ):
            events.append(event)

        # Should have error event about LLM client
        assert len(events) >= 1
        assert any("error" in str(e).lower() for e in events)


class TestLoadAgentResources:
    """Tests for _load_agent_resources method."""

    def _make_session_factory(self, mock_db):
        """Return a mock session factory whose context manager yields mock_db."""
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return MagicMock(return_value=mock_cm)

    @pytest.mark.asyncio
    async def test_load_agent_resources_success(
        self, mock_agent_loader, mock_chat_service, mock_tool_registry, mock_db, sample_db_agent
    ):
        """Test successful resource loading."""
        from unittest.mock import patch

        from src.services.agents.chat_stream_service import ChatStreamService

        mock_tool_registry.load_agent_mcp_tools = AsyncMock(return_value=[])
        mock_tool_registry.load_agent_custom_tools = AsyncMock(return_value=None)
        service = ChatStreamService(mock_agent_loader, mock_chat_service, tool_registry=mock_tool_registry)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.core.database.get_async_session_factory",
            return_value=self._make_session_factory(mock_db),
        ):
            agent_kbs, agent_tools, mcp_tool_names = await service._load_agent_resources(sample_db_agent, mock_db)

        assert agent_kbs == []
        assert agent_tools == []
        assert mcp_tool_names == []

    @pytest.mark.asyncio
    async def test_load_agent_resources_with_exception(
        self, mock_agent_loader, mock_chat_service, mock_tool_registry, mock_db, sample_db_agent
    ):
        """Test resource loading handles exceptions."""
        from unittest.mock import patch

        from src.services.agents.chat_stream_service import ChatStreamService

        mock_tool_registry.load_agent_mcp_tools = AsyncMock(side_effect=Exception("MCP error"))
        mock_tool_registry.load_agent_custom_tools = AsyncMock(side_effect=Exception("Custom tool error"))
        service = ChatStreamService(mock_agent_loader, mock_chat_service, tool_registry=mock_tool_registry)

        mock_db.execute = AsyncMock(side_effect=Exception("Database error"))

        with patch(
            "src.core.database.get_async_session_factory",
            return_value=self._make_session_factory(mock_db),
        ):
            agent_kbs, agent_tools, mcp_tool_names = await service._load_agent_resources(sample_db_agent, mock_db)

        assert agent_kbs == []
        assert agent_tools == []
        assert mcp_tool_names == []


class TestRetrieveRagContext:
    """Tests for _retrieve_rag_context method."""

    @pytest.mark.asyncio
    async def test_retrieve_rag_context_skip_disabled(self, mock_agent_loader, mock_chat_service, sample_db_agent):
        """Test RAG skipped when disabled."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        context_text, sources = await service._retrieve_rag_context(
            message="Hello",
            db_agent=sample_db_agent,
            agent_kbs=[],
            rag_config={"enabled": False},
            should_perform_rag=False,
        )

        assert context_text == ""
        assert sources == []

    @pytest.mark.asyncio
    async def test_retrieve_rag_context_skip_no_kbs(self, mock_agent_loader, mock_chat_service, sample_db_agent):
        """Test RAG skipped when no knowledge bases."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        context_text, sources = await service._retrieve_rag_context(
            message="Hello",
            db_agent=sample_db_agent,
            agent_kbs=[],
            rag_config={"enabled": True},
            should_perform_rag=False,
        )

        assert context_text == ""
        assert sources == []


class TestBuildPrompt:
    """Tests for _build_prompt method."""

    @pytest.mark.asyncio
    async def test_build_prompt_basic(self, mock_agent_loader, mock_chat_service, mock_db, sample_db_agent):
        """Test basic prompt building."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        with patch("src.services.agents.prompt_builder.SystemPromptBuilder") as mock_builder:
            mock_builder_instance = Mock()
            mock_builder_instance.build_enhanced_prompt = AsyncMock(return_value="System prompt")
            mock_builder.return_value = mock_builder_instance

            system_prompt, messages = await service._build_prompt(
                db=mock_db,
                db_agent=sample_db_agent,
                conversation_history=None,
                attachment_context="",
                context_text="",
                message="Hello",
                perf_config={},
            )

            # Check system prompt is built
            assert "System prompt" in system_prompt
            # Check messages contains the user message
            assert len(messages) >= 1
            assert any(m.get("content") == "Hello" for m in messages)

    @pytest.mark.asyncio
    async def test_build_prompt_with_context(self, mock_agent_loader, mock_chat_service, mock_db, sample_db_agent):
        """Test prompt building with RAG context."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        with patch("src.services.agents.prompt_builder.SystemPromptBuilder") as mock_builder:
            mock_builder_instance = Mock()
            mock_builder_instance.build_enhanced_prompt = AsyncMock(return_value="System prompt")
            mock_builder.return_value = mock_builder_instance

            system_prompt, messages = await service._build_prompt(
                db=mock_db,
                db_agent=sample_db_agent,
                conversation_history=None,
                attachment_context="",
                context_text="# Retrieved Context\nSome relevant info",
                message="Hello",
                perf_config={},
            )

            assert "Retrieved Context" in system_prompt
            assert "Cite sources" in system_prompt

    @pytest.mark.asyncio
    async def test_build_prompt_with_attachments(self, mock_agent_loader, mock_chat_service, mock_db, sample_db_agent):
        """Test prompt building with attachments."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        with patch("src.services.agents.prompt_builder.SystemPromptBuilder") as mock_builder:
            mock_builder_instance = Mock()
            mock_builder_instance.build_enhanced_prompt = AsyncMock(
                return_value="System prompt\n\n[Attachment: file.pdf content]"
            )
            mock_builder.return_value = mock_builder_instance

            system_prompt, messages = await service._build_prompt(
                db=mock_db,
                db_agent=sample_db_agent,
                conversation_history=None,
                attachment_context="[Attachment: file.pdf content]",
                context_text="",
                message="Hello",
                perf_config={},
            )

            assert "[Attachment: file.pdf content]" in system_prompt

    @pytest.mark.asyncio
    async def test_build_prompt_with_history(self, mock_agent_loader, mock_chat_service, mock_db, sample_db_agent):
        """Test prompt building with conversation history."""
        from src.services.agents.chat_stream_service import ChatStreamService

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        with patch("src.services.agents.prompt_builder.SystemPromptBuilder") as mock_builder:
            mock_builder_instance = Mock()
            mock_builder_instance.build_enhanced_prompt = AsyncMock(return_value="System prompt")
            mock_builder.return_value = mock_builder_instance

            with patch("src.services.agents.chat_stream_service.get_conversation_cache") as mock_cache:
                mock_cache_instance = Mock()
                mock_cache_instance.get_conversation_summary = AsyncMock(return_value=None)
                mock_cache.return_value = mock_cache_instance

                with patch("src.services.agents.context_manager.ContextManager") as mock_context:
                    mock_context_instance = Mock()
                    mock_context_instance.build_context.return_value = {
                        "strategy_used": "combined",
                        "estimated_tokens": 100,
                        "compression_applied": False,
                        "has_summary": False,
                        "context_parts": [
                            {
                                "type": "recent_messages",
                                "content": [
                                    {"role": "user", "content": "Previous message"},
                                    {"role": "assistant", "content": "Previous response"},
                                ],
                            }
                        ],
                    }
                    mock_context.return_value = mock_context_instance

                    history = [
                        {"role": "user", "content": "Previous message"},
                        {"role": "assistant", "content": "Previous response"},
                    ]

                    system_prompt, messages = await service._build_prompt(
                        db=mock_db,
                        db_agent=sample_db_agent,
                        conversation_history=history,
                        attachment_context="",
                        context_text="",
                        message="Hello",
                        perf_config={},
                    )

                    # Messages should include history and current message
                    assert len(messages) >= 1
                    # Check that messages contains the current user message
                    user_messages = [m for m in messages if m.get("role") == "user"]
                    assert any("Hello" in m.get("content", "") for m in user_messages)


class TestStreamWithoutTools:
    """Tests for _stream_without_tools method."""

    @pytest.mark.asyncio
    async def test_stream_without_tools_success(self, mock_agent_loader, mock_chat_service):
        """Test streaming without tools."""
        from src.services.agents.chat_stream_service import ChatStreamService, StreamState

        service = ChatStreamService(mock_agent_loader, mock_chat_service)

        agent = Mock()

        async def mock_stream(prompt):
            yield "Hello "
            yield "World!"

        agent.llm_client.generate_content_stream = mock_stream

        state = StreamState(assistant_chunks=[], chart_data=[])
        start_time = 1000.0

        events = []
        async for event in service._stream_without_tools(agent, start_time, state, prompt="test prompt"):
            events.append(event)

        # Should have events for chunks
        assert len(events) >= 2
        assert len(state.assistant_chunks) == 2
        assert "".join(state.assistant_chunks) == "Hello World!"


class TestStreamWithTools:
    """Tests for _stream_with_tools method."""

    @pytest.fixture(autouse=True)
    def patch_compute_resolver(self):
        with patch(
            "src.services.compute.resolver.build_compute_session_for_agent",
            new_callable=AsyncMock,
            return_value=None,
        ):
            yield

    @pytest.mark.asyncio
    async def test_stream_with_tools_text_event(
        self,
        mock_agent_loader,
        mock_chat_service,
        mock_output_sanitizer,
        mock_db,
        sample_db_agent,
        sample_agent,
    ):
        """Test streaming with tools handles text events."""
        from src.services.agents.chat_stream_service import ChatStreamService, StreamState

        service = ChatStreamService(mock_agent_loader, mock_chat_service, output_sanitizer=mock_output_sanitizer)

        state = StreamState(assistant_chunks=[], chart_data=[])
        start_time = 1000.0

        with patch("src.services.agents.function_calling.FunctionCallingHandler") as mock_handler:

            async def mock_stream(*args, **kwargs):
                yield {"type": "text", "content": "Hello"}
                yield {"type": "text", "content": " World"}

            mock_handler_instance = Mock()
            mock_handler_instance.generate_with_functions_stream = mock_stream
            mock_handler.return_value = mock_handler_instance

            events = []
            async for event in service._stream_with_tools(
                agent=sample_agent,
                db_agent=sample_db_agent,
                prompt="test",
                messages=[{"role": "user", "content": "test"}],
                tool_names=["tool1"],
                trace_id=None,
                conversation_uuid=None,
                user_message_id=None,
                start_time=start_time,
                state=state,
                db=mock_db,
            ):
                events.append(event)

            # Should have events including first_token and chunks
            assert len(events) >= 2

    @pytest.mark.asyncio
    async def test_stream_with_tools_function_call_event(
        self,
        mock_agent_loader,
        mock_chat_service,
        mock_output_sanitizer,
        mock_db,
        sample_db_agent,
        sample_agent,
    ):
        """Test streaming with tools handles function call events."""
        from src.services.agents.chat_stream_service import ChatStreamService, StreamState

        service = ChatStreamService(mock_agent_loader, mock_chat_service, output_sanitizer=mock_output_sanitizer)

        state = StreamState(assistant_chunks=[], chart_data=[])
        start_time = 1000.0

        with patch("src.services.agents.function_calling.FunctionCallingHandler") as mock_handler:

            async def mock_stream(*args, **kwargs):
                yield {"type": "function_call", "name": "search_tool"}
                yield {"type": "function_result", "name": "search_tool", "result": "data"}

            mock_handler_instance = Mock()
            mock_handler_instance.generate_with_functions_stream = mock_stream
            mock_handler.return_value = mock_handler_instance

            events = []
            async for event in service._stream_with_tools(
                agent=sample_agent,
                db_agent=sample_db_agent,
                prompt="test",
                messages=[{"role": "user", "content": "test"}],
                tool_names=["search_tool"],
                trace_id=None,
                conversation_uuid=None,
                user_message_id=None,
                start_time=start_time,
                state=state,
                db=mock_db,
            ):
                events.append(event)

            # Should have status events for tool usage
            assert len(events) >= 2
            assert any("search_tool" in str(e) for e in events)

    @pytest.mark.asyncio
    async def test_stream_with_tools_chart_event(
        self,
        mock_agent_loader,
        mock_chat_service,
        mock_output_sanitizer,
        mock_db,
        sample_db_agent,
        sample_agent,
    ):
        """Test streaming with tools handles chart events."""
        from src.services.agents.chat_stream_service import ChatStreamService, StreamState

        service = ChatStreamService(mock_agent_loader, mock_chat_service, output_sanitizer=mock_output_sanitizer)

        state = StreamState(assistant_chunks=[], chart_data=[])
        start_time = 1000.0

        with patch("src.services.agents.function_calling.FunctionCallingHandler") as mock_handler:

            async def mock_stream(*args, **kwargs):
                yield {
                    "type": "chart",
                    "chart": {
                        "chart_type": "bar",
                        "title": "Test Chart",
                        "data": {"x": [1, 2], "y": [3, 4]},
                        "config": {},
                    },
                }

            mock_handler_instance = Mock()
            mock_handler_instance.generate_with_functions_stream = mock_stream
            mock_handler.return_value = mock_handler_instance

            events = []
            async for event in service._stream_with_tools(
                agent=sample_agent,
                db_agent=sample_db_agent,
                prompt="test",
                messages=[{"role": "user", "content": "test"}],
                tool_names=["chart_tool"],
                trace_id=None,
                conversation_uuid=None,
                user_message_id=None,
                start_time=start_time,
                state=state,
                db=mock_db,
            ):
                events.append(event)

            # Should have chart data in state
            assert len(state.chart_data) == 1
            assert state.chart_data[0]["type"] == "bar"
            assert state.chart_data[0]["title"] == "Test Chart"
