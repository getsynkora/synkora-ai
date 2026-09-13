"""
Database Tools for Synkora Agents.

Provides internal database query capabilities for PostgreSQL and Elasticsearch,
as well as chart generation from query results.
"""

import asyncio
import json
import logging
import re
import time
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.chart import Chart
from src.models.database_connection import DatabaseConnection
from src.services.charts import ChartService
from src.services.database import (
    BigQueryConnector,
    ClickHouseConnector,
    DatabricksConnector,
    DatadogConnector,
    DockerConnector,
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connector cache — reuse live connectors across agent tool calls.
# Key: connection_id (str), Value: (connector, last_used_timestamp)
# ---------------------------------------------------------------------------
_CONNECTOR_TTL = 300  # 5 minutes
_connector_cache: dict[str, tuple[Any, float]] = {}
_connector_locks: dict[str, asyncio.Lock] = {}

# Maximum characters for query result data returned to the LLM.
# ~50 K chars ≈ 12 K tokens — large enough for meaningful analysis,
# small enough to never blow the context window.
_MAX_RESULT_CHARS = 50_000

# Chart-type → rendering library mapping (mirrors generate_chart_from_csv.py)
_CHARTJS_TYPES = {"bar", "line", "pie", "doughnut", "scatter"}
_RECHARTS_TYPES = {"area", "stacked_bar", "radar", "treemap", "funnel"}
_PLOTLY_TYPES = {"heatmap", "box", "box_plot", "violin", "candlestick", "waterfall"}


# ---------------------------------------------------------------------------
# Write-statement guard — prevent agents from issuing mutating SQL
# ---------------------------------------------------------------------------

_WRITE_PATTERN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE|EXEC|EXECUTE|MERGE)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Row-count guard — prevent LLM from fetching millions of raw rows
# ---------------------------------------------------------------------------

# SQL-based DB types where we can run COUNT(*) to estimate table size
_SQL_COUNT_GUARD_TYPES = frozenset(
    # Supabase excluded — PostgREST blocks COUNT(*) queries (PGRST123) unless
    # db-aggregates-enabled=true, which Supabase disables by default.
    {"POSTGRESQL", "MYSQL", "BIGQUERY", "SNOWFLAKE", "SQLSERVER", "CLICKHOUSE", "DUCKDB", "SQLITE"}
)

# If estimated row count exceeds this, force the LLM to use aggregation
_COUNT_GUARD_THRESHOLD = 50_000


def _is_broad_select(query: str) -> bool:
    """
    Return True if *query* looks like a broad SELECT that could return millions of rows.

    A SELECT is 'broad' when it has none of: LIMIT, GROUP BY, or aggregate functions
    (COUNT/SUM/AVG/MIN/MAX and friends).  Any of those patterns means the query
    is already scoped or aggregated and we let it through.
    """
    q = query.strip().upper()
    if not q.startswith("SELECT"):
        return False
    if re.search(r"\bLIMIT\b", q):
        return False
    if re.search(r"\bGROUP\s+BY\b", q):
        return False
    if re.search(r"\b(COUNT|SUM|AVG|MIN|MAX|PERCENTILE|STDDEV|VARIANCE|MEDIAN)\s*\(", q):
        return False
    return True


