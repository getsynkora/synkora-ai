"""
Webhook endpoints API - get told when something happens instead of polling.

Authentication: ``Authorization: Bearer <agent api key>`` with the ``webhooks:manage`` permission.
Endpoints are registered on the key's own tenant. If that tenant manages customer tenants, it also
receives their events, with ``tenant_id`` and ``tenant_external_ref`` in each payload.

Events: ``usage.threshold`` (a message pool reached 80% or 100%), ``subscription.updated``.
Each delivery is signed: ``X-Synkora-Signature: t=<seconds>,v1=<hex HMAC-SHA256 of "<t>.<body>">``,
using the secret returned when the endpoint was created.
"""

import asyncio
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.agent_api_auth import require_permission
from src.models.agent_api_key import AgentApiKey
from src.models.webhook_endpoint import WebhookEndpoint
from src.services.activity.api_audit import audit_api_action
from src.services.agents.security import encrypt_value
from src.services.outbound_webhooks import (
    DESTINATION_REFUSED,
    EVENT_PING,
    MAX_ENDPOINTS_PER_TENANT,
    SUBSCRIBABLE_EVENTS,
    build_event,
    deliver_to,
    destination_error,
    new_secret,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public/webhooks", tags=["Webhooks API"])


# DNS lookups for registration run on their own small pool with a deadline, so a host name whose nameserver never
# answers cannot tie up the threads the rest of the API relies on.
_DNS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="webhook-dns")
DNS_DEADLINE_SECONDS = 5
TEST_COOLDOWN_SECONDS = 60


REACTIVATE_COOLDOWN_SECONDS = 3600
# One registration lookup at a time per tenant, so one tenant cannot occupy the whole lookup pool
_tenant_dns_slots: dict[uuid.UUID, asyncio.Semaphore] = {}


async def _check_destination(url: str, tenant_id: uuid.UUID) -> str | None:
    slot = _tenant_dns_slots.setdefault(tenant_id, asyncio.Semaphore(1))
    if slot.locked():
        return "Another address check for this account is still running; try again shortly"
    async with slot:
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(_DNS_EXECUTOR, destination_error, url), timeout=DNS_DEADLINE_SECONDS
            )
        except TimeoutError:
            return DESTINATION_REFUSED


async def _claim_cooldown(db: AsyncSession, endpoint_id: uuid.UUID, column, seconds: int) -> bool:
    """
    Atomically take a cooldown slot: one conditional UPDATE, so two concurrent requests cannot both pass.
    Returns False while the cooldown is still running.
    """
    now = datetime.now(UTC)
    claimed = await db.execute(
        update(WebhookEndpoint)
        .where(
            WebhookEndpoint.id == endpoint_id,
            or_(column.is_(None), column < now - timedelta(seconds=seconds)),
        )
        .values({column.key: now})
        .returning(WebhookEndpoint.id)
    )
    if claimed.first() is None:
        await db.rollback()
        return False
    await db.commit()
    return True


class CreateWebhookRequest(BaseModel):
    url: str = Field(..., max_length=2048, description="HTTPS URL that will receive events")
    events: list[str] = Field(default_factory=list, description="Event types to receive. Empty means all")
    description: str | None = Field(None, max_length=255)


class WebhookInfo(BaseModel):
    id: str
    url: str
    description: str | None
    events: list[str]
    is_active: bool
    created_at: datetime


class CreatedWebhook(WebhookInfo):
    secret: str = Field(..., description="Signing secret. Shown once; store it now")


def _info(endpoint: WebhookEndpoint) -> WebhookInfo:
    return WebhookInfo(
        id=str(endpoint.id),
        url=endpoint.url,
        description=endpoint.description,
        events=list(endpoint.events or []),
        is_active=bool(endpoint.is_active),
        created_at=endpoint.created_at,
    )


async def _own_endpoint(db: AsyncSession, api_key: AgentApiKey, webhook_id: uuid.UUID) -> WebhookEndpoint:
    endpoint = await db.scalar(
        select(WebhookEndpoint).where(WebhookEndpoint.id == webhook_id, WebhookEndpoint.tenant_id == api_key.tenant_id)
    )
    if endpoint is None:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return endpoint


