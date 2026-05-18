"""
AgentTool - Wrapper to execute agents as tools

Allows parent agents to invoke sub-agents as callable tools,
with streaming support and state management.
"""

import logging
import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.agents.runtime_context import RuntimeContext

logger = logging.getLogger(__name__)


class AgentTool:
    """
    Wrapper that makes an Agent callable as a tool.

    This enables explicit invocation pattern where a parent agent
    can call a sub-agent as if it were a regular tool function.
    """

    def __init__(self, agent_id: uuid.UUID, agent_name: str, description: str, db: AsyncSession):
        """
        Initialize AgentTool.

        Args:
            agent_id: ID of the agent to wrap
            agent_name: Name of the agent (used as tool name)
            description: Description of what the agent does
            db: Database session
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.description = description
        self.db = db

    def get_function_definition(self) -> dict[str, Any]:
        """
        Get OpenAI function definition for this agent tool.

        Returns:
            Function definition dict
        """
        return {
            "type": "function",
            "function": {
                "name": self.agent_name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "The task or question to delegate to this agent"}
                    },
                    "required": ["task"],
                },
            },
        }

    async def execute(self, task: str, context: RuntimeContext) -> AsyncGenerator[dict[str, Any], None]:
        """
        Execute the agent with the given task.

        This creates a child context, executes the agent, and streams
        the results back to the parent agent.

        Args:
            task: Task description to pass to the agent
            context: Parent agent's runtime context

        Yields:
            Stream of events from the agent execution
        """
        from src.models.agent import Agent
        from src.services.agents.config import AgentOrchestrator

        # Get the agent
        result = await self.db.execute(select(Agent).filter(Agent.id == self.agent_id))
        agent = result.scalar_one_or_none()
        if not agent:
            error_msg = f"Agent {self.agent_name} not found"
            logger.error(error_msg)
            yield {"type": "error", "content": error_msg}
            return

        # Create child context with shared state
        child_context = context.create_child_context(self.agent_id)

        # Add task to shared state
        child_context.set_state(f"_task_for_{self.agent_name}", task)

        logger.info(f"Executing sub-agent {self.agent_name} (parent: {context.agent_id})")

        try:
            # Create orchestrator for the sub-agent
            orchestrator = AgentOrchestrator(agent, self.db)

            # Execute the agent with the task as user message
            async for event in orchestrator.run(
                user_message=task,
                conversation_id=context.conversation_id,
                user_id=context.user_id,
                runtime_context=child_context,
            ):
                # Stream events back to parent
                yield event

                # If agent sets output_key, save final response to state
                if event.get("type") == "agent_response" and agent.output_key and event.get("content"):
                    child_context.set_state(agent.output_key, event["content"])
                    logger.debug(f"Saved output to state['{agent.output_key}']")

        except Exception as e:
            error_msg = f"Error executing sub-agent {self.agent_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            yield {"type": "error", "content": error_msg}

    async def execute_sync(self, task: str, context: RuntimeContext) -> str:
        """
        Execute agent and return final result as string.

        This is a convenience method for parent agents that just need
        the final result without streaming.

        Args:
            task: Task description
            context: Parent runtime context

        Returns:
            Final agent response as string
        """
        result_parts = []

        async for event in self.execute(task, context):
            if event.get("type") == "agent_response":
                content = event.get("content", "")
                if content:
                    result_parts.append(content)

        return "\n".join(result_parts) if result_parts else ""


async def create_agent_tools(parent_agent_id: uuid.UUID, db: AsyncSession) -> list[AgentTool]:
    """
    Create AgentTool instances for all sub-agents of a parent.

    Args:
        parent_agent_id: ID of the parent agent
        db: Database session

    Returns:
        List of AgentTool instances
    """
    from src.models.agent import Agent

    result = await db.execute(select(Agent).filter(Agent.id == parent_agent_id))
    parent = result.scalar_one_or_none()
    if not parent:
        return []

    sub_agents = await parent.get_sub_agents(db, active_only=True)

    tools = []
    for sub_agent in sub_agents:
        tool = AgentTool(
            agent_id=sub_agent.id,
            agent_name=sub_agent.agent_name,
            description=sub_agent.description or f"Delegate tasks to {sub_agent.agent_name}",
            db=db,
        )
        tools.append(tool)

    logger.info(f"Created {len(tools)} agent tools for parent {parent.agent_name}")

    return tools


def _render_template(text: str | None, state: dict[str, Any] | None) -> str | None:
    """
    Render template with state variables, safely handling non-template curly braces.

    Args:
        text: Template text that may contain {variable} placeholders
        state: Dictionary of variable values

    Returns:
        Rendered text with variables replaced
    """
    if not text or not state:
        return text

    class _SafeDict(dict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    try:
        return text.format_map(_SafeDict(state))
    except (ValueError, KeyError) as e:
        # If formatting fails (e.g., due to CSS/code with curly braces),
        # log the error and return the original text
        logger.warning(f"Template rendering failed, returning original text. Error: {e}")
        return text


async def execute_agent(
    agent_name: str,
    user_input: str,
    user_id: str,
    db: AsyncSession,
    conversation_id: str | None = None,
    llm_config_id: str | None = None,
    state: dict[str, Any] | None = None,
    event_callback: Callable | None = None,
    tenant_id: str | None = None,
    **_kwargs,
) -> dict[str, Any]:
    """
    Execute a sub-agent and return a normalized response payload.

    This helper is used by workflow executors.
    Delegates to ChatStreamService for proper tool execution and streaming.

    Args:
        agent_name: Name of the sub-agent to execute
        user_input: Input message for the agent
        user_id: User ID for the execution
        db: Database session
        conversation_id: Optional conversation ID (typically None for sub-agents)
        llm_config_id: Optional LLM config ID override
        state: Workflow state dictionary (includes previous_output)
        event_callback: Optional async callback to stream events to parent (for UI updates)
        **_kwargs: Additional keyword arguments

    Returns:
        Dict with status, response, and result
    """
    from src.services.agents.agent_loader_service import AgentLoaderService
    from src.services.agents.agent_manager import AgentManager
    from src.services.agents.chat_service import ChatService
    from src.services.agents.chat_stream_service import ChatStreamService

    # Render prompt with state variables (includes previous_output from previous agent)
    rendered_prompt = _render_template(user_input, state) or user_input

    try:
        # Use the existing ChatStreamService which handles:
        # - Tool loading and execution
        # - Function calling
        # - RAG retrieval
        # - Proper streaming
        # - Error handling
        agent_manager = AgentManager()
        agent_loader = AgentLoaderService(agent_manager)
        chat_service = ChatService()
        stream_service = ChatStreamService(
            agent_loader=agent_loader,
            chat_service=chat_service,
        )

        # Collect streamed response AND forward events to orchestrator
        response_parts = []

        # Stream agent response and forward all events to parent
        async for sse_event in stream_service.stream_agent_response(
            agent_name=agent_name,
            message=rendered_prompt,
            conversation_history=None,
            conversation_id=None,
            attachments=None,
            llm_config_id=llm_config_id,
            db=db,
            tenant_id=tenant_id,
        ):
            # Parse SSE events to accumulate text content
            # Events come as "data: {json}\n\n"
            if sse_event.startswith("data: "):
                import json

                try:
                    event_data = json.loads(sse_event[6:])  # Skip "data: " prefix
                    event_type = event_data.get("type")

                    # Log event for debugging
                    logger.debug(f"Sub-agent '{agent_name}' event: {event_type}")

                    # Forward parsed event to callback (for workflow streaming)
                    if event_callback:
                        # Call with correct signature: (event_type, data)
                        await event_callback(event_type, {"agent_name": agent_name, **event_data})

                    # Accumulate content chunks into full response
                    if event_type == "chunk":
                        chunk = event_data.get("content", "")
                        if chunk:
                            response_parts.append(chunk)
                    elif event_type == "error":
                        error_msg = event_data.get("error", "Unknown error")
                        logger.error(f"Sub-agent '{agent_name}' error: {error_msg}")
                        return {
                            "status": "error",
                            "response": "",
                            "error": error_msg,
                        }
                except json.JSONDecodeError:
                    # Skip malformed events
                    continue

        # Join all accumulated chunks into final response
        response = "".join(response_parts)

        if not response:
            logger.warning(f"Sub-agent '{agent_name}' produced no output (received {len(response_parts)} chunks)")
            # Return empty response but still mark as success
            return {
                "status": "success",
                "response": "",
                "result": {"response": ""},
            }

        logger.info(f"Sub-agent '{agent_name}' completed: {len(response)} chars from {len(response_parts)} chunks")

        return {
            "status": "success",
            "response": response,
            "result": {"response": response},
        }

    except Exception as e:
        error_msg = f"Error executing agent '{agent_name}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "status": "error",
            "response": "",
            "error": error_msg,
        }
