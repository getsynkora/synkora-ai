"""
Unit tests for S3 Storage Service.

Tests file upload, download, deletion, and presigned URL generation.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


class TestS3StorageServiceInit:
    """Test S3StorageService initialization."""

    @patch("src.services.storage.s3_storage.boto3")
    @patch.dict("os.environ", {"AWS_S3_BUCKET": "test-bucket", "AWS_REGION": "us-east-1"})
    def test_init_with_env_vars(self, mock_boto3):
        """Test initialization with environment variables."""
        from src.services.storage.s3_storage import S3StorageService

        service = S3StorageService()

        assert service.bucket_name == "test-bucket"
        assert service.region == "us-east-1"
        mock_boto3.client.assert_called()

    @patch("src.services.storage.s3_storage.boto3")
    def test_init_with_explicit_params(self, mock_boto3):
        """Test initialization with explicit parameters."""
        from src.services.storage.s3_storage import S3StorageService

        service = S3StorageService(
            bucket_name="my-bucket",
            region="eu-west-1",
            access_key="AKIAIOSFODNN7EXAMPLE",
            secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        )

        assert service.bucket_name == "my-bucket"
        assert service.region == "eu-west-1"

    @patch("src.services.storage.s3_storage.boto3")
    @patch.dict("os.environ", {}, clear=True)
    def test_init_without_bucket_raises_error(self, mock_boto3):
        """Test that missing bucket name raises ValueError."""
        from src.services.storage.s3_storage import S3StorageService

        with pytest.raises(ValueError) as exc_info:
            S3StorageService(bucket_name=None)

        assert "bucket name must be provided" in str(exc_info.value).lower()

    @patch("src.services.storage.s3_storage.boto3")
    @patch.dict("os.environ", {"AWS_S3_BUCKET": "test-bucket", "AWS_ENDPOINT_URL": "http://localhost:9000"})
    def test_init_with_custom_endpoint(self, mock_boto3):
        """Test initialization with custom endpoint (MinIO)."""
        from src.services.storage.s3_storage import S3StorageService

        service = S3StorageService()

        assert service.bucket_name == "test-bucket"


class TestUploadFile:
    """Test file upload functionality."""

    @pytest.fixture
    def mock_s3_service(self):
        """Create mock S3 service."""
        with patch("src.services.storage.s3_storage.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService(bucket_name="test-bucket", region="us-east-1")
            service.s3_client = mock_client
            yield service, mock_client

    def test_upload_file_bytes(self, mock_s3_service):
        """Test uploading file from bytes."""
        service, mock_client = mock_s3_service

        result = service.upload_file(
            file_content=b"test content",
            key="test/file.txt",
            content_type="text/plain",
        )

        assert result["bucket"] == "test-bucket"
        assert result["key"] == "test/file.txt"
        assert "url" in result
        mock_client.upload_fileobj.assert_called_once()

    def test_upload_file_with_metadata(self, mock_s3_service):
        """Test uploading file with metadata."""
        service, mock_client = mock_s3_service

        result = service.upload_file(
            file_content=b"test content",
            key="test/file.txt",
            metadata={"custom_field": "value"},
        )

        assert result["key"] == "test/file.txt"
        # Verify metadata was passed
        call_args = mock_client.upload_fileobj.call_args
        assert "Metadata" in call_args.kwargs.get("ExtraArgs", {})

    def test_upload_file_auto_content_type(self, mock_s3_service):
        """Test that content type is auto-detected."""
        service, mock_client = mock_s3_service

        result = service.upload_file(
            file_content=b"test content",
            key="test/document.pdf",
        )

        assert result["key"] == "test/document.pdf"
        # Content type should be detected from extension
        call_args = mock_client.upload_fileobj.call_args
        extra_args = call_args.kwargs.get("ExtraArgs", {})
        assert extra_args.get("ContentType") == "application/pdf"

    def test_upload_file_error(self, mock_s3_service):
        """Test upload error handling."""
        service, mock_client = mock_s3_service
        mock_client.upload_fileobj.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Internal Error"}}, "upload_fileobj"
        )

        with pytest.raises(Exception) as exc_info:
            service.upload_file(b"test", "test/file.txt")

        assert "S3 upload failed" in str(exc_info.value)


class TestDownloadFile:
    """Test file download functionality."""

    @pytest.fixture
    def mock_s3_service(self):
        """Create mock S3 service."""
        with patch("src.services.storage.s3_storage.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService(bucket_name="test-bucket", region="us-east-1")
            service.s3_client = mock_client
            yield service, mock_client

    def test_download_file_success(self, mock_s3_service):
        """Test successful file download."""
        service, mock_client = mock_s3_service

        mock_body = MagicMock()
        mock_body.read.return_value = b"file content"
        mock_client.get_object.return_value = {"Body": mock_body}

        result = service.download_file("test/file.txt")

        assert result == b"file content"
        mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="test/file.txt")

    def test_download_file_not_found(self, mock_s3_service):
        """Test download when file doesn't exist."""
        service, mock_client = mock_s3_service
        mock_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "get_object"
        )

        with pytest.raises(Exception) as exc_info:
            service.download_file("nonexistent/file.txt")

        assert "S3 download failed" in str(exc_info.value)


