"""Unit tests for enhanced_rag_service's ADVANCED-mode (Company Brain) retrieval branch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.knowledge_base import IngestionMode
from src.services.knowledge_base.enhanced_rag_service import (
    EnhancedRAGService,
    RAGConfig,
    RetrievalStrategy,
)


class TestRetrieveFromKBAdvancedMode:
    @pytest.mark.asyncio
    async def test_advanced_mode_kb_searches_company_brain_backend(self):
        service = EnhancedRAGService()

        kb = MagicMock()
        kb.id = 42
        kb.ingestion_mode = IngestionMode.ADVANCED
        kb.name = "Advanced KB"
        kb.get_embedding_config_decrypted.return_value = {}
        kb.embedding_provider = MagicMock(value="sentence_transformers")
        kb.embedding_model = "all-MiniLM-L6-v2"

        agent_kb = MagicMock()
        agent_kb.retrieval_config = {}

        config = RAGConfig(strategy=RetrievalStrategy.HYBRID)

        mock_search_result = MagicMock()
        mock_search_result.doc_id = "doc-1"
        mock_search_result.score = 0.9
        mock_search_result.vector_score = 0.9
        mock_search_result.keyword_score = 0.0
        mock_search_result.content = "hello world"
        mock_search_result.title = "Doc One"
        mock_search_result.metadata = {"external_id": "ext-1"}

        mock_backend = MagicMock()
        mock_backend.search = AsyncMock(return_value=MagicMock(results=[mock_search_result]))

        with (
            patch(
                "src.services.knowledge_base.enhanced_rag_service.get_search_backend",
                return_value=mock_backend,
            ),
            patch(
                "src.services.knowledge_base.embedding_service.EmbeddingService.embed_texts",
                return_value=[[0.1] * 384],
            ),
        ):
            results = await service._retrieve_from_kb(
                query="test query",
                query_variations=["test query"],
                kb=kb,
                agent_kb=agent_kb,
                embedding_service=MagicMock(),
                vector_db_pool=MagicMock(),
                config=config,
            )

        mock_backend.search.assert_awaited_once()
        call_kwargs = mock_backend.search.call_args.kwargs
        assert call_kwargs["knowledge_base_id"] == "42"
        assert len(results) == 1
        assert results[0].kb_id == 42
        assert results[0].text == "hello world"
