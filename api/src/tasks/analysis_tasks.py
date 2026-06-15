"""Background task: execute deferred database query and post result to conversation."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from src.celery_app import celery_app
from src.core.database import get_db
from src.models.analysis_job import AnalysisJob, JobStatus

logger = logging.getLogger(__name__)


def _load_job(job_id: str, db: Session) -> AnalysisJob | None:
    return db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()


async def _execute_job_query(job: AnalysisJob) -> dict[str, Any]:
    """Run the stored query against the data source using the same per-source
    execution functions as internal_query_database."""
    from sqlalchemy import select

    from src.core.database import create_celery_async_session
    from src.models.database_connection import DatabaseConnection
    from src.services.agents.internal_tools.database_tools import (
        _execute_elasticsearch_query,
        _execute_generic_query,
        _execute_postgresql_query,
        _execute_sqlite_query,
        _truncate_rows_for_llm,
    )

    async_session_factory = create_celery_async_session()
    async with async_session_factory() as db:
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.id == job.connection_id,
            DatabaseConnection.tenant_id == job.tenant_id,
        )
        result = await db.execute(stmt)
        connection = result.scalar_one_or_none()

    if not connection:
        return {"success": False, "error": f"Connection {job.connection_id} not found"}

    db_type = str(connection.database_type).upper()

    if db_type == "POSTGRESQL":
        raw = await _execute_postgresql_query(connection, job.query)
    elif db_type == "ELASTICSEARCH":
        raw = await _execute_elasticsearch_query(connection, job.query)
    elif db_type == "SQLITE":
        raw = await _execute_sqlite_query(connection, job.query)
    elif db_type in (
        "MYSQL",
        "MONGODB",
        "SUPABASE",
        "BIGQUERY",
        "SNOWFLAKE",
        "SQLSERVER",
        "CLICKHOUSE",
        "DUCKDB",
        "DATADOG",
        "DATABRICKS",
        "DOCKER",
    ):
        raw = await _execute_generic_query(connection, job.query)
    else:
        return {"success": False, "error": f"Unsupported database type: {db_type}"}

    # Normalise row field — ES returns 'data', SQL returns 'rows'
    rows = raw.get("rows") or raw.get("data") or []
    total = raw.get("row_count") or raw.get("total_hits") or len(rows)
    trimmed, note = _truncate_rows_for_llm(rows, len(rows))

    result_dict = {**raw, "rows": trimmed, "row_count": total}
    if note:
        result_dict["truncation_note"] = note
    return result_dict


async def _save_result_as_message(job: AnalysisJob, content: str) -> None:
    """Save the analysis result as an assistant message in the conversation."""
    from src.core.database import create_celery_async_session
    from src.services.agents.chat_service import ChatService

    async_session_factory = create_celery_async_session()
    async with async_session_factory() as db:
        await ChatService.save_assistant_message(
            conversation_id=job.conversation_id,
            content=content,
            db=db,
        )


async def _notify_conversation(job: AnalysisJob) -> None:
    """Push a WebSocket event so the UI refreshes the conversation."""
    try:
        from src.core.websocket import connection_manager

        await connection_manager.send_to_room(
            f"conversation:{job.conversation_id}",
            {
                "type": "analysis_job_completed",
                "data": {
                    "job_id": str(job.id),
                    "conversation_id": str(job.conversation_id),
                    "status": job.status.value,
                },
            },
        )
    except Exception as e:
        # WS delivery is best-effort — do not fail the task over it
        logger.warning("WebSocket notify failed for job %s: %s", job.id, e)


def _cell(value: Any, max_len: int = 120) -> str:
    """Render a table cell value: truncate long strings, flatten nested objects."""
    import json as _json

    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        try:
            text = _json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
    else:
        text = str(value)
    # Escape markdown table delimiters and strip newlines
    text = text.replace("|", "\\|").replace("\n", " ").replace("\r", "")
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return text


def _format_result_content(job: AnalysisJob, query_result: dict[str, Any]) -> str:
    """Turn raw query result into a human-readable assistant message."""
    if not query_result.get("success", True) and query_result.get("error"):
        return f"Background analysis failed: {query_result['error']}"

    rows = query_result.get("rows", [])
    row_count = query_result.get("row_count", len(rows))
    note = query_result.get("truncation_note", "")

    lines = [f"**Background analysis complete** ({row_count:,} rows processed)\n"]
    if rows:
        cols = list(rows[0].keys()) if rows else []
        if cols:
            lines.append(" | ".join(cols))
            lines.append(" | ".join(["---"] * len(cols)))
            for row in rows[:20]:
                lines.append(" | ".join(_cell(row.get(c)) for c in cols))
    if note:
        lines.append(f"\n_{note}_")
    return "\n".join(lines)


@celery_app.task(
    bind=True,
    name="tasks.run_analysis_job",
    max_retries=0,
    soft_time_limit=3300,
    time_limit=3600,
)
def run_analysis_job(self, job_id: str) -> dict[str, Any]:
    """
    Execute a deferred database analysis job.

    Loads the AnalysisJob, runs the query against the data source,
    saves the result as an assistant message, and pushes a WebSocket event.
    """
    db: Session = next(get_db())
    job = _load_job(job_id, db)

    if not job:
        logger.error("AnalysisJob %s not found", job_id)
        db.close()
        return {"status": "error", "reason": "job not found"}

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    db.add(job)
    db.commit()

    async def _run():
        try:
            query_result = await _execute_job_query(job)
            content = _format_result_content(job, query_result)

            if query_result.get("success", True) and not query_result.get("error"):
                job.status = JobStatus.COMPLETED
                job.rows_processed = query_result.get("row_count", 0)
                job.result_summary = {
                    "rows": query_result.get("rows", [])[:50],
                    "row_count": query_result.get("row_count", 0),
                    "columns": query_result.get("columns", []),
                }
            else:
                job.status = JobStatus.FAILED
                job.error = query_result.get("error", "Unknown error")

            job.completed_at = datetime.now(UTC)

            await _save_result_as_message(job, content)
            await _notify_conversation(job)

        except Exception as exc:
            logger.exception("AnalysisJob %s failed: %s", job_id, exc)
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.completed_at = datetime.now(UTC)

            error_content = f"Background analysis encountered an error: {exc}"
            try:
                await _save_result_as_message(job, error_content)
                await _notify_conversation(job)
            except Exception:
                pass

    # Clear the connector cache before starting a new event loop — cached async
    # connectors from a previous asyncio.run() call hold references to a closed
    # event loop and will raise "Event loop is closed" on reuse.
    try:
        from src.services.agents.internal_tools.database_tools import _connector_cache

        _connector_cache.clear()
    except Exception:
        pass

    asyncio.run(_run())

    db.add(job)
    db.commit()
    db.close()

    return {"status": job.status.value, "job_id": job_id}
