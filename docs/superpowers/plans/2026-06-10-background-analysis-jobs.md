# Background Analysis Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an agent's database query is flagged as `background=true`, defer it to a Celery task that posts the result back as an assistant message in the same conversation via WebSocket.

**Architecture:** Add a deferral path to the existing `internal_query_database_wrapper` in `adk_tools.py`. When triggered, the wrapper creates an `AnalysisJob` row and queues a Celery task. The task runs the query using existing connectors, saves the result via `ChatService.save_assistant_message`, and pushes a `analysis_job_completed` WebSocket event to the conversation room. No changes to existing inline query behavior.

**Tech Stack:** SQLAlchemy (async + sync), Alembic, Celery, FastAPI, `create_celery_async_session()` for DB access in tasks, `connection_manager.send_to_room()` for WebSocket delivery.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `api/src/models/analysis_job.py` | `AnalysisJob` model + `JobStatus` / `JobType` enums |
| Modify | `api/src/models/__init__.py` | Export new model + enums |
| Create | `api/migrations/versions/20260610_0001_add_analysis_jobs.py` | Create `analysis_jobs` table |
| Create | `api/src/schemas/analysis_job.py` | Pydantic response schemas |
| Create | `api/src/tasks/analysis_tasks.py` | Celery task: run query → save message → push WS |
| Modify | `api/src/services/agents/adk_tools.py` | Deferral check in `internal_query_database_wrapper` |
| Create | `api/src/controllers/agents/analysis.py` | `GET /analysis-jobs` and `GET /analysis-jobs/{id}` |
| Modify | `api/src/router_registry.py` | Register analysis controller |
| Create | `api/tests/unit/models/test_analysis_job.py` | Model unit tests |
| Create | `api/tests/unit/tasks/test_analysis_tasks.py` | Task unit tests |
| Create | `api/tests/unit/controllers/test_analysis_controller.py` | Controller unit tests |

---

## Task 1: AnalysisJob Model

**Files:**
- Create: `api/src/models/analysis_job.py`
- Modify: `api/src/models/__init__.py`

- [ ] **Step 1: Write failing test**

```python
# api/tests/unit/models/test_analysis_job.py
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
    assert {"id", "tenant_id", "agent_id", "conversation_id", "status",
            "job_type", "source_type", "connection_id", "query",
            "analysis_spec", "result_summary", "write_log",
            "rows_processed", "error", "started_at", "completed_at",
            "created_at"}.issubset(cols)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd api && pytest tests/unit/models/test_analysis_job.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.models.analysis_job'`

- [ ] **Step 3: Create the model**

```python
# api/src/models/analysis_job.py
"""AnalysisJob model — tracks background database query/write jobs."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.models.base import BaseModel, TenantMixin


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(str, enum.Enum):
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
```

- [ ] **Step 4: Export from `__init__.py`**

Add after the `from .agent_approval import ...` line in `api/src/models/__init__.py`:

```python
from .analysis_job import AnalysisJob, JobStatus, JobType
```

- [ ] **Step 5: Run test to confirm it passes**

```bash
cd api && pytest tests/unit/models/test_analysis_job.py -v
```

Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
cd api && git add src/models/analysis_job.py src/models/__init__.py tests/unit/models/test_analysis_job.py
git commit -m "feat: add AnalysisJob model with JobStatus/JobType enums"
```

---

## Task 2: Alembic Migration

**Files:**
- Create: `api/migrations/versions/20260610_0001_add_analysis_jobs.py`

- [ ] **Step 1: Find the latest revision ID**

```bash
cd api && python -c "
import re, pathlib
files = sorted(pathlib.Path('migrations/versions').glob('*.py'))
for f in files[-3:]:
    m = re.search(r'revision = \"(.+?)\"', f.read_text())
    if m: print(f.name, '->', m.group(1))
