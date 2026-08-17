# Data Source Auto-Sync Scheduling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `sync_frequency_minutes` actually mean something by wiring the existing-but-dead `sync_all_data_sources_task` into Celery beat, filtered so it only dispatches syncs for data sources whose interval has actually elapsed.

**Architecture:** `sync_all_data_sources_task` (`api/src/tasks/data_source_tasks.py`) already exists and already does the right per-source dispatch (`sync_data_source_task.delay(...)` after creating a `DataSourceSyncJob` row) — it is simply never scheduled and dispatches unconditionally for every `ACTIVE` source regardless of how recently it last synced. This plan adds (1) due-time filtering to `_dispatch_all_syncs()` and (2) a `beat_schedule` entry so the task actually runs.

**Tech Stack:** Celery beat, SQLAlchemy async, pytest + unittest.mock (no DB needed — existing test file mocks `asyncio.run`).

---

## Context (verified, no placeholders)

- `api/src/tasks/data_source_tasks.py` (152 lines, read in full):
  - `sync_all_data_sources_task(tenant_id: str | None = None) -> dict[str, Any]` (`@celery_app.task(name="sync_all_data_sources_task")`) calls `asyncio.run(_dispatch_all_syncs(tenant_id))`.
  - `_dispatch_all_syncs(tenant_id: str | None) -> dict[str, Any]` currently queries `select(DataSource).where(DataSource.status == DataSourceStatus.ACTIVE)` with no `sync_enabled`/timing filter, then for every row creates a `DataSourceSyncJob(data_source_id=ds.id, tenant_id=ds.tenant_id, status=SyncStatus.IN_PROGRESS, started_at=datetime.now(UTC))`, flushes it to get `sync_job.id`, and calls `sync_data_source_task.delay(data_source_id=ds.id, sync_job_id=sync_job.id, full_sync=False)`.
  - Zero references to this task exist in `api/src/celery_app.py`'s `beat_schedule` or `task_routes` — confirmed via grep. It is unreachable except by manual invocation today.
- `api/src/models/data_source.py` (`DataSource(BaseModel, TimestampMixin)`, no `SoftDeleteMixin`/`deleted_at`):
  - `sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)`
  - `sync_frequency_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)`
  - `last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)` — **timezone-aware**, so comparisons against `datetime.now(UTC)` work directly, no naive/aware mismatch.
- `api/src/celery_app.py`:
  - No dedicated queue for data-source sync tasks exists or is needed — `sync_data_source_task`/`sync_all_data_sources_task` have no `task_routes` entry today, so they already fall through to `task_default_queue="default"`, handled by the always-running `celery-worker` container (`docker-compose.yml:489`, `-Q default`). No new queue/worker needed.
  - `beat_schedule` dict entries follow this exact shape (e.g. `api/src/celery_app.py:187-191`):
    ```python
    "company-brain-consume-active-streams": {
        "task": "company_brain_consume_active_streams_task",
        "schedule": 30.0,
    },
    ```
- `api/tests/unit/tasks/test_data_source_tasks.py` (104 lines, read in full) — existing test conventions: mocks `asyncio.run` entirely via `@patch("src.tasks.data_source_tasks.asyncio.run")`, never touches a real DB. New tests for `_dispatch_all_syncs()`'s filtering logic must instead call `_dispatch_all_syncs()` directly (it's an importable async function) with a mocked `create_celery_async_session`.

## Task 1: Add due-time filtering to `_dispatch_all_syncs()`

**Files:**
- Modify: `api/src/tasks/data_source_tasks.py`
- Test: `api/tests/unit/tasks/test_data_source_tasks.py`

- [ ] **Step 1: Write the failing tests**

Add this new test class to the end of `api/tests/unit/tasks/test_data_source_tasks.py` (after the existing `TestSyncAllDataSourcesTaskExecution` class):

