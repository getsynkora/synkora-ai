"""VideoGenerationJob model — tracks async AI video generation jobs."""

from enum import StrEnum

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import BaseModel, TenantMixin


class VideoJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoGenerationJob(TenantMixin, BaseModel):
    __tablename__ = "video_generation_jobs"

    agent_id = Column(UUID(as_uuid=True), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(
        Enum(VideoJobStatus, name="video_job_status"),
        nullable=False,
        default=VideoJobStatus.PENDING,
    )
    provider = Column(String(50), nullable=False)  # kling | minimax_video
    prompt = Column(Text, nullable=False)
    duration = Column(Integer, nullable=False, default=5)
    external_task_id = Column(String(255), nullable=True)  # provider's task ID
    video_url = Column(Text, nullable=True)  # S3 presigned URL when done
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
