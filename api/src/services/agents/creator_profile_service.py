"""CreatorProfile service — manage creator/developer public profiles."""

import logging
import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.agent_public_profile import AgentPublicProfile
from src.models.creator_profile import CreatorProfile

logger = logging.getLogger(__name__)


class CreatorProfileService:
    """Service for managing creator profiles."""

    @staticmethod
    def _to_username(text: str) -> str:
        """Convert text to valid username (alphanumeric + underscores, max 50 chars)."""
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9_]", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text[:45] or "creator"

    @staticmethod
    async def generate_username(base: str, db: AsyncSession, exclude_id: UUID | None = None) -> str:
        """Generate unique username, deduplicating with _2, _3, etc."""
        base_uname = CreatorProfileService._to_username(base)
        candidate = base_uname
        counter = 2
        while True:
            stmt = select(CreatorProfile).where(CreatorProfile.username == candidate)
            if exclude_id:
                stmt = stmt.where(CreatorProfile.id != exclude_id)
            result = await db.execute(stmt)
            if result.scalar_one_or_none() is None:
                return candidate
            candidate = f"{base_uname}_{counter}"
            counter += 1

    @staticmethod
    async def get_by_username(username: str, db: AsyncSession) -> CreatorProfile | None:
        result = await db.execute(select(CreatorProfile).where(CreatorProfile.username == username))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_tenant_id(tenant_id: UUID, db: AsyncSession) -> CreatorProfile | None:
        result = await db.execute(select(CreatorProfile).where(CreatorProfile.tenant_id == tenant_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_profile(tenant_id: UUID, data: dict, db: AsyncSession) -> CreatorProfile:
        """Create or update creator profile for a tenant."""
        result = await db.execute(select(CreatorProfile).where(CreatorProfile.tenant_id == tenant_id))
        profile = result.scalar_one_or_none()

        if profile is None:
            base = data.get("username") or data.get("display_name") or str(tenant_id)[:8]
            username = await CreatorProfileService.generate_username(base, db)
            profile = CreatorProfile(tenant_id=tenant_id, username=username)
            db.add(profile)

        # Handle username update
        if "username" in data and data["username"] != profile.username:
            new_uname = CreatorProfileService._to_username(data["username"])
            existing = await CreatorProfileService.get_by_username(new_uname, db)
            if existing and existing.id != profile.id:
                raise ValueError(f"Username '{new_uname}' is already taken")
            profile.username = new_uname

        updatable = [
            "display_name",
            "bio",
            "avatar_url",
            "banner_image_url",
            "website_url",
            "twitter_url",
            "linkedin_url",
            "github_url",
            "is_public",
        ]
        for field in updatable:
            if field in data:
                setattr(profile, field, data[field])

        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def get_public_creator_data(username: str, db: AsyncSession) -> dict | None:
        """Get creator profile + published agents + stats."""
        creator = await CreatorProfileService.get_by_username(username, db)
        if creator is None or not creator.is_public:
            return None

        # Get published agent profiles for this tenant
        profiles_result = await db.execute(
            select(AgentPublicProfile).where(
                AgentPublicProfile.tenant_id == creator.tenant_id,
                AgentPublicProfile.is_published.is_(True),
            )
        )
        profiles = profiles_result.scalars().all()

        # Get agent names
        agent_ids = [p.agent_id for p in profiles]
        agents_data = {}
        if agent_ids:
            agents_result = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
            agents_data = {a.id: a for a in agents_result.scalars().all()}

        return {
            "creator": creator,
            "published_profiles": profiles,
            "agents": agents_data,
        }

    @staticmethod
    async def initiate_stripe_onboarding(tenant_id: UUID, db: AsyncSession) -> str:
        """Start Stripe Connect onboarding. Returns onboarding URL."""
        import stripe

        profile = await CreatorProfileService.get_by_tenant_id(tenant_id, db)
        if profile is None:
            raise ValueError("Creator profile not found. Create a profile first.")

        import asyncio

        # Create Stripe Connect account if not yet created
        if not profile.stripe_account_id:
            account = await asyncio.to_thread(stripe.Account.create, type="express")
            profile.stripe_account_id = account["id"]
            await db.commit()

        # Create account link (onboarding URL)
        account_link = await asyncio.to_thread(
            stripe.AccountLink.create,
            account=profile.stripe_account_id,
            refresh_url="",  # Caller provides actual URLs at controller level
            return_url="",
            type="account_onboarding",
        )
        return account_link["url"]

    @staticmethod
    async def complete_stripe_onboarding(tenant_id: UUID, stripe_account_id: str, db: AsyncSession) -> CreatorProfile:
        """Mark Stripe onboarding as complete."""
        profile = await CreatorProfileService.get_by_tenant_id(tenant_id, db)
        if profile is None:
            raise ValueError("Creator profile not found")
        profile.stripe_account_id = stripe_account_id
        profile.stripe_onboarding_complete = True
        await db.commit()
        await db.refresh(profile)
        return profile
