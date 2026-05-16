"""
Integration tests for Agent CRUD operations.

Tests the complete lifecycle of agents: create, list, get, update, delete, clone.
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

    # Create user and get token
    email = f"test_agent_crud_{uuid.uuid4()}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Agent CRUD Test User",
            "tenant_name": "Agent CRUD Test Org",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    tenant_id = data["data"]["tenant"]["id"]
    account_id = data["data"]["account"]["id"]

    # Manually activate account for testing (simulating email verification)
    result = await async_db_session.execute(select(Account).filter_by(email=email))
    account = result.scalar_one()
    account.status = AccountStatus.ACTIVE
    await async_db_session.commit()

    # Login to get token
    login_response = await async_client.post(
        "/console/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == status.HTTP_200_OK
    token = login_response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}, tenant_id, account_id


class TestAgentsCRUDIntegration:
    """Test Agent CRUD operations."""

    @pytest.mark.asyncio
    async def test_agent_full_lifecycle(self, async_client: AsyncClient, auth_headers):
        """Test complete agent lifecycle: create -> get -> update -> delete."""
        headers, tenant_id, account_id = auth_headers
        agent_name = f"TestAgent_{uuid.uuid4().hex[:8]}"

        # 1. Create Agent
        create_response = await async_client.post(
            "/api/v1/agents/",
            json={
                "agent_type": "llm",
                "config": {
                    "name": agent_name,
                    "description": "Test agent for integration tests",
                    "system_prompt": "You are a helpful assistant.",
                    "llm_config": {
                        "provider": "openai",
                        "model_name": "gpt-3.5-turbo",
                        "api_key": "sk-test-key-12345",
                        "temperature": 0.7,
                    },
                    "tools": [],
                },
            },
            headers=headers,
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        create_data = create_response.json()
        assert create_data["success"] is True
        assert create_data["data"]["agent_name"] == agent_name
        agent_slug = create_data["data"]["slug"]
        assert agent_slug  # slug must be present in create response

        # 2. Get Agent
        get_response = await async_client.get(f"/api/v1/agents/{agent_slug}", headers=headers)
        assert get_response.status_code == status.HTTP_200_OK
        get_data = get_response.json()
        assert get_data["success"] is True
        assert get_data["data"]["agent_name"] == agent_name
        assert get_data["data"]["description"] == "Test agent for integration tests"

        # 3. List Agents
        list_response = await async_client.get("/api/v1/agents/", headers=headers)
        assert list_response.status_code == status.HTTP_200_OK
        list_data = list_response.json()
        assert list_data["success"] is True
        assert any(a.get("slug") == agent_slug for a in list_data["data"].get("agents_list", []))

        # 4. Update Agent
        update_response = await async_client.put(
            f"/api/v1/agents/{agent_slug}",
            json={
                "description": "Updated description",
                "system_prompt": "You are an updated helpful assistant.",
            },
            headers=headers,
        )
        assert update_response.status_code == status.HTTP_200_OK
        update_data = update_response.json()
        assert update_data["success"] is True

        # Verify update
        verify_response = await async_client.get(f"/api/v1/agents/{agent_slug}", headers=headers)
        verify_data = verify_response.json()
        assert verify_data["data"]["description"] == "Updated description"
        assert verify_data["data"]["system_prompt"] == "You are an updated helpful assistant."

        # 5. Delete Agent
        delete_response = await async_client.delete(f"/api/v1/agents/{agent_slug}", headers=headers)
        assert delete_response.status_code == status.HTTP_200_OK
        delete_data = delete_response.json()
        assert delete_data["success"] is True

        # Verify deletion - agent should not be accessible
        verify_deleted = await async_client.get(f"/api/v1/agents/{agent_slug}", headers=headers)
        assert verify_deleted.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_agent_with_duplicate_name(self, async_client: AsyncClient, auth_headers):
        """Test that creating an agent with duplicate name fails."""
        headers, tenant_id, account_id = auth_headers
        agent_name = f"DuplicateAgent_{uuid.uuid4().hex[:8]}"

        # Create first agent
        first_response = await async_client.post(
            "/api/v1/agents/",
            json={
                "agent_type": "llm",
                "config": {
                    "name": agent_name,
                    "description": "First agent",
                    "system_prompt": "You are a helpful assistant.",
                    "llm_config": {
                        "provider": "openai",
                        "model_name": "gpt-3.5-turbo",
                        "api_key": "sk-test-key",
                        "temperature": 0.7,
                    },
                    "tools": [],
                },
            },
            headers=headers,
        )
        assert first_response.status_code == status.HTTP_201_CREATED

        # Try to create second agent with same name
        second_response = await async_client.post(
            "/api/v1/agents/",
            json={
                "agent_type": "llm",
                "config": {
                    "name": agent_name,
                    "description": "Second agent",
                    "system_prompt": "You are another assistant.",
                    "llm_config": {
                        "provider": "openai",
                        "model_name": "gpt-3.5-turbo",
                        "api_key": "sk-test-key",
                        "temperature": 0.7,
                    },
                    "tools": [],
                },
            },
            headers=headers,
        )
        assert second_response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    async def test_create_agent_with_invalid_type(self, async_client: AsyncClient, auth_headers):
        """Test that creating an agent with invalid type fails."""
        headers, tenant_id, account_id = auth_headers
        agent_name = f"InvalidTypeAgent_{uuid.uuid4().hex[:8]}"

        response = await async_client.post(
            "/api/v1/agents/",
            json={
                "agent_type": "invalid_type",
                "config": {
                    "name": agent_name,
                    "description": "Test agent",
                    "system_prompt": "You are a helpful assistant.",
                    "llm_config": {
                        "provider": "openai",
                        "model_name": "gpt-3.5-turbo",
                        "api_key": "sk-test-key",
                        "temperature": 0.7,
                    },
                    "tools": [],
                },
            },
            headers=headers,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_get_nonexistent_agent(self, async_client: AsyncClient, auth_headers):
        """Test that getting a nonexistent agent returns 404."""
        headers, tenant_id, account_id = auth_headers

        response = await async_client.get("/api/v1/agents/nonexistent_agent_name", headers=headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_nonexistent_agent(self, async_client: AsyncClient, auth_headers):
        """Test that updating a nonexistent agent returns 404."""
        headers, tenant_id, account_id = auth_headers

        response = await async_client.put(
            "/api/v1/agents/nonexistent_agent_name",
            json={"description": "Updated description"},
            headers=headers,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_agent_pagination(self, async_client: AsyncClient, auth_headers):
        """Test agent list pagination."""
        headers, tenant_id, account_id = auth_headers

        # Create multiple agents (stop if we hit plan limit)
        agent_names = []
        created_count = 0
        for i in range(5):
            agent_name = f"PaginationAgent_{uuid.uuid4().hex[:8]}_{i}"
            create_resp = await async_client.post(
                "/api/v1/agents/",
                json={
                    "agent_type": "llm",
                    "config": {
                        "name": agent_name,
                        "description": f"Test agent {i}",
                        "system_prompt": "You are a helpful assistant.",
                        "llm_config": {
                            "provider": "openai",
                            "model_name": "gpt-3.5-turbo",
                            "api_key": "sk-test-key",
                            "temperature": 0.7,
                        },
                        "tools": [],
                    },
                },
                headers=headers,
            )
            # Accept 201 (created) or 403 (plan limit reached)
            if create_resp.status_code == status.HTTP_403_FORBIDDEN:
                # Plan limit reached, stop creating more agents
                break
            assert create_resp.status_code == status.HTTP_201_CREATED
            agent_names.append(agent_name)
            created_count += 1

        # Skip pagination assertions if we couldn't create any agents
        if created_count == 0:
            pytest.skip("Plan limit reached - could not create test agents")

        # Test pagination - page 1 with page_size 2
        page1_response = await async_client.get("/api/v1/agents/?page=1&page_size=2", headers=headers)
        assert page1_response.status_code == status.HTTP_200_OK
        page1_data = page1_response.json()
        assert "pagination" in page1_data["data"]
        # Verify pagination structure exists
        assert "page" in page1_data["data"]["pagination"]
        assert "total" in page1_data["data"]["pagination"]

        # Test pagination - page 2 (if we have enough agents)
        if created_count > 2:
            page2_response = await async_client.get("/api/v1/agents/?page=2&page_size=2", headers=headers)
            assert page2_response.status_code == status.HTTP_200_OK
            page2_data = page2_response.json()
            assert "agents_list" in page2_data["data"]

    @pytest.mark.asyncio
    async def test_agent_clone(self, async_client: AsyncClient, auth_headers):
        """Test agent cloning functionality."""
        headers, tenant_id, account_id = auth_headers
        original_agent_name = f"OriginalAgent_{uuid.uuid4().hex[:8]}"
        cloned_agent_name = f"ClonedAgent_{uuid.uuid4().hex[:8]}"

        # Create original agent
        create_response = await async_client.post(
            "/api/v1/agents/",
            json={
                "agent_type": "llm",
                "config": {
                    "name": original_agent_name,
                    "description": "Original agent to clone",
                    "system_prompt": "You are the original assistant.",
                    "llm_config": {
                        "provider": "openai",
                        "model_name": "gpt-3.5-turbo",
                        "api_key": "sk-test-key",
                        "temperature": 0.7,
                    },
                    "tools": [],
                },
            },
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        original_slug = create_response.json()["data"]["slug"]

        # Clone the agent
        clone_response = await async_client.post(
            f"/api/v1/agents/{original_slug}/clone",
            json={
                "new_name": cloned_agent_name,
                "clone_tools": True,
                "clone_knowledge_bases": False,
                "clone_sub_agents": False,
                "clone_workflows": False,
            },
            headers=headers,
        )
        assert clone_response.status_code == status.HTTP_201_CREATED
        clone_data = clone_response.json()
        assert clone_data["success"] is True
        assert clone_data["data"]["agent_name"] == cloned_agent_name
        cloned_slug = clone_data["data"]["slug"]

        # Verify cloned agent exists
        get_response = await async_client.get(f"/api/v1/agents/{cloned_slug}", headers=headers)
        assert get_response.status_code == status.HTTP_200_OK
        cloned_data = get_response.json()
        assert cloned_data["data"]["description"] == "Original agent to clone"

    @pytest.mark.asyncio
    async def test_agent_stats(self, async_client: AsyncClient, auth_headers):
        """Test agent statistics endpoint."""
        headers, tenant_id, account_id = auth_headers
        agent_name = f"StatsAgent_{uuid.uuid4().hex[:8]}"

        # Create agent
        create_resp = await async_client.post(
            "/api/v1/agents/",
            json={
                "agent_type": "llm",
                "config": {
                    "name": agent_name,
                    "description": "Agent for stats testing",
                    "system_prompt": "You are a helpful assistant.",
                    "llm_config": {
                        "provider": "openai",
                        "model_name": "gpt-3.5-turbo",
                        "api_key": "sk-test-key",
                        "temperature": 0.7,
                    },
                    "tools": [],
                },
            },
            headers=headers,
        )
        agent_slug = create_resp.json()["data"]["slug"]

        # Get agent stats
        stats_response = await async_client.get(f"/api/v1/agents/{agent_slug}/stats", headers=headers)
        assert stats_response.status_code == status.HTTP_200_OK
        stats_data = stats_response.json()
        assert stats_data["success"] is True
        assert stats_data["data"]["agent_name"] == agent_name
        assert "execution_count" in stats_data["data"]
        assert "success_rate" in stats_data["data"]

    @pytest.mark.asyncio
    async def test_agent_reset(self, async_client: AsyncClient, auth_headers):
        """Test agent reset functionality."""
        headers, tenant_id, account_id = auth_headers
        agent_name = f"ResetAgent_{uuid.uuid4().hex[:8]}"

        # Create agent
        create_resp = await async_client.post(
            "/api/v1/agents/",
            json={
                "agent_type": "llm",
                "config": {
                    "name": agent_name,
                    "description": "Agent for reset testing",
                    "system_prompt": "You are a helpful assistant.",
                    "llm_config": {
                        "provider": "openai",
                        "model_name": "gpt-3.5-turbo",
                        "api_key": "sk-test-key",
                        "temperature": 0.7,
                    },
                    "tools": [],
                },
            },
            headers=headers,
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        agent_slug = create_resp.json()["data"]["slug"]

        # Reset agent
        reset_response = await async_client.post(f"/api/v1/agents/{agent_slug}/reset", headers=headers)
        assert reset_response.status_code == status.HTTP_200_OK
        reset_data = reset_response.json()
        assert reset_data["success"] is True

    @pytest.mark.asyncio
    async def test_update_agent_public_status(self, async_client: AsyncClient, auth_headers):
        """Test updating agent public status."""
        headers, tenant_id, account_id = auth_headers
        agent_name = f"PublicAgent_{uuid.uuid4().hex[:8]}"

        # Create agent
        create_resp = await async_client.post(
            "/api/v1/agents/",
            json={
                "agent_type": "llm",
                "config": {
                    "name": agent_name,
                    "description": "Agent for public status testing",
                    "system_prompt": "You are a helpful assistant.",
                    "llm_config": {
                        "provider": "openai",
                        "model_name": "gpt-3.5-turbo",
                        "api_key": "sk-test-key",
                        "temperature": 0.7,
                    },
                    "tools": [],
                },
            },
            headers=headers,
        )
        agent_slug = create_resp.json()["data"]["slug"]

        # Update to public
        update_response = await async_client.put(
            f"/api/v1/agents/{agent_slug}",
            json={"is_public": True, "category": "general", "tags": ["test", "public"]},
            headers=headers,
        )
        assert update_response.status_code == status.HTTP_200_OK

        # Verify update
        get_response = await async_client.get(f"/api/v1/agents/{agent_slug}", headers=headers)
        get_data = get_response.json()
        assert get_data["data"]["is_public"] is True
        assert get_data["data"]["category"] == "general"
        assert "test" in get_data["data"]["tags"]


class TestAgentsCategoriesIntegration:
    """Test Agent categories endpoint."""

    @pytest.mark.asyncio
    async def test_list_agent_categories(self, async_client: AsyncClient, auth_headers):
        """Test listing agent categories."""
        headers, tenant_id, account_id = auth_headers

        # Create a public agent with category
        agent_name = f"CategoryAgent_{uuid.uuid4().hex[:8]}"
        await async_client.post(
            "/api/v1/agents/",
            json={
                "agent_type": "llm",
                "is_public": True,
                "category": "productivity",
                "config": {
                    "name": agent_name,
                    "description": "Agent for category testing",
                    "system_prompt": "You are a helpful assistant.",
                    "llm_config": {
                        "provider": "openai",
                        "model_name": "gpt-3.5-turbo",
                        "api_key": "sk-test-key",
                        "temperature": 0.7,
                    },
                    "tools": [],
                },
            },
            headers=headers,
        )

        # Make agent public
        await async_client.put(
            f"/api/v1/agents/{agent_name}",
            json={"is_public": True, "category": "productivity"},
            headers=headers,
        )

        # List categories
        categories_response = await async_client.get("/api/v1/agents/categories", headers=headers)
        assert categories_response.status_code == status.HTTP_200_OK
        categories_data = categories_response.json()
        assert categories_data["success"] is True
        assert "categories" in categories_data["data"]
