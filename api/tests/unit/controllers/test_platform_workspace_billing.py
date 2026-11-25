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
    values = {"id": uuid4(), "name": "Acme", "external_billing": False, "created_at": datetime(2026, 11, 1, tzinfo=UTC)}
    values.update(fields)
    return SimpleNamespace(**values)


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


def test_only_platform_admins_can_change_billing():
    app = FastAPI()
    app.include_router(platform_settings.router, prefix="/api/v1")
    app.dependency_overrides[get_async_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_account] = lambda: MagicMock(is_platform_admin="false")
    response = TestClient(app).patch(f"/api/v1/platform-settings/workspaces/{uuid4()}", json={"external_billing": True})
    assert response.status_code == 403


def test_switching_external_billing_on_is_saved_and_logged(client, db):
    tenant = _tenant()
    db.get.return_value = tenant
    with patch.object(platform_settings.ActivityLogService, "queue_activity") as log:
        response = client.patch(f"/api/v1/platform-settings/workspaces/{tenant.id}", json={"external_billing": True})
    assert response.status_code == 200
    assert tenant.external_billing is True
    db.commit.assert_awaited_once()
    assert log.call_args.kwargs["action"] == "workspace.external_billing_changed"
    assert log.call_args.kwargs["account_id"] == ADMIN.id


def test_an_unknown_workspace_is_not_found(client, db):
    db.get.return_value = None
    response = client.patch(f"/api/v1/platform-settings/workspaces/{uuid4()}", json={"external_billing": True})
    assert response.status_code == 404


def test_without_a_search_only_externally_billed_workspaces_are_listed(client, db):
    rows = MagicMock()
    rows.scalars.return_value.all.return_value = [_tenant(external_billing=True)]
    db.execute.return_value = rows
    response = client.get("/api/v1/platform-settings/workspaces")
    assert response.status_code == 200 and response.json()[0]["external_billing"] is True
    assert "external_billing" in str(db.execute.call_args.args[0])


def test_a_search_matches_the_name_or_the_exact_id(client, db):
    rows = MagicMock()
    rows.scalars.return_value.all.return_value = []
    db.execute.return_value = rows
    workspace_id = uuid4()
    client.get("/api/v1/platform-settings/workspaces", params={"search": str(workspace_id)})
    compiled = db.execute.call_args.args[0].compile()
    assert workspace_id in compiled.params.values()
    assert "external_billing" not in str(compiled).split("WHERE", 1)[1]