class TestDeleteFile:
    """Test file deletion functionality."""

    @pytest.fixture
    def mock_s3_service(self):
        """Create mock S3 service."""
        with patch("src.services.storage.s3_storage.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService(bucket_name="test-bucket", region="us-east-1")
            service.s3_client = mock_client
            yield service, mock_client

    def test_delete_file_success(self, mock_s3_service):
        """Test successful file deletion."""
        service, mock_client = mock_s3_service

        result = service.delete_file("test/file.txt")

        assert result is True
        mock_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="test/file.txt")

    def test_delete_file_error(self, mock_s3_service):
        """Test deletion error handling."""
        service, mock_client = mock_s3_service
        mock_client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Error"}}, "delete_object"
        )

        with pytest.raises(Exception) as exc_info:
            service.delete_file("test/file.txt")

        assert "S3 deletion failed" in str(exc_info.value)


class TestPresignedUrl:
    """Test presigned URL generation."""

    @pytest.fixture
    def mock_s3_service(self):
        """Create mock S3 service."""
        with patch("src.services.storage.s3_storage.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService(bucket_name="test-bucket", region="us-east-1")
            service.s3_client = mock_client
            service.presigned_client = mock_client
            yield service, mock_client

    def test_generate_presigned_url(self, mock_s3_service):
        """Test presigned URL generation."""
        service, mock_client = mock_s3_service
        mock_client.generate_presigned_url.return_value = "https://bucket.s3.amazonaws.com/key?X-Amz-Algorithm=..."

        result = service.generate_presigned_url("test/file.txt", expiration=3600)

        assert "https://" in result
        mock_client.generate_presigned_url.assert_called_once()

    def test_generate_presigned_url_from_s3_uri(self, mock_s3_service):
        """Test presigned URL from S3 URI format."""
        service, mock_client = mock_s3_service
        mock_client.generate_presigned_url.return_value = "https://bucket.s3.amazonaws.com/key?X-Amz-Algorithm=..."

        result = service.generate_presigned_url("s3://test-bucket/path/to/file.txt")

        assert result is not None
        # Verify the key was extracted correctly
        call_args = mock_client.generate_presigned_url.call_args
        assert call_args[1]["Params"]["Key"] == "path/to/file.txt"

    def test_generate_presigned_url_invalid_s3_uri(self, mock_s3_service):
        """Test presigned URL with invalid S3 URI."""
        service, mock_client = mock_s3_service

        with pytest.raises(ValueError) as exc_info:
            service.generate_presigned_url("s3://bucket-only")

        assert "Invalid S3 URI" in str(exc_info.value)

    def test_generate_presigned_url_error(self, mock_s3_service):
        """Test presigned URL error handling."""
        service, mock_client = mock_s3_service
        mock_client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Error"}}, "generate_presigned_url"
        )

        with pytest.raises(Exception) as exc_info:
            service.generate_presigned_url("test/file.txt")

        assert "Presigned URL generation failed" in str(exc_info.value)


class TestFileExists:
    """Test file existence check."""

    @pytest.fixture
    def mock_s3_service(self):
        """Create mock S3 service."""
        with patch("src.services.storage.s3_storage.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService(bucket_name="test-bucket", region="us-east-1")
            service.s3_client = mock_client
            yield service, mock_client

    def test_file_exists_true(self, mock_s3_service):
        """Test file exists returns True."""
        service, mock_client = mock_s3_service
        mock_client.head_object.return_value = {}

        result = service.file_exists("test/file.txt")

        assert result is True

    def test_file_exists_false(self, mock_s3_service):
        """Test file exists returns False when not found."""
        service, mock_client = mock_s3_service
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "head_object"
        )

        result = service.file_exists("nonexistent/file.txt")

        assert result is False


