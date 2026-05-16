"""Agent public profile endpoints — manage landing page data for agents."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.services.agents.agent_public_profile_service import AgentPublicProfileService

logger = logging.getLogger(__name__)

router = APIRouter()  # Auth: mounted at /api/v1/agents
public_router = APIRouter()  # Public: mounted at root


class UpsertPublicProfileRequest(BaseModel):
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
    slug: str | None = None


@router.get("/{agent_slug}/public-profile")
async def get_public_profile(
    agent_slug: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
):
    """Get the public profile for an agent."""
    agent_result = await db.execute(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    from src.models.agent_public_profile import AgentPublicProfile

    profile_result = await db.execute(select(AgentPublicProfile).where(AgentPublicProfile.agent_id == agent.id))
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public profile not found")

    return {
        "id": str(profile.id),
        "agent_id": str(profile.agent_id),
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
        "cta_label": profile.cta_label,
        "accent_color": profile.accent_color,
        "is_published": profile.is_published,
    }


@router.put("/{agent_slug}/public-profile")
async def upsert_public_profile(
    agent_slug: str,
    body: UpsertPublicProfileRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
):
    """Create or update the public profile for an agent."""
    agent_result = await db.execute(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = agent_result.scalar_one_or_none()
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

    return {
        "id": str(profile.id),
        "agent_id": str(profile.agent_id),
        "slug": profile.slug,
        "tagline": profile.tagline,
        "long_description": profile.long_description,
        "cta_label": profile.cta_label,
        "accent_color": profile.accent_color,
        "seo_title": profile.seo_title,
        "seo_description": profile.seo_description,
        "is_published": profile.is_published,
    }


@router.post("/{agent_slug}/public-profile/publish")
async def publish_public_profile(
    agent_slug: str,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
):
    """Publish the public profile, making it accessible via the public endpoint."""
    agent_result = await db.execute(select(Agent).where(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    try:
        profile = await AgentPublicProfileService.publish_profile(
            agent_id=agent.id,
            tenant_id=tenant_id,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"slug": profile.slug, "is_published": profile.is_published}


@public_router.get("/api/public/agents/{slug}")
async def get_published_agent_profile(
    slug: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a published agent public profile (no auth required)."""
    await AgentPublicProfileService.increment_view_count(slug, db)
    data = await AgentPublicProfileService.get_public_profile_full(slug, db)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent profile not found")

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
        "cta_label": profile.cta_label,
        "accent_color": profile.accent_color,
        "seo_title": profile.seo_title,
        "seo_description": profile.seo_description,
        "og_image_url": profile.og_image_url,
        "agent": {
            "id": str(agent.id) if agent else None,
            "agent_name": agent.agent_name if agent else None,
            "description": agent.description if agent else None,
            "category": agent.category if agent else None,
            "tags": agent.tags if agent else [],
        }
        if agent
        else None,
        "pricing": {
            "model": pricing.pricing_model,
            "session_credits": pricing.session_credits,
            "daily_credits": pricing.daily_credits,
            "weekly_credits": pricing.weekly_credits,
            "monthly_credits": pricing.monthly_subscription_credits,
            "trial_messages": pricing.trial_messages or 0,
        }
        if pricing
        else None,
        "creator": {
            "display_name": creator.display_name if creator else None,
            "bio": creator.bio if creator else None,
        }
        if creator
        else None,
    }
