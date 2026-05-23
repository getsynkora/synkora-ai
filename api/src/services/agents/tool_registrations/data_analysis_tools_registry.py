"""Data Analysis Tools Registry - Registers data analysis tools with the ADK tool registry."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_data_analysis_tools(registry: Any):
    """
    Register data analysis tools with the ADK tool registry.

    These tools allow agents to query various data sources (Datadog, Databricks, Docker),
    analyze uploaded files, generate statistics, and export reports in multiple formats.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.file_analysis_tools import (
        query_file_with_duckdb,
    )
    from src.services.agents.tool_registrations.data_analysis_tool_functions import (
        analyze_data_statistics,
        export_data_report,
        list_data_sources,
        query_databricks,
        query_datadog_logs,
        query_datadog_metrics,
        query_docker_logs,
    )
    from src.services.agents.tool_registrations.generate_chart_from_csv import (
        generate_chart_from_data,
    )

    # Register data source discovery tool (must be listed first so agent discovers it)
    registry.register_tool(
        name="list_data_sources",
        description=(
            "List all configured Datadog, Databricks, and Docker connections available to this agent. "
            "Call this FIRST whenever you need to query these systems and don't already know the connection_id. "
            "Each result includes a 'connection_id' (UUID string) and a 'query_tool' field telling you "
            "which tool to call next. Datadog connections also expose a 'logs_tool' field — use "
            "query_datadog_metrics for time-series metrics and query_datadog_logs for log events."
        ),
        parameters={"type": "object", "properties": {}, "required": []},
        function=list_data_sources,
    )

    # Register Datadog metrics query tool
    registry.register_tool(
        name="query_datadog_metrics",
        description=(
            "Query TIME-SERIES METRICS from Datadog (e.g. CPU, memory, request rates, error rates). "
            "Use DogStatsD query syntax: 'avg:system.cpu.user{*}', 'sum:trace.web.request.hits{service:api}'. "
            "Returns metric series with timestamps and values. "
            "To query LOG EVENTS instead, use query_datadog_logs. "
            "If you don't know the connection_id, call list_data_sources first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "connection_id": {
                    "type": "string",
                    "description": "UUID of the Datadog connection (use list_data_sources to discover it)",
                },
                "query": {
                    "type": "string",
                    "description": "DogStatsD metric query (e.g., 'avg:system.cpu.user{*}' or 'sum:trace.web.request.hits{service:myapp}')",
                },
                "from_time": {
                    "type": "string",
                    "description": "Start time in ISO-8601 format (e.g., '2024-01-01T00:00:00Z')",
                },
                "to_time": {
                    "type": "string",
                    "description": "End time in ISO-8601 format (e.g., '2024-01-31T23:59:59Z')",
                },
            },
            "required": ["connection_id", "query", "from_time", "to_time"],
        },
        function=query_datadog_metrics,
    )

    # Register Datadog logs query tool
    registry.register_tool(
        name="query_datadog_logs",
        description=(
            "Search LOG EVENTS from Datadog using the Logs API v2. "
            "Use Datadog log search syntax: 'service:account_migration', 'status:error', "
            "'service:api @http.status_code:500', 'host:web-01 -status:info'. "
            "Returns log events with timestamp, message, service, status, host, and tags. "
            "Use this for log analysis, error investigation, and audit trails — NOT for metrics. "
            "If you don't know the connection_id, call list_data_sources first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "connection_id": {
                    "type": "string",
                    "description": "UUID of the Datadog connection (use list_data_sources to discover it)",
                },
                "query": {
                    "type": "string",
                    "description": "Datadog log search query (e.g., 'service:account_migration status:error' or '@http.status_code:[500 TO 599]')",
                },
                "from_time": {
                    "type": "string",
                    "description": "Start time in ISO-8601 format (e.g., '2024-01-01T00:00:00Z') or relative (e.g., 'now-1h')",
                },
                "to_time": {
                    "type": "string",
                    "description": "End time in ISO-8601 format or relative (e.g., 'now')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of log events to return (default: 100, max: 1000)",
                    "default": 100,
                },
            },
            "required": ["connection_id", "query", "from_time", "to_time"],
        },
        function=query_datadog_logs,
    )

    # Register Databricks SQL query tool
    registry.register_tool(
        name="query_databricks",
        description=(
            "Execute SQL queries on Databricks data lakehouse. Use this to analyze large datasets, "
            "run complex queries, or aggregate data. Returns query results with rows and columns. "
            "If you don't know the connection_id, call list_data_sources first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "connection_id": {
                    "type": "string",
                    "description": "UUID of the Databricks connection (use list_data_sources to discover it)",
                },
                "query": {
                    "type": "string",
                    "description": "SQL query to execute (e.g., 'SELECT * FROM users LIMIT 100')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return (default: 1000)",
                    "default": 1000,
                },
            },
            "required": ["connection_id", "query"],
        },
        function=query_databricks,
    )

    # Register Docker logs query tool
    registry.register_tool(
        name="query_docker_logs",
        description=(
            "Fetch logs from Docker containers. Use this to analyze application logs, debug issues, "
            "or monitor container activity. Returns log lines with timestamps. "
            "If you don't know the connection_id, call list_data_sources first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "connection_id": {
                    "type": "string",
                    "description": "UUID of the Docker connection (use list_data_sources to discover it)",
                },
                "container_id": {
                    "type": "string",
                    "description": "Docker container ID to fetch logs from (optional if container_name is provided)",
                },
                "container_name": {
                    "type": "string",
                    "description": "Docker container name (alternative to container_id)",
                },
                "since": {"type": "string", "description": "Only return logs since this time in ISO format (optional)"},
                "tail": {
                    "type": "integer",
                    "description": "Number of lines from the end of the logs to show (default: 1000)",
                    "default": 1000,
                },
            },
            "required": ["connection_id"],
        },
        function=query_docker_logs,
    )

    # Register data statistics calculator tool
    registry.register_tool(
        name="analyze_data_statistics",
        description="Calculate comprehensive statistics for a dataset. Accepts data in multiple formats (CSV text, JSON string, or query results). Automatically detects format and parses. Returns summary statistics (mean, median, std dev), distributions, missing values, and data types. Use this to understand data patterns and uploaded file contents.",
        parameters={
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Data as a string (CSV content, JSON array string, or any delimited text format - will be auto-detected and parsed)",
                },
                "columns": {
                    "type": "array",
                    "description": "Specific columns to analyze (optional, analyzes all if not specified)",
                    "items": {"type": "string"},
                },
            },
            "required": ["data"],
        },
        function=analyze_data_statistics,
    )

    # Register report export tool
    registry.register_tool(
        name="export_data_report",
        description="Export analysis results or data to a file. Supports CSV, Excel (.xlsx), JSON, and HTML formats. Returns download URL for the exported file. Use this to save and share analysis results.",
        parameters={
            "type": "object",
            "properties": {
                "data": {
                    "type": "array",
                    "description": "Array of data objects to export",
                    "items": {"type": "object"},
                },
                "format": {
                    "type": "string",
                    "enum": ["csv", "excel", "json", "html"],
                    "description": "Export format (csv, excel, json, or html)",
                },
                "filename": {
                    "type": "string",
                    "description": "Name for the exported file without extension (optional, auto-generated if not provided)",
                },
                "title": {
                    "type": "string",
                    "description": "Title for the report (used in HTML/Excel headers, optional)",
                },
            },
            "required": ["data", "format"],
        },
        function=export_data_report,
    )

    # Register chart generation tool for CSV/JSON data (different from internal_generate_chart
    # which takes DB query results — this one takes raw CSV/JSON strings from uploaded files)
    registry.register_tool(
        name="generate_chart_from_data",
        description=(
            "Generate a visualization from CSV or JSON string data. Use this for uploaded files or raw data strings. "
            "For database query results, use internal_generate_chart instead. "
            "IMPORTANT: After calling this tool the chart is automatically rendered in the UI — do NOT embed any image URL or markdown image syntax in your response. Simply describe the chart you created.\n\n"
            "Chart.js types (basic): bar, line, pie, doughnut, scatter\n"
            "Recharts types (advanced): area, stacked_bar, radar, treemap, funnel\n"
            "Plotly types (statistical): heatmap, box, violin, candlestick, waterfall\n\n"
            "Notes:\n"
            "- heatmap with no x/y columns builds a correlation matrix of all numeric columns\n"
            "- box/violin visualize distributions; no x_column needed (uses all numeric columns)\n"
            "- candlestick requires columns named open, high, low, close\n"
            "- stacked_bar uses x_column for categories; stacks all other numeric columns\n"
            "- funnel auto-sorts by value descending"
        ),
        parameters={
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "CSV text or JSON array string containing the data to visualize",
                },
                "chart_type": {
                    "type": "string",
                    "enum": [
                        "bar",
                        "line",
                        "pie",
                        "doughnut",
                        "scatter",
                        "area",
                        "stacked_bar",
                        "radar",
                        "treemap",
                        "funnel",
                        "heatmap",
                        "box",
                        "violin",
                        "candlestick",
                        "waterfall",
                    ],
                    "description": "Type of chart to generate",
                },
                "title": {"type": "string", "description": "Chart title"},
                "x_column": {
                    "type": "string",
                    "description": "Column name for X-axis / category / label column",
                },
                "y_column": {
                    "type": "string",
                    "description": "Column name for Y-axis / value column",
                },
                "description": {"type": "string", "description": "Optional chart description"},
            },
            "required": ["data", "chart_type", "title"],
        },
        function=generate_chart_from_data,
    )

    # Register DuckDB file query tool — lets agents query large uploaded CSV/Parquet/JSON files
    registry.register_tool(
        name="query_file_with_duckdb",
        description=(
            "Execute a SQL query against a large CSV, Parquet, or JSON file uploaded to S3. "
            "The file is queried in-process using DuckDB — no database connection record needed. "
            "The query MUST use read_csv_auto(s3_url), read_parquet(s3_url), or read_json_auto(s3_url) "
            "as the table source, where s3_url is the exact s3:// URL provided by the user.\n\n"
            "Examples:\n"
            "  SELECT * FROM read_csv_auto('s3://bucket/path/file.csv') LIMIT 10\n"
            "  SELECT category, SUM(amount) FROM read_csv_auto('s3://bucket/path/file.csv') GROUP BY category\n"
            "  SELECT * FROM read_parquet('s3://bucket/path/data.parquet') WHERE date > '2024-01-01'\n\n"
            "IMPORTANT — for large exports or when the user wants a downloadable file:\n"
            "  Set output_path to a filename like 'filtered.csv'. The full result is saved to the "
            "workspace and you get back the path — then call internal_s3_upload_file to upload it.\n"
            "  Without output_path, only up to 1000 rows are returned inline (for quick inspection)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "s3_url": {
                    "type": "string",
                    "description": "S3 URL of the uploaded file, e.g. s3://bucket/data-uploads/tenant/2026/05/19/uuid_sales.csv",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "DuckDB SQL query. Must reference the file via read_csv_auto(s3_url), "
                        "read_parquet(s3_url), or read_json_auto(s3_url). "
                        "Example: SELECT region, COUNT(*) FROM read_csv_auto('s3://...') GROUP BY region"
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": (
                        "Optional filename to save ALL query results as CSV in the workspace "
                        "(e.g. 'filtered.csv'). Use this whenever the user wants a downloadable file. "
                        "When set, rows are not returned inline — use internal_s3_upload_file next."
                    ),
                },
            },
            "required": ["s3_url", "query"],
        },
        function=query_file_with_duckdb,
    )

    logger.info("Registered 9 data analysis tools")
