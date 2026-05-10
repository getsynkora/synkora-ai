"""
Seed data for default subscription plans

Pricing Strategy:
- Free: Full-featured entry point with generous limits (all features unlocked)
- Professional ($79/mo): For growing businesses with advanced needs
- Enterprise ($299/mo): For large organizations with full features
- Hobby / Starter: Hidden legacy tiers (is_active=False), existing subscribers unaffected

Simplified Credit Model (BYOK - Bring Your Own Key):
- 1 credit = 1 platform action (message, tool use, KB query, agent execution)
- File uploads = 2 credits (storage costs)
- Customers use their own LLM API keys, so all models cost the same credits
- Credit value: ~100-330 credits per dollar (better value at higher tiers)
"""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.subscription_plan import PlanTier, SubscriptionPlan

logger = logging.getLogger(__name__)


async def seed_subscription_plans(db: AsyncSession, update: bool = False) -> None:
    """
    Create or update subscription plans.

    Args:
        db: Database session
        update: If True, update existing plans. If False, skip if plans exist.
    """
    from sqlalchemy import func

    # Check if plans already exist
    result = await db.execute(select(func.count()).select_from(SubscriptionPlan))
    existing_count = result.scalar() or 0

    if existing_count > 0 and not update:
        logger.info("Subscription plans already exist, skipping seed (use --update to update)")
        return

    plans = [
        # FREE TIER - Full-featured entry point with generous limits
        {
            "name": "Free",
            "tier": PlanTier.FREE,
            "description": "Everything you need to build and deploy AI agents",
            "price_monthly": Decimal("0.00"),
            "price_yearly": Decimal("0.00"),
            "credits_monthly": 3000,
            "credits_rollover": False,
            # Column-based limits (enforced by middleware)
            "max_agents": 20,
            "max_team_members": 5,
            "max_api_calls_per_month": 3000,
            "max_knowledge_bases": 10,
            "max_data_sources": 50,
            "max_custom_tools": 10,
            "max_database_connections": 3,
            "max_mcp_servers": 5,
            "max_scheduled_tasks": 5,
            "max_widgets": 10,
            "max_slack_bots": 2,
            "max_api_keys": 5,
            # Feature flags (for UI/feature gating)
            "features": {
                "max_conversations": 1000,
                "max_messages_per_conversation": 2000,
                "knowledge_bases": True,
                "custom_tools": True,
                "mcp_servers": True,
                "api_access": True,
                "priority_support": False,
                "advanced_analytics": False,
                "custom_domains": False,
                "webhooks": True,
                "white_label": False,
                "sso": False,
                "audit_logs": False,
                "overage_allowed": False,
                "grace_period_days": 0,
                "platform_engineer_agent": True,
                "serverless_execution": False,
            },
            "is_active": True,
        },
        # HOBBY TIER - Hidden (legacy, not available for new subscriptions)
        {
            "name": "Hobby",
            "tier": PlanTier.HOBBY,
            "description": "For individual creators and hobbyists",
            "price_monthly": Decimal("9.00"),
            "price_yearly": Decimal("90.00"),
            "credits_monthly": 1000,
            "credits_rollover": False,
            "max_agents": 15,
            "max_team_members": 2,
            "max_api_calls_per_month": 1000,
            "max_knowledge_bases": 5,
            "max_data_sources": 10,
            "max_custom_tools": 10,
            "max_database_connections": 1,
            "max_mcp_servers": 3,
            "max_scheduled_tasks": 5,
            "max_widgets": 5,
            "max_slack_bots": 1,
            "max_api_keys": 0,
            "features": {
                "max_conversations": 500,
                "max_messages_per_conversation": 1000,
                "knowledge_bases": True,
                "custom_tools": True,
                "mcp_servers": True,
                "api_access": False,
                "priority_support": False,
                "advanced_analytics": False,
                "custom_domains": False,
                "webhooks": True,
                "white_label": False,
                "sso": False,
                "audit_logs": False,
                "overage_allowed": False,
                "grace_period_days": 3,
                "platform_engineer_agent": True,
                "serverless_execution": False,
            },
            "is_active": False,
        },
        # STARTER TIER - Hidden (legacy, not available for new subscriptions)
        {
            "name": "Starter",
            "tier": PlanTier.STARTER,
            "description": "For individuals and small teams",
            "price_monthly": Decimal("19.00"),
            "price_yearly": Decimal("190.00"),
            "credits_monthly": 3000,
            "credits_rollover": False,
            "max_agents": 25,
            "max_team_members": 3,
            "max_api_calls_per_month": 5000,
            "max_knowledge_bases": 10,
            "max_data_sources": 20,
            "max_custom_tools": 20,
            "max_database_connections": 3,
            "max_mcp_servers": 10,
            "max_scheduled_tasks": 10,
            "max_widgets": 10,
            "max_slack_bots": 3,
            "max_api_keys": 10,
            "features": {
                "max_conversations": 2000,
                "max_messages_per_conversation": 5000,
                "knowledge_bases": True,
                "custom_tools": True,
                "mcp_servers": True,
                "api_access": True,
                "priority_support": False,
                "advanced_analytics": False,
                "custom_domains": False,
                "webhooks": True,
                "white_label": False,
                "sso": False,
                "audit_logs": False,
                "overage_allowed": True,
                "overage_rate_per_credit": 0.01,
                "grace_period_days": 7,
                "platform_engineer_agent": True,
                "serverless_execution": False,
            },
            "is_active": False,
        },
        # PROFESSIONAL TIER - Growing businesses
        {
            "name": "Professional",
            "tier": PlanTier.PROFESSIONAL,
            "description": "For growing businesses",
            "price_monthly": Decimal("79.00"),
            "price_yearly": Decimal("790.00"),  # 2 months free
            "credits_monthly": 15000,  # 15,000 messages/actions per month
            "credits_rollover": True,  # Credits roll over!
            # Column-based limits
            "max_agents": 100,
            "max_team_members": 10,
            "max_api_calls_per_month": 50000,
            "max_knowledge_bases": 50,
            "max_data_sources": 100,
            "max_custom_tools": None,  # Unlimited
            "max_database_connections": 10,
            "max_mcp_servers": 50,
            "max_scheduled_tasks": 50,
            "max_widgets": 50,
            "max_slack_bots": 10,
            "max_api_keys": 50,  # Higher API key limit
            # Feature flags
            "features": {
                "max_conversations": -1,  # Unlimited
                "max_messages_per_conversation": -1,  # Unlimited
                "knowledge_bases": True,
                "custom_tools": True,
                "mcp_servers": True,
                "api_access": True,
                "priority_support": True,
                "advanced_analytics": True,
                "custom_domains": True,
                "webhooks": True,
                "white_label": False,
                "sso": False,
                "audit_logs": True,
                "overage_allowed": True,
                "overage_rate_per_credit": 0.008,  # $0.008 per credit (better rate)
                "grace_period_days": 14,
                "max_rollover_credits": 30000,  # Can accumulate up to 2 months
                "platform_engineer_agent": True,
                "serverless_execution": True,
            },
            "is_active": True,
        },
        # ENTERPRISE TIER - Large organizations
        {
            "name": "Enterprise",
            "tier": PlanTier.ENTERPRISE,
            "description": "For large organizations",
            "price_monthly": Decimal("299.00"),
            "price_yearly": Decimal("2990.00"),  # 2 months free
            "credits_monthly": 100000,  # 100,000 messages/actions per month
            "credits_rollover": True,  # Credits roll over!
            # Column-based limits (all unlimited)
            "max_agents": None,  # Unlimited
            "max_team_members": None,  # Unlimited
            "max_api_calls_per_month": None,  # Unlimited
            "max_knowledge_bases": None,  # Unlimited
            "max_data_sources": None,  # Unlimited
            "max_custom_tools": None,  # Unlimited
            "max_database_connections": None,  # Unlimited
            "max_mcp_servers": None,  # Unlimited
            "max_scheduled_tasks": None,  # Unlimited
            "max_widgets": None,  # Unlimited
            "max_slack_bots": None,  # Unlimited
            "max_api_keys": None,  # Unlimited
            # Feature flags
            "features": {
                "max_conversations": -1,  # Unlimited
                "max_messages_per_conversation": -1,  # Unlimited
                "knowledge_bases": True,
                "custom_tools": True,
                "mcp_servers": True,
                "api_access": True,
                "priority_support": True,
                "advanced_analytics": True,
                "custom_domains": True,
                "webhooks": True,
                "white_label": True,
                "sso": True,
                "audit_logs": True,
                "dedicated_support": True,
                "custom_integrations": True,
                "sla_guarantee": True,
                "overage_allowed": True,
                "overage_rate_per_credit": 0.005,  # $0.005 per credit (best rate)
                "grace_period_days": 30,
                "max_rollover_credits": 300000,  # Can accumulate up to 3 months
                "platform_engineer_agent": True,
                "serverless_execution": True,
            },
            "is_active": True,
        },
    ]

    if update and existing_count > 0:
        # Update existing plans
        updated_count = 0
        created_count = 0

        for plan_data in plans:
            tier = plan_data["tier"]
            result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.tier == tier))
            existing_plan = result.scalar_one_or_none()

            if existing_plan:
                # Update existing plan
                for key, value in plan_data.items():
                    if key != "tier":  # Don't change the tier
                        setattr(existing_plan, key, value)
                updated_count += 1
                logger.info(f"Updated plan: {plan_data['name']}")
            else:
                # Create new plan
                plan = SubscriptionPlan(**plan_data)
                db.add(plan)
                created_count += 1
                logger.info(f"Created plan: {plan_data['name']}")

        await db.commit()
        logger.info(f"Successfully updated {updated_count} plans, created {created_count} new plans")
    else:
        # Create all new plans
        for plan_data in plans:
            plan = SubscriptionPlan(**plan_data)
            db.add(plan)

        await db.commit()
        logger.info(f"Successfully seeded {len(plans)} subscription plans")


if __name__ == "__main__":
    import argparse
    import asyncio

    from src.core.database import get_async_db

    parser = argparse.ArgumentParser(description="Seed subscription plans")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update existing plans instead of skipping",
    )
    args = parser.parse_args()

    async def main():
        async for db in get_async_db():
            try:
                await seed_subscription_plans(db, update=args.update)
            finally:
                await db.close()

    asyncio.run(main())
