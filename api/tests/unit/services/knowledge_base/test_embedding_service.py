"""Unit tests for EmbeddingService provider dispatch.

The KnowledgeBase.embedding_provider enum (models/knowledge_base.py) stores
UPPERCASE values (e.g. "SENTENCE_TRANSFORMERS", "COHERE", "HUGGINGFACE"), and
every caller passes `knowledge_base.embedding_provider.value` directly into
EmbeddingService(provider=...). The provider dispatch must therefore accept
these uppercase values without raising "Unsupported embedding provider".
"""

import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.services.knowledge_base.embedding_service import EmbeddingService, _run_async


class TestEmbeddingServiceProviderDispatch:
    def test_sentence_transformers_uppercase_does_not_raise(self):
        """This is the default embedding_provider value for every new KB."""
        EmbeddingService(provider="SENTENCE_TRANSFORMERS", model_name="all-MiniLM-L6-v2")

    def test_huggingface_uppercase_does_not_raise(self):
        EmbeddingService(provider="HUGGINGFACE", model_name="some-model")

    def test_cohere_uppercase_does_not_raise(self):
        mock_cohere = MagicMock()
        with patch.dict(sys.modules, {"cohere": mock_cohere}):
            EmbeddingService(provider="COHERE", model_name="embed-v3", config={"api_key": "key"})

    def test_openai_uppercase_still_works(self):
        with patch("openai.OpenAI") as MockClient:
            MockClient.return_value = MagicMock()
            EmbeddingService(provider="OPENAI", model_name="text-embedding-3-small", config={"api_key": "key"})

    def test_unknown_provider_still_raises(self):
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            EmbeddingService(provider="NOT_A_REAL_PROVIDER", model_name="x")

    def test_run_async_reuses_the_same_event_loop_across_calls(self):
        """`get_ml_client()` (src/core/ml_client.py) caches a single httpx.AsyncClient
        at module scope, bound to whichever event loop is running when it's first
        used. If `_run_async` tears down its event loop after every call, every
        embedding call after the very first one in a worker process's lifetime
        fails with "RuntimeError: Event loop is closed" — reproduced live during
        Company Brain end-to-end verification (2nd of 2 sequential embed_texts()
        batches failed with exactly this error).
        """

        async def get_loop_id():
            return id(asyncio.get_running_loop())

        first = _run_async(get_loop_id())
        second = _run_async(get_loop_id())
        assert first == second

    def test_sentence_transformers_embed_texts_routes_to_ml_client(self):
        service = EmbeddingService(provider="SENTENCE_TRANSFORMERS", model_name="all-MiniLM-L6-v2")

        async def fake_embed(texts, model):
            return [[0.1, 0.2] for _ in texts]

        mock_client = MagicMock()
        mock_client.embed = fake_embed
        with patch("src.core.ml_client.get_ml_client", return_value=mock_client):
            result = service.embed_texts(["hello world"])

        assert result == [[0.1, 0.2]]
