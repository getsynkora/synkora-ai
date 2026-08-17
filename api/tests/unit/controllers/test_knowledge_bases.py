"""Tests for knowledge bases controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.knowledge_bases import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.knowledge_base import IngestionMode, KnowledgeBaseStatus


def setup_db_execute_mock(mock_db, return_value, return_list=False):
    """Helper to mock async db.execute() pattern."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = return_value
    mock_result.scalar.return_value = 1 if return_list else return_value
    if return_list:
        mock_result.scalars.return_value.all.return_value = return_value if return_value else []
    else:
        mock_result.scalars.return_value.all.return_value = [return_value] if return_value else []
    mock_result.scalars.return_value.first.return_value = return_value
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_result


@pytest.fixture
def mock_db_session():
    db = AsyncMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def client(mock_db_session):
    app = FastAPI()
    app.include_router(router)

    # Mock dependencies
    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db

    # Mock tenant ID
    tenant_id = uuid.uuid4()
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    return TestClient(app), tenant_id, mock_db_session


def _create_mock_knowledge_base(kb_id, tenant_id, **kwargs):
    """Helper to create mock knowledge base."""
    mock_kb = MagicMock()
    mock_kb.id = kb_id
    mock_kb.tenant_id = tenant_id
    mock_kb.name = kwargs.get("name", "Test Knowledge Base")
    mock_kb.description = kwargs.get("description", "Test description")
    mock_kb.embedding_provider = kwargs.get("embedding_provider", "SENTENCE_TRANSFORMERS")
    mock_kb.embedding_model = kwargs.get("embedding_model", "all-MiniLM-L6-v2")
    mock_kb.embedding_config = kwargs.get("embedding_config", {})
    mock_kb.vector_db_provider = kwargs.get("vector_db_provider", "QDRANT")
    mock_kb.vector_db_config = kwargs.get("vector_db_config", {})
    mock_kb.chunking_strategy = kwargs.get("chunking_strategy", "SEMANTIC")
    mock_kb.chunk_size = kwargs.get("chunk_size", 1500)
    mock_kb.chunk_overlap = kwargs.get("chunk_overlap", 150)
    mock_kb.min_chunk_size = kwargs.get("min_chunk_size", 500)
    mock_kb.max_chunk_size = kwargs.get("max_chunk_size", 3000)
    mock_kb.chunking_config = kwargs.get("chunking_config", {})
    mock_kb.total_documents = kwargs.get("total_documents", 0)
    mock_kb.total_chunks = kwargs.get("total_chunks", 0)
    mock_kb.status = kwargs.get("status", KnowledgeBaseStatus.ACTIVE)
    mock_kb.ingestion_mode = kwargs.get("ingestion_mode", IngestionMode.STANDARD)
    mock_kb.created_at = datetime.now(UTC)
    mock_kb.updated_at = datetime.now(UTC)
    mock_kb.get_embedding_config_decrypted = MagicMock(return_value={})
    mock_kb.get_vector_db_config_decrypted = MagicMock(return_value={})
    mock_kb.set_embedding_config_encrypted = MagicMock()
    mock_kb.set_vector_db_config_encrypted = MagicMock()
    return mock_kb


