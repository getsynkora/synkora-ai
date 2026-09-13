from types import SimpleNamespace

CONTEXT = SimpleNamespace(tenant_id="11111111-1111-1111-1111-111111111111")
ROOT = f"tenants/{CONTEXT.tenant_id}/"
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.services.agents.internal_tools.storage_tools import (
    internal_s3_delete_file,
    internal_s3_download_file,
    internal_s3_file_exists,
    internal_s3_generate_presigned_url,
    internal_s3_get_file_metadata,
    internal_s3_list_files,
    internal_s3_upload_directory,
    internal_s3_upload_file,
)


class TestStorageTools:
    """Test storage tools with workspace path mocking."""

    MOCK_WORKSPACE = "/tmp/synkora/workspaces/tenant1/conv1"

    @pytest.fixture
    def mock_s3_service(self):
        with patch("src.services.agents.internal_tools.storage_tools.get_s3_storage") as mock_get:
            service = MagicMock()
            mock_get.return_value = service
            yield service

    @pytest.mark.asyncio
    async def test_internal_s3_upload_file(self, mock_s3_service):
        file_content = b"test content"
        file_path = f"{self.MOCK_WORKSPACE}/test.txt"
        mock_s3_service.upload_file.return_value = {
            "key": "test.txt",
            "url": "s3://bucket/test.txt",
            "bucket": "bucket",
        }
        mock_s3_service.generate_presigned_url.return_value = "https://presigned.url"

        with (
            patch(
                "src.services.agents.internal_tools.storage_tools._get_workspace_path", return_value=self.MOCK_WORKSPACE
            ),
            patch(
                "src.services.agents.internal_tools.storage_tools._validate_path_in_workspace",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("builtins.open", mock_open(read_data=file_content)),
            patch("os.path.getsize", return_value=len(file_content)),
        ):
            result = await internal_s3_upload_file(file_path, runtime_context=CONTEXT)

            assert result["success"] is True
            assert result["s3_key"] == "test.txt"
            assert result["presigned_url"] == "https://presigned.url"
            mock_s3_service.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_internal_s3_upload_file_not_found(self, mock_s3_service):
        file_path = f"{self.MOCK_WORKSPACE}/nonexistent.txt"
        with (
            patch(
                "src.services.agents.internal_tools.storage_tools._get_workspace_path", return_value=self.MOCK_WORKSPACE
            ),
            patch(
                "src.services.agents.internal_tools.storage_tools._validate_path_in_workspace",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=False),
        ):
            result = await internal_s3_upload_file(file_path, runtime_context=CONTEXT)
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_internal_s3_upload_directory(self, mock_s3_service):
        dir_path = f"{self.MOCK_WORKSPACE}/dir"
        mock_s3_service.upload_file.return_value = {"url": "s3://url"}
        mock_s3_service.generate_presigned_url.return_value = "https://url"

        with (
            patch(
                "src.services.agents.internal_tools.storage_tools._get_workspace_path", return_value=self.MOCK_WORKSPACE
            ),
            patch(
                "src.services.agents.internal_tools.storage_tools._validate_path_in_workspace",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=True),
            patch("os.walk", return_value=[(dir_path, [], ["file1.txt", "index.md"])]),
            patch("builtins.open", mock_open(read_data=b"content")),
            patch("os.path.getsize", return_value=10),
        ):
            result = await internal_s3_upload_directory(dir_path, "prefix", runtime_context=CONTEXT)

            assert result["success"] is True
            assert result["total_uploaded"] == 2
            assert result["index_url"] == "https://url"

    @pytest.mark.asyncio
    async def test_internal_s3_download_file(self, mock_s3_service):
        output_path = f"{self.MOCK_WORKSPACE}/out.txt"
        mock_s3_service.download_file.return_value = b"content"

        # Download to memory (no output_path, no workspace validation needed)
        result = await internal_s3_download_file("key", runtime_context=CONTEXT)
        assert result["success"] is True
        assert result["content"] == "content"

        # Download to file within workspace
        with (
            patch(
                "src.services.agents.internal_tools.storage_tools._get_workspace_path", return_value=self.MOCK_WORKSPACE
            ),
            patch(
                "src.services.agents.internal_tools.storage_tools._validate_path_in_workspace",
                return_value=(True, None),
            ),
            patch("os.makedirs"),
            patch("builtins.open", mock_open()) as mock_file,
        ):
            result = await internal_s3_download_file("key", output_path=output_path, runtime_context=CONTEXT)
            assert result["success"] is True
            mock_file().write.assert_called_with(b"content")

    @pytest.mark.asyncio
    async def test_internal_s3_generate_presigned_url(self, mock_s3_service):
        mock_s3_service.generate_presigned_url.return_value = "https://url"

        result = await internal_s3_generate_presigned_url("key", runtime_context=CONTEXT)

        assert result["success"] is True
        assert result["presigned_url"] == "https://url"
        assert result["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_internal_s3_list_files(self, mock_s3_service):
        mock_s3_service.list_files.return_value = [{"key": "file1"}, {"key": "file2"}]

        result = await internal_s3_list_files(prefix="test", runtime_context=CONTEXT)

        assert result["success"] is True
        assert len(result["files"]) == 2
        assert result["prefix"] == ROOT + "test"

    @pytest.mark.asyncio
    async def test_internal_s3_delete_file(self, mock_s3_service):
        result = await internal_s3_delete_file("key", runtime_context=CONTEXT)

        assert result["success"] is True
        mock_s3_service.delete_file.assert_called_with(ROOT + "key")

    @pytest.mark.asyncio
    async def test_internal_s3_file_exists(self, mock_s3_service):
        mock_s3_service.file_exists.return_value = True

        result = await internal_s3_file_exists("key", runtime_context=CONTEXT)

        assert result["success"] is True
        assert result["exists"] is True

    @pytest.mark.asyncio
    async def test_internal_s3_get_file_metadata(self, mock_s3_service):
        mock_s3_service.get_file_metadata.return_value = {"size": 100, "type": "text/plain"}

        result = await internal_s3_get_file_metadata("key", runtime_context=CONTEXT)

        assert result["success"] is True
        assert result["size"] == 100
