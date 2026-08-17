"""Tests for data sources controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.data_sources import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.data_source import DataSourceStatus, DataSourceType


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def client(mock_db_session):
    app = FastAPI()
    app.include_router(router)

    # Mock dependencies - use async generator for db
    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db

    # Mock tenant ID
    tenant_id = uuid.uuid4()
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    # Mock current account (required for create/update endpoints)
    mock_account = MagicMock()
    mock_account.id = uuid.uuid4()
    mock_account.email = "test@example.com"
    mock_account.tenant_id = tenant_id
    app.dependency_overrides[get_current_account] = lambda: mock_account

    return TestClient(app), tenant_id, mock_db_session


def _create_mock_data_source(ds_id, tenant_id, kb_id, **kwargs):
    """Helper to create mock data source."""
    mock_ds = MagicMock()
    mock_ds.id = ds_id
    mock_ds.tenant_id = tenant_id
    mock_ds.knowledge_base_id = kb_id
    mock_ds.name = kwargs.get("name", "Test Data Source")
    mock_ds.type = kwargs.get("type", DataSourceType.SLACK)
    mock_ds.config = kwargs.get("config", {})
    mock_ds.status = kwargs.get("status", DataSourceStatus.ACTIVE)
    mock_ds.sync_enabled = kwargs.get("sync_enabled", True)
    mock_ds.last_sync_at = kwargs.get("last_sync_at")
    mock_ds.last_error = kwargs.get("last_error")
    mock_ds.total_documents = kwargs.get("total_documents", 0)
    mock_ds.created_at = datetime.now(UTC)
    mock_ds.updated_at = datetime.now(UTC)
    # Explicitly set oauth_app to None to avoid MagicMock auto-creation
    # which causes Pydantic validation errors for OAuthAppInfo
    mock_ds.oauth_app = kwargs.get("oauth_app")
    return mock_ds


def _create_mock_knowledge_base(kb_id, tenant_id):
    """Helper to create mock knowledge base."""
    mock_kb = MagicMock()
    mock_kb.id = kb_id
    mock_kb.tenant_id = tenant_id
    mock_kb.name = "Test Knowledge Base"
    return mock_kb


class TestCreateDataSource:
    """Tests for creating data sources."""

    def test_create_data_source_success(self, client):
        """Test successful data source creation."""
        test_client, tenant_id, mock_db = client

        kb_id = 1
        ds_id = 1

        # Mock knowledge base exists
        mock_kb = _create_mock_knowledge_base(kb_id, tenant_id)
        # Mock re-fetched data source returned after commit
        mock_ds = _create_mock_data_source(ds_id, tenant_id, kb_id, name="Test Slack Source")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        mock_result.scalar_one.return_value = mock_ds
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.add = MagicMock()

        response = test_client.post(
            "/data-sources",
            json={
                "name": "Test Slack Source",
                "type": "SLACK",
                "knowledge_base_id": kb_id,
                "config": {"channels": ["general"]},
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test Slack Source"

    def test_create_data_source_kb_not_found(self, client):
        """Test creating data source with non-existent knowledge base."""
        test_client, tenant_id, mock_db = client

        # Mock knowledge base not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.post(
            "/data-sources", json={"name": "Test Source", "type": "SLACK", "knowledge_base_id": 999, "config": {}}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_data_source_with_slack_bot_id(self, client):
        """Test creating a Slack data source that reuses an existing SlackBot's credentials."""
        test_client, tenant_id, mock_db = client

        kb_id = 1
        ds_id = 1
        slack_bot_id = str(uuid.uuid4())

        mock_kb = _create_mock_knowledge_base(kb_id, tenant_id)
        mock_bot = MagicMock()
        mock_bot.id = slack_bot_id
        mock_bot.tenant_id = tenant_id
        mock_ds = _create_mock_data_source(ds_id, tenant_id, kb_id, name="Reused Bot Source")
        mock_ds.slack_bot_id = slack_bot_id

        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            elif call_count[0] == 2:
                mock_result.scalar_one_or_none.return_value = mock_bot
            else:
                mock_result.scalar_one.return_value = mock_ds
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)
        mock_db.add = MagicMock()

        response = test_client.post(
            "/data-sources",
            json={
                "name": "Reused Bot Source",
                "type": "SLACK",
                "knowledge_base_id": kb_id,
                "config": {"channels": ["general"]},
                "slack_bot_id": slack_bot_id,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_data_source_duplicate_slack_bot_rejected(self, client):
        """Test that connecting the same Slack bot to a KB it's already linked to is rejected."""
        test_client, tenant_id, mock_db = client

        kb_id = 1
        slack_bot_id = str(uuid.uuid4())

        mock_kb = _create_mock_knowledge_base(kb_id, tenant_id)
        mock_bot = MagicMock()
        mock_bot.id = slack_bot_id
        mock_bot.tenant_id = tenant_id

        existing_ds = _create_mock_data_source(1, tenant_id, kb_id, name="Existing Slack Source")
        existing_ds.slack_bot_id = uuid.UUID(slack_bot_id)
        existing_ds.oauth_app_id = None

        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            elif call_count[0] == 2:
                mock_result.scalar_one_or_none.return_value = mock_bot
            else:
                mock_result.scalars.return_value.all.return_value = [existing_ds]
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        response = test_client.post(
            "/data-sources",
            json={
                "name": "Duplicate Slack Source",
                "type": "SLACK",
                "knowledge_base_id": kb_id,
                "config": {},
                "slack_bot_id": slack_bot_id,
            },
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already connected" in response.json()["detail"]

    def test_create_data_source_slack_bot_not_found(self, client):
        """Test creating a data source with a non-existent slack_bot_id."""
        test_client, tenant_id, mock_db = client

        kb_id = 1
        mock_kb = _create_mock_knowledge_base(kb_id, tenant_id)

        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_result = MagicMock()
            if call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_kb
            else:
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        response = test_client.post(
            "/data-sources",
            json={
                "name": "Test Source",
                "type": "SLACK",
                "knowledge_base_id": kb_id,
                "config": {},
                "slack_bot_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestListDataSources:
    """Tests for listing data sources."""

    def test_list_data_sources_success(self, client):
        """Test listing all data sources."""
        test_client, tenant_id, mock_db = client

        mock_ds = _create_mock_data_source(1, tenant_id, 1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_ds]
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/data-sources")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_list_data_sources_filter_by_kb(self, client):
        """Test listing data sources filtered by knowledge base."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/data-sources?knowledge_base_id=1")

        assert response.status_code == status.HTTP_200_OK


class TestGetDataSource:
    """Tests for getting a specific data source."""

    def test_get_data_source_success(self, client):
        """Test getting a specific data source."""
        test_client, tenant_id, mock_db = client

        mock_ds = _create_mock_data_source(1, tenant_id, 1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ds
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/data-sources/1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == 1

    def test_get_data_source_not_found(self, client):
        """Test getting non-existent data source."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/data-sources/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateDataSource:
    """Tests for updating data sources."""

    def test_update_data_source_success(self, client):
        """Test updating a data source."""
        test_client, tenant_id, mock_db = client

        mock_ds = _create_mock_data_source(1, tenant_id, 1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ds
        mock_result.scalar_one.return_value = mock_ds
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.put(
            "/data-sources/1", json={"name": "Updated Name", "config": {"channels": ["general", "random"]}}
        )

        assert response.status_code == status.HTTP_200_OK
        mock_db.commit.assert_called()

    def test_update_data_source_not_found(self, client):
        """Test updating non-existent data source."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.put("/data-sources/999", json={"name": "Updated"})

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteDataSource:
    """Tests for deleting data sources."""

    def test_delete_data_source_success(self, client):
        """Test deleting a data source."""
        test_client, tenant_id, mock_db = client

        mock_ds = _create_mock_data_source(1, tenant_id, 1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ds
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.delete("/data-sources/1")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_db.delete.assert_called_once()

    def test_delete_data_source_not_found(self, client):
        """Test deleting non-existent data source."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.delete("/data-sources/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestTestConnection:
    """Tests for testing data source connections."""

    def test_test_connection_success(self, client):
        """Test successful connection test."""
        test_client, tenant_id, mock_db = client

        mock_ds = _create_mock_data_source(1, tenant_id, 1, type=DataSourceType.SLACK)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ds
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("src.controllers.data_sources.get_connector") as mock_get_connector:
            mock_connector = MagicMock()
            mock_connector.test_connection = AsyncMock(
                return_value={"success": True, "message": "Connection successful", "details": {}}
            )
            mock_get_connector.return_value = mock_connector

            response = test_client.post("/data-sources/1/test-connection")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True

    def test_test_connection_failed(self, client):
        """Test failed connection test."""
        test_client, tenant_id, mock_db = client

        mock_ds = _create_mock_data_source(1, tenant_id, 1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ds
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch("src.controllers.data_sources.get_connector") as mock_get_connector:
            mock_connector = MagicMock()
            mock_connector.test_connection = AsyncMock(
                return_value={
                    "success": False,
                    "message": "Connection failed",
                    "details": {"error": "Invalid credentials"},
                }
            )
            mock_get_connector.return_value = mock_connector

            response = test_client.post("/data-sources/1/test-connection")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is False


class TestTriggerSync:
    """Tests for triggering data source sync."""

    def test_trigger_sync_success(self, client):
        """Test triggering sync successfully."""
        test_client, tenant_id, mock_db = client

        mock_ds = _create_mock_data_source(1, tenant_id, 1, status=DataSourceStatus.ACTIVE)

        # Track execute calls to return appropriate responses
        execute_call_count = [0]

        def execute_side_effect(*args, **kwargs):
            execute_call_count[0] += 1
            mock_result = MagicMock()
            if execute_call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_ds  # First query returns data source
            else:
                mock_result.scalar_one_or_none.return_value = (
                    None  # Subsequent queries return None (no in-progress sync)
                )
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        # Mock adding sync job
        def mock_add(sync_job):
            sync_job.id = 1

        mock_db.add = MagicMock(side_effect=mock_add)
        mock_db.refresh = AsyncMock()

        response = test_client.post("/data-sources/1/sync")

        assert response.status_code == status.HTTP_202_ACCEPTED

    def test_trigger_sync_inactive_source(self, client):
        """Test triggering sync on inactive data source."""
        test_client, tenant_id, mock_db = client

        mock_ds = _create_mock_data_source(1, tenant_id, 1, status=DataSourceStatus.INACTIVE)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ds
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.post("/data-sources/1/sync")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestGetSyncStatus:
    """Tests for getting sync status."""

    def test_get_sync_status_success(self, client):
        """Test getting sync status."""
        test_client, tenant_id, mock_db = client

        mock_ds = _create_mock_data_source(
            1, tenant_id, 1, status=DataSourceStatus.ACTIVE, total_documents=100, last_sync_at=datetime.now(UTC)
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_ds
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = test_client.get("/data-sources/1/sync-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_documents"] == 100


class TestGetSyncHistory:
    """Tests for getting sync history."""

    def test_get_sync_history_success(self, client):
        """Test getting sync history."""
        test_client, tenant_id, mock_db = client

        mock_ds = _create_mock_data_source(1, tenant_id, 1)

        # Mock sync jobs
        mock_sync_job = MagicMock()
        mock_sync_job.id = 1
        mock_sync_job.started_at = datetime.now(UTC)
        mock_sync_job.completed_at = datetime.now(UTC)
        mock_sync_job.status = MagicMock(value="completed")
        mock_sync_job.documents_processed = 50
        mock_sync_job.documents_added = 40
        mock_sync_job.documents_updated = 10
        mock_sync_job.documents_deleted = 0
        mock_sync_job.documents_failed = 0
        mock_sync_job.error_message = None

        # First call returns data source, second call for sync jobs
        execute_call_count = [0]

        def execute_side_effect(*args, **kwargs):
            execute_call_count[0] += 1
            mock_result = MagicMock()
            if execute_call_count[0] == 1:
                mock_result.scalar_one_or_none.return_value = mock_ds
            else:
                mock_result.scalars.return_value.all.return_value = [mock_sync_job]
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        response = test_client.get("/data-sources/1/sync-history")

        assert response.status_code == status.HTTP_200_OK
