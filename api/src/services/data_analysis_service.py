"""Data Analysis Service for processing and analyzing data from various sources."""

import asyncio
import csv
import io
import logging
import zipfile
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pandas as pd
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.storage import get_storage_service
from src.models.data_source import DataSource, DataSourceType
from src.models.database_connection import DatabaseConnection
from src.services.data_sources.databricks_connector import DatabricksConnector
from src.services.data_sources.datadog_connector import DatadogConnector
from src.services.data_sources.docker_logs_connector import DockerLogsConnector
from src.services.database import (
    BigQueryConnector,
    ClickHouseConnector,
    DuckDBConnector,
    ElasticsearchConnector,
    MongoDBConnector,
    MySQLConnector,
    PostgreSQLConnector,
    SnowflakeConnector,
    SQLiteConnector,
    SQLServerConnector,
    SupabaseConnector,
)
from src.services.database import (
    DatabricksConnector as DBDatabricksConnector,
)
from src.services.database import (
    DatadogConnector as DBDatadogConnector,
)
from src.services.database import (
    DockerConnector as DBDockerConnector,
)

logger = logging.getLogger(__name__)

# SECURITY: Maximum allowed LIMIT value to prevent DoS
MAX_LIMIT = 10000
DEFAULT_LIMIT = 1000

# Formula injection prefixes that are dangerous in spreadsheet apps
_FORMULA_PREFIXES = ("=", "+", "-", "@")


async def _run_sync(fn, *args):
    """Run a blocking function in the default executor without stalling the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, fn, *args)


def _sanitize_formula(value: Any) -> Any:
    """Prefix spreadsheet formula triggers with a single quote so they render as text."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


