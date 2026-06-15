"""Celery tasks for agent execution."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from src.celery_app import celery_app
from src.core.database import SessionLocal

logger = logging.getLogger(__name__)

# System prompt used for spawned worker sub-agents.
# Workers receive a task_description and must execute it directly using their tools.
# They must NOT inherit the orchestrator's "don't do work directly" instructions.
_WORKER_SYSTEM_PROMPT = """You are a task execution agent. Your job is to complete the specific task given to you using your available tools.

Execute the task directly and thoroughly:
- Use your tools to gather information, perform actions, and complete the work
- Be specific and detailed in your findings
- Report clearly what you did and what you found
- Do NOT spawn sub-agents or delegate — complete the task yourself

When finished, provide a clear summary of what you accomplished."""


# Exceptions that should NOT be retried (permanent failures)
class PermanentTaskError(Exception):
    """Exception for errors that should not be retried."""

    pass


class RetryableTaskError(Exception):
    """Exception for errors that can be retried."""

    pass


# Error patterns that indicate permanent failures (no point retrying)
PERMANENT_ERROR_PATTERNS = [
    "not found",
    "does not exist",
    "invalid",
    "unauthorized",
    "forbidden",
    "permission denied",
    "authentication failed",
    "not allowed",
    "blocked",
    "security",
]


def is_permanent_error(error_message: str) -> bool:
    """
    Check if an error is permanent and should not be retried.

    Args:
        error_message: The error message to check

    Returns:
        True if the error is permanent, False if it might be transient
    """
    error_lower = error_message.lower()
    return any(pattern in error_lower for pattern in PERMANENT_ERROR_PATTERNS)


@celery_app.task(
    name="process_webhook_event",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(RetryableTaskError,),  # Only auto-retry for retryable errors
    retry_backoff=True,  # Exponential backoff: 60s, 120s, 240s
    retry_backoff_max=300,  # Max 5 minutes between retries
    retry_jitter=True,  # Add randomness to prevent thundering herd
)
def process_webhook_event(self, webhook_id: str, event_id: str, parsed_data: dict[str, Any]):
    """
    Process webhook event by calling agent.

    The agent receives the webhook data and uses its configured tools to:
    - Review PRs and comment on GitHub
    - Post updates to Slack channels
    - Create/update Jira issues
    - Update ClickUp tasks
    - Or simply process and log the event

    The agent's tools determine WHERE and HOW the output is sent.
    This task just calls the agent - no hardcoded output handling.

    Retry Logic:
    - Max 3 retries with exponential backoff (60s, 120s, 240s)
    - Only retries transient errors (network issues, timeouts)
    - Does NOT retry permanent errors (not found, invalid, unauthorized)

    Args:
        webhook_id: UUID of the webhook
        event_id: UUID of the webhook event
        parsed_data: Parsed webhook data (PR info, issue info, etc.)
    """
    db = SessionLocal()
    current_retry = self.request.retries

    try:
        from src.models.agent import Agent
        from src.models.agent_webhook import AgentWebhook, AgentWebhookEvent
        from src.services.agents.agent_loader_service import AgentLoaderService
        from src.services.agents.agent_manager import AgentManager
        from src.services.agents.chat_service import ChatService
        from src.services.agents.chat_stream_service import ChatStreamService

        # Load webhook and event
        webhook = db.query(AgentWebhook).filter(AgentWebhook.id == UUID(webhook_id)).first()

        if not webhook:
            logger.error(f"Webhook {webhook_id} not found - permanent failure, not retrying")
            return  # Don't retry - webhook doesn't exist

        event = db.query(AgentWebhookEvent).filter(AgentWebhookEvent.id == UUID(event_id)).first()

        if not event:
            logger.error(f"Event {event_id} not found - permanent failure, not retrying")
            return  # Don't retry - event doesn't exist

        # Idempotency check: only process events that are genuinely unstarted.
        # pending    → queued but never started, safe to process
        # processing → this task already set it below; re-running risks duplicate PR reviews
        # completed/success → already done
        # failed → exhausted retries, giving up was intentional
        # retrying/retry → Celery already has a retry scheduled, don't double-execute
        if event.status != "pending":
            logger.info(f"Skipping event {event_id} — status is '{event.status}', only 'pending' events are processed")
            return

        # Mark as processing immediately so worker restarts don't re-run this task
        event.status = "processing"
        event.retry_count = current_retry
        db.commit()

        if current_retry > 0:
            logger.info(f"🔄 Retry attempt {current_retry}/{self.max_retries} for event {event_id}")

        agent_db = db.query(Agent).filter(Agent.id == webhook.agent_id).first()
        if not agent_db:
            logger.error(f"Agent not found for webhook {webhook_id} - permanent failure")
            event.status = "failed"
            event.error_message = "Agent not found"
            db.commit()
            return  # Don't retry - agent doesn't exist

        logger.info(f"🚀 Processing webhook event {event_id} for agent '{agent_db.agent_name}'")

        # Build contextual message for agent
        event_type = parsed_data.get("event_type", "unknown")
        provider = webhook.provider

        # Format webhook data as clear context for the agent
        message = f"""[Webhook Event Context: {provider} - {event_type}]