"
```

Note the revision ID from the last file — you'll use it as `down_revision`.

- [ ] **Step 2: Create the migration file**

Replace `<LAST_REVISION>` with the value from step 1:

```python
# api/migrations/versions/20260610_0001_add_analysis_jobs.py
"""Add analysis_jobs table for background query jobs

Revision ID: 20260610_0001
Revises: <LAST_REVISION>
Create Date: 2026-06-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260610_0001"
down_revision = "<LAST_REVISION>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("job_type", sa.String(10), nullable=False, server_default="read"),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("query", sa.Text, nullable=True),
        sa.Column("analysis_spec", postgresql.JSONB, nullable=True,
                  server_default=sa.text("'{}'")),
        sa.Column("result_summary", postgresql.JSONB, nullable=True),
        sa.Column("write_log", postgresql.JSONB, nullable=True),
        sa.Column("rows_processed", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_analysis_jobs_tenant_id", "analysis_jobs", ["tenant_id"])
    op.create_index("ix_analysis_jobs_conversation_id", "analysis_jobs", ["conversation_id"])
    op.create_index(
        "ix_analysis_jobs_status_active",
        "analysis_jobs",
        ["status"],
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_jobs_status_active", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_conversation_id", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_tenant_id", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
```

- [ ] **Step 3: Apply migration**

```bash
cd api && alembic upgrade head
```

Expected: Migration runs without error.

- [ ] **Step 4: Verify table exists**

```bash
cd api && python -c "
from src.core.database import get_db
db = next(get_db())
result = db.execute(__import__('sqlalchemy').text(\"SELECT COUNT(*) FROM analysis_jobs\"))
print('analysis_jobs row count:', result.scalar())
db.close()
"
```

Expected: `analysis_jobs row count: 0`

- [ ] **Step 5: Commit**

```bash
cd api && git add migrations/versions/20260610_0001_add_analysis_jobs.py
git commit -m "feat: add analysis_jobs migration"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `api/src/schemas/analysis_job.py`

- [ ] **Step 1: Create the schemas file**

```python
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
```

- [ ] **Step 2: Verify schemas import cleanly**

```bash
cd api && python -c "from src.schemas.analysis_job import AnalysisJobListItem, AnalysisJobDetail; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd api && git add src/schemas/analysis_job.py
git commit -m "feat: add AnalysisJob Pydantic schemas"
```

---

## Task 4: Celery Task

**Files:**
- Create: `api/src/tasks/analysis_tasks.py`
- Create: `api/tests/unit/tasks/test_analysis_tasks.py`

- [ ] **Step 1: Write failing tests**

```python
# api/tests/unit/tasks/test_analysis_tasks.py
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


def test_run_analysis_job_marks_running_then_completed(mock_job):
    """Task transitions job from pending → running → completed."""
    query_result = {
        "success": True,
        "rows": [{"status": "active", "count": 42}],
        "row_count": 1,
        "columns": ["status", "count"],
    }

    with (
        patch("src.tasks.analysis_tasks._load_job", return_value=mock_job),
        patch("src.tasks.analysis_tasks._execute_job_query", new_callable=AsyncMock, return_value=query_result),
        patch("src.tasks.analysis_tasks._save_result_as_message", new_callable=AsyncMock),
        patch("src.tasks.analysis_tasks._notify_conversation", new_callable=AsyncMock),
        patch("src.tasks.analysis_tasks._persist_job", new_callable=AsyncMock),
    ):
        from src.tasks.analysis_tasks import run_analysis_job
        run_analysis_job(str(mock_job.id))

    assert mock_job.status == JobStatus.COMPLETED
    assert mock_job.rows_processed == 1
    assert mock_job.result_summary is not None
    assert mock_job.completed_at is not None


def test_run_analysis_job_marks_failed_on_error(mock_job):
    """Task marks job as failed and saves error message when query throws."""

    with (
        patch("src.tasks.analysis_tasks._load_job", return_value=mock_job),
        patch("src.tasks.analysis_tasks._execute_job_query", new_callable=AsyncMock,
              side_effect=Exception("connection refused")),
        patch("src.tasks.analysis_tasks._save_result_as_message", new_callable=AsyncMock),
        patch("src.tasks.analysis_tasks._notify_conversation", new_callable=AsyncMock),
        patch("src.tasks.analysis_tasks._persist_job", new_callable=AsyncMock),
    ):
        from src.tasks.analysis_tasks import run_analysis_job
        run_analysis_job(str(mock_job.id))

    assert mock_job.status == JobStatus.FAILED
    assert "connection refused" in mock_job.error
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd api && pytest tests/unit/tasks/test_analysis_tasks.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.tasks.analysis_tasks'`

- [ ] **Step 3: Create the Celery task**

```python
# api/src/tasks/analysis_tasks.py
"""Background task: execute deferred database query and post result to conversation."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.celery_app import celery_app
from src.core.database import create_celery_async_session, get_db
from src.models.analysis_job import AnalysisJob, JobStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers — each does one thing, easy to test independently
# ---------------------------------------------------------------------------


