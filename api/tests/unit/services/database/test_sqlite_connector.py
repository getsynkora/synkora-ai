from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.database.sqlite_connector import SQLiteConnector


class TestSQLiteConnector:
    @pytest.fixture
    def connector(self):
        return SQLiteConnector(database_path="/tmp/test.db")

    @pytest.fixture
    def mock_cursor(self):
        # Use a custom class to handle both awaitable and async context manager behavior
        class MockCursor:
            def __init__(self):
                self.fetchall = AsyncMock()
                self.fetchmany = AsyncMock()
                self.fetchone = AsyncMock()
                self.description = [("col1",), ("col2",)]
                self.close = AsyncMock()

            def __await__(self):
                async def _():
                    return self

                return _().__await__()

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                pass

        return MockCursor()

    @pytest.fixture
    def mock_conn(self, mock_cursor):
        conn = MagicMock()
        # execute returns the cursor immediately, which handles await/async with
        conn.execute = MagicMock(return_value=mock_cursor)
        conn.close = AsyncMock()
        conn._execute = AsyncMock()
        conn.set_progress_handler = AsyncMock()
        conn.row_factory = None
        return conn

    @pytest.mark.asyncio
    async def test_connect_success(self, connector, mock_conn):
        with (
            patch("src.services.database.sqlite_connector.local_database_path", return_value="/tmp/test.db"),
            patch("src.services.database.sqlite_connector.Path") as MockPath,
            patch("src.services.database.sqlite_connector.aiosqlite.connect", new_callable=AsyncMock) as mock_connect,
        ):
            MockPath.return_value.parent.mkdir.return_value = None
            mock_connect.return_value = mock_conn

            result = await connector.connect()

            assert result is True
            assert connector._connection == mock_conn
            mock_connect.assert_called_once()
            # Verify foreign keys enabled
            mock_conn.execute.assert_any_call("PRAGMA foreign_keys = ON")

    @pytest.mark.asyncio
    async def test_connect_failure(self, connector):
        with patch("src.services.database.sqlite_connector.Path") as MockPath:
            MockPath.side_effect = Exception("Path error")

            result = await connector.connect()

            assert result is False
            assert connector._connection is None

    @pytest.mark.asyncio
    async def test_disconnect(self, connector, mock_conn):
        connector._connection = mock_conn
        await connector.disconnect()

        mock_conn.close.assert_called_once()
        assert connector._connection is None

    @pytest.mark.asyncio
    async def test_execute_query_success(self, connector, mock_conn, mock_cursor):
        connector._connection = mock_conn

        # Setup fetchall result
        # Note: rows are converted to dict in implementation using dict(row)
        # Since we can't easily mock aiosqlite.Row behavior with simple dicts in this custom class context if we returned pure dicts,
        # let's ensure the rows behave like mappings.
        # But implementation does `result_rows = [dict(row) for row in rows]`.
        # If row is a dict, dict(row) works.
        mock_cursor.fetchmany.return_value = [{"col1": "val1", "col2": "val2"}]

        result = await connector.execute_query("SELECT * FROM table")

        assert result["success"] is True
        assert result["rows"] == [{"col1": "val1", "col2": "val2"}]
        assert result["columns"] == ["col1", "col2"]

    @pytest.mark.asyncio
    async def test_execute_query_error(self, connector, mock_conn, mock_cursor):
        connector._connection = mock_conn
        mock_cursor.fetchmany.side_effect = Exception("Query Error")

        result = await connector.execute_query("SELECT * FROM table")

        assert result["success"] is False
        assert "Query Error" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_count(self, connector, mock_conn, mock_cursor):
        connector._connection = mock_conn
        mock_cursor.fetchone.return_value = [42]

        result = await connector.execute_count("SELECT COUNT(*) FROM table")

        assert result["success"] is True
        assert result["count"] == 42

    @pytest.mark.asyncio
    async def test_test_connection_success(self, connector, mock_conn, mock_cursor):
        with (
            patch.object(connector, "connect", return_value=True),
            patch.object(connector, "disconnect", new_callable=AsyncMock),
            patch("src.services.database.sqlite_connector.Path") as MockPath,
        ):
            connector._connection = mock_conn
            mock_cursor.fetchone.return_value = ["3.35.0"]

            MockPath.return_value.exists.return_value = True
            MockPath.return_value.stat.return_value.st_size = 1024

            result = await connector.test_connection()

            assert result["success"] is True
            assert "3.35.0" in result["details"]["version"]
            assert result["details"]["file_size_bytes"] == 1024

    @pytest.mark.asyncio
    async def test_get_tables(self, connector, mock_conn, mock_cursor):
        connector._connection = mock_conn
        mock_cursor.fetchall.return_value = [{"name": "t1"}, {"name": "t2"}]

        tables = await connector.get_tables()

        assert tables == ["t1", "t2"]

    @pytest.mark.asyncio
    async def test_get_schema(self, connector, mock_conn, mock_cursor):
        connector._connection = mock_conn

        # First fetchall: tables
        # Second fetchall: columns for table 1
        mock_cursor.fetchall.side_effect = [
            [{"name": "users", "type": "table"}],
            [{"name": "id", "type": "INTEGER", "notnull": 1, "dflt_value": None, "pk": 1}],
        ]

        result = await connector.get_schema()

        assert result["success"] is True
        assert len(result["tables"]) == 1
        table = result["tables"][0]
        assert table["name"] == "users"
        assert table["columns"][0]["name"] == "id"
        assert table["columns"][0]["primary_key"] is True

    @pytest.mark.asyncio
    async def test_get_table_info(self, connector, mock_conn, mock_cursor):
        connector._connection = mock_conn

        # Sequence: columns, fks, count
        mock_cursor.fetchall.side_effect = [
            [{"name": "id", "type": "INTEGER", "pk": 1}],  # columns
            [],  # fks
        ]
        mock_cursor.fetchone.return_value = [10]  # count

        result = await connector.get_table_info("users")

        assert result["success"] is True
        assert result["table_name"] == "users"
        assert result["primary_keys"] == ["id"]
        assert result["row_count"] == 10

    @pytest.mark.asyncio
    async def test_get_sample_data(self, connector):
        with patch.object(connector, "execute_query", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "rows": []}

            await connector.get_sample_data("users", limit=5)

            mock_execute.assert_called_once()
            args = mock_execute.call_args[0]
            assert "LIMIT ?" in args[0]
            assert args[1] == [5]