Event Data:
{json.dumps(parsed_data, indent=2)}

Please process this webhook event using your configured tools."""

        logger.info("📤 Calling agent with webhook context")

        # Create chat stream service
        agent_manager = AgentManager()
        agent_loader = AgentLoaderService(agent_manager)
        chat_service = ChatService()
        chat_stream_service = ChatStreamService(
            agent_loader=agent_loader,
            chat_service=chat_service,
        )

        # Call agent using the same infrastructure as Slack/Widget/Chat
        # Agent will use its tools to decide where to send output
        response_chunks = []

        async def process_agent():
            """Stream agent response and collect chunks."""
            from src.core.database import create_celery_async_session, reset_async_engine

            # Reset global async engine so get_async_session_factory() re-initializes
            # bound to this event loop (not the previous Celery task's closed loop)
            reset_async_engine()

            async_session_factory = create_celery_async_session()
            async with async_session_factory() as async_db:
                async for sse_event in chat_stream_service.stream_agent_response(
                    agent_name=agent_db.agent_name,
                    tenant_id=str(agent_db.tenant_id),
                    message=message,
                    conversation_history=None,
                    conversation_id=None,
                    attachments=None,
                    llm_config_id=None,
                    db=async_db,
                ):
                    # Parse SSE events
                    if sse_event.startswith("data: "):
                        try:
                            event_data = json.loads(sse_event[6:])
                            if event_data.get("type") == "chunk":
                                response_chunks.append(event_data.get("content", ""))
                        except json.JSONDecodeError:
                            pass

        # Execute agent call and send outputs in a single event loop.
        # Using two separate loops (one for agent execution, one for output delivery)
        # doubles the loop allocation/teardown cost and risks leaving dangling tasks
        # between the two loops.
        async def run_agent_and_deliver():
            await process_agent()

            # response_chunks is a list defined in the enclosing scope — no nonlocal needed
            response = "".join(response_chunks)

            if not response:
                return response, []

            from src.core.database import create_celery_async_session
            from src.services.agent_output_service import AgentOutputService

            context = {
                "agent_name": agent_db.agent_name,
                "event_type": event_type,
                "provider": provider,
                "webhook_id": webhook_id,
                "event_id": event_id,
            }

            # Wrap output delivery so a failure here doesn't fail the whole task
            try:
                logger.info("📬 Sending outputs to configured destinations...")
                async_session_factory = create_celery_async_session()
                async with async_session_factory() as async_db:
                    output_service = AgentOutputService(async_db)
                    deliveries = await output_service.send_outputs(
                        agent_id=webhook.agent_id,
                        agent_response=response,
                        context=context,
                        webhook_event_id=UUID(event_id),
                        trigger_type="webhook",
                    )
                return response, deliveries
            except Exception as output_error:
                logger.error(f"Error sending outputs: {output_error}", exc_info=True)
                return response, []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response_text, deliveries = loop.run_until_complete(run_agent_and_deliver())
            # Drain background tasks (e.g. LiteLLM async logging) before closing
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()

        # Update event status
        event.status = "completed"
        event.processing_completed_at = datetime.now(UTC)
        db.commit()

        # Log output delivery results
        if response_text and deliveries:
            logger.info(f"📨 Sent {len(deliveries)} outputs")
            for delivery in deliveries:
                if delivery.status == "delivered":
                    logger.info(f"  ✅ {delivery.provider.value}: Delivered")
                else:
                    logger.warning(f"  ❌ {delivery.provider.value}: {delivery.error_message}")

        logger.info(f"✅ Successfully processed webhook event {event_id}")
        if response_text:
            logger.info(f"📝 Agent response preview: {response_text[:200]}...")
        else:
            logger.info("🔧 Agent used tools to handle event (no text response)")

    except PermanentTaskError as e:
        # Permanent error - don't retry
        logger.error(f"❌ Permanent error processing webhook event {event_id}: {e}")
        _update_event_failure(db, event_id, str(e), is_final=True)

    except RetryableTaskError as e:
        # Retryable error - will be auto-retried by Celery
        logger.warning(f"⚠️ Retryable error processing webhook event {event_id}: {e}")
        _update_event_failure(db, event_id, str(e), is_final=False, retry_count=current_retry)
        raise  # Re-raise to trigger Celery's auto-retry

    except Exception as e:
        error_message = str(e)
        logger.error(f"❌ Error processing webhook event {event_id}: {e}", exc_info=True)

        # Check if this is a permanent error based on the message
        if is_permanent_error(error_message):
            logger.info(f"Error classified as permanent - not retrying: {error_message[:100]}")
            _update_event_failure(db, event_id, error_message, is_final=True)
            return  # Don't retry

        # Check if we've exhausted retries
        if current_retry >= self.max_retries:
            logger.error(f"Max retries ({self.max_retries}) exhausted for event {event_id}")
            _update_event_failure(db, event_id, f"Max retries exhausted. Last error: {error_message}", is_final=True)
            return  # Don't retry - we've tried enough

        # Transient error - retry
        logger.info(f"Scheduling retry {current_retry + 1}/{self.max_retries} for event {event_id}")
        _update_event_failure(db, event_id, error_message, is_final=False, retry_count=current_retry)
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task(
    name="execute_spawn_agent_task",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
)
def execute_spawn_agent_task(
    self,
    tenant_id: str,
    parent_agent_id: str,
    task_description: str,
    target_agent_name: str | None = None,
    use_worker_prompt: bool = True,
) -> dict[str, Any]:
    """
    Execute a sub-task in the background via Celery.

    Args:
        tenant_id: Tenant ID for isolation
        parent_agent_id: ID of the parent agent
        task_description: The focused task for the sub-agent to complete
        target_agent_name: Slug/name of the agent to run (parent or registered sub-agent)
        use_worker_prompt: True → apply worker system prompt override (self-clone mode)
                           False → run agent with its own system prompt (registered sub-agent)

    Returns:
        dict with success status and result or error
    """
    db = SessionLocal()
    current_retry = self.request.retries

    try:
        from src.models.agent import Agent
        from src.services.agents.agent_loader_service import AgentLoaderService
        from src.services.agents.agent_manager import AgentManager
        from src.services.agents.chat_service import ChatService
        from src.services.agents.chat_stream_service import ChatStreamService

        logger.info(
            f"Executing spawn_agent task for agent {parent_agent_id} (retry {current_retry}/{self.max_retries})"
        )

        # Load parent agent to resolve tenant and fallback name
        parent_agent = (
            db.query(Agent)
            .filter(
                Agent.id == UUID(parent_agent_id),
                Agent.tenant_id == UUID(tenant_id),
            )
            .first()
        )

        if not parent_agent:
            logger.error(f"Agent {parent_agent_id} not found for tenant {tenant_id} - permanent failure")
            return {"success": False, "error": f"Agent {parent_agent_id} not found"}

        # Use target_agent_name if provided, otherwise fall back to parent agent
        run_agent_name = target_agent_name or parent_agent.agent_name

        focused_prompt = f"""## Sub-Task