def _load_job(job_id: str, db: Session) -> AnalysisJob | None:
    return db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()


async def _execute_job_query(job: AnalysisJob) -> dict[str, Any]:
    """Run the stored query against the data source and return raw result dict."""
    from src.core.database import create_celery_async_session
    from src.models.database_connection import DatabaseConnection
    from src.services.agents.internal_tools.database_tools import (
        _get_or_create_connector,
        _truncate_rows_for_llm,
    )

    async_session_factory = create_celery_async_session()
    async with async_session_factory() as db:
        from sqlalchemy import select

        stmt = select(DatabaseConnection).where(
            DatabaseConnection.id == job.connection_id,
            DatabaseConnection.tenant_id == job.tenant_id,
        )
        result = await db.execute(stmt)
        connection = result.scalar_one_or_none()

    if not connection:
        return {"success": False, "error": f"Connection {job.connection_id} not found"}

    connector = await _get_or_create_connector(connection)
    if not connector:
        return {"success": False, "error": f"Unsupported database type: {connection.database_type}"}

    raw = await connector.execute_query(job.query)
    rows = raw.get("rows", [])
    total = len(rows)
    trimmed, note = _truncate_rows_for_llm(rows, total)

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


async def _persist_job(job: AnalysisJob, db: Session) -> None:
    """Flush job state changes to the database (sync session passed from task)."""
    db.add(job)
    db.commit()


def _format_result_content(job: AnalysisJob, query_result: dict[str, Any]) -> str:
    """Turn raw query result into a human-readable assistant message."""
    if not query_result.get("success", True) and query_result.get("error"):
        return f"Background analysis failed: {query_result['error']}"

    rows = query_result.get("rows", [])
    row_count = query_result.get("row_count", len(rows))
    note = query_result.get("truncation_note", "")

    lines = [f"**Background analysis complete** ({row_count:,} rows processed)\n"]
    if rows:
        # Show first 20 rows as a simple table summary
        cols = list(rows[0].keys()) if rows else []
        if cols:
            lines.append(" | ".join(cols))
            lines.append(" | ".join(["---"] * len(cols)))
            for row in rows[:20]:
                lines.append(" | ".join(str(row.get(c, "")) for c in cols))
    if note:
        lines.append(f"\n_{note}_")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Celery task entry point
# ---------------------------------------------------------------------------


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
                    "rows": query_result.get("rows", [])[:50],  # Keep max 50 rows
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

    asyncio.run(_run())

    db.add(job)
    db.commit()
    db.close()

    return {"status": job.status.value, "job_id": job_id}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd api && pytest tests/unit/tasks/test_analysis_tasks.py -v
```

Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
cd api && git add src/tasks/analysis_tasks.py tests/unit/tasks/test_analysis_tasks.py
git commit -m "feat: add run_analysis_job Celery task"
```

---

## Task 5: Deferral in the DB Tool Wrapper

**Files:**
- Modify: `api/src/services/agents/adk_tools.py` (around line 793)

- [ ] **Step 1: Write failing test**

