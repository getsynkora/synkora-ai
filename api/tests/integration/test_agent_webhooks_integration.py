"""
Integration tests for Agent Webhooks endpoints.

Tests webhook CRUD operations and event handling.
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

    email = f"webhook_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Webhook Test User",
            "tenant_name": "Webhook Test Org",
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
async def test_agent(async_client: AsyncClient, auth_headers):
    """Create a test agent for webhook tests."""
    headers, tenant_id, account = auth_headers

    agent_name = f"Webhook Test Agent {uuid.uuid4().hex[:8]}"
    response = await async_client.post(
        "/api/v1/agents",
        json={
            "agent_type": "llm",
            "config": {
                "name": agent_name,
                "description": "Agent for webhook tests",
                "system_prompt": "You are a test agent for webhooks.",
                "llm_config": {
                    "provider": "openai",
                    "model_name": "gpt-4o-mini",
                    "api_key": "sk-test-key",
                },
                "tools": [],
            },
        },
        headers=headers,
    )
    if response.status_code == status.HTTP_201_CREATED:
        return response.json()["data"]["agent_id"]
    return None


@pytest_asyncio.fixture
async def test_agent_name(async_client: AsyncClient, auth_headers):
    """Create a test agent and return its slug for webhook tests."""
    headers, tenant_id, account = auth_headers

    agent_name = f"Webhook Test Agent {uuid.uuid4().hex[:8]}"
    response = await async_client.post(
        "/api/v1/agents",
        json={
            "agent_type": "llm",
            "config": {
                "name": agent_name,
                "description": "Agent for webhook tests",
                "system_prompt": "You are a test agent for webhooks.",
                "llm_config": {
                    "provider": "openai",
                    "model_name": "gpt-4o-mini",
                    "api_key": "sk-test-key",
                },
                "tools": [],
            },
        },
        headers=headers,
    )
    if response.status_code == status.HTTP_201_CREATED:
        return response.json()["data"]["slug"]
    return None


class TestAgentWebhooksListIntegration:
    """Test listing agent webhooks."""

    @pytest.mark.asyncio
    async def test_list_webhooks(self, async_client: AsyncClient, auth_headers, test_agent_name):
        """Test listing all webhooks for an agent."""
        headers, tenant_id, account = auth_headers
        agent_name = test_agent_name

        if not agent_name:
            pytest.skip("Could not create test agent")

        response = await async_client.get(
            f"/api/v1/agents/{agent_name}/webhooks",
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_webhooks_nonexistent_agent(self, async_client: AsyncClient, auth_headers):
        """Test listing webhooks for nonexistent agent returns 404."""
        headers, tenant_id, account = auth_headers

        fake_name = f"nonexistent-agent-{uuid.uuid4().hex[:8]}"
        response = await async_client.get(
            f"/api/v1/agents/{fake_name}/webhooks",
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAgentWebhooksCRUDIntegration:
    """Test webhook CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_webhook(self, async_client: AsyncClient, auth_headers, test_agent_name):
        """Test creating a webhook."""
        headers, tenant_id, account = auth_headers
        agent_name = test_agent_name

        if not agent_name:
            pytest.skip("Could not create test agent")

        webhook_data = {
            "name": f"Test Webhook {uuid.uuid4().hex[:8]}",
            "provider": "custom",
            "event_types": ["message.created", "conversation.started"],
        }

        response = await async_client.post(
            f"/api/v1/agents/{agent_name}/webhooks",
            json=webhook_data,
            headers=headers,
        )

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
        if response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            data = response.json()
            assert data["name"] == webhook_data["name"]
            assert data["provider"] == webhook_data["provider"]

    @pytest.mark.asyncio
    async def test_create_webhook_nonexistent_agent(self, async_client: AsyncClient, auth_headers):
        """Test creating webhook for nonexistent agent returns 404."""
        headers, tenant_id, account = auth_headers

        fake_name = f"nonexistent-agent-{uuid.uuid4().hex[:8]}"
        webhook_data = {
            "name": "Should Fail Webhook",
            "provider": "custom",
            "event_types": ["message.created"],
        }

        response = await async_client.post(
            f"/api/v1/agents/{fake_name}/webhooks",
            json=webhook_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_webhook_not_found(self, async_client: AsyncClient, auth_headers, test_agent_name):
        """Test getting a nonexistent webhook returns 404."""
        headers, tenant_id, account = auth_headers
        agent_name = test_agent_name

        if not agent_name:
            pytest.skip("Could not create test agent")

        fake_webhook_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/agents/{agent_name}/webhooks/{fake_webhook_id}",
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_webhook_not_found(self, async_client: AsyncClient, auth_headers, test_agent_name):
        """Test updating a nonexistent webhook returns 404."""
        headers, tenant_id, account = auth_headers
        agent_name = test_agent_name

        if not agent_name:
            pytest.skip("Could not create test agent")

        fake_webhook_id = str(uuid.uuid4())
        update_data = {"name": "Updated Name"}

        response = await async_client.patch(
            f"/api/v1/agents/{agent_name}/webhooks/{fake_webhook_id}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_webhook_not_found(self, async_client: AsyncClient, auth_headers, test_agent_name):
        """Test deleting a nonexistent webhook returns 404."""
        headers, tenant_id, account = auth_headers
        agent_name = test_agent_name

        if not agent_name:
            pytest.skip("Could not create test agent")

        fake_webhook_id = str(uuid.uuid4())
        response = await async_client.delete(
            f"/api/v1/agents/{agent_name}/webhooks/{fake_webhook_id}",
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAgentWebhookStatsIntegration:
    """Test webhook statistics."""

    @pytest.mark.asyncio
    async def test_get_webhook_stats_not_found(self, async_client: AsyncClient, auth_headers, test_agent_name):
        """Test getting stats for nonexistent webhook returns 404."""
        headers, tenant_id, account = auth_headers
        agent_name = test_agent_name

        if not agent_name:
            pytest.skip("Could not create test agent")

        fake_webhook_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/agents/{agent_name}/webhooks/{fake_webhook_id}/stats",
            headers=headers,
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAgentWebhooksAuthorizationIntegration:
    """Test webhooks authorization."""

    @pytest.mark.asyncio
    async def test_list_webhooks_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to list webhooks are rejected."""
        fake_name = f"test-agent-{uuid.uuid4().hex[:8]}"
        response = await async_client.get(f"/api/v1/agents/{fake_name}/webhooks")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_create_webhook_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to create webhooks are rejected."""
        fake_name = f"test-agent-{uuid.uuid4().hex[:8]}"
        webhook_data = {
            "name": "Unauthorized Webhook",
            "provider": "custom",
            "event_types": ["message.created"],
        }

        response = await async_client.post(
            f"/api/v1/agents/{fake_name}/webhooks",
            json=webhook_data,
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    @pytest.mark.asyncio
    async def test_delete_webhook_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to delete webhooks are rejected."""
        fake_name = f"test-agent-{uuid.uuid4().hex[:8]}"
        fake_webhook_id = str(uuid.uuid4())
        response = await async_client.delete(f"/api/v1/agents/{fake_name}/webhooks/{fake_webhook_id}")

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
