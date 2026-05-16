"""Tests for app store sources controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.app_store_sources import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.app_store_source import StoreType


@pytest.fixture
def mock_db_session():
    db = AsyncMock()
    db.add = MagicMock()  # add is sync, not async
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def client(mock_db_session):
    app = FastAPI()
    app.include_router(router)

    tenant_id = uuid.uuid4()

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    return TestClient(app), tenant_id, mock_db_session


def _create_mock_source(source_id, tenant_id, **kwargs):
    """Helper to create a mock app store source."""
    source = MagicMock()
    source.id = source_id
    source.tenant_id = tenant_id
    source.knowledge_base_id = kwargs.get("knowledge_base_id", 1)
    source.store_type = kwargs.get("store_type", StoreType.GOOGLE_PLAY)
    source.app_id = kwargs.get("app_id", "com.example.app")
    source.app_name = kwargs.get("app_name", "Test App")
    source.sync_frequency = kwargs.get("sync_frequency", "daily")
    source.last_sync_at = kwargs.get("last_sync_at")
    source.next_sync_at = kwargs.get("next_sync_at")
    source.min_rating = kwargs.get("min_rating", 1)
    source.languages = kwargs.get("languages", ["en"])
    source.countries = kwargs.get("countries", ["us"])
    source.status = kwargs.get("status", "active")
    source.total_reviews_collected = kwargs.get("total_reviews_collected", 0)
    source.created_at = datetime.now(UTC)
    source.updated_at = datetime.now(UTC)
    return source


class TestCreateAppStoreSource:
    """Tests for creating app store sources."""

    def test_create_google_play_source_success(self, client):
        """Test successfully creating a Google Play source."""
        test_client, tenant_id, mock_db = client

        source_id = uuid.uuid4()

        def mock_add(source):
            source.id = source_id
            source.tenant_id = tenant_id
            source.knowledge_base_id = 1
            source.store_type = StoreType.GOOGLE_PLAY
            source.app_id = "com.example.app"
            source.app_name = "My App"
            source.sync_frequency = "daily"
            source.min_rating = 3
            source.languages = ["en", "es"]
            source.countries = ["us", "mx"]
            source.status = "active"
            source.created_at = datetime.now(UTC)
            source.updated_at = datetime.now(UTC)
            source.last_sync_at = None
            source.next_sync_at = None
            source.total_reviews_collected = 0

        mock_db.add.side_effect = mock_add

        response = test_client.post(
            "/app-store-sources",
            json={
                "knowledge_base_id": 1,
                "store_type": "google_play",
                "app_id": "com.example.app",
                "app_name": "My App",
                "sync_frequency": "daily",
                "min_rating": 3,
                "languages": ["en", "es"],
                "countries": ["us", "mx"],
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_apple_store_source_success(self, client):
        """Test successfully creating an Apple App Store source."""
        test_client, tenant_id, mock_db = client

        source_id = uuid.uuid4()

        def mock_add(source):
            source.id = source_id
            source.tenant_id = tenant_id
            source.knowledge_base_id = 1
            source.store_type = StoreType.APPLE_APP_STORE
            source.app_id = "123456789"
            source.app_name = "My iOS App"
            source.sync_frequency = "daily"
            source.min_rating = 1
            source.languages = ["en"]
            source.countries = ["us"]
            source.status = "active"
            source.created_at = datetime.now(UTC)
            source.updated_at = datetime.now(UTC)
            source.last_sync_at = None
            source.next_sync_at = None
            source.total_reviews_collected = 0

        mock_db.add.side_effect = mock_add

        response = test_client.post(
            "/app-store-sources",
            json={
                "knowledge_base_id": 1,
                "store_type": "apple_app_store",
                "app_id": "123456789",
                "app_name": "My iOS App",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_source_invalid_sync_frequency(self, client):
        """Test creating source with invalid sync frequency."""
        test_client, tenant_id, mock_db = client

        response = test_client.post(
            "/app-store-sources",
            json={
                "store_type": "GOOGLE_PLAY",
                "app_id": "com.example.app",
                "app_name": "My App",
                "sync_frequency": "hourly",  # Invalid
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestListAppStoreSources:
    """Tests for listing app store sources."""

    def test_list_sources_success(self, client):
        """Test successfully listing app store sources."""
        test_client, tenant_id, mock_db = client

        source = _create_mock_source(uuid.uuid4(), tenant_id)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [source]
        mock_db.execute.return_value = mock_result

        response = test_client.get("/app-store-sources")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_list_sources_empty(self, client):
        """Test listing when no sources exist."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        response = test_client.get("/app-store-sources")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 0


