"""
Unit tests for DuckDBConnector.

All tests run against a real in-process DuckDB engine (no mocks of duckdb itself).
Only the DatabaseConnection ORM model is mocked.
"""

import csv
import os
import tempfile
from unittest.mock import MagicMock
from uuid import UUID

import duckdb
import pytest

from src.services.database.duckdb_connector import DuckDBConnector, _validate_identifier

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_connection(database_path: str = ":memory:", connection_params: dict | None = None) -> MagicMock:
    """Return a minimal mock of DatabaseConnection."""
    conn = MagicMock()
    conn.tenant_id = UUID("11111111-1111-4111-8111-111111111111")
    conn.database_path = database_path
    conn.connection_params = connection_params or {}
    conn.password_encrypted = None
    return conn


# ---------------------------------------------------------------------------
# _validate_identifier
# ---------------------------------------------------------------------------


class TestValidateIdentifier:
    def test_valid_simple(self):
        assert _validate_identifier("users") is True

    def test_valid_underscore(self):
        assert _validate_identifier("_my_table") is True

    def test_valid_mixed_case(self):
        assert _validate_identifier("OrderItems") is True

    def test_empty_string(self):
        assert _validate_identifier("") is False

    def test_starts_with_digit(self):
        assert _validate_identifier("1table") is False

    def test_hyphen_rejected(self):
        assert _validate_identifier("my-table") is False

    def test_dangerous_keyword_select(self):
        assert _validate_identifier("select") is False

    def test_dangerous_keyword_drop(self):
        assert _validate_identifier("drop") is False

    def test_dangerous_keyword_union(self):
        assert _validate_identifier("union") is False


# ---------------------------------------------------------------------------
# DuckDBConnector — lifecycle
# ---------------------------------------------------------------------------


