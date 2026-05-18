"""
Base workflow executor for ADK-style agents.

Supports optional persistence through WorkflowPersistenceService
for resume capability and audit trails.
"""

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.models.agent import Agent
from src.models.agent_sub_agent import AgentSubAgent

if TYPE_CHECKING:
    from src.services.agents.workflow_persistence_service import WorkflowPersistenceService

logger = logging.getLogger(__name__)


class BaseWorkflowExecutor(ABC):
    """
    Base class for workflow executors.

    Provides common functionality for all workflow types including:
    - State management
    - Condition evaluation
    - Timeout handling
    - Error handling
    - Optional persistence for resume capability

    To enable persistence, set the `persistence` and `execution_id` attributes
    before calling execute():

        executor = SequentialExecutor(agent, sub_agents)
        executor.persistence = WorkflowPersistenceService(db, tenant_id)
        execution = await executor.persistence.create_execution(...)
        executor.execution_id = execution.id
        result = await executor.execute(...)
    """

    def __init__(self, agent: Agent, sub_agents: list[AgentSubAgent]):
        """
        Initialize the workflow executor.

        Args:
            agent: The parent workflow agent
            sub_agents: List of sub-agents to execute
        """
        self.agent = agent
        self.sub_agents = sorted(sub_agents, key=lambda x: x.execution_order)
        self.state: dict[str, Any] = {}
        self.execution_log: list[dict[str, Any]] = []

        # Optional persistence support
        self.persistence: WorkflowPersistenceService | None = None
        self.execution_id: uuid.UUID | None = None
        self._current_step_index: int = 0

    @abstractmethod
    async def execute(self, initial_input: str, user_id: str, **kwargs) -> dict[str, Any]:
        """
        Execute the workflow.

        Args:
            initial_input: Initial user input
            user_id: User ID for the execution
            **kwargs: Additional execution parameters

        Returns:
            Dict containing the final state and execution results
        """
        pass

    def initialize_state(self, initial_input: str) -> None:
        """
        Initialize the workflow state with user input.

        Args:
            initial_input: Initial user input
        """
        self.state = {
            "user_input": initial_input,
            "workflow_start_time": datetime.now(UTC).isoformat(),
            "iteration": 0,
        }
        self._current_step_index = 0

    async def _persist_started(self) -> None:
        """Mark workflow as started in persistence layer."""
        if self.persistence and self.execution_id:
            await self.persistence.mark_started(self.execution_id)

    async def _persist_state(self) -> None:
        """Persist current state to database."""
        if self.persistence and self.execution_id:
            await self.persistence.update_state(
                self.execution_id,
                self.state,
                self._current_step_index,
                self.execution_log,
            )

    async def _persist_completed(self, final_result: dict[str, Any]) -> None:
        """Mark workflow as completed in persistence layer."""
        if self.persistence and self.execution_id:
            await self.persistence.mark_completed(self.execution_id, final_result)

    async def _persist_failed(self, error: str) -> None:
        """Mark workflow as failed in persistence layer."""
        if self.persistence and self.execution_id:
            await self.persistence.mark_failed(self.execution_id, error)

    def get_state_value(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the workflow state.

        Args:
            key: State key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The state value or default
        """
        return self.state.get(key, default)

    def set_state_value(self, key: str, value: Any) -> None:
        """
        Set a value in the workflow state.

        Args:
            key: State key to set
            value: Value to set
        """
        self.state[key] = value

    def evaluate_condition(self, condition: str | None) -> bool:
        """
        Evaluate a condition against the current state.

        SECURITY: Uses SafeConditionEvaluator instead of eval() to prevent
        arbitrary code execution. Only allows comparisons, boolean operators,
        and state variable access.

        Args:
            condition: Condition string to evaluate (e.g., "state.error == None")

        Returns:
            True if condition is met or no condition specified, False otherwise

        Examples of allowed conditions:
            - "state.status == 'completed'"
            - "state.count > 0 and state.error == None"
            - "not state.has_error"
        """
        if not condition:
            return True

        try:
            # SECURITY: Use safe evaluator instead of eval()
            from src.services.security.safe_eval import safe_eval_condition

            # Pass self.state directly - conditions access it via "state.key"
            result = safe_eval_condition(condition, self.state)
            return result

        except Exception as e:
            logger.warning(f"Condition evaluation failed: {condition}, error: {str(e)}")
            return False

    def get_agent_input(self, sub_agent: AgentSubAgent) -> str:
        """
        Get the input for a sub-agent based on its execution config.

        Args:
            sub_agent: The sub-agent to get input for

        Returns:
            The input string for the agent
        """
        execution_config = sub_agent.execution_config or {}
        input_keys = execution_config.get("input_keys", [])

        if not input_keys:
            # If no input keys, check if there's previous output from another agent
            user_input = self.state.get("user_input", "")
            previous_output = self.state.get("previous_output")

            if previous_output:
                # Combine user input with previous agent's output for context
                return f"{user_input}\n\n[Previous Agent Output]:\n{previous_output}"

            return user_input

        # Gather inputs from state based on input_keys
        inputs = []
        for key in input_keys:
            value = self.state.get(key)
            if value is not None:
                inputs.append(f"{key}: {value}")

        return "\n".join(inputs) if inputs else self.state.get("user_input", "")

    def store_agent_output(self, sub_agent: AgentSubAgent, output: str) -> None:
        """
        Store the output of a sub-agent execution.

        Args:
            sub_agent: The sub-agent that produced the output
            output: The output to store
        """
        execution_config = sub_agent.execution_config or {}
        output_key = (
            execution_config.get("output_key")
            or getattr(sub_agent.sub_agent, "output_key", None)
            or f"agent_{sub_agent.sub_agent_id}_output"
        )

        self.state[output_key] = output

    def log_execution(self, sub_agent_id: str, status: str, **kwargs) -> None:
        """
        Log an execution event.

        Args:
            sub_agent_id: ID of the sub-agent
            status: Execution status (started, completed, failed, skipped)
            **kwargs: Additional log data
        """
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "sub_agent_id": sub_agent_id,
            "status": status,
            **kwargs,
        }
        self.execution_log.append(log_entry)
        # Use %s formatting to avoid issues with curly braces in log data
        logger.info("Workflow execution: %s", log_entry)

    async def execute_sub_agent(
        self, sub_agent: AgentSubAgent, user_id: str, step_index: int | None = None, **kwargs
    ) -> str | None:
        """
        Execute a single sub-agent.

        Args:
            sub_agent: The sub-agent to execute
            user_id: User ID for the execution
            step_index: Optional step index for persistence (defaults to _current_step_index)
            **kwargs: Additional execution parameters (must include 'db', may include 'event_callback')

        Returns:
            The agent's output or None if execution failed
        """
        from src.services.agents.agent_tool import execute_agent

        execution_config = sub_agent.execution_config or {}
        current_step = step_index if step_index is not None else self._current_step_index

        # Check condition
        condition = execution_config.get("condition")
        if not self.evaluate_condition(condition):
            self.log_execution(sub_agent.sub_agent_id, "skipped", reason="Condition not met", condition=condition)

            # Persist skipped step
            if self.persistence and self.execution_id:
                await self.persistence.save_step_skipped(
                    self.execution_id, sub_agent, current_step, f"Condition not met: {condition}"
                )

            return None

        # Get input for the agent
        agent_input = self.get_agent_input(sub_agent)

        # Log start
        self.log_execution(
            sub_agent.sub_agent_id,
            "started",
            input=agent_input[:200] if isinstance(agent_input, str) else str(agent_input)[:200],
        )

        # Persist step start
        if self.persistence and self.execution_id:
            await self.persistence.save_step_start(
                self.execution_id,
                sub_agent,
                current_step,
                agent_input[:10000] if agent_input else "",  # Limit input size
            )

        # Extract db and event_callback from kwargs
        db = kwargs.get("db")
        event_callback = kwargs.get("event_callback")

        # Emit sub-agent start event (using "start" type to match agent_tool.py forwarding)
        if event_callback:
            await event_callback(
                "start",
                {
                    "agent_name": sub_agent.sub_agent.agent_name,
                    "sub_agent_id": str(sub_agent.sub_agent_id),
                    "input_preview": agent_input[:200] if isinstance(agent_input, str) else str(agent_input)[:200],
                },
            )

        if not db:
            error_msg = "Database session (db) is required but not provided in kwargs"
            logger.error(f"Sub-agent execution error: {error_msg}")
            self.state["error"] = error_msg
            self.log_execution(sub_agent.sub_agent_id, "failed", error=error_msg)

            # Persist step failure
            if self.persistence and self.execution_id:
                await self.persistence.save_step_failed(self.execution_id, current_step, error_msg)

            # Emit error event (using "error" type to match agent_tool.py forwarding)
            if event_callback:
                await event_callback(
                    "error",
                    {
                        "agent_name": sub_agent.sub_agent.agent_name,
                        "sub_agent_id": str(sub_agent.sub_agent_id),
                        "error": error_msg,
                    },
                )

            return None

        try:
            # Execute the agent with db parameter and event callback
            result = await execute_agent(
                agent_name=sub_agent.sub_agent.slug or sub_agent.sub_agent.agent_name,
                user_input=agent_input,
                user_id=user_id,
                db=db,
                state=self.state,
                event_callback=event_callback,
                tenant_id=str(self.agent.tenant_id) if self.agent.tenant_id else None,
                **{k: v for k, v in kwargs.items() if k not in ("db", "event_callback")},
            )

            output = result.get("response", "")

            # Store output in state
            self.store_agent_output(sub_agent, output)

            # Determine output key for persistence
            output_key = (
                execution_config.get("output_key")
                or getattr(sub_agent.sub_agent, "output_key", None)
                or f"agent_{sub_agent.sub_agent_id}_output"
            )

            # Log completion
            self.log_execution(
                sub_agent.sub_agent_id,
                "completed",
                output=output[:200] if isinstance(output, str) else str(output)[:200],
            )

            # Persist step completion
            if self.persistence and self.execution_id:
                await self.persistence.save_step_complete(
                    self.execution_id,
                    current_step,
                    output[:50000] if output else "",  # Limit output size
                    output_key,
                )
                # Also persist updated state
                await self._persist_state()

            # Emit sub-agent complete event (using "done" type to match agent_tool.py forwarding)
            if event_callback:
                await event_callback(
                    "done",
                    {
                        "agent_name": sub_agent.sub_agent.agent_name,
                        "sub_agent_id": str(sub_agent.sub_agent_id),
                        "output_preview": output[:200] if isinstance(output, str) else str(output)[:200],
                    },
                )

            return output

        except Exception as e:
            # Use %s formatting to avoid issues with curly braces in error messages
            logger.error("Sub-agent execution failed: %s, error: %s", sub_agent.sub_agent_id, str(e))

            # Store error in state
            self.state["error"] = str(e)
            self.state[f"error_{sub_agent.sub_agent_id}"] = str(e)

            # Log failure
            self.log_execution(sub_agent.sub_agent_id, "failed", error=str(e))

            # Persist step failure
            if self.persistence and self.execution_id:
                await self.persistence.save_step_failed(self.execution_id, current_step, str(e))

            # Emit error event (using "error" type to match agent_tool.py forwarding)
            if event_callback:
                await event_callback(
                    "error",
                    {
                        "agent_name": sub_agent.sub_agent.agent_name,
                        "sub_agent_id": str(sub_agent.sub_agent_id),
                        "error": str(e),
                    },
                )

            # Check retry config
            retry_on_error = execution_config.get("retry_on_error", False)
            if retry_on_error:
                # Retry logic can be added here for fault-tolerant workflows
                pass

            return None

    def get_final_result(self) -> dict[str, Any]:
        """
        Get the final execution result.

        Returns:
            Dict containing the final state and execution log
        """
        return {
            "state": self.state,
            "execution_log": self.execution_log,
            "status": "completed" if not self.state.get("error") else "failed",
            "workflow_type": self.agent.workflow_type,
        }
