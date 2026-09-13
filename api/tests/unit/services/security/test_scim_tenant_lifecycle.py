"""Real ORM/database tests: SCIM authority must stop at the tenant boundary."""

from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from src.models.scim_membership import SCIMMembership
from src.models.tenant import Account, AccountRole, AccountStatus, TenantAccountJoin
from src.services import scim_service as service


@pytest.fixture
def database():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    # Clone only the needed tables; keep real ORM mapping and SQL execution.
    for model in (Account, TenantAccountJoin, SCIMMembership):
        table = model.__table__.to_metadata(metadata)
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = sa.JSON()
        for constraint in list(table.foreign_key_constraints):
            table.constraints.remove(constraint)
        for column in table.columns:
            column.foreign_keys.clear()
        table.foreign_keys.clear()
    metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:

        class Adapter:
            def add(self, obj):
                session.add(obj)

            async def execute(self, stmt):
                return session.execute(stmt)

            async def delete(self, obj):
                session.delete(obj)

            async def commit(self):
                session.commit()

            async def flush(self):
                session.flush()

            async def refresh(self, obj):
                session.refresh(obj)

        yield Adapter(), session
    engine.dispose()


def seed(session):
    a, b = uuid4(), uuid4()
    user = Account(name="Original", email="original@example.invalid", status=AccountStatus.ACTIVE, auth_version=3)
    session.add(user)
    session.flush()
    for tenant, role in ((a, AccountRole.NORMAL), (b, AccountRole.OWNER)):
        session.add(TenantAccountJoin(tenant_id=tenant, account_id=user.id, role=role))
    session.commit()
    return a, b, user


@pytest.mark.asyncio
async def test_existing_foreign_account_cannot_be_linked(database):
    db, session = database
    a, b, user = seed(session)
    with pytest.raises(ValueError):
        await service.create_user(db, uuid4(), {"userName": user.email})
    assert session.query(TenantAccountJoin).count() == 2
    assert user.email == "original@example.invalid" and user.status == AccountStatus.ACTIVE


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["put", "patch", "delete"])
async def test_disable_and_delete_only_affect_current_tenant(database, operation):
    db, session = database
    a, b, user = seed(session)
    if operation == "put":
        await service.update_user(
            db, a, str(user.id), {"userName": user.email, "active": False, "displayName": "Local name"}
        )
    elif operation == "patch":
        await service.patch_user(db, a, str(user.id), [{"op": "replace", "path": "active", "value": False}])
    else:
        assert await service.delete_user(db, a, str(user.id))
    assert session.query(TenantAccountJoin).filter_by(tenant_id=a).count() == 0
    assert session.query(TenantAccountJoin).filter_by(tenant_id=b).one().role == AccountRole.OWNER
    assert user.status == AccountStatus.ACTIVE and user.name == "Original" and user.auth_version == 3
    assert (await service.get_user(db, b, str(user.id)))["active"] is True
    if operation == "delete":
        assert await service.get_user(db, a, str(user.id)) is None
    else:
        resource = await service.get_user(db, a, str(user.id))
        assert resource["active"] is False
        assert (await service.list_users(db, a))["totalResults"] == 1
        await service.patch_user(db, a, str(user.id), [{"op": "replace", "path": "active", "value": True}])
        assert (await service.get_user(db, a, str(user.id)))["active"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operations",
    [
        [{"op": "replace", "path": "userName", "value": "attacker@example.invalid"}],
        [{"op": "replace", "value": {"active": False, "userName": "attacker@example.invalid"}}],
        [{"op": "add", "value": {"userName": "attacker@example.invalid"}}],
        [
            {"op": "replace", "path": "active", "value": False},
            {"op": "replace", "path": "userName", "value": "attacker@example.invalid"},
        ],
    ],
)
async def test_global_identity_mutation_and_partial_batches_are_rejected(database, operations):
    db, session = database
    a, b, user = seed(session)
    with pytest.raises(ValueError):
        await service.patch_user(db, a, str(user.id), operations)
    session.commit()  # Even a subsequent commit cannot persist a partial rejected batch.
    assert user.email == "original@example.invalid" and user.status == AccountStatus.ACTIVE
    assert session.query(TenantAccountJoin).count() == 2


