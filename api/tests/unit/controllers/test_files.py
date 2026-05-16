"""Tests for files controller."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.files import files_router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id


@pytest.fixture
def mock_s3_storage():
    with patch("src.controllers.files.S3StorageService") as mock:
        yield mock


@pytest.fixture
def mock_file_security():
    """Mock FileSecurityService to bypass magic byte validation in unit tests."""
    with patch("src.controllers.files.file_security") as mock:
        # Default to valid file
        mock.validate_file.return_value = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "file_type": "image/png",
            "mime_type": "image/png",
        }
        yield mock


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def client(mock_s3_storage, mock_db_session, mock_file_security):
    app = FastAPI()
    app.include_router(files_router, prefix="/files")

    # Mock dependencies
    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db

    # Mock tenant ID
    tenant_id = uuid.uuid4()
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id

    return TestClient(app), tenant_id, mock_db_session, mock_s3_storage


def _create_mock_agent(agent_id, agent_name, tenant_id, **kwargs):
    """Helper to create mock agent."""
    mock_agent = MagicMock()
    mock_agent.id = agent_id
    mock_agent.agent_name = agent_name
    mock_agent.tenant_id = tenant_id
    mock_agent.avatar = kwargs.get("avatar")
    mock_agent.created_at = datetime.now(UTC)
    mock_agent.updated_at = datetime.now(UTC)
    return mock_agent


class TestUploadFile:
    """Tests for file upload."""

    def test_upload_file_success(self, client):
        """Test successful file upload."""
        test_client, tenant_id, mock_db, mock_s3 = client

        # Mock S3 upload
        mock_storage = mock_s3.return_value
        mock_storage.generate_key.return_value = f"{tenant_id}/uploads/test.txt"
        mock_storage.upload_file.return_value = {
            "url": f"s3://bucket/{tenant_id}/uploads/test.txt",
            "key": f"{tenant_id}/uploads/test.txt",
        }
        mock_storage.generate_presigned_url.return_value = "https://s3.amazonaws.com/bucket/key?signed"

        # Create test file
        files = {"file": ("test.txt", b"test content", "text/plain")}

        response = test_client.post("/files/upload", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "url" in data["data"]

    def test_upload_avatar_success(self, client):
        """Test successful avatar upload."""
        test_client, tenant_id, mock_db, mock_s3 = client

        agent_id = uuid.uuid4()
        agent_name = "test-agent"

        # Mock agent lookup
        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        # Mock S3 upload
        mock_storage = mock_s3.return_value
        mock_storage.generate_key.return_value = f"{tenant_id}/agent-avatars/{agent_name}_avatar.png"
        mock_storage.upload_file.return_value = {
            "url": f"s3://bucket/{tenant_id}/agent-avatars/{agent_name}_avatar.png",
            "key": f"{tenant_id}/agent-avatars/{agent_name}_avatar.png",
        }
        mock_storage.generate_presigned_url.return_value = "https://s3.amazonaws.com/bucket/key?signed"

        # Create test image file
        files = {"file": ("avatar.png", b"PNG image content", "image/png")}
        data = {"agent_slug": agent_name, "entity_type": "agent_avatar"}

        response = test_client.post("/files/upload", files=files, data=data)

        assert response.status_code == status.HTTP_200_OK
        data_response = response.json()
        assert data_response["success"] is True
        assert "updated_entity" in data_response["data"]

    def test_upload_avatar_non_image(self, client):
        """Test avatar upload with non-image file."""
        test_client, tenant_id, mock_db, mock_s3 = client

        # Create test non-image file
        files = {"file": ("doc.pdf", b"PDF content", "application/pdf")}
        data = {"agent_slug": "test-agent", "entity_type": "agent_avatar"}

        response = test_client.post("/files/upload", files=files, data=data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_avatar_file_too_large(self, client):
        """Test avatar upload with file exceeding size limit."""
        test_client, tenant_id, mock_db, mock_s3 = client

        # Create large test file (>5MB)
        large_content = b"x" * (6 * 1024 * 1024)  # 6MB
        files = {"file": ("avatar.png", large_content, "image/png")}
        data = {"agent_slug": "test-agent", "entity_type": "agent_avatar"}

        response = test_client.post("/files/upload", files=files, data=data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_avatar_agent_not_found(self, client):
        """Test avatar upload for non-existent agent."""
        test_client, tenant_id, mock_db, mock_s3 = client

        # Mock agent not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Mock S3 upload (still succeeds)
        mock_storage = mock_s3.return_value
        mock_storage.generate_key.return_value = f"{tenant_id}/agent-avatars/nonexistent_avatar.png"
        mock_storage.upload_file.return_value = {
            "url": f"s3://bucket/{tenant_id}/agent-avatars/nonexistent_avatar.png",
            "key": f"{tenant_id}/agent-avatars/nonexistent_avatar.png",
        }
        mock_storage.generate_presigned_url.return_value = "https://s3.amazonaws.com/bucket/key?signed"

        files = {"file": ("avatar.png", b"PNG content", "image/png")}
        data = {"agent_slug": "nonexistent-agent", "entity_type": "agent_avatar"}

        response = test_client.post("/files/upload", files=files, data=data)

        # File upload succeeds but with warning
        assert response.status_code == status.HTTP_200_OK
        data_response = response.json()
        assert "warning" in data_response["data"]

    def test_upload_file_s3_error(self, client):
        """Test file upload with S3 error."""
        test_client, tenant_id, mock_db, mock_s3 = client

        # Mock S3 upload failure
        mock_storage = mock_s3.return_value
        mock_storage.generate_key.return_value = "key"
        mock_storage.upload_file.side_effect = Exception("S3 upload failed")

        files = {"file": ("test.txt", b"content", "text/plain")}

        response = test_client.post("/files/upload", files=files)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_upload_file_jpg_avatar(self, client):
        """Test avatar upload with JPG image."""
        test_client, tenant_id, mock_db, mock_s3 = client

        agent_id = uuid.uuid4()
        agent_name = "test-agent"

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_storage = mock_s3.return_value
        mock_storage.generate_key.return_value = f"{tenant_id}/agent-avatars/{agent_name}_avatar.jpg"
        mock_storage.upload_file.return_value = {
            "url": f"s3://bucket/{tenant_id}/agent-avatars/{agent_name}_avatar.jpg",
            "key": f"{tenant_id}/agent-avatars/{agent_name}_avatar.jpg",
        }
        mock_storage.generate_presigned_url.return_value = "https://presigned.url"

        files = {"file": ("avatar.jpg", b"JPG content", "image/jpeg")}
        data = {"agent_slug": agent_name, "entity_type": "agent_avatar"}

        response = test_client.post("/files/upload", files=files, data=data)

        assert response.status_code == status.HTTP_200_OK

    def test_upload_updates_agent_avatar_field(self, client):
        """Test that avatar upload updates agent's avatar field."""
        test_client, tenant_id, mock_db, mock_s3 = client

        agent_id = uuid.uuid4()
        agent_name = "test-agent"
        old_avatar = "s3://bucket/old-avatar.png"

        mock_agent = _create_mock_agent(agent_id, agent_name, tenant_id, avatar=old_avatar)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db.execute.return_value = mock_result

        mock_storage = mock_s3.return_value
        new_s3_url = f"s3://bucket/{tenant_id}/agent-avatars/{agent_name}_avatar.png"
        mock_storage.generate_key.return_value = f"{tenant_id}/agent-avatars/{agent_name}_avatar.png"
        mock_storage.upload_file.return_value = {
            "url": new_s3_url,
            "key": f"{tenant_id}/agent-avatars/{agent_name}_avatar.png",
        }
        mock_storage.generate_presigned_url.return_value = "https://presigned.url"

        files = {"file": ("avatar.png", b"PNG content", "image/png")}
        data = {"agent_slug": agent_name, "entity_type": "agent_avatar"}

        response = test_client.post("/files/upload", files=files, data=data)

        assert response.status_code == status.HTTP_200_OK
        data_response = response.json()
        assert data_response["data"]["updated_entity"]["previous_value"] == old_avatar
        assert data_response["data"]["updated_entity"]["new_value"] == new_s3_url
        mock_db.commit.assert_called()
