"""Webhook management endpoints for agents."""

import json
import logging
import secrets
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.redis import get_redis_async
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.agent_webhook import AgentWebhook, AgentWebhookEvent
from src.services.agents.security import encrypt_value
from src.services.webhooks.webhook_processor import WebhookProcessor

logger = logging.getLogger(__name__)
router = APIRouter()
public_router = APIRouter()  # Public routes without authentication


# SECURITY: Redis-backed distributed rate limiter for webhooks.
# Counters are shared across all pods, so limits are enforced globally.
class WebhookRateLimiter:
    """Redis-backed rate limiter for webhook endpoints to prevent DoS attacks."""

    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

    async def _incr_with_ttl(self, redis, key: str, ttl: int) -> int:
        """Atomic increment; TTL is set only when the key is created for the first time."""
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, ttl)
        return count

    async def is_rate_limited(self, key: str) -> tuple[bool, str]:
        """
        Check if a webhook token is rate limited.

        Args:
            key: The webhook token or IP address

        Returns:
            Tuple of (is_limited, reason)
        """
        try:
            redis = get_redis_async()
            min_count = int(await redis.get(f"wh_rl_min:{key}") or 0)
            if min_count >= self.requests_per_minute:
                return True, f"Rate limit exceeded: {self.requests_per_minute} requests per minute"
            hr_count = int(await redis.get(f"wh_rl_hr:{key}") or 0)
            if hr_count >= self.requests_per_hour:
                return True, f"Rate limit exceeded: {self.requests_per_hour} requests per hour"
            return False, ""
        except Exception:
            logger.warning("Redis unavailable for webhook rate limit check — failing open")
            return False, ""

    async def record_request(self, key: str) -> None:
        """Record a request for rate limiting."""
        try:
            redis = get_redis_async()
            await self._incr_with_ttl(redis, f"wh_rl_min:{key}", 60)
            await self._incr_with_ttl(redis, f"wh_rl_hr:{key}", 3600)
        except Exception:
            logger.warning("Redis unavailable — webhook rate limit counter not incremented")


# Global rate limiter instance
webhook_rate_limiter = WebhookRateLimiter()


# Schemas
class WebhookCreate(BaseModel):
    name: str = Field(..., description="Webhook name")
    provider: str = Field(..., description="Provider: github, clickup, jira, slack, custom")
    event_types: list[str] | None = Field(None, description="Event types to process")
    config: dict | None = Field(None, description="Additional configuration")
    retry_config: dict | None = Field(None, description="Retry configuration")


class WebhookUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    event_types: list[str] | None = None
    config: dict | None = None
    retry_config: dict | None = None


class WebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    name: str
    provider: str
    webhook_url: str
    is_active: bool
    event_types: list[str] | None
    config: dict | None
    success_count: int
    failure_count: int
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WebhookEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    webhook_id: UUID
    event_id: str | None
    event_type: str
    status: str
    parsed_data: dict | None
    error_message: str | None
    retry_count: int
    agent_execution_id: str | None
    created_at: datetime


