"""Data Analysis tools for agents."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.data_analysis_service import DataAnalysisService
from src.services.report_export_service import ReportExportService

logger = logging.getLogger(__name__)


class DataAnalysisTools:
    """Tools for data analysis that agents can use."""

    def __init__(self, tenant_id: str, db: AsyncSession):
        """Initialize data analysis tools.

        Args:
            tenant_id: The tenant ID for the agent
            db: Async database session
        """
        self.tenant_id = tenant_id
        self.db = db
        self.analysis_service = DataAnalysisService(db)
        self.export_service = ReportExportService(db, tenant_id)

    def get_tools(self) -> list[dict[str, Any]]:
        """Get all data analysis tools available to the agent.

        Returns:
            List of tool definitions
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "query_datadog_metrics",
                    "description": "Query metrics from Datadog monitoring platform. Use this to fetch system metrics, application performance data, or custom metrics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data_source_id": {
                                "type": "integer",
                                "description": "The ID of the Datadog data source to query",
                            },
                            "query": {
                                "type": "string",
                                "description": "The Datadog metric query (e.g., 'avg:system.cpu.user{*}')",
                            },
                            "from_time": {
                                "type": "string",
                                "description": "Start time in ISO format (e.g., '2024-01-01T00:00:00Z')",
                            },
                            "to_time": {
                                "type": "string",
                                "description": "End time in ISO format (e.g., '2024-01-31T23:59:59Z')",
                            },
                        },
                        "required": ["data_source_id", "query", "from_time", "to_time"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_databricks",
                    "description": "Execute SQL queries on Databricks data lakehouse. Use this to analyze large datasets, run complex queries, or aggregate data.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data_source_id": {
                                "type": "integer",
                                "description": "The ID of the Databricks data source to query",
                            },
                            "query": {
                                "type": "string",
                                "description": "SQL query to execute (e.g., 'SELECT * FROM users LIMIT 100')",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of rows to return (default: 1000)",
                            },
                        },
                        "required": ["data_source_id", "query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_docker_logs",
                    "description": "Fetch logs from Docker containers. Use this to analyze application logs, debug issues, or monitor container activity.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data_source_id": {
                                "type": "integer",
                                "description": "The ID of the Docker data source to query",
                            },
                            "container_id": {"type": "string", "description": "Docker container ID to fetch logs from"},
                            "container_name": {
                                "type": "string",
                                "description": "Docker container name (alternative to container_id)",
                            },
                            "since": {"type": "string", "description": "Only return logs since this time (ISO format)"},
                            "tail": {
                                "type": "integer",
                                "description": "Number of lines from the end of the logs to show (default: 1000)",
                            },
                        },
                        "required": ["data_source_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_database",
                    "description": "Execute SQL queries on connected databases (PostgreSQL, SQLite, Elasticsearch). Use this to fetch data from your application databases.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "connection_id": {
                                "type": "string",
                                "description": "The UUID of the database connection to query",
                            },
                            "query": {"type": "string", "description": "SQL query to execute"},
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of rows to return (default: 1000)",
                            },
                        },
                        "required": ["connection_id", "query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_uploaded_file",
                    "description": "Analyze a previously uploaded CSV or data file. Returns statistics and data preview.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to the uploaded file in storage"}
                        },
                        "required": ["file_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "export_data_report",
                    "description": "Export analysis results or data to a file. Supports CSV, Excel, JSON, and HTML formats.",
                    "parameters": {
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
                                "description": "Export format",
                            },
                            "filename": {
                                "type": "string",
                                "description": "Name for the exported file (without extension)",
                            },
                            "title": {"type": "string", "description": "Title for the report (used in HTML/Excel)"},
                        },
                        "required": ["data", "format"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_data_statistics",
                    "description": "Calculate statistics for a dataset. Returns summary statistics, distributions, and insights.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "data": {
                                "type": "array",
                                "description": "Array of data objects to analyze",
                                "items": {"type": "object"},
                            },
                            "columns": {
                                "type": "array",
                                "description": "Specific columns to analyze (optional)",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["data"],
                    },
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a data analysis tool.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        try:
            if tool_name == "query_datadog_metrics":
                return await self._query_datadog_metrics(**arguments)
            elif tool_name == "query_databricks":
                return await self._query_databricks(**arguments)
            elif tool_name == "query_docker_logs":
                return await self._query_docker_logs(**arguments)
            elif tool_name == "query_database":
                return await self._query_database(**arguments)
            elif tool_name == "analyze_uploaded_file":
                return await self._analyze_uploaded_file(**arguments)
            elif tool_name == "export_data_report":
                return await self._export_data_report(**arguments)
            elif tool_name == "get_data_statistics":
                return await self._get_data_statistics(**arguments)
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"success": False, "error": str(e)}

    async def _query_datadog_metrics(
        self, data_source_id: int, query: str, from_time: str, to_time: str
    ) -> dict[str, Any]:
        """Query Datadog metrics."""
        result = await self.analysis_service.query_data_source(
            data_source_id=data_source_id,
            query_params={"query_type": "metrics", "query": query, "from_time": from_time, "to_time": to_time},
        )
        return result

    async def _query_databricks(self, data_source_id: int, query: str, limit: int | None = 1000) -> dict[str, Any]:
        """Query Databricks."""
        result = await self.analysis_service.query_data_source(
            data_source_id=data_source_id, query_params={"query": query, "limit": limit}
        )
        return result

    async def _query_docker_logs(
        self,
        data_source_id: int,
        container_id: str | None = None,
        container_name: str | None = None,
        since: str | None = None,
        tail: int | None = 1000,
    ) -> dict[str, Any]:
        """Query Docker logs."""
        query_params: dict[str, Any] = {"tail": tail}
        if container_id:
            query_params["container_id"] = container_id
        if container_name:
            query_params["container_name"] = container_name
        if since:
            query_params["since"] = since

        result = await self.analysis_service.query_data_source(data_source_id=data_source_id, query_params=query_params)
        return result

    async def _query_database(self, connection_id: str, query: str, limit: int | None = 1000) -> dict[str, Any]:
        """Query database."""
        result = await self.analysis_service.query_database(connection_id=connection_id, query=query, limit=limit)
        return result

    async def _analyze_uploaded_file(self, file_path: str) -> dict[str, Any]:
        """Analyze an uploaded file."""
        # Re-analyze the file from storage
        result = await self.analysis_service.analyze_file_from_path(file_path)
        return result

    async def _export_data_report(
        self, data: list[dict[str, Any]], format: str, filename: str | None = None, title: str | None = None
    ) -> dict[str, Any]:
        """Export data as a report."""
        result = await self.export_service.export_report(
            data=data,
            format=format,
            filename=filename or f"report_{int(__import__('time').time())}",
            title=title,
            tenant_id=self.tenant_id,
        )
        return result

    async def _get_data_statistics(
        self, data: list[dict[str, Any]], columns: list[str] | None = None
    ) -> dict[str, Any]:
        """Calculate statistics for data."""
        try:
            import pandas as pd

            df = pd.DataFrame(data)

            if columns:
                df = df[columns]

            stats = {
                "success": True,
                "row_count": len(df),
                "column_count": len(df.columns),
                "columns": list(df.columns),
                "data_types": df.dtypes.astype(str).to_dict(),
                "missing_values": df.isnull().sum().to_dict(),
                "numeric_stats": {},
            }

            # Get numeric column statistics
            numeric_cols = df.select_dtypes(include=["number"]).columns
            for col in numeric_cols:
                stats["numeric_stats"][col] = {
                    "mean": float(df[col].mean()),
                    "median": float(df[col].median()),
                    "std": float(df[col].std()),
                    "min": float(df[col].min()),
                    "max": float(df[col].max()),
                    "quartiles": {
                        "q25": float(df[col].quantile(0.25)),
                        "q50": float(df[col].quantile(0.50)),
                        "q75": float(df[col].quantile(0.75)),
                    },
                }

            return stats
        except Exception as e:
            return {"success": False, "error": f"Failed to calculate statistics: {str(e)}"}
