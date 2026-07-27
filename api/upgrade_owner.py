import asyncio
from sqlalchemy import text
from src.core.database import get_async_session_factory

async def upgrade():
    async with get_async_session_factory()() as db:
        # Get tenant_id and enterprise plan id
        r = await db.execute(text(
            "SELECT t.id FROM tenants t "
            "JOIN tenant_account_joins taj ON t.id = taj.tenant_id "
            "JOIN accounts a ON a.id = taj.account_id "
            "WHERE a.email = 'rajuniit+me3@gmail.com'"
        ))
        tenant_id = r.scalar_one()

        r = await db.execute(text("SELECT id FROM subscription_plans WHERE name ILIKE '%enterprise%' LIMIT 1"))
        plan_id = r.scalar_one()

        print(f"Tenant: {tenant_id}, Enterprise plan: {plan_id}")

        # Update subscription to Enterprise
        # Check if subscription exists
        r = await db.execute(text("SELECT id FROM tenant_subscriptions WHERE tenant_id = :tid"), {'tid': tenant_id})
        existing = r.fetchone()
        if existing:
            r = await db.execute(text(
                "UPDATE tenant_subscriptions SET plan_id = :plan_id, status = 'ACTIVE', updated_at = now() WHERE tenant_id = :tid"
            ), {'plan_id': plan_id, 'tid': tenant_id})
            print(f"Subscription updated: {r.rowcount}")
        else:
            r = await db.execute(text(
                "INSERT INTO tenant_subscriptions "
                "(id, tenant_id, plan_id, status, billing_cycle, current_period_start, current_period_end, payment_provider, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :tid, :plan_id, 'ACTIVE', 'MONTHLY', now(), now() + interval '100 years', 'manual', now(), now())"
            ), {'plan_id': plan_id, 'tid': tenant_id})
            print(f"Subscription inserted: {r.rowcount}")

        # Upsert credit balance — 1,000,000 credits
        r = await db.execute(text(
            "INSERT INTO credit_balances (id, tenant_id, total_credits, used_credits, available_credits, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :tid, 1000000, 0, 1000000, now(), now()) "
            "ON CONFLICT (tenant_id) DO UPDATE "
            "SET total_credits = 1000000, used_credits = 0, available_credits = 1000000, updated_at = now()"
        ), {'tid': tenant_id})
        print(f"Credit balance rows: {r.rowcount}")

        await db.commit()
        print("Done — owner upgraded to Enterprise with 1,000,000 credits.")

asyncio.run(upgrade())
