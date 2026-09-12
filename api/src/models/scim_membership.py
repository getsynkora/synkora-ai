"""Tenant-local SCIM profile retained while membership is suspended."""

from sqlalchemy import JSON, CheckConstraint, Column, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import BaseModel


class SCIMMembership(BaseModel):
    __tablename__ = "scim_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_id", name="uq_scim_membership"),
        CheckConstraint("role IN ('normal', 'admin', 'owner')", name="ck_scim_membership_role"),
    )

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    display_name = Column(String(255), nullable=True)
    role = Column(String(30), nullable=False, default="normal")

    membership_attributes = Column(JSON, nullable=True)
