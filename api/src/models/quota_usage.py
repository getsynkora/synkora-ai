"""
Quota usage models.

Generic per-pool message metering. A plan defines named quota pools
(``SubscriptionPlan.quota_pools``); these tables record how much of each pool a
tenant has used in a billing period. Pool keys are free-form slugs, so the same
mechanism serves any product or industry.
"""

import sqlalchemy as sa
from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel


class QuotaUsage(BaseModel):
    """Units consumed from one quota pool in one billing period."""

    __tablename__ = "quota_usage"
    __table_args__ = (UniqueConstraint("tenant_id", "pool_key", "period_start", name="uq_quota_usage_period"),)

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant ID",
    )
    pool_key = Column(String(64), nullable=False, comment="Quota pool slug defined by the plan")
    period_start = Column(sa.DateTime(timezone=True), nullable=False, comment="Start of the billing period")
    used = Column(Integer, nullable=False, default=0, comment="Units consumed in this period")


class QuotaUsageEvent(BaseModel):
    """One metered unit, keyed for idempotency so retried tasks never double count."""

    __tablename__ = "quota_usage_events"

    idempotency_key = Column(String(255), nullable=False, unique=True, comment="e.g. msg_<message_id>")
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant ID",
    )
    pool_key = Column(String(64), nullable=False, comment="Quota pool slug")
    period_start = Column(sa.DateTime(timezone=True), nullable=False, comment="Billing period the unit counted in")
    amount = Column(Integer, nullable=False, default=1, comment="Units consumed")
