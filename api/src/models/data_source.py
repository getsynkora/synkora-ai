"""Data source models for external integrations."""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, TimestampMixin


class DataSourceType(enum.StrEnum):
    """Data source types."""

    SLACK = "SLACK"
    GMAIL = "GMAIL"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    NOTION = "NOTION"
    CONFLUENCE = "CONFLUENCE"
    GITHUB = "GITHUB"
    GITLAB = "GITLAB"
    TELEGRAM = "TELEGRAM"
    MANUAL = "MANUAL"  # For direct file uploads from UI
    WEB = "WEB"  # For website crawling
    CUSTOM = "CUSTOM"
    # Project Management
    JIRA = "JIRA"
    CLICKUP = "CLICKUP"
    LINEAR = "LINEAR"
    ASANA = "ASANA"
    # Data Analysis Sources
    DATADOG = "DATADOG"
    DATABRICKS = "DATABRICKS"
    DOCKER_LOGS = "DOCKER_LOGS"
    CSV_FILE = "CSV_FILE"
    ZIP_FILE = "ZIP_FILE"


class DataSourceStatus(enum.StrEnum):
    """Data source connection status."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"
    SYNCING = "SYNCING"


class SyncStatus(enum.StrEnum):
    """Sync job status."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DataSource(BaseModel, TimestampMixin):
    """Data source configuration and connection details."""

    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    knowledge_base_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[DataSourceType] = mapped_column(Enum(DataSourceType), nullable=False, index=True)
    status: Mapped[DataSourceStatus] = mapped_column(
        Enum(DataSourceStatus), nullable=False, default=DataSourceStatus.INACTIVE
    )

    # OAuth connection details
    oauth_app_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("oauth_apps.id", ondelete="SET NULL"), nullable=True
    )
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Configuration
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Example config for Slack: {"workspace_id": "...", "channels": ["general", "random"]}
    # Example config for Gmail: {"labels": ["INBOX", "SENT"], "query": "is:unread"}

    # Sync settings
    sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sync_frequency_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)  # Default: hourly
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    total_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Company Brain domain assignment (nullable — sources without a domain are undomained)
    brain_domain_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brain_domains.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional Company Brain domain this source belongs to",
    )

    # Custom connector config for CUSTOM type sources (connector_class + init kwargs)
    custom_connector_config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Used when type=CUSTOM: {connector_class: 'mymodule.MyConnector', ...kwargs}",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="data_sources")
    knowledge_base: Mapped[Optional["KnowledgeBase"]] = relationship("KnowledgeBase", back_populates="data_sources")
    oauth_app: Mapped[Optional["OAuthApp"]] = relationship("OAuthApp")
    brain_domain: Mapped[Optional["BrainDomain"]] = relationship(
        "BrainDomain",
        back_populates="data_sources",
        foreign_keys=[brain_domain_id],
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="data_source", cascade="all, delete-orphan"
    )
    data_source_documents: Mapped[list["DataSourceDocument"]] = relationship(
        "DataSourceDocument", back_populates="data_source", cascade="all, delete-orphan"
    )
    sync_jobs: Mapped[list["DataSourceSyncJob"]] = relationship(
        "DataSourceSyncJob", back_populates="data_source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DataSource(id={self.id}, name={self.name}, type={self.type})>"


class DataSourceDocument(BaseModel, TimestampMixin):
    """Individual documents/items from data sources."""

    __tablename__ = "data_source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data_source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # External reference
    external_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # e.g., Slack message ID, Gmail message ID
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Content
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False, default="text")  # text, html, markdown

    # Metadata
    doc_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Example for Slack: {"channel": "general", "user": "john", "thread_ts": "..."}
    # Example for Gmail: {"from": "...", "to": "...", "subject": "...", "labels": [...]}

    # Tiered storage (hot/warm/archive) — see company_brain_tier_migration_task
    storage_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="hot")

    # Vector embedding
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # Qdrant point ID
    is_embedded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    data_source: Mapped["DataSource"] = relationship("DataSource", back_populates="data_source_documents")
    tenant: Mapped["Tenant"] = relationship("Tenant")

    def __repr__(self) -> str:
        return f"<DataSourceDocument(id={self.id}, external_id={self.external_id})>"


class DataSourceSyncJob(BaseModel, TimestampMixin):
    """Sync job tracking for data sources."""

    __tablename__ = "data_source_sync_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data_source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[SyncStatus] = mapped_column(Enum(SyncStatus), nullable=False, default=SyncStatus.PENDING, index=True)

    # Job details
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Statistics
    documents_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    documents_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    data_source: Mapped["DataSource"] = relationship("DataSource", back_populates="sync_jobs")
    tenant: Mapped["Tenant"] = relationship("Tenant")

    def __repr__(self) -> str:
        return f"<DataSourceSyncJob(id={self.id}, status={self.status})>"