# Endpoints
@router.post("/{agent_slug}/webhooks", response_model=WebhookResponse)
async def create_webhook(
    agent_slug: str,
    webhook_data: WebhookCreate,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Create a new webhook for an agent."""
    # Get agent
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Generate unique webhook URL
    webhook_token = secrets.token_urlsafe(32)
    webhook_url = f"/api/webhooks/{webhook_token}"

    # Generate and encrypt secret (always — user may want to enable verification later)
    plain_secret = secrets.token_urlsafe(32)
    encrypted_secret = encrypt_value(plain_secret)

    # Providers that natively support HMAC signatures have verification on by default.
    # Sentry and custom don't send signatures by default, so verification is off by default
    # but can be enabled by the user via the verify_signature config flag.
    PROVIDERS_WITH_SIGNATURES = {"github", "gitlab", "clickup", "jira", "slack"}
    config = dict(webhook_data.config or {})
    if "verify_signature" not in config:
        config["verify_signature"] = webhook_data.provider in PROVIDERS_WITH_SIGNATURES

    # Create webhook
    webhook = AgentWebhook(
        agent_id=agent.id,
        name=webhook_data.name,
        provider=webhook_data.provider,
        webhook_url=webhook_url,
        secret=encrypted_secret,
        event_types=webhook_data.event_types,
        config=config,
        retry_config=webhook_data.retry_config or {"max_retries": 3, "retry_delay": 60},
    )

    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    logger.info(f"Created webhook {webhook.id} for agent {agent.slug}")

    # Return response with plain secret (one-time only)
    response = WebhookResponse.model_validate(webhook)
    response.config = response.config or {}
    response.config["secret"] = plain_secret

    return response


@router.get("/{agent_slug}/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(
    agent_slug: str,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """List all webhooks for an agent."""
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    result = await db.execute(select(AgentWebhook).filter(AgentWebhook.agent_id == agent.id))
    webhooks = result.scalars().all()

    return [WebhookResponse.model_validate(w) for w in webhooks]


@router.get("/{agent_slug}/webhooks/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    agent_slug: str,
    webhook_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Get webhook details."""
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    result = await db.execute(
        select(AgentWebhook).filter(AgentWebhook.id == webhook_id, AgentWebhook.agent_id == agent.id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    return WebhookResponse.model_validate(webhook)


@router.patch("/{agent_slug}/webhooks/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    agent_slug: str,
    webhook_id: UUID,
    webhook_data: WebhookUpdate,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Update webhook configuration."""
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    result = await db.execute(
        select(AgentWebhook).filter(AgentWebhook.id == webhook_id, AgentWebhook.agent_id == agent.id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    # Update fields
    update_data = webhook_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(webhook, field, value)

    await db.commit()
    await db.refresh(webhook)

    logger.info(f"Updated webhook {webhook.id}")

    return WebhookResponse.model_validate(webhook)


@router.delete("/{agent_slug}/webhooks/{webhook_id}")
async def delete_webhook(
    agent_slug: str,
    webhook_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Delete a webhook."""
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    result = await db.execute(
        select(AgentWebhook).filter(AgentWebhook.id == webhook_id, AgentWebhook.agent_id == agent.id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    await db.delete(webhook)
    await db.commit()

    logger.info(f"Deleted webhook {webhook_id}")

    return {"message": "Webhook deleted"}


@public_router.post("/api/webhooks/{webhook_token}")
async def receive_webhook(webhook_token: str, request: Request, db: AsyncSession = Depends(get_async_db)):
    """Receive and process webhook event (public endpoint - no auth required)."""
    # SECURITY: Rate limit by webhook token to prevent DoS
    is_limited, limit_reason = await webhook_rate_limiter.is_rate_limited(webhook_token)
    if is_limited:
        logger.warning(f"Rate limit exceeded for webhook (token length: {len(webhook_token)})")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=limit_reason)

    # Record the request for rate limiting
    await webhook_rate_limiter.record_request(webhook_token)

    # Find webhook by URL token
    webhook_url = f"/api/webhooks/{webhook_token}"
    result = await db.execute(select(AgentWebhook).filter(AgentWebhook.webhook_url == webhook_url))
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    # Get request data
    payload = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    logger.info(f"Received webhook: {len(payload)} bytes, content-type: {headers.get('content-type')}")

    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty request body")

    try:
        content_type = headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type:
            # GitHub (and others) can send payload as form-encoded: payload=<url-encoded-json>
            from urllib.parse import parse_qs

            parsed = parse_qs(payload.decode("utf-8"))
            raw_json = parsed.get("payload", [None])[0]
            if raw_json is None:
                raise json.JSONDecodeError("Missing 'payload' field in form data", "", 0)
            payload_dict = json.loads(raw_json)
        else:
            payload_dict = json.loads(payload)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON: {e}, body: {payload[:200]}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON: {str(e)}")

    # Process webhook
    processor = WebhookProcessor(db)
    result = await processor.process_webhook(
        webhook=webhook, payload=payload, payload_dict=payload_dict, headers=headers
    )

    return result


@router.get("/{agent_slug}/webhooks/{webhook_id}/events", response_model=list[WebhookEventResponse])
async def list_webhook_events(
    agent_slug: str,
    webhook_id: UUID,
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """List webhook events."""
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    result = await db.execute(
        select(AgentWebhook).filter(AgentWebhook.id == webhook_id, AgentWebhook.agent_id == agent.id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    query = select(AgentWebhookEvent).filter(AgentWebhookEvent.webhook_id == webhook_id)

    if status_filter:
        query = query.filter(AgentWebhookEvent.status == status_filter)

    query = query.order_by(AgentWebhookEvent.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    events = result.scalars().all()

    return [WebhookEventResponse.model_validate(e) for e in events]


@router.delete("/{agent_slug}/webhooks/{webhook_id}/events/{event_id}")
async def delete_webhook_event(
    agent_slug: str,
    webhook_id: UUID,
    event_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Delete a single webhook event record."""
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    result = await db.execute(
        select(AgentWebhook).filter(AgentWebhook.id == webhook_id, AgentWebhook.agent_id == agent.id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    result = await db.execute(
        select(AgentWebhookEvent).filter(AgentWebhookEvent.id == event_id, AgentWebhookEvent.webhook_id == webhook_id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    await db.delete(event)
    await db.commit()

    logger.info(f"Deleted webhook event {event_id}")
    return {"message": "Event deleted"}


@router.get("/{agent_slug}/webhooks/{webhook_id}/stats")
async def get_webhook_stats(
    agent_slug: str,
    webhook_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Get webhook statistics."""
    result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    result = await db.execute(
        select(AgentWebhook).filter(AgentWebhook.id == webhook_id, AgentWebhook.agent_id == agent.id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    # Get event counts by status
    from sqlalchemy import func

    result = await db.execute(
        select(AgentWebhookEvent.status, func.count(AgentWebhookEvent.id))
        .filter(AgentWebhookEvent.webhook_id == webhook_id)
        .group_by(AgentWebhookEvent.status)
    )
    status_counts = result.all()

    return {
        "webhook_id": webhook.id,
        "success_count": webhook.success_count,
        "failure_count": webhook.failure_count,
        "last_triggered_at": webhook.last_triggered_at,
        "event_status_counts": dict(status_counts),
    }
