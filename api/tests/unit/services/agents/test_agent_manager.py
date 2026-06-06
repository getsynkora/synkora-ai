from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.agent_manager import AgentManager
from src.services.agents.base_agent import BaseAgent
from src.services.agents.config import AgentConfig, ModelConfig, WorkflowConfig


class TestAgentManager:
    @pytest.fixture
    def mock_registry(self):
        registry = MagicMock()
        registry.__contains__.return_value = False
        registry.contains.return_value = False
        return registry

    @pytest.fixture
    def manager(self, mock_registry):
        return AgentManager(registry=mock_registry)

    @pytest.fixture
    def mock_agent_config(self):
        return AgentConfig(
            name="TestAgent", description="Test", llm_config=ModelConfig(provider="openai", model_name="gpt-4")
        )

    @pytest.fixture
    def mock_agent_class(self):
        mock_class = MagicMock()
        mock_instance = MagicMock(spec=BaseAgent)
        mock_class.return_value = mock_instance
        return mock_class

    @pytest.mark.asyncio
    async def test_create_agent_success(self, manager, mock_agent_config, mock_agent_class, mock_registry):
        with patch("src.services.agents.agent_manager.get_api_key_manager") as mock_key_manager:
            mock_key_manager.return_value.encrypt_api_key.return_value = "encrypted_key"

            agent = await manager.create_agent(mock_agent_config, mock_agent_class, api_key="secret_key")

            mock_agent_class.assert_called_once()
            agent.initialize_client.assert_called_with("secret_key")
            mock_registry.register.assert_called_once_with(agent, tenant_id="", runtime_id=None)
            assert mock_agent_config.llm_config.api_key == "encrypted_key"

    @pytest.mark.asyncio
    async def test_create_agent_duplicate(self, manager, mock_agent_config, mock_agent_class, mock_registry):
        mock_registry.contains.return_value = True

        with pytest.raises(ValueError, match="already exists"):
            await manager.create_agent(mock_agent_config, mock_agent_class)

    @pytest.mark.asyncio
    async def test_execute_agent_success(self, manager, mock_registry):
        mock_agent = AsyncMock()
        mock_agent.run.return_value = {"status": "success", "result": "data"}
        mock_registry.get.return_value = mock_agent

        result = await manager.execute_agent("TestAgent", {"input": "data"})

        assert result["status"] == "success"
        mock_agent.run.assert_called_once_with({"input": "data"})

    @pytest.mark.asyncio
    async def test_execute_agent_not_found(self, manager, mock_registry):
        mock_registry.get.return_value = None

        with pytest.raises(KeyError, match="not found"):
            await manager.execute_agent("UnknownAgent", {})

    @pytest.mark.asyncio
    async def test_execute_workflow_sequential(self, manager):
        workflow_config = WorkflowConfig(
            name="SeqWorkflow",
            description="Sequential workflow",
            execution_mode="sequential",
            agents=["Agent1", "Agent2"],
        )

        with patch.object(manager, "_execute_with_retry") as mock_exec:
            mock_exec.side_effect = [
                {"status": "success", "result": {"out": 1}},
                {"status": "success", "result": {"out": 2}},
            ]

            result = await manager.execute_workflow(workflow_config, {"start": 0})

            assert result["status"] == "success"
            assert len(result["results"]) == 2
            # Second agent should receive output of first
            mock_exec.assert_called_with("Agent2", {"out": 1}, workflow_config.max_retries)

    @pytest.mark.asyncio
    async def test_execute_workflow_parallel(self, manager):
        workflow_config = WorkflowConfig(
            name="ParWorkflow", description="Parallel workflow", execution_mode="parallel", agents=["Agent1", "Agent2"]
        )

        with patch.object(manager, "_execute_with_retry") as mock_exec:
            mock_exec.return_value = {"status": "success"}

            result = await manager.execute_workflow(workflow_config, {"data": 1})

            assert result["status"] == "success"
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_workflow_conditional(self, manager):
        workflow_config = WorkflowConfig(
            name="CondWorkflow",
            description="Conditional workflow",
            execution_mode="conditional",
            agents=["Agent1", "Agent2"],
            routing_logic={"Agent1": {"on_success": "Agent2"}},
        )

        with patch.object(manager, "_execute_conditional_workflow") as mock_cond:
            mock_cond.return_value = [{"status": "success"}]

            result = await manager.execute_workflow(workflow_config, {})

            assert result["status"] == "success"
            mock_cond.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self, manager):
        with patch.object(manager, "execute_agent") as mock_exec:
            mock_exec.return_value = {"status": "success"}

            result = await manager._execute_with_retry("Agent1", {}, 3)

            assert result["status"] == "success"
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_retry_fail_then_success(self, manager):
        with patch.object(manager, "execute_agent") as mock_exec:
            # Fail twice, then succeed
            mock_exec.side_effect = [{"status": "error", "error": "fail1"}, Exception("fail2"), {"status": "success"}]

            result = await manager._execute_with_retry("Agent1", {}, 3)

            assert result["status"] == "success"
            assert mock_exec.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_max_retries(self, manager):
        with patch.object(manager, "execute_agent") as mock_exec:
            mock_exec.return_value = {"status": "error", "error": "fail"}

            result = await manager._execute_with_retry("Agent1", {}, 2)

            assert result["status"] == "error"
            # Initial + 2 retries = 3 calls
            assert mock_exec.call_count == 3

    @pytest.mark.asyncio
    async def test_agent_management_methods(self, manager, mock_registry):
        # Test list
        mock_registry.list_agents.return_value = ["Agent1"]
        assert manager.list_agents() == ["Agent1"]

        # Test delete
        # The delete_agent method calls unregister which is synchronous in the mock unless we make it async
        # Wait, delete_agent IS async in manager: async def delete_agent(self, agent_name: str) -> None:
        # self.registry.unregister(agent_name) is likely sync

        # The original test failed because it expected KeyError but got nothing.
        # This is because we mocked registry.unregister to do nothing by default.

        # Let's make it fail
        mock_registry.unregister.side_effect = KeyError("Not found")

        with pytest.raises(KeyError):
            await manager.delete_agent("Unknown")

        # Test stats
        mock_agent = MagicMock()
        mock_agent.get_stats.return_value = {"stat": 1}
        mock_registry.get.return_value = mock_agent
        assert manager.get_agent_stats("Agent1") == {"stat": 1}
