"""
Outbound webhooks - tell a tenant (and the tenant that manages it) when something happens.

Events:
- ``usage.threshold``: a message pool reached 80% or 100% of its allowance
- ``subscription.updated``: a subscription's plan, status or period changed
- ``ping``: sent by the "test" action to check an endpoint

Every delivery is a JSON POST signed with the endpoint's secret::

    X-Synkora-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<body>">

Events for a tenant also go to the endpoints of the tenant that manages it, with the customer's
``tenant_id`` and ``tenant_external_ref`` in the payload, so one endpoint hears about every customer.
"""

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tenant import Tenant
from src.models.webhook_endpoint import WebhookEndpoint
from src.services.security.url_validator import validate_url

logger = logging.getLogger(__name__)

EVENT_USAGE_THRESHOLD = "usage.threshold"
EVENT_SUBSCRIPTION_UPDATED = "subscription.updated"
EVENT_PING = "ping"
SUBSCRIBABLE_EVENTS = frozenset({EVENT_USAGE_THRESHOLD, EVENT_SUBSCRIPTION_UPDATED})

USAGE_THRESHOLDS = (80, 100)
MAX_ENDPOINTS_PER_TENANT = 10
MAX_CONSECUTIVE_FAILURES = 10


def new_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(32)}"


def sign_payload(secret: str, timestamp: int, body: str) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()


def destination_error(url: str) -> str | None:
    """Why this URL may not receive webhooks, or None. HTTPS only; private and internal addresses are refused."""
    ok, error = validate_url(url, allowed_schemes=["https"], block_private_ips=True, resolve_dns=True)
    return None if ok else (error or "URL is not allowed")


def build_event(event_type: str, tenant: Tenant | None, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "created_at": datetime.now(UTC).isoformat(),
        "tenant_id": str(tenant.id) if tenant else None,
        "tenant_external_ref": tenant.external_ref if tenant else None,
        "data": data,
    }


def deliver_to(endpoint_id: uuid.UUID, event: dict[str, Any]) -> None:
    """Queue one delivery. Imported lazily so importing this module does not start Celery."""
    from src.tasks.webhook_tasks import deliver_webhook_event

    deliver_webhook_event.delay(str(endpoint_id), event["id"], event["type"], event)


async def emit_event(db: AsyncSession, tenant_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> int:
    """
    Queue ``event_type`` for the tenant's own endpoints and its manager's. Returns how many were queued.

    Never raises: telling someone about an event must not break the action that caused it.
    """
    try:
        tenant = await db.get(Tenant, tenant_id)
        owner_ids = [tenant_id]
        if tenant is not None and tenant.managed_by_tenant_id:
            owner_ids.append(tenant.managed_by_tenant_id)

        result = await db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.tenant_id.in_(owner_ids),
                WebhookEndpoint.is_active.is_(True),
                or_(WebhookEndpoint.events == [], WebhookEndpoint.events.any(event_type)),
            )
        )
        endpoints = result.scalars().all()
        if not endpoints:
            return 0
        event = build_event(event_type, tenant, data)
        for endpoint in endpoints:
            deliver_to(endpoint.id, event)
        return len(endpoints)
    except Exception:
        logger.warning("Could not queue webhook event %s for tenant %s", event_type, tenant_id, exc_info=True)
        return 0


def subscription_event_data(subscription: Any, plan_name: str | None) -> dict[str, Any]:
    """The facts a receiver needs about a subscription change."""
    status = getattr(subscription.status, "value", subscription.status)
    return {
        "plan": plan_name,
        "status": status,
        "current_period_start": subscription.current_period_start.isoformat()
        if subscription.current_period_start
        else None,
        "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        "cancel_at_period_end": bool(subscription.cancel_at_period_end),
    }
