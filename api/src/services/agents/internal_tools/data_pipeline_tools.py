"""
Data Pipeline Tools for Synkora Agents.


Provides a tool that queries an external database (BigQuery, Supabase, Postgres, etc.)
optionally filtering by a list of values read from an uploaded S3 CSV/file,
then saves ALL results directly to S3 and returns a presigned download URL.


This bypasses the LLM context window entirely — no row truncation, no fabrication.
"""

import asyncio
import csv
import io
import logging
import os
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


_BATCH_SIZE_MIN = 50
_BATCH_SIZE_MAX = 2000
_DEFAULT_BATCH_SIZE = 500


async def _duckdb_read_column(s3_url: str, column: str) -> list[Any]:
    """
    Use DuckDB to read all (distinct) values from a single column of an S3 file.


    Supports CSV, Parquet, and JSON files (auto-detected by extension).
    Credentials come from env vars: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
    AWS_REGION, AWS_ENDPOINT_URL.
    """
    import duckdb

    def _sync():
        conn = duckdb.connect(":memory:")
        try:
            conn.execute("INSTALL httpfs; LOAD httpfs;")

            access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
            secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
            region = os.getenv("AWS_REGION", "us-east-1")
            endpoint = os.getenv("AWS_ENDPOINT_URL", "")

            if access_key and secret_key:
                conn.execute(f"SET s3_access_key_id='{access_key.replace(chr(39), chr(39) * 2)}'")
                conn.execute(f"SET s3_secret_access_key='{secret_key.replace(chr(39), chr(39) * 2)}'")
                conn.execute(f"SET s3_region='{region}'")

            if endpoint:
                host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
                conn.execute(f"SET s3_endpoint='{host}'")
                conn.execute("SET s3_use_ssl=false")
                conn.execute("SET s3_url_style='path'")

            url_lower = s3_url.lower()
            if url_lower.endswith(".parquet"):
                read_fn = "read_parquet"
            elif url_lower.endswith(".json") or url_lower.endswith(".jsonl"):
                read_fn = "read_json_auto"
            else:
                read_fn = "read_csv_auto"

            # Use double-quoted identifier to handle spaces / mixed-case column names
            safe_col = column.replace('"', '""')
            result = conn.execute(
                f'SELECT DISTINCT "{safe_col}" FROM {read_fn}(\'{s3_url}\') WHERE "{safe_col}" IS NOT NULL'
            )
            df = result.fetchdf()
            return df[column].tolist()
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync)


def _sql_value_list(values: list[Any]) -> str:
    """Format a Python list as a SQL IN-list literal, properly escaped."""
    parts = []
    for v in values:
        if v is None:
            parts.append("NULL")
        elif isinstance(v, str):
            parts.append("'" + v.replace("'", "''") + "'")
        else:
            parts.append(str(v))
    return ", ".join(parts)


