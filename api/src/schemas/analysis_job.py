# api/src/schemas/analysis_job.py
"""Pydantic schemas for AnalysisJob API responses."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from src.models.analysis_job import JobStatus, JobType


class AnalysisJobListItem(BaseModel):
    id: UUID
    status: JobStatus
    job_type: JobType
    source_type: str | None
    conversation_id: UUID
    rows_processed: int | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisJobDetail(AnalysisJobListItem):
    query: str | None
    analysis_spec: dict[str, Any] | None
    result_summary: dict[str, Any] | None
    write_log: dict[str, Any] | None
