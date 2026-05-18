"""
Agent manager for orchestrating agent operations.

Provides high-level management of agents, workflows, and multi-agent systems.
"""

import asyncio
import logging
from typing import Any

from src.services.agents.base_agent import BaseAgent
from src.services.agents.config import AgentConfig, WorkflowConfig
from src.services.agents.registry import AgentRegistry, get_registry
from src.services.agents.security import get_api_key_manager

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Manager for orchestrating agent operations.

    Handles agent creation, execution, workflow management, and multi-agent coordination.
    """

    def __init__(self, registry: AgentRegistry | None = None):
        """
        Initialize the agent manager.

        Args:
            registry: Optional agent registry (uses global if not provided)
        """
        self.registry = registry or get_registry()
        logger.info("Agent manager initialized")

    async def create_agent(
        self,
        config: AgentConfig,
        agent_class: type[BaseAgent],
        api_key: str | None = None,
        observability_config: dict[str, Any] | None = None,
        tenant_id: str = "",
    ) -> BaseAgent:
        """
        Create and register a new agent.

        Args:
            config: Agent configuration
            agent_class: Agent class to instantiate
            api_key: Optional API key for the agent
            observability_config: Optional observability configuration
            tenant_id: Tenant identifier for registry scoping

        Returns:
            Created agent instance

        Raises:
            ValueError: If agent already exists
        """
        if self.registry.contains(config.name, tenant_id):
            raise ValueError(f"Agent '{config.name}' already exists")

        # Encrypt API key if provided
        if api_key:
            key_manager = get_api_key_manager()
            encrypted_key = key_manager.encrypt_api_key(api_key)

            # Store encrypted key in config
            config.llm_config.api_key = encrypted_key
            logger.info(f"API key encrypted for agent: {config.name}")

        # Create agent instance with observability config
        agent = agent_class(config, observability_config=observability_config)

        # Initialize client with decrypted API key
        if api_key:
            logger.info(f"🔑 Initializing LLM client for agent '{config.name}' with API key (length: {len(api_key)})")
            try:
                agent.initialize_client(api_key)
                logger.info(f"✅ LLM client initialized successfully for agent '{config.name}'")
            except Exception as e:
                logger.error(f"❌ Failed to initialize LLM client for agent '{config.name}': {e}", exc_info=True)
                raise  # Re-raise to prevent registering broken agent
        else:
            logger.warning(f"⚠️  No API key provided for agent '{config.name}', LLM client will not be initialized")

        # Register agent (tenant-scoped)
        self.registry.register(agent, tenant_id=tenant_id)

        logger.info(f"Created and registered agent: {config.name} (tenant={tenant_id})")
        return agent

    async def execute_agent(self, agent_name: str, input_data: dict[str, Any], tenant_id: str = "") -> dict[str, Any]:
        """
        Execute a registered agent.

        Args:
            agent_name: Name of the agent to execute
            input_data: Input data for the agent
            tenant_id: Tenant identifier for registry scoping

        Returns:
            Execution result

        Raises:
            KeyError: If agent not found
        """
        agent = self.registry.get(agent_name, tenant_id)
        if not agent:
            raise KeyError(f"Agent '{agent_name}' not found")

        return await agent.run(input_data)

    async def execute_workflow(self, workflow_config: WorkflowConfig, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a multi-agent workflow.

        Args:
            workflow_config: Workflow configuration
            input_data: Initial input data

        Returns:
            Workflow execution result
        """
        logger.info(f"Executing workflow: {workflow_config.name}")

        results = []
        current_input = input_data

        try:
            if workflow_config.execution_mode == "sequential":
                # Execute agents sequentially
                for agent_name in workflow_config.agents:
                    result = await self._execute_with_retry(agent_name, current_input, workflow_config.max_retries)
                    results.append(result)

                    # Use output as input for next agent
                    if result["status"] == "success":
                        current_input = result["result"]
                    else:
                        # Stop on error
                        break

            elif workflow_config.execution_mode == "parallel":
                # Execute agents in parallel
                tasks = [
                    self._execute_with_retry(agent_name, input_data, workflow_config.max_retries)
                    for agent_name in workflow_config.agents
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            elif workflow_config.execution_mode == "conditional":
                # Execute with conditional routing
                results = await self._execute_conditional_workflow(workflow_config, input_data)

            else:
                raise ValueError(f"Unknown execution mode: {workflow_config.execution_mode}")

            # Determine overall status
            all_success = all(isinstance(r, dict) and r.get("status") == "success" for r in results)

            return {
                "workflow_name": workflow_config.name,
                "status": "success" if all_success else "partial_success",
                "execution_mode": workflow_config.execution_mode,
                "results": results,
                "agent_count": len(workflow_config.agents),
            }

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            return {
                "workflow_name": workflow_config.name,
                "status": "error",
                "error": str(e),
                "results": results,
            }

    async def _execute_with_retry(
        self, agent_name: str, input_data: dict[str, Any], max_retries: int
    ) -> dict[str, Any]:
        """
        Execute agent with retry logic.

        Args:
            agent_name: Name of the agent
            input_data: Input data
            max_retries: Maximum number of retries

        Returns:
            Execution result
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                result = await self.execute_agent(agent_name, input_data)
                if result["status"] == "success":
                    return result

                last_error = result.get("error", "Unknown error")

                if attempt < max_retries:
                    logger.warning(f"Agent {agent_name} failed (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                    await asyncio.sleep(2**attempt)  # Exponential backoff

            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    logger.warning(f"Agent {agent_name} error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    await asyncio.sleep(2**attempt)

        return {
            "agent_name": agent_name,
            "status": "error",
            "error": f"Failed after {max_retries + 1} attempts: {last_error}",
        }

    async def _execute_conditional_workflow(
        self, workflow_config: WorkflowConfig, input_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Execute workflow with conditional routing.

        Args:
            workflow_config: Workflow configuration
            input_data: Input data

        Returns:
            List of execution results
        """
        results = []
        routing_logic = workflow_config.routing_logic or {}

        current_agent_idx = 0
        current_input = input_data

        while current_agent_idx < len(workflow_config.agents):
            agent_name = workflow_config.agents[current_agent_idx]

            # Execute current agent
            result = await self._execute_with_retry(agent_name, current_input, workflow_config.max_retries)
            results.append(result)

            # Determine next agent based on routing logic
            if result["status"] == "success":
                current_input = result["result"]

                # Check routing logic for next agent
                next_agent = routing_logic.get(agent_name, {}).get("on_success")
                if next_agent:
                    try:
                        current_agent_idx = workflow_config.agents.index(next_agent)
                    except ValueError:
                        logger.warning(f"Next agent '{next_agent}' not found in workflow")
                        break
                else:
                    current_agent_idx += 1
            else:
                # Handle failure routing
                next_agent = routing_logic.get(agent_name, {}).get("on_failure")
                if next_agent:
                    try:
                        current_agent_idx = workflow_config.agents.index(next_agent)
                    except ValueError:
                        logger.warning(f"Failure agent '{next_agent}' not found in workflow")
                        break
                else:
                    break

        return results

    def get_agent_stats(self, agent_name: str, tenant_id: str = "") -> dict[str, Any]:
        """
        Get statistics for a specific agent.

        Args:
            agent_name: Name of the agent
            tenant_id: Tenant identifier for registry scoping

        Returns:
            Agent statistics

        Raises:
            KeyError: If agent not found
        """
        agent = self.registry.get(agent_name, tenant_id)
        if not agent:
            raise KeyError(f"Agent '{agent_name}' not found")

        return agent.get_stats()

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """
        Get statistics for all agents.

        Returns:
            Dictionary mapping agent names to their statistics
        """
        return self.registry.get_all_stats()

    def list_agents(self) -> list[str]:
        """
        List all registered agents.

        Returns:
            List of agent names
        """
        return self.registry.list_agents()

    async def delete_agent(self, agent_name: str, tenant_id: str = "") -> None:
        """
        Delete an agent from the registry.

        Args:
            agent_name: Name of the agent to delete
            tenant_id: Tenant identifier for registry scoping

        Raises:
            KeyError: If agent not found
        """
        self.registry.unregister(agent_name, tenant_id)
        logger.info(f"Deleted agent: {agent_name} (tenant={tenant_id})")

    async def reset_agent(self, agent_name: str, tenant_id: str = "") -> None:
        """
        Reset an agent by evicting it from the in-memory registry.

        Evicting forces a full reload from Redis/DB on the next request, ensuring
        any updated LLM configs or tool changes take effect immediately. Simply
        calling agent.reset() would keep the stale LLM client in memory.

        Args:
            agent_name: Name of the agent to reset
            tenant_id: Tenant identifier for registry scoping

        Raises:
            KeyError: If agent not found
        """
        agent = self.registry.get(agent_name, tenant_id)
        if not agent:
            raise KeyError(f"Agent '{agent_name}' not found")

        self.registry.unregister(agent_name, tenant_id)
        logger.info(f"Reset agent (evicted from registry): {agent_name}")

    async def reset_all_agents(self) -> None:
        """Reset all registered agents."""
        self.registry.reset_all()
        logger.info("Reset all agents")
