from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.controllers import platform_settings
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, require_platform_admin

ADMIN = MagicMock(id=uuid4())


def _tenant(**fields):
    values = {
        "id": uuid4(),
        "name": "Acme",
        "status": "ACTIVE",
        "external_billing": False,
        "created_at": datetime(2026, 11, 1, tzinfo=UTC),
    }
    values.update(fields)
    return SimpleNamespace(**values)


def _owner(**fields):
    values = {
        "id": uuid4(),
        "name": "Ana",
        "email": "ana@acme.test",
        "status": "INACTIVE",
        "email_verification_token": "hashed-token",
    }
    values.update(fields)
    return SimpleNamespace(**values)


def _rows(scalars=None, pairs=None, first=None):
    """A result of db.execute: .scalars().all(), .all() (tenant id, owner pairs) or .first()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = scalars or []
    result.all.return_value = pairs or []
    result.first.return_value = first
    return result


@pytest.fixture
def db():
    session = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(platform_settings.router, prefix="/api/v1")
    app.dependency_overrides[get_async_db] = lambda: db
    app.dependency_overrides[get_current_account] = lambda: ADMIN
    app.dependency_overrides[require_platform_admin] = lambda: None
    return TestClient(app)


@pytest.mark.parametrize(
    ("path", "body"),
    [("", {"external_billing": True}), ("", {"status": "SUSPENDED"}), ("/owner", {"status": "ACTIVE"})],
)
def test_only_platform_admins_can_change_workspaces_or_owners(path, body):
    app = FastAPI()
    app.include_router(platform_settings.router, prefix="/api/v1")
    app.dependency_overrides[get_async_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_account] = lambda: MagicMock(is_platform_admin="false")
    response = TestClient(app).patch(f"/api/v1/platform-settings/workspaces/{uuid4()}{path}", json=body)
    assert response.status_code == 403


def test_switching_external_billing_on_is_saved_and_logged(client, db):
    tenant = _tenant()
    db.get.return_value = tenant
    db.execute.return_value = _rows()
    with patch.object(platform_settings.ActivityLogService, "queue_activity") as log:
        response = client.patch(f"/api/v1/platform-settings/workspaces/{tenant.id}", json={"external_billing": True})
    assert response.status_code == 200
    assert tenant.external_billing is True
    db.commit.assert_awaited_once()
    assert log.call_args.kwargs["action"] == "workspace.updated_by_platform_admin"
    assert log.call_args.kwargs["details"] == {"external_billing": True}
    assert log.call_args.kwargs["account_id"] == ADMIN.id


def test_a_workspace_can_be_suspended_and_shows_its_owner(client, db):
    tenant, owner = _tenant(), _owner(status="ACTIVE")
    db.get.return_value = tenant
    db.execute.side_effect = [_rows(first=None), _rows(pairs=[(tenant.id, owner)])]  # not the admin's own; owner
    with patch.object(platform_settings.ActivityLogService, "queue_activity"):
        response = client.patch(f"/api/v1/platform-settings/workspaces/{tenant.id}", json={"status": "SUSPENDED"})
    assert response.status_code == 200
    assert tenant.status == "SUSPENDED"
    assert response.json()["owner"]["email"] == "ana@acme.test"


def test_an_admin_cannot_suspend_their_own_workspace(client, db):
    tenant = _tenant()
    db.get.return_value = tenant
    db.execute.return_value = _rows(first=(uuid4(),))  # the admin is a member
    response = client.patch(f"/api/v1/platform-settings/workspaces/{tenant.id}", json={"status": "SUSPENDED"})
    assert response.status_code == 400
    assert tenant.status == "ACTIVE"
    db.commit.assert_not_awaited()


def test_nothing_to_change_is_refused(client, db):
    db.get.return_value = _tenant()
    response = client.patch(f"/api/v1/platform-settings/workspaces/{uuid4()}", json={})
    assert response.status_code == 400


def test_only_active_or_suspended_can_be_set(client, db):
    db.get.return_value = _tenant()
    response = client.patch(f"/api/v1/platform-settings/workspaces/{uuid4()}", json={"status": "DELETED"})
    assert response.status_code == 422


def test_an_unknown_workspace_is_not_found(client, db):
    db.get.return_value = None
    response = client.patch(f"/api/v1/platform-settings/workspaces/{uuid4()}", json={"external_billing": True})
    assert response.status_code == 404


def test_activating_an_unverified_owner_verifies_them(client, db):
    tenant, owner = _tenant(), _owner()
    db.get.return_value = tenant
    db.execute.return_value = _rows(pairs=[(tenant.id, owner)])
    with patch.object(platform_settings.ActivityLogService, "queue_activity") as log:
        response = client.patch(f"/api/v1/platform-settings/workspaces/{tenant.id}/owner", json={"status": "ACTIVE"})
    assert response.status_code == 200
    assert owner.status == "ACTIVE"
    assert owner.email_verification_token is None
    assert response.json()["owner"]["status"] == "ACTIVE"
    assert log.call_args.kwargs["resource_id"] == owner.id


def test_suspending_an_owner_keeps_their_verification_as_it_was(client, db):
    tenant, owner = _tenant(), _owner(status="ACTIVE", email_verification_token=None)
    db.get.return_value = tenant
    db.execute.return_value = _rows(pairs=[(tenant.id, owner)])
    with patch.object(platform_settings.ActivityLogService, "queue_activity"):
        response = client.patch(f"/api/v1/platform-settings/workspaces/{tenant.id}/owner", json={"status": "SUSPENDED"})
    assert response.status_code == 200
    assert owner.status == "SUSPENDED"


def test_an_admin_cannot_change_their_own_account(client, db):
    tenant, owner = _tenant(), _owner(id=ADMIN.id, status="ACTIVE")
    db.get.return_value = tenant
    db.execute.return_value = _rows(pairs=[(tenant.id, owner)])
    response = client.patch(f"/api/v1/platform-settings/workspaces/{tenant.id}/owner", json={"status": "SUSPENDED"})
    assert response.status_code == 400
    assert owner.status == "ACTIVE"


def test_a_workspace_without_an_owner_has_nothing_to_activate(client, db):
    db.get.return_value = _tenant()
    db.execute.return_value = _rows()
    response = client.patch(f"/api/v1/platform-settings/workspaces/{uuid4()}/owner", json={"status": "ACTIVE"})
    assert response.status_code == 404


def test_without_a_search_only_externally_billed_workspaces_are_listed(client, db):
    tenant = _tenant(external_billing=True)
    db.execute.side_effect = [_rows(scalars=[tenant]), _rows(pairs=[(tenant.id, _owner())])]
    response = client.get("/api/v1/platform-settings/workspaces")
    assert response.status_code == 200
    body = response.json()[0]
    assert body["external_billing"] is True and body["owner"]["status"] == "INACTIVE"
    assert "external_billing" in str(db.execute.call_args_list[0].args[0])


def test_a_search_matches_the_name_the_exact_id_or_the_owners_email(client, db):
    db.execute.return_value = _rows()
    workspace_id = uuid4()
    client.get("/api/v1/platform-settings/workspaces", params={"search": str(workspace_id)})
    compiled = db.execute.call_args.args[0].compile()
    where = str(compiled).split("WHERE", 1)[1]
    assert workspace_id in compiled.params.values()
    assert "accounts.email" in where
    assert "external_billing" not in where
