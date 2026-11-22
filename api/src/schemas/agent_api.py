"""
Pydantic schemas for Agent API endpoints.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Request Schemas


class ChatRequest(BaseModel):
    """Request schema for agent chat."""

    message: str = Field(..., description="The message to send to the agent")
    conversation_id: UUID | None = Field(None, description="Optional conversation ID to continue existing conversation")
    metadata: dict[str, Any] | None = Field(default_factory=dict, description="Optional metadata for the message")
    language: str | None = Field(
        None,
        max_length=20,
        description="Language of the client UI as a BCP-47 code (e.g. 'de'); the agent replies in it by default",
    )
    external_user_id: str | None = Field(
        None,
        max_length=255,
        description="Your id for the end user. Stored on a new conversation; continuing it requires the same id",
    )
    external_org_id: str | None = Field(None, max_length=255, description="Your id for the end user's organisation")
    external_user_name: str | None = Field(None, max_length=255)
    external_user_email: str | None = Field(None, max_length=255)
    attachments: list[dict[str, Any]] | None = Field(
        None,
        description='Files uploaded to this conversation, as [{"token": "..."}] from the attachments endpoint (max 5)',
    )


class CreateApiKeyRequest(BaseModel):
    """Request schema for creating an API key."""

    key_name: str = Field(..., description="Name for the API key")
    agent_id: UUID | None = Field(None, description="Optional agent ID to scope the key to")
    permissions: list[str] = Field(
        default_factory=lambda: ["agent:chat"],
        description="List of permissions for the API key",
    )
    rate_limit_per_minute: int = Field(60, description="Rate limit per minute", ge=1, le=1000)
    rate_limit_per_hour: int = Field(3600, description="Rate limit per hour", ge=1, le=100000)
    rate_limit_per_day: int = Field(10000, description="Rate limit per day", ge=1, le=1000000)
    allowed_ips: list[str] | None = Field(None, description="List of allowed IP addresses")
    allowed_origins: list[str] | None = Field(None, description="List of allowed CORS origins")
    expires_at: datetime | None = Field(None, description="Optional expiration date for the key")

    @field_validator("permissions")
    @classmethod
    def _check_permissions(cls, value):
        # Validated here so both the create and the update routes refuse operator-only or malformed permissions
        from src.services.agent_api.api_key_service import validate_requested_permissions

        return value if value is None else validate_requested_permissions(value)


class UpdateApiKeyRequest(BaseModel):
    """Request schema for updating an API key."""

    key_name: str | None = Field(None, description="New name for the API key")
    is_active: bool | None = Field(None, description="Active status")
    permissions: list[str] | None = Field(None, description="Updated permissions")
    rate_limit_per_minute: int | None = Field(None, description="Updated rate limit per minute", ge=1, le=1000)
    rate_limit_per_hour: int | None = Field(None, description="Updated rate limit per hour", ge=1, le=100000)
    rate_limit_per_day: int | None = Field(None, description="Updated rate limit per day", ge=1, le=1000000)
    allowed_ips: list[str] | None = Field(None, description="Updated list of allowed IP addresses")
    allowed_origins: list[str] | None = Field(None, description="Updated list of allowed CORS origins")
    expires_at: datetime | None = Field(None, description="Updated expiration date")

    @field_validator("permissions")
    @classmethod
    def _check_permissions(cls, value):
        # Validated here so both the create and the update routes refuse operator-only or malformed permissions
        from src.services.agent_api.api_key_service import validate_requested_permissions

        return value if value is None else validate_requested_permissions(value)


# Response Schemas


class ChatResponse(BaseModel):
    """Response schema for agent chat."""

    conversation_id: UUID = Field(..., description="The conversation ID")
    message: str = Field(..., description="The agent's response message")
    tokens_used: int | None = Field(None, description="Number of tokens used")
    metadata: dict[str, Any] | None = Field(default_factory=dict, description="Additional metadata")


class AgentInfo(BaseModel):
    """Schema for agent information."""

    id: UUID = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent name")
    description: str | None = Field(None, description="Agent description")
    model: str | None = Field(None, description="LLM model used by the agent")
    capabilities: list[str] | None = Field(default_factory=list, description="Agent capabilities")


class AgentListResponse(BaseModel):
    """Response schema for listing agents."""

    agents: list[AgentInfo] = Field(..., description="List of available agents")
    total: int = Field(..., description="Total number of agents")


class ApiKeyResponse(BaseModel):
    """Response schema for API key (without sensitive data)."""

    id: UUID = Field(..., description="API key ID")
    key_name: str = Field(..., description="API key name")
    key_prefix: str = Field(..., description="API key prefix (e.g., sk_live_)")
    agent_id: UUID | None = Field(None, description="Scoped agent ID")
    permissions: list[str] = Field(..., description="List of permissions")
    rate_limit_per_minute: int = Field(..., description="Rate limit per minute")
    rate_limit_per_hour: int = Field(..., description="Rate limit per hour")
    rate_limit_per_day: int = Field(..., description="Rate limit per day")
    allowed_ips: list[str] | None = Field(None, description="Allowed IP addresses")
    allowed_origins: list[str] | None = Field(None, description="Allowed origins")
    is_active: bool = Field(..., description="Active status")
    expires_at: datetime | None = Field(None, description="Expiration date")
    last_used_at: datetime | None = Field(None, description="Last used timestamp")
    total_requests: int = Field(0, description="Total number of requests")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CreateApiKeyResponse(BaseModel):
    """Response schema for creating an API key (includes full key once)."""

    id: UUID = Field(..., description="API key ID")
    key_name: str = Field(..., description="API key name")
    api_key: str = Field(..., description="Full API key (only shown once at creation)")
    key_prefix: str = Field(..., description="API key prefix")
    agent_id: UUID | None = Field(None, description="Scoped agent ID")
    permissions: list[str] = Field(..., description="List of permissions")
    rate_limit_per_minute: int = Field(..., description="Rate limit per minute")
    rate_limit_per_hour: int = Field(..., description="Rate limit per hour")
    rate_limit_per_day: int = Field(..., description="Rate limit per day")
    allowed_ips: list[str] | None = Field(None, description="Allowed IP addresses")
    allowed_origins: list[str] | None = Field(None, description="Allowed origins")
    expires_at: datetime | None = Field(None, description="Expiration date")
    created_at: datetime = Field(..., description="Creation timestamp")


class ApiKeyListResponse(BaseModel):
    """Response schema for listing API keys."""

    keys: list[ApiKeyResponse] = Field(..., description="List of API keys")
    total: int = Field(..., description="Total number of keys")


class UsageStats(BaseModel):
    """Schema for usage statistics."""

    total_requests: int = Field(..., description="Total number of requests")
    total_tokens: int = Field(..., description="Total tokens used")
    total_cost: float = Field(..., description="Total cost")
    period_start: datetime = Field(..., description="Period start date")
    period_end: datetime = Field(..., description="Period end date")


class UsageByEndpoint(BaseModel):
    """Schema for usage statistics by endpoint."""

    endpoint: str = Field(..., description="API endpoint")
    requests: int = Field(..., description="Number of requests")
    avg_response_time_ms: float = Field(..., description="Average response time in ms")
    error_rate: float = Field(..., description="Error rate (0-1)")


class UsageStatsResponse(BaseModel):
    """Response schema for usage statistics."""

    overall: UsageStats = Field(..., description="Overall usage statistics")
    by_endpoint: list[UsageByEndpoint] = Field(..., description="Usage statistics by endpoint")


class ChatResponse(BaseModel):
    """Complete (non-streaming) agent reply."""

    conversation_id: UUID = Field(..., description="Conversation the reply belongs to")
    message: str = Field(..., description="The agent's reply")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="Knowledge sources used, if any")
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateConversationRequest(BaseModel):
    """Request schema for starting a conversation."""

    name: str | None = Field(None, max_length=255)
    external_user_id: str | None = Field(None, max_length=255)
    external_org_id: str | None = Field(None, max_length=255)
    external_user_name: str | None = Field(None, max_length=255)
    external_user_email: str | None = Field(None, max_length=255)


class MessageFeedbackRequest(BaseModel):
    """Thumbs up or down on a message."""

    rating: Literal["up", "down"] | None = Field(None, description="'up', 'down', or null to clear")
    comment: str | None = Field(None, max_length=2000)
    external_user_id: str | None = Field(None, max_length=255, description="Must match the conversation's end user")


class ConversationInfo(BaseModel):
    """Schema for conversation information."""

    id: UUID = Field(..., description="Conversation ID")
    agent_id: UUID = Field(..., description="Agent ID")
    name: str | None = Field(None, description="Conversation name")
    external_user_id: str | None = Field(None, description="Your id for the end user it belongs to")
    external_org_id: str | None = Field(None, description="Your id for the end user's organisation")
    external_user_name: str | None = Field(None)
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(..., description="Number of messages in conversation")


class ConversationListResponse(BaseModel):
    """Response schema for listing conversations."""

    conversations: list[ConversationInfo] = Field(..., description="List of conversations")
    total: int = Field(..., description="Total number of conversations")


class ErrorResponse(BaseModel):
    """Schema for error responses."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: dict[str, Any] | None = Field(None, description="Additional details")
