"""Unit tests for StreamConsumer's batch processing and embedding."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.company_brain.ingestion.stream_consumer import StreamConsumer


@pytest.mark.asyncio
async def test_process_batch_includes_knowledge_base_id_in_index_metadata():
    consumer = StreamConsumer()
    mock_kb = MagicMock()
    mock_kb.id = 42
    mock_kb.embedding_provider = MagicMock(value="SENTENCE_TRANSFORMERS")
    mock_kb.embedding_model = "all-MiniLM-L6-v2"
    mock_kb.get_embedding_config_decrypted.return_value = {}

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_kb
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None

    mock_search = AsyncMock()
    mock_search.index_documents = AsyncMock(return_value={"indexed": 1, "failed": 0})
    mock_dedup = AsyncMock()
    mock_dedup.filter_unseen = AsyncMock(return_value=["ext-1"])
    mock_dedup.mark_seen_batch = AsyncMock()

    raw_docs = [{"id": "ext-1", "content": "hello world this is enough content", "metadata": {}}]

    with (
        patch(
            "src.services.company_brain.ingestion.stream_consumer.create_celery_async_session",
            return_value=lambda: mock_session_cm,
        ),
        patch("src.services.company_brain.search.factory.get_search_backend", return_value=mock_search),
        patch("src.services.company_brain.ingestion.dedup.get_dedup_backend", return_value=mock_dedup),
        patch("src.services.company_brain.ingestion.chunker.chunk_document") as mock_chunk,
        patch.object(consumer, "_embed_batch", new=AsyncMock(return_value=[[0.1, 0.2]])),
    ):
        mock_chunk.return_value = [
            {"id": "ext-1", "chunk_index": 0, "chunk_content": "hello world this is enough content"}
        ]
        await consumer._process_batch(
            kb_id=42, tenant_id="tenant-1", source_type="slack", raw_docs=raw_docs, min_tokens=1
        )

    assert mock_search.index_documents.await_args.kwargs["knowledge_base_id"] == 42
    indexed_docs = mock_search.index_documents.await_args.kwargs["documents"]
    assert indexed_docs[0]["metadata"]["knowledge_base_id"] == 42


@pytest.mark.asyncio
async def test_process_batch_does_not_mark_seen_when_indexing_fails():
    """RedisSetDedup has no separate "failed" state — once `mark_seen_batch` is
    called for an external_id, `filter_unseen` will exclude it from every future
    batch forever (until the dedup TTL expires days later). If indexing fails
    (Qdrant error, invalid point ID, etc.) but dedup is marked anyway, the
    document is permanently and silently lost even though it was never actually
    stored. Reproduced live: a batch that failed to index in Qdrant was marked
    seen, so reprocessing later re-skipped it as "already seen" instead of
    retrying.
    """
    consumer = StreamConsumer()
    mock_kb = MagicMock()
    mock_kb.id = 42
    mock_kb.embedding_provider = MagicMock(value="SENTENCE_TRANSFORMERS")
    mock_kb.embedding_model = "all-MiniLM-L6-v2"
    mock_kb.get_embedding_config_decrypted.return_value = {}

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_kb
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None

    mock_search = AsyncMock()
    mock_search.index_documents = AsyncMock(return_value={"indexed": 0, "failed": 1})
    mock_dedup = AsyncMock()
    mock_dedup.filter_unseen = AsyncMock(return_value=["ext-1"])
    mock_dedup.mark_seen_batch = AsyncMock()

    raw_docs = [{"id": "ext-1", "content": "hello world this is enough content", "metadata": {}}]

    with (
        patch(
            "src.services.company_brain.ingestion.stream_consumer.create_celery_async_session",
            return_value=lambda: mock_session_cm,
        ),
        patch("src.services.company_brain.search.factory.get_search_backend", return_value=mock_search),
        patch("src.services.company_brain.ingestion.dedup.get_dedup_backend", return_value=mock_dedup),
        patch("src.services.company_brain.ingestion.chunker.chunk_document") as mock_chunk,
        patch.object(consumer, "_embed_batch", new=AsyncMock(return_value=[[0.1, 0.2]])),
    ):
        mock_chunk.return_value = [
            {"id": "ext-1", "chunk_index": 0, "chunk_content": "hello world this is enough content"}
        ]
        stats = await consumer._process_batch(
            kb_id=42, tenant_id="tenant-1", source_type="slack", raw_docs=raw_docs, min_tokens=1
        )

    assert stats["failed"] == 1
    mock_dedup.mark_seen_batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_embed_batch_uses_kb_embedding_config():
    consumer = StreamConsumer()
    mock_kb = MagicMock()
    mock_kb.embedding_provider = MagicMock(value="OPENAI")
    mock_kb.embedding_model = "text-embedding-3-small"
    mock_kb.get_embedding_config_decrypted.return_value = {"api_key": "sk-test"}

    with patch("src.services.knowledge_base.embedding_service.EmbeddingService") as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc.embed_texts.return_value = [[0.1, 0.2, 0.3]]
        mock_svc_cls.return_value = mock_svc

        result = await consumer._embed_batch(["hello"], mock_kb)

    mock_svc_cls.assert_called_once_with(
        provider="OPENAI", model_name="text-embedding-3-small", config={"api_key": "sk-test"}
    )
    mock_svc.embed_texts.assert_called_once_with(["hello"], batch_size=32)
    assert result == [[0.1, 0.2, 0.3]]
