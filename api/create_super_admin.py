#!/usr/bin/env python3
"""
Script to create a super admin user with Platform Owner role.

This script performs the following:
1. Seeds system roles and permissions (if not already done)
2. Creates a tenant for the super admin
3. Creates the super admin account
4. Assigns Platform Owner role to the account

Usage:
    python create_super_admin.py

Interactive prompts will guide you through the process.
"""

import asyncio
import getpass
import os
import sys
from uuid import uuid4

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from datetime import UTC

import bcrypt
from sqlalchemy.orm import Session

from src.core.database import get_async_session_factory, get_db
from src.models import (
    Account,
    AccountRole,
    AccountStatus,
    Role,
    Tenant,
    TenantAccountJoin,
    TenantPlan,
    TenantStatus,
    TenantType,
)
from src.models.subscription_plan import PlanTier, SubscriptionPlan
from src.models.tenant_subscription import BillingCycle, SubscriptionStatus, TenantSubscription
from src.services.permissions.seed_roles_permissions import seed_roles_and_permissions


async def _run_seed_roles_and_permissions():
    """Run the async seed function with an async session."""
    factory = get_async_session_factory()
    async with factory() as async_db:
        await seed_roles_and_permissions(async_db)


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def create_super_admin(email: str, password: str, name: str, tenant_name: str, db: Session) -> tuple[bool, str]:
    """
    Create a super admin user with Platform Owner role.

    Args:
        email: Email address for the super admin
        password: Password for the super admin
        name: Full name of the super admin
        tenant_name: Name of the tenant to create
        db: Database session

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # 1. Check if email already exists
        existing_account = db.query(Account).filter(Account.email == email).first()
        if existing_account:
            return False, f"Account with email '{email}' already exists"

        print("\n📋 Step 1: Seeding system roles and permissions...")
        # 2. Seed roles and permissions
        try:
            asyncio.run(_run_seed_roles_and_permissions())
            print("✅ Roles and permissions seeded successfully")
        except Exception as e:
            # If already seeded, that's okay
            print(f"ℹ️  Roles may already be seeded: {str(e)}")

        # 3. Find Platform Owner role
        print("\n📋 Step 2: Finding Platform Owner role...")
        platform_owner_role = (
            db.query(Role)
            .filter(Role.name == "Platform Owner", Role.is_system.is_(True), Role.tenant_id.is_(None))
            .first()
        )

        if not platform_owner_role:
            return False, "Platform Owner role not found. Please run seed_roles_permissions first."

        print(f"✅ Found Platform Owner role (ID: {platform_owner_role.id})")

        # 4. Create tenant
        print(f"\n📋 Step 3: Creating tenant '{tenant_name}'...")
        tenant = Tenant(
            id=uuid4(),
            name=tenant_name,
            plan=TenantPlan.ENTERPRISE.value,  # Super admin gets enterprise plan
            tenant_type=TenantType.PLATFORM.value,  # Platform tenant
            status=TenantStatus.ACTIVE.value,
        )
        db.add(tenant)
        db.flush()
        print(f"✅ Created tenant: {tenant.name} (ID: {tenant.id})")

        # 5. Create account
        print("\n📋 Step 4: Creating super admin account...")
        account = Account(
            id=uuid4(),
            email=email,
            name=name,
            password_hash=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            status=AccountStatus.ACTIVE.value,
            is_platform_admin=True,  # Mark as platform admin
        )
        db.add(account)
        db.flush()
        print(f"✅ Created account: {account.name} ({account.email})")
        print(f"   Account ID: {account.id}")

        # 6. Create tenant-account join with Platform Owner role
        print("\n📋 Step 5: Assigning Platform Owner role...")
        tenant_account_join = TenantAccountJoin(
            id=uuid4(),
            tenant_id=tenant.id,
            account_id=account.id,
            role=AccountRole.OWNER,
            role_id=platform_owner_role.id,
        )
        db.add(tenant_account_join)

        # 7. Create Enterprise subscription (never-expiring) for super admin
        print("\n📋 Step 6: Assigning Enterprise subscription...")
        from datetime import datetime

        enterprise_plan = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.tier == PlanTier.ENTERPRISE, SubscriptionPlan.is_active.is_(True))
            .first()
        )
        if enterprise_plan:
            subscription = TenantSubscription(
                id=uuid4(),
                tenant_id=tenant.id,
                plan_id=enterprise_plan.id,
                status=SubscriptionStatus.ACTIVE,
                billing_cycle=BillingCycle.YEARLY,
                current_period_start=datetime.now(UTC),
                current_period_end=datetime(9999, 12, 31, tzinfo=UTC),
                payment_provider="internal",
                auto_renew="true",
            )
            db.add(subscription)
            print(f"✅ Enterprise subscription assigned (plan: {enterprise_plan.name})")
        else:
            print("⚠️  Enterprise plan not found — subscription not created. Run seed_plans first.")

        # 8. Allocate unlimited credits for super admin
        print("\n📋 Step 7: Allocating credits...")
        from src.models.credit_balance import CreditBalance
        from src.models.credit_transaction import CreditTransaction, TransactionType

        SUPER_ADMIN_CREDITS = 10_000_000  # 10 million credits
        credit_balance = CreditBalance(
            tenant_id=tenant.id,
            total_credits=SUPER_ADMIN_CREDITS,
            used_credits=0,
            available_credits=SUPER_ADMIN_CREDITS,
        )
        db.add(credit_balance)
        db.flush()

        credit_tx = CreditTransaction(
            credit_balance_id=credit_balance.id,
            tenant_id=tenant.id,
            amount=SUPER_ADMIN_CREDITS,
            transaction_type=TransactionType.ADJUSTMENT,
            description="Initial super admin credit allocation",
            balance_after=SUPER_ADMIN_CREDITS,
        )
        db.add(credit_tx)
        print(f"✅ {SUPER_ADMIN_CREDITS:,} credits allocated")

        # 9. Commit all changes
        db.commit()

        print("\n✅ Successfully created super admin!")
        print(f"\n{'=' * 60}")
        print("SUPER ADMIN CREDENTIALS")
        print(f"{'=' * 60}")
        print(f"Email:        {email}")
        print(f"Name:         {name}")
        print(f"Tenant:       {tenant_name}")
        print(f"Tenant ID:    {tenant.id}")
        print(f"Account ID:   {account.id}")
        print("Role:         Platform Owner")
        print(f"{'=' * 60}")
        print("\n⚠️  IMPORTANT: Save these credentials securely!")
        print("You can now log in to the platform with the email and password.")

        return True, "Super admin created successfully"

    except Exception as e:
        db.rollback()
        import traceback

        traceback.print_exc()
        return False, f"Error creating super admin: {str(e)}"


def main():
    """Main entry point with interactive prompts."""
    print("\n" + "=" * 60)
    print("SYNKORA - SUPER ADMIN CREATION")
    print("=" * 60)
    print("\nThis script will create a super admin user with Platform Owner role.")
    print("The super admin will have full access to all platform features.\n")

    # Get user input
    while True:
        email = input("Enter super admin email: ").strip()
        if not email:
            print("❌ Email cannot be empty")
            continue
        if not validate_email(email):
            print("❌ Invalid email format")
            continue
        break

    while True:
        password = getpass.getpass("Enter super admin password: ")
        if not password:
            print("❌ Password cannot be empty")
            continue
        if len(password) < 8:
            print("❌ Password must be at least 8 characters")
            continue

        password_confirm = getpass.getpass("Confirm password: ")
        if password != password_confirm:
            print("❌ Passwords do not match")
            continue
        break

    while True:
        name = input("Enter super admin full name: ").strip()
        if not name:
            print("❌ Name cannot be empty")
            continue
        break

    while True:
        tenant_name = input("Enter tenant/organization name: ").strip()
        if not tenant_name:
            print("❌ Tenant name cannot be empty")
            continue
        break

    # Confirm
    print("\n" + "=" * 60)
    print("CONFIRM DETAILS")
    print("=" * 60)
    print(f"Email:         {email}")
    print(f"Name:          {name}")
    print(f"Tenant Name:   {tenant_name}")
    print("Role:          Platform Owner")
    print("=" * 60)

    confirm = input("\nProceed with creation? (yes/no): ").strip().lower()
    if confirm not in ["yes", "y"]:
        print("\n❌ Cancelled by user")
        sys.exit(0)

    # Create super admin
    print("\n🔄 Creating super admin...\n")

    db: Session = next(get_db())
    try:
        success, message = create_super_admin(email=email, password=password, name=name, tenant_name=tenant_name, db=db)

        if success:
            print(f"\n✅ {message}")
            sys.exit(0)
        else:
            print(f"\n❌ {message}")
            sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
