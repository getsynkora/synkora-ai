"""Tenant-scoped local analytics with filesystem/network access disabled."""

import asyncio
import logging
import re
from typing import Any

from src.models.database_connection import DatabaseConnection
from src.services.security.local_databases import local_database_path

logger = logging.getLogger(__name__)

# Safe identifier: letter or underscore, then alphanumeric / underscore
VALID_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

DANGEROUS_KEYWORDS = frozenset(
    [
        "select",
        "insert",
        "update",
        "delete",
        "drop",
        "truncate",
        "create",
        "alter",
        "grant",
        "revoke",
        "union",
        "exec",
        "execute",
    ]
)


def _validate_identifier(identifier: str) -> bool:
    """Return True if *identifier* is safe to interpolate into a SQL string."""
    if not identifier:
        return False
    if not VALID_IDENTIFIER_PATTERN.match(identifier):
        logger.warning("Invalid DuckDB identifier rejected: %s", identifier)
        return False
    if identifier.lower() in DANGEROUS_KEYWORDS:
        logger.warning("Dangerous keyword rejected as identifier: %s", identifier)
        return False
    return True


class DuckDBConnector:
    """
    Async-compatible DuckDB connector for in-process analytics.

    All DuckDB operations run in a ``ThreadPoolExecutor`` via
    ``run_in_executor`` so they do not block the asyncio event loop.

    Connection parameters (from ``DatabaseConnection`` model):
        - ``database_path`` — operator-provisioned filename under
          LOCAL_DATABASE_ROOT/<tenant UUID>/, or ``:memory:``.
        Persistent files open read-only. Extensions and remote file access are disabled.

    The interface mirrors ``PostgreSQLConnector`` and ``MySQLConnector``.
    """

    def __init__(
        self,
        database_connection: DatabaseConnection,
        timeout: float = 30.0,
    ):
        """
        Initialise the connector.

        Args:
            database_connection: DatabaseConnection model instance.
            timeout: Query deadline in seconds, capped at 30 seconds.
        """
        self.database_connection = database_connection
        self.timeout = timeout
        self._conn = None  # duckdb.DuckDBPyConnection

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_sync(self, fn, *args):
        """Run a synchronous callable in the default thread-pool executor."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, fn, *args)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """
        Open a restricted in-memory or read-only tenant database.

        Returns:
            True on success, False on failure.
        """
        try:
            import duckdb  # noqa: PLC0415  (deferred — optional dep)
        except ImportError:
            logger.error("duckdb is not installed. Add 'duckdb' to dependencies.")
            return False

        try:
            database_path = local_database_path(
                self.database_connection.database_path, self.database_connection.tenant_id, memory=True
            )
            if (self.database_connection.connection_params or {}).get("extensions"):
                raise ValueError("Extensions are disabled for local analytics")

            def _open() -> Any:
                return duckdb.connect(
                    database_path,
                    read_only=database_path != ":memory:",
                    config={
                        "enable_external_access": "false",
                        "autoload_known_extensions": "false",
                        "autoinstall_known_extensions": "false",
                        "allow_community_extensions": "false",
                        "allow_unsigned_extensions": "false",
                        "lock_configuration": "true",
                        "memory_limit": "128MB",
                        "threads": "1",
                        "max_temp_directory_size": "0B",
                    },
                )

            conn = await self._run_sync(_open)

            self._conn = conn
            logger.info("DuckDB opened: %s", database_path)
            return True

        except Exception as e:
            logger.error("Failed to open DuckDB: %s", e)
            return False

    async def disconnect(self) -> None:
        """Close the DuckDB connection."""
        if self._conn is not None:
            try:
                await self._run_sync(self._conn.close)
            except Exception as e:
                logger.warning("Error while closing DuckDB connection: %s", e)
            finally:
                self._conn = None
                logger.info("DuckDB connection closed")

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    async def execute_query(self, query: str, params: list[Any] | None = None) -> dict[str, Any]:
        """
        Execute a SQL query (or DuckDB special form) and return results.

        Standard SQL runs with external access disabled. Results are limited
        to 10,000 rows and approximately 2 MiB, with a query deadline.

        Args:
            query:  SQL string.  Positional parameters use ``?`` placeholders.
            params: Optional list of parameter values bound to ``?`` placeholders.

        Returns:
            ``{"success": bool, "rows": list[dict], "row_count": int,
               "columns": list[str], "error": str}``
        """
        if self._conn is None:
            return {
                "success": False,
                "rows": [],
                "row_count": 0,
                "columns": [],
                "error": "Not connected. Call connect() first.",
            }

        try:
            if len(query.encode("utf-8")) > 65536:
                raise ValueError("Query is too large")

            def _execute(c=self._conn, q=query, p=params):
                if p:
                    rel = c.execute(q, p)
                else:
                    rel = c.execute(q)
                columns = [item[0] for item in rel.description]
                rows = rel.fetchmany(10001)
                if len(rows) > 10000 or sum(len(str(row)) for row in rows) > 2 * 1024 * 1024:
                    raise ValueError("Query result exceeds the limit")
                return columns, [dict(zip(columns, row, strict=True)) for row in rows]

            pending = self._run_sync(_execute)
            try:
                columns, rows = await asyncio.wait_for(asyncio.shield(pending), timeout=min(self.timeout, 30))
            except (TimeoutError, asyncio.CancelledError):
                self._conn.interrupt()
                try:
                    await pending
                except Exception:
                    pass
                raise

            return {
                "success": True,
                "rows": rows,
                "row_count": len(rows),
                "columns": columns,
            }

        except Exception as e:
            logger.error("DuckDB query failed: %s", e)
            return {
                "success": False,
                "rows": [],
                "row_count": 0,
                "columns": [],
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    async def test_connection(self) -> dict[str, Any]:
        """
        Verify the DuckDB connection is functional.

        Runs ``SELECT 42 AS answer`` and reports the database path plus any
        extensions that were loaded.

        Returns:
            ``{"success": bool, "message": str, "details": dict}``
        """
        connected = await self.connect()
        if not connected:
            return {"success": False, "message": "Failed to open DuckDB", "details": {}}

        try:
            result = await self.execute_query("SELECT 42 AS answer")
            if not result["success"]:
                return {"success": False, "message": "Connected but test query failed", "details": {}}

            conn_params = self.database_connection.connection_params or {}
            database_path = self.database_connection.database_path or ":memory:"
            extensions = conn_params.get("extensions", [])

            return {
                "success": True,
                "message": "Connection successful",
                "details": {
                    "answer": result["rows"][0].get("answer") if result["rows"] else None,
                    "database_path": database_path,
                    "extensions_loaded": extensions,
                },
            }

        except Exception as e:
            logger.error("DuckDB connection test failed: %s", e)
            return {"success": False, "message": f"Connection test failed: {e}", "details": {}}

        finally:
            await self.disconnect()

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    async def get_tables(self) -> list[str]:
        """
        Return the names of all tables currently in the DuckDB database.

        Returns:
            List of table name strings, empty list on error.
        """
        result = await self.execute_query("SHOW TABLES")
        if not result["success"]:
            return []
        return [list(row.values())[0] for row in result["rows"] if row]

    async def get_schema(self) -> dict[str, Any]:
        """
        Return schema information for up to 20 tables.

        For each table, ``DESCRIBE {table}`` is called to collect column
        names and types.

        Returns:
            ``{"success": bool, "tables": [{"name": str, "columns": [{"name": str, "type": str}]}],
               "error": str}``
        """
        try:
            tables = await self.get_tables()
            table_info = []

            for table in tables[:20]:
                if not _validate_identifier(table):
                    logger.warning("Skipping table with unsafe name during schema fetch: %s", table)
                    continue

                describe_result = await self.execute_query(f'DESCRIBE "{table}"')
                if describe_result["success"]:
                    columns = [
                        {
                            "name": row.get("column_name", row.get("Field", "")),
                            "type": row.get("column_type", row.get("Type", "")),
                        }
                        for row in describe_result["rows"]
                    ]
                else:
                    columns = []

                table_info.append({"name": table, "columns": columns})

            return {"success": True, "tables": table_info}

        except Exception as e:
            logger.error("Failed to get DuckDB schema: %s", e)
            return {"success": False, "tables": [], "error": str(e)}

    async def get_table_info(self, table_name: str) -> dict[str, Any]:
        """
        Return column details for a specific table via ``DESCRIBE``.

        Args:
            table_name: Name of the table.  Must match
                        ``[A-Za-z_][A-Za-z0-9_]*``.

        Returns:
            ``{"success": bool, "table_name": str, "columns": [{"name": str, "type": str}],
               "error": str}``
        """
        if not _validate_identifier(table_name):
            return {
                "success": False,
                "table_name": table_name,
                "columns": [],
                "error": f"Invalid or unsafe table name: '{table_name}'",
            }

        result = await self.execute_query(f'DESCRIBE "{table_name}"')
        if not result["success"]:
            return {
                "success": False,
                "table_name": table_name,
                "columns": [],
                "error": result.get("error", "Unknown error"),
            }

        columns = [
            {
                "name": row.get("column_name", row.get("Field", "")),
                "type": row.get("column_type", row.get("Type", "")),
            }
            for row in result["rows"]
        ]

        return {
            "success": True,
            "table_name": table_name,
            "columns": columns,
        }
