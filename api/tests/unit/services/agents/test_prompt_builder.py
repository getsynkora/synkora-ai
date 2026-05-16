import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.agent_context_file import AgentContextFile
from src.services.agents.prompt_builder import SystemPromptBuilder


class TestSystemPromptBuilder:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def builder(self, mock_db):
        return SystemPromptBuilder(mock_db)

    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock(spec=Agent)
        agent.id = uuid.uuid4()
        agent.system_prompt = "Original Prompt"
        return agent

    @pytest.mark.asyncio
    async def test_build_enhanced_prompt_no_context(self, builder, mock_agent):
        with patch.object(builder, "_build_context_section", new_callable=AsyncMock) as mock_context:
            mock_context.return_value = ""

            prompt = await builder.build_enhanced_prompt(mock_agent, include_context_files=False)
            assert "Original Prompt" in prompt
            assert "Current date:" in prompt
            assert "Current date and time" not in prompt

            prompt = await builder.build_enhanced_prompt(mock_agent, include_context_files=True)
            assert "Original Prompt" in prompt

    @pytest.mark.asyncio
    async def test_build_enhanced_prompt_with_context(self, builder, mock_agent):
        with patch.object(builder, "_build_context_section", new_callable=AsyncMock) as mock_context:
            mock_context.return_value = "Context Data"

            prompt = await builder.build_enhanced_prompt(mock_agent, include_context_files=True)
            assert "Original Prompt" in prompt
            assert "Context Data" in prompt

    def _make_mock_session(self, files):
        """Helper: build a mock async session that returns `files` from execute."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = files
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_cm)
        return MagicMock(return_value=mock_factory)

    def _make_mock_cache(self):
        """Helper: build a cache mock with a cache-miss on get_context_files."""
        mock_cache_instance = MagicMock()
        mock_cache_instance.get_context_files = AsyncMock(return_value=None)
        mock_cache_instance.set_context_files = AsyncMock()
        mock_cache = MagicMock(return_value=mock_cache_instance)
        return mock_cache

    @pytest.mark.asyncio
    async def test_build_context_section_no_files(self, builder, mock_agent):
        with patch("src.services.cache.get_agent_cache", self._make_mock_cache()):
            with patch("src.core.database.get_async_session_factory", self._make_mock_session([])):
                context = await builder._build_context_section(mock_agent)
                assert context == ""

    @pytest.mark.asyncio
    async def test_build_context_section_with_files(self, builder, mock_agent):
        file1 = MagicMock(spec=AgentContextFile)
        file1.filename = "file1.txt"
        file1.extracted_text = "Content 1"

        with patch("src.services.cache.get_agent_cache", self._make_mock_cache()):
            with patch("src.core.database.get_async_session_factory", self._make_mock_session([file1])):
                context = await builder._build_context_section(mock_agent)
                assert "CONTEXT FILES" in context
                assert "file1.txt" in context
                assert "Content 1" in context

    @pytest.mark.asyncio
    async def test_build_context_section_length_limit(self, builder, mock_agent):
        file1 = MagicMock(spec=AgentContextFile)
        file1.filename = "file1.txt"
        file1.extracted_text = "Content 1"

        with patch("src.services.cache.get_agent_cache", self._make_mock_cache()):
            with patch("src.core.database.get_async_session_factory", self._make_mock_session([file1])):
                context = await builder._build_context_section(mock_agent, max_context_length=5)
                assert "Content truncated" in context

    @pytest.mark.asyncio
    async def test_build_context_section_auto_compacts_large_files(self, builder, mock_agent):
        file1 = MagicMock(spec=AgentContextFile)
        file1.filename = "policy.txt"
        file1.extracted_text = ("Policy guidance for approvals and compliance. " * 200).strip()

        with patch("src.services.cache.get_agent_cache", self._make_mock_cache()):
            with patch("src.core.database.get_async_session_factory", self._make_mock_session([file1])):
                context = await builder._build_context_section(
                    mock_agent,
                    context_mode="auto",
                    context_query="compliance approvals",
                    full_context_threshold=200,
                    preview_chars=120,
                )
                assert "CONTEXT FILES (COMPACTED)" in context
                assert "policy.txt" in context
                assert "compacted for token efficiency" in context
                assert len(context) < len(file1.extracted_text)

    @pytest.mark.asyncio
    async def test_get_context_summary(self, builder, mock_agent):
        file1 = MagicMock(spec=AgentContextFile)
        file1.extraction_status = "COMPLETED"
        file1.file_size = 100
        file1.extracted_text = "text"
        file1.filename = "test.txt"
        file1.file_type = "text/plain"

        # Mock database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [file1]
        builder.db.execute = AsyncMock(return_value=mock_result)

        summary = await builder.get_context_summary(mock_agent)
        assert summary["total_files"] == 1
        assert summary["completed_files"] == 1
        assert summary["total_size_bytes"] == 100

    def test_format_context_for_chat(self):
        prompt = SystemPromptBuilder.format_context_for_chat("Sys", "Ctx", "User Msg")
        assert "Sys" in prompt
        assert "Ctx" in prompt
        assert "User Msg" in prompt
