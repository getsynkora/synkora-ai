"""
Subscription Service - Manages subscription plans and tenant subscriptions
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.credit_transaction import TransactionType
from src.models.subscription_plan import PlanTier, SubscriptionPlan
from src.models.tenant_subscription import SubscriptionStatus, TenantSubscription
from src.services.billing.credit_service import CreditService


class SubscriptionService:
    """Service for managing subscriptions"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.credit_service = CreditService(db)

    async def get_plan(self, plan_id: UUID) -> SubscriptionPlan | None:
        """Get subscription plan by ID"""
        result = await self.db.execute(select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id))
        return result.scalar_one_or_none()

    async def get_plan_by_tier(self, tier: PlanTier) -> SubscriptionPlan | None:
        """Get subscription plan by tier"""
        result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.tier == tier).where(SubscriptionPlan.is_active)
        )
        return result.scalar_one_or_none()

    async def list_active_plans(self) -> list[SubscriptionPlan]:
        """List all active subscription plans"""
        result = await self.db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.is_active).order_by(SubscriptionPlan.price_monthly)
        )
        return list(result.scalars().all())

    async def get_tenant_subscription(self, tenant_id: UUID) -> TenantSubscription | None:
        """Get active subscription for a tenant"""
        from sqlalchemy.orm import selectinload

        result = await self.db.execute(
            select(TenantSubscription)
            .options(selectinload(TenantSubscription.plan))
            .where(TenantSubscription.tenant_id == tenant_id)
            .where(TenantSubscription.status == SubscriptionStatus.ACTIVE)
        )
        return result.scalar_one_or_none()

    async def create_subscription(
        self,
        tenant_id: UUID,
        plan_id: UUID,
        stripe_subscription_id: str | None = None,
        paddle_subscription_id: str | None = None,
        payment_provider: str = "stripe",
    ) -> TenantSubscription:
        """Create a new subscription for a tenant"""
        plan = await self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        # Cancel any existing active subscription
        existing = await self.get_tenant_subscription(tenant_id)
        if existing:
            existing.status = SubscriptionStatus.CANCELLED
            existing.cancelled_at = datetime.now(UTC)

        # Calculate billing dates
        now = datetime.now(UTC)
        next_billing = now + timedelta(days=30)  # Monthly billing

        # Create new subscription
        subscription = TenantSubscription(
            tenant_id=tenant_id,
            plan_id=plan_id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now,
            current_period_end=next_billing,
            payment_provider=payment_provider,
            stripe_subscription_id=stripe_subscription_id,
            paddle_subscription_id=paddle_subscription_id,
        )

        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)

        # Add credits to tenant's balance
        await self.credit_service.add_credits(
            tenant_id=tenant_id,
            amount=plan.credits_monthly,
            transaction_type=TransactionType.SUBSCRIPTION_ALLOCATION,
            description=f"Monthly credits for {plan.name} plan",
            reference_id=subscription.id,
        )

        return subscription

    async def renew_subscription(self, subscription_id: UUID) -> TenantSubscription:
        """Renew a subscription (called during billing cycle)"""
        result = await self.db.execute(select(TenantSubscription).where(TenantSubscription.id == subscription_id))
        subscription = result.scalar_one_or_none()

        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        plan = await self.get_plan(subscription.plan_id)
        if not plan:
            raise ValueError(f"Plan {subscription.plan_id} not found")

        # Update billing period
        now = datetime.now(UTC)
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=30)

        # Start the new period from zero used. Unused credits, top-ups included, expire unless
        # the plan allows rollover, and then only up to max_rollover_credits. Previously the old
        # total stayed in place and every renewal piled the new grant on top of it.
        max_rollover = int((plan.features or {}).get("max_rollover_credits", 0) or 0)
        await self.credit_service.apply_monthly_rollover(
            tenant_id=subscription.tenant_id,
            new_credits=0,
            max_rollover=max_rollover,
            credits_rollover=bool(plan.credits_rollover),
        )

        # Add the new monthly credits (quota-pool plans grant none; their pools reset per period)
        if plan.credits_monthly:
            await self.credit_service.add_credits(
                tenant_id=subscription.tenant_id,
                amount=plan.credits_monthly,
                transaction_type=TransactionType.SUBSCRIPTION_ALLOCATION,
                description=f"Monthly credits renewal for {plan.name} plan",
                reference_id=subscription.id,
            )

        await self.db.commit()
        await self.db.refresh(subscription)

        return subscription

    async def cancel_subscription(self, subscription_id: UUID, immediate: bool = False) -> TenantSubscription:
        """Cancel a subscription"""
        result = await self.db.execute(select(TenantSubscription).where(TenantSubscription.id == subscription_id))
        subscription = result.scalar_one_or_none()

        if not subscription:
            raise ValueError(f"Subscription {subscription_id} not found")

        if immediate:
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancelled_at = datetime.now(UTC)
        else:
            # Cancel at end of billing period
            subscription.cancel_at_period_end = True

        await self.db.commit()
        await self.db.refresh(subscription)

        return subscription

    async def upgrade_subscription(self, tenant_id: UUID, new_plan_id: UUID) -> TenantSubscription:
        """Upgrade/downgrade a subscription"""
        current_subscription = await self.get_tenant_subscription(tenant_id)
        if not current_subscription:
            raise ValueError("No active subscription found")

        new_plan = await self.get_plan(new_plan_id)
        if not new_plan:
            raise ValueError(f"Plan {new_plan_id} not found")

        current_plan = await self.get_plan(current_subscription.plan_id)
        if not current_plan:
            raise ValueError(f"Current plan {current_subscription.plan_id} not found")

        # Calculate prorated credits
        days_remaining = (current_subscription.current_period_end - datetime.now(UTC)).days
        if days_remaining > 0:
            # Prorated credit adjustment
            daily_credits_old = current_plan.credits_monthly / 30
            daily_credits_new = new_plan.credits_monthly / 30
            credit_diff = int((daily_credits_new - daily_credits_old) * days_remaining)

            if credit_diff > 0:
                await self.credit_service.add_credits(
                    tenant_id=tenant_id,
                    amount=credit_diff,
                    transaction_type=TransactionType.SUBSCRIPTION_ALLOCATION,
                    description=f"Prorated credits for upgrade to {new_plan.name}",
                    reference_id=current_subscription.id,
                )

        # Update subscription
        current_subscription.plan_id = new_plan_id

        await self.db.commit()
        await self.db.refresh(current_subscription)

        return current_subscription

    async def get_subscription_history(self, tenant_id: UUID, limit: int = 10) -> list[TenantSubscription]:
        """Get subscription history for a tenant"""
        result = await self.db.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_subscription(self, tenant_id: UUID) -> TenantSubscription | None:
        """Get active subscription for a tenant (alias for get_tenant_subscription)"""
        return await self.get_tenant_subscription(tenant_id)

    async def get_subscription_by_tenant(self, tenant_id: UUID) -> TenantSubscription | None:
        """Get active subscription for a tenant (async version)"""
        return await self.get_tenant_subscription(tenant_id)

    async def get_available_plans(self) -> list[SubscriptionPlan]:
        """Get all available subscription plans (alias for list_active_plans)"""
        return await self.list_active_plans()

    async def get_subscription_payment_provider(self, tenant_id: UUID) -> str | None:
        """Get the payment provider for a tenant's active subscription"""
        subscription = await self.get_tenant_subscription(tenant_id)
        if subscription:
            return getattr(subscription, "payment_provider", "stripe")
        return None