```python
# api/tests/unit/services/test_adk_deferral.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_background_flag_creates_job_and_returns_deferred():
    """When config contains background=True, wrapper creates job and returns deferred response."""
    runtime_ctx = MagicMock()
    runtime_ctx.tenant_id = uuid.uuid4()
    runtime_ctx.agent_id = uuid.uuid4()
    runtime_ctx.conversation_id = uuid.uuid4()
    runtime_ctx.user_id = uuid.uuid4()
    db_mock = AsyncMock()
    runtime_ctx.db_session = db_mock
    runtime_ctx.allowed_database_connections = ["conn-123"]

    config = {
        "_runtime_context": runtime_ctx,
        "background": True,
    }

    mock_job_id = uuid.uuid4()

    with (
        patch("src.services.agents.adk_tools._create_analysis_job",
              new_callable=AsyncMock, return_value=mock_job_id),
        patch("src.celery_app.celery_app.send_task") as mock_send,
    ):
        from src.services.agents.adk_tools import _maybe_defer_to_background

        result = await _maybe_defer_to_background(
            connection_id="conn-123",
            query="SELECT status, COUNT(*) FROM logs GROUP BY status",
            config=config,
            tenant_id=str(runtime_ctx.tenant_id),
            db_session=db_mock,
        )

    assert result["deferred"] is True
    assert str(mock_job_id) in result["message"]
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_no_background_flag_returns_none():
    """Without background=True, _maybe_defer_to_background returns None (run inline)."""
    config = {"_runtime_context": MagicMock(), "background": False}

    from src.services.agents.adk_tools import _maybe_defer_to_background

    result = await _maybe_defer_to_background(
        connection_id="conn-123",
        query="SELECT 1",
        config=config,
        tenant_id="tenant-1",
        db_session=AsyncMock(),
    )

    assert result is None
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd api && pytest tests/unit/services/test_adk_deferral.py -v
```

Expected: `ImportError: cannot import name '_maybe_defer_to_background'`

- [ ] **Step 3: Add `_create_analysis_job` and `_maybe_defer_to_background` helpers to `adk_tools.py`**

Add these two functions near the top of `adk_tools.py`, after the imports section (before the `ADKToolRegistry` class definition):

```python
async def _create_analysis_job(
    tenant_id: str,
    agent_id: str,
    conversation_id: str,
    connection_id: str,
    query: str,
    source_type: str,
    db_session,
) -> "uuid.UUID":
    """Insert an AnalysisJob row and return its id."""
    import uuid as _uuid
    from datetime import UTC, datetime

    from src.models.analysis_job import AnalysisJob, JobStatus, JobType

    job = AnalysisJob(
        tenant_id=_uuid.UUID(str(tenant_id)),
        agent_id=_uuid.UUID(str(agent_id)),
        conversation_id=_uuid.UUID(str(conversation_id)),
        connection_id=_uuid.UUID(str(connection_id)) if connection_id else None,
        status=JobStatus.PENDING,
        job_type=JobType.READ,
        source_type=source_type.upper() if source_type else None,
        query=query,
        analysis_spec={},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job.id


async def _maybe_defer_to_background(
    connection_id: str,
    query: str,
    config: dict,
    tenant_id: str,
    db_session,
) -> dict | None:
    """
    Check if this query should be deferred to a background job.

    Returns a deferred-response dict if background=True in config,
    or None if the query should run inline.
    """
    if not config or not config.get("background"):
        return None

    runtime_context = config.get("_runtime_context")
    if not runtime_context:
        return None

    agent_id = getattr(runtime_context, "agent_id", None)
    conversation_id = getattr(runtime_context, "conversation_id", None)

    if not agent_id or not conversation_id:
        logger.warning("[DB Tool] background=True but missing agent_id or conversation_id — running inline")
        return None

    # Determine source type from the connection
    source_type = "UNKNOWN"
    try:
        from sqlalchemy import select

        from src.models.database_connection import DatabaseConnection

        stmt = select(DatabaseConnection.database_type).where(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.tenant_id == tenant_id,
        )
        result = await db_session.execute(stmt)
        db_type = result.scalar_one_or_none()
        if db_type:
            source_type = str(db_type).upper()
    except Exception:
        pass

    job_id = await _create_analysis_job(
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        conversation_id=str(conversation_id),
        connection_id=connection_id,
        query=query,
        source_type=source_type,
        db_session=db_session,
    )

    from src.celery_app import celery_app as _celery_app

    _celery_app.send_task("tasks.run_analysis_job", args=[str(job_id)])

    logger.info("[DB Tool] Deferred query to background job %s (conversation=%s)", job_id, conversation_id)

    return {
        "success": True,
        "deferred": True,
        "job_id": str(job_id),
        "message": (
            f"This analysis is running in the background (job {job_id}). "
            "I'll post the results here when it's ready."
        ),
    }
```