@pytest.mark.asyncio
async def test_create_inactive_then_activate_and_reject_foreign_operations(database):
    db, session = database
    a, b = uuid4(), uuid4()
    resource = await service.create_user(db, a, {"userName": "new@example.invalid", "active": False})
    assert resource["active"] is False
    assert await service.get_user(db, b, resource["id"]) is None
    assert await service.update_user(db, b, resource["id"], {"active": True}) is None
    assert await service.patch_user(db, b, resource["id"], [{"op": "replace", "path": "active", "value": True}]) is None
    assert await service.delete_user(db, b, resource["id"]) is False
    updated = await service.update_user(
        db, a, resource["id"], {**resource, "active": True, "displayName": "Tenant name"}
    )
    assert updated["active"] is True
    assert session.query(Account).one().name == "new"


@pytest.mark.asyncio
async def test_reactivation_preserves_membership_permissions(database):
    db, session = database
    a, b, user = seed(session)
    membership = session.query(TenantAccountJoin).filter_by(tenant_id=a).one()
    role_id = uuid4()
    membership.role_id = role_id
    membership.custom_permissions = '{"restricted":true}'
    session.commit()
    await service.patch_user(db, a, str(user.id), [{"op": "replace", "path": "active", "value": False}])
    from src.services.auth_service import AuthService

    assert not await AuthService.check_permission(db, user.id, a, AccountRole.NORMAL)
    assert await AuthService.check_permission(db, user.id, b, AccountRole.OWNER)
    await service.patch_user(db, a, str(user.id), [{"op": "replace", "path": "active", "value": True}])
    restored = session.query(TenantAccountJoin).filter_by(tenant_id=a).one()
    assert restored.role_id == role_id and restored.custom_permissions == '{"restricted":true}'


@pytest.mark.asyncio
async def test_put_rejects_email_mutation(database):
    db, session = database
    a, b, user = seed(session)
    with pytest.raises(ValueError):
        await service.update_user(db, a, str(user.id), {"userName": "attacker@example.invalid", "active": False})
    session.commit()
    assert user.email == "original@example.invalid"
    assert session.query(TenantAccountJoin).count() == 2


def test_scim_migration_roundtrip():
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from alembic.script import ScriptDirectory

    directory = Path(__file__).resolve().parents[4] / "migrations"
    spec = importlib.util.spec_from_file_location(
        "scim_migration", directory / "versions/20260909_0003_scim_memberships.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert "scim_memberships" in sa.inspect(connection).get_table_names()
            assert {"tenant_id", "account_id", "membership_attributes"} <= {
                c["name"] for c in sa.inspect(connection).get_columns("scim_memberships")
            }
            module.downgrade()
            assert "scim_memberships" not in sa.inspect(connection).get_table_names()
    assert len(ScriptDirectory(str(directory)).get_heads()) == 1
    assert "20260909_0003" in {r.revision for r in ScriptDirectory(str(directory)).walk_revisions()}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,payload",
    [
        ("PUT", {"userName": "attacker@example.invalid", "active": False}),
        ("PATCH", {"Operations": [{"op": "replace", "path": "userName", "value": "attacker@example.invalid"}]}),
    ],
)
async def test_http_identity_mutation_returns_400(database, method, payload):
    import httpx
    from fastapi import FastAPI

    from src.controllers.scim import get_scim_tenant, scim_router
    from src.core.database import get_async_db

    db, session = database
    a, b, user = seed(session)
    app = FastAPI()
    app.include_router(scim_router)
    app.dependency_overrides[get_scim_tenant] = lambda: a
    app.dependency_overrides[get_async_db] = lambda: db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request(method, f"/scim/v2/Users/{user.id}", json=payload)
    assert response.status_code == 400
    assert user.email == "original@example.invalid"
    assert session.query(TenantAccountJoin).count() == 2
