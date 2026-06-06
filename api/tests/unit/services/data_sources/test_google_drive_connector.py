import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Mock heavy Google API dependencies before importing the module under test.
# test_adk_tools.py runs first (alphabetical order) and sets sys.modules["googleapiclient"]
# to a MagicMock that Python's import system can't traverse as a package.
# Register all sub-modules we need so lazy imports inside the connector resolve correctly.
if "googleapiclient" not in sys.modules:
    sys.modules["googleapiclient"] = MagicMock()
sys.modules.setdefault("googleapiclient.discovery", MagicMock())
sys.modules.setdefault("googleapiclient.http", MagicMock())
sys.modules.setdefault("google.oauth2", MagicMock())
sys.modules.setdefault("google.oauth2.credentials", MagicMock())

from src.models.data_source import DataSource
from src.services.data_sources.google_drive_connector import GoogleDriveConnector


class TestGoogleDriveConnector:
    @pytest.fixture
    def mock_data_source(self):
        ds = MagicMock(spec=DataSource)
        ds.id = "ds-123"
        return ds

    @pytest.fixture
    def mock_db_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_oauth_provider(self):
        provider = MagicMock()
        provider.client_id = "client_id"
        provider.client_secret = "client_secret"
        return provider

    @pytest.fixture
    def connector(self, mock_data_source, mock_db_session, mock_oauth_provider):
        return GoogleDriveConnector(mock_data_source, mock_db_session, mock_oauth_provider)

    @pytest.mark.asyncio
    async def test_connect_success(self, connector):
        # Mock get_oauth_token
        mock_token = MagicMock()
        mock_token.access_token = "access"
        mock_token.refresh_token = "refresh"

        with (
            patch.object(connector, "_get_oauth_token", return_value=mock_token),
            patch("google.oauth2.credentials.Credentials") as mock_creds,
            patch("googleapiclient.discovery.build") as mock_build,
        ):
            result = await connector.connect()

            assert result is True
            assert connector.service is not None
            mock_creds.assert_called_once()
            mock_build.assert_called_with("drive", "v3", credentials=mock_creds.return_value)

    @pytest.mark.asyncio
    async def test_connect_no_token(self, connector):
        with patch.object(connector, "_get_oauth_token", return_value=None):
            with pytest.raises(ValueError, match="No OAuth token found"):
                await connector.connect()

    @pytest.mark.asyncio
    async def test_fetch_documents_success(self, connector):
        connector.service = MagicMock()
        mock_files = connector.service.files.return_value

        # Mock list response
        mock_files.list.return_value.execute.return_value = {
            "files": [
                {
                    "id": "file1",
                    "name": "Doc 1",
                    "mimeType": "text/plain",
                    "owners": [{"displayName": "Owner", "emailAddress": "owner@test.com"}],
                }
            ]
        }

        # Mock extract content
        with patch.object(connector, "_extract_file_content", return_value="File content"):
            docs = await connector.fetch_documents()

            assert len(docs) == 1
            assert docs[0]["id"] == "file1"
            assert docs[0]["text"] == "File content"
            assert docs[0]["metadata"]["title"] == "Doc 1"

    @pytest.mark.asyncio
    async def test_extract_file_content_google_doc(self, connector):
        connector.service = MagicMock()
        file_meta = {"id": "doc1", "mimeType": "application/vnd.google-apps.document", "name": "My Doc"}

        # Mock export_media
        mock_request = MagicMock()
        connector.service.files.return_value.export_media.return_value = mock_request

        # Mock downloader
        with patch("googleapiclient.http.MediaIoBaseDownload") as MockDownloader:
            instance = MockDownloader.return_value
            instance.next_chunk.return_value = (None, True)

            # We need to simulate writing to the IO buffer passed to MediaIoBaseDownload
            def side_effect(fh, req):
                fh.write(b"Exported Content")
                return instance

            MockDownloader.side_effect = side_effect

            content = await connector._extract_file_content(file_meta)

            assert content == "Exported Content"
            connector.service.files.return_value.export_media.assert_called_with(fileId="doc1", mimeType="text/plain")

    @pytest.mark.asyncio
    async def test_extract_file_content_pdf(self, connector):
        file_meta = {"id": "pdf1", "mimeType": "application/pdf", "name": "My PDF.pdf"}

        # Mock get_media
        mock_request = MagicMock()
        connector.service = MagicMock()
        connector.service.files.return_value.get_media.return_value = mock_request

        with patch("googleapiclient.http.MediaIoBaseDownload") as MockDownloader:
            instance = MockDownloader.return_value
            instance.next_chunk.return_value = (None, True)
            MockDownloader.side_effect = lambda fh, req: instance

            content = await connector._extract_file_content(file_meta)

            assert "[PDF Document: My PDF.pdf]" in content

    @pytest.mark.asyncio
    async def test_get_document_count(self, connector):
        connector.service = MagicMock()
        connector.service.files.return_value.list.return_value.execute.return_value = {
            "files": [{"id": "1"}, {"id": "2"}]
        }

        count = await connector.get_document_count()
        assert count == 2

    @pytest.mark.asyncio
    async def test_search_documents(self, connector):
        connector.service = MagicMock()
        connector.service.files.return_value.list.return_value.execute.return_value = {
            "files": [{"id": "file1", "name": "Match", "mimeType": "text/plain"}]
        }

        with patch.object(connector, "_extract_file_content", return_value="Content"):
            results = await connector.search_documents("query")

            assert len(results) == 1
            assert results[0]["id"] == "file1"

    @pytest.mark.asyncio
    async def test_validate_connection_success(self, connector):
        connector.service = MagicMock()
        connector.service.about.return_value.get.return_value.execute.return_value = {
            "user": {"emailAddress": "user@test.com"}
        }

        result = await connector.validate_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_connection_failure(self, connector):
        connector.service = MagicMock()
        connector.service.about.return_value.get.side_effect = Exception("API Error")

        result = await connector.validate_connection()
        assert result is False
