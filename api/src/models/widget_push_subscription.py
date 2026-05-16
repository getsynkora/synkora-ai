"""Widget push subscription model for FCM mobile push notifications."""

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.models.base import BaseModel


class WidgetPushSubscription(BaseModel):
    """
    Stores FCM device tokens per widget/conversation so the backend
    can send push notifications when an agent reply completes.

    No FK constraints — survives widget or conversation deletion.
    """

    __tablename__ = "widget_push_subscriptions"

    widget_id = Column(UUID(as_uuid=True), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), nullable=True)
    fcm_token = Column(Text, nullable=False)
    platform = Column(String(20), nullable=False)  # 'android' | 'ios' | 'web'
    external_user_id = Column(String(255), nullable=True)  # app-side user identifier for per-user topic targeting

    def __repr__(self) -> str:
        return f"<WidgetPushSubscription(widget={self.widget_id}, platform={self.platform})>"
