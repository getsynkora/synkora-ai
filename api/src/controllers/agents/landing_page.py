"""Agent landing page endpoints — manage and serve agent public profiles."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.controllers.agents.index import convert_s3_uri_to_presigned_url
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.services.agents.agent_public_profile_service import AgentPublicProfileService
from src.services.billing.agent_user_subscription_service import AgentUserSubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter()  # Auth-required: prefix /api/v1/agents
public_router = APIRouter()  # Public: no prefix
webhook_router = APIRouter()  # Stripe webhooks: no prefix


# --- Schemas ---


class PublicProfileUpsertRequest(BaseModel):
    slug: str | None = None
    tagline: str | None = None
    long_description: str | None = None
    hero_image_url: str | None = None
    preview_video_url: str | None = None
    gallery_images: list | None = None
    example_conversations: list | None = None
    creator_bio: str | None = None
    creator_display_name: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    og_image_url: str | None = None
    cta_label: str | None = None
    accent_color: str | None = None


class SubscribeRequest(BaseModel):
    pricing_id: UUID
    tier: str  # SESSION|DAILY|WEEKLY|MONTHLY
    discount_code: str | None = None


class GuestEmailSubscribeRequest(BaseModel):
    email: str


class CheckoutRequest(BaseModel):
    pricing_id: UUID
    tier: str
    guest_email: str
    success_url: str
    cancel_url: str


# --- Auth-required endpoints ---


@router.get("/{agent_slug}/public-profile")
async def get_agent_public_profile(
    agent_slug: str,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get the public profile for an agent (owner view)."""
    from sqlalchemy import select as sa_select

    from src.models.agent_public_profile import AgentPublicProfile

    result = await db.execute(sa_select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    r = await db.execute(sa_select(AgentPublicProfile).where(AgentPublicProfile.agent_id == agent.id))
    profile = r.scalar_one_or_none()
    if profile is None:
        return {"profile": None}
    return {"profile": profile.__dict__}


@router.put("/{agent_slug}/public-profile")
async def upsert_agent_public_profile(
    agent_slug: str,
    body: PublicProfileUpsertRequest,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Create or update the public landing page profile for an agent."""
    from sqlalchemy import select

    result = await db.execute(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    try:
        profile = await AgentPublicProfileService.upsert_profile(
            agent_id=agent.id,
            tenant_id=tenant_id,
            data=body.model_dump(exclude_none=True),
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"profile": profile.__dict__}


@router.post("/{agent_slug}/public-profile/publish")
async def publish_agent_public_profile(
    agent_slug: str,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Publish the agent landing page."""
    from sqlalchemy import select

    result = await db.execute(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    try:
        profile = await AgentPublicProfileService.publish_profile(agent.id, tenant_id, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"published": True, "slug": profile.slug}


# --- Public endpoints ---


@public_router.get("/api/public/agents/{slug}")
async def get_public_agent_landing(slug: str, db: AsyncSession = Depends(get_async_db)):
    """Get full public landing page data for an agent by slug.

    Falls back to default (free) landing page data when no published profile
    exists but a public agent with a matching slugified name is found.
    """
    from sqlalchemy import select as sa_select

    from src.models.agent_pricing import AgentPricing

    data = await AgentPublicProfileService.get_public_profile_full(slug, db)

    if data is not None:
        profile = data["profile"]
        agent = data["agent"]
        pricing = data["pricing"]
        creator = data["creator"]

        return {
            "slug": profile.slug,
            "tagline": profile.tagline,
            "long_description": profile.long_description,
            "hero_image_url": profile.hero_image_url,
            "preview_video_url": profile.preview_video_url,
            "gallery_images": profile.gallery_images,
            "example_conversations": profile.example_conversations,
            "creator_bio": profile.creator_bio,
            "creator_display_name": profile.creator_display_name,
            "seo_title": profile.seo_title,
            "seo_description": profile.seo_description,
            "og_image_url": profile.og_image_url,
            "cta_label": profile.cta_label or "Try it free",
            "accent_color": profile.accent_color,
            "view_count": profile.view_count,
            "agent_name": agent.agent_name if agent else None,
            "agent_avatar": convert_s3_uri_to_presigned_url(agent.avatar) if agent and agent.avatar else None,
            "allow_subscriptions": agent.allow_subscriptions if agent else False,
            "description": agent.description if agent else None,
            "pricing": {
                "id": str(pricing.id),
                "pricing_model": pricing.pricing_model,
                "session_credits": pricing.session_credits,
                "daily_credits": pricing.daily_credits,
                "weekly_credits": pricing.weekly_credits,
                "monthly_credits": pricing.monthly_subscription_credits,
                "trial_messages": pricing.trial_messages or 0,
            }
            if pricing
            else None,
            "creator": {
                "username": creator.username,
                "display_name": creator.display_name,
                "bio": creator.bio,
                "avatar_url": creator.avatar_url,
                "website_url": creator.website_url,
                "twitter_url": creator.twitter_url,
                "linkedin_url": creator.linkedin_url,
                "github_url": creator.github_url,
            }
            if creator
            else None,
        }

    # ── Fallback: no published profile — find agent by slug field ──
    result = await db.execute(
        sa_select(Agent).where(
            Agent.is_public.is_(True),
            Agent.slug == slug,
        )
    )
    agent = result.scalar_one_or_none()

    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Load pricing (use it if free, else treat as free for default page)
    pricing_result = await db.execute(sa_select(AgentPricing).where(AgentPricing.agent_id == agent.id))
    pricing = pricing_result.scalar_one_or_none()

    return {
        "slug": slug,
        "tagline": None,
        "long_description": agent.description,
        "hero_image_url": convert_s3_uri_to_presigned_url(agent.avatar) if agent.avatar else None,
        "preview_video_url": None,
        "gallery_images": [],
        "example_conversations": [],
        "creator_bio": None,
        "creator_display_name": None,
        "seo_title": agent.agent_name,
        "seo_description": agent.description,
        "og_image_url": convert_s3_uri_to_presigned_url(agent.avatar) if agent.avatar else None,
        "cta_label": "Try it free",
        "accent_color": None,
        "view_count": 0,
        "agent_name": agent.agent_name,
        "agent_avatar": convert_s3_uri_to_presigned_url(agent.avatar) if agent.avatar else None,
        "allow_subscriptions": agent.allow_subscriptions,
        "description": agent.description,
        "pricing": {
            "id": str(pricing.id),
            "pricing_model": pricing.pricing_model,
            "session_credits": pricing.session_credits,
            "daily_credits": pricing.daily_credits,
            "weekly_credits": pricing.weekly_credits,
            "monthly_credits": pricing.monthly_subscription_credits,
            "trial_messages": pricing.trial_messages or 0,
        }
        if pricing and pricing.pricing_model != "FREE"
        else None,
        "creator": None,
    }


@public_router.post("/api/public/agents/{slug}/email-subscribe")
async def email_subscribe_to_agent(
    slug: str,
    body: GuestEmailSubscribeRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Free email subscription to agent outputs — no payment required."""
    from sqlalchemy import select as sa_select

    from src.models.agent_public_profile import AgentPublicProfile
    from src.models.agent_subscription import AgentSubscription

    r = await db.execute(sa_select(AgentPublicProfile).where(AgentPublicProfile.slug == slug))
    profile = r.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    agent_result = await db.execute(sa_select(Agent).where(Agent.id == profile.agent_id))
    agent = agent_result.scalar_one_or_none()
    if agent is None or not agent.allow_subscriptions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Subscriptions are disabled for this agent")

    result = await db.execute(
        sa_select(AgentSubscription).where(
            AgentSubscription.agent_id == profile.agent_id,
            AgentSubscription.email == body.email,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.is_active:
            return {"message": "Already subscribed"}
        existing.is_active = True
        await db.commit()
        return {"message": "Subscription reactivated"}

    sub = AgentSubscription(agent_id=profile.agent_id, email=body.email)
    db.add(sub)
    await db.commit()
    logger.info(f"Email subscription: {body.email} -> slug {slug}")
    return {"message": "Subscribed successfully"}


@public_router.post("/api/public/agents/{slug}/view")
async def record_agent_view(slug: str, db: AsyncSession = Depends(get_async_db)):
    """Increment view count for an agent landing page."""
    await AgentPublicProfileService.increment_view_count(slug, db)
    return {"ok": True}


@public_router.post("/api/public/agents/{slug}/subscribe")
async def subscribe_to_agent(
    slug: str,
    body: SubscribeRequest,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Subscribe an authenticated user to an agent using credits."""
    from sqlalchemy import select

    from src.models.agent_public_profile import AgentPublicProfile

    r = await db.execute(select(AgentPublicProfile).where(AgentPublicProfile.slug == slug))
    profile = r.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    try:
        sub = await AgentUserSubscriptionService.subscribe_account_user(
            agent_id=profile.agent_id,
            pricing_id=body.pricing_id,
            subscriber_tenant_id=tenant_id,
            tier=body.tier,
            db=db,
            discount_code=body.discount_code,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"subscription_id": str(sub.id), "status": sub.status, "expires_at": sub.expires_at}


@public_router.post("/api/public/agents/{slug}/checkout")
async def create_guest_checkout(
    slug: str,
    body: CheckoutRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Create a Stripe Checkout session for guest subscription."""
    from sqlalchemy import select

    from src.models.agent_public_profile import AgentPublicProfile

    r = await db.execute(select(AgentPublicProfile).where(AgentPublicProfile.slug == slug))
    profile = r.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    try:
        checkout_url = await AgentUserSubscriptionService.create_stripe_checkout_session(
            agent_id=profile.agent_id,
            pricing_id=body.pricing_id,
            tier=body.tier,
            guest_email=body.guest_email,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured or unavailable",
        )

    return {"checkout_url": checkout_url}


@webhook_router.post("/api/webhooks/stripe/agent-subscriptions")
async def stripe_agent_subscription_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Handle Stripe webhooks for agent subscription fulfillment."""
    import json

    import stripe

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    from src.config.settings import settings

    webhook_secret = getattr(settings, "stripe_webhook_secret_agent_subs", None)

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = json.loads(payload)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        meta = session.get("metadata", {})
        if meta.get("agent_id"):  # Only handle agent subscription sessions
            try:
                raw_token, guest_email = await AgentUserSubscriptionService.fulfill_guest_subscription(
                    session["id"], db
                )
                # TODO: Send email with token to guest_email
                logger.info(f"Fulfilled guest subscription for {guest_email}")
            except Exception as e:
                logger.error(f"Failed to fulfill subscription: {e}")

    return {"received": True}