```python
class TestDispatchAllSyncsFiltering:
    """Tests for _dispatch_all_syncs() due-time filtering logic."""

    def _make_ds(self, ds_id, sync_enabled=True, sync_frequency_minutes=60, last_sync_at=None):
        from src.models.data_source import DataSourceStatus, DataSourceType

        ds = MagicMock()
        ds.id = ds_id
        ds.tenant_id = uuid4()
        ds.type = DataSourceType.SLACK
        ds.status = DataSourceStatus.ACTIVE
        ds.sync_enabled = sync_enabled
        ds.sync_frequency_minutes = sync_frequency_minutes
        ds.last_sync_at = last_sync_at
        return ds

    @pytest.mark.asyncio
    async def test_dispatches_source_never_synced(self):
        """A source with last_sync_at=None (never synced) is always due."""
        from src.tasks.data_source_tasks import _dispatch_all_syncs

        ds = self._make_ds(1, last_sync_at=None)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ds]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        def mock_add(job):
            job.id = 100

        mock_db.add = MagicMock(side_effect=mock_add)

        mock_session_factory = MagicMock(return_value=mock_db)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("src.core.database.create_celery_async_session", return_value=mock_session_factory),
            patch("src.tasks.data_source_tasks.sync_data_source_task") as mock_task,
        ):
            result = await _dispatch_all_syncs(tenant_id=None)

        assert result == {"queued": 1, "failed": 0}
        mock_task.delay.assert_called_once_with(data_source_id=1, sync_job_id=100, full_sync=False)

    @pytest.mark.asyncio
    async def test_skips_source_synced_recently(self):
        """A source synced 10 minutes ago with a 60-minute frequency is NOT due yet."""
        from src.tasks.data_source_tasks import _dispatch_all_syncs

        ds = self._make_ds(2, sync_frequency_minutes=60, last_sync_at=datetime.now(UTC) - timedelta(minutes=10))
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ds]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_session_factory = MagicMock(return_value=mock_db)

        with (
            patch("src.core.database.create_celery_async_session", return_value=mock_session_factory),
            patch("src.tasks.data_source_tasks.sync_data_source_task") as mock_task,
        ):
            result = await _dispatch_all_syncs(tenant_id=None)

        assert result == {"queued": 0, "failed": 0}
        mock_task.delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatches_source_past_due(self):
        """A source synced 90 minutes ago with a 60-minute frequency IS due."""
        from src.tasks.data_source_tasks import _dispatch_all_syncs

        ds = self._make_ds(3, sync_frequency_minutes=60, last_sync_at=datetime.now(UTC) - timedelta(minutes=90))
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [ds]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        def mock_add(job):
            job.id = 101

        mock_db.add = MagicMock(side_effect=mock_add)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)

        mock_session_factory = MagicMock(return_value=mock_db)

        with (
            patch("src.core.database.create_celery_async_session", return_value=mock_session_factory),
            patch("src.tasks.data_source_tasks.sync_data_source_task") as mock_task,
        ):
            result = await _dispatch_all_syncs(tenant_id=None)

        assert result == {"queued": 1, "failed": 0}
        mock_task.delay.assert_called_once_with(data_source_id=3, sync_job_id=101, full_sync=False)
```

Add the required imports at the top of the test file (it currently only imports `AsyncMock, MagicMock, patch` and `uuid4`):

```python
from datetime import UTC, datetime, timedelta
```

and add `import pytest` for `pytest.mark.asyncio` (already imported at line 6 — confirm, no change needed if already present).

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/tasks/test_data_source_tasks.py -v -k TestDispatchAllSyncsFiltering`
Expected: FAIL (all 3 tests) — `_dispatch_all_syncs` doesn't yet filter by due time, so `test_skips_source_synced_recently` fails because it dispatches when it shouldn't, and the mock patch target `src.core.database.create_celery_async_session` won't yet match how the real function imports it (this confirms the test harness needs the patch target verified against the real import — see Step 3 note below).

- [ ] **Step 3: Implement due-time filtering**

Replace `_dispatch_all_syncs()` in `api/src/tasks/data_source_tasks.py` (currently lines 116-151) with:

```python
async def _dispatch_all_syncs(tenant_id: str | None) -> dict[str, Any]:
    from sqlalchemy import select

    from src.core.database import create_celery_async_session
    from src.models.data_source import DataSource, DataSourceStatus, DataSourceSyncJob, SyncStatus

    async with create_celery_async_session()() as db:
        q = select(DataSource).where(
            DataSource.status == DataSourceStatus.ACTIVE,
            DataSource.sync_enabled.is_(True),
        )
        if tenant_id:
            from uuid import UUID

            q = q.where(DataSource.tenant_id == UUID(tenant_id))
        result = await db.execute(q)
        data_sources = result.scalars().all()

        now = datetime.now(UTC)
        due_sources = [
            ds
            for ds in data_sources
            if ds.last_sync_at is None or ds.last_sync_at + timedelta(minutes=ds.sync_frequency_minutes) <= now
        ]

        queued, failed = 0, 0
        for ds in due_sources:
            try:
                sync_job = DataSourceSyncJob(
                    data_source_id=ds.id,
                    tenant_id=ds.tenant_id,
                    status=SyncStatus.IN_PROGRESS,
                    started_at=now,
                )
                db.add(sync_job)
                await db.flush()
                sync_data_source_task.delay(data_source_id=ds.id, sync_job_id=sync_job.id, full_sync=False)
                queued += 1
            except Exception as e:
                logger.error(f"Failed to queue sync for {ds.id}: {e}")
                failed += 1

        await db.commit()

    logger.info(f"Queued {queued}/{len(data_sources)} due data source syncs ({len(data_sources)} active+enabled)")
    return {"queued": queued, "failed": failed}