class DataAnalysisService:
    """Service for data analysis operations."""

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        """Initialize data analysis service.

        Args:
            db: Async database session
            tenant_id: Tenant ID
        """
        self.db = db
        self.tenant_id = tenant_id
        self.storage = get_storage_service()

    async def upload_and_process_file(self, file: UploadFile, file_type: str = "auto") -> dict[str, Any]:
        """Upload and process CSV or ZIP file for analysis.

        Args:
            file: Uploaded file
            file_type: Type of file (csv, zip, or auto-detect)

        Returns:
            Dict with file info and processed data summary
        """
        try:
            # Auto-detect file type if needed
            if file_type == "auto":
                if file.filename.endswith(".csv"):
                    file_type = "csv"
                elif file.filename.endswith(".zip"):
                    file_type = "zip"
                else:
                    # Try to detect from content
                    content = await file.read(1024)
                    await file.seek(0)

                    if b"PK\x03\x04" in content[:4]:  # ZIP magic number
                        file_type = "zip"
                    else:
                        file_type = "csv"

            # Process based on type
            if file_type == "csv":
                result = await self._process_csv_file(file)
            elif file_type == "zip":
                result = await self._process_zip_file(file)
            else:
                return {"success": False, "message": f"Unsupported file type: {file_type}"}

            # Store file in storage
            file_path = f"data-analysis/{self.tenant_id}/{datetime.now(UTC).strftime('%Y/%m/%d')}/{file.filename}"
            await file.seek(0)
            stored_path = await self.storage.upload_file(file.file, file_path)

            result["file_path"] = stored_path
            result["file_name"] = file.filename
            result["file_size"] = file.size

            return result

        except Exception as e:
            logger.error(f"Failed to upload and process file: {e}")
            return {"success": False, "message": f"File processing failed: {str(e)}", "error": str(e)}

    async def _process_csv_file(self, file: UploadFile) -> dict[str, Any]:
        """Process CSV file.

        Args:
            file: CSV file

        Returns:
            Dict with CSV processing results
        """
        try:
            # Read CSV content
            content = await file.read()

            # Detect delimiter and encoding
            sample = content[:10000].decode("utf-8", errors="ignore")
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter

            # PERFORMANCE: Run blocking pandas work off the event loop
            def _parse_csv():
                _df = pd.read_csv(io.BytesIO(content), delimiter=delimiter)
                _stats = {
                    "rows": len(_df),
                    "columns": len(_df.columns),
                    "column_names": _df.columns.tolist(),
                    "data_types": _df.dtypes.astype(str).to_dict(),
                    "missing_values": _df.isnull().sum().to_dict(),
                    "sample_data": _df.head(10).to_dict(orient="records"),
                }
                _numeric_stats = {}
                for col in _df.select_dtypes(include=["number"]).columns:
                    _numeric_stats[col] = {
                        "min": float(_df[col].min()),
                        "max": float(_df[col].max()),
                        "mean": float(_df[col].mean()),
                        "median": float(_df[col].median()),
                        "std": float(_df[col].std()),
                    }
                _preview = _df.head(100).to_dict(orient="records")
                return _stats, _numeric_stats, _preview

            stats, numeric_stats, preview = await _run_sync(_parse_csv)

            return {
                "success": True,
                "file_type": "csv",
                "delimiter": delimiter,
                "statistics": stats,
                "numeric_statistics": numeric_stats,
                "data_preview": preview,
            }

        except Exception as e:
            logger.error(f"Failed to process CSV file: {e}")
            return {"success": False, "message": f"CSV processing failed: {str(e)}", "error": str(e)}

    @staticmethod
    def _is_safe_zip_member(member_name: str) -> bool:
        """
        Check if a ZIP member name is safe (no path traversal).

        SECURITY: Prevents ZIP slip attacks where malicious archives contain
        entries like "../../../etc/passwd" to escape the extraction directory.

        Args:
            member_name: Name of the ZIP member

        Returns:
            True if safe, False if potentially malicious
        """
        # Reject absolute paths
        if member_name.startswith("/") or member_name.startswith("\\"):
            return False

        # Reject path traversal sequences
        if ".." in member_name:
            return False

        # Reject names with null bytes (can be used for null byte injection)
        if "\x00" in member_name:
            return False

        # Normalize and check for traversal after normalization
        import os

        normalized = os.path.normpath(member_name)
        if normalized.startswith("..") or normalized.startswith("/"):
            return False

        return True

    async def _process_zip_file(self, file: UploadFile) -> dict[str, Any]:
        """Process ZIP file containing multiple CSV files.

        SECURITY: Validates all member names to prevent path traversal attacks.

        Args:
            file: ZIP file

        Returns:
            Dict with ZIP processing results
        """
        try:
            # Read ZIP content
            content = await file.read()

            # SECURITY: Zip bomb protection — cap total uncompressed size at 512 MB
            MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024  # 512 MB
            MAX_CSV_BYTES = 64 * 1024 * 1024  # 64 MB per individual CSV file

            # Extract ZIP
            with zipfile.ZipFile(io.BytesIO(content)) as zip_file:
                file_list = zip_file.namelist()

                # SECURITY: Check total uncompressed size before extracting anything
                info_list = zip_file.infolist()
                total_uncompressed = sum(info.file_size for info in info_list)

                # Check file count (zip bomb via many tiny files)
                if len(file_list) > 200:
                    return {
                        "success": False,
                        "message": f"ZIP archive contains too many files ({len(file_list)}). Maximum is 200.",
                    }

                if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                    return {
                        "success": False,
                        "message": f"ZIP archive exceeds maximum uncompressed size ({MAX_UNCOMPRESSED_BYTES // 1024 // 1024} MB)",
                    }

                # Check compression ratio (zip bomb detection)
                compressed_size = len(content)
                if compressed_size > 0 and total_uncompressed / compressed_size > 100:
                    return {
                        "success": False,
                        "message": "ZIP archive has suspicious compression ratio. Possible zip bomb.",
                    }

                # SECURITY: Filter out unsafe file names (path traversal protection)
                safe_files = []
                unsafe_files = []
                for name in file_list:
                    if self._is_safe_zip_member(name):
                        safe_files.append(name)
                    else:
                        unsafe_files.append(name)
                        logger.warning(f"SECURITY: Rejected unsafe ZIP member: {name}")

                csv_files = [f for f in safe_files if f.endswith(".csv")]

                results = {}
                for csv_filename in csv_files[:10]:  # Limit to first 10 CSV files
                    try:
                        # SECURITY: Double-check the filename is safe before opening
                        if not self._is_safe_zip_member(csv_filename):
                            logger.warning(f"SECURITY: Skipping unsafe CSV file: {csv_filename}")
                            continue

                        # SECURITY: Check individual file size before reading
                        member_info = zip_file.getinfo(csv_filename)
                        if member_info.file_size > MAX_CSV_BYTES:
                            results[csv_filename] = {
                                "error": f"CSV exceeds maximum size ({MAX_CSV_BYTES // 1024 // 1024} MB)"
                            }
                            continue

                        with zip_file.open(csv_filename) as csv_file:
                            # PERFORMANCE: Read CSV bytes first, then parse off event loop
                            raw = csv_file.read()

                        def _parse_zip_csv(b):
                            _df = pd.read_csv(io.BytesIO(b))
                            return {
                                "rows": len(_df),
                                "columns": len(_df.columns),
                                "column_names": _df.columns.tolist(),
                                "sample_data": _df.head(5).to_dict(orient="records"),
                            }

                        results[csv_filename] = await _run_sync(_parse_zip_csv, raw)
                    except Exception as e:
                        results[csv_filename] = {"error": str(e)}

                response = {
                    "success": True,
                    "file_type": "zip",
                    "total_files": len(file_list),
                    "csv_files_count": len(csv_files),
                    "processed_files": len(results),
                    "files": results,
                }

                # Include warning if unsafe files were found
                if unsafe_files:
                    response["security_warning"] = f"{len(unsafe_files)} file(s) with unsafe names were skipped"

                return response

        except Exception as e:
            logger.error(f"Failed to process ZIP file: {e}")
            return {"success": False, "message": f"ZIP processing failed: {str(e)}", "error": str(e)}

    async def query_data_source(self, data_source_id: int, query_params: dict[str, Any]) -> dict[str, Any]:
        """Query data from a data source (DataSource table, integer ID).

        Args:
            data_source_id: Integer ID from the data_sources table
            query_params: Query parameters specific to the data source type

        Returns:
            Dict with query results
        """
        try:
            stmt = select(DataSource).filter(DataSource.id == data_source_id, DataSource.tenant_id == self.tenant_id)
            result = await self.db.execute(stmt)
            data_source = result.scalar_one_or_none()

            if not data_source:
                return {"success": False, "message": "Data source not found"}

            # Route to appropriate connector
            if data_source.type == DataSourceType.DATADOG:
                connector = DatadogConnector(data_source, self.db)

                if query_params.get("query_type") == "metrics":
                    result = await connector.fetch_metrics(
                        query=query_params.get("query"),
                        from_time=query_params.get("from_time"),
                        to_time=query_params.get("to_time"),
                    )
                else:  # logs
                    result = await connector.fetch_logs(
                        query=query_params.get("query"),
                        from_time=query_params.get("from_time"),
                        to_time=query_params.get("to_time"),
                        limit=query_params.get("limit", 1000),
                    )

            elif data_source.type == DataSourceType.DATABRICKS:
                connector = DatabricksConnector(data_source, self.db)
                result = await connector.execute_query(query=query_params.get("query"), limit=query_params.get("limit"))

            elif data_source.type == DataSourceType.DOCKER_LOGS:
                connector = DockerLogsConnector(data_source, self.db)

                if query_params.get("container_id") or query_params.get("container_name"):
                    result = await connector.fetch_logs(
                        container_id=query_params.get("container_id"),
                        container_name=query_params.get("container_name"),
                        since=query_params.get("since"),
                        tail=query_params.get("tail", 1000),
                    )
                else:
                    result = await connector.fetch_all_configured_logs(
                        since=query_params.get("since"), tail=query_params.get("tail", 1000)
                    )

            else:
                return {"success": False, "message": f"Query not supported for data source type: {data_source.type}"}

            return result

        except Exception as e:
            # Roll back the aborted transaction so subsequent operations on this session still work
            await self.db.rollback()
            logger.error(f"Failed to query data source: {e}")
            return {"success": False, "message": f"Query failed: {str(e)}", "error": str(e)}

    async def query_datadog_connection(
        self, connection_id: UUID, query: str, from_time: str | None = None, to_time: str | None = None
    ) -> dict[str, Any]:
        """Query metrics from a Datadog DatabaseConnection (UUID ID).

        Args:
            connection_id: UUID of the DatabaseConnection record
            query: Datadog metric query string (e.g. 'avg:system.cpu.user{*}')
            from_time: Start time in ISO-8601 format (e.g. '2024-01-01T00:00:00Z')
            to_time: End time in ISO-8601 format

        Returns:
            Dict with metric series data
        """
        try:
            stmt = select(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id, DatabaseConnection.tenant_id == self.tenant_id
            )
            result = await self.db.execute(stmt)
            connection = result.scalar_one_or_none()

            if not connection:
                return {"success": False, "message": "Database connection not found"}

            connector = DBDatadogConnector(database_connection=connection)

            # Convert time strings to Unix timestamps expected by the Datadog API.
            # Supports ISO-8601 (e.g. '2024-01-01T00:00:00Z') and relative strings
            # (e.g. 'now', 'now-24h', 'now-1d', 'now-30m', 'now-1w').
            def _to_unix(t: str) -> int:
                import re
                from datetime import UTC, timedelta

                t = t.strip()
                if t == "now":
                    return int(datetime.now(UTC).timestamp())
                m = re.fullmatch(r"now-(\d+)([smhdw])", t)
                if m:
                    n, unit = int(m.group(1)), m.group(2)
                    delta = {
                        "s": timedelta(seconds=n),
                        "m": timedelta(minutes=n),
                        "h": timedelta(hours=n),
                        "d": timedelta(days=n),
                        "w": timedelta(weeks=n),
                    }[unit]
                    return int((datetime.now(UTC) - delta).timestamp())
                return int(datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp())

            params: dict[str, Any] = {}
            if from_time:
                params["from"] = _to_unix(from_time)
            if to_time:
                params["to"] = _to_unix(to_time)

            return await connector.execute_query(query=query, params=params or None)

        except Exception as e:
            logger.error(f"Failed to query Datadog connection: {e}")
            return {"success": False, "message": f"Query failed: {str(e)}", "error": str(e)}

    async def query_databricks_connection(
        self, connection_id: UUID, query: str, limit: int | None = None
    ) -> dict[str, Any]:
        """Execute a SQL query on a Databricks DatabaseConnection (UUID ID).

        Args:
            connection_id: UUID of the DatabaseConnection record
            query: SQL query to execute
            limit: Maximum rows to return (appended as LIMIT clause if not already present)

        Returns:
            Dict with columns, rows, and row_count
        """
        try:
            stmt = select(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id, DatabaseConnection.tenant_id == self.tenant_id
            )
            result = await self.db.execute(stmt)
            connection = result.scalar_one_or_none()

            if not connection:
                return {"success": False, "message": "Database connection not found"}

            # SECURITY: Validate and sanitize LIMIT value to prevent SQL injection
            if limit is not None and "LIMIT" not in query.upper():
                if isinstance(limit, int) and 1 <= limit <= MAX_LIMIT:
                    query = f"{query} LIMIT {int(limit)}"
                else:
                    query = f"{query} LIMIT {DEFAULT_LIMIT}"

            connector = DBDatabricksConnector(database_connection=connection)
            return await connector.execute_query(query=query)

        except Exception as e:
            logger.error(f"Failed to query Databricks connection: {e}")
            return {"success": False, "message": f"Query failed: {str(e)}", "error": str(e)}

    async def query_docker_connection(self, connection_id: UUID, query: str) -> dict[str, Any]:
        """Query a Docker daemon via a DatabaseConnection (UUID ID).

        Args:
            connection_id: UUID of the DatabaseConnection record
            query: Docker pseudo-query keyword (e.g. 'containers', 'logs <container_id>')

        Returns:
            Dict with container/log data
        """
        try:
            stmt = select(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id, DatabaseConnection.tenant_id == self.tenant_id
            )
            result = await self.db.execute(stmt)
            connection = result.scalar_one_or_none()

            if not connection:
                return {"success": False, "message": "Database connection not found"}

            connector = DBDockerConnector(database_connection=connection)
            return await connector.execute_query(query=query)

        except Exception as e:
            logger.error(f"Failed to query Docker connection: {e}")
            return {"success": False, "message": f"Query failed: {str(e)}", "error": str(e)}

    async def query_database_connection(
        self, connection_id: UUID, query: str, limit: int | None = None
    ) -> dict[str, Any]:
        """Query data from a database connection.

        Args:
            connection_id: Database connection ID
            query: SQL query
            limit: Maximum rows to return

        Returns:
            Dict with query results
        """
        try:
            stmt = select(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id, DatabaseConnection.tenant_id == self.tenant_id
            )
            result = await self.db.execute(stmt)
            connection = result.scalar_one_or_none()

            if not connection:
                return {"success": False, "message": "Database connection not found"}

            # SECURITY: Validate and sanitize LIMIT value to prevent SQL injection
            if limit is not None and "LIMIT" not in query.upper():
                # Ensure limit is a valid integer within bounds
                if isinstance(limit, int) and 1 <= limit <= MAX_LIMIT:
                    query = f"{query} LIMIT {int(limit)}"
                else:
                    query = f"{query} LIMIT {DEFAULT_LIMIT}"

            # database_type is stored as a plain string in the DB (Mapped[str]).
            # Normalise once so all comparisons below are safe regardless of whether
            # the column returned a string or an enum object.
            db_type = str(connection.database_type).upper().rsplit(".", 1)[-1]

            # Execute query based on database type
            if db_type == "POSTGRESQL":
                connector = PostgreSQLConnector(database_connection=connection)
                await connector.connect()
                result = await connector.execute_query(query)
                await connector.disconnect()

            elif db_type == "SQLITE":
                connector = SQLiteConnector(database_path=connection.database_path)
                await connector.connect()
                result = await connector.execute_query(query)
                await connector.disconnect()

            elif db_type == "ELASTICSEARCH":
                connector = ElasticsearchConnector(database_connection=connection)
                result = await connector.search(query)

            elif db_type == "MYSQL":
                connector = MySQLConnector(database_connection=connection)
                await connector.connect()
                result = await connector.execute_query(query)
                await connector.disconnect()

            elif db_type == "MONGODB":
                connector = MongoDBConnector(database_connection=connection)
                await connector.connect()
                result = await connector.execute_query(query)
                await connector.disconnect()

            elif db_type == "SUPABASE":
                connector = SupabaseConnector(database_connection=connection)
                await connector.connect()
                result = await connector.execute_query(query)
                await connector.disconnect()

            elif db_type == "BIGQUERY":
                connector = BigQueryConnector(database_connection=connection)
                await connector.connect()
                result = await connector.execute_query(query)
                await connector.disconnect()

            elif db_type == "SNOWFLAKE":
                connector = SnowflakeConnector(database_connection=connection)
                await connector.connect()
                result = await connector.execute_query(query)
                await connector.disconnect()

            elif db_type == "SQLSERVER":
                connector = SQLServerConnector(database_connection=connection)
                await connector.connect()
                result = await connector.execute_query(query)
                await connector.disconnect()

            elif db_type == "CLICKHOUSE":
                connector = ClickHouseConnector(database_connection=connection)
                await connector.connect()
                result = await connector.execute_query(query)
                await connector.disconnect()

            elif db_type == "DUCKDB":
                connector = DuckDBConnector(database_connection=connection)
                await connector.connect()
                result = await connector.execute_query(query)
                await connector.disconnect()

            else:
                return {
                    "success": False,
                    "message": f"Query not supported for database type: {connection.database_type}",
                }

            return {"success": True, "data": result, "query": query}

        except Exception as e:
            logger.error(f"Failed to query database: {e}")
            return {"success": False, "message": f"Query failed: {str(e)}", "error": str(e)}
