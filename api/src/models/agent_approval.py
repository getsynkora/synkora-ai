"""Agent Approval Request model for Human-in-the-Loop (HITL) flows."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.core.database import Base


class ApprovalStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"


class AgentApprovalRequest(Base):
    """
    Persists a pending human approval gate for an autonomous agent action.

    Lifecycle:
      PENDING → APPROVED (user said yes) → EXECUTED (tool ran)
      PENDING → REJECTED (user said no or gave feedback)
      PENDING → EXPIRED  (TTL elapsed without reply)
    """

    __tablename__ = "agent_approval_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("scheduled_tasks.id", ondelete="CASCADE"), nullable=True)
    conversation_id = Column(UUID(as_uuid=True), nullable=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    agent_id = Column(UUID(as_uuid=True), nullable=False)
    agent_name = Column(String(255), nullable=False)

    # The exact tool call being gated
    tool_name = Column(String(255), nullable=False)
    tool_args = Column(JSONB, nullable=False, default=dict)
    tool_args_hash = Column(String(64), nullable=False)  # sha256(json(sorted tool_args))

    status = Column(
        Enum(ApprovalStatus, name="approval_status_enum"),
        nullable=False,
        default=ApprovalStatus.PENDING,
    )

    # Which channel was used to notify the user
    notification_channel = Column(String(50), nullable=False)  # slack | whatsapp | whatsapp_web | chat
    # Channel-specific routing info (slack_bot_id+channel_id, to_phone, conversation_id, etc.)
    notification_ref = Column(JSONB, nullable=False, default=dict)

    expires_at = Column(DateTime(timezone=True), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    execution_result = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        Index("ix_approval_task_status", "task_id", "status"),
        Index("ix_approval_tenant_status", "tenant_id", "status"),
        Index("ix_approval_agent_status", "agent_id", "status"),
        Index("ix_approval_conversation_status", "conversation_id", "status"),
    )
