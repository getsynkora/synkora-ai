"""
Pytest configuration and fixtures.

This module provides shared fixtures for all tests including database setup,
test client, and factory fixtures.
"""

import asyncio
import os
import socket
import uuid
from collections.abc import AsyncGenerator, Generator
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env.test into os.environ BEFORE any src.* imports.
#
# Why here and not after imports:
#   settings.py runs `settings = get_settings()` at module level. The first
#   `from src.config import settings` import triggers that call, which reads
#   os.environ at that instant. If we load .env.test after, it's too late —
#   the dev/prod values already cached by @lru_cache.
#
# Why force-set (not setdefault):
#   The api container starts with env_file: ./api/.env, which puts dev DB
#   settings into os.environ. setdefault would let those win. We need test
#   values to win so the tests never touch the dev database.
#
# Path is resolved relative to this file, not CWD, so it works regardless
# of where pytest is invoked (api/, /, inside Docker, etc.).
# ---------------------------------------------------------------------------
_ENV_TEST = Path(__file__).resolve().parent.parent / ".env.test"
if _ENV_TEST.exists():
    from dotenv import dotenv_values

    for _k, _v in dotenv_values(_ENV_TEST).items():
        if _v is not None:
            os.environ[_k] = _v
else:
    raise FileNotFoundError(
        f".env.test not found at {_ENV_TEST}\n"
        "Create it from .env.example and set APP_ENV=test, DB_DATABASE=synkora_test."
    )

# ---------------------------------------------------------------------------
# Docker network auto-detection.
#
# .env.test ships with DB_HOST=localhost / DB_PORT=5439 for local use
# (postgres-test is mapped to host port 5439 in docker-compose.yml).
#
# When running inside the Docker network (e.g. `docker-compose exec api pytest`)
# the postgres-test service is reachable at hostname "postgres-test" on port 5432.
# Detect this by attempting a DNS lookup of the service name — it resolves only
# inside the Docker network — and override DB_HOST/DB_PORT automatically so the
# user does not need to remember to pass -e flags.
# ---------------------------------------------------------------------------
try:
    socket.gethostbyname("postgres-test")
    # Hostname resolved → we are inside the Docker network.
    os.environ["DB_HOST"] = "postgres-test"
    os.environ["DB_PORT"] = "5432"
except (socket.gaierror, OSError):
    pass  # Outside Docker — keep .env.test values (localhost:5439)

# ---------------------------------------------------------------------------
# Now it is safe to import src modules — the settings singleton will be
# created with the test env vars already in os.environ.
# ---------------------------------------------------------------------------
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from src.config import settings as global_settings

# Safety check — abort early before any DB connection is attempted.
# Both conditions must hold: the env must be "test" AND the DB name must contain "test".
if global_settings.app_env != "test" or "test" not in global_settings.db_database:
    raise RuntimeError(
        f"Refusing to import test fixtures: DB safety check failed.\n"
        f"  app_env={global_settings.app_env!r} (must be 'test')\n"
        f"  db_database={global_settings.db_database!r} (must contain 'test')\n"
        f"Check that .env.test sets APP_ENV=test and DB_DATABASE=synkora_test."
    )

# Import other modules after settings are verified
from src.app import create_app
from src.core.database import Base
from src.models import Account, AccountRole, AccountStatus, Tenant, TenantAccountJoin, TenantPlan, TenantStatus
from src.models.subscription_plan import PlanTier, SubscriptionPlan