```

Add `timedelta` to the existing `from datetime import UTC, datetime` import at the top of the file (line 5):

```python
from datetime import UTC, datetime, timedelta
```

Since `_dispatch_all_syncs` imports `create_celery_async_session` from `src.core.database` **inside the function body** (not at module scope), the correct patch target in the tests is `src.core.database.create_celery_async_session`, matching what's already written in Step 1 — no further change needed there.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/tasks/test_data_source_tasks.py -v`
Expected: All tests PASS, including the 3 new `TestDispatchAllSyncsFiltering` tests and all pre-existing tests in the file (no regressions).

- [ ] **Step 5: Commit**

```bash
git add api/src/tasks/data_source_tasks.py api/tests/unit/tasks/test_data_source_tasks.py
git commit -m "feat: filter data source auto-sync dispatch by due time"
```

## Task 2: Schedule `sync_all_data_sources_task` in Celery beat

**Files:**
- Modify: `api/src/celery_app.py`

- [ ] **Step 1: Add the beat_schedule entry**

In `api/src/celery_app.py`, inside the `beat_schedule={...}` dict, add a new entry. Insert it right after the `"generate-daily-digests"` entry (around line 176, before `"poll-llm-batches"`) to group it near the other periodic-fan-out entries:

```python
        # Fan out due data source syncs (sync_frequency_minutes-based) every 5 minutes.
        "dispatch-due-data-source-syncs": {
            "task": "sync_all_data_sources_task",
            "schedule": crontab(minute="*/5"),
        },
```

No `task_routes` entry is needed — `sync_all_data_sources_task` and `sync_data_source_task` have never had one and both already fall through to `task_default_queue="default"`, served by the always-running `celery-worker` container.

- [ ] **Step 2: Verify the module still imports cleanly**

Run: `docker compose exec -T api python -c "from src.celery_app import celery_app; print('dispatch-due-data-source-syncs' in celery_app.conf.beat_schedule)"`
Expected output: `True`

- [ ] **Step 3: Commit**

```bash
git add api/src/celery_app.py
git commit -m "feat: schedule due data source sync dispatch every 5 minutes"
```

## Task 3: Restart services and verify live

- [ ] **Step 1: Restart the API and beat/worker containers**

```bash
docker compose restart api celery-beat celery-worker
```

(Confirm the actual beat container name via `docker compose ps` first if `celery-beat` doesn't match — some setups name it `celery-worker-beat` or run beat embedded in the `celery-worker` command; check `docker-compose.yml` for the container running `celery -A src.celery_app beat`.)

- [ ] **Step 2: Confirm the schedule is loaded**

Run: `docker compose logs celery-beat --tail=50 | grep -i "dispatch-due-data-source-syncs"`
Expected: A log line showing the new periodic task registered in beat's schedule (Celery beat logs its full schedule on startup).

## Self-Review Notes

- **Spec coverage:** This plan covers Phase 1.1 from `docs/superpowers/specs/2026-08-17-company-brain-kb-unification-design.md` in full — auto-sync scheduling using real `sync_frequency_minutes`/`last_sync_at` fields (design spec's pseudocode incorrectly referenced a non-existent `last_synced_at` field and a non-existent `DataSource.deleted_at` — both corrected here using the verified real schema).
- **No placeholders:** All code shown is complete and directly runnable; no TODOs.
- **Type consistency:** `_dispatch_all_syncs(tenant_id: str | None) -> dict[str, Any]` signature unchanged from the existing task — only its internal filtering logic changes, so `sync_all_data_sources_task`'s existing `asyncio.run(_dispatch_all_syncs(tenant_id))` call site needs no changes.
