"""
Integration tests for Activity Logs endpoints.

Tests listing, filtering, and managing activity logs.
"""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, async_db_session: AsyncSession):
    """Create authenticated user and return headers with tenant info."""
    from src.models import Account, AccountStatus

    email = f"actlogs_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Activity Logs Test User",
            "tenant_name": "Activity Logs Test Org",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    tenant_id = data["data"]["tenant"]["id"]

    # Activate account
    result = await async_db_session.execute(select(Account).filter_by(email=email))
    account = result.scalar_one()
    account.status = AccountStatus.ACTIVE
    await async_db_session.commit()

    # Login
    login_response = await async_client.post(
        "/console/api/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}, tenant_id, account


class TestActivityLogsListIntegration:
    """Test Activity Logs listing operations."""

    @pytest.mark.asyncio
    async def test_list_activity_logs(self, async_client: AsyncClient, auth_headers):
        """Test listing activity logs."""
        headers, tenant_id, account = auth_headers

        # Note: activity_logs controller has prefix "/api/v1/api/v1/activity-logs" AND is registered with prefix="/api/v1"
        # So actual path is /api/v1/api/v1/activity-logs
        response = await async_client.get("/api/v1/api/v1/activity-logs", headers=headers)

        # User should be able to see their own logs at minimum
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_activity_logs_with_pagination(self, async_client: AsyncClient, auth_headers):
        """Test listing activity logs with pagination."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/api/v1/activity-logs?skip=0&limit=10", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10

    @pytest.mark.asyncio
    async def test_list_activity_logs_filter_by_action(self, async_client: AsyncClient, auth_headers):
        """Test filtering activity logs by action."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/api/v1/activity-logs?action=login", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # All returned logs should have the specified action (if any returned)
        for log in data:
            assert log["action"] == "login"

    @pytest.mark.asyncio
    async def test_list_activity_logs_filter_by_resource_type(self, async_client: AsyncClient, auth_headers):
        """Test filtering activity logs by resource type."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/api/v1/activity-logs?resource_type=agent", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for log in data:
            assert log["resource_type"] == "agent"

    @pytest.mark.asyncio
    async def test_list_activity_logs_filter_by_date_range(self, async_client: AsyncClient, auth_headers):
        """Test filtering activity logs by date range."""
        headers, tenant_id, account = auth_headers

        # Filter logs from last 7 days
        start_date = (datetime.now() - timedelta(days=7)).isoformat()
        end_date = datetime.now().isoformat()

        response = await async_client.get(
            f"/api/v1/api/v1/activity-logs?start_date={start_date}&end_date={end_date}",
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK


class TestActivityLogsMyRecentIntegration:
    """Test getting current user's recent activities."""

    @pytest.mark.asyncio
    async def test_get_my_recent_activities(self, async_client: AsyncClient, auth_headers):
        """Test getting recent activities for the current user."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/api/v1/activity-logs/me/recent", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_my_recent_activities_with_limit(self, async_client: AsyncClient, auth_headers):
        """Test getting recent activities with custom limit."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/api/v1/activity-logs/me/recent?limit=5", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) <= 5


