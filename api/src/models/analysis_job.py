"""AnalysisJob model — tracks background database query/write jobs."""

from enum import StrEnum

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.models.base import BaseModel, TenantMixin


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(StrEnum):
    READ = "read"
    WRITE = "write"


class AnalysisJob(TenantMixin, BaseModel):
    __tablename__ = "analysis_jobs"

    agent_id = Column(UUID(as_uuid=True), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(
        Enum(JobStatus, name="analysis_job_status"),
        nullable=False,
        default=JobStatus.PENDING,
    )
    job_type = Column(
        Enum(JobType, name="analysis_job_type"),
        nullable=False,
        default=JobType.READ,
    )
    source_type = Column(String(50), nullable=True)
    connection_id = Column(UUID(as_uuid=True), nullable=True)
    query = Column(Text, nullable=True)
    analysis_spec = Column(JSONB, nullable=True, default=dict)
    result_summary = Column(JSONB, nullable=True)
    write_log = Column(JSONB, nullable=True)
    rows_processed = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
