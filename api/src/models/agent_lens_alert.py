"""
Agent Lens Alert Model

Alert configuration per agent — threshold-based monitoring rules.
"""

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.models.base import BaseModel, TenantMixin


class AgentLensAlert(BaseModel, TenantMixin):
    """Alert configuration for an agent metric threshold."""

    __tablename__ = "agent_lens_alerts"

    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(String(255), nullable=False)

    # Metric: failure_rate | cost_per_session | avg_latency_ms | total_cost_usd | token_count
    metric = Column(String(50), nullable=False)
    # Condition: gt | lt
    condition = Column(String(10), nullable=False)
    threshold = Column(Numeric(14, 4), nullable=False)
    window_minutes = Column(Integer, nullable=False, server_default="60")

    # Notification: email | webhook
    notify_method = Column(String(20), nullable=False, server_default="email")
    notify_config = Column(JSONB, nullable=True)  # {email: "...", url: "..."}

    is_active = Column(Boolean, nullable=False, server_default="true")
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_lens_alert_tenant_agent", "tenant_id", "agent_id"),)
