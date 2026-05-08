"""
Scheduled tasks for executing database queries and generating charts
"""

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from src.celery_app import celery_app
from src.core.database import get_db
from src.models.database_connection import DatabaseConnection, DatabaseConnectionType
from src.models.scheduled_task import ScheduledTask, TaskExecution, TaskStatus
from src.services.charts import ChartService
from src.services.database import ElasticsearchConnector, PostgreSQLConnector
from src.tasks.followup_reminder_task import execute_followup_reminder

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.execute_scheduled_task", soft_time_limit=3300, time_limit=3600)
def execute_scheduled_task(
    self,
    task_id: str,
    approval_id: str | None = None,
    feedback_text: str | None = None,
) -> dict[str, Any]:
    """
    Execute a scheduled task

    Args:
        task_id: ID of the scheduled task to execute (UUID as string)

    Returns:
        Dict containing execution results
    """
    db: Session = next(get_db())

    try:
        # Get the scheduled task
        task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if not task:
            raise ValueError(f"Scheduled task {task_id} not found")

        if not task.is_active:
            logger.info(f"Task {task_id} is not active, skipping execution")
            return {"status": "skipped", "reason": "Task is not active"}

        # Create execution record
        execution = TaskExecution(
            task_id=task_id,
            status=TaskStatus.RUNNING,
            started_at=datetime.now(UTC),
            celery_task_id=self.request.id,
        )
        db.add(execution)
        db.commit()

        try:
            # --- Execution Backend Routing ---
            # Skip routing when this process IS the external backend (Lambda /
            # Cloud Run / DO Functions set SYNKORA_DIRECT_EXECUTION=true in their
            # env). Without this check the handler would dispatch to itself again,
            # causing an infinite loop.
            _direct_execution = os.environ.get("SYNKORA_DIRECT_EXECUTION", "false").lower() == "true"

            if not _direct_execution and task.task_type in ("agent_task", "autonomous_agent"):
                _agent_id = task.config.get("agent_id") if task.config else None
                if _agent_id:
                    from src.models.agent import Agent as _Agent

                    _agent_obj = (
                        db.query(_Agent).filter(_Agent.id == _agent_id, _Agent.tenant_id == task.tenant_id).first()
                    )

                    if _agent_obj:
                        _backend_name = (getattr(_agent_obj, "execution_backend", None) or "celery").lower()
                        if _backend_name != "celery":
                            from src.services.agents.execution_backends import get_execution_backend

                            # Credentials come from platform env vars (AWSConfig / GCPConfig).
                            # Tenants only choose the backend — no per-agent credentials stored.
                            _backend = get_execution_backend(_backend_name)
                            if not _backend.is_supported_task_type(task.task_type):
                                raise ValueError(
                                    f"Backend '{_backend_name}' does not support task type "
                                    f"'{task.task_type}'. Use 'cloud_run' or 'celery' for "
                                    "autonomous_agent tasks."
                                )

                            # Run the async dispatch in a new event loop
                            import asyncio as _asyncio

                            _loop = _asyncio.new_event_loop()
                            try:
                                _ext_id = _loop.run_until_complete(
                                    _backend.dispatch(
                                        str(task.id),
                                        task.task_type,
                                        str(_agent_id),
                                        str(task.tenant_id),
                                    )
                                )
                            finally:
                                _loop.close()

                            execution.status = TaskStatus.SUCCESS
                            execution.result = {"external_id": _ext_id, "backend": _backend_name}
                            execution.completed_at = datetime.now(UTC)
                            task.last_run_at = datetime.now(UTC)
                            db.commit()
                            logger.info(
                                f"Task {task_id} dispatched externally via {_backend_name} (external_id={_ext_id})"
                            )
                            return {"status": "dispatched_externally", "backend": _backend_name}

            # Handle followup reminder tasks
            if task.task_type == "followup_reminder":
                # Get agent_id from task config
                agent_id = task.config.get("agent_id")
                if not agent_id:
                    raise ValueError("agent_id not found in task config")

                result = execute_followup_reminder(
                    task_id=str(task.id), tenant_id=str(task.tenant_id), agent_id=str(agent_id), task_config=task.config
                )

                # Update execution status
                if result.get("success"):
                    execution.status = TaskStatus.SUCCESS
                    execution.result = result

                    # Check if task should be disabled
                    if result.get("should_disable_task"):
                        task.is_active = False
                else:
                    execution.status = TaskStatus.FAILED
                    execution.error_message = result.get("error", "Unknown error")

                execution.completed_at = datetime.now(UTC)
                task.last_run_at = datetime.now(UTC)

                db.commit()

                logger.info(f"Successfully executed followup reminder task {task_id}")
                return result

            # Handle generic agent tasks (no database connection required)
            if task.task_type == "agent_task":
                # Get agent_id and prompt from task config
                agent_id = task.config.get("agent_id")
                task_prompt = task.config.get("prompt") or task.config.get("task_description") or task.description

                if not agent_id:
                    logger.error(f"agent_id not found in task config for task {task_id} — deactivating task")
                    task.is_active = False
                    execution.status = TaskStatus.FAILED
                    execution.error_message = "agent_id not found in task config — task deactivated"
                    execution.completed_at = datetime.now(UTC)
                    task.last_run_at = datetime.now(UTC)
                    db.commit()
                    return {"status": "failed", "reason": "agent_id not found in task config — task deactivated"}

                if not task_prompt:
                    raise ValueError("prompt or task_description not found in task config")

                # Import required services
                from src.models.agent import Agent
                from src.services.agents.agent_loader_service import AgentLoaderService
                from src.services.agents.agent_manager import AgentManager
                from src.services.agents.chat_service import ChatService
                from src.services.agents.chat_stream_service import ChatStreamService

                # Load agent from DB — scope to task's tenant to prevent cross-tenant access
                agent = db.query(Agent).filter(Agent.id == agent_id, Agent.tenant_id == task.tenant_id).first()
                if not agent:
                    logger.error(
                        f"Agent {agent_id} not found for task {task_id} (tenant {task.tenant_id}) — deactivating task"
                    )
                    task.is_active = False
                    execution.status = TaskStatus.FAILED
                    execution.error_message = f"Agent {agent_id} not found — task deactivated"
                    execution.completed_at = datetime.now(UTC)
                    task.last_run_at = datetime.now(UTC)
                    db.commit()
                    return {"status": "failed", "reason": f"Agent {agent_id} not found — task deactivated"}

                logger.info(f"🚀 Executing scheduled agent task '{task.name}' with agent '{agent.agent_name}'")

                # Get task creator's email (for tasks that need to send emails to the user)
                creator_email = None
                if task.created_by:
                    from src.models.tenant import Account

                    creator = db.query(Account).filter(Account.id == task.created_by).first()
                    if creator:
                        creator_email = creator.email

                # Create chat stream service
                agent_manager = AgentManager()
                agent_loader = AgentLoaderService(agent_manager)
                chat_service = ChatService()
                chat_stream_service = ChatStreamService(
                    agent_loader=agent_loader,
                    chat_service=chat_service,
                )

                # Build task config context (exclude internal fields like agent_id, prompt)
                # Also replace any [EMAIL_REDACTED] placeholders with the actual creator email
                config_context = ""
                context_items: dict = {}
                if task.config:
                    context_items = {
                        k: v for k, v in task.config.items() if k not in ("agent_id", "prompt", "task_description")
                    }
                    # Replace redacted email placeholders with actual creator email
                    if creator_email:
                        for key, value in context_items.items():
                            if isinstance(value, str) and "[EMAIL_REDACTED]" in value or value == "[EMAIL_REDACTED]":
                                context_items[key] = creator_email

                    if context_items:
                        import json as json_module

                        config_context = (
                            f"\n\n## Task Configuration\n```json\n{json_module.dumps(context_items, indent=2)}\n```"
                        )

                # Add creator email to context if available (as fallback)
                creator_context = ""
                if creator_email:
                    creator_context = f"\n\n## Task Creator\nThis task was created by: {creator_email}\nIf you need to send emails or notifications, use this email address."

                # Build the prompt with context
                full_prompt = f"""## Scheduled Task: {task.name}
{config_context}
{creator_context}

{task_prompt}

This is an automated scheduled task. Complete it thoroughly and provide your findings."""

                # Collect response chunks
                response_chunks = []

                async def process_agent():
                    """Stream agent response and collect chunks."""
                    import json as json_module

                    from src.core.database import create_celery_async_session, reset_async_engine

                    reset_async_engine()

                    # Pass task_config in shared_state for tools to resolve redacted values
                    task_shared_state = {
                        "task_config": context_items if context_items else {},
                        "captured_email": {},
                    }

                    async_session_factory = create_celery_async_session()
                    async with async_session_factory() as async_db:
                        async for sse_event in chat_stream_service.stream_agent_response(
                            agent_name=agent.agent_name,
                            message=full_prompt,
                            conversation_history=None,
                            conversation_id=None,
                            attachments=None,
                            llm_config_id=None,
                            db=async_db,
                            user_id=str(task.created_by) if task.created_by else None,
                            shared_state=task_shared_state,
                        ):
                            # Parse SSE events
                            if sse_event.startswith("data: "):
                                try:
                                    event_data = json_module.loads(sse_event[6:])
                                    if event_data.get("type") == "chunk":
                                        response_chunks.append(event_data.get("content", ""))
                                except json_module.JSONDecodeError:
                                    pass

                # Execute async agent call (30-minute cap to prevent stuck tasks)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(asyncio.wait_for(process_agent(), timeout=1800))
                loop.close()

                response_text = "".join(response_chunks)

                # Dispatch to agent subscribers
                if agent_id and agent.allow_subscriptions:
                    from src.config.settings import settings
                    from src.models.agent_subscription import AgentSubscription
                    from src.tasks.email_tasks import send_email_task

                    subs = (
                        db.query(AgentSubscription)
                        .filter(
                            AgentSubscription.agent_id == agent_id,
                            AgentSubscription.is_active == True,  # noqa: E712
                        )
                        .limit(1000)
                        .all()
                    )
                    if subs:
                        base_url = settings.webhook_base_url or f"http://{settings.api_host}:{settings.api_port}"
                        task_date = datetime.now(UTC).strftime("%B %d, %Y")

                        # Use the actual email the agent sent; fall back to response_text if agent didn't send one
                        captured = task_shared_state.get("captured_email", {})
                        if captured.get("html_body"):
                            email_subject = captured.get("subject") or f"[{task.name}] {task_date}"
                            raw_content_html = captured["html_body"]
                        else:
                            import markdown as md_lib

                            email_subject = f"[{task.name}] {task_date}"
                            raw_content_html = md_lib.markdown(
                                response_text,
                                extensions=["tables", "fenced_code", "nl2br"],
                            )

                        for sub in subs:
                            # Check if this email subscription requires active payment
                            if sub.paid_subscription_id is not None:
                                from src.models.agent_user_subscription import (
                                    AgentUserSubscription,
                                    SubscriptionAccessStatus,
                                )

                                paid_result = db.get(AgentUserSubscription, sub.paid_subscription_id)
                                if paid_result is None or paid_result.status != SubscriptionAccessStatus.ACTIVE:
                                    sub.is_active = False
                                    continue
                            unsubscribe_url = f"{base_url}/unsubscribe?token={sub.unsubscribe_token}"
                            unsubscribe_footer = (
                                f'<p style="font-size:11px;color:#9ca3af;text-align:center;margin:16px 0 0">'
                                f"You're receiving this because you subscribed to <strong>{task.name}</strong> reports."
                                f'&nbsp;<a href="{unsubscribe_url}" style="color:#9ca3af">Unsubscribe</a></p>'
                            )
                            send_email_task.delay(
                                tenant_id=str(task.tenant_id),
                                to_email=sub.email,
                                subject=email_subject,
                                html_body=raw_content_html + unsubscribe_footer,
                            )
                        logger.info(f"Dispatched report to {len(subs)} subscriber(s) for agent {agent_id}")

                result = {
                    "status": "success",
                    "task_id": str(task.id),
                    "task_name": task.name,
                    "agent_name": agent.agent_name,
                    "executed_at": datetime.now(UTC).isoformat(),
                    "response_preview": response_text[:500] if response_text else None,
                    "has_response": bool(response_text),
                }

                # Execute webhook callback if configured
                callback_url = task.config.get("callback_url")
                callback_data = task.config.get("callback_data", {})
                if callback_url:
                    try:
                        import httpx

                        from src.services.agents.internal_tools.web_tools import _is_url_safe

                        is_safe, ssrf_error = asyncio.run(_is_url_safe(callback_url))
                        if not is_safe:
                            logger.warning(f"Callback URL blocked for task {task_id}: {ssrf_error}")
                            result["callback_error"] = f"Callback URL blocked: {ssrf_error}"
                        else:
                            with httpx.Client(timeout=30.0, follow_redirects=False) as client:
                                response = client.post(
                                    callback_url,
                                    json={
                                        "task_id": str(task.id),
                                        "task_name": task.name,
                                        "tenant_id": str(task.tenant_id),
                                        "executed_at": datetime.now(UTC).isoformat(),
                                        "agent_response": response_text,
                                        **callback_data,
                                    },
                                )
                                result["callback_status"] = response.status_code
                                result["callback_response"] = response.text[:500] if response.text else None
                    except Exception as callback_error:
                        logger.warning(f"Callback failed for task {task_id}: {str(callback_error)}")
                        result["callback_error"] = str(callback_error)

                execution.status = TaskStatus.SUCCESS
                execution.result = result
                execution.completed_at = datetime.now(UTC)
                execution.execution_time_seconds = (execution.completed_at - execution.started_at).total_seconds()
                task.last_run_at = datetime.now(UTC)

                db.commit()

                if response_text:
                    logger.info(
                        f"✅ Successfully executed agent task {task_id}: {task.name} - Response: {response_text[:100]}..."
                    )
                else:
                    logger.info(f"🔧 Agent task {task_id} completed (agent used tools, no text response)")

                return result

            # Handle autonomous agent tasks
            if task.task_type == "autonomous_agent":
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    asyncio.wait_for(
                        _run_autonomous_agent(task, db, approval_id=approval_id, feedback_text=feedback_text),
                        timeout=1800,
                    )
                )
                loop.close()

                raw_status = result.get("status")
                if raw_status == "awaiting_approval":
                    execution.status = TaskStatus.AWAITING_APPROVAL
                elif raw_status == "success":
                    execution.status = TaskStatus.SUCCESS
                else:
                    execution.status = TaskStatus.FAILED

                execution.result = result
                execution.error_message = (
                    result.get("error") if raw_status not in ("success", "awaiting_approval") else None
                )
                execution.completed_at = datetime.now(UTC)
                execution.execution_time_seconds = (execution.completed_at - execution.started_at).total_seconds()
                task.last_run_at = datetime.now(UTC)

                db.commit()

                logger.info(f"Autonomous agent task {task_id} finished with status={raw_status}")
                return result

            # Handle database query tasks
            # Ensure we have a database connection for non-followup tasks
            if not task.database_connection_id:
                raise ValueError(f"database_connection_id is required for task type {task.task_type}")

            # Get the database connection — scope to task's tenant to prevent cross-tenant access
            connection = (
                db.query(DatabaseConnection)
                .filter(
                    DatabaseConnection.id == task.database_connection_id,
                    DatabaseConnection.tenant_id == task.tenant_id,
                )
                .first()
            )

            if not connection:
                raise ValueError(f"Database connection {task.database_connection_id} not found")

            # Create appropriate connector based on type
            if connection.database_type == DatabaseConnectionType.POSTGRESQL:
                connector = PostgreSQLConnector(connection)
            elif connection.database_type == DatabaseConnectionType.ELASTICSEARCH:
                connector = ElasticsearchConnector(connection)
            else:
                raise ValueError(f"Unsupported database type: {connection.database_type}")

            # Execute the query using asyncio
            async def execute_async():
                await connector.connect()
                result = await connector.execute_query(task.query)
                await connector.disconnect()
                return result

            query_result = asyncio.run(execute_async())

            # Calculate rows affected
            rows_affected = len(query_result.get("rows", []))

            # Generate chart if configured (chart config is in task.config)
            chart_data = None
            chart_config = task.config.get("chart_config") if task.config else None
            if chart_config:
                chart_service = ChartService(db)
                chart_data = chart_service.generate_chart(data=query_result.get("rows", []), chart_config=chart_config)

            # Store results in the JSONB result column
            execution.result = {
                "query_result": query_result,
                "rows_affected": rows_affected,
                "chart_data": chart_data,
            }

            # Update execution status
            execution.status = TaskStatus.SUCCESS
            execution.completed_at = datetime.now(UTC)
            execution.execution_time_seconds = (execution.completed_at - execution.started_at).total_seconds()

            # Update task last run
            task.last_run_at = datetime.now(UTC)

            db.commit()

            logger.info(f"Successfully executed task {task_id}")

            return {
                "status": "success",
                "execution_id": str(execution.id),
                "rows_affected": rows_affected,
                "has_chart": chart_data is not None,
            }

        except Exception as e:
            # Update execution with error
            execution.status = TaskStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now(UTC)

            # Update task last run
            task.last_run_at = datetime.now(UTC)

            db.commit()

            logger.error(f"Failed to execute task {task_id}: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Error executing scheduled task {task_id}: {str(e)}")
        raise
    finally:
        db.close()