class TestDuckDBConnectorLifecycle:
    @pytest.mark.asyncio
    async def test_connect_and_disconnect_memory(self):
        conn = DuckDBConnector(_mock_connection())
        ok = await conn.connect()
        assert ok is True
        assert conn._conn is not None
        await conn.disconnect()
        assert conn._conn is None

    @pytest.mark.asyncio
    async def test_connect_file_based(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LOCAL_DATABASE_ROOT", str(tmp_path))
        folder = tmp_path / "11111111-1111-4111-8111-111111111111"
        folder.mkdir()
        db_file = folder / "test.duckdb"
        duckdb.connect(str(db_file)).close()
        conn = DuckDBConnector(_mock_connection(database_path="test.duckdb"))
        assert await conn.connect()
        await conn.disconnect()
        assert db_file.exists()

    @pytest.mark.asyncio
    async def test_test_connection_returns_42(self):
        conn = DuckDBConnector(_mock_connection())
        result = await conn.test_connection()
        assert result["success"] is True
        assert result["details"]["answer"] == 42
        assert result["details"]["database_path"] == ":memory:"


# ---------------------------------------------------------------------------
# DuckDBConnector — query execution
# ---------------------------------------------------------------------------


class TestDuckDBConnectorQueries:
    @pytest.fixture
    async def connector(self):
        c = DuckDBConnector(_mock_connection())
        await c.connect()
        yield c
        await c.disconnect()

    @pytest.mark.asyncio
    async def test_basic_select(self, connector):
        result = await connector.execute_query("SELECT 1 AS a, 2 AS b")
        assert result["success"] is True
        assert result["row_count"] == 1
        assert result["columns"] == ["a", "b"]
        assert result["rows"][0] == {"a": 1, "b": 2}

    @pytest.mark.asyncio
    async def test_create_table_and_insert(self, connector):
        await connector.execute_query("CREATE TABLE t (id INTEGER, name VARCHAR)")
        await connector.execute_query("INSERT INTO t VALUES (1, 'alice'), (2, 'bob')")
        result = await connector.execute_query("SELECT * FROM t ORDER BY id")
        assert result["success"] is True
        assert result["row_count"] == 2
        assert result["rows"][0]["name"] == "alice"

    @pytest.mark.asyncio
    async def test_aggregation_query(self, connector):
        await connector.execute_query("CREATE TABLE sales (region VARCHAR, amount INTEGER)")
        await connector.execute_query("INSERT INTO sales VALUES ('east', 100), ('west', 200), ('east', 150)")
        result = await connector.execute_query(
            "SELECT region, SUM(amount) AS total FROM sales GROUP BY region ORDER BY region"
        )
        assert result["success"] is True
        assert result["row_count"] == 2
        totals = {r["region"]: r["total"] for r in result["rows"]}
        assert totals["east"] == 250
        assert totals["west"] == 200

    @pytest.mark.asyncio
    async def test_invalid_sql_returns_error(self, connector):
        result = await connector.execute_query("SELECT * FROM nonexistent_table_xyz")
        assert result["success"] is False
        assert result["error"]

    @pytest.mark.asyncio
    async def test_query_before_connect_returns_error(self):
        conn = DuckDBConnector(_mock_connection())
        # Not connected
        result = await conn.execute_query("SELECT 1")
        assert result["success"] is False
        assert "connect" in result["error"].lower()


# ---------------------------------------------------------------------------
# DuckDBConnector — CSV file reading (DuckDB special forms)
# ---------------------------------------------------------------------------


class TestDuckDBCSVReading:
    @pytest.fixture
    async def connector(self):
        c = DuckDBConnector(_mock_connection())
        await c.connect()
        yield c
        await c.disconnect()

    @pytest.mark.asyncio
    async def test_read_csv_auto(self, connector, tmp_path):
        csv_file = tmp_path / "data.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "score"])
            writer.writerow(["alice", "95"])
            writer.writerow(["bob", "87"])

        result = await connector.execute_query(f"SELECT * FROM read_csv_auto('{csv_file}') ORDER BY name")
        assert result["success"] is False
        assert "disabled" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_csv_aggregation(self, connector, tmp_path):
        csv_file = tmp_path / "events.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["category", "value"])
            for _ in range(5):
                writer.writerow(["A", "10"])
            for _ in range(3):
                writer.writerow(["B", "20"])

        result = await connector.execute_query(
            f"SELECT category, COUNT(*) AS cnt, SUM(value::INTEGER) AS total "
            f"FROM read_csv_auto('{csv_file}') GROUP BY category ORDER BY category"
        )
        assert result["success"] is False
        assert "disabled" in result["error"].lower()


# ---------------------------------------------------------------------------
# DuckDBConnector — schema introspection
# ---------------------------------------------------------------------------


class TestDuckDBSchema:
    @pytest.fixture
    async def connector(self):
        c = DuckDBConnector(_mock_connection())
        await c.connect()
        yield c
        await c.disconnect()

    @pytest.mark.asyncio
    async def test_get_tables_empty(self, connector):
        tables = await connector.get_tables()
        assert isinstance(tables, list)
        assert tables == []

    @pytest.mark.asyncio
    async def test_get_tables_after_create(self, connector):
        await connector.execute_query("CREATE TABLE users (id INTEGER, email VARCHAR)")
        await connector.execute_query("CREATE TABLE orders (id INTEGER, user_id INTEGER)")
        tables = await connector.get_tables()
        assert "users" in tables
        assert "orders" in tables

    @pytest.mark.asyncio
    async def test_get_schema(self, connector):
        await connector.execute_query("CREATE TABLE products (id INTEGER, name VARCHAR, price DOUBLE)")
        schema = await connector.get_schema()
        assert schema["success"] is True
        table_names = [t["name"] for t in schema["tables"]]
        assert "products" in table_names
        product = next(t for t in schema["tables"] if t["name"] == "products")
        col_names = [c["name"] for c in product["columns"]]
        assert "id" in col_names
        assert "name" in col_names
        assert "price" in col_names

    @pytest.mark.asyncio
    async def test_get_table_info(self, connector):
        await connector.execute_query("CREATE TABLE items (sku VARCHAR, qty INTEGER)")
        info = await connector.get_table_info("items")
        assert info["success"] is True
        assert info["table_name"] == "items"
        col_names = [c["name"] for c in info["columns"]]
        assert "sku" in col_names
        assert "qty" in col_names

    @pytest.mark.asyncio
    async def test_get_table_info_unsafe_name(self, connector):
        info = await connector.get_table_info("drop")
        assert info["success"] is False
        assert "unsafe" in info["error"].lower() or "invalid" in info["error"].lower()


# ---------------------------------------------------------------------------
# Row-count guard helpers (database_tools module)
# ---------------------------------------------------------------------------


class TestRowCountGuardHelpers:
    """Tests for _is_broad_select and _extract_from_table in database_tools."""

    def test_is_broad_select_plain(self):
        from src.services.agents.internal_tools.database_tools import _is_broad_select

        assert _is_broad_select("SELECT * FROM users") is True

    def test_is_broad_select_with_where(self):
        from src.services.agents.internal_tools.database_tools import _is_broad_select

        # WHERE alone doesn't make it safe — still broad
        assert _is_broad_select("SELECT * FROM users WHERE status = 'active'") is True

    def test_is_broad_select_with_limit(self):
        from src.services.agents.internal_tools.database_tools import _is_broad_select

        assert _is_broad_select("SELECT * FROM users LIMIT 100") is False

    def test_is_broad_select_with_group_by(self):
        from src.services.agents.internal_tools.database_tools import _is_broad_select

        assert _is_broad_select("SELECT status, COUNT(*) FROM users GROUP BY status") is False

    def test_is_broad_select_with_count(self):
        from src.services.agents.internal_tools.database_tools import _is_broad_select

        assert _is_broad_select("SELECT COUNT(*) FROM orders") is False

    def test_is_broad_select_with_avg(self):
        from src.services.agents.internal_tools.database_tools import _is_broad_select

        assert _is_broad_select("SELECT AVG(amount) FROM payments") is False

    def test_is_broad_select_non_select(self):
        from src.services.agents.internal_tools.database_tools import _is_broad_select

        assert _is_broad_select("INSERT INTO users VALUES (1)") is False

    def test_extract_from_table_simple(self):
        from src.services.agents.internal_tools.database_tools import _extract_from_table

        assert _extract_from_table("SELECT * FROM orders") == "orders"

    def test_extract_from_table_schema_qualified(self):
        from src.services.agents.internal_tools.database_tools import _extract_from_table

        assert _extract_from_table("SELECT * FROM public.users") == "public.users"

    def test_extract_from_table_quoted(self):
        from src.services.agents.internal_tools.database_tools import _extract_from_table

        result = _extract_from_table('SELECT * FROM "MyTable"')
        assert result == "MyTable"

    def test_extract_from_table_no_from(self):
        from src.services.agents.internal_tools.database_tools import _extract_from_table

        assert _extract_from_table("SELECT 1") is None
