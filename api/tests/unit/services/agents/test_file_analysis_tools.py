"""Unit tests for query_file_with_duckdb agent tool."""
import pytest
import pandas as pd
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_query_file_with_duckdb_success():
    """Returns rows, columns, and row_count on a successful query."""
    from src.services.agents.internal_tools.file_analysis_tools import query_file_with_duckdb

    mock_df = pd.DataFrame([{"category": "A", "total": 100}, {"category": "B", "total": 200}])
    s3_url = "s3://bucket/data-uploads/tenant/file.csv"

    with patch(
        "src.services.agents.internal_tools.file_analysis_tools._run_duckdb_query",
        new_callable=AsyncMock,
    ) as mock_run:
        mock_run.return_value = mock_df
        result = await query_file_with_duckdb(
            s3_url=s3_url,
            query=f"SELECT category, SUM(amount) AS total FROM read_csv_auto('{s3_url}') GROUP BY category",
        )

    assert result["success"] is True
    assert result["row_count"] == 2
    assert "category" in result["columns"]
    assert result["rows"][0]["category"] == "A"
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_query_file_rejects_non_s3_url():
    """Rejects URLs that do not use the s3:// scheme."""
    from src.services.agents.internal_tools.file_analysis_tools import query_file_with_duckdb

    result = await query_file_with_duckdb(
        s3_url="file:///etc/passwd",
        query="SELECT 1",
    )
    assert result["success"] is False
    assert "s3://" in result["error"]


@pytest.mark.asyncio
async def test_query_file_rejects_path_traversal_in_url():
    """Rejects s3 URLs containing '..' path traversal."""
    from src.services.agents.internal_tools.file_analysis_tools import query_file_with_duckdb

    result = await query_file_with_duckdb(
        s3_url="s3://bucket/../secret/file.csv",
        query="SELECT 1",
    )
    assert result["success"] is False
    assert ".." in result["error"]


@pytest.mark.asyncio
async def test_query_file_rejects_query_without_read_function():
    """Rejects SQL that does not reference a DuckDB read function."""
    from src.services.agents.internal_tools.file_analysis_tools import query_file_with_duckdb

    result = await query_file_with_duckdb(
        s3_url="s3://bucket/data-uploads/tenant/file.csv",
        query="SELECT * FROM some_table",
    )
    assert result["success"] is False
    assert "read_csv_auto" in result["error"]


@pytest.mark.asyncio
async def test_query_file_rejects_query_with_different_s3_url():
    """Rejects SQL where the s3_url in the query doesn't match the parameter."""
    from src.services.agents.internal_tools.file_analysis_tools import query_file_with_duckdb

    s3_url = "s3://bucket/data-uploads/tenant/file.csv"
    result = await query_file_with_duckdb(
        s3_url=s3_url,
        query="SELECT * FROM read_csv_auto('s3://bucket/other/secret.csv')",
    )
    assert result["success"] is False
    assert "s3_url" in result["error"]


@pytest.mark.asyncio
async def test_query_file_truncates_large_result():
    """Truncates results when row count exceeds MAX_ROWS."""
    from src.services.agents.internal_tools.file_analysis_tools import (
        MAX_ROWS,
        query_file_with_duckdb,
    )

    s3_url = "s3://bucket/data-uploads/tenant/file.csv"
    large_df = pd.DataFrame([{"id": i, "val": i * 2} for i in range(MAX_ROWS + 500)])

    with patch(
        "src.services.agents.internal_tools.file_analysis_tools._run_duckdb_query",
        new_callable=AsyncMock,
    ) as mock_run:
        mock_run.return_value = large_df
        result = await query_file_with_duckdb(
            s3_url=s3_url,
            query=f"SELECT id, val FROM read_csv_auto('{s3_url}')",
        )

    assert result["success"] is True
    assert result["row_count"] == MAX_ROWS
    assert result["truncated"] is True
    assert result["total_rows_in_result"] == MAX_ROWS + 500


@pytest.mark.asyncio
async def test_query_file_handles_duckdb_error_gracefully():
    """Returns success=False with error message when DuckDB raises."""
    from src.services.agents.internal_tools.file_analysis_tools import query_file_with_duckdb

    s3_url = "s3://bucket/data-uploads/tenant/file.csv"

    with patch(
        "src.services.agents.internal_tools.file_analysis_tools._run_duckdb_query",
        new_callable=AsyncMock,
    ) as mock_run:
        mock_run.side_effect = Exception("IO Error: file not found in S3")
        result = await query_file_with_duckdb(
            s3_url=s3_url,
            query=f"SELECT * FROM read_csv_auto('{s3_url}')",
        )

    assert result["success"] is False
    assert "IO Error" in result["error"]