class TestGetFileMetadata:
    """Test file metadata retrieval."""

    @pytest.fixture
    def mock_s3_service(self):
        """Create mock S3 service."""
        with patch("src.services.storage.s3_storage.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService(bucket_name="test-bucket", region="us-east-1")
            service.s3_client = mock_client
            yield service, mock_client

    def test_get_file_metadata_success(self, mock_s3_service):
        """Test successful metadata retrieval."""
        service, mock_client = mock_s3_service
        mock_client.head_object.return_value = {
            "ContentLength": 1024,
            "ContentType": "text/plain",
            "LastModified": datetime(2024, 1, 1),
            "Metadata": {"custom": "value"},
            "ETag": '"abc123"',
        }

        result = service.get_file_metadata("test/file.txt")

        assert result["size"] == 1024
        assert result["content_type"] == "text/plain"
        assert result["etag"] == "abc123"

    def test_get_file_metadata_error(self, mock_s3_service):
        """Test metadata retrieval error handling."""
        service, mock_client = mock_s3_service
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "head_object"
        )

        with pytest.raises(Exception) as exc_info:
            service.get_file_metadata("nonexistent/file.txt")

        assert "S3 metadata retrieval failed" in str(exc_info.value)


class TestListFiles:
    """Test file listing."""

    @pytest.fixture
    def mock_s3_service(self):
        """Create mock S3 service."""
        with patch("src.services.storage.s3_storage.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService(bucket_name="test-bucket", region="us-east-1")
            service.s3_client = mock_client
            yield service, mock_client

    def test_list_files_success(self, mock_s3_service):
        """Test successful file listing."""
        service, mock_client = mock_s3_service
        mock_client.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": "test/file1.txt",
                    "Size": 100,
                    "LastModified": datetime(2024, 1, 1),
                    "ETag": '"abc"',
                },
                {
                    "Key": "test/file2.txt",
                    "Size": 200,
                    "LastModified": datetime(2024, 1, 2),
                    "ETag": '"def"',
                },
            ]
        }

        result = service.list_files(prefix="test/")

        assert len(result) == 2
        assert result[0]["key"] == "test/file1.txt"
        assert result[1]["key"] == "test/file2.txt"

    def test_list_files_empty(self, mock_s3_service):
        """Test listing when no files exist."""
        service, mock_client = mock_s3_service
        mock_client.list_objects_v2.return_value = {}

        result = service.list_files(prefix="empty/")

        assert result == []


