"""
Agent Pricing Service

Handles agent monetization, pricing configuration, and revenue calculations.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.agent_pricing import AgentPricing, PricingModel
from src.models.agent_revenue import AgentRevenue, RevenueStatus


class AgentPricingService:
    """Service for managing agent pricing and monetization"""

    # Conversion rate for credits to USD (for reporting)
    CREDIT_VALUE_USD = Decimal("0.02")

    @staticmethod
    async def get_agent_pricing(agent_id: UUID, db: AsyncSession) -> AgentPricing | None:
        """Get pricing configuration for an agent"""
        result = await db.execute(select(AgentPricing).where(AgentPricing.agent_id == agent_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_agent_pricing(
        agent_id: UUID,
        tenant_id: UUID,
        pricing_model: PricingModel,
        credits_per_use: int = 0,
        revenue_share_percentage: Decimal = Decimal("70.00"),
        monthly_subscription_credits: int | None = None,
        db: AsyncSession = None,
    ) -> AgentPricing:
        """Create pricing configuration for an agent"""
        if db is None:
            raise ValueError("Database session is required")

        # Check if pricing already exists
        existing = await AgentPricingService.get_agent_pricing(agent_id, db)
        if existing:
            raise ValueError("Pricing configuration already exists for this agent")

        # Validate pricing model
        if pricing_model == PricingModel.PER_USE and credits_per_use <= 0:
            raise ValueError("Per-use agents must have a positive credit cost")

        if pricing_model == PricingModel.SUBSCRIPTION and not monthly_subscription_credits:
            raise ValueError("Subscription agents must have a monthly credit cost")

        # Create pricing
        pricing = AgentPricing(
            agent_id=agent_id,
            tenant_id=tenant_id,
            pricing_model=pricing_model,
            credits_per_use=credits_per_use,
            revenue_share_percentage=revenue_share_percentage,
            monthly_subscription_credits=monthly_subscription_credits,
            is_active=True,
        )

        db.add(pricing)
        await db.commit()
        await db.refresh(pricing)

        return pricing

    @staticmethod
    async def update_agent_pricing(
        agent_id: UUID,
        pricing_model: PricingModel | None = None,
        credits_per_use: int | None = None,
        revenue_share_percentage: Decimal | None = None,
        monthly_subscription_credits: int | None = None,
        is_active: bool | None = None,
        db: AsyncSession = None,
    ) -> AgentPricing:
        """Update pricing configuration for an agent"""
        if db is None:
            raise ValueError("Database session is required")

        pricing = await AgentPricingService.get_agent_pricing(agent_id, db)
        if not pricing:
            raise ValueError("Pricing configuration not found for this agent")

        # Update fields
        if pricing_model is not None:
            pricing.pricing_model = pricing_model

        if credits_per_use is not None:
            pricing.credits_per_use = credits_per_use

        if revenue_share_percentage is not None:
            pricing.revenue_share_percentage = revenue_share_percentage

        if monthly_subscription_credits is not None:
            pricing.monthly_subscription_credits = monthly_subscription_credits

        if is_active is not None:
            pricing.is_active = is_active

        await db.commit()
        await db.refresh(pricing)

        return pricing

    @staticmethod
    async def calculate_agent_cost(agent_id: UUID, base_action_cost: int, db: AsyncSession) -> int:
        """Calculate total credit cost for using an agent"""
        pricing = await AgentPricingService.get_agent_pricing(agent_id, db)

        if not pricing or pricing.is_free or not pricing.is_active:
            return base_action_cost

        if pricing.pricing_model == PricingModel.PER_USE:
            return base_action_cost + (pricing.credits_per_use or 0)

        # For subscription agents, only charge base action cost
        # (subscription fee is handled separately)
        return base_action_cost

    @staticmethod
    async def record_agent_usage(
        agent_id: UUID, transaction_id: UUID, credits_used: int, db: AsyncSession
    ) -> AgentRevenue | None:
        """
        Record agent usage and calculate revenue distribution.

        Args:
            agent_id: ID of the agent used
            transaction_id: ID of the credit transaction
            credits_used: Total credits used in this interaction
            db: Database session
        """
        # Get agent pricing
        pricing = await AgentPricingService.get_agent_pricing(agent_id, db)
        if not pricing or not pricing.is_paid:
            return None

        # Calculate split
        # Creator gets revenue_share_percentage of the total credits used
        # Platform gets the rest

        # Note: Revenue logic might depend on whether we share ALL credits or only the markup.
        # Assuming we share ALL credits used for the agent invocation if it's a paid agent.
        # Or typically, platform takes base cost + fee?
        # Let's stick to the simple revenue share on the total credits for now as per model.

        creator_share_pct = pricing.revenue_share_percentage
        creator_credits = round(credits_used * float(creator_share_pct) / 100)
        platform_credits = credits_used - creator_credits

        # Create revenue record
        revenue = AgentRevenue(
            agent_pricing_id=pricing.id,
            tenant_id=pricing.tenant_id,  # Creator's tenant
            transaction_id=transaction_id,
            total_credits=credits_used,
            creator_credits=creator_credits,
            platform_credits=platform_credits,
            revenue_share_percentage=creator_share_pct,
            status=RevenueStatus.PENDING,
        )

        # Update totals on pricing record
        pricing.total_uses += 1
        pricing.total_revenue_credits += creator_credits

        db.add(revenue)
        await db.commit()
        await db.refresh(revenue)

        return revenue

    @staticmethod
    async def get_agent_earnings(
        agent_id: UUID, start_date: datetime | None = None, end_date: datetime | None = None, db: AsyncSession = None
    ) -> dict:
        """Get earnings summary for an agent (in credits and estimated USD)"""
        if db is None:
            raise ValueError("Database session is required")

        # Default to last 30 days if no dates provided
        if not end_date:
            end_date = datetime.now(UTC)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Need to join with AgentPricing to filter by agent_id, as AgentRevenue links to AgentPricing
        query = (
            select(
                func.sum(AgentRevenue.total_credits).label("total_credits"),
                func.sum(AgentRevenue.platform_credits).label("total_platform_credits"),
                func.sum(AgentRevenue.creator_credits).label("total_creator_credits"),
                func.count(AgentRevenue.id).label("total_transactions"),
            )
            .join(AgentPricing, AgentPricing.id == AgentRevenue.agent_pricing_id)
            .where(
                and_(
                    AgentPricing.agent_id == agent_id,
                    AgentRevenue.created_at >= start_date,
                    AgentRevenue.created_at <= end_date,
                )
            )
        )

        result = await db.execute(query)
        row = result.first()

        total_credits = int(row.total_credits or 0)
        creator_credits = int(row.total_creator_credits or 0)
        platform_credits = int(row.total_platform_credits or 0)

        return {
            "agent_id": str(agent_id),
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "total_credits": total_credits,
            "creator_credits": creator_credits,
            "platform_credits": platform_credits,
            "total_revenue_usd": float(Decimal(total_credits) * AgentPricingService.CREDIT_VALUE_USD),
            "creator_earnings_usd": float(Decimal(creator_credits) * AgentPricingService.CREDIT_VALUE_USD),
            "total_transactions": int(row.total_transactions or 0),
        }

    @staticmethod
    async def get_creator_earnings(
        creator_tenant_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        db: AsyncSession = None,
    ) -> dict:
        """Get total earnings for a creator tenant across all their agents"""
        if db is None:
            raise ValueError("Database session is required")

        if not end_date:
            end_date = datetime.now(UTC)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Build query
        query = select(
            func.sum(AgentRevenue.total_credits).label("total_credits"),
            func.sum(AgentRevenue.platform_credits).label("total_platform_credits"),
            func.sum(AgentRevenue.creator_credits).label("total_creator_credits"),
            func.count(func.distinct(AgentRevenue.agent_pricing_id)).label("monetized_agents"),
            func.count(AgentRevenue.id).label("total_transactions"),
        ).where(
            and_(
                AgentRevenue.tenant_id == creator_tenant_id,
                AgentRevenue.created_at >= start_date,
                AgentRevenue.created_at <= end_date,
            )
        )

        result = await db.execute(query)
        row = result.first()

        # Get pending payout amount
        pending_query = select(func.sum(AgentRevenue.creator_credits)).where(
            and_(AgentRevenue.tenant_id == creator_tenant_id, AgentRevenue.status == RevenueStatus.PENDING)
        )
        pending_result = await db.execute(pending_query)
        pending_credits = pending_result.scalar() or 0

        creator_credits = int(row.total_creator_credits or 0)

        return {
            "creator_tenant_id": str(creator_tenant_id),
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "creator_credits": creator_credits,
            "creator_earnings_usd": float(Decimal(creator_credits) * AgentPricingService.CREDIT_VALUE_USD),
            "pending_payout_credits": int(pending_credits),
            "pending_payout_usd": float(Decimal(pending_credits) * AgentPricingService.CREDIT_VALUE_USD),
            "monetized_agents": int(row.monetized_agents or 0),
            "total_transactions": int(row.total_transactions or 0),
        }

    @staticmethod
    async def get_top_earning_agents(
        limit: int = 10, start_date: datetime | None = None, end_date: datetime | None = None, db: AsyncSession = None
    ) -> list[dict]:
        """Get top earning agents"""
        if db is None:
            raise ValueError("Database session is required")

        if not end_date:
            end_date = datetime.now(UTC)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Join AgentRevenue -> AgentPricing -> Agent
        query = (
            select(
                Agent.id.label("agent_id"),
                Agent.agent_name,
                func.sum(AgentRevenue.total_credits).label("total_revenue_credits"),
                func.sum(AgentRevenue.creator_credits).label("creator_earnings_credits"),
                func.count(AgentRevenue.id).label("usage_count"),
            )
            .join(AgentPricing, AgentPricing.id == AgentRevenue.agent_pricing_id)
            .join(Agent, Agent.id == AgentPricing.agent_id)
            .where(and_(AgentRevenue.created_at >= start_date, AgentRevenue.created_at <= end_date))
            .group_by(Agent.id, Agent.agent_name)
            .order_by(func.sum(AgentRevenue.creator_credits).desc())
            .limit(limit)
        )

        result = await db.execute(query)
        rows = result.all()

        return [
            {
                "agent_id": str(row.agent_id),
                "agent_name": row.agent_name,
                "total_revenue_credits": int(row.total_revenue_credits),
                "creator_earnings_credits": int(row.creator_earnings_credits),
                "creator_earnings_usd": float(
                    Decimal(row.creator_earnings_credits) * AgentPricingService.CREDIT_VALUE_USD
                ),
                "usage_count": int(row.usage_count),
            }
            for row in rows
        ]

    @staticmethod
    async def calculate_agent_cost_by_tier(
        pricing: "AgentPricing",
        tier: str,
        db: AsyncSession,
        discount_code: str | None = None,
    ) -> int:
        """Calculate credit cost for a specific access tier, applying optional discount."""
        from src.services.billing.discount_code_service import DiscountCodeService

        tier_map = {
            "SESSION": pricing.session_credits,
            "DAILY": pricing.daily_credits,
            "WEEKLY": pricing.weekly_credits,
            "MONTHLY": pricing.monthly_subscription_credits,
        }
        base = tier_map.get(tier)
        if base is None:
            raise ValueError(f"No credit cost configured for tier '{tier}'")

        if discount_code:
            discount = await DiscountCodeService.validate_code(discount_code, pricing.id, db)
            if discount:
                return await DiscountCodeService.apply_and_consume(discount.id, base, db)

        return base

    @staticmethod
    async def get_upsell_prompt(agent_id: UUID, db: AsyncSession) -> dict | None:
        """Return pricing data for the paywall upsell prompt.

        Returns a dict with pricing info for the agent if paid, None if free.
        """
        from src.models.agent_public_profile import AgentPublicProfile

        pricing = await AgentPricingService.get_agent_pricing(agent_id, db)
        if pricing is None or pricing.is_free:
            return None

        # Get slug for deep-link
        profile_result = await db.execute(select(AgentPublicProfile).where(AgentPublicProfile.agent_id == agent_id))
        profile = profile_result.scalar_one_or_none()

        return {
            "pricing_id": str(pricing.id),
            "pricing_model": pricing.pricing_model,
            "session_credits": pricing.session_credits,
            "daily_credits": pricing.daily_credits,
            "weekly_credits": pricing.weekly_credits,
            "monthly_credits": pricing.monthly_subscription_credits,
            "trial_messages": pricing.trial_messages or 0,
            "slug": profile.slug if profile else None,
        }