async def _run_autonomous_agent(
    task: ScheduledTask,
    db: Any,
    approval_id: str | None = None,
    feedback_text: str | None = None,
) -> dict[str, Any]:
    """
    Execute one autonomous agent run.

    1. Resolve agent (tenant-scoped).
    2. Get or create a persistent memory conversation.
    3. Build a prompt that injects previous run memory.
    4. Stream the agent response via ChatStreamService (saves messages automatically).
    5. Parse [REMEMBER]{...}[/REMEMBER] blocks and persist them as SYSTEM messages.
    6. Deliver outputs via AgentOutputService.

    Returns a result dict compatible with TaskExecution.result.
    """
    import json as json_module
    import re
    import uuid as uuid_module

    from src.core.database import create_celery_async_session, reset_async_engine
    from src.models.agent import Agent
    from src.models.conversation import Conversation, ConversationStatus
    from src.models.message import Message, MessageRole
    from src.services.agents.agent_loader_service import AgentLoaderService
    from src.services.agents.agent_manager import AgentManager
    from src.services.agents.chat_service import ChatService
    from src.services.agents.chat_stream_service import ChatStreamService
    from src.services.agents.conversation_memory_service import ConversationMemoryService

    cfg = task.config or {}
    agent_id = cfg.get("agent_id")
    goal = cfg.get("goal", "Complete your assigned goal.")
    max_steps = cfg.get("max_steps", 20)

    # Build approval_config for shared_state (used by the HITL gate in adk_tools)
    approval_config: dict = {}
    approval_context: dict = {}  # injected at the top of the prompt when approved
    if cfg.get("require_approval"):
        approval_config = {
            "require_approval": True,
            "approval_mode": cfg.get("approval_mode", "smart"),
            "require_approval_tools": cfg.get("require_approval_tools", []),
            "approval_channel": cfg.get("approval_channel", "chat"),
            "approval_channel_config": cfg.get("approval_channel_config", {}),
            "approval_timeout_minutes": cfg.get("approval_timeout_minutes", 60),
            "task_id": str(task.id),
            "agent_id": str(agent_id),
            "tenant_id": str(task.tenant_id),
            "agent_name": "",  # will be filled after agent is loaded
        }

    # If this run was triggered by an approval, load the approval context
    if approval_id:
        from src.models.agent_approval import AgentApprovalRequest

        # SECURITY: scope by tenant_id to prevent cross-tenant approval injection
        _approval = (
            db.query(AgentApprovalRequest)
            .filter(
                AgentApprovalRequest.id == approval_id,
                AgentApprovalRequest.tenant_id == task.tenant_id,
            )
            .first()
        )
        if _approval:
            approval_context = {
                "approved": True,
                "tool_name": _approval.tool_name,
                "tool_args": _approval.tool_args,
                "channel": _approval.notification_channel,
                "approval_id": str(_approval.id),
            }
            logger.info(f"Autonomous task {task.id}: resuming with approval {approval_id} for {_approval.tool_name}")

    # --- 1. Resolve agent ---
    agent = db.query(Agent).filter(Agent.id == agent_id, Agent.tenant_id == task.tenant_id).first()
    if not agent:
        logger.error(f"Autonomous task {task.id}: agent {agent_id} not found — deactivating")
        task.is_active = False
        db.commit()
        return {"status": "failed", "error": f"Agent {agent_id} not found — task deactivated"}

    # Fill agent_name now that we have the agent
    if approval_config:
        approval_config["agent_name"] = agent.agent_name

    # --- 2. Get or create memory conversation ---
    conv_id: str | None = cfg.get("autonomous_conversation_id")

    reset_async_engine()
    async_session_factory = create_celery_async_session()

    async with async_session_factory() as async_db:
        # Verify conversation still exists; create if missing
        if conv_id:
            from sqlalchemy import select as aselect

            # SECURITY: verify conversation belongs to this agent (tenant-scoped via agent)
            result = await async_db.execute(
                aselect(Conversation).filter(
                    Conversation.id == conv_id,
                    Conversation.agent_id == agent.id,
                )
            )
            if result.scalar_one_or_none() is None:
                conv_id = None  # will be recreated below

        if not conv_id:
            new_conv = Conversation(
                id=uuid_module.uuid4(),
                agent_id=agent.id,
                name=f"[Autonomous] {agent.agent_name}",
                status=ConversationStatus.ACTIVE,
            )
            async_db.add(new_conv)
            await async_db.commit()
            conv_id = str(new_conv.id)

            # Persist conversation ID back into task config (sync db)
            updated_cfg = dict(task.config)
            updated_cfg["autonomous_conversation_id"] = conv_id
            task.config = updated_cfg
            db.commit()

        # --- 3. Build memory context ---
        memory_service = ConversationMemoryService(async_db)
        memory_ctx = await memory_service.get_conversation_context(
            conversation_id=conv_id,
            include_summary=True,
            max_messages=20,
        )

        memory_parts: list[str] = []
        if memory_ctx.get("summary"):
            memory_parts.append(f"[Summary of previous runs]\n{memory_ctx['summary']}")
        recent = memory_ctx.get("messages", [])
        if recent:
            lines = []
            for m in recent[-10:]:
                role_label = m.get("role", "unknown").upper()
                content_snippet = str(m.get("content", ""))[:500]
                lines.append(f"{role_label}: {content_snippet}")
            memory_parts.append("[Recent messages]\n" + "\n".join(lines))

        memory_block = "\n\n".join(memory_parts) if memory_parts else "(no prior memory)"

        # Count prior executions for display
        from sqlalchemy import func
        from sqlalchemy import select as aselect2

        from src.models.scheduled_task import TaskExecution as TE

        count_result = await async_db.execute(aselect2(func.count()).select_from(TE).filter(TE.task_id == task.id))
        run_number = (count_result.scalar() or 0) + 1

        # Build approval prefix / HITL instruction
        if approval_context.get("approved"):
            _tool = approval_context["tool_name"]
            _args = json_module.dumps(approval_context["tool_args"], ensure_ascii=False)
            _channel = approval_context["channel"]
            approval_prefix = (
                f"[APPROVED ACTION]\n"
                f"A human approved the following action via {_channel}.\n"
                f"Tool: {_tool}\n"
                f"Arguments: {_args}\n"
                f"Execute this exact action now. Do not ask for confirmation again.\n\n"
            )
        elif feedback_text:
            approval_prefix = (
                f"[USER FEEDBACK ON PREVIOUS DRAFT]\n"
                f"The user reviewed your last proposed action and provided feedback:\n"
                f'"{feedback_text}"\n'
                f"Revise your approach based on this feedback, then propose the updated action.\n\n"
            )
        elif cfg.get("require_approval"):
            approval_prefix = (
                "[HUMAN APPROVAL MODE]\n"
                "Before calling any action tool (post, send, create, write, commit, etc.), "
                "you MUST stop and let the system handle the approval. "
                "The system will automatically request human approval before executing the action. "
                "You do not need to include any special markers — simply call the tool as normal "
                "and the approval gate will intercept it.\n\n"
            )
        else:
            approval_prefix = ""

        full_prompt = (
            f"{approval_prefix}"
            f"[AUTONOMOUS MODE]\n"
            f"Goal: {goal}\n"
            f"Run #{run_number} | {datetime.now(UTC).isoformat()}\n"
            f"Max tool-call budget: {max_steps}\n\n"
            f"[Memory from previous runs]\n{memory_block}\n\n"
            f"Complete your goal. To persist facts for next run, include:\n"
            f'[REMEMBER]{{"key": "value"}}[/REMEMBER]'
        )

        # --- 3b. Context Window Guard ---
        # Estimate tokens in the initial prompt + conversation history before starting
        from src.services.agents.context_window_guard import ContextWindowGuard

        _guard = ContextWindowGuard()
        # Rough estimate: full_prompt + all recent message content
        _estimated_tokens = len(full_prompt) // 4 + sum(len(str(m.get("content", ""))) // 4 for m in recent)
        # Get model name from agent's llm_config for accurate limit lookup
        _model_name = "default"
        if agent.llm_config and isinstance(agent.llm_config, dict):
            _model_name = agent.llm_config.get("model", "default")

        _guard_result = _guard.evaluate(_model_name, _estimated_tokens)

        if _guard_result.should_block:
            logger.warning(
                f"Autonomous task {task.id}: context window exhausted "
                f"({_estimated_tokens} estimated tokens), cannot run"
            )
            return {
                "status": "failed",
                "error": _guard_result.message,
                "task_id": str(task.id),
                "agent_name": agent.agent_name,
                "run_number": run_number,
                "executed_at": datetime.now(UTC).isoformat(),
                "has_response": False,
            }

        if _guard_result.should_summarize:
            # Compact: keep only the summary + last 3 messages, drop the rest
            logger.info(
                f"Autonomous task {task.id}: context window at "
                f"{_guard_result.remaining_percentage:.0%} remaining — compacting memory "
                f"({_estimated_tokens} estimated tokens)"
            )
            _compact_parts: list[str] = []
            if memory_ctx.get("summary"):
                _compact_parts.append(f"[Summary of previous runs]\n{memory_ctx['summary']}")
            if recent:
                _lines = []
                for _m in recent[-3:]:
                    _role = _m.get("role", "unknown").upper()
                    _snippet = str(_m.get("content", ""))[:200]
                    _lines.append(f"{_role}: {_snippet}")
                _compact_parts.append("[Recent messages (compacted due to context limits)]\n" + "\n".join(_lines))
            _compact_parts.append("[NOTE: Conversation history was compacted. Focus on the goal below.]")
            memory_block = "\n\n".join(_compact_parts)
            # Rebuild full_prompt with compacted memory
            full_prompt = (
                f"{approval_prefix}"
                f"[AUTONOMOUS MODE]\n"
                f"Goal: {goal}\n"
                f"Run #{run_number} | {datetime.now(UTC).isoformat()}\n"
                f"Max tool-call budget: {max_steps}\n\n"
                f"[Memory from previous runs]\n{memory_block}\n\n"
                f"Complete your goal. To persist facts for next run, include:\n"
                f'[REMEMBER]{{"key": "value"}}[/REMEMBER]'
            )

        elif _guard_result.should_warn:
            logger.warning(
                f"Autonomous task {task.id}: context window at "
                f"{_guard_result.remaining_percentage:.0%} remaining "
                f"({_estimated_tokens} estimated tokens)"
            )

        # --- 4. Execute agent ---
        agent_manager = AgentManager()
        agent_loader = AgentLoaderService(agent_manager)
        chat_stream_service = ChatStreamService(
            agent_loader=agent_loader,
            chat_service=ChatService(),
        )

        response_chunks: list[str] = []

        task_shared_state: dict = {}
        if approval_config:
            # Update channel_config for chat channel to include the memory conversation_id
            if approval_config.get("approval_channel") == "chat" and conv_id:
                channel_cfg = dict(approval_config.get("approval_channel_config", {}))
                channel_cfg.setdefault("conversation_id", conv_id)
                approval_config["approval_channel_config"] = channel_cfg
            task_shared_state["approval_config"] = approval_config

        async for sse_event in chat_stream_service.stream_agent_response(
            agent_name=agent.agent_name,
            message=full_prompt,
            conversation_history=None,
            conversation_id=conv_id,
            attachments=None,
            llm_config_id=None,
            db=async_db,
            user_id=str(task.created_by) if task.created_by else None,
            tenant_id=task.tenant_id,
            shared_state=task_shared_state,
            trigger_source="scheduler",
            trigger_detail=task.name,
        ):
            if sse_event.startswith("data: "):
                try:
                    event_data = json_module.loads(sse_event[6:])
                    if event_data.get("type") == "chunk":
                        response_chunks.append(event_data.get("content", ""))
                except json_module.JSONDecodeError:
                    pass

        response_text = "".join(response_chunks)

        # --- 5. Parse [REMEMBER] blocks and persist as SYSTEM messages ---
        remember_pattern = re.compile(r"\[REMEMBER\](.*?)\[/REMEMBER\]", re.DOTALL)
        for match in remember_pattern.finditer(response_text):
            raw_json = match.group(1).strip()
            try:
                memory_data = json_module.loads(raw_json)
                content = json_module.dumps(memory_data, ensure_ascii=False)
            except json_module.JSONDecodeError:
                content = raw_json

            system_msg = Message(
                id=uuid_module.uuid4(),
                conversation_id=conv_id,
                role=MessageRole.SYSTEM,
                content=f"[AUTONOMOUS MEMORY] {content}",
                message_metadata={"source": "autonomous_remember", "run": run_number},
            )
            async_db.add(system_msg)

        await async_db.commit()

        # --- 6. Deliver outputs ---
        try:
            from src.services.agent_output_service import AgentOutputService

            output_service = AgentOutputService(async_db)
            await output_service.send_outputs(
                agent_id=agent.id,
                agent_response=response_text,
                context={
                    "agent_name": agent.agent_name,
                    "trigger_type": "autonomous",
                    "run_number": run_number,
                    "task_name": task.name,
                },
                trigger_type="webhook",  # reuse webhook trigger configs
            )
        except Exception as output_err:
            logger.warning(f"Autonomous task {task.id}: output delivery error: {output_err}")

    # Check if the response indicates the agent is waiting for approval
    # (agent outputs approval_required signal from the gate)
    final_status = "success"
    if response_text and "awaiting_approval" in response_text.lower():
        final_status = "awaiting_approval"

    return {
        "status": final_status,
        "task_id": str(task.id),
        "agent_name": agent.agent_name,
        "run_number": run_number,
        "executed_at": datetime.now(UTC).isoformat(),
        "response_preview": response_text[:500] if response_text else None,
        "has_response": bool(response_text),
    }


