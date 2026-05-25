"""
Spawn Agent Tool for creating sub-agents.

Allows agents to spawn sub-agents for complex, multi-step, or long-running tasks.
Similar to Claude Code's Task tool for autonomous agent orchestration.

Uses Celery for background task execution with:
- Persistent task tracking via Redis
- Built-in retry logic with exponential backoff
- Scales across multiple workers
- Tasks survive restarts
"""

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def internal_spawn_agent(
    task_description: str,
    run_in_background: bool = False,
    db: AsyncSession | None = None,
    tenant_id: str | None = None,
    account_id: str | None = None,
    parent_agent_id: str | None = None,
    parent_agent_name: str | None = None,
    **context,
) -> dict[str, Any]:
    """
    Spawn a sub-agent to handle complex or long-running tasks.

    This tool delegates a focused task to the same parent agent configuration,
    running either synchronously or in the background via Celery.

    The sub-agent inherits the parent agent's:
    - LLM configuration
    - Tools
    - System prompt

    Only the task description changes (provides focused scope).

    Args:
        task_description: Clear description of what the sub-agent should accomplish
        run_in_background: If True, runs async via Celery and returns task_id
        db: Database session
        tenant_id: Tenant ID for isolation
        account_id: Account ID
        parent_agent_id: ID of the parent agent spawning this sub-agent
        parent_agent_name: Name of the parent agent
        **context: Additional context from runtime

    Returns:
        dict with:
        - If run_in_background=False: {"success": True, "result": <agent response>}
        - If run_in_background=True: {"success": True, "task_id": <id>, "message": "..."}

    Example usage by agent:
        # Synchronous task (blocks until complete)
        spawn_agent(task_description="Research the latest AI frameworks")

        # Background task (returns immediately with task_id)
        spawn_agent(task_description="Analyze all error logs", run_in_background=True)
    """
    try:
        if not task_description or not task_description.strip():
            return {"success": False, "error": "task_description is required"}

        if not tenant_id:
            return {"success": False, "error": "tenant_id not found in context"}

        if not parent_agent_id:
            return {"success": False, "error": "parent_agent_id not found in context"}

        logger.info(f"Spawning sub-agent for task: {task_description[:100]}... (background={run_in_background})")

        if run_in_background:
            # Submit to Celery for background execution
            from src.tasks.agent_tasks import execute_spawn_agent_task

            result = execute_spawn_agent_task.delay(
                tenant_id=tenant_id,
                parent_agent_id=parent_agent_id,
                task_description=task_description,
            )

            # Store tenant ownership of this task in Redis so check_task can verify isolation
            try:
                from src.config.redis import get_redis_async

                _redis = get_redis_async()
                await _redis.setex(f"task_tenant:{result.id}", 86400, str(tenant_id))
            except Exception as _re:
                logger.warning("Failed to store task tenant in Redis: %s", _re)

            return {
                "success": True,
                "task_id": result.id,
                "message": f"Task started in background. Use check_task('{result.id}') to get results.",
            }
        else:
            # Execute synchronously using existing infrastructure
            result = await _execute_sub_agent(
                task_description=task_description,
                parent_agent_name=parent_agent_name,
                tenant_id=tenant_id,
                db=db,
            )

            return {
                "success": True,
                "result": result,
            }

    except Exception as e:
        logger.error(f"Error spawning agent: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_check_task(
    task_id: str,
    tenant_id: str | None = None,
    **context,
) -> dict[str, Any]:
    """
    Check the status and result of a background task using Celery's AsyncResult.

    Use this to retrieve results from tasks spawned with run_in_background=True.

    Args:
        task_id: The task ID returned from spawn_agent
        tenant_id: Tenant ID for isolation
        **context: Additional context from runtime

    Returns:
        dict with:
        - status: 'pending', 'started', 'success', 'failure', 'retry', 'revoked'
        - result: The agent's response (if success)
        - error: Error message (if failure)
    """
    try:
        if not task_id:
            return {"success": False, "error": "task_id is required"}

        # Tenant isolation: verify this task belongs to the calling tenant
        if tenant_id:
            try:
                from src.config.redis import get_redis_async

                _redis = get_redis_async()
                stored_tenant = await _redis.get(f"task_tenant:{task_id}")
                if stored_tenant and stored_tenant != str(tenant_id):
                    return {"error": "Task not found", "status": "not_found", "success": False}
            except Exception as _re:
                logger.warning("Failed to verify task tenant in Redis: %s", _re)

        from celery.result import AsyncResult

        result = AsyncResult(task_id)

        # Map Celery states to user-friendly statuses
        status_map = {
            "PENDING": "pending",
            "STARTED": "running",
            "SUCCESS": "completed",
            "FAILURE": "failed",
            "RETRY": "retrying",
            "REVOKED": "cancelled",
        }

        status = status_map.get(result.state, result.state.lower())

        response = {
            "success": True,
            "task_id": task_id,
            "status": status,
        }

        if result.successful():
            # Get the actual result dict from the Celery task
            task_result = result.result
            if isinstance(task_result, dict):
                response["result"] = task_result.get("result")
                if not task_result.get("success"):
                    response["error"] = task_result.get("error")
            else:
                response["result"] = task_result
        elif result.failed():
            response["error"] = str(result.result) if result.result else "Task failed"

        return response

    except Exception as e:
        logger.error(f"Error checking task: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_list_background_tasks(
    tenant_id: str | None = None,
    limit: int = 20,
    **context,
) -> dict[str, Any]:
    """
    List recent background tasks.

    Note: With Celery, we can only list tasks that are still in the result backend.
    Results expire after 1 hour by default (configured in celery_app.py).

    Args:
        tenant_id: Tenant ID for isolation
        limit: Maximum number of tasks to return
        **context: Additional context from runtime

    Returns:
        dict with information about querying tasks
    """
    try:
        # Celery doesn't maintain a list of tasks per tenant by default
        # Users should track their own task_ids from spawn_agent responses
        return {
            "success": True,
            "message": (
                "To check task status, use check_task(task_id) with the task_id "
                "returned from spawn_agent. Task results are available for 1 hour."
            ),
            "note": "Track task_ids from spawn_agent responses to check their status later.",
        }

    except Exception as e:
        logger.error(f"Error listing tasks: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


_WORKER_SYSTEM_PROMPT = """You are a task execution agent. Your job is to complete the specific task given to you using your available tools.

Execute the task directly and thoroughly:
- Use your tools to gather information, perform actions, and complete the work
- Be specific and detailed in your findings
- Report clearly what you did and what you found
- Do NOT spawn sub-agents or delegate — complete the task yourself

When finished, provide a clear summary of what you accomplished."""


async def _execute_sub_agent(
    task_description: str,
    parent_agent_name: str | None,
    tenant_id: str | None = None,
    db: AsyncSession | None = None,
) -> str:
    """
    Execute a sub-agent synchronously and return its response.

    This uses the existing ChatStreamService infrastructure to run the agent
    with the same configuration as the parent.
    """
    from src.core.database import get_async_session_factory
    from src.services.agents.agent_loader_service import AgentLoaderService
    from src.services.agents.agent_manager import AgentManager
    from src.services.agents.chat_service import ChatService
    from src.services.agents.chat_stream_service import ChatStreamService

    # Always create a fresh session — never reuse the parent's active session.
    # spawn_agent is called concurrently (asyncio.gather) for parallel sub-agents;
    # sharing one AsyncSession across concurrent coroutines causes immediate failures.
    db = get_async_session_factory()()
    should_close_db = True

    try:
        # Sanitize task_description: cap length and wrap in delimiters to prevent
        # prompt injection from user-controlled content reaching the sub-agent.
        sandboxed_desc = f"--- BEGIN SUB-TASK ---\n{task_description[:4000]}\n--- END SUB-TASK ---"

        # Build the focused sub-task prompt
        full_prompt = f"""## Sub-Task

{sandboxed_desc}

Complete this task thoroughly and provide your findings. Be comprehensive but concise."""

        if parent_agent_name:
            agent_manager = AgentManager()
            agent_loader = AgentLoaderService(agent_manager)
            chat_service = ChatService()
            chat_stream_service = ChatStreamService(
                agent_loader=agent_loader,
                chat_service=chat_service,
            )

            # Stream the response and collect chunks
            response_chunks = []

            async for sse_event in chat_stream_service.stream_agent_response(
                agent_name=parent_agent_name,
                tenant_id=tenant_id,
                message=full_prompt,
                conversation_history=None,
                conversation_id=None,
                attachments=None,
                llm_config_id=None,
                db=db,
                override_system_prompt=_WORKER_SYSTEM_PROMPT,
                override_agentic_config={"parallel_tools": True},
            ):
                # Parse SSE events
                if sse_event.startswith("data: "):
                    try:
                        event_data = json.loads(sse_event[6:])
                        if event_data.get("type") == "chunk":
                            response_chunks.append(event_data.get("content", ""))
                    except json.JSONDecodeError:
                        pass

            return "".join(response_chunks) or "Sub-agent completed but returned no response."

        else:
            return "Error: parent_agent_name is required for sub-agent execution."

    finally:
        if should_close_db:
            await db.close()