class TestGenerateKey:
    """Test key generation."""

    @pytest.fixture
    def mock_s3_service(self):
        """Create mock S3 service."""
        with patch("src.services.storage.s3_storage.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService(bucket_name="test-bucket", region="us-east-1")
            yield service

    def test_generate_key_format(self, mock_s3_service):
        """Test key generation format."""
        service = mock_s3_service
        tenant_id = uuid.uuid4()
        timestamp = datetime(2024, 6, 15, 10, 30, 0)

        result = service.generate_key(
            tenant_id=tenant_id,
            source_type="SLACK",
            filename="document.pdf",
            timestamp=timestamp,
        )

        assert str(tenant_id) in result
        assert "SLACK" in result
        assert "2024/06/15" in result
        assert "document.pdf" in result

    def test_generate_key_uses_current_time(self, mock_s3_service):
        """Test key generation uses current time when not provided."""
        service = mock_s3_service
        tenant_id = uuid.uuid4()

        result = service.generate_key(
            tenant_id=tenant_id,
            source_type="gmail",
            filename="email.eml",
        )

        # Should contain today's date
        today = datetime.now(UTC).strftime("%Y/%m/%d")
        assert today in result


class TestCopyFile:
    """Test file copy functionality."""

    @pytest.fixture
    def mock_s3_service(self):
        """Create mock S3 service."""
        with patch("src.services.storage.s3_storage.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService(bucket_name="test-bucket", region="us-east-1")
            service.s3_client = mock_client
            yield service, mock_client

    def test_copy_file_success(self, mock_s3_service):
        """Test successful file copy."""
        service, mock_client = mock_s3_service

        result = service.copy_file("source/file.txt", "dest/file.txt")

        assert result["source_key"] == "source/file.txt"
        assert result["dest_key"] == "dest/file.txt"
        mock_client.copy_object.assert_called_once()

    def test_copy_file_error(self, mock_s3_service):
        """Test copy error handling."""
        service, mock_client = mock_s3_service
        mock_client.copy_object.side_effect = ClientError({"Error": {"Code": "500", "Message": "Error"}}, "copy_object")

        with pytest.raises(Exception) as exc_info:
            service.copy_file("source/file.txt", "dest/file.txt")

        assert "S3 copy failed" in str(exc_info.value)


class TestExtractOwnKeyFromUrl:
    """Test detection of URLs pointing at our own S3/MinIO storage.

    Presigned URLs are signed with AWS_PUBLIC_ENDPOINT_URL (e.g. http://localhost:9000 in
    dev) for browser access, but that host isn't reachable from inside a server-side
    fetch and is correctly SSRF-blocked as "localhost". Internal tools need a way to
    recognize "this is our own storage" and fetch bytes directly via the S3 client
    instead of going through a public HTTP round-trip.
    """

    @pytest.fixture
    def mock_s3_service(self):
        with (
            patch("src.services.storage.s3_storage.boto3"),
            patch.dict(
                "os.environ",
                {
                    "AWS_S3_BUCKET": "test-bucket",
                    "AWS_ENDPOINT_URL": "http://minio:9000",
                    "AWS_PUBLIC_ENDPOINT_URL": "http://localhost:9000",
                },
            ),
        ):
            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService()
            yield service

    def test_matches_public_endpoint_url(self, mock_s3_service):
        service = mock_s3_service

        key = service.extract_own_key_from_url(
            "http://localhost:9000/test-bucket/agent-uploads/shot.png?X-Amz-Algorithm=foo"
        )

        assert key == "agent-uploads/shot.png"

    def test_matches_internal_endpoint_url(self, mock_s3_service):
        service = mock_s3_service

        key = service.extract_own_key_from_url("http://minio:9000/test-bucket/agent-uploads/shot.png")

        assert key == "agent-uploads/shot.png"

    def test_returns_none_for_unrelated_url(self, mock_s3_service):
        service = mock_s3_service

        key = service.extract_own_key_from_url("https://example.com/some/file.png")

        assert key is None

    def test_returns_none_for_wrong_bucket(self, mock_s3_service):
        service = mock_s3_service

        key = service.extract_own_key_from_url("http://localhost:9000/some-other-bucket/agent-uploads/shot.png")

        assert key is None

    def test_unquotes_key(self, mock_s3_service):
        service = mock_s3_service

        key = service.extract_own_key_from_url("http://localhost:9000/test-bucket/agent%20uploads/shot.png")

        assert key == "agent uploads/shot.png"


class TestDownloadIfOwnUrl:
    """Test the combined detect-and-fetch helper used by internal tools."""

    @pytest.fixture
    def mock_s3_service(self):
        with (
            patch("src.services.storage.s3_storage.boto3") as mock_boto3,
            patch.dict(
                "os.environ",
                {
                    "AWS_S3_BUCKET": "test-bucket",
                    "AWS_ENDPOINT_URL": "http://minio:9000",
                    "AWS_PUBLIC_ENDPOINT_URL": "http://localhost:9000",
                },
            ),
        ):
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService()
            service.s3_client = mock_client
            yield service, mock_client

    @pytest.mark.asyncio
    async def test_fetches_bytes_directly_for_own_url(self, mock_s3_service):
        service, mock_client = mock_s3_service
        mock_body = MagicMock()
        mock_body.read.return_value = b"screenshot bytes"
        mock_client.get_object.return_value = {"Body": mock_body}

        result = await service.download_if_own_url("http://localhost:9000/test-bucket/agent-uploads/shot.png")

        assert result == b"screenshot bytes"
        mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="agent-uploads/shot.png")

    @pytest.mark.asyncio
    async def test_returns_none_for_non_own_url(self, mock_s3_service):
        service, mock_client = mock_s3_service

        result = await service.download_if_own_url("https://example.com/some/file.png")

        assert result is None
        mock_client.get_object.assert_not_called()


class TestAsyncMethods:
    """Test async method wrappers."""

    @pytest.fixture
    def mock_s3_service(self):
        """Create mock S3 service."""
        with patch("src.services.storage.s3_storage.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client

            from src.services.storage.s3_storage import S3StorageService

            service = S3StorageService(bucket_name="test-bucket", region="us-east-1")
            service.s3_client = mock_client
            yield service, mock_client

    @pytest.mark.asyncio
    async def test_upload_file_content_async(self, mock_s3_service):
        """Test async upload wrapper."""
        service, mock_client = mock_s3_service

        result = await service.upload_file_content(
            file_content=b"test content",
            key="test/file.txt",
        )

        assert "s3://" in result

    @pytest.mark.asyncio
    async def test_download_file_content_async(self, mock_s3_service):
        """Test async download wrapper."""
        service, mock_client = mock_s3_service

        mock_body = MagicMock()
        mock_body.read.return_value = b"file content"
        mock_client.get_object.return_value = {"Body": mock_body}

        result = await service.download_file_content("s3://test-bucket/test/file.txt")

        assert result == b"file content"

    @pytest.mark.asyncio
    async def test_download_file_content_from_key(self, mock_s3_service):
        """Test async download from plain key."""
        service, mock_client = mock_s3_service

        mock_body = MagicMock()
        mock_body.read.return_value = b"file content"
        mock_client.get_object.return_value = {"Body": mock_body}

        result = await service.download_file_content("test/file.txt")

        assert result == b"file content"
