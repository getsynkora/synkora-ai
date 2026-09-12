"""
Document model for RAG knowledge base.
"""

import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .document_segment import DocumentSegment


class DocumentStatus(enum.StrEnum):
    """Document processing status."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    ARCHIVED = "ARCHIVED"


class Document(BaseModel):
    """
    Document model for storing processed documents.

    Documents are uploaded files that have been processed and chunked
    for use in RAG (Retrieval-Augmented Generation).
    """

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    data_source_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("data_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Extracted content
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="text"
    )  # text, html, markdown, pdf, csv

    # S3 Storage (RAW FILE)
    s3_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    s3_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Source Attribution
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )  # SLACK, gmail, google_drive, csv, pdf, teams, manual
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata stored as JSON
    doc_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example: {"channel": "general", "user": "john", "timestamp": "..."}

    # Image metadata for multimodal support
    has_images: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    images: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example: [{"page": 1, "index": 1, "s3_url": "...", "width": 800, "height": 600}]

    # Upload metadata
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    upload_source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="data_source"
    )  # ui, api, data_source

    # Statistics
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Processing status
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="documents")
    data_source: Mapped[Optional["DataSource"]] = relationship("DataSource", back_populates="documents")
    segments: Mapped[list["DocumentSegment"]] = relationship(
        "DocumentSegment",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Document {self.name} ({self.status.value})>"

    def to_dict(self, _exclude: set[str] | None = None) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "knowledge_base_id": self.knowledge_base_id,
            "data_source_id": self.data_source_id,
            "name": self.name,
            "content_type": self.content_type,
            "source_type": self.source_type,
            "external_id": self.external_id,
            "external_url": self.external_url,
            "s3_bucket": self.s3_bucket,
            "s3_key": self.s3_key,
            "s3_url": self.s3_url,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "has_images": self.has_images,
            "image_count": self.image_count,
            "images": self.images,
            "original_filename": self.original_filename,
            "upload_source": self.upload_source,
            "status": self.status.value,
            "error": self.error,
            "metadata": self.doc_metadata,
            "source_created_at": self.source_created_at.isoformat() if self.source_created_at else None,
            "source_updated_at": self.source_updated_at.isoformat() if self.source_updated_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "segment_count": self.segment_count,
        }

    @property
    def is_processed(self) -> bool:
        """Check if document is fully processed."""
        return self.status == DocumentStatus.COMPLETED

    @property
    def has_error(self) -> bool:
        """Check if document has processing error."""
        return self.status == DocumentStatus.ERROR

    @property
    def segment_count(self) -> int:
        """Get number of segments.

        Prefers a cached _segment_count (set via column_property or manual
        annotation) to avoid lazy-loading the full segments collection.
        """
        if hasattr(self, "_segment_count") and self._segment_count is not None:
            return self._segment_count
        return len(self.segments) if self.segments else 0

    def update_from_dict(self, data: dict[str, Any], _exclude: set[str] | None = None) -> None:
        """Update document from dictionary."""
        for key, value in data.items():
            if hasattr(self, key) and key not in ["id", "created_at"]:
                setattr(self, key, value)
        self.updated_at = datetime.now(UTC)
