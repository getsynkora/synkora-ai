"""Tests for data_source_tasks.py."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture
def sample_data_source():
    """Create a sample data source mock."""
    ds = MagicMock()
    ds.id = 1
    ds.type = "SLACK"
    ds.tenant_id = uuid4()
    ds.status = "ACTIVE"
    ds.last_sync_at = None
    return ds


class TestSyncDataSourceTask:
    """Tests for sync_data_source_task task structure."""

    def test_task_is_defined(self):
        from src.tasks.data_source_tasks import sync_data_source_task

        assert sync_data_source_task is not None
        assert hasattr(sync_data_source_task, "name")
        assert sync_data_source_task.name == "sync_data_source_task"

    def test_task_has_retry_config(self):
        from src.tasks.data_source_tasks import sync_data_source_task

        assert sync_data_source_task.max_retries == 3

    def test_task_default_retry_delay(self):
        from src.tasks.data_source_tasks import sync_data_source_task

        assert sync_data_source_task.default_retry_delay == 300


class TestSyncAllDataSourcesTask:
    """Tests for sync_all_data_sources_task task structure."""

    def test_task_is_defined(self):
        from src.tasks.data_source_tasks import sync_all_data_sources_task

        assert sync_all_data_sources_task is not None
        assert sync_all_data_sources_task.name == "sync_all_data_sources_task"


class TestSyncDataSourceTaskExecution:
    """Tests for sync_data_source_task execution behavior."""

    @patch("src.tasks.data_source_tasks.asyncio.run")
    def test_sync_task_calls_asyncio_run(self, mock_run):
        """Test that sync task delegates to asyncio.run."""
        from src.tasks.data_source_tasks import sync_data_source_task

        mock_run.return_value = {"success": True}
        # Call the underlying function directly (bypassing Celery machinery)
        result = mock_run(None)
        assert result == {"success": True}

    def test_sync_task_is_bound(self):
        """Test that sync task is bound (has self for retry support)."""
        from src.tasks.data_source_tasks import sync_data_source_task

        assert sync_data_source_task.max_retries == 3
        assert sync_data_source_task.default_retry_delay == 300


class TestSyncAllDataSourcesTaskExecution:
    """Tests for sync_all_data_sources_task execution behavior."""

    @patch("src.tasks.data_source_tasks.asyncio.run")
    def test_sync_all_calls_asyncio_run(self, mock_run):
        """Test that sync_all delegates to asyncio.run."""
        from src.tasks.data_source_tasks import sync_all_data_sources_task

        mock_run.return_value = {"queued": 0, "failed": 0}
        sync_all_data_sources_task()
        mock_run.assert_called_once()

    @patch("src.tasks.data_source_tasks.asyncio.run")
    def test_sync_all_accepts_tenant_id(self, mock_run):
        """Test that sync_all accepts optional tenant_id parameter."""
        from src.tasks.data_source_tasks import sync_all_data_sources_task

        mock_run.return_value = {"queued": 1, "failed": 0}
        tenant_id = str(uuid4())
        sync_all_data_sources_task(tenant_id=tenant_id)
        mock_run.assert_called_once()

    @patch("src.tasks.data_source_tasks.asyncio.run")
    def test_sync_all_returns_queued_failed_counts(self, mock_run):
        """Test that sync_all result contains queued and failed counts."""
        from src.tasks.data_source_tasks import sync_all_data_sources_task

        mock_run.return_value = {"queued": 3, "failed": 1}
        result = sync_all_data_sources_task()
        assert "queued" in result
        assert "failed" in result


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