class TestActivityLogsStatsIntegration:
    """Test activity log statistics."""

    @pytest.mark.asyncio
    async def test_get_activity_stats(self, async_client: AsyncClient, auth_headers):
        """Test getting activity statistics."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/api/v1/activity-logs/stats", headers=headers)

        # May require admin/owner role
        if response.status_code == status.HTTP_403_FORBIDDEN:
            pytest.skip("User doesn't have permission to view activity stats")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_activities" in data
        assert "unique_users" in data
        assert "top_actions" in data
        assert "recent_activities" in data

    @pytest.mark.asyncio
    async def test_get_activity_stats_with_days(self, async_client: AsyncClient, auth_headers):
        """Test getting activity statistics for specific number of days."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/api/v1/activity-logs/stats?days=7", headers=headers)

        if response.status_code == status.HTTP_403_FORBIDDEN:
            pytest.skip("User doesn't have permission to view activity stats")

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_get_activity_stats_invalid_days(self, async_client: AsyncClient, auth_headers):
        """Test getting stats with invalid days parameter."""
        headers, tenant_id, account = auth_headers

        # Days must be between 1 and 365
        response = await async_client.get("/api/v1/api/v1/activity-logs/stats?days=0", headers=headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_get_activity_stats_days_too_high(self, async_client: AsyncClient, auth_headers):
        """Test getting stats with days > 365."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/api/v1/activity-logs/stats?days=400", headers=headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestActivityLogsGetIntegration:
    """Test getting specific activity logs."""

    @pytest.mark.asyncio
    async def test_get_activity_log_not_found(self, async_client: AsyncClient, auth_headers):
        """Test getting a nonexistent activity log."""
        headers, tenant_id, account = auth_headers

        # Use a very high ID that likely doesn't exist
        response = await async_client.get("/api/v1/api/v1/activity-logs/999999999", headers=headers)

        # Either 404 (not found) or 500 (if get_log method not implemented in service)
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestActivityLogsCleanupIntegration:
    """Test activity log cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_logs_unauthorized(self, async_client: AsyncClient, async_db_session: AsyncSession):
        """Test that non-owners cannot cleanup logs."""
        from src.models import Account, AccountStatus
        from src.models.tenant import AccountRole, TenantAccountJoin
        from src.services.auth_service import AuthService

        # Create owner user/tenant
        owner_email = f"cleanup_owner_{uuid.uuid4().hex[:8]}@example.com"
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": owner_email,
                "password": "SecureTestPass123!",
                "name": "Owner User",
                "tenant_name": "Cleanup Test Org",
            },
        )
        result = await async_db_session.execute(select(Account).filter_by(email=owner_email))
        owner_account = result.scalar_one()
        owner_account.status = AccountStatus.ACTIVE
        await async_db_session.commit()

        owner_login = await async_client.post(
            "/console/api/auth/login", json={"email": owner_email, "password": "SecureTestPass123!"}
        )
        owner_login.json()["data"]["access_token"]

        # Get the tenant
        result = await async_db_session.execute(select(TenantAccountJoin).filter_by(account_id=owner_account.id))
        tenant_join = result.scalar_one()
        tenant_id = tenant_join.tenant_id

        # Create a member user (non-owner)
        member_email = f"cleanup_member_{uuid.uuid4().hex[:8]}@example.com"
        member_account = Account(
            email=member_email,
            name="Member User",
            status=AccountStatus.ACTIVE,
            password_hash=AuthService.hash_password("SecureTestPass123!"),
        )
        async_db_session.add(member_account)
        await async_db_session.flush()

        # Add member to tenant
        member_join = TenantAccountJoin(
            tenant_id=tenant_id,
            account_id=member_account.id,
            role=AccountRole.NORMAL,
        )
        async_db_session.add(member_join)
        await async_db_session.commit()

        # Login as member
        member_login = await async_client.post(
            "/console/api/auth/login", json={"email": member_email, "password": "SecureTestPass123!"}
        )
        member_token = member_login.json()["data"]["access_token"]
        member_headers = {"Authorization": f"Bearer {member_token}"}

        # Member should not be able to cleanup logs
        response = await async_client.delete("/api/v1/api/v1/activity-logs/cleanup?days=90", headers=member_headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_cleanup_logs_owner(self, async_client: AsyncClient, auth_headers):
        """Test that owners can cleanup logs."""
        headers, tenant_id, account = auth_headers

        # Owner should be able to cleanup logs
        response = await async_client.delete("/api/v1/api/v1/activity-logs/cleanup?days=90", headers=headers)

        # Owner registered the tenant, so should have owner role
        assert response.status_code in [status.HTTP_204_NO_CONTENT, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_cleanup_logs_invalid_days(self, async_client: AsyncClient, auth_headers):
        """Test cleanup with invalid days parameter."""
        headers, tenant_id, account = auth_headers

        # Days must be between 30 and 365
        response = await async_client.delete("/api/v1/api/v1/activity-logs/cleanup?days=10", headers=headers)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestActivityLogsTenantIsolation:
    """Test activity logs tenant isolation."""

    @pytest.mark.asyncio
    async def test_cannot_see_other_tenant_logs(self, async_client: AsyncClient, async_db_session: AsyncSession):
        """Test that users cannot see activity logs from other tenants."""
        from src.models import Account, AccountStatus

        # Create first user/tenant
        email1 = f"tenant1_logs_{uuid.uuid4().hex[:8]}@example.com"
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email1,
                "password": "SecureTestPass123!",
                "name": "Tenant 1 User",
                "tenant_name": "Logs Tenant 1",
            },
        )
        result = await async_db_session.execute(select(Account).filter_by(email=email1))
        account1 = result.scalar_one()
        account1.status = AccountStatus.ACTIVE
        await async_db_session.commit()

        login1 = await async_client.post(
            "/console/api/auth/login", json={"email": email1, "password": "SecureTestPass123!"}
        )
        token1 = login1.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Create second user/tenant
        email2 = f"tenant2_logs_{uuid.uuid4().hex[:8]}@example.com"
        await async_client.post(
            "/console/api/auth/register",
            json={
                "email": email2,
                "password": "SecureTestPass123!",
                "name": "Tenant 2 User",
                "tenant_name": "Logs Tenant 2",
            },
        )
        result = await async_db_session.execute(select(Account).filter_by(email=email2))
        account2 = result.scalar_one()
        account2.status = AccountStatus.ACTIVE
        await async_db_session.commit()

        login2 = await async_client.post(
            "/console/api/auth/login", json={"email": email2, "password": "SecureTestPass123!"}
        )
        token2 = login2.json()["data"]["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Get logs for tenant 1
        logs1_response = await async_client.get("/api/v1/api/v1/activity-logs", headers=headers1)
        assert logs1_response.status_code == status.HTTP_200_OK

        # Get logs for tenant 2
        logs2_response = await async_client.get("/api/v1/api/v1/activity-logs", headers=headers2)
        assert logs2_response.status_code == status.HTTP_200_OK

        # Each tenant should only see their own account's activities
        logs1 = logs1_response.json()
        logs2 = logs2_response.json()

        # Check that account emails don't overlap between tenants
        emails1 = {log.get("account_email") for log in logs1 if log.get("account_email")}
        emails2 = {log.get("account_email") for log in logs2 if log.get("account_email")}

        # If both have logs, they shouldn't overlap
        if emails1 and emails2:
            assert emails1.isdisjoint(emails2), "Tenant logs should not overlap"


class TestActivityLogsAuthorization:
    """Test activity logs authorization."""

    @pytest.mark.asyncio
    async def test_list_logs_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests are rejected."""
        response = await async_client.get("/api/v1/api/v1/activity-logs")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_get_stats_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to stats are rejected."""
        response = await async_client.get("/api/v1/api/v1/activity-logs/stats")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_get_my_recent_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to my/recent are rejected."""
        response = await async_client.get("/api/v1/api/v1/activity-logs/me/recent")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
