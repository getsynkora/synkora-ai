"""
Google A2A Protocol service.

Implements the Agent-to-Agent (A2A) protocol for Synkora agents:
- Agent Card generation (discovery metadata)
- Synchronous message/send
- Async task creation, polling, cancellation
- SSE task streaming

Reference: https://google.github.io/A2A/
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_a2a_task import A2ATaskStatus, AgentA2ATask

logger = logging.getLogger(__name__)

# Default task TTL in hours
TASK_TTL_HOURS = 24


def _extract_message_text(message: dict) -> str:
    """Extract plain text from an A2A message object."""
    parts = message.get("parts", [])
    texts = []
    for part in parts:
        if part.get("type") == "text":
            texts.append(part.get("text", ""))
    return " ".join(texts)


def _build_a2a_message(text: str, role: str = "agent") -> dict:
    """Build an A2A-format message dict."""
    return {
        "role": role,
        "parts": [{"type": "text", "text": text}],
    }


def _task_to_dict(task: AgentA2ATask) -> dict:
    """Serialize an AgentA2ATask to an A2A-compatible task object."""
    result: dict[str, Any] = {
        "id": task.task_id,
        "contextId": task.context_id,
        "status": {
            "state": task.status,
            "timestamp": task.updated_at.isoformat() if task.updated_at else None,
        },
    }
    if task.output_text and task.status == A2ATaskStatus.COMPLETED:
        result["artifacts"] = [
            {
                "name": "response",
                "parts": [{"type": "text", "text": task.output_text}],
            }
        ]
    if task.status == A2ATaskStatus.FAILED:
        result["status"]["error"] = {
            "code": task.error_code or "INTERNAL_ERROR",
            "message": task.error_message or "Agent execution failed",
        }
    return result


async def _collect_agent_response(agent, message: str, conversation_id: str | None, db: AsyncSession) -> str:
    """Invoke ChatStreamService and return the collected text response."""
    from src.services.agents.agent_loader_service import AgentLoaderService
    from src.services.agents.agent_manager import AgentManager
    from src.services.agents.chat_service import ChatService
    from src.services.agents.chat_stream_service import ChatStreamService

    agent_manager = AgentManager()
    agent_loader = AgentLoaderService(agent_manager)
    chat_service = ChatService()
    stream_service = ChatStreamService(agent_loader=agent_loader, chat_service=chat_service)

    chunks: list[str] = []
    async for sse_event in stream_service.stream_agent_response(
        agent_name=agent.slug,
        message=message,
        conversation_history=None,
        conversation_id=conversation_id,
        attachments=None,
        llm_config_id=None,
        db=db,
    ):
        if sse_event.startswith("data: "):
            try:
                data = json.loads(sse_event[6:])
                if data.get("type") == "chunk" and data.get("content"):
                    chunks.append(data["content"])
            except (json.JSONDecodeError, KeyError):
                pass

    return "".join(chunks)


class A2AService:
    """Implements the Google A2A protocol for a Synkora agent."""

    def get_agent_card(self, agent, base_url: str) -> dict:
        """Build the Agent Card JSON for a given agent."""
        metadata = agent.agent_metadata or {}
        integrations = metadata.get("integrations_config", {})
        skills_config = integrations.get("a2a_skills", [])

        # Default skill if none configured
        if not skills_config:
            skills_config = [
                {
                    "id": "chat",
                    "name": "Chat",
                    "description": agent.description or f"Interact with the {agent.agent_name} agent",
                }
            ]

        endpoint_url = f"{base_url.rstrip('/')}/api/a2a/agents/{agent.id}"

        return {
            "name": integrations.get("a2a_name") or agent.agent_name,
            "description": agent.description or "",
            "url": endpoint_url,
            "version": "1.0.0",
            "capabilities": {
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": False,
            },
            "authentication": {
                "schemes": ["Bearer"],
            },
            "skills": skills_config,
        }

    async def send_message(self, agent, input_message: dict, db: AsyncSession) -> dict:
        """
        Synchronous message/send: run the agent and return the completed task.
        """
        task_id = str(uuid.uuid4())
        context_id = input_message.get("contextId") or str(uuid.uuid4())
        message = input_message.get("message", {})
        text = _extract_message_text(message)

        try:
            result_text = await _collect_agent_response(agent, text, context_id, db)
            return {
                "id": task_id,
                "contextId": context_id,
                "status": {
                    "state": A2ATaskStatus.COMPLETED,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                "artifacts": [
                    {
                        "name": "response",
                        "parts": [{"type": "text", "text": result_text}],
                    }
                ],
            }
        except Exception as exc:
            logger.exception(f"[A2A] message/send failed for agent {agent.id}: {exc}")
            return {
                "id": task_id,
                "contextId": context_id,
                "status": {
                    "state": A2ATaskStatus.FAILED,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "error": {"code": "INTERNAL_ERROR", "message": str(exc)},
                },
            }

    async def create_task(
        self,
        agent,
        input_message: dict,
        caller_info: dict | None,
        db: AsyncSession,
    ) -> AgentA2ATask:
        """
        Create an async A2A task record and queue it for Celery execution.
        """
        task_id = input_message.get("id") or str(uuid.uuid4())
        context_id = input_message.get("contextId") or str(uuid.uuid4())
        message = input_message.get("message", {})

        task = AgentA2ATask(
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            task_id=task_id,
            context_id=context_id,
            status=A2ATaskStatus.SUBMITTED,
            input_message=message,
            caller_info=caller_info,
            expires_at=datetime.now(UTC) + timedelta(hours=TASK_TTL_HOURS),
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

        # Queue for async execution
        from src.tasks.a2a_tasks import execute_a2a_task

        execute_a2a_task.delay(str(task.id))

        return task

    async def get_task(self, agent_id: str, task_id: str, db: AsyncSession) -> AgentA2ATask | None:
        """Retrieve an A2A task by agent_id + task_id."""
        result = await db.execute(
            select(AgentA2ATask).where(
                AgentA2ATask.agent_id == uuid.UUID(str(agent_id)),
                AgentA2ATask.task_id == task_id,
            )
        )
        return result.scalar_one_or_none()

    async def cancel_task(self, task: AgentA2ATask, db: AsyncSession) -> AgentA2ATask:
        """Cancel a task if it is still cancelable."""
        if task.status in (A2ATaskStatus.SUBMITTED, A2ATaskStatus.WORKING, A2ATaskStatus.INPUT_REQUIRED):
            task.status = A2ATaskStatus.CANCELED
            task.updated_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(task)
        return task

    async def stream_task(self, agent, task: AgentA2ATask, db: AsyncSession) -> AsyncGenerator[str, None]:
        """
        SSE stream: emit status updates while the agent executes.

        For tasks/sendSubscribe: create task, emit events as the agent runs.
        """
        from src.services.agents.agent_loader_service import AgentLoaderService
        from src.services.agents.agent_manager import AgentManager
        from src.services.agents.chat_service import ChatService
        from src.services.agents.chat_stream_service import ChatStreamService

        # Emit working status
        task.status = A2ATaskStatus.WORKING
        task.updated_at = datetime.now(UTC)
        await db.commit()

        yield f"data: {json.dumps({'id': task.task_id, 'status': {'state': A2ATaskStatus.WORKING}})}\n\n"

        agent_manager = AgentManager()
        agent_loader = AgentLoaderService(agent_manager)
        chat_service = ChatService()
        stream_service = ChatStreamService(agent_loader=agent_loader, chat_service=chat_service)

        message_text = _extract_message_text(task.input_message)
        chunks: list[str] = []

        try:
            async for sse_event in stream_service.stream_agent_response(
                agent_name=agent.slug,
                message=message_text,
                conversation_history=None,
                conversation_id=task.context_id,
                attachments=None,
                llm_config_id=None,
                db=db,
            ):
                if sse_event.startswith("data: "):
                    try:
                        data = json.loads(sse_event[6:])
                        if data.get("type") == "chunk" and data.get("content"):
                            chunk_text = data["content"]
                            chunks.append(chunk_text)
                            # Emit partial artifact
                            event_data = {
                                "id": task.task_id,
                                "status": {"state": A2ATaskStatus.WORKING},
                                "artifact": {
                                    "name": "response",
                                    "parts": [{"type": "text", "text": chunk_text}],
                                    "append": True,
                                },
                            }
                            yield f"data: {json.dumps(event_data)}\n\n"
                    except (json.JSONDecodeError, KeyError):
                        pass

            # Completed
            output_text = "".join(chunks)
            task.status = A2ATaskStatus.COMPLETED
            task.output_text = output_text
            task.updated_at = datetime.now(UTC)
            await db.commit()

            final_event = {
                "id": task.task_id,
                "status": {
                    "state": A2ATaskStatus.COMPLETED,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                "artifacts": [
                    {
                        "name": "response",
                        "parts": [{"type": "text", "text": output_text}],
                    }
                ],
            }
            yield f"data: {json.dumps(final_event)}\n\n"

        except Exception as exc:
            logger.exception(f"[A2A] stream_task failed for task {task.task_id}: {exc}")
            task.status = A2ATaskStatus.FAILED
            task.error_code = "INTERNAL_ERROR"
            task.error_message = str(exc)
            task.updated_at = datetime.now(UTC)
            await db.commit()

            error_event = {
                "id": task.task_id,
                "status": {
                    "state": A2ATaskStatus.FAILED,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "error": {"code": "INTERNAL_ERROR", "message": str(exc)},
                },
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    async def execute_task(self, task_id_str: str) -> None:
        """
        Execute an A2A task from a Celery worker.

        Called by execute_a2a_task Celery task.
        """
        from src.core.database import create_celery_async_session, reset_async_engine

        reset_async_engine()
        async_session_factory = create_celery_async_session()

        async with async_session_factory() as db:
            result = await db.execute(select(AgentA2ATask).where(AgentA2ATask.id == uuid.UUID(task_id_str)))
            task = result.scalar_one_or_none()

            if not task:
                logger.error(f"[A2A] Task {task_id_str} not found")
                return

            if task.status not in (A2ATaskStatus.SUBMITTED,):
                logger.info(f"[A2A] Task {task.task_id} already in status {task.status}, skipping")
                return

            # Load agent
            from src.models.agent import Agent

            agent_result = await db.execute(select(Agent).where(Agent.id == task.agent_id))
            agent = agent_result.scalar_one_or_none()

            if not agent:
                task.status = A2ATaskStatus.FAILED
                task.error_code = "AGENT_NOT_FOUND"
                task.error_message = f"Agent {task.agent_id} not found"
                task.updated_at = datetime.now(UTC)
                await db.commit()
                return

            # Mark as working
            task.status = A2ATaskStatus.WORKING
            task.updated_at = datetime.now(UTC)
            await db.commit()

            message_text = _extract_message_text(task.input_message)

            try:
                result_text = await _collect_agent_response(agent, message_text, task.context_id, db)
                task.status = A2ATaskStatus.COMPLETED
                task.output_text = result_text
            except Exception as exc:
                logger.exception(f"[A2A] execute_task failed for {task.task_id}: {exc}")
                task.status = A2ATaskStatus.FAILED
                task.error_code = "INTERNAL_ERROR"
                task.error_message = str(exc)

            task.updated_at = datetime.now(UTC)
            await db.commit()
