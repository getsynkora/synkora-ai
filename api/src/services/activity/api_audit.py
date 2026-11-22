"""Audit trail for privileged actions taken with an API key (no logged-in account is involved)."""

import logging
from typing import Any
from uuid import UUID

from fastapi import Request

from src.services.activity.activity_log_service import ActivityLogService

logger = logging.getLogger(__name__)


def audit_api_action(
    api_key: Any,
    request: Request | None,
    action: str,
    resource_type: str,
    resource_id: UUID | None = None,
    details: dict | None = None,
) -> None:
    """
    Record an action in the acting tenant's activity log, with the key that did it. Never raises: an audit
    failure must not undo or block the action, but it is logged.
    """
    try:
        ActivityLogService.queue_activity(
            tenant_id=api_key.tenant_id,
            account_id=None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details={"api_key_id": str(api_key.id), "api_key_prefix": api_key.key_prefix, **(details or {})},
            ip_address=request.client.host if request is not None and request.client else None,
            user_agent=request.headers.get("User-Agent", "")[:255] if request is not None else None,
        )
    except Exception:
        logger.warning("Could not record audit event %s", action, exc_info=True)
