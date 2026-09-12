import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scheduled_task import ScheduledTask
from src.services.scheduler.scheduler_service import SchedulerService


@pytest.fixture
def mock_db_session():
    """Create a mock async database session."""
    session = AsyncMock(spec=AsyncSession)
    # Make sure add is a regular method (not awaitable) but commit, refresh, delete, flush are awaitable
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def scheduler_service(mock_db_session):
    with (
        patch("src.services.scheduler.scheduler_service.TaskExecutor") as mock_executor,
        patch("src.services.scheduler.scheduler_service.CronValidator") as mock_validator,
    ):
        service = SchedulerService(mock_db_session)
        service.task_executor = mock_executor.return_value
        service.cron_validator = mock_validator.return_value

        # Setup default validator behavior
        service.cron_validator.validate.return_value = {"is_valid": True}

        yield service


class TestSchedulerService:
    async def test_create_task(self, scheduler_service, mock_db_session):
        tenant_id = uuid.uuid4()
        created_by = uuid.uuid4()

        task = await scheduler_service.create_task(
            tenant_id=tenant_id,
            name="Test Task",
            task_type="database_query",
            schedule="0 0 * * *",
            database_connection_id=1,
            query="SELECT 1",
            created_by=created_by,
        )

        assert isinstance(task, ScheduledTask)
        assert task.tenant_id == tenant_id
        assert task.name == "Test Task"
        assert task.cron_expression == "0 0 * * *"  # Check cron_expression instead of schedule
        assert task.schedule_type == "cron"
        assert task.config == {"database_connection_id": 1, "query": "SELECT 1"}  # Check config
        assert task.created_by == created_by

        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    async def test_create_task_invalid_cron(self, scheduler_service):
        scheduler_service.cron_validator.validate.return_value = {"is_valid": False, "error": "Invalid cron"}

        with pytest.raises(ValueError, match="Invalid cron expression"):
            await scheduler_service.create_task(
                tenant_id=uuid.uuid4(),
                name="Test Task",
                task_type="database_query",
                schedule="invalid",
                database_connection_id=1,
                query="SELECT 1",
                created_by=uuid.uuid4(),
            )

    async def test_update_task(self, scheduler_service, mock_db_session):
        task_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        existing_task = ScheduledTask(
            id=task_id, tenant_id=tenant_id, name="Old Name", cron_expression="0 0 * * *", config={}
        )

        # Setup execute mock to return the existing task
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_task
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        updated_task = await scheduler_service.update_task(
            task_id=task_id, tenant_id=tenant_id, name="New Name", schedule="0 12 * * *"
        )

        assert updated_task.name == "New Name"
        assert updated_task.cron_expression == "0 12 * * *"
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    async def test_delete_task(self, scheduler_service, mock_db_session):
        task_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        existing_task = ScheduledTask(id=task_id, tenant_id=tenant_id)

        # Setup execute mock to return the existing task
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_task
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        await scheduler_service.delete_task(task_id, tenant_id=tenant_id)

        mock_db_session.delete.assert_awaited_once_with(existing_task)
        mock_db_session.commit.assert_awaited_once()

    async def test_get_task(self, scheduler_service, mock_db_session):
        task_id = uuid.uuid4()
        expected_task = ScheduledTask(id=task_id)

        # Setup execute mock to return the expected task
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expected_task
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await scheduler_service.get_task(task_id)

        assert result == expected_task
        mock_db_session.execute.assert_awaited_once()

    async def test_list_tasks(self, scheduler_service, mock_db_session):
        tenant_id = uuid.uuid4()
        expected_tasks = [ScheduledTask(id=uuid.uuid4()), ScheduledTask(id=uuid.uuid4())]

        # Setup execute mock to return the expected tasks
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = expected_tasks
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await scheduler_service.list_tasks(tenant_id)

        assert len(result) == 2
        assert result == expected_tasks

    def test_execute_task_async(self, scheduler_service):
        task_id = uuid.uuid4()

        with patch("src.services.scheduler.scheduler_service.execute_scheduled_task") as mock_celery_task:
            scheduler_service.execute_task_async(task_id)
            mock_celery_task.delay.assert_called_once_with(str(task_id))

    async def test_toggle_task(self, scheduler_service, mock_db_session):
        task_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        task = ScheduledTask(id=task_id, tenant_id=tenant_id, is_active=True)

        # Setup execute mock to return the task
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = task
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        await scheduler_service.toggle_task(task_id, tenant_id=tenant_id)

        assert task.is_active is False
        mock_db_session.commit.assert_awaited_once()
        mock_db_session.refresh.assert_awaited_once()

    async def test_get_task_executions(self, scheduler_service, mock_db_session):
        task_id = uuid.uuid4()

        # Setup execute mock to return empty list
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await scheduler_service.get_task_executions(task_id)

        assert isinstance(result, list)
        mock_db_session.execute.assert_awaited_once()
