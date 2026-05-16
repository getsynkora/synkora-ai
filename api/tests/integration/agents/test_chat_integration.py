import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.agent_llm_config import AgentLLMConfig


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, async_db_session: AsyncSession):
    from src.models import Account, AccountStatus

    # Create user and get token
    email = f"test_integration_{uuid.uuid4()}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Integration Test User",
            "tenant_name": "Integration Test Org",
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


class TestChatIntegration:
    @pytest.mark.asyncio
    async def test_chat_stream_integration(
        self, async_client: AsyncClient, async_db_session: AsyncSession, auth_headers
    ):
        headers, tenant_id, account_id = auth_headers

        # Create an agent in the DB for this tenant
        agent_name = f"integration_agent_{uuid.uuid4().hex[:8]}"

        # Create agent
        agent = Agent(
            agent_name=agent_name,
            slug=agent_name,
            tenant_id=uuid.UUID(tenant_id),
            description="Integration Test Agent",
            system_prompt="You are a helpful assistant.",
            agent_type="llm",
            llm_config={"provider": "openai", "model": "gpt-3.5-turbo", "api_key": "sk-test-key", "temperature": 0.7},
            is_public=False,
            status="ACTIVE",
        )
        async_db_session.add(agent)
        await async_db_session.commit()
        await async_db_session.refresh(agent)

        # Create default LLM config - append to relationship instead of setting agent_id
        # This ensures the relationship is properly connected in SQLAlchemy's identity map
        llm_config = AgentLLMConfig(
            tenant_id=uuid.UUID(tenant_id),
            name="Default Config",
            provider="openai",
            model_name="gpt-3.5-turbo",
            api_key="sk-test-key",
            is_default=True,
            enabled=True,
        )
        agent.llm_configs.append(llm_config)
        await async_db_session.commit()
        # Expire cache so controller gets fresh data with relationships from DB
        async_db_session.expire_all()

        # Patch services to avoid real API calls
        from unittest.mock import AsyncMock, MagicMock, patch

        # We patch where services are used in the controller
        with (
            patch("src.controllers.agents.chat.advanced_prompt_scanner") as mock_scanner,
            patch("src.controllers.agents.chat.chat_stream_service") as mock_chat_stream,
            patch("src.services.billing.ChatBillingService") as mock_billing_cls,
        ):
            # Mock scanner to return safe
            mock_scanner.scan_comprehensive_async = AsyncMock(
                return_value={
                    "is_safe": True,
                    "risk_score": 0.0,
                    "threat_level": "SAFE",
                    "detections": [],
                    "layers_triggered": 0,
                }
            )

            # Mock billing service to return valid
            mock_billing_instance = MagicMock()
            mock_billing_result = MagicMock()
            mock_billing_result.is_valid = True
            mock_billing_instance.validate_chat_request = AsyncMock(return_value=mock_billing_result)
            mock_billing_cls.return_value = mock_billing_instance

            # Mock the stream response - return the generator directly, not a coroutine
            async def mock_stream_generator():
                yield 'data: {"type": "message", "content": "Hello"}\n\n'
                yield 'data: {"type": "done"}\n\n'

            mock_chat_stream.stream_agent_response = MagicMock(return_value=mock_stream_generator())

            # Make the request
            response = await async_client.post(
                "/api/v1/agents/chat/stream",
                json={
                    "agent_slug": agent_name,
                    "message": "Hello",
                    "conversation_history": [],
                    "conversation_id": None,
                    "attachments": None,
                    "llm_config_id": None,
                },
                headers=headers,
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
