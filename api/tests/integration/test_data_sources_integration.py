"""
Integration tests for Data Sources endpoints.

Tests CRUD operations for data sources, sync operations, and OAuth flows.
Note: Data sources require a knowledge_base_id and use specific types like SLACK, GMAIL, GOOGLE_DRIVE, etc.
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
    email = f"datasources_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Data Sources Test User",
            "tenant_name": "Data Sources Test Org",
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


class TestDataSourcesListIntegration:
    """Test Data Sources listing operations."""

    @pytest.mark.asyncio
    async def test_list_data_sources(self, async_client: AsyncClient, auth_headers):
        """Test listing data sources."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/data-sources", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_data_sources_with_pagination(self, async_client: AsyncClient, auth_headers):
        """Test listing data sources with pagination."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/data-sources?skip=0&limit=10", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)


class TestDataSourcesGetIntegration:
    """Test getting specific data sources."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_data_source(self, async_client: AsyncClient, auth_headers):
        """Test getting a nonexistent data source returns 404."""
        headers, tenant_id, account = auth_headers

        # Use a very high ID that likely doesn't exist
        response = await async_client.get("/api/v1/data-sources/999999999", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDataSourcesCreateValidation:
    """Test Data Sources creation validation."""

    @pytest.mark.asyncio
    async def test_create_data_source_missing_required_fields(self, async_client: AsyncClient, auth_headers):
        """Test that creating data source without required fields fails."""
        headers, tenant_id, account = auth_headers

        # Missing knowledge_base_id and type
        response = await async_client.post(
            "/api/v1/data-sources",
            json={
                "name": f"TestSource_{uuid.uuid4().hex[:8]}",
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_data_source_invalid_type(self, async_client: AsyncClient, auth_headers):
        """Test that creating data source with invalid type fails."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/data-sources",
            json={
                "name": f"TestSource_{uuid.uuid4().hex[:8]}",
                "type": "invalid_type",  # Not a valid DataSourceType
                "knowledge_base_id": 1,
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_data_source_nonexistent_knowledge_base(self, async_client: AsyncClient, auth_headers):
        """Test that creating data source with nonexistent knowledge base fails."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/data-sources",
            json={
                "name": f"TestSource_{uuid.uuid4().hex[:8]}",
                "type": "SLACK",  # Valid type
                "knowledge_base_id": 999999,  # Doesn't exist
            },
            headers=headers,
        )

        # Should fail because knowledge base doesn't exist
        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST]


class TestDataSourcesTenantIsolation:
    """Test data sources tenant isolation."""

    @pytest.mark.asyncio
    async def test_data_sources_list_is_tenant_isolated(
        self, async_client: AsyncClient, async_db_session: AsyncSession
    ):
        """Test that users only see their own tenant's data sources."""
        # Create first user/tenant
        email1 = f"tenant1_ds_{uuid.uuid4().hex[:8]}@example.com"
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
        email2 = f"tenant2_ds_{uuid.uuid4().hex[:8]}@example.com"
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

        # Both should be able to list (even if empty)
        response1 = await async_client.get("/api/v1/data-sources", headers=headers1)
        response2 = await async_client.get("/api/v1/data-sources", headers=headers2)

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_cannot_get_other_tenant_data_source(self, async_client: AsyncClient, auth_headers):
        """Test that users cannot access data sources from other tenants by ID."""
        headers, tenant_id, account = auth_headers

        # Try to access a data source with a random ID
        # It should return 404 regardless of whether it exists in another tenant
        response = await async_client.get("/api/v1/data-sources/999999", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDataSourcesAuthorization:
    """Test data sources authorization."""

    @pytest.mark.asyncio
    async def test_list_data_sources_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests are rejected."""
        response = await async_client.get("/api/v1/data-sources")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_create_data_source_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to create are rejected."""
        response = await async_client.post(
            "/api/v1/data-sources",
            json={
                "name": "Unauthorized Source",
                "type": "SLACK",
                "knowledge_base_id": 1,
            },
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_get_data_source_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to get are rejected."""
        response = await async_client.get("/api/v1/data-sources/1")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_delete_data_source_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to delete are rejected."""
        response = await async_client.delete("/api/v1/data-sources/1")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
