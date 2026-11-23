"""
Outbound webhooks - tell a tenant (and the tenant that manages it) when something happens.

Events:
- ``usage.threshold``: a message pool reached 80% or 100% of its allowance
- ``subscription.updated``: a subscription's plan, status or period changed
- ``ping``: sent by the "test" action to check an endpoint

Every delivery is a JSON POST signed with the endpoint's secret::

    X-Synkora-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<body>">

Receivers should recompute the HMAC over the raw body, compare it in constant time, and reject a ``t`` more than
5 minutes old so a captured delivery cannot be replayed. ``X-Synkora-Delivery`` is unique per event; ignore repeats.

Events for a tenant also go to the endpoints of the tenant that manages it, with the customer's
``tenant_id`` and ``tenant_external_ref`` in the payload, so one endpoint hears about every customer.
"""

import hashlib
import hmac
import ipaddress
import logging
import secrets
import socket
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests
import urllib3
from requests.adapters import HTTPAdapter
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tenant import Tenant
from src.models.webhook_endpoint import WebhookEndpoint

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


@dataclass(frozen=True)
class Destination:
    """A webhook URL checked and resolved once. Requests connect to ``ip``, never to a second DNS answer."""

    host: str
    port: int
    ip: str
    target: str  # path and query


ALLOWED_PORTS = frozenset({443})
DESTINATION_REFUSED = "URL must resolve to a public address"

_IPV6_GLOBAL_UNICAST = ipaddress.ip_network("2000::/3")

# Address forms that embed another address or are not real destinations (NAT64, 6to4, Teredo)
_TRANSITION_NETWORKS = tuple(
    ipaddress.ip_network(n) for n in ("64:ff9b::/96", "64:ff9b:1::/48", "2002::/16", "2001::/32")
)


def is_public_address(value: str) -> bool:
    """True only for a globally routable unicast address. IPv4-mapped IPv6 is judged as its IPv4 address."""
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return is_public_address(str(address.ipv4_mapped))
        # Only global unicast IPv6 (2000::/3). This refuses IPv4-compatible (::/96) and SIIT (::ffff:0:0/96)
        # forms, which a translator could route to an internal IPv4 address.
        if address not in _IPV6_GLOBAL_UNICAST:
            return False
        if any(address in network for network in _TRANSITION_NETWORKS):
            return False
    return address.is_global and not address.is_multicast


def resolve_destination(url: str) -> tuple[Destination | None, str | None]:
    """
    Check a webhook URL and resolve it once. Returns ``(destination, None)`` or ``(None, reason)``.

    The URL is parsed with the same parser the HTTP client uses, so what is checked is what is contacted.
    It must be https on port 443, with no user info, backslashes, spaces, control or non-ASCII characters,
    and every address the name resolves to must be public.
    """
    if not url or any(ord(c) < 33 or ord(c) > 126 or c == "\\" for c in url):
        return None, "URL contains characters that are not allowed"
    try:
        parsed = urllib3.util.parse_url(url)
    except urllib3.exceptions.LocationParseError:
        return None, "URL is not valid"
    if parsed.scheme != "https":
        return None, "Only https URLs are allowed"
    if parsed.auth:
        return None, "URLs with a user name or password are not allowed"
    if not parsed.host:
        return None, "URL has no host"
    port = parsed.port or 443
    if port not in ALLOWED_PORTS:
        return None, f"Only port {sorted(ALLOWED_PORTS)[0]} is allowed"

    host = parsed.host.strip("[]")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        return None, DESTINATION_REFUSED
    addresses = [info[4][0] for info in infos]
    if not addresses or any(not is_public_address(a) for a in addresses):
        # Same answer whether the name resolves to an internal address or not at all, so the check cannot be
        # used to discover internal host names.
        return None, DESTINATION_REFUSED
    return Destination(host=host, port=port, ip=addresses[0], target=parsed.request_uri or "/"), None


def destination_error(url: str) -> str | None:
    """Why this URL may not receive webhooks, or None."""
    return resolve_destination(url)[1]


class _PinnedAdapter(HTTPAdapter):
    """Connect to a fixed IP while the TLS name, certificate check and Host header use the original host."""

    def __init__(self, host: str):
        self._pinned_host = host
        super().__init__()

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        super().init_poolmanager(
            connections,
            maxsize,
            block=block,
            server_hostname=self._pinned_host,
            assert_hostname=self._pinned_host,
            **pool_kwargs,
        )


def post_pinned(
    destination: Destination,
    body: str,
    headers: dict[str, str],
    timeout: float | tuple[float, float],
    verify: bool | str = True,
) -> int:
    """
    POST ``body`` to the destination's already-checked IP and return the HTTP status.

    No second DNS lookup happens, redirects are not followed, environment proxies are ignored, and the
    response body is never read, so a hostile receiver cannot redirect, rebind or flood the worker.
    """
    ip = f"[{destination.ip}]" if ":" in destination.ip else destination.ip
    url = f"https://{ip}:{destination.port}{destination.target}"
    host = f"[{destination.host}]" if ":" in destination.host else destination.host
    host_header = host if destination.port == 443 else f"{host}:{destination.port}"
    session = requests.Session()
    session.trust_env = False
    session.mount("https://", _PinnedAdapter(destination.host))
    try:
        response = session.post(
            url,
            data=body,
            headers={**headers, "Host": host_header},
            timeout=timeout,
            allow_redirects=False,
            stream=True,
            verify=verify,
        )
        try:
            return response.status_code
        finally:
            response.close()
    finally:
        session.close()


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


async def has_platform_manager_key(db: AsyncSession, tenant_id: uuid.UUID) -> bool:
    from src.models.agent_api_key import AgentApiKey

    key_id = await db.scalar(
        select(AgentApiKey.id)
        .where(
            AgentApiKey.tenant_id == tenant_id,
            AgentApiKey.agent_id.is_(None),
            AgentApiKey.is_active.is_(True),
            AgentApiKey.permissions.any("tenants:manage"),
            or_(AgentApiKey.expires_at.is_(None), AgentApiKey.expires_at > datetime.now(UTC)),
        )
        .limit(1)
    )
    return key_id is not None


async def emit_event(db: AsyncSession, tenant_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> int:
    """
    Queue ``event_type`` for the tenant's own endpoints and its manager's. Returns how many were queued.

    Never raises: telling someone about an event must not break the action that caused it.
    """
    try:
        tenant = await db.get(Tenant, tenant_id)
        owner_ids = [tenant_id]
        if tenant is not None and tenant.managed_by_tenant_id:
            # Only a manager that is still allowed to manage tenants hears about its customers: one an operator
            # enabled, or one holding an active platform key with tenants:manage (revoking it stops the events)
            manager = await db.get(Tenant, tenant.managed_by_tenant_id)
            if manager is not None and (manager.can_manage_tenants or await has_platform_manager_key(db, manager.id)):
                owner_ids.append(manager.id)

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