{task_description}

Complete this task thoroughly and provide your findings. Be comprehensive but concise."""

        logger.info(f"Calling agent '{run_agent_name}' with sub-task (worker_prompt={use_worker_prompt})")

        agent_manager = AgentManager()
        chat_stream_service = ChatStreamService(
            agent_loader=AgentLoaderService(agent_manager),
            chat_service=ChatService(),
        )

        response_chunks = []

        async def process_agent():
            """Stream agent response and collect chunks."""
            from src.core.database import create_celery_async_session, reset_async_engine

            reset_async_engine()

            stream_kwargs: dict = {
                "agent_name": run_agent_name,
                "tenant_id": str(parent_agent.tenant_id),
                "message": focused_prompt,
                "conversation_history": None,
                "conversation_id": None,
                "attachments": None,
                "llm_config_id": None,
                "override_agentic_config": {"parallel_tools": True},
            }
            if use_worker_prompt:
                stream_kwargs["override_system_prompt"] = _WORKER_SYSTEM_PROMPT

            async_session_factory = create_celery_async_session()
            async with async_session_factory() as async_db:
                stream_kwargs["db"] = async_db
                async for sse_event in chat_stream_service.stream_agent_response(**stream_kwargs):
                    # Parse SSE events
                    if sse_event.startswith("data: "):
                        try:
                            event_data = json.loads(sse_event[6:])
                            if event_data.get("type") == "chunk":
                                response_chunks.append(event_data.get("content", ""))
                        except json.JSONDecodeError:
                            pass

        # Execute async agent call, then drain background tasks (e.g. LiteLLM async
        # logging) with a hard 5-second cap so a hung HTTP call can't stall the worker.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(process_agent())
            pending = {t for t in asyncio.all_tasks(loop) if not t.done()}
            if pending:
                # Give background tasks up to 5 s; cancel whatever is still running.
                done, still_pending = loop.run_until_complete(asyncio.wait(pending, timeout=5.0))
                for task in still_pending:
                    task.cancel()
                if still_pending:
                    loop.run_until_complete(asyncio.gather(*still_pending, return_exceptions=True))
        finally:
            loop.close()

        response_text = "".join(response_chunks)

        if response_text:
            logger.info(f"✅ Spawn agent task completed. Response preview: {response_text[:200]}...")
            return {"success": True, "result": response_text}
        else:
            logger.info("🔧 Spawn agent task completed (agent used tools, no text response)")
            return {"success": True, "result": "Task completed (agent used tools to handle the request)"}

    except Exception as e:
        error_message = str(e)
        logger.error(f"❌ Error executing spawn_agent task: {e}", exc_info=True)

        # Check if this is a permanent error
        if is_permanent_error(error_message):
            logger.info(f"Error classified as permanent - not retrying: {error_message[:100]}")
            return {"success": False, "error": error_message}

        # Check if we've exhausted retries
        if current_retry >= self.max_retries:
            logger.error(f"Max retries ({self.max_retries}) exhausted for spawn_agent task")
            return {"success": False, "error": f"Max retries exhausted. Last error: {error_message}"}

        # Transient error - retry
        logger.info(f"Scheduling retry {current_retry + 1}/{self.max_retries}")
        raise self.retry(exc=e)

    finally:
        db.close()


def _update_event_failure(db, event_id: str, error_message: str, is_final: bool, retry_count: int = 0) -> None:
    """
    Update webhook event with failure information.

    Args:
        db: Database session
        event_id: Event UUID string
        error_message: Error message to store
        is_final: Whether this is a final failure (no more retries)
        retry_count: Current retry count
    """
    try:
        from src.models.agent_webhook import AgentWebhookEvent

        event = db.query(AgentWebhookEvent).filter(AgentWebhookEvent.id == UUID(event_id)).first()

        if event:
            event.retry_count = retry_count
            event.error_message = error_message[:1000] if error_message else None

            if is_final:
                event.status = "failed"
                event.processing_completed_at = datetime.now(UTC)
            else:
                event.status = "retrying"

            db.commit()
    except Exception as update_error:
        logger.error(f"Failed to update event status: {update_error}")
