"""
Integration tests for Scheduled Tasks endpoints.

Tests CRUD operations for scheduled tasks and execution history.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, async_db_session: AsyncSession):
    """Create authenticated user and return headers with tenant info."""
    from src.models import Account, AccountStatus

    email = f"scheduled_tasks_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Scheduled Tasks Test User",
            "tenant_name": "Scheduled Tasks Test Org",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    tenant_id = data["data"]["tenant"]["id"]

    # Activate account
    result = await async_db_session.execute(select(Account).filter_by(email=email))
    account = result.scalar_one_or_none()
    account.status = AccountStatus.ACTIVE
    await async_db_session.commit()

    # Login
    login_response = await async_client.post(
        "/console/api/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}, tenant_id


class TestScheduledTasksCRUDIntegration:
    """Test Scheduled Tasks CRUD operations."""

    def test_scheduled_task_full_lifecycle(self, client: TestClient, auth_headers):
        """Test complete scheduled task lifecycle: create -> get -> update -> delete."""
        headers, tenant_id = auth_headers
        task_name = f"TestTask_{uuid.uuid4().hex[:8]}"

        # 1. Create Scheduled Task
        create_response = client.post(
            "/api/v1/scheduled-tasks",
            json={
                "name": task_name,
                "description": "Test scheduled task for integration tests",
                "task_type": "agent_task",
                "interval_seconds": 3600,  # 1 hour
                "config": {"agent_id": str(uuid.uuid4()), "message": "Hello"},
                "is_active": True,
            },
            headers=headers,
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        create_data = create_response.json()
        assert create_data["name"] == task_name
        assert create_data["is_active"] is True
        task_id = str(create_data["id"])

        # 2. Get Scheduled Task
        get_response = client.get(f"/api/v1/scheduled-tasks/{task_id}", headers=headers)
        assert get_response.status_code == status.HTTP_200_OK
        get_data = get_response.json()
        assert get_data["name"] == task_name

        # 3. List Scheduled Tasks
        list_response = client.get("/api/v1/scheduled-tasks", headers=headers)
        assert list_response.status_code == status.HTTP_200_OK
        list_data = list_response.json()
        task_ids = [str(t["id"]) for t in list_data]
        assert task_id in task_ids

        # 4. Update Scheduled Task
        update_response = client.put(
            f"/api/v1/scheduled-tasks/{task_id}",
            json={
                "name": f"{task_name}_updated",
                "description": "Updated description",
                "interval_seconds": 7200,  # 2 hours
                "is_active": False,
            },
            headers=headers,
        )
        assert update_response.status_code == status.HTTP_200_OK
        update_data = update_response.json()
        assert update_data["name"] == f"{task_name}_updated"
        assert update_data["is_active"] is False
        assert update_data["interval_seconds"] == 7200

        # 5. Delete Scheduled Task
        delete_response = client.delete(f"/api/v1/scheduled-tasks/{task_id}", headers=headers)
        assert delete_response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]

        # Verify deletion
        verify_response = client.get(f"/api/v1/scheduled-tasks/{task_id}", headers=headers)
        assert verify_response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_database_query_task(self, client: TestClient, auth_headers):
        """Test creating a database query scheduled task."""
        headers, tenant_id = auth_headers
        task_name = f"DBQueryTask_{uuid.uuid4().hex[:8]}"

        response = client.post(
            "/api/v1/scheduled-tasks",
            json={
                "name": task_name,
                "description": "Database query task",
                "task_type": "database_query",
                "interval_seconds": 1800,  # 30 minutes
                "database_connection_id": 1,  # May not exist, but tests validation
                "query": "SELECT COUNT(*) FROM users",
                "is_active": False,
            },
            headers=headers,
        )

        # May fail if database_connection_id doesn't exist, but should validate task_type
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]

    def test_create_chart_generation_task(self, client: TestClient, auth_headers):
        """Test creating a chart generation scheduled task."""
        headers, tenant_id = auth_headers
        task_name = f"ChartTask_{uuid.uuid4().hex[:8]}"

        response = client.post(
            "/api/v1/scheduled-tasks",
            json={
                "name": task_name,
                "description": "Chart generation task",
                "task_type": "chart_generation",
                "interval_seconds": 86400,  # Daily
                "chart_config": {
                    "chart_type": "line",
                    "title": "Daily Metrics",
                    "x_axis": "date",
                    "y_axis": "count",
                },
                "is_active": True,
            },
            headers=headers,
        )

        # May fail due to missing dependencies, but validates structure
        assert response.status_code in [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]

    def test_create_task_invalid_type(self, client: TestClient, auth_headers):
        """Test that creating task with invalid type fails."""
        headers, tenant_id = auth_headers

        response = client.post(
            "/api/v1/scheduled-tasks",
            json={
                "name": f"InvalidTypeTask_{uuid.uuid4().hex[:8]}",
                "description": "Invalid task type",
                "task_type": "invalid_type",  # Invalid
                "interval_seconds": 3600,
                "is_active": True,
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_create_task_invalid_interval(self, client: TestClient, auth_headers):
        """Test that creating task with invalid interval fails."""
        headers, tenant_id = auth_headers

        response = client.post(
            "/api/v1/scheduled-tasks",
            json={
                "name": f"InvalidIntervalTask_{uuid.uuid4().hex[:8]}",
                "description": "Invalid interval",
                "task_type": "agent_task",
                "interval_seconds": 0,  # Invalid - must be > 0
                "is_active": True,
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_get_nonexistent_task(self, client: TestClient, auth_headers):
        """Test getting a nonexistent task returns 404."""
        headers, tenant_id = auth_headers
        fake_id = str(uuid.uuid4())

        response = client.get(f"/api/v1/scheduled-tasks/{fake_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_tasks_with_different_status(self, client: TestClient, auth_headers):
        """Test that listing returns tasks with different active status."""
        headers, tenant_id = auth_headers

        # Create active task
        active_name = f"ActiveTask_{uuid.uuid4().hex[:8]}"
        active_response = client.post(
            "/api/v1/scheduled-tasks",
            json={
                "name": active_name,
                "description": "Active task",
                "task_type": "agent_task",
                "interval_seconds": 3600,
                "is_active": True,
                "config": {"agent_id": str(uuid.uuid4())},
            },
            headers=headers,
        )
        assert active_response.status_code == status.HTTP_201_CREATED

        # Create inactive task
        inactive_name = f"InactiveTask_{uuid.uuid4().hex[:8]}"
        inactive_response = client.post(
            "/api/v1/scheduled-tasks",
            json={
                "name": inactive_name,
                "description": "Inactive task",
                "task_type": "agent_task",
                "interval_seconds": 3600,
                "is_active": False,
                "config": {"agent_id": str(uuid.uuid4())},
            },
            headers=headers,
        )
        assert inactive_response.status_code == status.HTTP_201_CREATED

        # List all tasks
        response = client.get("/api/v1/scheduled-tasks", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Both tasks should be in the list
        task_dict = {t["name"]: t for t in data}
        assert active_name in task_dict
        assert inactive_name in task_dict

        # Verify their is_active status
        assert task_dict[active_name]["is_active"] is True
        assert task_dict[inactive_name]["is_active"] is False


class TestScheduledTasksTenantIsolation:
    """Test scheduled tasks tenant isolation."""

    @pytest.mark.asyncio
    async def test_cannot_access_other_tenant_task(self, async_client: AsyncClient, async_db_session: AsyncSession):
        """Test that users cannot access tasks from other tenants."""
        from src.models import Account, AccountStatus

        # Create first user/tenant
        email1 = f"tenant1_task_{uuid.uuid4().hex[:8]}@example.com"
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email1,
                "password": "SecureTestPass123!",
                "name": "Tenant 1 User",
                "tenant_name": "Tenant 1 Org",
            },
        )
        result1 = await async_db_session.execute(select(Account).filter_by(email=email1))
        account1 = result1.scalar_one_or_none()
        account1.status = AccountStatus.ACTIVE
        await async_db_session.commit()

        login1 = await async_client.post(
            "/console/api/auth/login", json={"email": email1, "password": "SecureTestPass123!"}
        )
        token1 = login1.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Create second user/tenant
        email2 = f"tenant2_task_{uuid.uuid4().hex[:8]}@example.com"
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email2,
                "password": "SecureTestPass123!",
                "name": "Tenant 2 User",
                "tenant_name": "Tenant 2 Org",
            },
        )
        result2 = await async_db_session.execute(select(Account).filter_by(email=email2))
        account2 = result2.scalar_one_or_none()
        account2.status = AccountStatus.ACTIVE
        await async_db_session.commit()

        login2 = await async_client.post(
            "/console/api/auth/login", json={"email": email2, "password": "SecureTestPass123!"}
        )
        token2 = login2.json()["data"]["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Create task as tenant 1
        task_name = f"IsolatedTask_{uuid.uuid4().hex[:8]}"
        create_response = await async_client.post(
            "/api/v1/scheduled-tasks",
            json={
                "name": task_name,
                "description": "Tenant 1 task",
                "task_type": "agent_task",
                "interval_seconds": 3600,
                "is_active": True,
                "config": {"agent_id": str(uuid.uuid4())},
            },
            headers=headers1,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        task_id = str(create_response.json()["id"])

        # Tenant 2 should not be able to access tenant 1's task
        # Either 403 (Forbidden) or 404 (Not Found) is acceptable for tenant isolation
        get_response = await async_client.get(f"/api/v1/scheduled-tasks/{task_id}", headers=headers2)
        assert get_response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

        # Tenant 2 should not be able to update tenant 1's task
        update_response = await async_client.put(
            f"/api/v1/scheduled-tasks/{task_id}",
            json={"name": "Hacked Task"},
            headers=headers2,
        )
        assert update_response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

        # Tenant 2 should not be able to delete tenant 1's task
        delete_response = await async_client.delete(f"/api/v1/scheduled-tasks/{task_id}", headers=headers2)
        assert delete_response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]


class TestCronValidation:
    """Test cron expression validation."""

    def test_validate_valid_cron(self, client: TestClient, auth_headers):
        """Test validating a valid cron expression."""
        headers, tenant_id = auth_headers

        response = client.post(
            "/api/v1/scheduled-tasks/validate-cron",
            json={"cron_expression": "0 9 * * 1-5"},  # 9 AM weekdays
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_valid"] is True
        assert "next_run" in data

    def test_validate_invalid_cron(self, client: TestClient, auth_headers):
        """Test validating an invalid cron expression."""
        headers, tenant_id = auth_headers

        response = client.post(
            "/api/v1/scheduled-tasks/validate-cron",
            json={"cron_expression": "invalid cron"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_valid"] is False
        assert "error" in data
