import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.analysis_job import AnalysisJob, JobStatus


@pytest.fixture
def mock_job():
    job = MagicMock(spec=AnalysisJob)
    job.id = uuid.uuid4()
    job.tenant_id = uuid.uuid4()
    job.agent_id = uuid.uuid4()
    job.conversation_id = uuid.uuid4()
    job.connection_id = uuid.uuid4()
    job.query = "SELECT status, COUNT(*) FROM vehicles GROUP BY status"
    job.source_type = "POSTGRESQL"
    job.status = JobStatus.PENDING
    return job


def _make_mock_db(mock_job):
    """Return a MagicMock db session whose add/commit/close do nothing."""
    mock_db = MagicMock()
    mock_db.add = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.close = MagicMock()
    return mock_db


def test_run_analysis_job_marks_completed(mock_job):
    query_result = {
        "success": True,
        "rows": [{"status": "active", "count": 42}],
        "row_count": 1,
        "columns": ["status", "count"],
    }
    mock_db = _make_mock_db(mock_job)

    with (
        patch("src.tasks.analysis_tasks._load_job", return_value=mock_job),
        patch("src.tasks.analysis_tasks._execute_job_query", new_callable=AsyncMock, return_value=query_result),
        patch("src.tasks.analysis_tasks._save_result_as_message", new_callable=AsyncMock),
        patch("src.tasks.analysis_tasks._notify_conversation", new_callable=AsyncMock),
        # patch the name as imported inside the task module
        patch("src.tasks.analysis_tasks.get_db", return_value=iter([mock_db])),
    ):
        from src.tasks.analysis_tasks import run_analysis_job

        run_analysis_job(str(mock_job.id))

    assert mock_job.status == JobStatus.COMPLETED
    assert mock_job.rows_processed == 1
    assert mock_job.result_summary is not None
    assert mock_job.completed_at is not None
    mock_db.commit.assert_called()
    mock_db.close.assert_called_once()


def test_run_analysis_job_marks_failed_on_error(mock_job):
    mock_db = _make_mock_db(mock_job)

    with (
        patch("src.tasks.analysis_tasks._load_job", return_value=mock_job),
        patch(
            "src.tasks.analysis_tasks._execute_job_query",
            new_callable=AsyncMock,
            side_effect=Exception("connection refused"),
        ),
        patch("src.tasks.analysis_tasks._save_result_as_message", new_callable=AsyncMock),
        patch("src.tasks.analysis_tasks._notify_conversation", new_callable=AsyncMock),
        patch("src.tasks.analysis_tasks.get_db", return_value=iter([mock_db])),
    ):
        from src.tasks.analysis_tasks import run_analysis_job

        run_analysis_job(str(mock_job.id))

    assert mock_job.status == JobStatus.FAILED
    assert "connection refused" in mock_job.error
    mock_db.commit.assert_called()
    mock_db.close.assert_called_once()


def test_format_result_content_success(mock_job):
    from src.tasks.analysis_tasks import _format_result_content

    result = _format_result_content(
        mock_job,
        {
            "success": True,
            "rows": [{"zone": "A", "revenue": 1000}],
            "row_count": 1,
            "columns": ["zone", "revenue"],
        },
    )

    assert "Background analysis complete" in result
    assert "1" in result  # row count


def test_format_result_content_failure(mock_job):
    from src.tasks.analysis_tasks import _format_result_content

    result = _format_result_content(
        mock_job,
        {
            "success": False,
            "error": "timeout after 30s",
        },
    )

    assert "failed" in result.lower()
    assert "timeout" in result