- [ ] **Step 4: Call `_maybe_defer_to_background` in `internal_query_database_wrapper`**

In `adk_tools.py`, find `internal_query_database_wrapper` (around line 793). Add the deferral call right before the `return await internal_query_database(...)` line:

```python
            # Background deferral: if config["background"] is True, queue a job
            deferred = await _maybe_defer_to_background(
                connection_id=connection_id,
                query=query,
                config=config,
                tenant_id=str(tenant_id),
                db_session=db_session,
            )
            if deferred is not None:
                return deferred

            return await internal_query_database(
                connection_id=connection_id, query=query, tenant_id=tenant_id, db_session=db_session, config=config
            )
```

- [ ] **Step 5: Run tests**

```bash
cd api && pytest tests/unit/services/test_adk_deferral.py -v
```

Expected: 2 PASSED

- [ ] **Step 6: Commit**

```bash
cd api && git add src/services/agents/adk_tools.py tests/unit/services/test_adk_deferral.py
git commit -m "feat: add background deferral to internal_query_database_wrapper"
```

---

## Task 6: REST Controller

**Files:**
- Create: `api/src/controllers/agents/analysis.py`
- Modify: `api/src/router_registry.py`
- Create: `api/tests/unit/controllers/test_analysis_controller.py`

- [ ] **Step 1: Write failing tests**

```python
# api/tests/unit/controllers/test_analysis_controller.py
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.controllers.agents.analysis import router
from src.models.analysis_job import AnalysisJob, JobStatus, JobType

app = FastAPI()
app.include_router(router)


def _make_job(conversation_id):
    job = MagicMock(spec=AnalysisJob)
    job.id = uuid.uuid4()
    job.status = JobStatus.COMPLETED
    job.job_type = JobType.READ
    job.source_type = "POSTGRESQL"
    job.conversation_id = conversation_id
    job.rows_processed = 10
    job.error = None
    job.query = "SELECT 1"
    job.analysis_spec = {}
    job.result_summary = {"rows": [], "row_count": 10}
    job.write_log = None
    job.started_at = None
    job.completed_at = None
    job.created_at = MagicMock()
    return job


@pytest.mark.asyncio
async def test_list_analysis_jobs_returns_200():
    conversation_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    jobs = [_make_job(conversation_id)]

    with (
        patch("src.controllers.agents.analysis.get_current_tenant_id", return_value=tenant_id),
        patch("src.controllers.agents.analysis._get_agent", new_callable=AsyncMock,
              return_value=MagicMock(id=agent_id)),
        patch("src.controllers.agents.analysis._list_jobs", new_callable=AsyncMock, return_value=jobs),
        patch("src.core.database.get_async_db", return_value=AsyncMock()),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                f"/agents/my-agent/analysis-jobs?conversation_id={conversation_id}"
            )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd api && pytest tests/unit/controllers/test_analysis_controller.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.controllers.agents.analysis'`

- [ ] **Step 3: Create the controller**

