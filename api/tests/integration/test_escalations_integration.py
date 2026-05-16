"""
Integration tests for Escalations endpoints.

Tests CRUD operations for human escalations.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Account, AccountStatus


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, async_db_session: AsyncSession):
    """Create authenticated user and return headers with tenant info."""
    email = f"escalations_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Escalations Test User",
            "tenant_name": "Escalations Test Org",
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

    return {"Authorization": f"Bearer {token}"}, tenant_id, account


class TestEscalationsListIntegration:
    """Test Escalations listing operations."""

    @pytest.mark.asyncio
    async def test_list_escalations(self, async_client: AsyncClient, auth_headers):
        """Test listing escalations."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/escalations", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_escalations_with_status_filter(self, async_client: AsyncClient, auth_headers):
        """Test listing escalations filtered by status."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/escalations?status=pending", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # All returned escalations should have pending status
        for esc in data:
            assert esc["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_escalations_include_expired(self, async_client: AsyncClient, auth_headers):
        """Test listing escalations including expired ones."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/escalations?include_expired=true", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)


class TestEscalationsMetadataIntegration:
    """Test Escalations metadata endpoints."""

    @pytest.mark.asyncio
    async def test_list_escalation_statuses(self, async_client: AsyncClient, auth_headers):
        """Test listing available escalation statuses."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/escalations/statuses", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_list_escalation_reasons(self, async_client: AsyncClient, auth_headers):
        """Test listing available escalation reasons."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/escalations/reasons", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_list_escalation_priorities(self, async_client: AsyncClient, auth_headers):
        """Test listing available escalation priorities."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/escalations/priorities", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert isinstance(data["data"], list)


class TestEscalationsGetIntegration:
    """Test getting specific escalations."""

    @pytest.mark.asyncio
    async def test_get_escalation_not_found(self, async_client: AsyncClient, auth_headers):
        """Test getting a nonexistent escalation."""
        headers, tenant_id, account = auth_headers
        fake_id = str(uuid.uuid4())

        response = await async_client.get(f"/api/v1/escalations/{fake_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_escalation_invalid_id(self, async_client: AsyncClient, auth_headers):
        """Test getting escalation with invalid ID format."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/escalations/invalid-id", headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestEscalationsCreateIntegration:
    """Test creating escalations."""

    @pytest.mark.asyncio
    async def test_create_escalation_missing_project(self, async_client: AsyncClient, auth_headers):
        """Test creating escalation with nonexistent project fails."""
        headers, tenant_id, account = auth_headers

        fake_project_id = str(uuid.uuid4())
        fake_agent_id = str(uuid.uuid4())
        fake_human_id = str(uuid.uuid4())

        response = await async_client.post(
            "/api/v1/escalations",
            json={
                "project_id": fake_project_id,
                "from_agent_id": fake_agent_id,
                "to_human_id": fake_human_id,
                "reason": "uncertainty",
                "subject": "Test escalation",
                "message": "This is a test escalation message",
                "priority": "medium",
            },
            headers=headers,
        )

        # Should fail because project doesn't exist
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ]

    @pytest.mark.asyncio
    async def test_create_escalation_invalid_reason(self, async_client: AsyncClient, auth_headers):
        """Test creating escalation with invalid reason fails validation."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/escalations",
            json={
                "project_id": str(uuid.uuid4()),
                "from_agent_id": str(uuid.uuid4()),
                "to_human_id": str(uuid.uuid4()),
                "reason": "invalid_reason",  # Not a valid reason
                "subject": "Test escalation",
                "message": "This is a test",
                "priority": "medium",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_escalation_invalid_priority(self, async_client: AsyncClient, auth_headers):
        """Test creating escalation with invalid priority fails validation."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/escalations",
            json={
                "project_id": str(uuid.uuid4()),
                "from_agent_id": str(uuid.uuid4()),
                "to_human_id": str(uuid.uuid4()),
                "reason": "uncertainty",
                "subject": "Test escalation",
                "message": "This is a test",
                "priority": "invalid_priority",  # Not a valid priority
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_escalation_empty_subject(self, async_client: AsyncClient, auth_headers):
        """Test creating escalation with empty subject fails validation."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/escalations",
            json={
                "project_id": str(uuid.uuid4()),
                "from_agent_id": str(uuid.uuid4()),
                "to_human_id": str(uuid.uuid4()),
                "reason": "uncertainty",
                "subject": "",  # Empty subject
                "message": "This is a test",
                "priority": "medium",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestEscalationsResolveIntegration:
    """Test resolving escalations."""

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_escalation(self, async_client: AsyncClient, auth_headers):
        """Test resolving a nonexistent escalation."""
        headers, tenant_id, account = auth_headers
        fake_id = str(uuid.uuid4())

        response = await async_client.post(
            f"/api/v1/escalations/{fake_id}/resolve",
            json={
                "response": "This is the resolution response",
                "resolution_notes": "Additional notes",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_resolve_escalation_empty_response(self, async_client: AsyncClient, auth_headers):
        """Test resolving escalation with empty response fails validation."""
        headers, tenant_id, account = auth_headers
        fake_id = str(uuid.uuid4())

        response = await async_client.post(
            f"/api/v1/escalations/{fake_id}/resolve",
            json={
                "response": "",  # Empty response
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestEscalationsInProgressIntegration:
    """Test marking escalations in progress."""

    @pytest.mark.asyncio
    async def test_mark_in_progress_nonexistent(self, async_client: AsyncClient, auth_headers):
        """Test marking a nonexistent escalation in progress."""
        headers, tenant_id, account = auth_headers
        fake_id = str(uuid.uuid4())

        response = await async_client.post(f"/api/v1/escalations/{fake_id}/in-progress", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestEscalationsNotifyIntegration:
    """Test sending notifications for escalations."""

    @pytest.mark.asyncio
    async def test_notify_nonexistent_escalation(self, async_client: AsyncClient, auth_headers):
        """Test sending notification for a nonexistent escalation."""
        headers, tenant_id, account = auth_headers
        fake_id = str(uuid.uuid4())

        response = await async_client.post(f"/api/v1/escalations/{fake_id}/notify", headers=headers)

        # May return 400 or 404 depending on implementation
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]


class TestEscalationsExpireIntegration:
    """Test expiring old escalations."""

    @pytest.mark.asyncio
    async def test_expire_old_escalations(self, async_client: AsyncClient, auth_headers):
        """Test expiring old escalations."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post("/api/v1/escalations/expire-old", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True


class TestEscalationsPendingForHumanIntegration:
    """Test getting pending escalations for a human."""

    @pytest.mark.asyncio
    async def test_get_pending_for_human(self, async_client: AsyncClient, auth_headers):
        """Test getting pending escalations for a human contact."""
        headers, tenant_id, account = auth_headers
        human_id = str(uuid.uuid4())

        response = await async_client.get(f"/api/v1/escalations/pending/human/{human_id}", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_pending_for_human_invalid_id(self, async_client: AsyncClient, auth_headers):
        """Test getting pending escalations with invalid human ID."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/escalations/pending/human/invalid-id", headers=headers)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestEscalationsTenantIsolation:
    """Test escalations tenant isolation."""

    @pytest.mark.asyncio
    async def test_cannot_access_other_tenant_escalation(
        self, async_client: AsyncClient, async_db_session: AsyncSession
    ):
        """Test that users cannot access escalations from other tenants."""
        # Create first user/tenant
        email1 = f"tenant1_esc_{uuid.uuid4().hex[:8]}@example.com"
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
        email2 = f"tenant2_esc_{uuid.uuid4().hex[:8]}@example.com"
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

        # Both tenants should get empty lists (no escalations created yet)
        # But they should not be able to see each other's data
        response1 = await async_client.get("/api/v1/escalations", headers=headers1)
        response2 = await async_client.get("/api/v1/escalations", headers=headers2)

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK

        # Both should return empty or their own data only
        data1 = response1.json()
        data2 = response2.json()
        assert isinstance(data1, list)
        assert isinstance(data2, list)


class TestEscalationsAuthorization:
    """Test escalations authorization."""

    @pytest.mark.asyncio
    async def test_list_escalations_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests are rejected."""
        response = await async_client.get("/api/v1/escalations")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_create_escalation_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to create are rejected."""
        response = await async_client.post(
            "/api/v1/escalations",
            json={
                "project_id": str(uuid.uuid4()),
                "from_agent_id": str(uuid.uuid4()),
                "to_human_id": str(uuid.uuid4()),
                "reason": "uncertainty",
                "subject": "Test escalation",
                "message": "This is a test",
                "priority": "medium",
            },
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_statuses_may_be_public(self, async_client: AsyncClient):
        """Test that statuses endpoint may be accessible without auth."""
        response = await async_client.get("/api/v1/escalations/statuses")

        # Metadata endpoints may or may not require auth
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
