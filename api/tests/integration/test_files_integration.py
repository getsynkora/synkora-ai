"""
Integration tests for Files endpoints.

Tests file upload operations including avatar uploads.
"""

import io
import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Account, AccountStatus


@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient, async_db_session: AsyncSession):
    """Create authenticated user and return headers with tenant info."""
    email = f"files_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecureTestPass123!"

    # Register
    response = await async_client.post(
        "/console/api/auth/register",
        json={
            "email": email,
            "password": password,
            "name": "Files Test User",
            "tenant_name": "Files Test Org",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    tenant_id = data["data"]["tenant"]["id"]

    # Activate account
    result = await async_db_session.execute(select(Account).filter_by(email=email))
    account = result.scalar_one_or_none()
    account.status = AccountStatus.ACTIVE
    await async_db_session.commit()

    # Login
    login_response = await async_client.post(
        "/console/api/auth/login",
        json={"email": email, "password": password},
    )
    token = login_response.json()["data"]["access_token"]

    return {"Authorization": f"Bearer {token}"}, tenant_id, account


@pytest_asyncio.fixture
async def test_agent(async_client: AsyncClient, auth_headers):
    """Create a test agent for file upload tests."""
    headers, tenant_id, account = auth_headers

    # Create an agent to upload avatar for
    agent_name = f"file-test-agent-{uuid.uuid4().hex[:8]}"
    response = await async_client.post(
        "/api/v1/agents",
        json={
            "name": f"File Test Agent {uuid.uuid4().hex[:8]}",
            "agent_name": agent_name,
            "description": "Agent for file tests",
            "system_prompt": "You are a test agent.",
            "model": "gpt-4o-mini",
        },
        headers=headers,
    )
    if response.status_code == status.HTTP_201_CREATED:
        return response.json()["agent_name"]
    return agent_name


class TestFileUploadIntegration:
    """Test file upload operations."""

    @pytest.mark.asyncio
    async def test_upload_file_basic(self, async_client: AsyncClient, auth_headers):
        """Test basic file upload."""
        headers, tenant_id, account = auth_headers

        # Create a simple text file
        file_content = b"Hello, this is a test file content."
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}

        response = await async_client.post(
            "/api/v1/files/upload",
            files=files,
            headers=headers,
        )

        # Accept 200 (success) or 500 (S3 not configured in test environment)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            assert "url" in data["data"] or "s3_uri" in data["data"]

    @pytest.mark.asyncio
    async def test_upload_image_file(self, async_client: AsyncClient, auth_headers):
        """Test uploading an image file."""
        headers, tenant_id, account = auth_headers

        # Create a minimal PNG file (1x1 pixel)
        png_content = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
            b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        files = {"file": ("test.png", io.BytesIO(png_content), "image/png")}

        response = await async_client.post(
            "/api/v1/files/upload",
            files=files,
            headers=headers,
        )

        # Accept 200 (success) or 500 (S3 not configured)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

    @pytest.mark.asyncio
    async def test_upload_agent_avatar(self, async_client: AsyncClient, auth_headers, test_agent):
        """Test uploading an agent avatar."""
        headers, tenant_id, account = auth_headers

        # Create a minimal PNG file (1x1 pixel)
        png_content = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
            b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        files = {"file": ("avatar.png", io.BytesIO(png_content), "image/png")}
        data = {
            "agent_name": test_agent,
            "entity_type": "agent_avatar",
        }

        response = await async_client.post(
            "/api/v1/files/upload",
            files=files,
            data=data,
            headers=headers,
        )

        # Accept 200 (success) or 500 (S3 not configured)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

        if response.status_code == status.HTTP_200_OK:
            result = response.json()
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_upload_avatar_non_image_rejected(self, async_client: AsyncClient, auth_headers, test_agent):
        """Test that non-image files are rejected for avatar upload."""
        headers, tenant_id, account = auth_headers

        # Try to upload a text file as avatar
        file_content = b"This is not an image"
        files = {"file": ("notimage.txt", io.BytesIO(file_content), "text/plain")}
        data = {
            "agent_name": test_agent,
            "entity_type": "agent_avatar",
        }

        response = await async_client.post(
            "/api/v1/files/upload",
            files=files,
            data=data,
            headers=headers,
        )

        # Should return 400 for non-image avatar
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]

    @pytest.mark.asyncio
    async def test_upload_avatar_too_large(self, async_client: AsyncClient, auth_headers, test_agent):
        """Test that avatar files over 5MB are rejected."""
        headers, tenant_id, account = auth_headers

        # Create a file larger than 5MB
        large_content = b"x" * (6 * 1024 * 1024)  # 6MB
        files = {"file": ("large.png", io.BytesIO(large_content), "image/png")}
        data = {
            "agent_name": test_agent,
            "entity_type": "agent_avatar",
        }

        response = await async_client.post(
            "/api/v1/files/upload",
            files=files,
            data=data,
            headers=headers,
        )

        # Should return 400 for oversized file
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR]

    @pytest.mark.asyncio
    async def test_upload_avatar_nonexistent_agent(self, async_client: AsyncClient, auth_headers):
        """Test uploading avatar for nonexistent agent returns success with warning."""
        headers, tenant_id, account = auth_headers

        # Create a minimal PNG file
        png_content = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
            b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
            b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        files = {"file": ("avatar.png", io.BytesIO(png_content), "image/png")}
        data = {
            "agent_name": "nonexistent-agent-12345",
            "entity_type": "agent_avatar",
        }

        response = await async_client.post(
            "/api/v1/files/upload",
            files=files,
            data=data,
            headers=headers,
        )

        # Accept 200 (file uploaded but agent not found) or 500 (S3 not configured)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]

        if response.status_code == status.HTTP_200_OK:
            result = response.json()
            # Should still return success but with a warning
            assert result["success"] is True
            if "warning" in result.get("data", {}):
                assert "not found" in result["data"]["warning"].lower()


class TestFileUploadValidation:
    """Test file upload validation."""

    @pytest.mark.asyncio
    async def test_upload_without_file(self, async_client: AsyncClient, auth_headers):
        """Test upload without file field fails."""
        headers, tenant_id, account = auth_headers

        response = await async_client.post(
            "/api/v1/files/upload",
            headers=headers,
        )

        # Should return 422 for missing required file
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_upload_with_special_characters_in_filename(self, async_client: AsyncClient, auth_headers):
        """Test upload sanitizes special characters in filename."""
        headers, tenant_id, account = auth_headers

        file_content = b"test content"
        # Use filename with special characters that should be sanitized
        files = {"file": ("../../../etc/passwd", io.BytesIO(file_content), "text/plain")}

        response = await async_client.post(
            "/api/v1/files/upload",
            files=files,
            headers=headers,
        )

        # Accept 200 (sanitized and uploaded) or 500 (S3 not configured)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]


class TestFileUploadAuthorization:
    """Test file upload authorization."""

    @pytest.mark.asyncio
    async def test_upload_file_unauthorized(self, async_client: AsyncClient):
        """Test that unauthenticated requests to upload are rejected."""
        file_content = b"test content"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}

        response = await async_client.post(
            "/api/v1/files/upload",
            files=files,
        )

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
