"""Audit chain append and full-field integrity verification.

Legacy entries remain distinguishable; they cannot establish full-field integrity.
Retention/deletion and tail truncation require an independently retained checkpoint.
"""

import hmac
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64


async def append_audit_log(
    db: AsyncSession,
    *,
    action: str,
    activity_type,
    account_id=None,
    tenant_id=None,
    resource_type=None,
    resource_id=None,
    description=None,
    activity_metadata=None,
    ip_address=None,
    user_agent=None,
    status="success",
    error_message=None,
) -> ActivityLog:
    """Append through the same locked transaction path used by activity logging."""
    from src.services.activity.activity_log_service import ActivityLogService

    return await ActivityLogService(db)._prepare_log_entry(
        tenant_id=tenant_id,
        account_id=account_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=activity_metadata,
        ip_address=ip_address,
        user_agent=user_agent,
        activity_type=activity_type,
        description=description,
        status=status,
        error_message=error_message,
    )


async def verify_chain(db: AsyncSession, tenant_id, limit=1000) -> dict:
    """Verify a chronological prefix, explicitly reporting legacy and truncated coverage."""
    if not 1 <= limit <= 10000:
        raise ValueError("Audit verification limit must be between 1 and 10000")
    if not settings.audit_chain_secret:
        logger.warning("AUDIT_CHAIN_SECRET not set; falling back to SECRET_KEY. Set a dedicated key for production.")
    secret = settings.audit_chain_secret or settings.secret_key
    if len(secret) < 32:
        return {"valid": False, "checked": 0, "error": "A strong audit signing key is required"}
    result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.tenant_id == tenant_id)
        .order_by(ActivityLog.created_at.asc(), ActivityLog.id.asc())
        .limit(limit + 1)
    )
    entries = result.scalars().all()
    prev_hash, checked, legacy = GENESIS_HASH, 0, 0
    for entry in entries[:limit]:
        metadata = entry.activity_metadata or {}
        audit = metadata.get("_audit", {})
        if not isinstance(audit, dict) or audit.get("version") != 2:
            legacy += 1
            prev_hash = entry.entry_hash or GENESIS_HASH
            continue
        expected = ActivityLog.compute_hash(
            entry_id=str(entry.id),
            action=entry.action,
            account_id=entry.account_id,
            tenant_id=entry.tenant_id,
            activity_type=str(entry.activity_type),
            created_at=entry.created_at.isoformat(),
            prev_hash=prev_hash,
            secret_key=secret,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            description=entry.description,
            activity_metadata=metadata,
            ip_address=entry.ip_address,
            user_agent=entry.user_agent,
            status=entry.status,
            error_message=entry.error_message,
        )
        if audit.get("prev_hash") != prev_hash or not hmac.compare_digest(entry.entry_hash or "", expected):
            return {"valid": False, "checked": checked, "legacy_entries": legacy, "first_broken_id": str(entry.id)}
        checked += 1
        prev_hash = entry.entry_hash
    return {
        "valid": legacy == 0,
        "checked": checked,
        "legacy_entries": legacy,
        "first_broken_id": None,
        "complete": len(entries) <= limit,
        "error": "Legacy entries do not provide full-field integrity" if legacy else None,
    }
