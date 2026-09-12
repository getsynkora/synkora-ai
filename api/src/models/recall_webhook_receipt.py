"""Committed Recall event IDs; receipt and database effects share a transaction."""

from sqlalchemy import Column, DateTime, String, func

from src.core.database import Base


class RecallWebhookReceipt(Base):
    __tablename__ = "recall_webhook_receipts"

    event_key = Column(String(64), primary_key=True)
    processed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