async def _seed_async_test_data() -> None:
    """
    Seed system roles/permissions AND subscription plans via async (asyncpg) connection.

    This is called via asyncio.run() in the session-scoped engine fixture to ensure
    that data is committed and visible to the middleware's async sessions (which also
    use asyncpg). Both sync and async engines point to the same PostgreSQL database,
    but seeding via async guarantees visibility for asyncpg-based reads.
    """
    from src.services.permissions.seed_roles_permissions import seed_roles_and_permissions

    async_test_engine = create_async_engine(
        global_settings.sqlalchemy_async_database_uri,
        echo=False,
        poolclass=NullPool,
    )
    try:
        factory = async_sessionmaker(
            bind=async_test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with factory() as db:
            # 1. Seed system roles and permissions (required for auth service owner-role lookup)
            await seed_roles_and_permissions(db)

            # 2. Re-seed subscription plans via async to ensure visibility to middleware
            #    (belt-and-suspenders: plans were already seeded via sync engine)
            await _seed_subscription_plans_async(db)
    finally:
        await async_test_engine.dispose()


async def _seed_subscription_plans_async(db: AsyncSession) -> None:
    """Seed subscription plans via async session for middleware visibility.

    Uses upsert (select + update-or-insert) to avoid FK violations from
    tenant_subscriptions referencing existing plan rows.
    """
    plan_specs = [
        {
            "name": "Free",
            "tier": PlanTier.FREE,
            "description": "Free tier for testing",
            "price_monthly": Decimal("0.00"),
            "price_yearly": Decimal("0.00"),
            "credits_monthly": 100,
            "credits_rollover": False,
            "max_agents": 10,
            "max_team_members": 5,
            "max_api_calls_per_month": 1000,
            "max_knowledge_bases": 10,
            "max_data_sources": 20,
            "max_custom_tools": 10,
            "max_database_connections": 5,
            "max_mcp_servers": 10,
            "max_scheduled_tasks": 10,
            "max_widgets": 10,
            "max_slack_bots": 5,
            "max_api_keys": 10,
            "features": {
                "max_conversations": 100,
                "max_messages_per_conversation": 500,
                "knowledge_bases": True,
                "custom_tools": True,
                "mcp_servers": True,
                "api_access": True,
                "webhooks": True,
                "audit_logs": True,
                "custom_domains": True,
                "sso": True,
                "advanced_analytics": True,
            },
            "is_active": True,
        },
        {
            "name": "Enterprise",
            "tier": PlanTier.ENTERPRISE,
            "description": "Enterprise tier for testing",
            "price_monthly": Decimal("299.00"),
            "price_yearly": Decimal("2990.00"),
            "credits_monthly": 50000,
            "credits_rollover": True,
            "max_agents": None,
            "max_team_members": None,
            "max_api_calls_per_month": None,
            "max_knowledge_bases": None,
            "max_data_sources": None,
            "max_custom_tools": None,
            "max_database_connections": None,
            "max_mcp_servers": None,
            "max_scheduled_tasks": None,
            "max_widgets": None,
            "max_slack_bots": None,
            "max_api_keys": None,
            "features": {
                "max_conversations": -1,
                "max_messages_per_conversation": -1,
                "knowledge_bases": True,
                "custom_tools": True,
                "mcp_servers": True,
                "api_access": True,
                "webhooks": True,
                "audit_logs": True,
                "custom_domains": True,
                "sso": True,
                "advanced_analytics": True,
                "white_label": True,
                "priority_support": True,
            },
            "is_active": True,
        },
    ]

    for spec in plan_specs:
        result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.tier == spec["tier"]))
        plan = result.scalar_one_or_none()
        if plan is not None:
            # Update existing plan with test-friendly values
            for key, val in spec.items():
                setattr(plan, key, val)
        else:
            db.add(SubscriptionPlan(**spec))

    await db.commit()


