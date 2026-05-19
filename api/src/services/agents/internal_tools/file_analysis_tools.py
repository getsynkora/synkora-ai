"""
DuckDB-powered file analysis tool for agents.

Lets agents query large CSV / Parquet / JSON files stored in S3 (or MinIO)
using DuckDB's read_csv_auto() / read_parquet() / read_json_auto() functions.

No DatabaseConnection record is needed — credentials are read from the same
env vars used by S3StorageService (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
AWS_ENDPOINT_URL, AWS_REGION).
"""

import asyncio
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

MAX_ROWS = 1_000
MAX_RESULT_CHARS = 50_000

# Allowed DuckDB table-valued functions for reading remote files.
# The query MUST reference at least one of these — prevents arbitrary
# filesystem reads or table references that could leak server-side data.
_ALLOWED_READ_FUNCTIONS = re.compile(
    r"read_csv_auto\s*\(|read_parquet\s*\(|read_json_auto\s*\(",
    re.IGNORECASE,
)


def _validate_s3_url(s3_url: str) -> str | None:
    """Return error message if s3_url is not safe, else None."""
    if not s3_url.startswith("s3://"):
        return "s3_url must start with s3://"
    if ".." in s3_url:
        return "s3_url must not contain '..'"
    return None


def _validate_query(query: str, s3_url: str) -> str | None:
    """Return error message if query is not acceptable, else None."""
    if not _ALLOWED_READ_FUNCTIONS.search(query):
        return "query must reference read_csv_auto(), read_parquet(), or read_json_auto() as the data source"
    if s3_url not in query:
        return "The s3_url must appear inside the query string"
    return None


async def _run_duckdb_query(query: str) -> Any:
    """
    Execute *query* in a fresh :memory: DuckDB connection inside a
    thread-pool executor (DuckDB's Python API is synchronous).

    S3 / MinIO credentials are read from env vars:
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
        AWS_ENDPOINT_URL (set for MinIO).
    """
    import duckdb  # optional dep — deferred import

    def _sync_run():
        conn = duckdb.connect(":memory:")
        try:
            conn.execute("INSTALL httpfs; LOAD httpfs;")

            region = os.getenv("AWS_REGION", "us-east-1")
            access_key = os.getenv("AWS_ACCESS_KEY_ID", "")
            secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
            endpoint = os.getenv("AWS_ENDPOINT_URL", "")

            if access_key and secret_key:
                conn.execute(f"SET s3_access_key_id='{access_key.replace(chr(39), chr(39) * 2)}'")
                conn.execute(f"SET s3_secret_access_key='{secret_key.replace(chr(39), chr(39) * 2)}'")
                conn.execute(f"SET s3_region='{region}'")

            if endpoint:
                # Strip scheme — DuckDB expects host:port
                host = endpoint.replace("https://", "").replace("http://", "").rstrip("/")
                conn.execute(f"SET s3_endpoint='{host}'")
                conn.execute("SET s3_use_ssl=false")
                conn.execute("SET s3_url_style='path'")

            rel = conn.execute(query)
            return rel.fetchdf()
        finally:
            conn.close()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_run)


async def query_file_with_duckdb(
    s3_url: str,
    query: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute a SQL query against a file stored in S3 / MinIO using DuckDB.

    The query MUST use read_csv_auto(s3_url), read_parquet(s3_url), or
    read_json_auto(s3_url) as its data source.

    Args:
        s3_url:  S3 URL of the uploaded file, e.g. ``s3://bucket/path/file.csv``
        query:   SQL referencing the file via a DuckDB read function.
        config:  Runtime context (not used — credentials come from env vars).

    Returns:
        ``{"success": bool, "rows": list[dict], "row_count": int,
           "columns": list[str], "truncated": bool, "error": str}``
    """
    _empty: dict[str, Any] = {"rows": [], "columns": [], "row_count": 0, "truncated": False}

    url_err = _validate_s3_url(s3_url)
    if url_err:
        return {"success": False, "error": url_err, **_empty}

    query_err = _validate_query(query, s3_url)
    if query_err:
        return {"success": False, "error": query_err, **_empty}

    try:
        df = await _run_duckdb_query(query)
    except ImportError:
        return {"success": False, "error": "duckdb is not installed on this server", **_empty}
    except Exception as exc:
        logger.error("DuckDB query failed: %s", exc)
        return {"success": False, "error": str(exc), **_empty}

    total = len(df)
    truncated = total > MAX_ROWS
    if truncated:
        df = df.head(MAX_ROWS)

    columns: list[str] = list(df.columns)

    import json

    try:
        rows: list[dict] = json.loads(json.dumps(df.to_dict(orient="records"), default=str))
    except Exception:
        rows = [{k: str(v) for k, v in row.items()} for row in df.to_dict(orient="records")]

    return {
        "success": True,
        "rows": rows,
        "row_count": len(rows),
        "columns": columns,
        "truncated": truncated,
        "total_rows_in_result": total,
    }
