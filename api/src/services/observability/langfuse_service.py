"""
Langfuse Service for LLM Observability and Tracing.

This service provides centralized Langfuse integration for:
- Tracing LLM calls with input/output
- Monitoring token usage and costs
- Debugging agent behavior and tool calls
- Analyzing conversation flows
- Tracking performance metrics
"""

import logging
import random
from typing import Any

from langfuse import Langfuse

from src.config.settings import settings
from src.services.observability.trace_redactor import redact, redact_messages

logger = logging.getLogger(__name__)


class LangfuseService:
    """
    Service for Langfuse observability integration.

    Provides methods for tracing LLM calls, agent executions, and tool usage.
    Supports configurable sampling rates and per-agent enable/disable.
    """

    _instance: "LangfuseService | None" = None
    _client: Langfuse | None = None
    _is_agent_specific: bool = False  # True for per-agent instances with custom credentials

    def __new__(cls) -> "LangfuseService":
        """Singleton pattern to ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize Langfuse client if configured."""
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._is_agent_specific = False
            self._setup_client()

    @classmethod
    def for_agent(cls, agent_config: dict[str, Any] | None) -> "LangfuseService":
        """
        Get a LangfuseService for an agent.

        If the agent has its own Langfuse credentials (host, public_key, secret_key),
        returns a new non-singleton instance configured with those credentials.
        Otherwise returns the global singleton.

        Args:
            agent_config: Agent observability configuration dict

        Returns:
            LangfuseService instance configured for this agent
        """
        if agent_config:
            host = agent_config.get("langfuse_host")
            public_key = agent_config.get("langfuse_public_key")
            secret_key = agent_config.get("langfuse_secret_key")
            if host and public_key and secret_key:
                # Create a per-agent instance bypassing the singleton
                instance = object.__new__(cls)
                instance._initialized = True
                instance._is_agent_specific = True
                instance._client = None
                try:
                    instance._client = Langfuse(
                        public_key=public_key,
                        secret_key=secret_key,
                        host=host,
                    )
                    logger.info("Per-agent Langfuse client initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to create per-agent Langfuse client: {e}")
                return instance
        return cls()  # Return global singleton

    def _setup_client(self) -> None:
        """Set up Langfuse client if properly configured."""
        if settings.is_configured:
            try:
                self._client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
                logger.info("Langfuse client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Langfuse client: {e}")
                self._client = None
        else:
            logger.info("Langfuse not configured, tracing disabled")
            self._client = None

    @property
    def is_enabled(self) -> bool:
        """Check if Langfuse is enabled and configured."""
        if self._is_agent_specific:
            # Per-agent instance: enabled as long as the client was created successfully
            return self._client is not None
        return settings.langfuse_enabled and self._client is not None

    def should_trace(self, agent_config: dict[str, Any] | None = None) -> bool:
        """
        Determine if a trace should be created based on configuration.

        Args:
            agent_config: Optional agent-specific observability configuration

        Returns:
            bool: True if trace should be created
        """
        if not self.is_enabled:
            return False

        # Check agent-specific configuration
        if agent_config:
            agent_enabled = agent_config.get("langfuse_enabled", True)
            if not agent_enabled:
                return False

            # Agent-specific sample rate
            agent_sample_rate = agent_config.get("sample_rate", settings.langfuse_sample_rate)
        else:
            agent_sample_rate = settings.langfuse_sample_rate

        # Apply sampling
        return random.random() < agent_sample_rate

    def create_trace(
        self,
        name: str,
        user_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Create a new trace for tracking an operation.

        Args:
            name: Name of the trace
            user_id: Optional user identifier
            session_id: Optional session/conversation identifier
            metadata: Optional metadata to attach to the trace

        Returns:
            str | None: Trace ID if created, None otherwise
        """
        if not self.is_enabled or not self._client:
            return None

        try:
            trace = self._client.trace(
                name=name,
                user_id=user_id,
                session_id=session_id,
                metadata=metadata or {},
            )
            return trace.id
        except Exception as e:
            logger.error(f"Failed to create trace: {e}")
            return None

    def update_trace(
        self,
        trace_id: str,
        output: dict[str, Any] | str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Update an existing trace with output and metadata.

        Args:
            trace_id: ID of the trace to update
            output: Output data
            metadata: Optional additional metadata
        """
        if not self.is_enabled or not self._client:
            return

        try:
            self._client.trace(
                id=trace_id,
                output=output,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to update trace: {e}")

    def create_generation(
        self,
        name: str,
        model: str,
        input_data: dict[str, Any] | str,
        output_data: dict[str, Any] | str | None = None,
        metadata: dict[str, Any] | None = None,
        usage: dict[str, int] | None = None,
        trace_id: str | None = None,
        parent_observation_id: str | None = None,
    ) -> str | None:
        """
        Create a generation (LLM call) observation.

        Args:
            name: Name of the generation
            model: Model identifier
            input_data: Input prompt/messages
            output_data: Output response
            metadata: Optional metadata
            usage: Token usage information
            trace_id: Optional trace ID to attach to
            parent_observation_id: Optional parent observation ID

        Returns:
            str | None: Generation ID if created, None otherwise
        """
        if not self.is_enabled or not self._client:
            return None

        # Redact PII/secrets before sending to Langfuse
        if isinstance(input_data, str):
            input_data = redact(input_data)
        elif isinstance(input_data, dict):
            input_data = {
                k: redact(v) if isinstance(v, str) else (redact_messages(v) if isinstance(v, list) else v)
                for k, v in input_data.items()
            }
        if isinstance(output_data, str):
            output_data = redact(output_data)
        elif isinstance(output_data, dict):
            output_data = {k: redact(v) if isinstance(v, str) else v for k, v in output_data.items()}

        try:
            generation = self._client.generation(
                name=name,
                model=model,
                input=input_data,
                output=output_data,
                metadata=metadata or {},
                usage=usage,
                trace_id=trace_id,
                parent_observation_id=parent_observation_id,
            )
            return generation.id
        except Exception as e:
            logger.error(f"Failed to create generation: {e}")
            return None

    def update_generation(
        self,
        generation_id: str,
        output_data: dict[str, Any] | str | None = None,
        usage: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Update an existing generation with output, usage, and metadata.

        Args:
            generation_id: ID of the generation to update
            output_data: Output response data
            usage: Token usage information
            metadata: Optional additional metadata
        """
        if not self.is_enabled or not self._client:
            return

        # Redact PII/secrets before sending to Langfuse
        if isinstance(output_data, str):
            output_data = redact(output_data)
        elif isinstance(output_data, dict):
            output_data = {k: redact(v) if isinstance(v, str) else v for k, v in output_data.items()}

        try:
            self._client.generation(
                id=generation_id,
                output=output_data,
                usage=usage,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to update generation: {e}")

    def create_span(
        self,
        name: str,
        input_data: dict[str, Any] | str | None = None,
        output_data: dict[str, Any] | str | None = None,
        metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
        parent_observation_id: str | None = None,
    ) -> None:
        """
        Create a span observation for tracking operations.

        Note: This method creates a complete span in one call.
        The Langfuse SDK handles everything internally - no need to update separately.

        Args:
            name: Name of the span
            input_data: Optional input data
            output_data: Optional output data
            metadata: Optional metadata
            trace_id: Optional trace ID to attach to
            parent_observation_id: Optional parent observation ID
        """
        if not self.is_enabled or not self._client:
            return

        try:
            self._client.span(
                name=name,
                input=input_data,
                output=output_data,
                metadata=metadata or {},
                trace_id=trace_id,
                parent_observation_id=parent_observation_id,
            )
        except Exception as e:
            logger.error(f"Failed to create span: {e}")

    def score_generation(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        """
        Add a score to a trace (e.g., user feedback).

        Args:
            trace_id: ID of the trace to score
            name: Name of the score (e.g., "user_feedback", "quality")
            value: Score value
            comment: Optional comment
        """
        if not self.is_enabled or not self._client:
            return

        try:
            self._client.score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment,
            )
        except Exception as e:
            logger.error(f"Failed to score generation: {e}")

    def flush(self) -> None:
        """Flush any pending traces to Langfuse."""
        if self._client:
            try:
                self._client.flush()
            except Exception as e:
                logger.error(f"Failed to flush Langfuse client: {e}")

    def shutdown(self) -> None:
        """Shutdown the Langfuse client gracefully."""
        if self._client:
            try:
                self._client.flush()
                logger.info("Langfuse client shut down successfully")
            except Exception as e:
                logger.error(f"Error during Langfuse shutdown: {e}")

    @staticmethod
    def get_trace_url(trace_id: str) -> str:
        """
        Get the Langfuse UI URL for a trace.

        Args:
            trace_id: ID of the trace

        Returns:
            str: URL to view the trace in Langfuse UI
        """
        return f"{settings.langfuse_host}/trace/{trace_id}"


# Global instance
langfuse_service = LangfuseService()
