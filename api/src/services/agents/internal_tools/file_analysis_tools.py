"""
DuckDB-powered file analysis tool for agents.

Lets agents query large CSV / Parquet / JSON files stored in S3 (or MinIO)
using DuckDB's read_csv_auto() / read_parquet() / read_json_auto() functions.

Only objects under the current tenant's storage prefix are staged for analysis.
DuckDB receives no storage credentials and can access only that staged file.
Engine restrictions are defense in depth; deployment isolation remains required.
"""

import asyncio
import logging
import os
import re
import threading
from typing import Any

logger = logging.getLogger(__name__)

MAX_ROWS = 1_000
MAX_RESULT_CHARS = 50_000
_ANALYSIS_SLOTS = threading.BoundedSemaphore(2)

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
    if any(char in s3_url for char in ("'", "\\", "?", "#", "\x00")):
        return "s3_url contains unsupported characters"
    if ".." in s3_url:
        return "s3_url must not contain '..'"
    return None


def _validate_query(query: str, s3_url: str) -> str | None:
    """Return error message if query is not acceptable, else None."""
    if len(query) > 32768:
        return "Analysis query exceeds size limit"
    if "/*" in query or "--" in query:
        return "SQL comments are not supported in file analysis"
    if not _ALLOWED_READ_FUNCTIONS.search(query):
        return "query must reference read_csv_auto(), read_parquet(), or read_json_auto() as the data source"
    if "'" + s3_url + "'" not in query:
        return "The s3_url must appear inside the query string"
    return None


def _query_local_dataset(query: str, s3_url: str, path: str) -> Any:
    """Execute one SELECT with access only to a staged, authorized dataset."""
    import duckdb
    import pandas as pd

    conn = duckdb.connect(
        ":memory:",
        config={
            "autoinstall_known_extensions": False,
            "autoload_known_extensions": False,
            "allow_community_extensions": False,
            "allow_unsigned_extensions": False,
            "memory_limit": "256MB",
            "threads": 1,
            "max_temp_directory_size": "0B",
        },
    )
    timer = threading.Timer(15, conn.interrupt)
    try:
        conn.execute("SET allowed_paths = ?", [[path]])
        conn.execute("SET enable_external_access = false")
        conn.execute("SET lock_configuration = true")
        statements = conn.extract_statements(query)
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise ValueError("Only one SELECT statement is allowed")
        # The untrusted SQL never receives storage credentials or remote access.
        local_query = query.replace("'" + s3_url + "'", "'" + path.replace("'", "''") + "'")
        timer.start()
        cursor = conn.execute(local_query)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchmany(MAX_ROWS + 1)
        return pd.DataFrame(rows, columns=columns)
    finally:
        timer.cancel()
        if timer.ident is not None:
            timer.join()
        conn.close()


async def _run_duckdb_query(query: str, s3_url: str, tenant_id: Any) -> Any:
    from tempfile import TemporaryDirectory
    from urllib.parse import urlsplit
    from uuid import UUID

    from src.services.storage.s3_storage import get_s3_storage

    tenant = str(UUID(str(tenant_id)))
    source = urlsplit(s3_url)
    storage = get_s3_storage()
    key = source.path.lstrip("/")
    if source.netloc != storage.bucket_name or not key.startswith((f"tenants/{tenant}/", f"data-uploads/{tenant}/")):
        raise ValueError("File does not belong to the current tenant")

    def stage_and_query():
        with TemporaryDirectory(prefix="synkora-analysis-") as directory:
            path = os.path.join(directory, "dataset")
            response = storage.s3_client.get_object(Bucket=storage.bucket_name, Key=key)
            body = response["Body"]
            try:
                total = 0
                with open(path, "wb") as output:
                    while chunk := body.read(65536):
                        total += len(chunk)
                        if total > 64 * 1024 * 1024:
                            raise ValueError("Analysis input exceeds 64 MiB")
                        output.write(chunk)
            finally:
                body.close()
            return _query_local_dataset(query, s3_url, path)

    def run():
        if not _ANALYSIS_SLOTS.acquire(timeout=15):
            raise ValueError("File analysis is busy; please retry")
        try:
            return stage_and_query()
        finally:
            _ANALYSIS_SLOTS.release()

    return await asyncio.to_thread(run)


