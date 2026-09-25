"""
Unit tests for AgentLoaderService JEV branch fallback (Task 2.4).

Verifies that when TypeSafe returns an error, routing falls back to
ModelRouter gracefully — no exception, no 500.
"""

import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.modules.setdefault("httpx", MagicMock())


def _make_db_agent(routing_mode="jev"):
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.tenant_id = uuid.uuid4()
    agent.agent_name = "test-jev-agent"
    agent.description = "A test agent"
    agent.routing_mode = routing_mode
    agent.routing_config = {
        "jev": {
            "features": {"model_routing": True, "tool_filtering": True},
            "model_tier_map": {"standard": "sonnet-uuid"},
        }
    }
    return agent


class TestJevLoaderFallback:
    @pytest.mark.asyncio
    async def test_fallback_when_typesafe_raises_request_error(self):
        """TypeSafe API raises httpx.RequestError → falls back to IntentClassifier + ModelRouter."""
        import httpx

        from src.services.agents.routing.jev_router import JevRoutingError

        db_agent = _make_db_agent()

        # Simulate: credentials resolve OK, but the evaluate() call fails
        mock_credentials = {"api_key": "test-key", "base_url": None}

        with (
            patch(
                "src.services.agents.agent_loader_service.AgentLoaderService._load_llm_configs_cached",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "src.services.agents.routing.jev_router.run_jev_routing",
                new=AsyncMock(side_effect=JevRoutingError("connection refused")),
            ),
            patch(
                "src.services.agents.credential_resolver.CredentialResolver",
            ) as MockResolver,
            patch(
                "src.core.typesafe_client.TypeSafeClient",
            ),
            patch(
                "src.services.agents.agent_loader_service.AgentLoaderService._run_routing",
                new=AsyncMock(return_value=(MagicMock(), "sonnet-uuid", [])),
            ) as mock_fallback,
        ):
            MockResolver.return_value.get_typesafe_credentials = AsyncMock(return_value=mock_credentials)

            from src.services.agents.agent_loader_service import AgentLoaderService

            service = object.__new__(AgentLoaderService)

            result = await service._run_jev_routing_with_fallback(
                db_agent=db_agent,
                query="test query",
                conversation_history=None,
                db=MagicMock(),
                requesting_tenant_id="",
            )

        # Should return 5-tuple with None for allowed_tool_names and jev_client
        routing_decision, config_id, fallback_ids, allowed_tool_names, jev_client = result
        assert config_id == "sonnet-uuid"
        assert allowed_tool_names is None
        assert jev_client is None
        mock_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fallback_when_no_credentials(self):
        """No TypeSafe credentials → falls back to IntentClassifier + ModelRouter."""
        db_agent = _make_db_agent()

        with (
            patch(
                "src.services.agents.credential_resolver.CredentialResolver",
            ) as MockResolver,
            patch(
                "src.services.agents.agent_loader_service.AgentLoaderService._run_routing",
                new=AsyncMock(return_value=(MagicMock(), "sonnet-uuid", [])),
            ) as mock_fallback,
        ):
            MockResolver.return_value.get_typesafe_credentials = AsyncMock(return_value=None)

            from src.services.agents.agent_loader_service import AgentLoaderService

            service = object.__new__(AgentLoaderService)

            result = await service._run_jev_routing_with_fallback(
                db_agent=db_agent,
                query="test query",
                conversation_history=None,
                db=MagicMock(),
                requesting_tenant_id="",
            )

        routing_decision, config_id, fallback_ids, allowed_tool_names, jev_client = result
        assert config_id == "sonnet-uuid"
        assert allowed_tool_names is None
        assert jev_client is None
        mock_fallback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_successful_jev_returns_allowed_tool_names_and_client(self):
        """When JEV succeeds, allowed_tool_names and jev_client are populated."""
        from src.services.agents.routing.jev_router import JevRoutingResult

        db_agent = _make_db_agent()
        mock_credentials = {"api_key": "test-key", "base_url": None}
        mock_jev_result = JevRoutingResult(
            config_id="sonnet-uuid",
            fallback_config_ids=["opus-uuid"],
            allowed_tool_names={"slack_send", "web_search"},
            complexity="moderate",
            model_tier="standard",
        )

        with (
            patch(
                "src.services.agents.agent_loader_service.AgentLoaderService._load_llm_configs_cached",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "src.services.agents.routing.jev_router.run_jev_routing",
                new=AsyncMock(return_value=mock_jev_result),
            ),
            patch(
                "src.services.agents.credential_resolver.CredentialResolver",
            ) as MockResolver,
            patch(
                "src.core.typesafe_client.TypeSafeClient",
            ) as MockClient,
        ):
            MockResolver.return_value.get_typesafe_credentials = AsyncMock(return_value=mock_credentials)
            mock_client_instance = MagicMock()
            MockClient.return_value = mock_client_instance

            from src.services.agents.agent_loader_service import AgentLoaderService

            service = object.__new__(AgentLoaderService)

            result = await service._run_jev_routing_with_fallback(
                db_agent=db_agent,
                query="test query",
                conversation_history=None,
                db=MagicMock(),
                requesting_tenant_id="",
            )

        routing_decision, config_id, fallback_ids, allowed_tool_names, jev_client = result
        assert config_id == "sonnet-uuid"
        assert allowed_tool_names == {"slack_send", "web_search"}
        assert jev_client is mock_client_instance