def _extract_from_table(query: str) -> str | None:
    """
    Extract the table name from the outermost FROM clause of a SELECT query.

    Skips FROM clauses that appear inside parentheses (subqueries, CTEs).
    Returns None when no suitable table name is found.
    """
    # Walk the query character-by-character tracking parenthesis depth.
    # Only consider FROM tokens at depth 0 (outermost query).
    depth = 0
    i = 0
    length = len(query)
    while i < length:
        ch = query[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and query[i : i + 4].upper() == "FROM":
            # Confirm it's a word boundary (not e.g. "INFORM")
            before = query[i - 1] if i > 0 else " "
            after = query[i + 4] if i + 4 < length else " "
            if not before.isalnum() and before != "_" and (not after.isalnum() and after != "_"):
                # Found FROM at top level — extract the table token
                rest = query[i + 4 :].lstrip()
                m = re.match(r'(["\']?[\w.]+["\']?)', rest)
                if m:
                    raw = m.group(1).strip("\"'`")
                    # Skip subquery opening paren or keyword
                    if not raw or raw.upper() in ("SELECT", "WITH"):
                        return None
                    return raw
                return None
        i += 1
    return None


async def _estimate_row_count(connector: Any, table_name: str) -> int | None:
    """
    Run ``SELECT COUNT(*) FROM table`` via *connector* and return the integer.

    Returns None if the estimate fails (e.g. schema-qualified names, views,
    virtual tables).  Failures are non-blocking — the guard simply skips.
    """
    try:
        # Quote the table name correctly.  schema.table → "schema"."table"; plain → "table".
        if "." in table_name:
            schema, tbl = table_name.split(".", 1)
            quoted = f'"{schema}"."{tbl}"'
        else:
            quoted = f'"{table_name}"'
        result = await connector.execute_query(f"SELECT COUNT(*) AS _n FROM {quoted}")
        rows = result.get("rows", [])
        if rows:
            row = rows[0]
            for key in ("_n", "n", "count", "COUNT(*)", "count(*)"):
                if key in row:
                    return int(row[key])
            # Fall back to first value in the row
            val = next(iter(row.values()), None)
            if val is not None:
                return int(val)
    except Exception as e:
        logger.debug("Row count estimation skipped for '%s': %s", table_name, e)
    return None


def _truncate_rows_for_llm(rows: list, total_rows: int) -> tuple[list, str | None]:
    """
    Trim *rows* so the JSON representation stays within _MAX_RESULT_CHARS.

    Returns (trimmed_rows, truncation_note) where truncation_note is None when
    no trimming was needed, or a human-readable warning string when it was.
    """
    if not rows:
        return rows, None

    serialized = json.dumps(rows)
    if len(serialized) <= _MAX_RESULT_CHARS:
        return rows, None

    # Binary-search for the largest prefix that fits
    lo, hi = 1, len(rows)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(json.dumps(rows[:mid])) <= _MAX_RESULT_CHARS:
            lo = mid
        else:
            hi = mid - 1

    kept = lo
    note = (
        f"Result truncated: returned {kept} of {total_rows} rows "
        f"(output exceeded {_MAX_RESULT_CHARS:,} character limit). "
        "Use a more specific query or add a LIMIT clause to reduce the result size."
    )
    logger.warning(note)
    return rows[:kept], note


def _library_for_chart_type(chart_type: str) -> str:
    """Return the rendering library that supports the given chart type."""
    ct = chart_type.lower().strip()
    if ct in _RECHARTS_TYPES:
        return "recharts"
    if ct in _PLOTLY_TYPES:
        return "plotly"
    return "chartjs"


async def _get_or_create_connector(connection: DatabaseConnection) -> Any:
    """
    Return a cached connector for *connection*, creating one if needed.

    Uses a per-connection asyncio.Lock to prevent duplicate pool creation
    on concurrent first calls for the same connection.
    """
    conn_key = str(connection.id)

    # Lazily create the per-key lock
    if conn_key not in _connector_locks:
        _connector_locks[conn_key] = asyncio.Lock()

    async with _connector_locks[conn_key]:
        # Evict if stale
        if conn_key in _connector_cache:
            connector, last_used = _connector_cache[conn_key]
            if time.monotonic() - last_used < _CONNECTOR_TTL:
                _connector_cache[conn_key] = (connector, time.monotonic())
                return connector
            # Stale — disconnect and remove
            try:
                await connector.disconnect()
            except Exception:
                pass
            del _connector_cache[conn_key]

        # Create a fresh connector
        db_type = str(connection.database_type).upper()
        if db_type == "POSTGRESQL":
            connector = PostgreSQLConnector(connection)
        elif db_type == "ELASTICSEARCH":
            connector = ElasticsearchConnector(connection)
        elif db_type == "SQLITE":
            connector = SQLiteConnector(database_path=connection.database_path, tenant_id=connection.tenant_id)
        elif db_type == "MYSQL":
            connector = MySQLConnector(connection)
        elif db_type == "MONGODB":
            connector = MongoDBConnector(connection)
        elif db_type == "SUPABASE":
            connector = SupabaseConnector(connection)
        elif db_type == "BIGQUERY":
            connector = BigQueryConnector(connection)
        elif db_type == "SNOWFLAKE":
            connector = SnowflakeConnector(connection)
        elif db_type == "SQLSERVER":
            connector = SQLServerConnector(connection)
        elif db_type == "CLICKHOUSE":
            connector = ClickHouseConnector(connection)
        elif db_type == "DUCKDB":
            connector = DuckDBConnector(connection)
        elif db_type == "DATADOG":
            connector = DatadogConnector(connection)
            # Datadog connector has no persistent connection; return directly
            _connector_cache[conn_key] = (connector, time.monotonic())
            return connector
        elif db_type == "DATABRICKS":
            connector = DatabricksConnector(connection)
            _connector_cache[conn_key] = (connector, time.monotonic())
            return connector
        elif db_type == "DOCKER":
            connector = DockerConnector(connection)
            _connector_cache[conn_key] = (connector, time.monotonic())
            return connector
        else:
            return None

        await connector.connect()
        _connector_cache[conn_key] = (connector, time.monotonic())
        logger.debug(f"Created and cached connector for connection {conn_key}")
        return connector


async def internal_query_database(
    connection_id: str, query: str, tenant_id: str, db_session: AsyncSession, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Execute a query on a configured database connection.

    This internal tool allows agents to query PostgreSQL or Elasticsearch databases
    that have been configured by the user. It handles connection management,
    query execution, and result formatting.

    Args:
        connection_id: UUID of the database connection to use
        query: Natural language query or SQL/DSL query string
        tenant_id: Tenant ID for authorization
        db_session: Database session for fetching connection details
        config: Optional configuration dictionary

    Returns:
        Dictionary containing:
        - success: Whether the query succeeded
        - data: Query results (list of rows/documents)
        - row_count: Number of rows/documents returned
        - columns: Column names (for SQL queries)
        - query_executed: The actual query that was executed
        - connection_name: Name of the database connection used
        - database_type: Type of database (postgresql, elasticsearch)
        - error: Error message (if any)
    """
    try:
        # Fetch database connection
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.id == UUID(str(connection_id)), DatabaseConnection.tenant_id == UUID(str(tenant_id))
        )
        result = await db_session.execute(stmt)
        connection = result.scalar_one_or_none()

        if not connection:
            return {"success": False, "error": f"Database connection not found: {connection_id}"}

        # Check connection status
        if connection.status != "active":
            return {"success": False, "error": f"Database connection is not active. Status: {connection.status}"}

        # Write-statement guard: block mutating SQL unless the connection explicitly allows writes.
        if _WRITE_PATTERN.match(query.strip()):
            return {
                "error": "Write statements are not permitted. Only SELECT queries are allowed.",
                "rows": [],
                "columns": [],
                "success": False,
            }

        # Execute query based on database type (use cached connector)
        db_type = str(connection.database_type).upper()

        # Row-count guard: prevent broad SELECT * on large tables.
        # Run a fast COUNT(*) first; if the table is too large, return a
        # structured error so the LLM rewrites the query with aggregations.
        if db_type in _SQL_COUNT_GUARD_TYPES and _is_broad_select(query):
            table_name = _extract_from_table(query)
            if table_name:
                try:
                    connector = await _get_or_create_connector(connection)
                    if connector:
                        row_count = await _estimate_row_count(connector, table_name)
                        if row_count is not None and row_count > _COUNT_GUARD_THRESHOLD:
                            logger.info(
                                "[DB Guard] Blocked broad SELECT on '%s' (%d rows > %d threshold)",
                                table_name,
                                row_count,
                                _COUNT_GUARD_THRESHOLD,
                            )
                            return {
                                "success": False,
                                "error": (
                                    f"Table '{table_name}' contains {row_count:,} rows — too large to "
                                    f"fetch with SELECT *. Rewrite the query using aggregation:\n"
                                    f"  • GROUP BY + COUNT/SUM/AVG to compute statistics\n"
                                    f"  • WHERE filters to narrow rows before fetching\n"
                                    f"  • LIMIT ≤1000 only for sampling a few rows\n"
                                    f"Example: SELECT status, COUNT(*) AS total "
                                    f"FROM {table_name} GROUP BY status\n"
                                    f"Never use SELECT * on tables with more than "
                                    f"{_COUNT_GUARD_THRESHOLD:,} rows."
                                ),
                                "row_count_estimate": row_count,
                                "connection_name": connection.name,
                                "database_type": db_type.lower(),
                            }
                except Exception as guard_err:
                    # Guard is non-blocking — log and continue with the original query
                    logger.debug("[DB Guard] Count check skipped (non-blocking): %s", guard_err)

        if db_type == "POSTGRESQL":
            return await _execute_postgresql_query(connection, query)
        elif db_type == "ELASTICSEARCH":
            return await _execute_elasticsearch_query(connection, query)
        elif db_type == "SQLITE":
            return await _execute_sqlite_query(connection, query)
        elif db_type in (
            "MYSQL",
            "MONGODB",
            "SUPABASE",
            "BIGQUERY",
            "SNOWFLAKE",
            "SQLSERVER",
            "CLICKHOUSE",
            "DUCKDB",
            "DATADOG",
            "DATABRICKS",
            "DOCKER",
        ):
            return await _execute_generic_query(connection, query)
        else:
            return {"success": False, "error": f"Unsupported database type: {connection.database_type}"}

    except Exception as e:
        logger.warning(f"Error executing database query: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to execute query: {str(e)}"}


async def _execute_postgresql_query(connection: DatabaseConnection, query: str) -> dict[str, Any]:
    """Execute a PostgreSQL query using a cached connector."""
    try:
        connector = await _get_or_create_connector(connection)
        if connector is None:
            return {
                "success": False,
                "error": "Failed to create PostgreSQL connector.",
                "connection_name": connection.name,
                "database_type": "postgresql",
            }

        result = await connector.execute_query(query)
        rows, note = _truncate_rows_for_llm(result.get("rows", []), result.get("row_count", 0))

        return {
            "success": True,
            "data": rows,
            "row_count": result.get("row_count", 0),
            "columns": result.get("columns", []),
            "query_executed": result.get("query", query),
            "connection_name": connection.name,
            "database_type": "postgresql",
            **({"truncation_note": note} if note else {}),
        }

    except Exception as e:
        logger.warning(f"PostgreSQL query error: {e}", exc_info=True)
        # Evict stale connector on error
        _connector_cache.pop(str(connection.id), None)
        return {
            "success": False,
            "error": f"PostgreSQL query failed: {str(e)}",
            "connection_name": connection.name,
            "database_type": "postgresql",
        }


async def _execute_elasticsearch_query(connection: DatabaseConnection, query: str) -> dict[str, Any]:
    """Execute an Elasticsearch query using a cached connector."""
    try:
        import json

        connector = await _get_or_create_connector(connection)
        if connector is None:
            return {
                "success": False,
                "error": "Failed to create Elasticsearch connector.",
                "connection_name": connection.name,
                "database_type": "elasticsearch",
            }

        try:
            query_dsl = json.loads(query)
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": "Natural language queries for Elasticsearch not yet implemented. Please provide DSL query as JSON.",
                "connection_name": connection.name,
                "database_type": "elasticsearch",
            }

        index = query_dsl.pop("index", "_all")
        size = query_dsl.pop("size", 10)
        from_ = query_dsl.pop("from", 0)
        result = await connector.execute_search(index=index, query=query_dsl, size=size, from_=from_)

        return {
            "success": result.get("success", False),
            "data": result.get("results", []),
            "row_count": len(result.get("results", [])),
            "total_hits": result.get("total", 0),
            "query_executed": query,
            "connection_name": connection.name,
            "database_type": "elasticsearch",
        }

    except Exception as e:
        logger.warning(f"Elasticsearch query error: {e}", exc_info=True)
        _connector_cache.pop(str(connection.id), None)
        return {
            "success": False,
            "error": f"Elasticsearch query failed: {str(e)}",
            "connection_name": connection.name,
            "database_type": "elasticsearch",
        }


async def _execute_generic_query(connection: DatabaseConnection, query: str) -> dict[str, Any]:
    """Execute a query on a MySQL or MongoDB connection using a cached connector."""
    db_type = str(connection.database_type).upper()
    display_type = db_type.lower()
    try:
        connector = await _get_or_create_connector(connection)
        if connector is None:
            return {
                "success": False,
                "error": f"Failed to create {display_type} connector.",
                "connection_name": connection.name,
                "database_type": display_type,
            }

        result = await connector.execute_query(query)
        rows, note = _truncate_rows_for_llm(result.get("rows", []), result.get("row_count", 0))

        return {
            "success": result.get("success", False),
            "data": rows,
            "row_count": result.get("row_count", 0),
            "columns": result.get("columns", []),
            "query_executed": query,
            "connection_name": connection.name,
            "database_type": display_type,
            "error": result.get("error"),
            **({"truncation_note": note} if note else {}),
        }

    except Exception as e:
        logger.warning(f"{db_type} query error: {e}", exc_info=True)
        _connector_cache.pop(str(connection.id), None)
        return {
            "success": False,
            "error": f"{db_type} query failed: {str(e)}",
            "connection_name": connection.name,
            "database_type": display_type,
        }


async def internal_list_database_connections(
    tenant_id: str, db_session: AsyncSession, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    List all database connections available to the agent.

    This tool allows agents to discover what database connections are configured
    and available for querying.

    Args:
        tenant_id: Tenant ID for authorization
        db_session: Database session for fetching connections
        config: Optional configuration dictionary

    Returns:
        Dictionary containing:
        - success: Whether the operation succeeded
        - connections: List of available connections with details
        - count: Number of connections
        - error: Error message (if any)
    """
    try:
        # Fetch all active database connections for tenant
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.tenant_id == UUID(str(tenant_id)), DatabaseConnection.status == "active"
        )
        result = await db_session.execute(stmt)
        connections = list(result.scalars().all())

        # Format connection details
        connection_list = []
        for conn in connections:
            connection_list.append(
                {
                    "id": str(conn.id),
                    "name": conn.name,
                    "type": conn.database_type,
                    "host": conn.host,
                    "port": conn.port,
                    "database": conn.database_name,
                    "database_path": conn.database_path,
                    "description": f"{conn.database_type.upper()} database"
                    + (
                        f" at {conn.host}:{conn.port}/{conn.database_name}"
                        if conn.host
                        else f" at {conn.database_path}"
                        if conn.database_path
                        else ""
                    ),
                }
            )

        return {"success": True, "connections": connection_list, "count": len(connection_list)}

    except Exception as e:
        logger.warning(f"Error listing database connections: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to list connections: {str(e)}"}


async def internal_get_database_schema(
    connection_id: str, tenant_id: str, db_session: AsyncSession, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Get schema information for a database connection.

    This tool allows agents to understand the structure of a database,
    including tables, columns, and data types.

    Args:
        connection_id: UUID of the database connection
        tenant_id: Tenant ID for authorization
        db_session: Database session for fetching connection details
        config: Optional configuration dictionary

    Returns:
        Dictionary containing:
        - success: Whether the operation succeeded
        - schema: Schema information (tables, indices, etc.)
        - connection_name: Name of the database connection
        - database_type: Type of database
        - error: Error message (if any)
    """
    try:
        # Fetch database connection
        stmt = select(DatabaseConnection).where(
            DatabaseConnection.id == UUID(str(connection_id)), DatabaseConnection.tenant_id == UUID(str(tenant_id))
        )
        result = await db_session.execute(stmt)
        connection = result.scalar_one_or_none()

        if not connection:
            return {"success": False, "error": f"Database connection not found: {connection_id}"}

        db_type = str(connection.database_type).upper()
        if db_type == "POSTGRESQL":
            return await _get_postgresql_schema(connection)
        elif db_type == "ELASTICSEARCH":
            return await _get_elasticsearch_schema(connection)
        elif db_type == "SQLITE":
            return await _get_sqlite_schema(connection)
        elif db_type in (
            "MYSQL",
            "MONGODB",
            "SUPABASE",
            "BIGQUERY",
            "SNOWFLAKE",
            "SQLSERVER",
            "CLICKHOUSE",
            "DUCKDB",
            "DATADOG",
            "DATABRICKS",
            "DOCKER",
        ):
            return await _get_generic_schema(connection)
        else:
            return {"success": False, "error": f"Unsupported database type: {connection.database_type}"}

    except Exception as e:
        logger.warning(f"Error getting database schema: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to get schema: {str(e)}"}


async def _get_postgresql_schema(connection: DatabaseConnection) -> dict[str, Any]:
    """Get PostgreSQL schema information using cached connector."""
    try:
        connector = await _get_or_create_connector(connection)
        if connector is None:
            return {
                "success": False,
                "error": "Failed to create PostgreSQL connector.",
                "connection_name": connection.name,
                "database_type": "postgresql",
            }

        tables = await connector.get_tables()
        schema_info = []
        for table in tables[:20]:
            table_info = await connector.get_table_info(table)
            schema_info.append(table_info)

        return {
            "success": True,
            "schema": {"tables": schema_info, "total_tables": len(tables)},
            "connection_name": connection.name,
            "database_type": "postgresql",
        }

    except Exception as e:
        logger.warning(f"PostgreSQL schema error: {e}", exc_info=True)
        _connector_cache.pop(str(connection.id), None)
        return {
            "success": False,
            "error": f"Failed to get PostgreSQL schema: {str(e)}",
            "connection_name": connection.name,
            "database_type": "postgresql",
        }


async def _get_elasticsearch_schema(connection: DatabaseConnection) -> dict[str, Any]:
    """Get Elasticsearch schema information using cached connector."""
    try:
        connector = await _get_or_create_connector(connection)
        if connector is None:
            return {
                "success": False,
                "error": "Failed to create Elasticsearch connector.",
                "connection_name": connection.name,
                "database_type": "elasticsearch",
            }

        indices_result = await connector.get_indices()
        indices = [idx["name"] for idx in (indices_result.get("indices") or [])]
        schema_info = []
        for index_name in indices[:20]:
            mapping = await connector.get_index_mapping(index_name)
            schema_info.append({"index": index_name, "mapping": mapping})

        return {
            "success": True,
            "schema": {"indices": schema_info, "total_indices": len(indices)},
            "connection_name": connection.name,
            "database_type": "elasticsearch",
        }

    except Exception as e:
        logger.warning(f"Elasticsearch schema error: {e}", exc_info=True)
        _connector_cache.pop(str(connection.id), None)
        return {
            "success": False,
            "error": f"Failed to get Elasticsearch schema: {str(e)}",
            "connection_name": connection.name,
            "database_type": "elasticsearch",
        }


async def _execute_sqlite_query(connection: DatabaseConnection, query: str) -> dict[str, Any]:
    """Execute a SQLite query using a cached connector."""
    try:
        connector = await _get_or_create_connector(connection)
        if connector is None:
            return {
                "success": False,
                "error": "Failed to create SQLite connector.",
                "connection_name": connection.name,
                "database_type": "sqlite",
            }

        result = await connector.execute_query(query)
        rows, note = _truncate_rows_for_llm(result.get("rows", []), result.get("row_count", 0))

        return {
            "success": True,
            "data": rows,
            "row_count": result.get("row_count", 0),
            "columns": result.get("columns", []),
            "query_executed": result.get("query", query),
            "connection_name": connection.name,
            "database_type": "sqlite",
            **({"truncation_note": note} if note else {}),
        }

    except Exception as e:
        logger.warning(f"SQLite query error: {e}", exc_info=True)
        _connector_cache.pop(str(connection.id), None)
        return {
            "success": False,
            "error": f"SQLite query failed: {str(e)}",
            "connection_name": connection.name,
            "database_type": "sqlite",
        }


async def _get_generic_schema(connection: DatabaseConnection) -> dict[str, Any]:
    """Get schema for MySQL or MongoDB using a cached connector."""
    db_type = str(connection.database_type).upper()
    display_type = db_type.lower()
    try:
        connector = await _get_or_create_connector(connection)
        if connector is None:
            return {
                "success": False,
                "error": f"Failed to create {display_type} connector.",
                "connection_name": connection.name,
                "database_type": display_type,
            }

        result = await connector.get_schema()
        tables = result.get("tables", [])
        return {
            "success": result.get("success", False),
            "schema": {"tables": tables[:20], "total_tables": len(tables)},
            "connection_name": connection.name,
            "database_type": display_type,
        }

    except Exception as e:
        logger.warning(f"{db_type} schema error: {e}", exc_info=True)
        _connector_cache.pop(str(connection.id), None)
        return {
            "success": False,
            "error": f"Failed to get {display_type} schema: {str(e)}",
            "connection_name": connection.name,
            "database_type": display_type,
        }


async def _get_sqlite_schema(connection: DatabaseConnection) -> dict[str, Any]:
    """Get SQLite schema information using cached connector."""
    try:
        connector = await _get_or_create_connector(connection)
        if connector is None:
            return {
                "success": False,
                "error": "Failed to create SQLite connector.",
                "connection_name": connection.name,
                "database_type": "sqlite",
            }

        schema_result = await connector.get_schema()

        if not schema_result.get("success"):
            return {
                "success": False,
                "error": schema_result.get("error", "Failed to get schema"),
                "connection_name": connection.name,
                "database_type": "sqlite",
            }

        tables = schema_result.get("tables", [])
        return {
            "success": True,
            "schema": {"tables": tables[:20], "total_tables": len(tables)},
            "connection_name": connection.name,
            "database_type": "sqlite",
        }

    except Exception as e:
        logger.warning(f"SQLite schema error: {e}", exc_info=True)
        _connector_cache.pop(str(connection.id), None)
        return {
            "success": False,
            "error": f"Failed to get SQLite schema: {str(e)}",
            "connection_name": connection.name,
            "database_type": "sqlite",
        }


async def internal_generate_chart(
    query_result: dict[str, Any],
    chart_type: str | None,
    title: str,
    agent_id: str,
    tenant_id: str,
    db_session: AsyncSession,
    conversation_id: str | None = None,
    message_id: str | None = None,
    description: str | None = None,
    config: dict[str, Any] | None = None,
    library: str | None = None,
) -> dict[str, Any]:
    """
    Generate a chart from database query results.

    Supports Chart.js (bar, line, pie, doughnut, scatter),
    Recharts (area, stacked_bar, radar, treemap, funnel),
    and Plotly (heatmap, box, violin, candlestick, waterfall).

    Args:
        query_result: Result from internal_query_database containing data
        chart_type: Type of chart or None for auto-detection
        title: Chart title
        agent_id: Agent ID creating the chart
        tenant_id: Tenant ID for authorization
        db_session: Database session
        conversation_id: Optional conversation ID to link chart to
        message_id: Optional message ID to link chart to
        description: Optional chart description
        config: Optional custom chart configuration
        library: Rendering library override (chartjs | recharts | plotly). Auto-detected from chart_type if None.

    Returns:
        Dictionary containing:
        - success: Whether chart generation succeeded
        - chart_id: ID of the created chart
        - chart_config: Generated chart configuration
        - chart_data: Formatted chart data
        - error: Error message (if any)
    """
    try:
        # Normalize query_result — the LLM may pass data in several shapes:
        #   0. A JSON string — parse it first
        #   1. A plain list of rows (e.g. from micromobility tool results aggregated by LLM)
        #   2. A flat dict of key→value pairs (e.g. {"total_reports": 276, "pending": 216})
        #   3. The standard {"success": True, "data": [...]} format from internal_query_database
        if isinstance(query_result, str):
            try:
                query_result = json.loads(query_result)
            except (json.JSONDecodeError, ValueError):
                return {
                    "success": False,
                    "error": "query_result is a string but could not be parsed as JSON. Pass a list or dict, not a string.",
                }

        if isinstance(query_result, list):
            query_result = {"success": True, "data": query_result, "row_count": len(query_result)}
        elif isinstance(query_result, dict) and "data" not in query_result:
            # Flat dict — convert each key/value into a row suitable for charting
            rows = [{"label": k, "value": v} for k, v in query_result.items() if isinstance(v, (int, float))]
            query_result = {"success": True, "data": rows, "row_count": len(rows)}

        # Clean query_result to remove any non-serializable objects
        # This prevents Session objects or other non-JSON-serializable data from being stored
        clean_query_result = {
            "success": query_result.get("success"),
            "data": query_result.get("data"),
            "row_count": query_result.get("row_count"),
            "columns": query_result.get("columns"),
            "query_executed": query_result.get("query_executed"),
            "connection_name": query_result.get("connection_name"),
            "database_type": query_result.get("database_type"),
        }

        # Extract data from query result
        # The LLM may pass query results with or without a "success" key
        data = clean_query_result.get("data", [])

        # If data is a paginated API response, unwrap to the inner list.
        # DRF format: {"count": N, "results": [...]}
        if isinstance(data, dict) and "results" in data:
            data = data["results"]
        # Micromobility format: {"meta": {...}, "data": [...]}
        elif isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            data = data["data"]

        # Validate that we have data to work with
        if not data:
            error_msg = clean_query_result.get("error", "No data available to generate chart")
            logger.warning(f"Chart generation failed: {error_msg}")
            return {"success": False, "error": error_msg}

        logger.info(f"Generating chart with {len(data)} data points")

        # Validate data shape: the chart service expects rows with at least 2 columns where
        # column 0 = label (x-axis) and column 1 = numeric value (y-axis).
        # If data rows look like raw API records (more than 3 columns, or no numeric second column),
        # return a helpful error so the agent can pre-aggregate before calling this tool.
        if isinstance(data, list) and data and isinstance(data[0], dict):
            columns = list(data[0].keys())
            if len(columns) > 3:
                col_names = ", ".join(columns[:6]) + ("..." if len(columns) > 6 else "")
                return {
                    "success": False,
                    "error": (
                        f"Data cannot be charted directly — it contains {len(columns)} columns "
                        f"({col_names}) and appears to be raw API records, not aggregated chart data. "
                        "Please pre-aggregate the data into rows with exactly 2 columns: "
                        "a label column (e.g. 'date') and a numeric value column (e.g. 'count'). "
                        'Example: [{"date": "2026-04-20", "count": 15}, ...]. '
                        "Then call internal_generate_chart again with the aggregated data."
                    ),
                }
            # Ensure the second column is (or can be cast to) a number
            if len(columns) >= 2:
                second_col = columns[1]
                sample_val = data[0].get(second_col)
                if sample_val is not None and not isinstance(sample_val, (int, float)):
                    try:
                        float(str(sample_val))
                    except (ValueError, TypeError):
                        return {
                            "success": False,
                            "error": (
                                f"Column '{second_col}' (value '{sample_val}') is not numeric. "
                                "The second column must contain numeric values for the y-axis. "
                                "Please provide pre-aggregated data with a label column and a numeric count/value column."
                            ),
                        }

        # Determine chart type if not specified
        if not chart_type:
            chart_type = "bar"  # Default to bar chart

        # Initialize chart service with db_session
        chart_service = ChartService(db_session)

        # Generate chart data structure (doesn't need db)
        chart_data = chart_service.generate_chart_from_query_result(query_result=data, chart_type=chart_type)

        # Determine rendering library: explicit override → auto-detect from type → default chartjs
        if not library:
            library = _library_for_chart_type(chart_type)

        # Generate chart configuration (doesn't need db)
        chart_config = chart_service._generate_chart_config(chart_type=chart_type, data=chart_data, library=library)

        # Merge with custom config if provided, but exclude runtime context
        if config:
            # Filter out non-serializable keys like _runtime_context
            clean_config = {k: v for k, v in config.items() if k != "_runtime_context" and not k.startswith("_")}
            if clean_config:
                chart_config.update(clean_config)

        # Create chart in database using a fresh session to avoid conflicts
        # when multiple charts are saved concurrently from parallel tool calls
        from src.core.database import get_async_session_factory

        chart_id: str | None = None
        session_factory = get_async_session_factory()
        async with session_factory() as new_session:
            async with new_session.begin():
                chart = Chart(
                    tenant_id=UUID(str(tenant_id)),
                    agent_id=UUID(str(agent_id)),
                    conversation_id=UUID(str(conversation_id)) if conversation_id else None,
                    message_id=UUID(str(message_id)) if message_id else None,
                    title=title,
                    description=description
                    or f"Chart generated from {clean_query_result.get('connection_name', 'database')} query",
                    chart_type=chart_type,
                    library=library,
                    config=chart_config,
                    data=chart_data,
                    query=clean_query_result.get("query_executed"),
                )
                new_session.add(chart)
            await new_session.refresh(chart)
            chart_id = str(chart.id)
            chart_type_saved = chart.chart_type
            chart_library = chart.library
            chart_config_saved = chart.config
            chart_data_saved = chart.data

        return {
            "success": True,
            "chart_id": chart_id,
            "chart_type": chart_type_saved,
            "library": chart_library,
            "chart_config": chart_config_saved,
            "chart_data": chart_data_saved,
            "message": f"Chart '{title}' created successfully",
        }

    except Exception as e:
        logger.warning(f"Error generating chart: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to generate chart: {str(e)}"}


async def internal_query_and_chart(
    connection_id: str,
    query: str,
    chart_title: str,
    tenant_id: str,
    agent_id: str,
    db_session: AsyncSession,
    chart_type: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    chart_description: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute a database query and automatically generate a chart from the results.

    This is a convenience tool that combines query execution and chart generation
    in a single step. It's useful when you know you want to visualize the query results.

    Args:
        connection_id: UUID of the database connection to use
        query: SQL or DSL query string
        chart_title: Title for the generated chart
        tenant_id: Tenant ID for authorization
        agent_id: Agent ID creating the chart
        db_session: Database session
        chart_type: Optional chart type (auto-detected if not provided)
        conversation_id: Optional conversation ID
        message_id: Optional message ID
        chart_description: Optional chart description
        config: Optional custom chart configuration

    Returns:
        Dictionary containing:
        - success: Whether the operation succeeded
        - query_result: Results from the database query
        - chart: Chart generation result
        - error: Error message (if any)
    """
    try:
        # Execute the query
        query_result = await internal_query_database(
            connection_id=connection_id, query=query, tenant_id=tenant_id, db_session=db_session
        )

        if not query_result.get("success"):
            return {
                "success": False,
                "error": f"Query failed: {query_result.get('error')}",
                "query_result": query_result,
            }

        # Create a clean query_result without any non-serializable objects
        clean_query_result = {
            "success": query_result.get("success"),
            "data": query_result.get("data"),
            "row_count": query_result.get("row_count"),
            "columns": query_result.get("columns"),
            "query_executed": query_result.get("query_executed"),
            "connection_name": query_result.get("connection_name"),
            "database_type": query_result.get("database_type"),
        }

        # Generate chart from results
        chart_result = await internal_generate_chart(
            query_result=clean_query_result,
            chart_type=chart_type,
            title=chart_title,
            agent_id=agent_id,
            tenant_id=tenant_id,
            db_session=db_session,
            conversation_id=conversation_id,
            message_id=message_id,
            description=chart_description,
            config=config,
        )

        return {
            "success": chart_result.get("success", False),
            "query_result": {
                "row_count": query_result.get("row_count"),
                "columns": query_result.get("columns"),
                "connection_name": query_result.get("connection_name"),
            },
            "chart": chart_result,
            "message": f"Query executed and chart '{chart_title}' generated successfully"
            if chart_result.get("success")
            else None,
            "error": chart_result.get("error") if not chart_result.get("success") else None,
        }

    except Exception as e:
        logger.warning(f"Error in query_and_chart: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to execute query and generate chart: {str(e)}"}
