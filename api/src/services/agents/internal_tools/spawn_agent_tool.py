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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def _resolve_target_agent(
    parent_agent_id: str,
    agent_name: str | None,
    tenant_id: str,
    db: AsyncSession | None,
) -> tuple[str | None, bool]:
    """
    Resolve which agent to run for this spawn call.

    Returns (agent_slug, use_worker_prompt):
    - If agent_name matches a registered sub-agent → (sub_agent_slug, False)
      (sub-agent runs with its own system prompt / tools)
    - Otherwise → (parent_agent_slug, True)
      (self-clone with worker system prompt, current behaviour)
    """
    if not db or not agent_name:
        return None, True  # fallback: caller will use parent_agent_name

    try:
        from uuid import UUID as _UUID

        from sqlalchemy import or_

        from src.models.agent import Agent
        from src.models.agent_sub_agent import AgentSubAgent

        # Find sub-agent by name or slug, scoped to this parent + tenant
        result = await db.execute(
            select(AgentSubAgent)
            .join(Agent, Agent.id == AgentSubAgent.sub_agent_id)
            .filter(
                AgentSubAgent.parent_agent_id == _UUID(parent_agent_id),
                AgentSubAgent.is_active,
                Agent.tenant_id == _UUID(tenant_id),
                or_(
                    Agent.agent_name.ilike(agent_name),
                    Agent.slug.ilike(agent_name),
                ),
            )
        )
        rel = result.scalar_one_or_none()
        if rel:
            sub = await db.get(Agent, rel.sub_agent_id)
            if sub:
                slug = sub.slug or sub.agent_name
                logger.info("spawn_agent: routing to registered sub-agent '%s'", slug)
                return slug, False  # sub-agent uses its own config

    except Exception as exc:
        logger.warning("spawn_agent: sub-agent lookup failed, falling back to self-clone: %s", exc)

    return None, True  # fallback


async def internal_spawn_agent(
    task_description: str,
    agent_name: str | None = None,
    run_in_background: bool = False,
    db: AsyncSession | None = None,
    tenant_id: str | None = None,
    account_id: str | None = None,
    parent_agent_id: str | None = None,
    parent_agent_name: str | None = None,
    **context,
) -> dict[str, Any]:
    """
    Spawn a sub-agent to handle a task.

    Routing behaviour:
    - agent_name given AND matches a registered sub-agent → runs that sub-agent
      with its own system prompt, tools, and LLM config.
    - agent_name not given OR no match → clones the parent agent (same config,
      focused only on task_description). Use this to fan-out the same agent
      across many independent tasks in parallel.

    Args:
        task_description: Clear description of what the sub-agent should accomplish
        agent_name: Optional name/slug of a registered sub-agent to delegate to.
                    If omitted the parent agent runs itself with a focused prompt.
        run_in_background: If True, runs async via Celery and returns task_id
        db: Database session
        tenant_id: Tenant ID for isolation
        parent_agent_id: ID of the parent agent spawning this sub-agent
        parent_agent_name: Name/slug of the parent agent

    Returns:
        dict with:
        - If run_in_background=False: {"success": True, "result": <agent response>}
        - If run_in_background=True: {"success": True, "task_id": <id>, "message": "..."}
    """
    try:
        if not task_description or not task_description.strip():
            return {"success": False, "error": "task_description is required"}

        if not tenant_id:
            return {"success": False, "error": "tenant_id not found in context"}

        if not parent_agent_id:
            return {"success": False, "error": "parent_agent_id not found in context"}

        # Resolve the target agent (registered sub-agent or self-clone)
        target_slug, use_worker_prompt = await _resolve_target_agent(
            parent_agent_id=parent_agent_id,
            agent_name=agent_name,
            tenant_id=tenant_id,
            db=db,
        )
        # Fall back to parent if no registered sub-agent matched
        if target_slug is None:
            target_slug = parent_agent_name
            use_worker_prompt = True

        logger.info(
            "Spawning sub-agent '%s' for task: %s... (background=%s, registered=%s)",
            target_slug,
            task_description[:80],
            run_in_background,
            not use_worker_prompt,
        )

        if run_in_background:
            from src.tasks.agent_tasks import execute_spawn_agent_task

            result = execute_spawn_agent_task.delay(
                tenant_id=tenant_id,
                parent_agent_id=parent_agent_id,
                task_description=task_description,
                target_agent_name=target_slug,
                use_worker_prompt=use_worker_prompt,
            )

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
            result = await _execute_sub_agent(
                task_description=task_description,
                target_agent_name=target_slug,
                use_worker_prompt=use_worker_prompt,
                tenant_id=tenant_id,
                db=db,
            )

            return {"success": True, "result": result}

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
    target_agent_name: str | None,
    use_worker_prompt: bool,
    tenant_id: str | None = None,
    db: AsyncSession | None = None,
) -> str:
    """
    Execute a sub-agent synchronously and return its response.

    Args:
        task_description: The task to execute
        target_agent_name: Slug/name of the agent to run
        use_worker_prompt: True → apply _WORKER_SYSTEM_PROMPT override (self-clone mode)
                           False → run agent with its own system prompt (registered sub-agent mode)
    """
    if not target_agent_name:
        return "Error: target_agent_name is required for sub-agent execution."

    from src.services.agents.agent_loader_service import AgentLoaderService
    from src.services.agents.agent_manager import AgentManager
    from src.services.agents.chat_service import ChatService
    from src.services.agents.chat_stream_service import ChatStreamService

    # Sanitize task_description to prevent prompt injection
    sandboxed_desc = f"--- BEGIN SUB-TASK ---\n{task_description[:4000]}\n--- END SUB-TASK ---"

    full_prompt = f"""## Sub-Task

{sandboxed_desc}

Complete this task thoroughly and provide your findings. Be comprehensive but concise."""

    agent_manager = AgentManager()
    chat_stream_service = ChatStreamService(
        agent_loader=AgentLoaderService(agent_manager),
        chat_service=ChatService(),
    )

    stream_kwargs: dict[str, Any] = {
        "agent_name": target_agent_name,
        "tenant_id": tenant_id,
        "message": full_prompt,
        "conversation_history": None,
        "conversation_id": None,
        "attachments": None,
        "llm_config_id": None,
        "db": None,
        "override_agentic_config": {"parallel_tools": True},
    }
    # Self-clone mode: override system prompt so the agent stays focused
    # Registered sub-agent mode: let it use its own system prompt
    if use_worker_prompt:
        stream_kwargs["override_system_prompt"] = _WORKER_SYSTEM_PROMPT

    response_chunks: list[str] = []
    error_messages: list[str] = []

    async for sse_event in chat_stream_service.stream_agent_response(**stream_kwargs):
        if sse_event.startswith("data: "):
            try:
                event_data = json.loads(sse_event[6:])
                event_type = event_data.get("type")
                if event_type == "chunk":
                    content = event_data.get("content")
                    if content:
                        response_chunks.append(content)
                elif event_type == "error":
                    error_msg = event_data.get("error", "Unknown error")
                    error_messages.append(error_msg)
                    logger.warning("Sub-agent '%s' error event: %s", target_agent_name, error_msg)
            except json.JSONDecodeError:
                pass

    result = "".join(response_chunks)
    if result:
        return result
    if error_messages:
        return f"Sub-agent encountered errors: {'; '.join(error_messages)}"
    return "Sub-agent completed but returned no response."