```python
# api/src/controllers/agents/analysis.py
"""
Analysis Job endpoints.

GET /agents/{agent_slug}/analysis-jobs               — list jobs for a conversation
GET /agents/{agent_slug}/analysis-jobs/{job_id}      — job detail + result
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.analysis_job import AnalysisJob
from src.schemas.analysis_job import AnalysisJobDetail, AnalysisJobListItem

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_JOBS = 50


async def _get_agent(agent_slug: str, tenant_id: UUID, db: AsyncSession) -> Agent:
    result = await db.execute(
        select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


async def _list_jobs(
    tenant_id: UUID, agent_id: UUID, conversation_id: UUID | None, db: AsyncSession
) -> list[AnalysisJob]:
    stmt = (
        select(AnalysisJob)
        .where(AnalysisJob.tenant_id == tenant_id, AnalysisJob.agent_id == agent_id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(_MAX_JOBS)
    )
    if conversation_id:
        stmt = stmt.where(AnalysisJob.conversation_id == conversation_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{agent_slug}/analysis-jobs", response_model=list[AnalysisJobListItem])
async def list_analysis_jobs(
    agent_slug: str,
    conversation_id: UUID | None = Query(default=None),
    tenant_id: UUID = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    agent = await _get_agent(agent_slug, tenant_id, db)
    jobs = await _list_jobs(tenant_id, agent.id, conversation_id, db)
    return [AnalysisJobListItem.model_validate(j) for j in jobs]


@router.get("/{agent_slug}/analysis-jobs/{job_id}", response_model=AnalysisJobDetail)
async def get_analysis_job(
    agent_slug: str,
    job_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    agent = await _get_agent(agent_slug, tenant_id, db)
    result = await db.execute(
        select(AnalysisJob).where(
            AnalysisJob.id == job_id,
            AnalysisJob.tenant_id == tenant_id,
            AnalysisJob.agent_id == agent.id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis job not found")
    return AnalysisJobDetail.model_validate(job)
```

- [ ] **Step 4: Register the router in `router_registry.py`**

In `api/src/router_registry.py`, find the block that registers `src.controllers.agents.autonomous_agents` (around line 116) and add the analysis router right after it:

```python
    RouteConfig(
        module="src.controllers.agents.analysis",
        attribute="router",
        prefix="/api/v1/agents",
        tags=["analysis-jobs"],
    ),
```

- [ ] **Step 5: Run tests**

```bash
cd api && pytest tests/unit/controllers/test_analysis_controller.py -v
```

Expected: 1 PASSED

- [ ] **Step 6: Commit**

```bash
cd api && git add src/controllers/agents/analysis.py src/router_registry.py tests/unit/controllers/test_analysis_controller.py
git commit -m "feat: add analysis-jobs REST endpoints and router registration"
```

---

## Task 7: Register Task with Celery + Smoke Test

**Files:**
- Modify: `api/src/celery_app.py` (include new task module)

- [ ] **Step 1: Check current task autodiscovery config in `celery_app.py`**

```bash
cd api && grep -n "include\|autodiscover\|analysis" src/celery_app.py | head -20
```

- [ ] **Step 2: Add `src.tasks.analysis_tasks` to the include list**

Find the `include=[...]` or `autodiscover_tasks([...])` list in `api/src/celery_app.py` and add:

```python
"src.tasks.analysis_tasks",
```

- [ ] **Step 3: Verify the task is discoverable**

```bash
cd api && python -c "
from src.celery_app import celery_app
celery_app.loader.import_default_modules()
print('registered tasks with analysis:')
for name in sorted(celery_app.tasks):
    if 'analysis' in name:
        print(' ', name)
"
```

Expected output includes: `tasks.run_analysis_job`

- [ ] **Step 4: Verify full test suite still passes**

```bash
cd api && pytest tests/unit/ -v --tb=short -q
```

Expected: All previously passing tests still pass, new tests pass.

- [ ] **Step 5: Commit**

```bash
cd api && git add src/celery_app.py
git commit -m "feat: register analysis_tasks with Celery autodiscovery"
```

---

## Usage Reference

### How an agent triggers a background job

The agent calls `internal_query_database` with `background: true` in the tool config:

```json
{
  "connection_id": "abc-123",
  "query": "SELECT zone, SUM(revenue) as total FROM trips WHERE date > '2026-01-01' GROUP BY zone ORDER BY total DESC",
  "config": {
    "background": true
  }
}
```

The tool returns immediately:
```json
{
  "success": true,
  "deferred": true,
  "job_id": "550e8400-...",
  "message": "This analysis is running in the background (job 550e8400-...). I'll post the results here when it's ready."
}
```

The agent streams this message to the user. When the Celery worker finishes, a new assistant message appears in the conversation automatically.

### How to check job status via API

```
GET /api/v1/agents/{agent_slug}/analysis-jobs?conversation_id={conv_id}
GET /api/v1/agents/{agent_slug}/analysis-jobs/{job_id}
```
