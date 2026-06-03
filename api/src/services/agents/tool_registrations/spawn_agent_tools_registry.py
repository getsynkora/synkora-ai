"""
Spawn Agent Tools Registry

Registers spawn_agent and check_task tools with the ADK tool registry.
These tools enable agents to spawn sub-agents for complex tasks using Celery.
"""

import logging
from typing import Any

from sqlalchemy import select

logger = logging.getLogger(__name__)


def register_spawn_agent_tools(registry):
    """
    Register all spawn agent tools with the ADK tool registry.


    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.spawn_agent_tool import (
        internal_check_task,
        internal_list_background_tasks,
        internal_spawn_agent,
    )

    async def spawn_agent_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None

        db = runtime_context.db_session if runtime_context else None
        tenant_id = str(runtime_context.tenant_id) if runtime_context else None
        parent_agent_id = str(runtime_context.agent_id) if runtime_context else None
        parent_agent_name = None

        if db and runtime_context and runtime_context.agent_id:
            try:
                from src.models.agent import Agent

                result = await db.execute(select(Agent).filter(Agent.id == runtime_context.agent_id))
                agent = result.scalar_one_or_none()
                if agent:
                    parent_agent_name = agent.slug
            except Exception as e:
                logger.warning(f"Could not load parent agent: {e}")

        return await internal_spawn_agent(
            task_description=kwargs.get("task_description", ""),
            run_in_background=kwargs.get("run_in_background", False),
            db=db,
            tenant_id=tenant_id,
            parent_agent_id=parent_agent_id,
            parent_agent_name=parent_agent_name,
        )

    async def check_task_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        tenant_id = str(runtime_context.tenant_id) if runtime_context else None

        return await internal_check_task(
            task_id=kwargs.get("task_id", ""),
            tenant_id=tenant_id,
        )

    async def list_background_tasks_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        tenant_id = str(runtime_context.tenant_id) if runtime_context else None

        return await internal_list_background_tasks(
            tenant_id=tenant_id,
            limit=kwargs.get("limit", 20),
        )

    registry.register_tool(
        name="spawn_agent",
        description="""Spawn a LOCAL sub-agent to handle a task in parallel with other sub-agents.


ONLY use spawn_agent when you have 2 or more INDEPENDENT tasks that can genuinely run at the same time.
Do NOT use spawn_agent for a single task — just do it yourself directly with your tools.
Do NOT use spawn_agent just because a task has multiple steps — sequential steps belong in your own loop.


GOOD — spawn when you have true fan-out:
- Query 5 different data sources in parallel
- Run independent analyses on separate datasets simultaneously


BAD — do NOT spawn for:
- A single query or lookup (use internal_query_database directly)
- A task you can complete in a few tool calls yourself
- Sequential steps where each depends on the previous result


DEFAULT (run_in_background=false): runs synchronously — blocks until complete and returns the result directly.


BACKGROUND (run_in_background=true): only use when a task will take longer than 5 minutes.
Returns a task_id — use check_task(task_id) to poll for the result later.



Do NOT use for calling a remote agent at an external URL — use call_remote_agent instead.""",
        parameters={
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "Clear, detailed description of what the sub-agent should accomplish. Be specific about expected outputs.",
                },
                "run_in_background": {
                    "type": "boolean",
                    "description": "Default false (synchronous, result returned directly). Set true ONLY for tasks longer than 5 minutes.",
                    "default": False,
                },
            },
            "required": ["task_description"],
        },
        function=spawn_agent_wrapper,
    )

    registry.register_tool(
        name="check_task",
        description="""Check the status and result of a background task.


Use this to retrieve results from tasks spawned with run_in_background=true.


Returns:
- status: 'pending', 'running', 'completed', 'failed', 'retrying', 'cancelled'
- result: The agent's response (if completed)
- error: Error message (if failed)""",
        parameters={
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The task_id returned from spawn_agent when run_in_background=true",
                },
            },
            "required": ["task_id"],
        },
        function=check_task_wrapper,
    )

    registry.register_tool(
        name="list_background_tasks",
        description="""Get information about checking background task status.


Note: Track task_ids from spawn_agent responses and use check_task to check their status.""",
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Not used - included for compatibility",
                    "default": 20,
                },
            },
            "required": [],
        },
        function=list_background_tasks_wrapper,
    )

    logger.info("Registered 3 spawn agent tools (spawn_agent, check_task, list_background_tasks)")