async def query_database_to_s3(
    connection_id: str,
    query: str,
    output_s3_key: str | None = None,
    filter_from_s3_url: str | None = None,
    filter_column: str | None = None,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Query an external database and save ALL results directly to S3 as a CSV.


    Two modes:


    1. Direct query (no filter file):
       Runs the SQL query as-is, streams all rows to S3.
       Use this when you already know the criteria or the result set is manageable.


    2. Filtered query with an uploaded S3 file (batch mode):
       Reads a column of values from an uploaded S3 CSV/Parquet/JSON file,
       splits them into batches, and runs the query once per batch, substituting
       {values} in the SQL with the current batch's comma-separated SQL literal.
       All batches are accumulated and saved as one CSV in S3.
       Use this to JOIN an uploaded file's data with an external database at any scale.


    Args:
        connection_id:      UUID of the database connection to query (from internal_list_database_connections).
        query:              SQL to execute. For batch mode, include a placeholder like
                            WHERE user_id IN ({values}) — the tool replaces {values} each batch.
        output_s3_key:      S3 key for the output CSV, e.g. "analysis/results_2026_06_03.csv".
                            Auto-generated under "analysis/" if not provided.
        filter_from_s3_url: S3 URL of the uploaded file containing filter values, e.g.
                            "s3://synkora-storage/data-uploads/.../users.csv".
                            Required for batch mode.
        filter_column:      Column name in the uploaded file to use as filter values,
                            e.g. "user_id" or "email". Required when filter_from_s3_url is set.
        batch_size:         Number of values per batch (default 500, max 2000).
                            Tune down if the database struggles with large IN lists.
        config:             Runtime context injected by the agent framework.


    Returns:
        {
          "success": True,
          "presigned_url": "https://...",   # Share this with the user — valid 7 days
          "s3_key": "analysis/results.csv",
          "row_count": 12345,
          "columns": ["user_id", "balance", ...],
          "batches_run": 50,                # batch mode only
          "message": "..."
        }
    """
    from uuid import UUID

    from sqlalchemy import select

    from src.models.database_connection import DatabaseConnection
    from src.services.agents.internal_tools.database_tools import (
        _execute_generic_query,
        _execute_postgresql_query,
    )
    from src.services.storage.s3_storage import get_s3_storage

    config = config or {}
    runtime_context = config.get("_runtime_context")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available"}

    if isinstance(runtime_context, dict):
        db_session = runtime_context.get("db_session")
        tenant_id = runtime_context.get("tenant_id")
    else:
        db_session = getattr(runtime_context, "db_session", None)
        tenant_id = getattr(runtime_context, "tenant_id", None)

    if not db_session or not tenant_id:
        return {"success": False, "error": "Runtime context incomplete (missing db_session or tenant_id)"}

    # --- Validate the connection is attached to this agent ---
    allowed = getattr(runtime_context, "allowed_database_connections", None) or []
    if not allowed:
        return {
            "success": False,
            "error": "No database connections are attached to this agent. "
            "Attach connections in the agent's Database Connections settings first.",
        }
    if connection_id not in allowed:
        return {
            "success": False,
            "error": f"Connection '{connection_id}' is not attached to this agent. "
            "Use internal_list_database_connections to see available connections.",
        }

    # --- Fetch the DatabaseConnection record ---
    stmt = select(DatabaseConnection).where(
        DatabaseConnection.id == UUID(connection_id),
        DatabaseConnection.tenant_id == UUID(str(tenant_id)),
    )
    result = await db_session.execute(stmt)
    connection = result.scalar_one_or_none()

    if not connection:
        return {"success": False, "error": f"Database connection not found: {connection_id}"}
    if connection.status != "active":
        return {"success": False, "error": f"Database connection is not active: {connection.status}"}

    # --- Validate batch mode args ---
    use_batching = bool(filter_from_s3_url and filter_column)
    if use_batching and "{values}" not in query:
        return {
            "success": False,
            "error": (
                "When using filter_from_s3_url, the query must contain a {values} placeholder. "
                "Example:  WHERE user_id IN ({values})"
            ),
        }

    batch_size = max(_BATCH_SIZE_MIN, min(_BATCH_SIZE_MAX, int(batch_size)))

    # --- Auto-generate output_s3_key if not provided ---
    if not output_s3_key:
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_s3_key = f"analysis/{tenant_id}/{ts}_results.csv"
    elif not output_s3_key.startswith("analysis/"):
        output_s3_key = f"analysis/{output_s3_key}"

    # --- Helper: run one SQL query on the connection ---
    db_type = str(connection.database_type).upper()

    async def _run(sql: str) -> dict[str, Any]:
        if db_type == "POSTGRESQL":
            return await _execute_postgresql_query(connection, sql)
        return await _execute_generic_query(connection, sql)

    # ----------------------------------------------------------------
    # Execute queries
    # ----------------------------------------------------------------
    all_rows: list[dict] = []
    columns: list[str] = []
    batches_run = 0

    if use_batching:
        # Step 1: read all filter values from the S3 file
        try:
            filter_values = await _duckdb_read_column(filter_from_s3_url, filter_column)  # type: ignore[arg-type]
        except Exception as exc:
            return {"success": False, "error": f"Failed to read '{filter_column}' from S3 file: {exc}"}

        if not filter_values:
            return {
                "success": False,
                "error": f"Column '{filter_column}' is empty or not found in {filter_from_s3_url}",
            }

        total_values = len(filter_values)
        batches = [filter_values[i : i + batch_size] for i in range(0, total_values, batch_size)]
        logger.info(
            "query_database_to_s3: %d distinct filter values → %d batches of %d",
            total_values,
            len(batches),
            batch_size,
        )

        # Step 2: query DB in batches
        for idx, batch in enumerate(batches):
            sql = query.replace("{values}", _sql_value_list(batch))
            qr = await _run(sql)

            if not qr.get("success"):
                logger.warning(
                    "query_database_to_s3: batch %d/%d failed: %s",
                    idx + 1,
                    len(batches),
                    qr.get("error"),
                )
                continue

            batch_rows = qr.get("data") or qr.get("rows") or []
            if not columns and qr.get("columns"):
                columns = qr["columns"]
            all_rows.extend(batch_rows)
            batches_run += 1

            if (idx + 1) % 10 == 0 or (idx + 1) == len(batches):
                logger.info(
                    "query_database_to_s3: %d/%d batches done, %d rows so far",
                    idx + 1,
                    len(batches),
                    len(all_rows),
                )
    else:
        # Single query, no batching
        qr = await _run(query)
        if not qr.get("success"):
            return qr
        all_rows = qr.get("data") or qr.get("rows") or []
        columns = qr.get("columns") or []
        batches_run = 1

    if not columns and all_rows:
        columns = list(all_rows[0].keys())

    # ----------------------------------------------------------------
    # Write results to an in-memory CSV and upload to S3
    # ----------------------------------------------------------------
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(all_rows)
    csv_bytes = buf.getvalue().encode("utf-8")

    s3 = get_s3_storage()

    def _upload():
        upload_result = s3.upload_file(
            file_content=csv_bytes,
            key=output_s3_key,
            content_type="text/csv",
        )
        presigned = s3.generate_presigned_url(key=output_s3_key, expiration=86400 * 7)
        return upload_result, presigned

    try:
        loop = asyncio.get_event_loop()
        upload_result, presigned_url = await loop.run_in_executor(None, _upload)
    except Exception as exc:
        logger.error("query_database_to_s3: S3 upload failed: %s", exc)
        return {"success": False, "error": f"Failed to upload results to S3: {exc}"}

    logger.info(
        "query_database_to_s3: uploaded %d rows to s3://%s/%s",
        len(all_rows),
        upload_result.get("bucket"),
        output_s3_key,
    )

    response: dict[str, Any] = {
        "success": True,
        "presigned_url": presigned_url,
        "s3_key": output_s3_key,
        "s3_uri": upload_result.get("url"),
        "row_count": len(all_rows),
        "columns": columns,
        "message": (
            f"Done. {len(all_rows):,} rows saved to S3. "
            f"Share this download link with the user (valid 7 days): {presigned_url}"
        ),
    }

    if use_batching:
        response["batches_run"] = batches_run
        response["total_filter_values"] = len(filter_values)  # type: ignore[possibly-undefined]

    return response
