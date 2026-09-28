"""Unit tests for the audit log export endpoint."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.activity_logs import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.tenant import AccountRole


def _make_log(tenant_id: uuid.UUID, account_id: uuid.UUID | None = None) -> MagicMock:
    log = MagicMock()
    log.id = uuid.uuid4()
    log.tenant_id = tenant_id
    log.account_id = account_id or uuid.uuid4()
    log.action = "create"
    log.resource_type = "agent"
    log.resource_id = uuid.uuid4()
    log.description = "test description"
    log.ip_address = "127.0.0.1"
    log.user_agent = "pytest"
    log.status = "success"
    log.created_at = datetime(2026, 9, 28, 12, 0, 0, tzinfo=UTC)
    return log


@pytest.fixture
def mock_activity_service():
    with patch("src.controllers.activity_logs.ActivityLogService") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_team_service():
    with patch("src.services.team.team_service.TeamService") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_verify_chain():
    with patch("src.controllers.activity_logs.verify_chain", new_callable=AsyncMock) as mock:
        mock.return_value = {"valid": True, "checked": 5, "legacy_entries": 0}
        yield mock


@pytest.fixture
def app_client(mock_activity_service, mock_team_service, mock_verify_chain):
    """Return (TestClient, tenant_id, mock_account, mocks)."""
    app = FastAPI()
    app.include_router(router)

    async def mock_db():
        yield AsyncMock()

    tenant_id = uuid.uuid4()
    mock_account = MagicMock()
    mock_account.id = uuid.uuid4()

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_account] = lambda: mock_account
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    client = TestClient(app, raise_server_exceptions=False)
    return (
        client,
        tenant_id,
        mock_account,
        {
            "activity": mock_activity_service,
            "team": mock_team_service,
            "chain": mock_verify_chain,
        },
    )


class TestExportActivityLogsCSV:
    def test_csv_format_returns_correct_content_type(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = [_make_log(tenant_id)]

        response = client.get("/api/v1/activity-logs/export?format=csv")

        assert response.status_code == status.HTTP_200_OK
        assert "text/csv" in response.headers["content-type"]

    def test_csv_format_has_attachment_disposition(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = [_make_log(tenant_id)]

        response = client.get("/api/v1/activity-logs/export?format=csv")

        assert response.status_code == status.HTTP_200_OK
        disposition = response.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert ".csv" in disposition

    def test_csv_contains_header_row(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = [_make_log(tenant_id)]

        response = client.get("/api/v1/activity-logs/export?format=csv")

        assert response.status_code == status.HTTP_200_OK
        first_line = response.text.splitlines()[0]
        assert "action" in first_line
        assert "resource_type" in first_line
        assert "created_at" in first_line

    def test_csv_contains_log_data(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        log = _make_log(tenant_id)
        mock_activity.list_logs.return_value = [log]

        response = client.get("/api/v1/activity-logs/export?format=csv")

        assert response.status_code == status.HTTP_200_OK
        assert "create" in response.text
        assert "agent" in response.text

    def test_csv_chain_valid_header_present(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = [_make_log(tenant_id)]

        response = client.get("/api/v1/activity-logs/export?format=csv")

        assert response.status_code == status.HTTP_200_OK
        assert "x-audit-chain-valid" in response.headers
        assert response.headers["x-audit-chain-valid"] == "true"

    def test_csv_chain_invalid_reflected_in_header(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value
        mocks["chain"].return_value = {"valid": False, "checked": 2}

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = [_make_log(tenant_id)]

        response = client.get("/api/v1/activity-logs/export?format=csv")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["x-audit-chain-valid"] == "false"

    def test_csv_empty_logs_still_has_header_row(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = []

        response = client.get("/api/v1/activity-logs/export?format=csv")

        assert response.status_code == status.HTTP_200_OK
        lines = [line for line in response.text.splitlines() if line.strip()]
        # Only the CSV header row, no data rows
        assert len(lines) == 1
        assert "action" in lines[0]


class TestExportActivityLogsJSON:
    def test_json_format_returns_correct_content_type(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = [_make_log(tenant_id)]

        response = client.get("/api/v1/activity-logs/export?format=json")

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

    def test_json_format_has_attachment_disposition(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = [_make_log(tenant_id)]

        response = client.get("/api/v1/activity-logs/export?format=json")

        assert response.status_code == status.HTTP_200_OK
        disposition = response.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert ".json" in disposition

    def test_json_format_returns_array(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        log = _make_log(tenant_id)
        mock_activity.list_logs.return_value = [log]

        response = client.get("/api/v1/activity-logs/export?format=json")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["action"] == "create"

    def test_json_default_format(self, app_client):
        """Default format (no ?format param) should be JSON."""
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = []

        response = client.get("/api/v1/activity-logs/export")

        assert response.status_code == status.HTTP_200_OK
        assert "application/json" in response.headers["content-type"]

    def test_json_chain_valid_header_present(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = []

        response = client.get("/api/v1/activity-logs/export?format=json")

        assert response.status_code == status.HTTP_200_OK
        assert "x-audit-chain-valid" in response.headers


class TestExportActivityLogsPermissions:
    def test_non_admin_member_gets_403(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value

        mock_team.get_team_member.return_value = {"role": "member"}

        response = client.get("/api/v1/activity-logs/export?format=csv")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_member_gets_403(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value

        mock_team.get_team_member.return_value = None

        response = client.get("/api/v1/activity-logs/export?format=json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_can_export(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = []

        response = client.get("/api/v1/activity-logs/export?format=json")

        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_export(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.ADMIN.value}
        mock_activity.list_logs.return_value = []

        response = client.get("/api/v1/activity-logs/export?format=csv")

        assert response.status_code == status.HTTP_200_OK

    def test_invalid_format_param_rejected(self, app_client):
        client, tenant_id, mock_account, mocks = app_client

        response = client.get("/api/v1/activity-logs/export?format=xml")

        # FastAPI validates the Query pattern and returns 422
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestExportActivityLogsFilters:
    def test_limit_param_is_forwarded(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = []

        response = client.get("/api/v1/activity-logs/export?format=json&limit=500")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_activity.list_logs.call_args[1]
        assert call_kwargs["limit"] == 500

    def test_limit_exceeding_10000_rejected(self, app_client):
        client, tenant_id, mock_account, mocks = app_client

        response = client.get("/api/v1/activity-logs/export?limit=99999")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_filters_forwarded_to_service(self, app_client):
        client, tenant_id, mock_account, mocks = app_client
        mock_team = mocks["team"].return_value
        mock_activity = mocks["activity"].return_value

        mock_team.get_team_member.return_value = {"role": AccountRole.OWNER.value}
        mock_activity.list_logs.return_value = []

        response = client.get("/api/v1/activity-logs/export?format=json&action=login&resource_type=auth")

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_activity.list_logs.call_args[1]
        assert call_kwargs["action"] == "login"
        assert call_kwargs["resource_type"] == "auth"
