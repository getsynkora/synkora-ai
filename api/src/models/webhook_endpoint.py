"""
Webhook endpoint model.

A URL a tenant registers to be told about events (usage thresholds, subscription changes). Events for a
tenant are also delivered to the endpoints of the tenant that manages it, so a product that runs customer
tenants hears about all of them on one endpoint.
"""

import sqlalchemy as sa
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from .base import BaseModel


class WebhookEndpoint(BaseModel):
    __tablename__ = "webhook_endpoints"

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant that owns this endpoint",
    )
    url = Column(String(2048), nullable=False, comment="HTTPS URL events are posted to")
    description = Column(String(255), nullable=True)
    secret = Column(Text, nullable=False, comment="Signing secret (encrypted)")
    events = Column(
        ARRAY(String),
        nullable=False,
        default=list,
        comment="Event types to deliver; empty means all events",
    )
    is_active = Column(Boolean, nullable=False, default=True, comment="Switched off after repeated failures")
    consecutive_failures = Column(Integer, nullable=False, default=0)
    last_tested_at = Column(sa.DateTime(timezone=True), nullable=True, comment="Last test ping, for the cooldown")
    last_reactivated_at = Column(
        sa.DateTime(timezone=True), nullable=True, comment="Last time it was switched back on, for the cooldown"
    )
