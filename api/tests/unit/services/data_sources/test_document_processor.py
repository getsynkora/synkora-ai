from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.data_source import DataSource, DataSourceDocument, DataSourceType
from src.models.knowledge_base import EmbeddingProvider, KnowledgeBase, VectorDBProvider
from src.services.data_sources.document_processor import DocumentProcessor


class TestDocumentProcessor:
    @pytest.fixture
    def mock_db_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def processor(self, mock_db_session):
        with (
            patch("src.services.data_sources.document_processor.TextProcessor") as MockTP,
            patch("src.services.data_sources.document_processor.S3StorageService") as MockS3,
            patch("src.services.data_sources.document_processor.ImageExtractor") as MockIE,
        ):
            proc = DocumentProcessor(mock_db_session)
            proc.text_processor = MockTP.return_value
            proc.s3_storage = MockS3.return_value
            proc.image_extractor = MockIE.return_value
            return proc

    @pytest.fixture
    def mock_data_source(self):
        ds = MagicMock(spec=DataSource)
        ds.id = 123
        ds.tenant_id = uuid4()
        ds.name = "Test Source"
        ds.knowledge_base_id = 456
        ds.type = DataSourceType.CUSTOM  # Use a valid enum member
        return ds

    @pytest.fixture
    def mock_kb(self):
        kb = MagicMock(spec=KnowledgeBase)
        kb.id = 456
        kb.embedding_provider = EmbeddingProvider.OPENAI
        kb.embedding_model = "text-embedding-3-small"
        kb.vector_db_provider = VectorDBProvider.PINECONE
        kb.chunk_size = 1000
        kb.chunk_overlap = 200
        kb.chunking_strategy = MagicMock()
        kb.chunking_strategy.value = "recursive"  # Mock enum value access
        kb.min_chunk_size = 100
        kb.max_chunk_size = 2000
        kb.chunking_config = {}
        kb.get_embedding_config_decrypted.return_value = {"api_key": "test-key"}
        kb.get_vector_db_config_decrypted.return_value = {
            "api_key": "pinecone-key",
            "environment": "us-east-1",
            "index_name": "test-index",
        }
        kb.vector_db_config = {"index_name": "test-index"}
        return kb

    @pytest.mark.asyncio
    async def test_process_documents_no_kb(self, processor, mock_data_source):
        mock_data_source.knowledge_base_id = None
        documents = [{"id": "doc1", "text": "content", "metadata": {}}]

        processor._store_documents_only = AsyncMock(return_value={"success": True})

        result = await processor.process_documents(mock_data_source, documents)

        assert result["success"] is True
        processor._store_documents_only.assert_called_once_with(mock_data_source, documents)

    @pytest.mark.asyncio
    async def test_process_documents_kb_not_found(self, processor, mock_db_session, mock_data_source):
        # Mock execute returning None for KB lookup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        documents = [{"id": "doc1", "text": "content"}]

        result = await processor.process_documents(mock_data_source, documents)

        assert result["success"] is False
        assert "Knowledge base not found" in result["error"]

    @pytest.mark.asyncio
    async def test_process_documents_success(self, processor, mock_db_session, mock_data_source, mock_kb):
        # Mock execute returning KB
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        documents = [{"id": "doc1", "text": "content"}]

        processor._process_and_embed = AsyncMock(return_value={"success": True})

        result = await processor.process_documents(mock_data_source, documents)

        assert result["success"] is True
        processor._process_and_embed.assert_called_once_with(mock_data_source, mock_kb, documents)

    @pytest.mark.asyncio
    async def test_store_documents_only(self, processor, mock_db_session, mock_data_source):
        documents = [
            {"id": "doc1", "text": "content1", "metadata": {"title": "Doc 1"}},
            {"id": "doc2", "text": "content2", "metadata": {"title": "Doc 2"}},
        ]

        # Mock execute returning None (no existing docs)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await processor._store_documents_only(mock_data_source, documents)

        assert result["success"] is True
        assert result["documents_processed"] == 2
        assert mock_db_session.add.call_count == 2
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_documents_only_update_existing(self, processor, mock_db_session, mock_data_source):
        documents = [{"id": "doc1", "text": "new content"}]

        existing_doc = MagicMock(spec=DataSourceDocument)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_doc
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await processor._store_documents_only(mock_data_source, documents)

        assert result["success"] is True
        assert existing_doc.content == "new content"
        mock_db_session.add.assert_not_called()  # Update doesn't need add if attached
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_and_embed_success(self, processor, mock_db_session, mock_data_source, mock_kb):
        documents = [{"id": "doc1", "text": "content", "metadata": {"url": "http://test.com"}}]

        # Mock EmbeddingService
        with patch("src.services.data_sources.document_processor.EmbeddingService") as MockES:
            mock_es_instance = MockES.return_value
            mock_es_instance.get_embedding_dimension.return_value = 1536
            mock_es_instance.embed_texts.return_value = [[0.1, 0.2, 0.3]]  # One chunk, one vector

            # Mock VectorDBProviderFactory and VectorDB
            with patch("src.services.data_sources.document_processor.VectorDBProviderFactory") as MockFactory:
                mock_vector_db = MagicMock()
                MockFactory.create.return_value = mock_vector_db
                mock_vector_db.collection_exists.return_value = True
                mock_vector_db.add_vectors.return_value = ["vec-id-1"]

                # Mock TextProcessor (already patched in fixture, access via processor instance)
                processor.text_processor.chunk_text.return_value = [{"text": "chunk content", "metadata": {}}]

                # Mock execute calls in order:
                # 1. DataSourceDocument check → scalar_one_or_none → None (new doc)
                # 2. Document/KB doc check → scalars().all() → [] (no existing docs)
                # 3. Post-loop count query → scalar_one → 1 (for KB stats update)
                mock_result_none = MagicMock()
                mock_result_none.scalar_one_or_none.return_value = None

                mock_result_none2 = MagicMock()
                mock_result_none2.scalars.return_value.all.return_value = []

                mock_result_count = MagicMock()
                mock_result_count.scalar_one.return_value = 1

                mock_db_session.execute = AsyncMock(
                    side_effect=[mock_result_none, mock_result_none2, mock_result_count]
                )

                # Mock Image extraction
                processor._extract_and_store_images = AsyncMock()

                result = await processor._process_and_embed(mock_data_source, mock_kb, documents)

                assert result["success"] is True
                assert result["documents_processed"] == 1
                assert result["total_chunks"] == 1

                # Verify DB calls
                mock_vector_db.connect.assert_called_once()
                mock_es_instance.embed_texts.assert_called_once()
                mock_vector_db.add_vectors.assert_called_once()
                mock_vector_db.disconnect.assert_called_once()

                # Verify document creation
                # We expect DataSourceDocument and Document and DocumentSegment to be added
                assert mock_db_session.add.call_count >= 3
                assert mock_db_session.commit.call_count >= 2

    @pytest.mark.asyncio
    async def test_process_and_embed_create_collection(self, processor, mock_db_session, mock_data_source, mock_kb):
        documents = []  # No documents, just setup check

        with patch("src.services.data_sources.document_processor.EmbeddingService") as MockES:
            mock_es_instance = MockES.return_value
            mock_es_instance.get_embedding_dimension.return_value = 1536

            with patch("src.services.data_sources.document_processor.VectorDBProviderFactory") as MockFactory:
                mock_vector_db = MagicMock()
                MockFactory.create.return_value = mock_vector_db
                mock_vector_db.collection_exists.return_value = False  # Doesn't exist

                # Mock the count query at end
                mock_result_count = MagicMock()
                mock_result_count.scalar_one.return_value = 0
                mock_db_session.execute = AsyncMock(return_value=mock_result_count)

                result = await processor._process_and_embed(mock_data_source, mock_kb, documents)

                mock_vector_db.create_collection.assert_called_once()
                assert result["documents_processed"] == 0

    @pytest.mark.asyncio
    async def test_extract_and_store_images(self, processor, mock_kb):
        ds_doc = MagicMock(spec=DataSourceDocument)
        ds_doc.id = uuid4()
        ds_doc.external_id = "doc1"
        ds_doc.external_url = "s3://bucket/file.pdf"
        ds_doc.content_type = "pdf"
        ds_doc.doc_metadata = {}

        processor.s3_storage.download_file_content = AsyncMock(return_value=b"pdf content")
        processor.image_extractor.extract_images = AsyncMock(
            return_value=[{"data": b"img1", "format": "PNG", "width": 100, "height": 100, "page": 1}]
        )
        processor.s3_storage.upload_file_content = AsyncMock(return_value="http://s3/img1.png")

        await processor._extract_and_store_images(ds_doc, mock_kb)

        processor.s3_storage.download_file_content.assert_called_once()
        processor.image_extractor.extract_images.assert_called_once()
        processor.s3_storage.upload_file_content.assert_called_once()

        assert ds_doc.doc_metadata["has_images"] is True
        assert ds_doc.doc_metadata["image_count"] == 1
