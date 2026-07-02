"""
Agent Context File Model

Database model for storing files that provide permanent context to agents.
These files are automatically included in the agent's system prompt.
"""

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel, TenantMixin


class AgentContextFile(BaseModel, TenantMixin):
    """
    Agent Context File model for storing context files attached to agents.

    These files provide permanent context that is automatically included
    in the agent's system prompt. Supports various file types including
    PDF, DOCX, TXT, MD, CSV, and HTML.

    Attributes:
        agent_id: Foreign key to the agent
        filename: Original filename
        file_type: File MIME type
        file_size: File size in bytes
        s3_key: S3 storage key
        s3_bucket: S3 bucket name
        load_mode: "always" (inject into system prompt) or "on_demand" (LLM loads via tool)
        description: Short description shown in manifest for on_demand files (auto-generated, user-overridable)
        extraction_status: Status of text extraction (pending, completed, failed)
        extraction_error: Error message if extraction failed
        display_order: Order for displaying files (lower numbers first)
        tenant_id: Tenant identifier for multi-tenancy
    """

    __tablename__ = "agent_context_files"

    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Agent this file belongs to",
    )

    filename = Column(String(255), nullable=False, comment="Original filename")

    file_type = Column(String(100), nullable=False, comment="File MIME type")

    file_size = Column(BigInteger, nullable=False, comment="File size in bytes")

    s3_key = Column(String(500), nullable=False, comment="S3 storage key")

    s3_bucket = Column(String(255), nullable=False, comment="S3 bucket name")

    load_mode = Column(
        String(20),
        nullable=False,
        default="always",
        comment="always | on_demand",
    )

    description = Column(
        String(500),
        nullable=True,
        comment="Short description shown to LLM in on-demand manifest (auto-generated, user-overridable)",
    )

    extraction_status = Column(
        String(50),
        nullable=False,
        default="PENDING",
        index=True,
        comment="Status of text extraction (PENDING, COMPLETED, FAILED)",
    )

    extraction_error = Column(Text, nullable=True, comment="Error message if extraction failed")

    display_order = Column(Integer, nullable=False, default=0, comment="Display order (lower numbers first)")

    # Relationships
    agent = relationship("Agent", back_populates="context_files")

    def __repr__(self) -> str:
        """String representation of agent context file."""
        return f"<AgentContextFile(id={self.id}, filename='{self.filename}', agent_id={self.agent_id})>"

    @property
    def is_extraction_complete(self) -> bool:
        """Check if text extraction is complete."""
        return self.extraction_status == "COMPLETED"

    @property
    def is_extraction_failed(self) -> bool:
        """Check if text extraction failed."""
        return self.extraction_status == "FAILED"

    @property
    def is_extraction_pending(self) -> bool:
        """Check if text extraction is pending."""
        return self.extraction_status == "PENDING"

    @property
    def file_extension(self) -> str:
        """Get file extension from filename."""
        if "." in self.filename:
            return self.filename.rsplit(".", 1)[1].lower()
        return ""

    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return round(self.file_size / (1024 * 1024), 2)

    def to_dict(self, exclude: set[str] | None = None) -> dict:
        """
        Convert to dictionary.

        Args:
            exclude: Additional fields to exclude

        Returns:
            Dictionary representation of the context file
        """
        data = super().to_dict(exclude=exclude)

        # Add computed fields
        data["file_extension"] = self.file_extension
        data["file_size_mb"] = self.file_size_mb
        data["is_extraction_complete"] = self.is_extraction_complete
        data["is_extraction_failed"] = self.is_extraction_failed
        data["is_extraction_pending"] = self.is_extraction_pending

        return data
