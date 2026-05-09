"""AgentPublicProfile service — manage agent public landing page data."""

import logging
import re
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.agent_pricing import AgentPricing
from src.models.agent_public_profile import AgentPublicProfile
from src.models.creator_profile import CreatorProfile

logger = logging.getLogger(__name__)


class AgentPublicProfileService:
    """Service for managing agent public profiles (landing pages)."""

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-friendly slug."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        text = re.sub(r"^-+|-+$", "", text)
        return text[:90]  # Leave room for dedup suffix

    @staticmethod
    async def generate_slug(base_name: str, db: AsyncSession, exclude_id: UUID | None = None) -> str:
        """Generate unique slug from base name. Deduplicates with -2, -3, etc."""
        base = AgentPublicProfileService._slugify(base_name) or "agent"
        candidate = base
        counter = 2
        while True:
            stmt = select(AgentPublicProfile).where(AgentPublicProfile.slug == candidate)
            if exclude_id:
                stmt = stmt.where(AgentPublicProfile.id != exclude_id)
            result = await db.execute(stmt)
            if result.scalar_one_or_none() is None:
                return candidate
            candidate = f"{base}-{counter}"
            counter += 1

    @staticmethod
    async def get_by_slug(slug: str, db: AsyncSession) -> AgentPublicProfile | None:
        """Get a public profile by slug (no auth required)."""
        result = await db.execute(select(AgentPublicProfile).where(AgentPublicProfile.slug == slug))
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_profile(agent_id: UUID, tenant_id: UUID, data: dict, db: AsyncSession) -> AgentPublicProfile:
        """Create or update the public profile for an agent."""
        result = await db.execute(select(AgentPublicProfile).where(AgentPublicProfile.agent_id == agent_id))
        profile = result.scalar_one_or_none()

        if profile is None:
            # Fetch agent name for slug generation
            agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = agent_result.scalar_one_or_none()
            base_name = data.get("slug") or (agent.agent_name if agent else str(agent_id))
            slug = await AgentPublicProfileService.generate_slug(base_name, db)
            profile = AgentPublicProfile(agent_id=agent_id, tenant_id=tenant_id, slug=slug)
            db.add(profile)

        # If caller provided a custom slug, validate + update it
        if "slug" in data and data["slug"] != profile.slug:
            new_slug = AgentPublicProfileService._slugify(data["slug"])
            if new_slug:
                existing = await AgentPublicProfileService.get_by_slug(new_slug, db)
                if existing and existing.id != profile.id:
                    raise ValueError(f"Slug '{new_slug}' is already taken")
                profile.slug = new_slug

        # Update fields
        updatable = [
            "tagline",
            "long_description",
            "hero_image_url",
            "preview_video_url",
            "gallery_images",
            "example_conversations",
            "creator_bio",
            "creator_display_name",
            "seo_title",
            "seo_description",
            "og_image_url",
            "cta_label",
            "accent_color",
        ]
        for field in updatable:
            if field in data:
                setattr(profile, field, data[field])

        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def publish_profile(agent_id: UUID, tenant_id: UUID, db: AsyncSession) -> AgentPublicProfile:
        """Publish a profile. Validates agent.is_public=True first."""
        # Check agent is public
        agent_result = await db.execute(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id))
        agent = agent_result.scalar_one_or_none()
        if agent is None:
            raise ValueError("Agent not found")
        if not agent.is_public:
            raise ValueError("Agent must be set to public before publishing landing page")

        result = await db.execute(
            select(AgentPublicProfile).where(
                AgentPublicProfile.agent_id == agent_id,
                AgentPublicProfile.tenant_id == tenant_id,
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            raise ValueError("Public profile not found. Create the profile first.")

        profile.is_published = True
        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def get_public_profile_full(slug: str, db: AsyncSession) -> dict | None:
        """Get full public profile data: agent + profile + creator + pricing."""
        result = await db.execute(
            select(AgentPublicProfile).where(
                AgentPublicProfile.slug == slug,
                AgentPublicProfile.is_published.is_(True),
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return None

        # Load agent
        agent_result = await db.execute(select(Agent).where(Agent.id == profile.agent_id))
        agent = agent_result.scalar_one_or_none()

        # Load pricing
        pricing_result = await db.execute(select(AgentPricing).where(AgentPricing.agent_id == profile.agent_id))
        pricing = pricing_result.scalar_one_or_none()

        # Load creator profile
        creator_result = await db.execute(select(CreatorProfile).where(CreatorProfile.tenant_id == profile.tenant_id))
        creator = creator_result.scalar_one_or_none()

        return {
            "profile": profile,
            "agent": agent,
            "pricing": pricing,
            "creator": creator,
        }

    @staticmethod
    async def increment_view_count(slug: str, db: AsyncSession) -> None:
        """Increment view count for a profile. Uses direct DB update."""
        from sqlalchemy import update as sql_update

        await db.execute(
            sql_update(AgentPublicProfile)
            .where(AgentPublicProfile.slug == slug)
            .values(view_count=AgentPublicProfile.view_count + 1)
        )
        await db.commit()
