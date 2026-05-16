import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, async_db_session: AsyncSession):
    from src.models import Account, AccountStatus

    # Create user and get token
    email = f"test_llm_{uuid.uuid4()}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "LLM Config Test User",
            "tenant_name": "LLM Config Test Org",
        },
    )
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
    token = login_response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}, tenant_id, account_id


class TestLLMConfigsIntegration:
    @pytest.mark.asyncio
    async def test_llm_config_lifecycle(self, async_client: AsyncClient, async_db_session: AsyncSession, auth_headers):
        headers, tenant_id, account_id = auth_headers

        # 1. Create Agent
        agent_name = f"LLMAgent_{uuid.uuid4().hex[:8]}"
        agent = Agent(
            agent_name=agent_name,
            slug=agent_name,
            tenant_id=uuid.UUID(tenant_id),
            description="Agent for LLM Config Tests",
            system_prompt="You are a bot.",
            agent_type="llm",
            llm_config={"provider": "openai", "model": "gpt-3.5-turbo", "api_key": "sk-test-key", "temperature": 0.7},
            is_public=False,
            status="ACTIVE",
        )
        async_db_session.add(agent)
        await async_db_session.commit()
        await async_db_session.refresh(agent)

        # 2. Create LLM Config
        response = await async_client.post(
            f"/api/v1/agents/{agent_name}/llm-configs",
            json={
                "name": "New Config",
                "provider": "anthropic",
                "model_name": "claude-2",
                "api_key": "sk-ant-test",
                "temperature": 0.5,
                "is_default": False,
            },
            headers=headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "New Config"
        assert data["provider"] == "anthropic"
        config_id = data["id"]

        # 3. Get LLM Config
        response = await async_client.get(f"/api/v1/agents/{agent_name}/llm-configs/{config_id}", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == config_id
        assert data["name"] == "New Config"

        # 4. List LLM Configs
        response = await async_client.get(f"/api/v1/agents/{agent_name}/llm-configs", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
        ids = [c["id"] for c in data]
        assert config_id in ids

        # 5. Update LLM Config
        response = await async_client.patch(
            f"/api/v1/agents/{agent_name}/llm-configs/{config_id}",
            json={"name": "Updated Config", "temperature": 0.9},
            headers=headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Config"
        assert data["temperature"] == 0.9

        # 6. Set Default
        response = await async_client.post(
            f"/api/v1/agents/{agent_name}/llm-configs/{config_id}/set-default", headers=headers
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_default"] is True

        # Create another config so we can delete the default one
        await async_client.post(
            f"/api/v1/agents/{agent_name}/llm-configs",
            json={
                "name": "Fallback Config",
                "provider": "openai",
                "model_name": "gpt-3.5-turbo",
                "api_key": "sk-test-key",
                "is_default": False,
            },
            headers=headers,
        )

        # 7. Delete LLM Config
        response = await async_client.delete(f"/api/v1/agents/{agent_name}/llm-configs/{config_id}", headers=headers)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deletion
        response = await async_client.get(f"/api/v1/agents/{agent_name}/llm-configs/{config_id}", headers=headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
