"""
Webhook endpoints API - get told when something happens instead of polling.

Authentication: ``Authorization: Bearer <agent api key>`` with the ``webhooks:manage`` permission.
Endpoints are registered on the key's own tenant. If that tenant manages customer tenants, it also
receives their events, with ``tenant_id`` and ``tenant_external_ref`` in each payload.

Events: ``usage.threshold`` (a message pool reached 80% or 100%), ``subscription.updated``.
Each delivery is signed: ``X-Synkora-Signature: t=<seconds>,v1=<hex HMAC-SHA256 of "<t>.<body>">``,
using the secret returned when the endpoint was created.
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.agent_api_auth import require_permission
from src.models.agent_api_key import AgentApiKey
from src.models.webhook_endpoint import WebhookEndpoint
from src.services.agents.security import encrypt_value
from src.services.outbound_webhooks import (
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
    api_key: AgentApiKey = Depends(require_permission("webhooks:manage")),
    db: AsyncSession = Depends(get_async_db),
):
    """Register an endpoint. Requires permission: webhooks:manage"""
    unknown = sorted(set(body.events) - SUBSCRIBABLE_EVENTS)
    if unknown:
        raise HTTPException(
            status_code=400, detail=f"Unknown events {unknown}. Choose from {sorted(SUBSCRIBABLE_EVENTS)}"
        )
    problem = destination_error(body.url)
    if problem:
        raise HTTPException(status_code=400, detail=f"This URL cannot be used: {problem}")

    existing = await db.scalar(
        select(func.count(WebhookEndpoint.id)).where(WebhookEndpoint.tenant_id == api_key.tenant_id)
    )
    if (existing or 0) >= MAX_ENDPOINTS_PER_TENANT:
        raise HTTPException(status_code=409, detail=f"At most {MAX_ENDPOINTS_PER_TENANT} webhook endpoints")

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
    api_key: AgentApiKey = Depends(require_permission("webhooks:manage")),
    db: AsyncSession = Depends(get_async_db),
):
    """Remove an endpoint. Requires permission: webhooks:manage"""
    endpoint = await _own_endpoint(db, api_key, webhook_id)
    await db.delete(endpoint)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{webhook_id}/reactivate", response_model=WebhookInfo)
async def reactivate_webhook(
    webhook_id: uuid.UUID,
    api_key: AgentApiKey = Depends(require_permission("webhooks:manage")),
    db: AsyncSession = Depends(get_async_db),
):
    """Switch an endpoint back on after it was disabled for repeated failures. Requires permission: webhooks:manage"""
    endpoint = await _own_endpoint(db, api_key, webhook_id)
    endpoint.is_active = True
    endpoint.consecutive_failures = 0
    await db.commit()
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
    event = build_event(EVENT_PING, None, {"message": "Webhook endpoint is working"})
    deliver_to(endpoint.id, event)
    return {"queued": True, "event_id": event["id"]}