class TestGetAppStoreSource:
    """Tests for getting a specific app store source."""

    def test_get_source_success(self, client):
        """Test successfully getting an app store source."""
        test_client, tenant_id, mock_db = client

        source_id = uuid.uuid4()
        source = _create_mock_source(source_id, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source
        mock_db.execute.return_value = mock_result

        response = test_client.get(f"/app-store-sources/{source_id}")

        assert response.status_code == status.HTTP_200_OK

    def test_get_source_not_found(self, client):
        """Test getting non-existent source."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.get(f"/app-store-sources/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateAppStoreSource:
    """Tests for updating app store sources."""

    def test_update_source_success(self, client):
        """Test successfully updating an app store source."""
        test_client, tenant_id, mock_db = client

        source_id = uuid.uuid4()
        source = _create_mock_source(source_id, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source
        mock_db.execute.return_value = mock_result

        response = test_client.patch(
            f"/app-store-sources/{source_id}", json={"app_name": "Updated App Name", "min_rating": 4}
        )

        assert response.status_code == status.HTTP_200_OK

    def test_update_source_not_found(self, client):
        """Test updating non-existent source."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.patch(f"/app-store-sources/{uuid.uuid4()}", json={"app_name": "Updated"})

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteAppStoreSource:
    """Tests for deleting app store sources."""

    def test_delete_source_success(self, client):
        """Test successfully deleting an app store source."""
        test_client, tenant_id, mock_db = client

        source_id = uuid.uuid4()
        source = _create_mock_source(source_id, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source
        mock_db.execute.return_value = mock_result

        response = test_client.delete(f"/app-store-sources/{source_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_source_not_found(self, client):
        """Test deleting non-existent source."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.delete(f"/app-store-sources/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSyncReviews:
    """Tests for syncing reviews."""

    def test_sync_reviews_success(self, client):
        """Test successfully triggering review sync."""
        test_client, tenant_id, mock_db = client

        source_id = uuid.uuid4()
        source = _create_mock_source(source_id, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = source
        mock_db.execute.return_value = mock_result

        with (
            patch("src.controllers.app_store_sources.get_connector"),
            patch("src.controllers.app_store_sources.ReviewSyncService") as mock_sync,
        ):
            mock_sync_instance = mock_sync.return_value
            mock_sync_instance.sync_source = AsyncMock(return_value={"synced": 10})

            response = test_client.post(f"/app-store-sources/{source_id}/sync")

        assert response.status_code == status.HTTP_200_OK

    def test_sync_reviews_source_not_found(self, client):
        """Test syncing reviews for non-existent source."""
        test_client, tenant_id, mock_db = client

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = test_client.post(f"/app-store-sources/{uuid.uuid4()}/sync")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestListReviews:
    """Tests for listing reviews."""

    def test_list_reviews_success(self, client):
        """Test successfully listing reviews."""
        test_client, tenant_id, mock_db = client

        source_id = uuid.uuid4()
        source = _create_mock_source(source_id, tenant_id)

        mock_review = MagicMock()
        mock_review.id = uuid.uuid4()
        mock_review.review_id = "review_123"
        mock_review.author_name = "Test User"
        mock_review.rating = 5
        mock_review.title = "Great app!"
        mock_review.content = "Really love this app"
        mock_review.language = "en"
        mock_review.country = "us"
        mock_review.app_version = "1.0.0"
        mock_review.review_date = datetime.now(UTC)
        mock_review.sentiment = "positive"
        mock_review.sentiment_score = 0.9
        mock_review.topics = ["usability"]
        mock_review.issues = []
        mock_review.features_mentioned = ["feature1"]

        # First execute for source check
        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = source
        # Second execute for reviews
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = [mock_review]

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        response = test_client.get(f"/app-store-sources/{source_id}/reviews")

        assert response.status_code == status.HTTP_200_OK

    def test_list_reviews_with_filters(self, client):
        """Test listing reviews with rating and sentiment filters."""
        test_client, tenant_id, mock_db = client

        source_id = uuid.uuid4()
        source = _create_mock_source(source_id, tenant_id)

        mock_result1 = MagicMock()
        mock_result1.scalar_one_or_none.return_value = source
        mock_result2 = MagicMock()
        mock_result2.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [mock_result1, mock_result2]

        response = test_client.get(f"/app-store-sources/{source_id}/reviews?min_rating=4&sentiment=positive")

        assert response.status_code == status.HTTP_200_OK
