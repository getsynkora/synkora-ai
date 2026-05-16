"""Tests for data analysis controller."""

import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.data_analysis import router
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def mock_account():
    account = MagicMock()
    account.id = uuid.uuid4()
    account.email = "test@example.com"
    account.name = "Test User"
    return account


@pytest.fixture
def client(mock_db_session, mock_account):
    app = FastAPI()
    app.include_router(router)

    tenant_id = uuid.uuid4()

    # Mock dependencies - use async generator for db
    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[get_current_account] = lambda: mock_account

    yield TestClient(app), tenant_id, mock_account, mock_db_session


class TestUploadAnalysisFile:
    """Tests for file upload endpoint."""

    def test_upload_csv_success(self, client):
        """Test successful CSV file upload."""
        test_client, tenant_id, mock_account, mock_db = client

        csv_content = b"name,age,city\nJohn,30,NYC\nJane,25,LA"

        with patch("src.controllers.data_analysis.DataAnalysisService") as MockService:
            mock_service = MockService.return_value
            mock_service.upload_and_process_file = AsyncMock(
                return_value={
                    "success": True,
                    "file_path": "/tmp/test.csv",
                    "file_name": "test.csv",
                    "file_size": len(csv_content),
                    "file_type": "csv",
                    "statistics": {"rows": 2, "columns": 3},
                    "data_preview": [{"name": "John", "age": 30, "city": "NYC"}],
                }
            )

            response = test_client.post(
                "/api/v1/data-analysis/upload-file", files={"file": ("test.csv", BytesIO(csv_content), "text/csv")}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["file_name"] == "test.csv"

    def test_upload_zip_success(self, client):
        """Test successful ZIP file upload."""
        test_client, tenant_id, mock_account, mock_db = client

        # Minimal ZIP file content (not valid but enough for test)
        zip_content = b"PK\x03\x04fake zip content"

        with (
            patch("src.controllers.data_analysis.DataAnalysisService") as MockService,
            patch("src.services.security.file_security.FileSecurityService") as MockFileSecurity,
        ):
            mock_service = MockService.return_value
            mock_service.upload_and_process_file = AsyncMock(
                return_value={
                    "success": True,
                    "file_path": "/tmp/test.zip",
                    "file_name": "test.zip",
                    "file_size": len(zip_content),
                    "file_type": "zip",
                }
            )
            MockFileSecurity.return_value.validate_file.return_value = {"is_valid": True}

            response = test_client.post(
                "/api/v1/data-analysis/upload-file",
                files={"file": ("test.zip", BytesIO(zip_content), "application/zip")},
                data={"file_type": "zip"},
            )

        assert response.status_code == status.HTTP_200_OK

    def test_upload_invalid_file_type(self, client):
        """Test upload with invalid file type."""
        test_client, tenant_id, mock_account, mock_db = client

        response = test_client.post(
            "/api/v1/data-analysis/upload-file", files={"file": ("test.txt", BytesIO(b"text content"), "text/plain")}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_upload_processing_failure(self, client):
        """Test file processing failure."""
        test_client, tenant_id, mock_account, mock_db = client

        csv_content = b"invalid,csv"

        with patch("src.controllers.data_analysis.DataAnalysisService") as MockService:
            mock_service = MockService.return_value
            mock_service.upload_and_process_file = AsyncMock(
                return_value={"success": False, "message": "Invalid CSV format"}
            )

            response = test_client.post(
                "/api/v1/data-analysis/upload-file", files={"file": ("test.csv", BytesIO(csv_content), "text/csv")}
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestQueryDataSource:
    """Tests for data source query endpoint."""

    def test_query_data_source_success(self, client):
        """Test successful data source query."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.data_analysis.DataAnalysisService") as MockService:
            mock_service = MockService.return_value
            mock_service.query_data_source = AsyncMock(
                return_value={"success": True, "data": [{"metric": "cpu", "value": 80}]}
            )

            response = test_client.post(
                "/api/v1/data-analysis/query-data-source", json={"data_source_id": 1, "query_params": {"metric": "cpu"}}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_query_data_source_failure(self, client):
        """Test data source query failure."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.data_analysis.DataAnalysisService") as MockService:
            mock_service = MockService.return_value
            mock_service.query_data_source = AsyncMock(
                return_value={"success": False, "message": "Connection failed", "error": "Timeout"}
            )

            response = test_client.post(
                "/api/v1/data-analysis/query-data-source", json={"data_source_id": 1, "query_params": {}}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is False


class TestQueryDatabase:
    """Tests for database query endpoint."""

    def test_query_database_success(self, client):
        """Test successful database query."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.data_analysis.DataAnalysisService") as MockService:
            mock_service = MockService.return_value
            mock_service.query_database_connection = AsyncMock(
                return_value={
                    "success": True,
                    "data": [{"id": 1, "name": "Test"}],
                    "columns": ["id", "name"],
                    "row_count": 1,
                }
            )

            response = test_client.post(
                "/api/v1/data-analysis/query-database",
                json={"connection_id": str(uuid.uuid4()), "query": "SELECT * FROM test", "limit": 100},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_query_database_failure(self, client):
        """Test database query failure."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.data_analysis.DataAnalysisService") as MockService:
            mock_service = MockService.return_value
            mock_service.query_database_connection = AsyncMock(
                return_value={"success": False, "message": "Query failed", "error": "SQL syntax error"}
            )

            response = test_client.post(
                "/api/v1/data-analysis/query-database",
                json={"connection_id": str(uuid.uuid4()), "query": "INVALID SQL"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is False

    def test_query_database_exception(self, client):
        """Test database query exception handling."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.data_analysis.DataAnalysisService") as MockService:
            mock_service = MockService.return_value
            mock_service.query_database_connection = AsyncMock(side_effect=Exception("Connection error"))

            response = test_client.post(
                "/api/v1/data-analysis/query-database", json={"connection_id": str(uuid.uuid4()), "query": "SELECT 1"}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is False
        assert "error" in data


class TestExportReport:
    """Tests for report export endpoint."""

    def test_export_csv_success(self, client):
        """Test successful CSV export."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.data_analysis.ReportExportService") as MockService:
            mock_service = MockService.return_value
            mock_service.export_report = AsyncMock(
                return_value={
                    "success": True,
                    "format": "csv",
                    "file_path": "/exports/report.csv",
                    "file_name": "report.csv",
                    "file_size": 1024,
                }
            )

            response = test_client.post(
                "/api/v1/data-analysis/export-report",
                json={"data": [{"id": 1, "name": "Test"}], "format": "csv", "filename": "report"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["format"] == "csv"
        assert "download_url" in data

    def test_export_excel_success(self, client):
        """Test successful Excel export."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.data_analysis.ReportExportService") as MockService:
            mock_service = MockService.return_value
            mock_service.export_report = AsyncMock(
                return_value={
                    "success": True,
                    "format": "xlsx",
                    "file_path": "/exports/report.xlsx",
                    "file_name": "report.xlsx",
                    "file_size": 2048,
                }
            )

            response = test_client.post(
                "/api/v1/data-analysis/export-report", json={"data": [{"id": 1, "name": "Test"}], "format": "excel"}
            )

        assert response.status_code == status.HTTP_200_OK

    def test_export_json_success(self, client):
        """Test successful JSON export."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.data_analysis.ReportExportService") as MockService:
            mock_service = MockService.return_value
            mock_service.export_report = AsyncMock(
                return_value={
                    "success": True,
                    "format": "json",
                    "file_path": "/exports/report.json",
                    "file_name": "report.json",
                    "file_size": 512,
                }
            )

            response = test_client.post(
                "/api/v1/data-analysis/export-report", json={"data": {"key": "value"}, "format": "json"}
            )

        assert response.status_code == status.HTTP_200_OK

    def test_export_with_title(self, client):
        """Test export with title."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.data_analysis.ReportExportService") as MockService:
            mock_service = MockService.return_value
            mock_service.export_report = AsyncMock(
                return_value={
                    "success": True,
                    "format": "html",
                    "file_path": "/exports/report.html",
                    "file_name": "report.html",
                }
            )

            response = test_client.post(
                "/api/v1/data-analysis/export-report",
                json={"data": [{"id": 1}], "format": "html", "title": "My Report"},
            )

        assert response.status_code == status.HTTP_200_OK

    def test_export_invalid_format(self, client):
        """Test export with invalid format."""
        test_client, tenant_id, mock_account, mock_db = client

        response = test_client.post(
            "/api/v1/data-analysis/export-report", json={"data": [{"id": 1}], "format": "invalid"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_export_failure(self, client):
        """Test export failure."""
        test_client, tenant_id, mock_account, mock_db = client

        with patch("src.controllers.data_analysis.ReportExportService") as MockService:
            mock_service = MockService.return_value
            mock_service.export_report = AsyncMock(return_value={"success": False, "message": "Export failed"})

            response = test_client.post(
                "/api/v1/data-analysis/export-report", json={"data": [{"id": 1}], "format": "csv"}
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is False


class TestListConnectors:
    """Tests for listing available connectors."""

    def test_list_connectors_success(self, client):
        """Test listing available connectors."""
        test_client, tenant_id, mock_account, mock_db = client

        response = test_client.get("/api/v1/data-analysis/connectors")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "connectors" in data
        assert "export_formats" in data
        assert len(data["connectors"]) > 0

    def test_list_connectors_contains_expected_types(self, client):
        """Test that connectors include expected types."""
        test_client, tenant_id, mock_account, mock_db = client

        response = test_client.get("/api/v1/data-analysis/connectors")

        data = response.json()
        connector_types = [c["type"] for c in data["connectors"]]

        assert "DATADOG" in connector_types
        assert "DATABRICKS" in connector_types
        assert "DOCKER_LOGS" in connector_types
        assert "CSV_FILE" in connector_types

    def test_list_connectors_export_formats(self, client):
        """Test that export formats are included."""
        test_client, tenant_id, mock_account, mock_db = client

        response = test_client.get("/api/v1/data-analysis/connectors")

        data = response.json()
        export_formats = [f["format"] for f in data["export_formats"]]

        assert "csv" in export_formats
        assert "excel" in export_formats
        assert "json" in export_formats
        assert "html" in export_formats
