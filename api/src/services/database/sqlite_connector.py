"""SQLite database connector with connection management and query execution."""

import logging
import re
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from src.services.security.local_databases import local_database_path

logger = logging.getLogger(__name__)


def _validate_identifier(name: str) -> bool:
    """
    SECURITY: Validate a SQL identifier (table/column name).

    Only allows alphanumeric characters, underscores, and dots.

    Args:
        name: The identifier to validate

    Returns:
        True if valid, False otherwise
    """
    # Only allow alphanumeric, underscore, and dot (for schema.table)
    return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$", name))


def _sanitize_identifier(name: str, quote: bool = True) -> str:
    """
    SECURITY: Sanitize a SQL identifier (table/column name) to prevent injection.

    Only allows alphanumeric characters, underscores, and dots.
    Returns a safely quoted identifier.

    Args:
        name: The identifier to sanitize
        quote: Whether to add double quotes (default True)

    Returns:
        Sanitized identifier (quoted if quote=True)

    Raises:
        ValueError: If identifier contains invalid characters
    """
    if not _validate_identifier(name):
        raise ValueError(f"Invalid identifier: {name}")

    if quote:
        # Double-quote the identifier to prevent any injection
        # In SQLite, double-quoted identifiers are safely escaped
        return f'"{name}"'
    else:
        # Return unquoted for PRAGMA statements (which don't support quotes)
        return name


def _authorize(action, arg1, arg2, database, source):
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() not in {"load_extension", "writefile", "readfile"}:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_PRAGMA and (arg1 or "").lower() in {
        "table_info",
        "table_xinfo",
        "index_list",
        "index_info",
        "foreign_key_list",
    }:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


