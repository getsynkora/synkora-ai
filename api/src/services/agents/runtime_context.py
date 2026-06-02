"""
Runtime context for tool execution.

Provides execution environment without exposing credentials.
Credentials are resolved on-demand by the CredentialResolver.
"""

import logging
import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Context variables for thread-safe credential injection
_runtime_context: ContextVar[Optional["RuntimeContext"]] = ContextVar("runtime_context", default=None)
_authenticated_clients: ContextVar[dict[str, Any] | None] = ContextVar("authenticated_clients", default=None)


@dataclass
class RuntimeContext:
    """
    Runtime execution context for agent tools.

    This context contains execution environment information but NO credentials.
    Credentials are resolved on-demand by the CredentialResolver when tools need them.

    For multi-agent systems, this context includes shared_state for communication
    between parent and sub-agents in the same execution hierarchy.

    Attributes:
        tenant_id: Multi-tenant isolation
        agent_id: Which agent is executing
        db_session: Database access for credential resolution
        llm_client: LLM client for tools that need to generate content (optional)
        conversation_id: Chat context (optional)
        message_id: Message context (optional)
        user_id: User context (optional)
        shared_state: Shared state dictionary for multi-agent communication (optional)
    """

    tenant_id: uuid.UUID
    agent_id: uuid.UUID
    db_session: AsyncSession | None
    db_session_factory: Callable[[], Any] | None = None
    llm_client: Any | None = None
    agent_slug: str | None = None  # Cached slug — avoids DB lookups in spawn_agent tools
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    shared_state: dict[str, Any] | None = None
    all_available_tools: list[dict[str, Any]] | None = None  # Agent's assigned tools only
    allowed_database_connections: list[str] | None = None  # Allowed DB connection IDs (None = all)
    compute_session: Any | None = None  # ComputeSession | None — remote compute backend
    email_template_id: uuid.UUID | None = None  # Assigned email template for this agent
    # Agent trace: monotonic counters for ES event ordering within a turn
    event_sequence: int = field(default=0)  # Increments per event; threaded through all hooks
    llm_call_index: int = field(default=0)  # Resets to 0 each user turn; increments per LLM call

    def __post_init__(self):
        """Initialize shared_state if not provided."""
        if self.shared_state is None:
            self.shared_state = {}

    def __enter__(self):
        """Set this context as active for the current execution."""
        _runtime_context.set(self)
        _authenticated_clients.set({})
        logger.debug(f"Runtime context activated for agent {self.agent_id}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clear context and cleanup authenticated clients."""
        # Close all authenticated clients
        clients = _authenticated_clients.get()
        if clients:
            for service_name, client in clients.items():
                if hasattr(client, "close"):
                    try:
                        client.close()
                        logger.debug(f"Closed authenticated client: {service_name}")
                    except Exception as e:
                        logger.warning(f"Failed to close {service_name} client: {e}")

        # Clear context variables
        _authenticated_clients.set(None)
        _runtime_context.set(None)
        logger.debug(f"Runtime context deactivated for agent {self.agent_id}")

    def set_state(self, key: str, value: Any) -> None:
        """
        Set a value in the shared state.

        This state is accessible to all agents in the execution hierarchy
        (parent and sub-agents share the same state dictionary).

        Args:
            key: State key
            value: Value to store
        """
        if self.shared_state is None:
            self.shared_state = {}
        self.shared_state[key] = value
        logger.debug(f"State updated: {key} = {str(value)[:100]}")

    def get_state(self, key: str, default: Any = None) -> Any:
        """
        Get a value from the shared state.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        if self.shared_state is None:
            return default
        return self.shared_state.get(key, default)

    def get_all_state(self) -> dict[str, Any]:
        """
        Get the entire shared state dictionary.

        Returns:
            Copy of the shared state
        """
        if self.shared_state is None:
            return {}
        return self.shared_state.copy()

    def create_child_context(self, child_agent_id: uuid.UUID) -> "RuntimeContext":
        """
        Create a child context for a sub-agent.

        The child context inherits the same shared_state dictionary,
        enabling state sharing between parent and sub-agents.

        Args:
            child_agent_id: ID of the sub-agent

        Returns:
            New RuntimeContext for the child agent
        """
        return RuntimeContext(
            tenant_id=self.tenant_id,
            agent_id=child_agent_id,
            db_session=self.db_session,
            db_session_factory=self.db_session_factory,
            llm_client=self.llm_client,
            # child_agent_id differs, so agent_slug is not inherited
            conversation_id=self.conversation_id,
            message_id=self.message_id,
            user_id=self.user_id,
            shared_state=self.shared_state,  # Share the same state dict!
            compute_session=self.compute_session,  # Propagate compute to sub-agents
            event_sequence=self.event_sequence,
        )

    def with_db_session(self, db_session: AsyncSession) -> "RuntimeContext":
        """
        Return a sibling context that shares execution state but uses a concrete
        short-lived DB session.
        """
        clone = RuntimeContext(
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            db_session=db_session,
            db_session_factory=self.db_session_factory,
            llm_client=self.llm_client,
            agent_slug=self.agent_slug,
            conversation_id=self.conversation_id,
            message_id=self.message_id,
            user_id=self.user_id,
            shared_state=self.shared_state,
            all_available_tools=self.all_available_tools,
            allowed_database_connections=self.allowed_database_connections,
            compute_session=self.compute_session,
            email_template_id=self.email_template_id,
            event_sequence=self.event_sequence,
            llm_call_index=self.llm_call_index,
        )
        return clone

    @asynccontextmanager
    async def scoped_db_context(self) -> AsyncGenerator["RuntimeContext", None]:
        """
        Yield a context with a usable DB session.

        HTTP chat streaming can keep db_session unset to avoid holding a pooled
        DB connection while waiting on external LLM calls. Tool execution then
        opens a short session only around the tool call.
        """
        if self.db_session is not None:
            yield self
            return

        factory = self.db_session_factory
        if factory is None:
            from src.core.database import get_async_session_factory

            factory = get_async_session_factory()

        async with factory() as session:
            yield self.with_db_session(session)


def get_runtime_context() -> RuntimeContext | None:
    """
    Get the current runtime context.

    Returns:
        Current RuntimeContext or None if not in a context
    """
    return _runtime_context.get()


def set_authenticated_client(service_name: str, client: Any) -> None:
    """
    Set an authenticated client in the current context.

    This is called by the CredentialResolver to inject authenticated clients
    that tools can access via get_authenticated_client().

    Args:
        service_name: Name of the service (e.g., "github", "gmail")
        client: Authenticated client instance
    """
    clients = _authenticated_clients.get()
    if clients is not None:
        clients[service_name] = client
        logger.debug(f"Injected authenticated client: {service_name}")
    else:
        logger.warning(f"Attempted to set authenticated client '{service_name}' outside of runtime context")


def get_authenticated_client(service_name: str) -> Any | None:
    """
    Get an authenticated client from the current context.

    Tools call this function to access authenticated clients that have been
    injected by the CredentialResolver based on the tool's auth requirements.

    Args:
        service_name: Name of the service (e.g., "github", "gmail")

    Returns:
        Authenticated client instance or None if not available

    Example:
        >>> github = get_authenticated_client("github")
        >>> if github:
        >>>     repos = github.search_repositories(query)
    """
    clients = _authenticated_clients.get()
    if clients is None:
        logger.warning(f"Attempted to get authenticated client '{service_name}' outside of runtime context")
        return None

    client = clients.get(service_name)
    if client is None:
        logger.debug(f"Authenticated client not found: {service_name}")

    return client


def clear_authenticated_client(service_name: str) -> None:
    """
    Clear a specific authenticated client from the current context.

    Args:
        service_name: Name of the service to clear
    """
    clients = _authenticated_clients.get()
    if clients and service_name in clients:
        client = clients.pop(service_name)
        if hasattr(client, "close"):
            try:
                client.close()
                logger.debug(f"Closed and cleared authenticated client: {service_name}")
            except Exception as e:
                logger.warning(f"Failed to close {service_name} client: {e}")
