"""Unit tests for presigned S3 upload URL endpoint."""

import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


@pytest.mark.asyncio
async def test_get_upload_presigned_url_returns_expected_fields(tenant_id):
    """Endpoint returns upload_url, s3_key, s3_url, and expires_in."""
    from src.controllers.data_analysis import get_analysis_upload_presigned_url

    mock_presigned = "https://minio:9000/bucket/data-uploads/tenant/file.csv?X-Amz-Signature=abc"

    with patch("src.services.storage.s3_storage.S3StorageService") as MockS3:
        instance = MockS3.return_value
        instance.bucket_name = "synkora"
        instance.presigned_client = MagicMock()
        instance.presigned_client.generate_presigned_url.return_value = mock_presigned

        result = await get_analysis_upload_presigned_url(
            filename="sales.csv",
            content_type="text/csv",
            tenant_id=tenant_id,
        )

    assert "upload_url" in result
    assert "s3_key" in result
    assert "s3_url" in result
    assert "expires_in" in result
    assert result["s3_url"].startswith("s3://synkora/")
    assert "sales_csv" in result["s3_key"] or "sales.csv" in result["s3_key"]
    assert result["expires_in"] == 3600


@pytest.mark.asyncio
async def test_get_upload_presigned_url_rejects_disallowed_content_type(tenant_id):
    """Endpoint raises 400 for disallowed content types."""
    from fastapi import HTTPException

    from src.controllers.data_analysis import get_analysis_upload_presigned_url

    with pytest.raises(HTTPException) as exc_info:
        await get_analysis_upload_presigned_url(
            filename="malware.exe",
            content_type="application/x-msdownload",
            tenant_id=tenant_id,
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_get_upload_presigned_url_sanitises_filename(tenant_id):
    """Dangerous filename characters are replaced."""
    from src.controllers.data_analysis import get_analysis_upload_presigned_url

    with patch("src.services.storage.s3_storage.S3StorageService") as MockS3:
        instance = MockS3.return_value
        instance.bucket_name = "synkora"
        instance.presigned_client = MagicMock()
        instance.presigned_client.generate_presigned_url.return_value = "https://example.com/url"

        result = await get_analysis_upload_presigned_url(
            filename="../../etc/passwd",
            content_type="text/csv",
            tenant_id=tenant_id,
        )

    # Path traversal chars replaced; key should not contain ..
    assert ".." not in result["s3_key"]
    assert "/" not in result["s3_key"].split("data-uploads/")[1].split("/")[-1]