@pytest.fixture(scope="session")
def engine():
    """Create test database engine (sync)."""

    # Safety check before creating engine
    if "test" not in global_settings.db_database and global_settings.db_database != "postgres":
        # Allow 'postgres' as it might be a maintenance db, but 'synkora' is dangerous if it's prod
        pass

    test_engine = create_engine(
        global_settings.sqlalchemy_database_uri,
        echo=False,
        pool_pre_ping=True,
    )

    # Ensure clean state by aggressively dropping everything.
    # SAFETY: Both conditions must be true — APP_ENV=test alone is not enough.
    # This prevents wiping the dev database if DB_DATABASE is misconfigured.
    if global_settings.app_env == "test" and "test" in global_settings.db_database:
        with test_engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
            conn.commit()
    else:
        raise RuntimeError(
            f"Refusing to run tests: DB safety check failed.\n"
            f"  app_env={global_settings.app_env!r} (must be 'test')\n"
            f"  db_database={global_settings.db_database!r} (must contain 'test')\n"
            f"Set DB_DATABASE=synkora_test and APP_ENV=test in .env.test or as env vars."
        )

    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    # Seed system roles/permissions AND subscription plans via async engine.
    # Using asyncio.run() ensures data is committed and visible to middleware's
    # asyncpg-based sessions (plan_restriction_middleware uses get_async_session_factory()).
    asyncio.run(_seed_async_test_data())

    yield test_engine

    # Drop all tables after tests — same AND guard as setup
    if global_settings.app_env == "test" and "test" in global_settings.db_database:
        try:
            Base.metadata.drop_all(bind=test_engine)
        except Exception:
            pass
    test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_engine(engine):
    """
    Create async test database engine (per-function to match event loop scope).

    Note: Must be function-scoped because pytest-asyncio uses function-scoped
    event loops by default. Session-scoped async engines cause 'attached to
    different loop' errors when connections are reused across tests.
    """
    async_test_engine = create_async_engine(
        global_settings.sqlalchemy_async_database_uri,
        echo=False,
        poolclass=NullPool,  # Use NullPool to avoid connection reuse issues
    )
    yield async_test_engine
    # Properly dispose of the engine after each test
    await async_test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_session_factory(async_engine):
    """Create async session factory for the app."""
    return async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    """
    Create a new sync database session for each test.

    For integration tests, commits are permanent because the app uses
    separate async connections that need to see committed data.
    Each test should use unique identifiers to avoid collisions.
    """
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest_asyncio.fixture(scope="function")
async def async_db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a new async database session for each test.

    Use this for unit tests that directly test async services.
    For integration tests with TestClient, use db_session instead.
    """
    async_session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session = async_session_factory()
    try:
        yield session
    finally:
        # Handle cleanup gracefully - session may already be in an inconsistent state
        # if the test failed during a database operation
        try:
            await session.close()
        except Exception:
            # Ignore cleanup errors - the NullPool will discard the connection anyway
            pass


@pytest.fixture
def client(db_session) -> TestClient:
    """
    Create FastAPI test client.

    Uses db_session for test-level sync operations (like auth_headers setup).
    Overrides get_async_db to create a fresh async engine inside the
    TestClient's event loop, avoiding "Event loop is closed" errors.
    """
    from src.core.database import get_async_db, reset_async_engine

    # Reset engine before creating client to ensure fresh state
    reset_async_engine()

    app = create_app()

    async def override_get_async_db():
        """Create a fresh async session in the current event loop."""
        from src.core.database import get_async_session_factory

        factory = get_async_session_factory()
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_async_db] = override_get_async_db
    with TestClient(app) as test_client:
        yield test_client
    # Reset after test to clean up
    reset_async_engine()


@pytest_asyncio.fixture
async def async_client(async_db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create async FastAPI test client with async database session override."""
    from src.core.database import get_async_db, reset_async_engine

    # Reset global engine to ensure it's created in the current event loop
    # This is critical because middlewares use get_async_session_factory() directly
    reset_async_engine()

    app = create_app()

    async def override_get_async_db():
        yield async_db_session

    app.dependency_overrides[get_async_db] = override_get_async_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    finally:
        # Cancel any pending background audit tasks spawned by ActivityLogService.queue_activity()
        # so they don't keep the event loop alive after the test ends.
        from src.services.activity.activity_log_service import _audit_bg_tasks

        for task in list(_audit_bg_tasks):
            task.cancel()
        if _audit_bg_tasks:
            await asyncio.gather(*list(_audit_bg_tasks), return_exceptions=True)
        _audit_bg_tasks.clear()

        # Reset engine after test to clean up connections
        reset_async_engine()


@pytest.fixture
def tenant(db_session: Session) -> Tenant:
    """Create a test tenant (sync for use with TestClient tests)."""
    tenant = Tenant(
        name="Test Organization",
        plan=TenantPlan.FREE,
        status=TenantStatus.ACTIVE,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def account(db_session: Session) -> Account:
    """Create a test account (sync for use with TestClient tests)."""
    account = Account(
        name="Test User",
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_password",
        status=AccountStatus.ACTIVE,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def tenant_member(db_session: Session, tenant: Tenant, account: Account) -> TenantAccountJoin:
    """Create a tenant-account relationship (sync for use with TestClient tests)."""
    member = TenantAccountJoin(
        tenant_id=tenant.id,
        account_id=account.id,
        role=AccountRole.OWNER,
    )
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)
    return member


# Async fixtures for unit tests that directly test async services
@pytest_asyncio.fixture
async def async_tenant(async_db_session: AsyncSession) -> Tenant:
    """Create a test tenant (async for unit service tests)."""
    tenant = Tenant(
        name="Test Organization",
        plan=TenantPlan.FREE,
        status=TenantStatus.ACTIVE,
    )
    async_db_session.add(tenant)
    await async_db_session.flush()
    await async_db_session.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def async_account(async_db_session: AsyncSession) -> Account:
    """Create a test account (async for unit service tests)."""
    account = Account(
        name="Test User",
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_password",
        status=AccountStatus.ACTIVE,
    )
    async_db_session.add(account)
    await async_db_session.flush()
    await async_db_session.refresh(account)
    return account


@pytest_asyncio.fixture
async def async_tenant_member(
    async_db_session: AsyncSession, async_tenant: Tenant, async_account: Account
) -> TenantAccountJoin:
    """Create a tenant-account relationship (async for unit service tests)."""
    member = TenantAccountJoin(
        tenant_id=async_tenant.id,
        account_id=async_account.id,
        role=AccountRole.OWNER,
    )
    async_db_session.add(member)
    await async_db_session.flush()
    await async_db_session.refresh(member)
    return member