# Number of scheduled tasks to load per batch during the due-check sweep.
# Keeps peak memory bounded regardless of total active task count.
_CHECK_BATCH_SIZE = 500


@celery_app.task(name="tasks.check_scheduled_tasks")
def check_scheduled_tasks() -> dict[str, Any]:
    """
    Check for due scheduled tasks and queue them for execution.
    This task runs every minute via Celery Beat.

    Processes tasks in batches of _CHECK_BATCH_SIZE (ordered by id for stable
    pagination) so memory usage stays constant even with 10k+ active tasks.

    Returns:
        Dict containing results of the check
    """
    db: Session = next(get_db())

    try:
        now = datetime.now(UTC)
        queued_count = 0
        total_due = 0
        offset = 0

        while True:
            # Fetch one page of active tasks ordered by a stable PK column so
            # OFFSET pagination is consistent across loop iterations.
            tasks = (
                db.query(ScheduledTask)
                .filter(ScheduledTask.is_active == True)  # noqa: E712
                .order_by(ScheduledTask.id)
                .limit(_CHECK_BATCH_SIZE)
                .offset(offset)
                .all()
            )

            if not tasks:
                break

            for task in tasks:
                try:
                    if _is_task_due_sync(task, now):
                        total_due += 1
                        execute_scheduled_task.delay(str(task.id))
                        # Update last_run_at immediately to prevent a second
                        # beat tick from re-queuing the same task this minute.
                        task.last_run_at = datetime.now(UTC)
                        queued_count += 1
                        logger.info(f"Queued scheduled task {task.id} ({task.name}) for execution")
                except Exception as e:
                    logger.error(f"Error processing task {task.id}: {str(e)}")

            # Commit after each batch so the last_run_at updates are durable
            # before we move on — avoids a large pending write set.
            db.commit()

            if len(tasks) < _CHECK_BATCH_SIZE:
                # Last (partial) page — no more rows to fetch.
                break

            offset += _CHECK_BATCH_SIZE

        logger.info(f"Checked scheduled tasks: {total_due} due, {queued_count} queued")

        return {
            "status": "success",
            "due_tasks": total_due,
            "queued_tasks": queued_count,
        }
    except Exception as e:
        logger.error(f"Error checking scheduled tasks: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def _is_task_due_sync(task: ScheduledTask, now: datetime) -> bool:
    """
    Check if a task is due to run based on interval or cron scheduling.
    Synchronous version for celery tasks.
    """
    from croniter import croniter

    # Make now timezone-aware if not already
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    # Make last_run_at timezone-aware for comparison
    last_run = task.last_run_at
    if last_run and last_run.tzinfo is None:
        last_run = last_run.replace(tzinfo=UTC)

    # If task has a cron schedule
    if task.cron_expression:
        try:
            # If task has never run, it's due
            if last_run is None:
                return True

            # Compute next scheduled run AFTER last_run (same logic as SchedulerService._is_cron_task_due)
            cron = croniter(task.cron_expression, last_run)
            next_scheduled = cron.get_next(datetime)
            if next_scheduled.tzinfo is None:
                next_scheduled = next_scheduled.replace(tzinfo=UTC)

            return next_scheduled <= now
        except Exception as e:
            logger.error(f"Error parsing cron schedule '{task.cron_expression}': {e}")
            return False

    # If task has an interval (in seconds)
    if task.interval_seconds and task.interval_seconds > 0:
        if last_run is None:
            return True
        elapsed = (now - last_run).total_seconds()
        return elapsed >= task.interval_seconds

    return False


@celery_app.task(name="tasks.cleanup_old_executions")
def cleanup_old_executions(days: int = 30) -> dict[str, Any]:
    """
    Clean up old task executions

    Args:
        days: Number of days to keep executions

    Returns:
        Dict containing cleanup results
    """
    db: Session = next(get_db())

    try:
        from datetime import timedelta

        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        # Delete old executions
        deleted_count = db.query(TaskExecution).filter(TaskExecution.completed_at < cutoff_date).delete()

        db.commit()

        logger.info(f"Cleaned up {deleted_count} old task executions")

        return {"status": "success", "deleted_count": deleted_count}

    except Exception as e:
        logger.error(f"Error cleaning up old executions: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="tasks.cleanup_audit_logs")
def cleanup_audit_logs() -> dict[str, Any]:
    """
    Delete activity logs older than AUDIT_LOG_RETENTION_DAYS (default 365).

    Default of 365 days satisfies SOC 2 and PCI DSS 1-year audit log
    requirements.  Configurable via the AUDIT_LOG_RETENTION_DAYS environment
    variable.  Runs daily at 1 AM via Celery beat.
    """
    retention_days = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "365"))

    async def _run() -> int:
        from src.core.database import get_async_session_factory
        from src.services.activity.activity_log_service import ActivityLogService

        async with get_async_session_factory()() as db:
            svc = ActivityLogService(db)
            return await svc.delete_old_logs(days=retention_days)

    try:
        deleted_count = asyncio.run(_run())
        logger.info(f"Audit log cleanup: deleted {deleted_count} entries older than {retention_days} days")
        return {"status": "success", "deleted_count": deleted_count, "retention_days": retention_days}
    except Exception as e:
        logger.error(f"Error cleaning up audit logs: {e}")
        raise


