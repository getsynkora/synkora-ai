"""Unit tests for QdrantHybridBackend knowledge_base_id scoping."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.company_brain.search.qdrant_hybrid_backend import (
    QdrantHybridBackend,
    _collection_name,
)


class TestCollectionName:
    def test_includes_knowledge_base_id_in_collection_name(self):
        name = _collection_name(tenant_id="tenant-abc", knowledge_base_id="42", tier="hot")
        assert "42" in name
        assert "tenant-abc" not in name  # tenant_id gets sanitized, so check the raw kb_id token
        assert name.startswith("cb_")
        assert name.endswith("_hot")

    def test_different_kb_ids_produce_different_collection_names(self):
        name_a = _collection_name(tenant_id="tenant-abc", knowledge_base_id="1", tier="hot")
        name_b = _collection_name(tenant_id="tenant-abc", knowledge_base_id="2", tier="hot")
        assert name_a != name_b


class TestEnsureCollectionCreatesRealCollection:
    """qdrant_client.models.VectorsConfig is a typing.Union alias (Union[VectorParams,
    Dict[str, VectorParams]]), not a constructible class. Calling VectorsConfig(...)
    raises "TypeError: Cannot instantiate typing.Union" — a plain dict must be passed
    for named vectors instead. This test exercises the real (non-mocked) collection
    creation path against the actual qdrant_client.models classes, since existing
    tests always mock out `_ensure_collection` and never caught this.
    """

    @pytest.mark.asyncio
    async def test_ensure_collection_creates_collection_when_missing(self):
        backend = QdrantHybridBackend()
        mock_client = MagicMock()
        mock_client.get_collection = AsyncMock(side_effect=Exception("not found"))
        mock_client.create_collection = AsyncMock()

        with patch.object(backend, "_get_client", return_value=mock_client):
            await backend._ensure_collection(
                tenant_id="tenant-abc", knowledge_base_id="42", tier="hot", dense_dim=384
            )

        mock_client.create_collection.assert_awaited_once()
        _, kwargs = mock_client.create_collection.call_args
        assert isinstance(kwargs["vectors_config"], dict)
        assert "dense" in kwargs["vectors_config"]


class TestIndexDocumentsUsesValidPointId:
    """Qdrant point IDs must be an unsigned integer or a UUID — arbitrary strings
    (e.g. Slack message-derived doc_ids like "C0B0ENY8UNQ_1786959431.976139_0",
    produced by StreamConsumer._process_batch's `f"{chunk['id']}_{chunk['chunk_index']}"`
    doc_id format) are rejected by real Qdrant with 400 Bad Request: "... is not
    a valid point ID, valid values are either an unsigned integer or a UUID."
    Reproduced against a live Qdrant instance during manual verification.
    """

    @pytest.mark.asyncio
    async def test_index_documents_converts_arbitrary_doc_id_to_valid_uuid_point_id(self):
        backend = QdrantHybridBackend()
        mock_client = MagicMock()
        mock_client.upsert = AsyncMock()

        with (
            patch.object(backend, "_get_client", return_value=mock_client),
            patch.object(backend, "_ensure_collection", new=AsyncMock()),
        ):
            await backend.index_documents(
                tenant_id="tenant-abc",
                knowledge_base_id="42",
                documents=[
                    {
                        "doc_id": "C0B0ENY8UNQ_1786959431.976139_0",
                        "external_id": "C0B0ENY8UNQ",
                        "source_type": "slack",
                        "content": "hello",
                        "embedding": [0.1] * 384,
                        "metadata": {},
                        "storage_tier": "hot",
                    }
                ],
            )

        mock_client.upsert.assert_awaited_once()
        _, kwargs = mock_client.upsert.call_args
        point = kwargs["points"][0]
        # A valid Qdrant point ID must be an int or a UUID — not the raw arbitrary doc_id.
        uuid.UUID(str(point.id))
        # The original doc_id must still be recoverable from the payload for lookups/dedup.
        assert point.payload["doc_id"] == "C0B0ENY8UNQ_1786959431.976139_0"

    def test_point_id_is_deterministic_for_same_doc_id(self):
        from src.services.company_brain.search.qdrant_hybrid_backend import _point_id

        assert _point_id("C0B0ENY8UNQ_1786959431.976139_0") == _point_id("C0B0ENY8UNQ_1786959431.976139_0")


class TestSearchScopedToKnowledgeBase:
    @pytest.mark.asyncio
    async def test_search_uses_kb_scoped_collection_name(self):
        backend = QdrantHybridBackend()
        mock_client = MagicMock()

        with (
            patch.object(backend, "_get_client", return_value=mock_client),
            patch.object(backend, "_ensure_collection"),
            patch.object(backend, "_search_collection", return_value=[]) as mock_search_collection,
        ):
            await backend.search(
                tenant_id="tenant-abc",
                knowledge_base_id="42",
                query="test query",
                query_vector=[0.1] * 384,
            )

        called_collection_names = [call.args[0] for call in mock_search_collection.call_args_list]
        assert all("42" in name for name in called_collection_names)
