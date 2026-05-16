"""
Agent Tool Call Log Model

Persists tool call telemetry beyond the 24h Redis TTL.
No FK constraints — survives agent/conversation deletion, same pattern as LLMTokenUsage.
"""

from sqlalchemy import Boolean, Column, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.models.base import BaseModel


class AgentToolCallLog(BaseModel):
    """Persisted record of a single tool execution."""

    __tablename__ = "agent_tool_call_logs"

    # No FK constraints — rows must survive parent deletion
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    agent_id = Column(UUID(as_uuid=True), nullable=True)
    conversation_id = Column(UUID(as_uuid=True), nullable=True)
    message_id = Column(UUID(as_uuid=True), nullable=True)

    tool_name = Column(String(255), nullable=False)
    tool_args = Column(JSONB, nullable=True)
    tool_result = Column(JSONB, nullable=True)  # truncated to 2 KB

    success = Column(Boolean, nullable=False, server_default="true")
    duration_ms = Column(Integer, nullable=True)
    retry_count = Column(Integer, nullable=False, server_default="0")
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_tool_call_tenant_agent_created", "tenant_id", "agent_id", "created_at"),
        Index("ix_tool_call_conversation_created", "conversation_id", "created_at"),
        Index("ix_tool_call_tenant_success", "tenant_id", "success"),
    )
