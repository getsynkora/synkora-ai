"""Base connector class for data source integrations."""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.data_source import DataSource, DataSourceStatus
from src.services.data_sources.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)


class SyncStatus(StrEnum):
    """Sync job status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class BaseConnector(ABC):
    """
    Abstract base class for data source connectors.

    All data source implementations must inherit from this class and implement
    the required methods.
    """

    def __init__(self, data_source: DataSource, db: AsyncSession):
        """
        Initialize the connector.

        Args:
            data_source: DataSource model instance
            db: Database session
        """
        self.data_source = data_source
        self.db = db
        self.client = None

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the data source.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection to the data source."""
        pass

    @abstractmethod
    async def test_connection(self) -> dict[str, Any]:
        """
        Test the connection to the data source.

        Returns:
            Dictionary with test results:
                {
                    "success": bool,
                    "message": str,
                    "details": dict
                }
        """
        pass

    @abstractmethod
    async def fetch_documents(self, since: datetime | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Fetch documents from the data source.

        Args:
            since: Fetch documents modified since this timestamp
            limit: Maximum number of documents to fetch

        Returns:
            List of documents with structure:
                {
                    "id": "unique_id",
                    "text": "document content",
                    "metadata": {
                        "title": "...",
                        "author": "...",
                        "timestamp": "...",
                        "source": "...",
                        ...
                    }
                }
        """
        pass

    @abstractmethod
    async def get_document_count(self) -> int:
        """
        Get total number of documents available.

        Returns:
            Total document count
        """
        pass

    async def sync(self, incremental: bool = True, batch_size: int = 100) -> dict[str, Any]:
        """
        Sync documents from the data source.

        Args:
            incremental: If True, only fetch new/updated documents
            batch_size: Number of documents to process per batch

        Returns:
            Sync result dictionary:
                {
                    "status": SyncStatus,
                    "documents_fetched": int,
                    "documents_processed": int,
                    "errors": List[str],
                    "started_at": datetime,
                    "completed_at": datetime
                }
        """
        started_at = datetime.now(UTC)
        errors = []
        documents_fetched = 0
        documents_processed = 0

        try:
            # Connect to data source
            connected = await self.connect()
            if not connected:
                raise ConnectionError("Failed to connect to data source")

            # Determine since timestamp for incremental sync
            since = None
            if incremental and self.data_source.last_sync_at:
                since = self.data_source.last_sync_at

            # Fetch documents
            logger.info(f"Fetching documents from {self.data_source.name} (incremental={incremental}, since={since})")
            documents = await self.fetch_documents(since=since)
            documents_fetched = len(documents)

            logger.info(f"Fetched {documents_fetched} documents")

            # Process documents in batches
            for i in range(0, len(documents), batch_size):
                batch = documents[i : i + batch_size]
                try:
                    await self._process_batch(batch)
                    documents_processed += len(batch)
                except Exception as e:
                    error_msg = f"Error processing batch {i // batch_size + 1}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Disconnect
            await self.disconnect()

            # Update data source
            completed_at = datetime.now(UTC)
            status = SyncStatus.SUCCESS if not errors else SyncStatus.PARTIAL

            self.data_source.last_sync_at = completed_at
            self.data_source.last_error = None if status == SyncStatus.SUCCESS else "; ".join(errors)
            self.data_source.total_documents = documents_processed
            await self.db.commit()

            return {
                "status": status,
                "documents_fetched": documents_fetched,
                "documents_processed": documents_processed,
                "errors": errors,
                "started_at": started_at,
                "completed_at": completed_at,
            }

        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

            # Update data source with error
            self.data_source.last_error = error_msg

            # A ConnectionError here means connect() itself failed (bad/corrupted
            # credentials, decryption failure, revoked token, etc.) — not a
            # transient issue expected to self-heal. Leaving status ACTIVE means
            # the periodic sync_all_data_sources_task dispatcher keeps re-picking
            # this data source up and failing identically forever. Mark it ERROR
            # so it's excluded from auto-dispatch until someone fixes the
            # credentials (which should reset status back to ACTIVE).
            if isinstance(e, ConnectionError):
                self.data_source.status = DataSourceStatus.ERROR

            await self.db.commit()

            return {
                "status": SyncStatus.FAILED,
                "documents_fetched": documents_fetched,
                "documents_processed": documents_processed,
                "errors": errors,
                "started_at": started_at,
                "completed_at": datetime.now(UTC),
            }

    async def _process_batch(self, documents: list[dict[str, Any]]) -> None:
        """
        Process a batch of documents.

        This processes documents through the knowledge base pipeline if linked,
        or stores them directly if not linked to a knowledge base.

        If the linked knowledge base is in ADVANCED ingestion mode, documents are
        routed through the Company Brain StreamProducer instead of the legacy
        DocumentProcessor pipeline.

        Args:
            documents: List of documents to process
        """
        logger.info(f"Processing batch of {len(documents)} documents")

        kb_id = self.data_source.knowledge_base_id
        if kb_id is not None:
            from src.models.knowledge_base import IngestionMode, KnowledgeBase

            result_kb = await self.db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
            kb = result_kb.scalar_one_or_none()
            if kb is not None and kb.ingestion_mode == IngestionMode.ADVANCED:
                from src.services.company_brain.ingestion.stream_producer import StreamProducer

                source_type = getattr(self.data_source.type, "value", str(self.data_source.type)).lower()
                # fetch_documents() implementations follow this class's documented "text"
                # field contract (see the abstract method above), but the Company Brain
                # stream/chunker pipeline only reads "content". Normalize here, at the
                # single bridging point, so every connector reaches it correctly.
                normalized_documents = [
                    {**doc, "content": doc.get("content") or doc.get("text", "")} for doc in documents
                ]
                producer = StreamProducer()
                push_result = await producer.push(
                    kb_id=kb_id,
                    tenant_id=str(self.data_source.tenant_id),
                    source_type=source_type,
                    documents=normalized_documents,
                )
                logger.info(
                    f"Queued {push_result.get('queued', 0)} documents to Company Brain stream, "
                    f"skipped {push_result.get('skipped', 0)}"
                )
                return

        # Use document processor to handle embedding and storage
        processor = DocumentProcessor(self.db)
        result = await processor.process_documents(self.data_source, documents)

        if result.get("success"):
            logger.info(
                f"Successfully processed {result.get('documents_processed', 0)} documents, "
                f"embedded {result.get('documents_embedded', 0)} documents"
            )
        else:
            logger.error(f"Document processing failed: {result.get('error')}")

    def get_sync_status(self) -> dict[str, Any]:
        """
        Get current sync status.

        Returns:
            Dictionary with sync status information
        """
        return {
            "status": self.data_source.status.value,
            "last_sync_at": self.data_source.last_sync_at,
            "last_error": self.data_source.last_error,
            "total_documents": self.data_source.total_documents,
        }

    def validate_config(self) -> dict[str, Any]:
        """
        Validate connector configuration.

        Returns:
            Dictionary with validation results:
                {
                    "valid": bool,
                    "errors": List[str]
                }
        """
        errors = []

        # Check if required config fields are present
        required_fields = self.get_required_config_fields()
        for field in required_fields:
            if field not in self.data_source.config:
                errors.append(f"Missing required config field: {field}")

        return {"valid": len(errors) == 0, "errors": errors}

    @abstractmethod
    def get_required_config_fields(self) -> list[str]:
        """
        Get list of required configuration fields.

        Returns:
            List of required field names
        """
        pass

    def get_oauth_url(self) -> str | None:
        """
        Get OAuth authorization URL if applicable.

        Returns:
            OAuth URL or None if not applicable
        """
        return None

    async def handle_oauth_callback(self, code: str) -> dict[str, Any]:
        """
        Handle OAuth callback.

        Args:
            code: OAuth authorization code

        Returns:
            Dictionary with OAuth result
        """
        raise NotImplementedError("OAuth not supported for this connector")
