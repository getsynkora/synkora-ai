"""Synkora Python SDK."""

from .client import AsyncSynkoraClient, SynkoraClient
from .exceptions import (
    AgentNotFoundError,
    APIError,
    AuthError,
    RateLimitError,
    StreamError,
    SynkoraError,
)
from .models import (
    AgentInfo,
    ChatResponse,
    ChunkEvent,
    CompactionEvent,
    ConversationInfo,
    DoneEvent,
    FirstTokenEvent,
    LLMCallEvent,
    SatisfactionPromptEvent,
    StartEvent,
    StatusEvent,
    StreamEvent,
    ToolStatusEvent,
)

__version__ = "0.1.0"
__all__ = [
    # Clients
    "SynkoraClient",
    "AsyncSynkoraClient",
    # Exceptions
    "SynkoraError",
    "AuthError",
    "AgentNotFoundError",
    "RateLimitError",
    "StreamError",
    "APIError",
    # Response models
    "AgentInfo",
    "ConversationInfo",
    "ChatResponse",
    # Stream events
    "StreamEvent",
    "StartEvent",
    "ChunkEvent",
    "StatusEvent",
    "ToolStatusEvent",
    "LLMCallEvent",
    "FirstTokenEvent",
    "DoneEvent",
    "CompactionEvent",
    "SatisfactionPromptEvent",
]
