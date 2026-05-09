"""Creator profile endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.services.agents.creator_profile_service import CreatorProfileService

logger = logging.getLogger(__name__)

router = APIRouter()  # Auth-required
public_router = APIRouter()  # Public


class CreatorProfileUpdateRequest(BaseModel):
    username: str | None = None
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    banner_image_url: str | None = None
    website_url: str | None = None
    twitter_url: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    is_public: bool | None = None


class StripeOnboardRequest(BaseModel):
    refresh_url: str
    return_url: str


@router.get("/api/v1/creator-profile")
async def get_my_creator_profile(
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get the current tenant's creator profile."""
    profile = await CreatorProfileService.get_by_tenant_id(tenant_id, db)
    if profile is None:
        return {"profile": None}
    return {"profile": profile.__dict__}


@router.put("/api/v1/creator-profile")
async def upsert_my_creator_profile(
    body: CreatorProfileUpdateRequest,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Create or update the current tenant's creator profile."""
    try:
        profile = await CreatorProfileService.upsert_profile(
            tenant_id=tenant_id,
            data=body.model_dump(exclude_none=True),
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"profile": profile.__dict__}


@router.post("/api/v1/creator-profile/stripe-onboard")
async def initiate_stripe_onboarding(
    body: StripeOnboardRequest,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Start Stripe Connect onboarding. Returns redirect URL."""
    import stripe

    profile = await CreatorProfileService.get_by_tenant_id(tenant_id, db)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Create a creator profile first")

    import asyncio

    if not profile.stripe_account_id:
        account_obj = await asyncio.to_thread(stripe.Account.create, type="express")
        profile.stripe_account_id = account_obj["id"]
        await db.commit()

    account_link = await asyncio.to_thread(
        stripe.AccountLink.create,
        account=profile.stripe_account_id,
        refresh_url=body.refresh_url,
        return_url=body.return_url,
        type="account_onboarding",
    )
    return {"onboarding_url": account_link["url"]}


@router.get("/api/v1/creator-profile/earnings")
async def get_creator_earnings(
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get creator earnings summary."""
    from src.services.billing.agent_pricing_service import AgentPricingService

    earnings = await AgentPricingService.get_creator_earnings(tenant_id, db=db)
    return {"earnings": earnings}


@router.get("/api/v1/creator-profile/payouts")
async def get_creator_payouts(
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get creator payout history."""
    from sqlalchemy import select

    from src.models.agent_revenue import AgentRevenue, RevenueStatus

    result = await db.execute(
        select(AgentRevenue)
        .where(
            AgentRevenue.tenant_id == tenant_id,
            AgentRevenue.status == RevenueStatus.PAID,
        )
        .order_by(AgentRevenue.created_at.desc())
        .limit(100)
    )
    records = result.scalars().all()
    return {"payouts": [r.__dict__ for r in records]}


@public_router.get("/creators/{username}")
async def get_creator_public_page(username: str, db: AsyncSession = Depends(get_async_db)):
    """Get a creator's public profile page data."""
    data = await CreatorProfileService.get_public_creator_data(username, db)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator not found")

    creator = data["creator"]
    profiles = data["published_profiles"]
    agents = data["agents"]

    return {
        "username": creator.username,
        "display_name": creator.display_name,
        "bio": creator.bio,
        "avatar_url": creator.avatar_url,
        "banner_image_url": creator.banner_image_url,
        "website_url": creator.website_url,
        "twitter_url": creator.twitter_url,
        "linkedin_url": creator.linkedin_url,
        "github_url": creator.github_url,
        "total_earnings_credits": creator.total_earnings_credits,
        "agents": [
            {
                "slug": p.slug,
                "tagline": p.tagline,
                "hero_image_url": p.hero_image_url,
                "cta_label": p.cta_label,
                "agent_name": agents[p.agent_id].agent_name if p.agent_id in agents else None,
            }
            for p in profiles
        ],
    }
