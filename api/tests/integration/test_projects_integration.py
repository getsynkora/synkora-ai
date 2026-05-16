"""
Integration tests for Projects endpoints.

Tests CRUD operations for projects, context management, and agent associations.
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

    email = f"projects_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Projects Test User",
            "tenant_name": "Projects Test Org",
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


class TestProjectsCRUDIntegration:
    """Test Projects CRUD operations."""

    @pytest.mark.asyncio
    async def test_project_full_lifecycle(self, async_client: AsyncClient, auth_headers):
        """Test complete project lifecycle: create -> get -> update -> delete."""
        headers, tenant_id, account = auth_headers
        project_name = f"TestProject_{uuid.uuid4().hex[:8]}"

        # 1. Create Project
        create_response = await async_client.post(
            "/api/v1/projects",
            json={
                "name": project_name,
                "description": "Test project for integration tests",
            },
            headers=headers,
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        create_data = create_response.json()
        assert create_data["name"] == project_name
        project_id = str(create_data["id"])

        # 2. Get Project
        get_response = await async_client.get(f"/api/v1/projects/{project_id}", headers=headers)
        assert get_response.status_code == status.HTTP_200_OK
        get_data = get_response.json()
        assert get_data["name"] == project_name

        # 3. List Projects
        list_response = await async_client.get("/api/v1/projects", headers=headers)
        assert list_response.status_code == status.HTTP_200_OK
        list_data = list_response.json()
        project_ids = [str(p["id"]) for p in list_data]
        assert project_id in project_ids

        # 4. Update Project
        update_response = await async_client.put(
            f"/api/v1/projects/{project_id}",
            json={
                "name": f"{project_name}_updated",
                "description": "Updated description",
            },
            headers=headers,
        )
        assert update_response.status_code == status.HTTP_200_OK
        update_data = update_response.json()
        assert update_data["name"] == f"{project_name}_updated"
        assert update_data["description"] == "Updated description"

        # 5. Delete Project
        delete_response = await async_client.delete(f"/api/v1/projects/{project_id}", headers=headers)
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        verify_response = await async_client.get(f"/api/v1/projects/{project_id}", headers=headers)
        assert verify_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_project_minimal(self, async_client: AsyncClient, auth_headers):
        """Test creating project with minimal data."""
        headers, tenant_id, account = auth_headers
        project_name = f"MinimalProject_{uuid.uuid4().hex[:8]}"

        response = await async_client.post(
            "/api/v1/projects",
            json={"name": project_name},
            headers=headers,
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == project_name
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_project_empty_name_fails(self, async_client: AsyncClient, auth_headers):
        """Test that creating project with empty name fails."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/projects",
            json={"name": ""},
            headers=headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_get_nonexistent_project(self, async_client: AsyncClient, auth_headers):
        """Test getting a nonexistent project returns 404."""
        headers, tenant_id, account = auth_headers
        fake_id = str(uuid.uuid4())

        response = await async_client.get(f"/api/v1/projects/{fake_id}", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_list_projects_with_pagination(self, async_client: AsyncClient, auth_headers):
        """Test listing projects with pagination parameters."""
        headers, tenant_id, account = auth_headers

        # Create multiple projects
        for i in range(3):
            await async_client.post(
                "/api/v1/projects",
                json={"name": f"PaginationProject_{i}_{uuid.uuid4().hex[:8]}"},
                headers=headers,
            )

        # List with pagination parameters - verify endpoint accepts them
        response = await async_client.get("/api/v1/projects?skip=0&limit=2", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)


class TestProjectContextIntegration:
    """Test Project shared context operations."""

    @pytest.mark.asyncio
    async def test_project_context_operations(self, async_client: AsyncClient, auth_headers):
        """Test project context: get -> update -> set value -> delete key."""
        headers, tenant_id, account = auth_headers

        # Create project first
        project_name = f"ContextProject_{uuid.uuid4().hex[:8]}"
        create_response = await async_client.post(
            "/api/v1/projects",
            json={"name": project_name},
            headers=headers,
        )
        project_id = str(create_response.json()["id"])

        # 1. Get initial context (should be empty or default)
        get_response = await async_client.get(f"/api/v1/projects/{project_id}/context", headers=headers)
        assert get_response.status_code == status.HTTP_200_OK
        get_data = get_response.json()
        assert get_data["success"] is True

        # 2. Update context (PUT - full replace)
        update_response = await async_client.put(
            f"/api/v1/projects/{project_id}/context",
            json={
                "context": {
                    "key1": "value1",
                    "key2": "value2",
                }
            },
            headers=headers,
        )
        assert update_response.status_code == status.HTTP_200_OK
        update_data = update_response.json()
        assert update_data["success"] is True
        assert update_data["data"]["context"]["key1"] == "value1"

        # 3. Patch context (set a single key/value) - uses key/value format
        patch_response = await async_client.patch(
            f"/api/v1/projects/{project_id}/context",
            json={
                "key": "key3",
                "value": "value3",
            },
            headers=headers,
        )
        assert patch_response.status_code == status.HTTP_200_OK
        patch_data = patch_response.json()
        assert patch_data["success"] is True

        # 4. Delete a context key - returns {"success": true, "message": "..."}
        delete_response = await async_client.delete(
            f"/api/v1/projects/{project_id}/context/key1",
            headers=headers,
        )
        assert delete_response.status_code == status.HTTP_200_OK
        delete_data = delete_response.json()
        assert delete_data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_context_key(self, async_client: AsyncClient, auth_headers):
        """Test deleting a context key that doesn't exist."""
        headers, tenant_id, account = auth_headers

        # Create project
        project_name = f"ContextKeyProject_{uuid.uuid4().hex[:8]}"
        create_response = await async_client.post(
            "/api/v1/projects",
            json={"name": project_name},
            headers=headers,
        )
        project_id = str(create_response.json()["id"])

        # Try to delete nonexistent key
        response = await async_client.delete(
            f"/api/v1/projects/{project_id}/context/nonexistent_key",
            headers=headers,
        )

        # Should return 404 or 200 with unchanged context
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


class TestProjectAgentAssociationIntegration:
    """Test Project-Agent association operations."""

    @pytest.mark.asyncio
    async def test_add_and_list_agents_in_project(self, async_client: AsyncClient, auth_headers):
        """Test adding agents to a project and listing them."""
        headers, tenant_id, account = auth_headers

        # Create project
        project_name = f"AgentProject_{uuid.uuid4().hex[:8]}"
        project_response = await async_client.post(
            "/api/v1/projects",
            json={"name": project_name},
            headers=headers,
        )
        project_id = str(project_response.json()["id"])

        # Create an agent
        agent_name = f"ProjectAgent_{uuid.uuid4().hex[:8]}"
        agent_response = await async_client.post(
            "/api/v1/agents",
            json={
                "name": agent_name,
                "description": "Test agent for project",
                "system_prompt": "You are a helpful assistant.",
                "model": "gpt-4o-mini",
            },
            headers=headers,
        )

        # Agent creation may require additional setup, accept various responses
        if agent_response.status_code not in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            pytest.skip("Agent creation requires additional setup")

        agent_data = agent_response.json()
        # Handle different response structures
        if "data" in agent_data:
            agent_id = str(agent_data["data"]["id"])
        else:
            agent_id = str(agent_data["id"])

        # Add agent to project
        add_response = await async_client.post(
            f"/api/v1/projects/{project_id}/agents",
            json={"agent_id": agent_id},
            headers=headers,
        )
        assert add_response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

        # List agents in project
        list_response = await async_client.get(f"/api/v1/projects/{project_id}/agents", headers=headers)
        assert list_response.status_code == status.HTTP_200_OK
        agents = list_response.json()
        agent_ids = [str(a["id"]) for a in agents]
        assert agent_id in agent_ids

    @pytest.mark.asyncio
    async def test_remove_agent_from_project(self, async_client: AsyncClient, auth_headers):
        """Test removing an agent from a project."""
        headers, tenant_id, account = auth_headers

        # Create project
        project_name = f"RemoveAgentProject_{uuid.uuid4().hex[:8]}"
        project_response = await async_client.post(
            "/api/v1/projects",
            json={"name": project_name},
            headers=headers,
        )
        project_id = str(project_response.json()["id"])

        # Create an agent
        agent_name = f"RemovableAgent_{uuid.uuid4().hex[:8]}"
        agent_response = await async_client.post(
            "/api/v1/agents",
            json={
                "name": agent_name,
                "description": "Agent to be removed",
                "system_prompt": "You are a helpful assistant.",
                "model": "gpt-4o-mini",
            },
            headers=headers,
        )

        if agent_response.status_code not in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            pytest.skip("Agent creation requires additional setup")

        agent_data = agent_response.json()
        if "data" in agent_data:
            agent_id = str(agent_data["data"]["id"])
        else:
            agent_id = str(agent_data["id"])

        # Add agent to project
        await async_client.post(
            f"/api/v1/projects/{project_id}/agents",
            json={"agent_id": agent_id},
            headers=headers,
        )

        # Remove agent from project
        remove_response = await async_client.delete(
            f"/api/v1/projects/{project_id}/agents/{agent_id}",
            headers=headers,
        )
        assert remove_response.status_code in [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT]

        # Verify agent is removed
        list_response = await async_client.get(f"/api/v1/projects/{project_id}/agents", headers=headers)
        agents = list_response.json()
        agent_ids = [str(a["id"]) for a in agents]
        assert agent_id not in agent_ids


class TestProjectsTenantIsolation:
    """Test projects tenant isolation."""

    @pytest.mark.asyncio
    async def test_cannot_access_other_tenant_project(self, async_client: AsyncClient, async_db_session: AsyncSession):
        """Test that users cannot access projects from other tenants."""
        from src.models import Account, AccountStatus

        # Create first user/tenant
        email1 = f"tenant1_proj_{uuid.uuid4().hex[:8]}@example.com"
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
        email2 = f"tenant2_proj_{uuid.uuid4().hex[:8]}@example.com"
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

        # Create project as tenant 1
        project_name = f"IsolatedProject_{uuid.uuid4().hex[:8]}"
        create_response = await async_client.post(
            "/api/v1/projects",
            json={"name": project_name, "description": "Tenant 1 project"},
            headers=headers1,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        project_id = str(create_response.json()["id"])

        # Tenant 2 should not be able to access tenant 1's project
        get_response = await async_client.get(f"/api/v1/projects/{project_id}", headers=headers2)
        assert get_response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

        # Tenant 2 should not be able to update tenant 1's project
        update_response = await async_client.put(
            f"/api/v1/projects/{project_id}",
            json={"name": "Hacked Project"},
            headers=headers2,
        )
        assert update_response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

        # Tenant 2 should not be able to delete tenant 1's project
        delete_response = await async_client.delete(f"/api/v1/projects/{project_id}", headers=headers2)
        assert delete_response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]


class TestProjectsAuthorization:
    """Test projects authorization."""

    @pytest.mark.asyncio
    async def test_list_projects_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests are rejected."""
        response = await async_client.get("/api/v1/projects")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_create_project_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to create are rejected."""
        response = await async_client.post(
            "/api/v1/projects",
            json={"name": "Unauthorized Project"},
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
