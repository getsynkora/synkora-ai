"""AgentUserSubscription service — paid chat/email access subscriptions."""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import stripe
from sqlalchemy import and_, select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_pricing import AgentPricing
from src.models.agent_user_subscription import AgentUserSubscription, SubscriptionAccessStatus
from src.services.billing.credit_service import CreditService
from src.services.billing.discount_code_service import DiscountCodeService

logger = logging.getLogger(__name__)

# Tier → access duration mapping
TIER_DURATIONS: dict[str, timedelta | None] = {
    "SESSION": timedelta(hours=2),
    "DAILY": timedelta(days=1),
    "WEEKLY": timedelta(days=7),
    "MONTHLY": timedelta(days=30),
    "EMAIL_ONE_TIME": None,  # No expiry for one-time email access
    "EMAIL_MONTHLY": timedelta(days=30),
}


def _hash_token(token: str) -> str:
    """SHA-256 hash a guest token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class AgentUserSubscriptionService:
    """Service for managing paid agent access subscriptions."""

    @staticmethod
    async def check_access(
        agent_id: UUID,
        db: AsyncSession,
        subscriber_tenant_id: UUID | None = None,
        guest_token: str | None = None,
    ) -> bool:
        """Check if a user/guest has active access to an agent."""
        if subscriber_tenant_id is None and guest_token is None:
            return False

        stmt = select(AgentUserSubscription).where(
            AgentUserSubscription.agent_id == agent_id,
            AgentUserSubscription.status == SubscriptionAccessStatus.ACTIVE,
        )

        if subscriber_tenant_id is not None:
            stmt = stmt.where(AgentUserSubscription.subscriber_tenant_id == subscriber_tenant_id)
        elif guest_token is not None:
            token_hash = _hash_token(guest_token)
            stmt = stmt.where(AgentUserSubscription.guest_token_hash == token_hash)

        result = await db.execute(stmt)
        sub = result.scalar_one_or_none()
        if sub is None:
            return False

        # Check expiry
        if sub.expires_at and sub.expires_at < datetime.now(UTC):
            sub.status = SubscriptionAccessStatus.EXPIRED
            await db.commit()
            return False

        return True

    @staticmethod
    async def subscribe_account_user(
        agent_id: UUID,
        pricing_id: UUID,
        subscriber_tenant_id: UUID,
        tier: str,
        db: AsyncSession,
        discount_code: str | None = None,
    ) -> AgentUserSubscription:
        """Subscribe an account user using credits."""
        pricing_result = await db.execute(select(AgentPricing).where(AgentPricing.id == pricing_id))
        pricing = pricing_result.scalar_one_or_none()
        if pricing is None:
            raise ValueError("Pricing configuration not found")

        # Determine cost
        tier_credit_map = {
            "SESSION": pricing.session_credits,
            "DAILY": pricing.daily_credits,
            "WEEKLY": pricing.weekly_credits,
            "MONTHLY": pricing.monthly_subscription_credits,
        }
        base_credits = tier_credit_map.get(tier)
        if base_credits is None:
            raise ValueError(f"No credit cost configured for tier '{tier}'")

        amount_credits = base_credits

        # Apply discount code if provided
        if discount_code:
            discount = await DiscountCodeService.validate_code(discount_code, pricing_id, db)
            if discount:
                amount_credits = await DiscountCodeService.apply_and_consume(discount.id, base_credits, db)

        # Deduct credits
        from src.models.credit_transaction import TransactionType

        credit_service = CreditService(db)
        await credit_service.deduct_credits(
            tenant_id=subscriber_tenant_id,
            amount=amount_credits,
            transaction_type=TransactionType.USAGE,
            description=f"Agent access subscription ({tier})",
        )

        # Record revenue
        from src.models.agent_revenue import AgentRevenue, RevenueStatus

        creator_credits = pricing.calculate_creator_revenue(amount_credits)
        platform_credits = pricing.calculate_platform_revenue(amount_credits)
        revenue = AgentRevenue(
            agent_pricing_id=pricing_id,
            tenant_id=pricing.tenant_id,
            total_credits=amount_credits,
            creator_credits=creator_credits,
            platform_credits=platform_credits,
            revenue_share_percentage=pricing.revenue_share_percentage,
            status=RevenueStatus.PENDING,
        )
        db.add(revenue)

        # Create subscription
        duration = TIER_DURATIONS.get(tier)
        now = datetime.now(UTC)
        sub = AgentUserSubscription(
            agent_id=agent_id,
            agent_pricing_id=pricing_id,
            subscriber_tenant_id=subscriber_tenant_id,
            pricing_tier=tier,
            amount_cents=0,  # Credit-based — no cents
            status=SubscriptionAccessStatus.ACTIVE,
            started_at=now,
            expires_at=now + duration if duration else None,
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)
        return sub

    @staticmethod
    async def create_stripe_checkout_session(
        agent_id: UUID,
        pricing_id: UUID,
        tier: str,
        guest_email: str,
        success_url: str,
        cancel_url: str,
        db: AsyncSession,
    ) -> str:
        """Create a Stripe Checkout Session for guest subscription. Returns checkout URL."""
        pricing_result = await db.execute(select(AgentPricing).where(AgentPricing.id == pricing_id))
        pricing = pricing_result.scalar_one_or_none()
        if pricing is None:
            raise ValueError("Pricing configuration not found")

        # Get price in cents
        price_map = {
            "SESSION": pricing.session_credits,  # 1 credit = 1 cent for guest
            "DAILY": pricing.daily_credits,
            "WEEKLY": pricing.weekly_credits,
            "MONTHLY": pricing.monthly_subscription_credits,
            "EMAIL_ONE_TIME": pricing.email_subscription_price_cents,
            "EMAIL_MONTHLY": pricing.email_subscription_price_cents,
        }
        amount_cents = price_map.get(tier)
        if not amount_cents:
            raise ValueError(f"No price configured for tier '{tier}'")

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": amount_cents,
                        "product_data": {
                            "name": f"Agent Access — {tier}",
                        },
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            customer_email=guest_email,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "type": "agent_access",
                "agent_id": str(agent_id),
                "pricing_id": str(pricing_id),
                "tier": tier,
                "guest_email": guest_email,
                "amount_cents": str(amount_cents),
            },
        )
        return session["url"]

    @staticmethod
    async def fulfill_guest_subscription(stripe_session_id: str, db: AsyncSession) -> tuple[str, str]:
        """Called after Stripe webhook checkout.session.completed. Returns (guest_token, guest_email)."""
        session = stripe.checkout.Session.retrieve(stripe_session_id)
        metadata = session["metadata"]

        agent_id = UUID(metadata["agent_id"])
        pricing_id = UUID(metadata["pricing_id"])
        tier = metadata["tier"]
        guest_email = metadata["guest_email"]
        amount_cents = int(metadata["amount_cents"])

        # Generate access token
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)

        duration = TIER_DURATIONS.get(tier)
        now = datetime.now(UTC)
        sub = AgentUserSubscription(
            agent_id=agent_id,
            agent_pricing_id=pricing_id,
            subscriber_tenant_id=None,
            guest_email=guest_email,
            guest_token_hash=token_hash,
            stripe_customer_id=session.get("customer"),
            pricing_tier=tier,
            amount_cents=amount_cents,
            status=SubscriptionAccessStatus.ACTIVE,
            started_at=now,
            expires_at=now + duration if duration else None,
        )
        db.add(sub)
        await db.commit()
        return raw_token, guest_email

    @staticmethod
    async def cancel_subscription(
        sub_id: UUID,
        db: AsyncSession,
        subscriber_tenant_id: UUID | None = None,
        guest_token: str | None = None,
    ) -> AgentUserSubscription:
        """Cancel an active subscription."""
        result = await db.execute(select(AgentUserSubscription).where(AgentUserSubscription.id == sub_id))
        sub = result.scalar_one_or_none()
        if sub is None:
            raise ValueError("Subscription not found")

        # Verify ownership
        if subscriber_tenant_id and sub.subscriber_tenant_id != subscriber_tenant_id:
            raise ValueError("Access denied")
        if guest_token:
            token_hash = _hash_token(guest_token)
            if sub.guest_token_hash != token_hash:
                raise ValueError("Access denied")

        sub.status = SubscriptionAccessStatus.CANCELLED
        sub.cancelled_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(sub)
        return sub

    @staticmethod
    async def expire_stale_subscriptions(db: AsyncSession) -> int:
        """Mark expired subscriptions as EXPIRED. Returns count updated."""
        now = datetime.now(UTC)
        result = await db.execute(
            sql_update(AgentUserSubscription)
            .where(
                AgentUserSubscription.status == SubscriptionAccessStatus.ACTIVE,
                AgentUserSubscription.expires_at.isnot(None),
                AgentUserSubscription.expires_at < now,
            )
            .values(status=SubscriptionAccessStatus.EXPIRED)
        )
        await db.commit()
        return result.rowcount

    @staticmethod
    async def convert_guest_to_account(
        guest_token: str,
        tenant_id: UUID,
        db: AsyncSession,
    ) -> AgentUserSubscription:
        """Transfer guest subscription to a newly registered account."""
        token_hash = _hash_token(guest_token)
        result = await db.execute(
            select(AgentUserSubscription).where(
                AgentUserSubscription.guest_token_hash == token_hash,
                AgentUserSubscription.status == SubscriptionAccessStatus.ACTIVE,
            )
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            raise ValueError("No active guest subscription found for this token")

        sub.subscriber_tenant_id = tenant_id
        sub.guest_token_hash = None  # Clear guest token after conversion
        sub.guest_email = None
        await db.commit()
        await db.refresh(sub)
        return sub
