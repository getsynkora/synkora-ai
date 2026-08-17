"""Unit tests for BaseConnector's ingestion routing (STANDARD vs ADVANCED KB modes)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.data_source import DataSource
from src.models.knowledge_base import IngestionMode, KnowledgeBase
from src.services.data_sources.base_connector import BaseConnector


class _ConcreteConnector(BaseConnector):
    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        pass

    async def test_connection(self) -> dict:
        return {"success": True, "message": "ok", "details": {}}

    async def fetch_documents(self, since: datetime | None = None, limit: int | None = None) -> list[dict]:
        return []

    async def get_document_count(self) -> int:
        return 0

    def get_required_config_fields(self) -> list[str]:
        return []


def _make_connector(knowledge_base_id, db):
    ds = MagicMock(spec=DataSource)
    ds.id = 1
    ds.tenant_id = "tenant-abc"
    ds.knowledge_base_id = knowledge_base_id
    ds.type = MagicMock(value="slack")
    return _ConcreteConnector(data_source=ds, db=db)


class TestProcessBatchRouting:
    @pytest.mark.asyncio
    async def test_no_knowledge_base_falls_back_to_document_processor(self):
        mock_db = AsyncMock()
        connector = _make_connector(knowledge_base_id=None, db=mock_db)

        with patch("src.services.data_sources.base_connector.DocumentProcessor") as MockProcessor:
            mock_processor = MockProcessor.return_value
            mock_processor.process_documents = AsyncMock(return_value={"success": True})
            await connector._process_batch([{"id": "1", "content": "hello", "metadata": {}}])

        mock_processor.process_documents.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_standard_mode_kb_falls_back_to_document_processor(self):
        mock_db = AsyncMock()
        mock_kb = MagicMock(spec=KnowledgeBase)
        mock_kb.ingestion_mode = IngestionMode.STANDARD
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        mock_db.execute = AsyncMock(return_value=mock_result)

        connector = _make_connector(knowledge_base_id=7, db=mock_db)

        with patch("src.services.data_sources.base_connector.DocumentProcessor") as MockProcessor:
            mock_processor = MockProcessor.return_value
            mock_processor.process_documents = AsyncMock(return_value={"success": True})
            await connector._process_batch([{"id": "1", "content": "hello", "metadata": {}}])

        mock_processor.process_documents.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_advanced_mode_kb_routes_through_stream_producer(self):
        mock_db = AsyncMock()
        mock_kb = MagicMock(spec=KnowledgeBase)
        mock_kb.ingestion_mode = IngestionMode.ADVANCED
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        mock_db.execute = AsyncMock(return_value=mock_result)

        connector = _make_connector(knowledge_base_id=7, db=mock_db)
        documents = [{"id": "1", "content": "hello", "metadata": {}}]

        with patch("src.services.company_brain.ingestion.stream_producer.StreamProducer") as MockProducer:
            mock_producer = MockProducer.return_value
            mock_producer.push = AsyncMock(return_value={"queued": 1, "skipped": 0})
            await connector._process_batch(documents)

        mock_producer.push.assert_awaited_once_with(
            kb_id=7,
            tenant_id="tenant-abc",
            source_type="slack",
            documents=documents,
        )

    @pytest.mark.asyncio
    async def test_advanced_mode_normalizes_text_field_to_content(self):
        """Connectors following the legacy fetch_documents() 'text' field contract
        (Slack, GitHub, GitLab, Google Drive, Gmail, Telegram, etc.) must have their
        documents normalized to 'content' before reaching the Company Brain
        StreamProducer/chunker, which only reads 'content'. Without this, every
        document from these connectors is silently dropped during chunking with no
        error logged.
        """
        mock_db = AsyncMock()
        mock_kb = MagicMock(spec=KnowledgeBase)
        mock_kb.ingestion_mode = IngestionMode.ADVANCED
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        mock_db.execute = AsyncMock(return_value=mock_result)

        connector = _make_connector(knowledge_base_id=7, db=mock_db)
        documents = [{"id": "1", "text": "hello world", "metadata": {}}]

        with patch("src.services.company_brain.ingestion.stream_producer.StreamProducer") as MockProducer:
            mock_producer = MockProducer.return_value
            mock_producer.push = AsyncMock(return_value={"queued": 1, "skipped": 0})
            await connector._process_batch(documents)

        pushed_documents = mock_producer.push.await_args.kwargs["documents"]
        assert pushed_documents[0]["content"] == "hello world"
