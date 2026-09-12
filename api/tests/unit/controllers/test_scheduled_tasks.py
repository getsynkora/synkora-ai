import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Since we are testing the controller directly via app or router, we need to setup the client
# We can use the app fixture or create a new app with just this router for isolation
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.scheduled_tasks import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.scheduled_task import ScheduledTask


@pytest.fixture
def mock_scheduler_service():
    with patch("src.controllers.scheduled_tasks.SchedulerService") as mock:
        mock_instance = AsyncMock()
        # These two methods are called without await (sync)
        mock_instance.execute_task_async = MagicMock()
        mock_instance.validate_cron = MagicMock()
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def client(mock_scheduler_service, mock_db_session):
    app = FastAPI()
    app.include_router(router)

    # Mock dependencies
    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_account] = lambda: MagicMock(id=uuid.uuid4())

    # Mock tenant ID
    tenant_id = uuid.uuid4()
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    return TestClient(app), tenant_id, mock_scheduler_service


class TestScheduledTasksController:
    def _create_mock_task(self, task_id, tenant_id, **kwargs):
        expected_task = MagicMock(spec=ScheduledTask)
        expected_task.id = task_id
        expected_task.tenant_id = tenant_id
        expected_task.name = "Test Task"
        expected_task.description = "Test Description"
        expected_task.task_type = "database_query"
        expected_task.schedule_type = "cron"  # Add required field
        expected_task.cron_expression = "0 0 * * *"
        expected_task.interval_seconds = None
        expected_task.database_connection_id = 1
        expected_task.query = "SELECT 1"
        expected_task.config = {}
        expected_task.is_active = True
        expected_task.last_run_at = None
        expected_task.next_run_at = None
        expected_task.last_run_status = None
        expected_task.created_at = datetime.now(UTC)
        expected_task.updated_at = datetime.now(UTC)
        expected_task.created_by = uuid.uuid4()  # Add required field

        for key, value in kwargs.items():
            setattr(expected_task, key, value)

        return expected_task

    def test_create_scheduled_task(self, client):
        test_client, tenant_id, mock_service_cls = client
        mock_service = mock_service_cls.return_value

        task_id = uuid.uuid4()
        expected_task = self._create_mock_task(task_id, tenant_id)

        # Controller calls create_agent_task, not create_task
        mock_service.create_agent_task.return_value = expected_task

        payload = {
            "name": "Test Task",
            "task_type": "database_query",
            "interval_seconds": 3600,  # 1 hour
            "database_connection_id": 1,
            "query": "SELECT 1",
            "chart_config": {},
            "is_active": True,
        }

        response = test_client.post("/scheduled-tasks", json=payload)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["id"] == str(task_id)
        assert data["name"] == "Test Task"

        mock_service.create_agent_task.assert_called_once()

    def test_list_scheduled_tasks(self, client):
        test_client, tenant_id, mock_service_cls = client
        mock_service = mock_service_cls.return_value

        task_id = uuid.uuid4()
        expected_task = self._create_mock_task(task_id, tenant_id)

        mock_service.list_tasks.return_value = [expected_task]

        response = test_client.get("/scheduled-tasks")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(task_id)

        mock_service.list_tasks.assert_called_with(tenant_id=tenant_id, skip=0, limit=100)

    def test_get_scheduled_task(self, client):
        test_client, tenant_id, mock_service_cls = client
        mock_service = mock_service_cls.return_value

        task_id = uuid.uuid4()
        expected_task = self._create_mock_task(task_id, tenant_id)

        mock_service.get_task.return_value = expected_task

        response = test_client.get(f"/scheduled-tasks/{task_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(task_id)

        mock_service.get_task.assert_called_with(task_id, tenant_id=tenant_id)

    def test_update_scheduled_task(self, client):
        test_client, tenant_id, mock_service_cls = client
        mock_service = mock_service_cls.return_value

        task_id = uuid.uuid4()
        expected_task = self._create_mock_task(task_id, tenant_id, name="Updated Task")

        mock_service.get_task.return_value = expected_task
        mock_service.update_task.return_value = expected_task

        payload = {"name": "Updated Task"}

        response = test_client.put(f"/scheduled-tasks/{task_id}", json=payload)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Task"

        mock_service.update_task.assert_called_with(task_id, tenant_id=tenant_id, name="Updated Task")

    def test_delete_scheduled_task(self, client):
        test_client, tenant_id, mock_service_cls = client
        mock_service = mock_service_cls.return_value

        task_id = uuid.uuid4()
        expected_task = self._create_mock_task(task_id, tenant_id)

        mock_service.get_task.return_value = expected_task

        response = test_client.delete(f"/scheduled-tasks/{task_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

        mock_service.delete_task.assert_called_with(task_id, tenant_id=tenant_id)

    def test_execute_scheduled_task(self, client):
        test_client, tenant_id, mock_service_cls = client
        mock_service = mock_service_cls.return_value

        task_id = uuid.uuid4()
        expected_task = self._create_mock_task(task_id, tenant_id)

        mock_service.get_task.return_value = expected_task

        response = test_client.post(f"/scheduled-tasks/{task_id}/execute")

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json()["message"] == "Task execution queued"

        mock_service.execute_task_async.assert_called_with(task_id)

    def test_toggle_scheduled_task(self, client):
        test_client, tenant_id, mock_service_cls = client
        mock_service = mock_service_cls.return_value

        task_id = uuid.uuid4()
        expected_task = self._create_mock_task(task_id, tenant_id, is_active=False)

        mock_service.get_task.return_value = expected_task
        mock_service.toggle_task.return_value = expected_task

        response = test_client.post(f"/scheduled-tasks/{task_id}/toggle")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_active"] is False

        mock_service.toggle_task.assert_called_with(task_id, tenant_id=tenant_id)

    def test_validate_cron_expression(self, client):
        test_client, tenant_id, mock_service_cls = client
        mock_service = mock_service_cls.return_value

        mock_service.validate_cron.return_value = {
            "is_valid": True,
            "next_run": "2023-01-01T00:00:00Z",
            "preview": ["2023-01-01T00:00:00Z"],
        }

        response = test_client.post("/scheduled-tasks/validate-cron", json={"cron_expression": "0 0 * * *"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_valid"] is True

        mock_service.validate_cron.assert_called_with("0 0 * * *")
