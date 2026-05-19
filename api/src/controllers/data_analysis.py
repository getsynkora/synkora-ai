"""Data Analysis API endpoints."""

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time
from typing import Any
from uuid import UUID
from uuid import uuid4 as _uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.core.errors import safe_error_message
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models import Account
from src.services.data_analysis_service import DataAnalysisService
from src.services.report_export_service import ReportExportService

logger = logging.getLogger(__name__)

_TOKEN_MAX_AGE_SECONDS = 3600  # Tokens expire after 1 hour


def _make_download_token(file_path: str) -> str:
    """Create a signed, time-stamped download token for a file path."""
    secret = os.getenv("SECRET_KEY", "").encode()
    ts = str(int(time.time()))
    sig = hmac.new(secret, f"{ts}:{file_path}".encode(), hashlib.sha256).hexdigest()
    payload = base64.urlsafe_b64encode(json.dumps({"path": file_path, "ts": ts, "sig": sig}).encode()).decode()
    return payload


def _verify_download_token(token: str) -> str | None:
    """Verify a signed download token and return the file path if valid.

    Returns the decoded file path on success, or None if the token is invalid,
    expired, or the HMAC does not match.
    """
    try:
        secret = os.getenv("SECRET_KEY", "").encode()
        decoded = json.loads(base64.urlsafe_b64decode(token.encode()).decode())
        file_path = decoded["path"]
        ts = decoded["ts"]
        provided_sig = decoded["sig"]

        # Verify signature using constant-time comparison
        expected_sig = hmac.new(secret, f"{ts}:{file_path}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(provided_sig, expected_sig):
            logger.warning("Download token HMAC mismatch")
            return None

        # Check expiry
        if int(time.time()) - int(ts) > _TOKEN_MAX_AGE_SECONDS:
            logger.warning("Download token has expired")
            return None

        return file_path
    except Exception:
        return None


router = APIRouter(prefix="/api/v1/data-analysis", tags=["data-analysis"])


# Request/Response Models
class UploadFileResponse(BaseModel):
    """Response model for file upload."""

    success: bool
    message: str | None = None
    file_path: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    file_type: str | None = None
    statistics: dict[str, Any] | None = None
    data_preview: list[dict[str, Any]] | None = None


class QueryDataSourceRequest(BaseModel):
    """Request model for querying data source."""

    data_source_id: int
    query_params: dict[str, Any] = Field(default_factory=dict)


class QueryDatabaseRequest(BaseModel):
    """Request model for querying database."""

    connection_id: str
    query: str
    limit: int | None = Field(None, gt=0, le=10000)


class ExportReportRequest(BaseModel):
    """Request model for exporting report."""

    data: list[dict[str, Any]] | dict[str, Any]
    format: str = Field(..., pattern="^(csv|excel|xlsx|json|html)$")
    filename: str | None = None
    title: str | None = None


class DataAnalysisResponse(BaseModel):
    """Response model for data analysis."""

    success: bool
    message: str | None = None
    data: Any = None
    error: str | None = None


class ReportExportResponse(BaseModel):
    """Response model for report export."""

    success: bool
    message: str | None = None
    format: str | None = None
    file_path: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    download_url: str | None = None


# Endpoints
@router.post("/upload-file", response_model=UploadFileResponse)
async def upload_analysis_file(
    file: UploadFile = File(...),
    file_type: str = Query("auto", pattern="^(auto|csv|zip)$"),
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> UploadFileResponse:
    """
    Upload CSV or ZIP file for data analysis.

    Args:
        file: File to upload
        file_type: Type of file (auto, csv, zip)
        db: Database session
        current_account: Authenticated user
        tenant_id: Current tenant ID

    Returns:
        Upload result with file info and data preview
    """
    try:
        # Streaming size check — file.size is unreliable for chunked uploads
        MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
        chunks = []
        total_size = 0
        while chunk := await file.read(65536):  # 64 KB chunks
            total_size += len(chunk)
            if total_size > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="File exceeds maximum size of 100 MB",
                )
            chunks.append(chunk)
        file_content = b"".join(chunks)

        # Validate file type by extension
        if not file.filename.endswith((".csv", ".zip")):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only CSV and ZIP files are supported")

        # Security validation — magic-number check, dangerous extension check, etc.
        from src.services.security.file_security import FileSecurityService

        file_security = FileSecurityService()
        validation = file_security.validate_file(file_content, file.filename, "document")
        if not validation.get("is_valid", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File rejected: {'; '.join(validation.get('errors', ['security check failed']))}",
            )

        # Reset the SpooledTemporaryFile so DataAnalysisService can read from it
        await file.seek(0)

        # Process file
        service = DataAnalysisService(db, tenant_id)
        result = await service.upload_and_process_file(file, file_type)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message", "File processing failed")
            )

        logger.info(f"File uploaded successfully: {file.filename}")

        return UploadFileResponse(
            success=True,
            message="File uploaded and processed successfully",
            file_path=result.get("file_path"),
            file_name=result.get("file_name"),
            file_size=result.get("file_size"),
            file_type=result.get("file_type"),
            statistics=result.get("statistics"),
            data_preview=result.get("data_preview"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=safe_error_message(e, "Failed to upload file", include_type=True),
        )


@router.post("/query-data-source", response_model=DataAnalysisResponse)
async def query_data_source(
    request: QueryDataSourceRequest,
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> DataAnalysisResponse:
    """
    Query data from a configured data source (Datadog, Databricks, Docker).

    Args:
        request: Query request with data source ID and parameters
        db: Database session
        current_account: Authenticated user
        tenant_id: Current tenant ID

    Returns:
        Query results
    """
    try:
        service = DataAnalysisService(db, tenant_id)
        result = await service.query_data_source(request.data_source_id, request.query_params)

        if not result.get("success"):
            return DataAnalysisResponse(success=False, message=result.get("message"), error=result.get("error"))

        return DataAnalysisResponse(success=True, message="Query executed successfully", data=result)

    except Exception as e:
        logger.error(f"Error querying data source: {e}", exc_info=True)
        msg = safe_error_message(e, "Query failed", include_type=False)
        return DataAnalysisResponse(success=False, message=msg, error=msg)


@router.post("/query-database", response_model=DataAnalysisResponse)
async def query_database(
    request: QueryDatabaseRequest,
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> DataAnalysisResponse:
    """
    Query data from a configured database connection.

    Args:
        request: Query request with connection ID and SQL query
        db: Database session
        current_account: Authenticated user
        tenant_id: Current tenant ID

    Returns:
        Query results
    """
    try:
        service = DataAnalysisService(db, tenant_id)
        result = await service.query_database_connection(UUID(request.connection_id), request.query, request.limit)

        if not result.get("success"):
            return DataAnalysisResponse(success=False, message=result.get("message"), error=result.get("error"))

        return DataAnalysisResponse(success=True, message="Query executed successfully", data=result)

    except Exception as e:
        logger.error(f"Error querying database: {e}", exc_info=True)
        msg = safe_error_message(e, "Query failed", include_type=False)
        return DataAnalysisResponse(success=False, message=msg, error=msg)


@router.post("/export-report", response_model=ReportExportResponse)
async def export_report(
    request: ExportReportRequest,
    db: AsyncSession = Depends(get_async_db),
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> ReportExportResponse:
    """
    Export analysis results to various formats (CSV, Excel, JSON, HTML, PDF).

    Args:
        request: Export request with data and format
        db: Database session
        current_account: Authenticated user
        tenant_id: Current tenant ID

    Returns:
        Export result with file info
    """
    try:
        service = ReportExportService(db, tenant_id)

        # Prepare kwargs
        kwargs = {}
        if request.title:
            kwargs["title"] = request.title

        result = await service.export_report(request.data, request.format, request.filename, **kwargs)

        if not result.get("success"):
            return ReportExportResponse(
                success=False,
                message=result.get("message"),
            )

        # Generate a signed download URL (path is never exposed in plain text)
        file_path = result.get("file_path", "")
        download_url = f"/api/v1/analysis/download?token={_make_download_token(file_path)}" if file_path else None

        return ReportExportResponse(
            success=True,
            message="Report exported successfully",
            format=result.get("format"),
            file_path=result.get("file_path"),
            file_name=result.get("file_name"),
            file_size=result.get("file_size"),
            download_url=download_url,
        )

    except Exception as e:
        logger.error(f"Error exporting report: {e}", exc_info=True)
        return ReportExportResponse(success=False, message=safe_error_message(e, "Export failed", include_type=False))


@router.get("/download")
async def download_analysis_file(
    token: str = Query(..., description="Signed download token from export endpoint"),
    current_account: Account = Depends(get_current_account),
) -> Any:
    """
    Download an exported analysis file using a signed token.

    The token is issued by the export endpoint and contains an HMAC-signed
    file path.  Tokens expire after 1 hour.
    """
    import mimetypes
    import pathlib

    from fastapi.responses import FileResponse

    file_path = _verify_download_token(token)
    if not file_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired download token")

    # Prevent path traversal — ensure the resolved path stays within /tmp
    resolved = pathlib.Path(file_path).resolve()
    if not str(resolved).startswith("/tmp/"):
        logger.warning("Download token contained path outside /tmp: %s", file_path)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid download token")

    if not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found or has been removed")

    media_type, _ = mimetypes.guess_type(str(resolved))
    return FileResponse(
        path=str(resolved),
        filename=resolved.name,
        media_type=media_type or "application/octet-stream",
    )


@router.get("/connectors", response_model=dict[str, Any])
async def list_available_connectors(current_account: Account = Depends(get_current_account)) -> dict[str, Any]:
    """
    List available data analysis connectors.

    Args:
        current_account: Authenticated user

    Returns:
        List of available connectors with their capabilities
    """
    return {
        "connectors": [
            {
                "type": "DATADOG",
                "name": "Datadog",
                "description": "Fetch metrics and logs from Datadog monitoring platform",
                "capabilities": ["metrics", "logs"],
                "config_fields": [
                    {"name": "api_key", "type": "string", "required": True, "sensitive": True},
                    {"name": "app_key", "type": "string", "required": True, "sensitive": True},
                    {"name": "site", "type": "string", "required": False, "default": "datadoghq.com"},
                ],
            },
            {
                "type": "DATABRICKS",
                "name": "Databricks",
                "description": "Execute SQL queries on Databricks data lakehouse",
                "capabilities": ["sql_query", "table_list"],
                "config_fields": [
                    {"name": "host", "type": "string", "required": True},
                    {"name": "token", "type": "string", "required": True, "sensitive": True},
                    {"name": "http_path", "type": "string", "required": True},
                    {"name": "catalog", "type": "string", "required": False, "default": "main"},
                    {"name": "schema", "type": "string", "required": False, "default": "default"},
                ],
            },
            {
                "type": "DOCKER_LOGS",
                "name": "Docker Logs",
                "description": "Fetch logs from Docker containers",
                "capabilities": ["logs", "container_list"],
                "config_fields": [
                    {"name": "host", "type": "string", "required": False, "default": "unix:///var/run/docker.sock"},
                    {"name": "container_ids", "type": "array", "required": False},
                    {"name": "container_names", "type": "array", "required": False},
                ],
            },
            {
                "type": "CSV_FILE",
                "name": "CSV File Upload",
                "description": "Upload and analyze CSV files",
                "capabilities": ["file_upload", "statistics"],
                "config_fields": [],
            },
            {
                "type": "ZIP_FILE",
                "name": "ZIP File Upload",
                "description": "Upload and analyze ZIP files containing CSV data",
                "capabilities": ["file_upload", "multi_file"],
                "config_fields": [],
            },
        ],
        "export_formats": [
            {"format": "csv", "name": "CSV", "description": "Comma-separated values"},
            {"format": "excel", "name": "Excel", "description": "Microsoft Excel spreadsheet (.xlsx)"},
            {"format": "json", "name": "JSON", "description": "JavaScript Object Notation"},
            {"format": "html", "name": "HTML", "description": "HTML table report"},
        ],
    }


# ---------------------------------------------------------------------------
# Presigned upload URL for large data files (CSV, Parquet, JSON, TSV)
# ---------------------------------------------------------------------------

_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9._\-]")
_ALLOWED_UPLOAD_CONTENT_TYPES = {
    "text/csv",
    "text/tab-separated-values",
    "application/json",
    "application/octet-stream",  # .parquet often arrives with this type
}


@router.get("/upload-presigned-url")
async def get_analysis_upload_presigned_url(
    filename: str,
    content_type: str = "text/csv",
    tenant_id: UUID = Depends(get_current_tenant_id),
) -> dict[str, Any]:
    """
    Return a presigned S3 PUT URL so the browser can upload a large data file
    directly to S3 without routing through the API server.

    The caller must HTTP PUT the file body to ``upload_url`` with a matching
    ``Content-Type`` header.  After upload completes, pass ``s3_url`` to the
    agent's ``query_file_with_duckdb`` tool.
    """
    from datetime import UTC, datetime

    from src.services.storage.s3_storage import S3StorageService

    if content_type not in _ALLOWED_UPLOAD_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"content_type must be one of: {', '.join(sorted(_ALLOWED_UPLOAD_CONTENT_TYPES))}",
        )

    # Sanitise filename — replace anything that isn't alphanumeric, dot, dash, underscore,
    # then collapse any remaining ".." sequences to prevent path traversal in the S3 key.
    safe_name = _SAFE_FILENAME_RE.sub("_", filename)
    safe_name = safe_name.replace("..", "_")
    if not safe_name or safe_name.strip("_").strip(".") == "":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")

    file_id = str(_uuid4())
    date_path = datetime.now(UTC).strftime("%Y/%m/%d")
    s3_key = f"data-uploads/{tenant_id}/{date_path}/{file_id}_{safe_name}"

    storage = S3StorageService()
    upload_url: str = storage.presigned_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": storage.bucket_name,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=3600,
    )

    return {
        "upload_url": upload_url,
        "s3_key": s3_key,
        "s3_url": f"s3://{storage.bucket_name}/{s3_key}",
        "expires_in": 3600,
    }