class SQLiteConnector:
    """
    SQLite connector with connection management and safe query execution.

    Provides connection management, query execution, and schema introspection
    for SQLite databases.
    """

    def __init__(self, database_path: str, timeout: float = 30.0, *, tenant_id=None):
        """
        Initialize SQLite connector.

        Args:
            database_path: Path to the SQLite database file
            timeout: Query timeout in seconds
        """
        self.db_path = database_path
        self.tenant_id = tenant_id
        self.timeout = timeout
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> bool:
        """
        Establish connection to SQLite database.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            path = local_database_path(self.db_path, self.tenant_id)
            self._resolved_path = path
            self._connection = await aiosqlite.connect(Path(path).as_uri() + "?mode=ro", uri=True, timeout=self.timeout)
            await self._connection.execute("PRAGMA foreign_keys = ON")
            await self._connection.execute("PRAGMA trusted_schema = OFF")
            # Install on the connection's worker thread (supports aiosqlite 0.21).
            await self._connection._execute(self._connection._conn.set_authorizer, _authorize)
            await self._connection._execute(self._connection._conn.setlimit, sqlite3.SQLITE_LIMIT_LENGTH, 1024 * 1024)
            await self._connection._execute(self._connection._conn.setlimit, sqlite3.SQLITE_LIMIT_SQL_LENGTH, 65536)
            deadline = time.monotonic() + min(self.timeout, 30)
            await self._connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)

            # Set row factory to return dict-like rows
            self._connection.row_factory = aiosqlite.Row

            logger.info(f"Connected to SQLite database: {self.db_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {str(e)}")
            await self.disconnect()
            return False

    async def disconnect(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Disconnected from SQLite")

    async def test_connection(self) -> dict[str, Any]:
        """
        Test the connection to SQLite.

        Returns:
            Dictionary with test results
        """
        try:
            connected = await self.connect()
            if not connected:
                return {"success": False, "message": "Failed to establish connection", "details": {}}

            # Execute simple query
            async with self._connection.execute("SELECT sqlite_version()") as cursor:
                version_row = await cursor.fetchone()
                version = version_row[0] if version_row else "Unknown"

            # Get database file info
            db_path = Path(getattr(self, "_resolved_path", self.db_path))
            file_size = db_path.stat().st_size if db_path.exists() else 0

            await self.disconnect()

            return {
                "success": True,
                "message": "Connection successful",
                "details": {"version": f"SQLite {version}", "database": self.db_path, "file_size_bytes": file_size},
            }

        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return {"success": False, "message": f"Connection test failed: {str(e)}", "details": {}}

    @asynccontextmanager
    async def get_connection(self):
        """
        Get the database connection.

        Yields:
            Database connection
        """
        if not self._connection:
            raise RuntimeError("Connection not initialized. Call connect() first.")

        yield self._connection

    async def execute_query(self, query: str, params: list[Any] | None = None) -> dict[str, Any]:
        """
        Execute a SQL query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Dictionary with query results:
                {
                    "success": bool,
                    "rows": List[Dict],
                    "row_count": int,
                    "columns": List[str],
                    "error": str (if failed)
                }
        """
        try:
            async with self.get_connection() as conn:
                # Execute query
                if params:
                    async with conn.execute(query, params) as cursor:
                        rows = await cursor.fetchmany(10001)
                        columns = [description[0] for description in cursor.description] if cursor.description else []
                else:
                    async with conn.execute(query) as cursor:
                        rows = await cursor.fetchmany(10001)
                        columns = [description[0] for description in cursor.description] if cursor.description else []

                if len(rows) > 10000 or sum(len(str(tuple(row))) for row in rows) > 2 * 1024 * 1024:
                    raise ValueError("Query result exceeds the limit")

                # Convert rows to list of dictionaries
                result_rows = [dict(row) for row in rows]

                return {"success": True, "rows": result_rows, "row_count": len(result_rows), "columns": columns}

        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            return {"success": False, "rows": [], "row_count": 0, "columns": [], "error": str(e)}

    async def execute_count(self, query: str, params: list[Any] | None = None) -> dict[str, Any]:
        """
        Execute a COUNT query.

        Args:
            query: SQL COUNT query
            params: Query parameters

        Returns:
            Dictionary with count result
        """
        try:
            async with self.get_connection() as conn:
                if params:
                    async with conn.execute(query, params) as cursor:
                        row = await cursor.fetchone()
                        count = row[0] if row else 0
                else:
                    async with conn.execute(query) as cursor:
                        row = await cursor.fetchone()
                        count = row[0] if row else 0

                return {"success": True, "count": count}

        except Exception as e:
            logger.error(f"Count query failed: {str(e)}")
            return {"success": False, "count": 0, "error": str(e)}

    async def get_schema(self) -> dict[str, Any]:
        """
        Get database schema information.

        Returns:
            Dictionary with schema information:
                {
                    "success": bool,
                    "tables": List[Dict],
                    "error": str (if failed)
                }
        """
        try:
            async with self.get_connection() as conn:
                # Get all tables
                tables_query = """
                    SELECT name, type
                    FROM sqlite_master
                    WHERE type IN ('table', 'view')
                    AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                """
                async with conn.execute(tables_query) as cursor:
                    tables_result = await cursor.fetchall()

                tables = []
                for table_row in tables_result:
                    table_name = table_row["name"]
                    table_type = table_row["type"]

                    # SECURITY: Validate table name before using in PRAGMA
                    # Even though names come from sqlite_master, validate for defense in depth
                    if not _validate_identifier(table_name):
                        logger.warning(f"SECURITY: Skipping invalid table name from sqlite_master: {table_name}")
                        continue

                    # Get columns for this table - use validated unquoted name for PRAGMA
                    safe_table = _sanitize_identifier(table_name, quote=False)
                    columns_query = f"PRAGMA table_info({safe_table})"
                    async with conn.execute(columns_query) as cursor:
                        columns_result = await cursor.fetchall()

                    columns = [
                        {
                            "name": col["name"],
                            "type": col["type"],
                            "nullable": not col["notnull"],
                            "default": col["dflt_value"],
                            "primary_key": bool(col["pk"]),
                        }
                        for col in columns_result
                    ]

                    tables.append({"name": table_name, "type": table_type, "columns": columns})

                return {"success": True, "tables": tables}

        except Exception as e:
            logger.error(f"Failed to get schema: {str(e)}")
            return {"success": False, "tables": [], "error": str(e)}

    async def get_table_info(self, table_name: str) -> dict[str, Any]:
        """
        Get detailed information about a specific table.

        Args:
            table_name: Name of the table

        Returns:
            Dictionary with table information
        """
        try:
            # SECURITY: Validate table name to prevent SQL injection
            if not _validate_identifier(table_name):
                raise ValueError(f"Invalid table name: {table_name}")

            # Use unquoted for PRAGMA, quoted for regular SQL
            safe_table_unquoted = _sanitize_identifier(table_name, quote=False)
            safe_table_quoted = _sanitize_identifier(table_name, quote=True)

            async with self.get_connection() as conn:
                # Get columns - PRAGMA requires unquoted identifier
                columns_query = f"PRAGMA table_info({safe_table_unquoted})"
                async with conn.execute(columns_query) as cursor:
                    columns = await cursor.fetchall()

                # Get primary keys
                primary_keys = [col["name"] for col in columns if col["pk"]]

                # Get foreign keys - PRAGMA requires unquoted identifier
                fk_query = f"PRAGMA foreign_key_list({safe_table_unquoted})"
                async with conn.execute(fk_query) as cursor:
                    fks = await cursor.fetchall()

                foreign_keys = [
                    {"column_name": fk["from"], "foreign_table_name": fk["table"], "foreign_column_name": fk["to"]}
                    for fk in fks
                ]

                # Get row count - use quoted identifier for regular SQL
                count_query = f"SELECT COUNT(*) FROM {safe_table_quoted}"
                async with conn.execute(count_query) as cursor:
                    row = await cursor.fetchone()
                    row_count = row[0] if row else 0

                return {
                    "success": True,
                    "table_name": table_name,
                    "columns": [dict(col) for col in columns],
                    "primary_keys": primary_keys,
                    "foreign_keys": foreign_keys,
                    "row_count": row_count,
                }

        except Exception as e:
            logger.error(f"Failed to get table info: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_sample_data(self, table_name: str, limit: int = 10) -> dict[str, Any]:
        """
        Get sample data from a table.

        Args:
            table_name: Name of the table
            limit: Number of rows to fetch

        Returns:
            Dictionary with sample data
        """
        try:
            # SECURITY: Validate and sanitize table name to prevent SQL injection
            safe_table = _sanitize_identifier(table_name)
            query = f"SELECT * FROM {safe_table} LIMIT ?"
            result = await self.execute_query(query, [limit])
            return result

        except Exception as e:
            logger.error(f"Failed to get sample data: {str(e)}")
            return {"success": False, "rows": [], "error": str(e)}

    async def get_tables(self) -> list[str]:
        """
        Get list of table names in the database.

        Returns:
            List of table names
        """
        try:
            async with self.get_connection() as conn:
                tables_query = """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                """
                async with conn.execute(tables_query) as cursor:
                    tables_result = await cursor.fetchall()
                return [row["name"] for row in tables_result]

        except Exception as e:
            logger.error(f"Failed to get tables: {str(e)}")
            return []
