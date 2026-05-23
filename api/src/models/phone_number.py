"""
PhoneNumber Model

Stores phone numbers (BYOP or platform-provisioned) linked to an agent.
"""

from sqlalchemy import Boolean, Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import BaseModel, TenantMixin


class PhoneNumber(BaseModel, TenantMixin):
    """
    Phone number record linked to an agent.

    Phase 1: BYOP only (is_provisioned=False).
    """

    __tablename__ = "phone_numbers"

    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)

    provider = Column(String(50), nullable=False, default="vapi", comment="Call platform provider (vapi)")

    phone_number = Column(String(20), nullable=False, comment="E.164 format, e.g. +14155551234")

    is_provisioned = Column(Boolean, nullable=False, default=False, comment="False = BYOP, True = platform-provisioned")

    provider_number_id = Column(String(255), nullable=True, comment="Provider's internal reference (nullable for BYOP)")

    is_active = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<PhoneNumber(id={self.id}, number='{self.phone_number}', provider='{self.provider}')>"
