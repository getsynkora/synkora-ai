import uuid

import pytest

from src.models.analysis_job import AnalysisJob, JobStatus, JobType


def test_job_status_values():
    assert JobStatus.PENDING == "pending"
    assert JobStatus.RUNNING == "running"
    assert JobStatus.COMPLETED == "completed"
    assert JobStatus.FAILED == "failed"


def test_job_type_values():
    assert JobType.READ == "read"
    assert JobType.WRITE == "write"


def test_analysis_job_table_name():
    assert AnalysisJob.__tablename__ == "analysis_jobs"


def test_analysis_job_has_required_columns():
    cols = {c.name for c in AnalysisJob.__table__.columns}
    assert {
        "id",
        "tenant_id",
        "agent_id",
        "conversation_id",
        "status",
        "job_type",
        "source_type",
        "connection_id",
        "query",
        "analysis_spec",
        "result_summary",
        "write_log",
        "rows_processed",
        "error",
        "started_at",
        "completed_at",
        "created_at",
    }.issubset(cols)