async def query_file_with_duckdb(
    s3_url: str,
    query: str,
    output_path: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any | None = None,
) -> dict[str, Any]:
    """
    Execute a SQL query against a file stored in S3 / MinIO using DuckDB.

    The query MUST use read_csv_auto(s3_url), read_parquet(s3_url), or
    read_json_auto(s3_url) as its data source.

    Args:
        s3_url:       S3 URL of the uploaded file, e.g. ``s3://bucket/path/file.csv``
        query:        SQL referencing the file via a DuckDB read function.
        output_path:  Optional filename (e.g. ``filtered.csv``) to write the full
                      result set to the workspace. When set, rows are NOT returned
                      inline — use this for large exports so the context stays small.
        config:       Runtime context (credentials come from env vars).
        runtime_context: Runtime context for workspace resolution.

    Returns:
        Without output_path: ``{"success": bool, "rows": list[dict], "row_count": int, ...}``
        With output_path:    ``{"success": bool, "output_path": str, "row_count": int, ...}``
    """
    _empty: dict[str, Any] = {"rows": [], "columns": [], "row_count": 0, "truncated": False}

    url_err = _validate_s3_url(s3_url)
    if url_err:
        return {"success": False, "error": url_err, **_empty}

    query_err = _validate_query(query, s3_url)
    if query_err:
        return {"success": False, "error": query_err, **_empty}

    runtime_context = runtime_context or (config.get("_runtime_context") if config else None)
    tenant_id = getattr(runtime_context, "tenant_id", None)
    if not tenant_id:
        return {"success": False, "error": "Verified tenant context is required", **_empty}

    try:
        df = await _run_duckdb_query(query, s3_url, tenant_id)
    except ImportError:
        return {"success": False, "error": "duckdb is not installed on this server", **_empty}
    except Exception as exc:
        logger.error("DuckDB query failed: %s", exc)
        return {"success": False, "error": str(exc), **_empty}

    total = len(df)
    columns: list[str] = list(df.columns)

    # --- Export to workspace file (preferred for large result sets) ---
    if output_path:
        df = df.head(MAX_ROWS)
        from src.services.agents.internal_tools.storage_tools import _get_workspace_path, _validate_path_in_workspace

        # runtime_context may be injected via config["_runtime_context"] by the ADK framework
        if runtime_context is None and config:
            runtime_context = config.get("_runtime_context")

        workspace_path = _get_workspace_path(config, runtime_context)
        is_valid, err = _validate_path_in_workspace(output_path, workspace_path)
        if not is_valid:
            return {"success": False, "error": err, **_empty}

        # Resolve relative path against workspace
        if workspace_path and not os.path.isabs(output_path):
            resolved = os.path.join(workspace_path, output_path)
        else:
            resolved = output_path

        os.makedirs(os.path.dirname(resolved) if os.path.dirname(resolved) else workspace_path or ".", exist_ok=True)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: df.to_csv(resolved, index=False))
        logger.info(f"DuckDB query results saved to: {resolved} ({total} rows)")

        return {
            "success": True,
            "output_path": resolved,
            "row_count": len(df),
            "truncated": total > MAX_ROWS,
            "columns": columns,
            "message": (
                f"Results ({len(df)} rows, {len(columns)} columns) saved to '{resolved}'. "
                f"Use internal_s3_upload_file with file_path='{output_path}' to upload it."
            ),
        }

    # --- Return rows inline (capped at MAX_ROWS) ---
    truncated = total > MAX_ROWS
    if truncated:
        df = df.head(MAX_ROWS)

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