@router.post("", response_model=CreatedWebhook, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: CreateWebhookRequest,
    request: Request,
    api_key: AgentApiKey = Depends(require_permission("webhooks:manage")),
    db: AsyncSession = Depends(get_async_db),
):
    """Register an endpoint. Requires permission: webhooks:manage"""
    unknown = sorted(set(body.events) - SUBSCRIBABLE_EVENTS)
    if unknown:
        raise HTTPException(
            status_code=400, detail=f"Unknown events {unknown}. Choose from {sorted(SUBSCRIBABLE_EVENTS)}"
        )
    # The cheap check first, so a tenant at its limit cannot trigger DNS lookups at all
    existing = await db.scalar(
        select(func.count(WebhookEndpoint.id)).where(WebhookEndpoint.tenant_id == api_key.tenant_id)
    )
    if (existing or 0) >= MAX_ENDPOINTS_PER_TENANT:
        raise HTTPException(status_code=409, detail=f"At most {MAX_ENDPOINTS_PER_TENANT} webhook endpoints")

    problem = await _check_destination(body.url, api_key.tenant_id)
    if problem:
        raise HTTPException(status_code=400, detail=f"This URL cannot be used: {problem}")

    secret = new_secret()
    endpoint = WebhookEndpoint(
        tenant_id=api_key.tenant_id,
        url=body.url,
        description=body.description,
        secret=encrypt_value(secret),
        events=sorted(set(body.events)),
        is_active=True,
        consecutive_failures=0,
    )
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)
    audit_api_action(api_key, request, "webhook.created", "webhook_endpoint", endpoint.id, {"events": endpoint.events})
    return CreatedWebhook(**_info(endpoint).model_dump(), secret=secret)


@router.get("", response_model=list[WebhookInfo])
async def list_webhooks(
    api_key: AgentApiKey = Depends(require_permission("webhooks:manage")),
    db: AsyncSession = Depends(get_async_db),
):
    """Your endpoints (never their secrets). Requires permission: webhooks:manage"""
    result = await db.execute(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.tenant_id == api_key.tenant_id)
        .order_by(WebhookEndpoint.created_at.desc())
    )
    return [_info(e) for e in result.scalars().all()]


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: uuid.UUID,
    request: Request,
    api_key: AgentApiKey = Depends(require_permission("webhooks:manage")),
    db: AsyncSession = Depends(get_async_db),
):
    """Remove an endpoint. Requires permission: webhooks:manage"""
    endpoint = await _own_endpoint(db, api_key, webhook_id)
    await db.delete(endpoint)
    await db.commit()
    audit_api_action(api_key, request, "webhook.deleted", "webhook_endpoint", webhook_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{webhook_id}/reactivate", response_model=WebhookInfo)
async def reactivate_webhook(
    webhook_id: uuid.UUID,
    request: Request,
    api_key: AgentApiKey = Depends(require_permission("webhooks:manage")),
    db: AsyncSession = Depends(get_async_db),
):
    """Switch an endpoint back on after it was disabled for repeated failures. Requires permission: webhooks:manage"""
    endpoint = await _own_endpoint(db, api_key, webhook_id)
    if not await _claim_cooldown(db, endpoint.id, WebhookEndpoint.last_reactivated_at, REACTIVATE_COOLDOWN_SECONDS):
        raise HTTPException(status_code=429, detail="An endpoint can be switched back on once an hour")
    endpoint.is_active = True
    endpoint.consecutive_failures = 0
    await db.commit()
    audit_api_action(api_key, request, "webhook.reactivated", "webhook_endpoint", webhook_id)
    await db.refresh(endpoint)
    return _info(endpoint)


@router.post("/{webhook_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def test_webhook(
    webhook_id: uuid.UUID,
    api_key: AgentApiKey = Depends(require_permission("webhooks:manage")),
    db: AsyncSession = Depends(get_async_db),
):
    """Send a ``ping`` event to the endpoint. Requires permission: webhooks:manage"""
    endpoint = await _own_endpoint(db, api_key, webhook_id)
    if not endpoint.is_active:
        raise HTTPException(
            status_code=409, detail="This endpoint is switched off after repeated failures. Reactivate it first"
        )
    if not await _claim_cooldown(db, endpoint.id, WebhookEndpoint.last_tested_at, TEST_COOLDOWN_SECONDS):
        raise HTTPException(
            status_code=429, detail=f"An endpoint can be tested once every {TEST_COOLDOWN_SECONDS} seconds"
        )
    event = build_event(EVENT_PING, None, {"message": "Webhook endpoint is working"})
    deliver_to(endpoint.id, event)
    return {"queued": True, "event_id": event["id"]}
