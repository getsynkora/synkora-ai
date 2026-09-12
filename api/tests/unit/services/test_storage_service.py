import io
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import ValidationError
from src.models import FileType, UploadFile
from src.services.storage_service import StorageService


@pytest.fixture
def mock_db_session():
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_storage_config():
    with patch("src.services.storage_service.storage_config") as mock_config:
        mock_config.MAX_FILE_SIZE = 1024 * 1024 * 10  # 10 MB
        mock_config.ALLOWED_EXTENSIONS = {".txt", ".jpg", ".png", ".pdf"}
        mock_config.STORAGE_TYPE = "local"
        mock_config.local_storage_path = Path("/tmp/storage")
        # Mock ensure_local_storage to do nothing
        mock_config.ensure_local_storage = MagicMock()
        yield mock_config


@pytest.fixture
def storage_service(mock_db_session, mock_storage_config):
    return StorageService(mock_db_session)


class TestStorageService:
    def test_get_file_type(self, storage_service):
        assert storage_service._get_file_type("image/jpeg") == FileType.IMAGE
        assert storage_service._get_file_type("audio/mpeg") == FileType.AUDIO
        assert storage_service._get_file_type("video/mp4") == FileType.VIDEO
        assert storage_service._get_file_type("application/pdf") == FileType.DOCUMENT
        assert storage_service._get_file_type("unknown/type") == FileType.OTHER

    @pytest.mark.asyncio
    async def test_upload_file_success(self, storage_service, mock_db_session):
        # Mock DB result for duplicate check (return None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        file_content = b"test content"
        file = io.BytesIO(file_content)
        filename = "test.txt"
        tenant_id = uuid.uuid4()
        created_by = uuid.uuid4()

        # Mock file writing. _store_local offloads the blocking write to a
        # thread via Path.mkdir()/Path.write_bytes() rather than builtins.open().
        with (
            patch.object(Path, "mkdir") as mock_mkdir,
            patch.object(Path, "write_bytes") as mock_write_bytes,
        ):
            result = await storage_service.upload_file(file, filename, tenant_id, created_by)

            # Assertions
            assert isinstance(result, UploadFile)
            assert result.name == filename
            assert result.tenant_id == tenant_id
            assert result.size == len(file_content)

            # Verify DB calls
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_awaited_once()
            mock_db_session.refresh.assert_awaited_once()

            # Verify file written
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            mock_write_bytes.assert_called_once_with(file_content)

    @pytest.mark.asyncio
    async def test_upload_file_validation_error_size(self, storage_service, mock_storage_config):
        file = io.BytesIO(b"a" * (mock_storage_config.MAX_FILE_SIZE + 1))
        filename = "large.txt"
        tenant_id = uuid.uuid4()

        with pytest.raises(ValidationError, match="File size exceeds"):
            await storage_service.upload_file(file, filename, tenant_id)

    @pytest.mark.asyncio
    async def test_upload_file_validation_error_extension(self, storage_service):
        file = io.BytesIO(b"content")
        filename = "test.exe"
        tenant_id = uuid.uuid4()

        with pytest.raises(ValidationError, match="File type '.exe' is not allowed"):
            await storage_service.upload_file(file, filename, tenant_id)

    @pytest.mark.asyncio
    async def test_upload_file_duplicate(self, storage_service, mock_db_session):
        # Mock existing file
        existing_file = UploadFile(id=uuid.uuid4(), name="test.txt")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_file
        mock_db_session.execute.return_value = mock_result

        file = io.BytesIO(b"content")
        filename = "test.txt"
        tenant_id = uuid.uuid4()

        result = await storage_service.upload_file(file, filename, tenant_id)

        assert result == existing_file
        mock_db_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_file(self, storage_service, mock_db_session):
        expected_file = UploadFile(id=uuid.uuid4())
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expected_file
        mock_db_session.execute.return_value = mock_result

        result = await storage_service.get_file(expected_file.id, uuid.uuid4())
        assert result == expected_file

    @pytest.mark.asyncio
    async def test_delete_file_success(self, storage_service, mock_db_session):
        file_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        file_obj = UploadFile(id=file_id, key="test/key.txt", tenant_id=tenant_id)

        # Mock get_file returning the file
        # Since get_file is async and called internally, we need to mock the DB query inside it
        # But wait, we are calling delete_file which calls get_file.
        # We can mock get_file method directly or rely on DB mock.
        # Relying on DB mock is better integration-like unit test.
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = file_obj
        mock_db_session.execute.return_value = mock_result

        with patch("pathlib.Path.unlink") as mock_unlink, patch("pathlib.Path.exists", return_value=True):
            result = await storage_service.delete_file(file_id, tenant_id)

            assert result is True
            mock_unlink.assert_called_once()
            mock_db_session.delete.assert_awaited_once_with(file_obj)
            mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, storage_service, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await storage_service.delete_file(uuid.uuid4(), uuid.uuid4())
        assert result is False
        mock_db_session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_files(self, storage_service, mock_db_session):
        files = [UploadFile(id=uuid.uuid4()), UploadFile(id=uuid.uuid4())]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = files
        mock_db_session.execute.return_value = mock_result

        result = await storage_service.list_files(uuid.uuid4())
        assert len(result) == 2
        assert result == files

    def test_get_file_path(self, storage_service, mock_storage_config):
        file = UploadFile(key="test.txt")
        path = storage_service.get_file_path(file)
        assert path == mock_storage_config.local_storage_path / "test.txt"

    def test_get_file_url(self, storage_service):
        file_id = uuid.uuid4()
        file = UploadFile(id=file_id)
        url = storage_service.get_file_url(file)
        assert url == f"/api/files/{file_id}"
