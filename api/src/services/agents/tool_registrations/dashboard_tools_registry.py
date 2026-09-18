"""Registers internal_generate_dashboard for agents."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.services.agents.adk_tools import ToolRegistry

logger = logging.getLogger(__name__)


def register_dashboard_tools(registry: ToolRegistry) -> None:
    from src.services.agents.internal_tools.dashboard_tools import internal_generate_dashboard

    async def internal_generate_dashboard_wrapper(
        config: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        return await internal_generate_dashboard(**kwargs, config=config)

    registry.register_tool(
        name="internal_generate_dashboard",
        description=(
            "Generate an interactive HTML dashboard from structured data and a layout spec, "
            "upload it to S3, and return a shareable URL.\n\n"
            "The dashboard renders interactive Plotly.js charts, KPI metric cards, "
            "sortable/paginated tables, and dropdown filters — all in a single self-contained "
            "HTML file viewable in any browser.\n\n"
            "WORKFLOW:\n"
            "1. Call query_file_with_duckdb to load data from an uploaded CSV/Excel/Parquet:\n"
            "   query: SELECT * FROM read_csv_auto('s3://bucket/path/file.csv') LIMIT 10000\n"
            "   (For database connections, use the relevant DB query tool instead.)\n"
            "2. Inspect the returned columns and rows to understand the data.\n"
            "3. Design sections appropriate to the user's request.\n"
            "4. Call this tool with title, sections, and data.\n"
            "5. ALWAYS copy the exact 'url' value from the tool result and share it with the user as a clickable link. Never omit it.\n\n"
            "IMPORTANT CONSTRAINTS:\n"
            "- chart 'y' field MUST be a single column name string, never an array. For multi-metric comparisons, use separate chart sections.\n"
            "- chart 'x' field MUST be a single column name string.\n\n"
            "SECTION TYPES:\n"
            "- kpi_row: Row of metric cards. kpis: [{label, column, agg, prefix?, suffix?}]\n"
            "  agg options: sum | mean | max | min | count | first | last\n"
            "  Use column=null with agg='count' for total row count.\n"
            "- chart: Interactive Plotly chart. Fields: chart_type, title, x (string), y (string), agg?, orientation?\n"
            "  chart_type: bar | line | area | pie | scatter | heatmap | horizontal_bar\n"
            "  y must be a single column name string — for multiple metrics create multiple chart sections.\n"
            "- table: Sortable paginated table. Fields: title?, columns (list), page_size (default 20)\n"
            "- filter: Dropdown filtering all charts+tables. Fields: column, label?\n"
            "  Put filter sections first — they appear as a strip above the content.\n"
            "- text: Heading + paragraph. Fields: heading?, body?\n\n"
            "VISIBILITY:\n"
            "- presigned (default): private URL, expires in 7 days\n"
            "- public: permanent URL — only if user explicitly requests a public/shareable link\n\n"
            "EXAMPLE sections for a sales CSV with columns [region, revenue, month, rep]:\n"
            '[\n  {"type":"filter","column":"region"},\n'
            '  {"type":"kpi_row","kpis":[\n'
            '    {"label":"Total Revenue","column":"revenue","agg":"sum","prefix":"$"},\n'
            '    {"label":"Deals","column":null,"agg":"count"}\n  ]},\n'
            '  {"type":"chart","chart_type":"bar","title":"Revenue by Region","x":"region","y":"revenue","agg":"sum"},\n'
            '  {"type":"chart","chart_type":"line","title":"Monthly Trend","x":"month","y":"revenue"},\n'
            '  {"type":"table","columns":["rep","region","revenue"]}\n]'
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Dashboard heading shown at the top of the page",
                },
                "sections": {
                    "type": "array",
                    "description": (
                        "Ordered list of section objects. Each must have a 'type' field. "
                        "Filter sections are displayed first regardless of their position in this list."
                    ),
                    "items": {"type": "object"},
                },
                "data": {
                    "type": "array",
                    "description": (
                        "Array of row objects — the data to visualize. "
                        "Typically the 'rows' field returned by query_file_with_duckdb."
                    ),
                    "items": {"type": "object"},
                },
                "visibility": {
                    "type": "string",
                    "enum": ["presigned", "public"],
                    "description": "presigned = private 7-day URL (default). public = permanent direct URL.",
                },
                "theme": {
                    "type": "string",
                    "enum": ["light"],
                    "description": "Visual theme. Only 'light' is supported.",
                },
            },
            "required": ["title", "sections", "data"],
        },
        function=internal_generate_dashboard_wrapper,
        tool_category="dashboard",
    )

    logger.info("Registered internal_generate_dashboard tool")