class TestCreateKnowledgeBase:
    """Tests for creating knowledge bases."""

    def test_create_knowledge_base_success(self, client):
        """Test successful knowledge base creation."""
        test_client, tenant_id, mock_db = client

        kb_id = 1

        def mock_add(kb):
            kb.id = kb_id
            kb.created_at = datetime.now(UTC)
            kb.updated_at = datetime.now(UTC)
            kb.status = KnowledgeBaseStatus.ACTIVE
            kb.total_documents = 0
            kb.total_chunks = 0
            kb.get_embedding_config_decrypted = MagicMock(return_value={})
            kb.get_vector_db_config_decrypted = MagicMock(return_value={})

        mock_db.add.side_effect = mock_add

        response = test_client.post(
            "/knowledge-bases",
            json={
                "name": "Test KB",
                "description": "Test description",
                "embedding_provider": "SENTENCE_TRANSFORMERS",
                "embedding_model": "all-MiniLM-L6-v2",
                "vector_db_provider": "QDRANT",
                "chunking_strategy": "SEMANTIC",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test KB"

    def test_create_knowledge_base_invalid_embedding_provider(self, client):
        """Test creating KB with invalid embedding provider."""
        test_client, tenant_id, mock_db = client

        response = test_client.post(
            "/knowledge-bases",
            json={
                "name": "Test KB",
                "embedding_provider": "invalid_provider",
                "embedding_model": "model",
                "vector_db_provider": "QDRANT",
                "chunking_strategy": "SEMANTIC",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_knowledge_base_invalid_vector_db(self, client):
        """Test creating KB with invalid vector DB provider."""
        test_client, tenant_id, mock_db = client

        response = test_client.post(
            "/knowledge-bases",
            json={
                "name": "Test KB",
                "embedding_provider": "SENTENCE_TRANSFORMERS",
                "embedding_model": "all-MiniLM-L6-v2",
                "vector_db_provider": "INVALID",
                "chunking_strategy": "SEMANTIC",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestCreateKnowledgeBaseIngestionMode:
    """Tests for the ingestion_mode field on KB creation."""

    def test_create_knowledge_base_defaults_to_standard_ingestion_mode(self, client):
        """Test creating a KB without ingestion_mode defaults to standard."""
        test_client, tenant_id, mock_db = client

        kb_id = 1

        def mock_add(kb):
            kb.id = kb_id
            kb.created_at = datetime.now(UTC)
            kb.updated_at = datetime.now(UTC)
            kb.status = KnowledgeBaseStatus.ACTIVE
            kb.total_documents = 0
            kb.total_chunks = 0
            kb.get_embedding_config_decrypted = MagicMock(return_value={})
            kb.get_vector_db_config_decrypted = MagicMock(return_value={})

        mock_db.add.side_effect = mock_add

        response = test_client.post(
            "/knowledge-bases",
            json={
                "name": "Test KB",
                "embedding_provider": "SENTENCE_TRANSFORMERS",
                "embedding_model": "all-MiniLM-L6-v2",
                "vector_db_provider": "QDRANT",
                "chunking_strategy": "SEMANTIC",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["ingestion_mode"] == "standard"

    def test_create_knowledge_base_accepts_advanced_ingestion_mode(self, client):
        """Test creating a KB with ingestion_mode=advanced."""
        test_client, tenant_id, mock_db = client

        kb_id = 1

        def mock_add(kb):
            kb.id = kb_id
            kb.created_at = datetime.now(UTC)
            kb.updated_at = datetime.now(UTC)
            kb.status = KnowledgeBaseStatus.ACTIVE
            kb.total_documents = 0
            kb.total_chunks = 0
            kb.get_embedding_config_decrypted = MagicMock(return_value={})
            kb.get_vector_db_config_decrypted = MagicMock(return_value={})

        mock_db.add.side_effect = mock_add

        response = test_client.post(
            "/knowledge-bases",
            json={
                "name": "Test KB",
                "embedding_provider": "SENTENCE_TRANSFORMERS",
                "embedding_model": "all-MiniLM-L6-v2",
                "vector_db_provider": "QDRANT",
                "chunking_strategy": "SEMANTIC",
                "ingestion_mode": "advanced",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["ingestion_mode"] == "advanced"

    def test_create_knowledge_base_invalid_ingestion_mode(self, client):
        """Test creating a KB with an invalid ingestion_mode."""
        test_client, tenant_id, mock_db = client

        response = test_client.post(
            "/knowledge-bases",
            json={
                "name": "Test KB",
                "embedding_provider": "SENTENCE_TRANSFORMERS",
                "embedding_model": "all-MiniLM-L6-v2",
                "vector_db_provider": "QDRANT",
                "chunking_strategy": "SEMANTIC",
                "ingestion_mode": "not_a_real_mode",
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestListKnowledgeBases:
    """Tests for listing knowledge bases."""

    def test_list_knowledge_bases_success(self, client):
        """Test listing all knowledge bases."""
        test_client, tenant_id, mock_db = client

        mock_kb = _create_mock_knowledge_base(1, tenant_id)
        setup_db_execute_mock(mock_db, [mock_kb], return_list=True)

        response = test_client.get("/knowledge-bases")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_list_knowledge_bases_with_pagination(self, client):
        """Test listing knowledge bases with pagination."""
        test_client, tenant_id, mock_db = client

        setup_db_execute_mock(mock_db, [], return_list=True)

        response = test_client.get("/knowledge-bases?skip=10&limit=5")

        assert response.status_code == status.HTTP_200_OK


class TestGetKnowledgeBase:
    """Tests for getting a specific knowledge base."""

    def test_get_knowledge_base_success(self, client):
        """Test getting a specific knowledge base."""
        test_client, tenant_id, mock_db = client

        mock_kb = _create_mock_knowledge_base(1, tenant_id)
        setup_db_execute_mock(mock_db, mock_kb)

        response = test_client.get("/knowledge-bases/1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == 1

    def test_get_knowledge_base_not_found(self, client):
        """Test getting non-existent knowledge base."""
        test_client, tenant_id, mock_db = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.get("/knowledge-bases/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateKnowledgeBase:
    """Tests for updating knowledge bases."""

    def test_update_knowledge_base_success(self, client):
        """Test updating a knowledge base."""
        test_client, tenant_id, mock_db = client

        mock_kb = _create_mock_knowledge_base(1, tenant_id)
        setup_db_execute_mock(mock_db, mock_kb)

        response = test_client.put(
            "/knowledge-bases/1", json={"name": "Updated KB Name", "description": "Updated description"}
        )

        assert response.status_code == status.HTTP_200_OK
        mock_db.commit.assert_called()

    def test_update_knowledge_base_not_found(self, client):
        """Test updating non-existent knowledge base."""
        test_client, tenant_id, mock_db = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.put("/knowledge-bases/999", json={"name": "Updated"})

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteKnowledgeBase:
    """Tests for deleting knowledge bases."""

    def test_delete_knowledge_base_success(self, client):
        """Test deleting a knowledge base."""
        test_client, tenant_id, mock_db = client

        mock_kb = _create_mock_knowledge_base(1, tenant_id)

        # First call returns KB (select), second is delete documents (delete)
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            else:
                mock_result.rowcount = 0
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_db.delete = AsyncMock()

        response = test_client.delete("/knowledge-bases/1")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_knowledge_base_not_found(self, client):
        """Test deleting non-existent knowledge base."""
        test_client, tenant_id, mock_db = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.delete("/knowledge-bases/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetKnowledgeBaseStats:
    """Tests for getting knowledge base statistics."""

    def test_get_stats_success(self, client):
        """Test getting knowledge base stats."""
        test_client, tenant_id, mock_db = client

        mock_kb = _create_mock_knowledge_base(1, tenant_id, total_documents=10, total_chunks=100)

        # Mock data sources
        mock_ds = MagicMock()
        mock_ds.id = 1
        mock_ds.name = "Test Source"
        mock_ds.type = MagicMock(value="SLACK")
        mock_ds.is_connected = True
        mock_ds.last_sync_at = datetime.now(UTC)

        # First call returns KB, second returns data sources
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            else:
                mock_result.scalars.return_value.all.return_value = [mock_ds]
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        response = test_client.get("/knowledge-bases/1/stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["document_count"] == 10
        assert data["total_chunks"] == 100


class TestSearchKnowledgeBase:
    """Tests for searching knowledge bases."""

    def test_search_success(self, client):
        """Test successful search."""
        test_client, tenant_id, mock_db = client

        mock_kb = _create_mock_knowledge_base(1, tenant_id)
        setup_db_execute_mock(mock_db, mock_kb)

        with patch("src.controllers.knowledge_bases.EmbeddingService"):
            with patch("src.controllers.knowledge_bases.RAGService") as mock_rag:
                mock_rag_instance = mock_rag.return_value
                mock_rag_instance.search_knowledge_base = AsyncMock(
                    return_value=[
                        {"document_id": 1, "chunk_id": 1, "text": "Test result", "score": 0.95, "metadata": {}}
                    ]
                )

                response = test_client.post(
                    "/knowledge-bases/1/search", json={"query": "test query", "limit": 5, "min_score": 0.7}
                )

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert len(data) == 1

    def test_search_kb_not_found(self, client):
        """Test searching non-existent knowledge base."""
        test_client, tenant_id, mock_db = client

        setup_db_execute_mock(mock_db, None)

        response = test_client.post("/knowledge-bases/999/search", json={"query": "test"})

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestListDocuments:
    """Tests for listing documents in a knowledge base."""

    def test_list_documents_success(self, client):
        """Test listing documents."""
        test_client, tenant_id, mock_db = client

        mock_kb = _create_mock_knowledge_base(1, tenant_id)

        # Mock document
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.name = "Test Document"
        mock_doc.source_type = "manual"
        mock_doc.external_url = None
        mock_doc.file_size = 1000
        mock_doc.segment_count = 5
        mock_doc.has_images = False
        mock_doc.image_count = 0
        mock_doc.created_at = datetime.now(UTC)
        mock_doc.updated_at = datetime.now(UTC)
        mock_doc.doc_metadata = {}
        mock_doc.status = MagicMock(value="completed")

        # First call returns KB, second returns count, third returns documents
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            elif call_count[0] == 2:
                mock_result.scalar.return_value = 1
            else:
                mock_result.scalars.return_value.all.return_value = [mock_doc]
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        response = test_client.get("/knowledge-bases/1/documents")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "documents" in data
        assert data["total"] == 1

    def test_list_documents_with_search(self, client):
        """Test listing documents with search filter."""
        test_client, tenant_id, mock_db = client

        mock_kb = _create_mock_knowledge_base(1, tenant_id)

        # First call returns KB, second returns count, third returns documents
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            elif call_count[0] == 2:
                mock_result.scalar.return_value = 0
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        response = test_client.get("/knowledge-bases/1/documents?search=test")

        assert response.status_code == status.HTTP_200_OK


class TestDeleteDocument:
    """Tests for deleting documents."""

    def test_delete_document_success(self, client):
        """Test deleting a document."""
        test_client, tenant_id, mock_db = client

        mock_kb = _create_mock_knowledge_base(1, tenant_id)

        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.name = "Test Document"

        # First call for KB, second for document
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            else:
                mock_result.scalar_one_or_none.return_value = mock_doc
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_db.delete = AsyncMock()

        response = test_client.delete(f"/knowledge-bases/1/documents/{mock_doc.id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_document_not_found(self, client):
        """Test deleting non-existent document."""
        test_client, tenant_id, mock_db = client

        mock_kb = _create_mock_knowledge_base(1, tenant_id)

        # First call returns KB, second returns None (document not found)
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        response = test_client.delete(f"/knowledge-bases/1/documents/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestBulkDeleteDocuments:
    """Tests for bulk deleting documents."""

    def test_bulk_delete_success(self, client):
        """Test bulk deleting documents."""
        test_client, tenant_id, mock_db = client

        mock_kb = _create_mock_knowledge_base(1, tenant_id)

        # First call returns KB, second is the delete
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            else:
                mock_result.rowcount = 3
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        doc_ids = [str(uuid.uuid4()) for _ in range(3)]

        response = test_client.post("/knowledge-bases/1/documents/bulk-delete", json=doc_ids)

        assert response.status_code == status.HTTP_204_NO_CONTENT
