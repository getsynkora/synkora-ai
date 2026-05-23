"""
PhoneCall Model

Records an inbound phone call, linked to a Conversation for transcript storage.
"""

import enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID

from src.models.base import BaseModel, TenantMixin


class PhoneCallStatus(enum.StrEnum):
    RINGING = "ringing"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no_answer"


class PhoneCall(BaseModel, TenantMixin):
    """
    Record of a single inbound phone call.

    Linked to a Conversation so the full transcript is visible in Agent Lens.
    """

    __tablename__ = "phone_calls"

    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)

    phone_number_id = Column(
        UUID(as_uuid=True), ForeignKey("phone_numbers.id", ondelete="SET NULL"), nullable=True, index=True
    )

    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    provider = Column(String(50), nullable=False, default="vapi")

    provider_call_id = Column(String(255), nullable=False, index=True, comment="Provider's call identifier")

    caller_number = Column(String(20), nullable=True, comment="E.164 caller number")

    status = Column(String(20), nullable=False, default=PhoneCallStatus.RINGING)

    started_at = Column(DateTime(timezone=True), nullable=True)

    answered_at = Column(DateTime(timezone=True), nullable=True)

    ended_at = Column(DateTime(timezone=True), nullable=True)

    duration_seconds = Column(Integer, nullable=True)

    recording_url = Column(Text, nullable=True)

    cost_cents = Column(Integer, nullable=True)

    call_metadata = Column(JSON, nullable=True, comment="Provider-specific extras")

    def __repr__(self) -> str:
        return f"<PhoneCall(id={self.id}, provider_call_id='{self.provider_call_id}', status='{self.status}')>"
