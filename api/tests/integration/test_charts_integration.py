"""
Integration tests for Charts endpoints.

Tests CRUD operations for charts.

Note: Charts controller uses AsyncSession but get_db returns sync Session,
which may cause compatibility issues. Tests accept 500 errors where appropriate.
"""

import uuid

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

    email = f"charts_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Charts Test User",
            "tenant_name": "Charts Test Org",
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


@pytest_asyncio.fixture
async def test_agent(async_client: AsyncClient, async_db_session: AsyncSession, auth_headers):
    """Create a test agent for chart tests."""
    from src.models.agent import Agent

    headers, tenant_id, account = auth_headers

    # Create agent directly in the database to avoid API issues
    agent = Agent(
        tenant_id=tenant_id,
        agent_name=f"chart-test-agent-{uuid.uuid4().hex[:8]}",
        description="Agent for chart tests",
        system_prompt="You are a test agent.",
        llm_config={"provider": "openai", "model": "gpt-4o-mini"},
    )
    async_db_session.add(agent)
    await async_db_session.commit()
    await async_db_session.refresh(agent)

    return str(agent.id)


class TestChartsListIntegration:
    """Test Charts listing operations."""

    @pytest.mark.asyncio
    async def test_list_charts(self, async_client: AsyncClient, auth_headers):
        """Test listing charts."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get("/api/v1/charts", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_charts_with_agent_filter(self, async_client: AsyncClient, auth_headers, test_agent):
        """Test listing charts filtered by agent."""
        headers, tenant_id, account = auth_headers

        response = await async_client.get(f"/api/v1/charts?agent_id={test_agent}", headers=headers)

        assert response.status_code == status.HTTP_200_OK


class TestChartsCRUDIntegration:
    """Test Charts CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_chart(self, async_client: AsyncClient, auth_headers, test_agent):
        """Test creating a chart."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/charts",
            json={
                "agent_id": test_agent,
                "title": f"Test Chart {uuid.uuid4().hex[:8]}",
                "chart_type": "bar",
                "library": "chartjs",
                "config": {"responsive": True},
                "data": {"labels": ["A", "B", "C"], "values": [1, 2, 3]},
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["chart_type"] == "bar"

    @pytest.mark.asyncio
    async def test_get_chart(self, async_client: AsyncClient, auth_headers, test_agent):
        """Test getting a specific chart."""
        headers, tenant_id, account = auth_headers

        # Create a chart first
        create_response = await async_client.post(
            "/api/v1/charts",
            json={
                "agent_id": test_agent,
                "title": "Get Test Chart",
                "chart_type": "line",
                "library": "chartjs",
                "config": {},
                "data": {},
            },
            headers=headers,
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        chart_id = create_response.json()["id"]
        response = await async_client.get(f"/api/v1/charts/{chart_id}", headers=headers)
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_get_nonexistent_chart(self, async_client: AsyncClient, auth_headers):
        """Test getting a nonexistent chart returns 404."""
        headers, tenant_id, account = auth_headers

        fake_id = str(uuid.uuid4())
        response = await async_client.get(f"/api/v1/charts/{fake_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_chart(self, async_client: AsyncClient, auth_headers, test_agent):
        """Test updating a chart."""
        headers, tenant_id, account = auth_headers

        # Create a chart first
        create_response = await async_client.post(
            "/api/v1/charts",
            json={
                "agent_id": test_agent,
                "title": "Update Test Chart",
                "chart_type": "pie",
                "library": "chartjs",
                "config": {},
                "data": {},
            },
            headers=headers,
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        chart_id = create_response.json()["id"]
        response = await async_client.patch(
            f"/api/v1/charts/{chart_id}",
            json={"title": "Updated Chart Title"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_delete_chart(self, async_client: AsyncClient, auth_headers, test_agent):
        """Test deleting a chart."""
        headers, tenant_id, account = auth_headers

        # Create a chart first
        create_response = await async_client.post(
            "/api/v1/charts",
            json={
                "agent_id": test_agent,
                "title": "Delete Test Chart",
                "chart_type": "doughnut",
                "library": "chartjs",
                "config": {},
                "data": {},
            },
            headers=headers,
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        chart_id = create_response.json()["id"]
        response = await async_client.delete(f"/api/v1/charts/{chart_id}", headers=headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestChartsValidation:
    """Test Charts validation."""

    @pytest.mark.asyncio
    async def test_create_chart_missing_required_fields(self, async_client: AsyncClient, auth_headers):
        """Test creating chart without required fields fails validation."""
        headers, tenant_id, account = auth_headers

        # Missing agent_id, title, chart_type, library, config, data
        response = await async_client.post(
            "/api/v1/charts",
            json={"description": "Only description"},
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_chart_empty_title(self, async_client: AsyncClient, auth_headers, test_agent):
        """Test creating chart with empty title fails validation."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/charts",
            json={
                "agent_id": test_agent,
                "title": "",
                "chart_type": "bar",
                "library": "chartjs",
                "config": {},
                "data": {},
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestChartsAuthorization:
    """Test Charts authorization."""

    @pytest.mark.asyncio
    async def test_list_charts_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to list are rejected."""
        response = await async_client.get("/api/v1/charts")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_create_chart_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to create are rejected."""
        response = await async_client.post(
            "/api/v1/charts",
            json={
                "agent_id": str(uuid.uuid4()),
                "title": "Unauthorized Chart",
                "chart_type": "bar",
                "library": "chartjs",
                "config": {},
                "data": {},
            },
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_get_chart_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to get are rejected."""
        response = await async_client.get(f"/api/v1/charts/{uuid.uuid4()}")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_update_chart_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to update are rejected."""
        response = await async_client.patch(
            f"/api/v1/charts/{uuid.uuid4()}",
            json={"title": "New Title"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_delete_chart_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to delete are rejected."""
        response = await async_client.delete(f"/api/v1/charts/{uuid.uuid4()}")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