@celery_app.task(name="tasks.cleanup_stale_webhook_events")
def cleanup_stale_webhook_events(stale_minutes: int = 30) -> dict[str, Any]:
    """
    Mark webhook events stuck in 'processing' as failed.

    Events stay in 'processing' forever when a Celery worker is killed mid-task
    (e.g. during a deployment). This task finds them and marks them failed so
    the UI shows the correct status instead of spinning forever.

    Args:
        stale_minutes: Minutes after which a 'processing' event is considered stale (default 30)
    """
    db: Session = next(get_db())

    try:
        from datetime import timedelta

        from src.models.agent_webhook import AgentWebhookEvent

        cutoff = datetime.now(UTC) - timedelta(minutes=stale_minutes)

        stale_events = (
            db.query(AgentWebhookEvent)
            .filter(
                AgentWebhookEvent.status == "processing",
                AgentWebhookEvent.processing_started_at < cutoff,
            )
            .all()
        )

        for event in stale_events:
            event.status = "failed"
            event.error_message = (
                f"Event timed out after {stale_minutes} minutes in 'processing' state. "
                "Worker likely restarted mid-task."
            )
            event.processing_completed_at = datetime.now(UTC)

        if stale_events:
            db.commit()
            logger.info(f"Marked {len(stale_events)} stale webhook event(s) as failed")

        return {"status": "success", "recovered": len(stale_events)}

    except Exception as e:
        logger.error(f"Error cleaning up stale webhook events: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="tasks.disable_dormant_accounts")
def disable_dormant_accounts() -> dict[str, Any]:
    """
    Automatically disable accounts that have been inactive for too long.

    Reads DORMANT_ACCOUNT_DAYS env var (default 90).  Accounts where
    last_login_at is older than that threshold AND status == 'ACTIVE'
    are set to 'INACTIVE'.  This limits the blast radius of compromised
    credentials from accounts that are no longer in use.

    Runs weekly (Sunday 02:00 UTC) via Celery Beat.
    """
    from datetime import timedelta

    from src.models.tenant import Account, AccountStatus

    dormant_days = int(os.environ.get("DORMANT_ACCOUNT_DAYS", 90))
    cutoff = datetime.now(UTC) - timedelta(days=dormant_days)

    db: Session = next(get_db())
    disabled_count = 0

    try:
        # Find active accounts that have not logged in since the cutoff date.
        # Accounts with a NULL last_login_at are treated as never-logged-in and
        # are excluded — they may be newly registered and awaiting first use.
        dormant_accounts = (
            db.query(Account)
            .filter(
                Account.status == AccountStatus.ACTIVE,
                Account.last_login_at.isnot(None),
                Account.last_login_at < cutoff.isoformat(),
            )
            .all()
        )

        for account in dormant_accounts:
            logger.warning(
                f"Disabling dormant account: id={account.id} email={account.email} "
                f"last_login_at={account.last_login_at} (threshold={dormant_days} days)"
            )
            account.status = AccountStatus.INACTIVE
            disabled_count += 1

        if disabled_count:
            db.commit()
            logger.warning(f"Dormant account sweep: disabled {disabled_count} account(s)")
        else:
            logger.info(f"Dormant account sweep: no accounts inactive for more than {dormant_days} days")

        return {"status": "success", "disabled_count": disabled_count, "dormant_days": dormant_days}

    except Exception as e:
        logger.error(f"Error disabling dormant accounts: {e}")
        db.rollback()
        raise
    finally:
        db.close()
