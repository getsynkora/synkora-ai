"""Report Export Service for generating reports in various formats."""

import asyncio
import html
import io
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.storage import get_storage_service, storage_config
from src.services.security.report_files import local_report_path, report_key

logger = logging.getLogger(__name__)

# Formula injection prefixes that trigger execution in spreadsheet apps (Excel, Google Sheets)
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _sanitize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Prefix any formula-like string values with a single quote so they render as text."""
    sanitized = {}
    for k, v in row.items():
        if isinstance(v, str) and v.startswith(_FORMULA_PREFIXES):
            sanitized[k] = "'" + v
        else:
            sanitized[k] = v
    return sanitized


class ReportExportService:
    """Service for exporting data analysis reports."""

    def __init__(self, db: AsyncSession, tenant_id: UUID):
        """Initialize report export service.

        Args:
            db: Async database session
            tenant_id: Tenant ID
        """
        self.db = db
        self.tenant_id = tenant_id
        self.storage = get_storage_service()

    async def _store_report(self, filename: str, content: bytes) -> str:
        if (
            not filename
            or filename in {".", ".."}
            or any(c in filename for c in "/\\%?#")
            or any(ord(c) < 32 for c in filename)
        ):
            raise ValueError("Invalid report filename")
        key = report_key(
            f"reports/{self.tenant_id}/{datetime.now(UTC).strftime('%Y/%m/%d')}/{uuid4().hex}_{filename}",
            self.tenant_id,
        )
        if storage_config.STORAGE_TYPE == "local":
            local_report_path(storage_config.local_storage_path, key, self.tenant_id)
        await asyncio.to_thread(self.storage.save_file, key, content)
        return key

    async def export_to_csv(self, data: list[dict[str, Any]], filename: str | None = None) -> dict[str, Any]:
        """Export data to CSV format.

        Args:
            data: List of dictionaries containing data
            filename: Custom filename (default: auto-generated)

        Returns:
            Dict with export info and file path
        """
        try:
            if not data:
                return {"success": False, "message": "No data to export"}

            # SECURITY: Sanitize formula injection before export
            sanitized_data = [_sanitize_row(row) for row in data]

            # Convert to DataFrame
            df = pd.DataFrame(sanitized_data)

            # Generate CSV
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue()

            # Generate filename
            if not filename:
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                filename = f"report_{timestamp}.csv"
            elif not filename.endswith(".csv"):
                filename = f"{filename}.csv"

            # Upload to storage
            stored_path = await self._store_report(filename, csv_content.encode("utf-8"))

            return {
                "success": True,
                "format": "csv",
                "file_path": stored_path,
                "file_name": filename,
                "file_size": len(csv_content),
                "rows": len(df),
                "columns": len(df.columns),
            }

        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")
            return {"success": False, "message": f"CSV export failed: {str(e)}", "error": str(e)}

    async def export_to_excel(
        self,
        data: list[dict[str, Any]] | dict[str, list[dict[str, Any]]],
        filename: str | None = None,
        sheet_name: str = "Sheet1",
    ) -> dict[str, Any]:
        """Export data to Excel format.

        Args:
            data: List of dicts or dict of sheet_name -> list of dicts
            filename: Custom filename (default: auto-generated)
            sheet_name: Sheet name (if single dataset)

        Returns:
            Dict with export info and file path
        """
        try:
            if not data:
                return {"success": False, "message": "No data to export"}

            # Create Excel writer
            excel_buffer = io.BytesIO()

            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                if isinstance(data, dict):
                    # Multiple sheets
                    for sheet, sheet_data in data.items():
                        if sheet_data:
                            # SECURITY: Sanitize formula injection per sheet
                            clean = [_sanitize_row(r) for r in sheet_data]
                            df = pd.DataFrame(clean)
                            df.to_excel(writer, sheet_name=sheet, index=False)
                else:
                    # Single sheet
                    # SECURITY: Sanitize formula injection
                    clean = [_sanitize_row(r) for r in data]
                    df = pd.DataFrame(clean)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

            excel_content = excel_buffer.getvalue()

            # Generate filename
            if not filename:
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                filename = f"report_{timestamp}.xlsx"
            elif not filename.endswith(".xlsx"):
                filename = f"{filename}.xlsx"

            # Upload to storage
            stored_path = await self._store_report(filename, excel_content)

            return {
                "success": True,
                "format": "excel",
                "file_path": stored_path,
                "file_name": filename,
                "file_size": len(excel_content),
            }

        except Exception as e:
            logger.error(f"Failed to export to Excel: {e}")
            return {"success": False, "message": f"Excel export failed: {str(e)}", "error": str(e)}

    async def export_to_json(self, data: Any, filename: str | None = None, pretty: bool = True) -> dict[str, Any]:
        """Export data to JSON format.

        Args:
            data: Data to export
            filename: Custom filename (default: auto-generated)
            pretty: Pretty-print JSON

        Returns:
            Dict with export info and file path
        """
        try:
            if not data:
                return {"success": False, "message": "No data to export"}

            # Generate JSON
            if pretty:
                json_content = json.dumps(data, indent=2, default=str)
            else:
                json_content = json.dumps(data, default=str)

            # Generate filename
            if not filename:
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                filename = f"report_{timestamp}.json"
            elif not filename.endswith(".json"):
                filename = f"{filename}.json"

            # Upload to storage
            stored_path = await self._store_report(filename, json_content.encode("utf-8"))

            return {
                "success": True,
                "format": "json",
                "file_path": stored_path,
                "file_name": filename,
                "file_size": len(json_content),
            }

        except Exception as e:
            logger.error(f"Failed to export to JSON: {e}")
            return {"success": False, "message": f"JSON export failed: {str(e)}", "error": str(e)}

    async def export_to_html(
        self,
        data: list[dict[str, Any]],
        filename: str | None = None,
        title: str = "Data Analysis Report",
        include_charts: bool = False,
    ) -> dict[str, Any]:
        """Export data to HTML format.

        Args:
            data: List of dictionaries containing data
            filename: Custom filename (default: auto-generated)
            title: Report title
            include_charts: Include visualizations (requires plotly)

        Returns:
            Dict with export info and file path
        """
        try:
            if not data:
                return {"success": False, "message": "No data to export"}

            # Convert to DataFrame
            df = pd.DataFrame(data)

            # Generate HTML
            html_parts = [
                "<!DOCTYPE html>",
                "<html>",
                "<head>",
                "<meta charset='utf-8'>",
                f"<title>{html.escape(title)}</title>",
                "<style>",
                "body { font-family: Arial, sans-serif; margin: 20px; }",
                "h1 { color: #333; }",
                "table { border-collapse: collapse; width: 100%; margin-top: 20px; }",
                "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
                "th { background-color: #4CAF50; color: white; }",
                "tr:nth-child(even) { background-color: #f2f2f2; }",
                "</style>",
                "</head>",
                "<body>",
                f"<h1>{html.escape(title)}</h1>",
                f"<p>Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>",
                f"<p>Total rows: {len(df)}</p>",
                df.to_html(index=False, classes="data-table", escape=True),
                "</body>",
                "</html>",
            ]

            html_content = "\n".join(html_parts)

            # Generate filename
            if not filename:
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                filename = f"report_{timestamp}.html"
            elif not filename.endswith(".html"):
                filename = f"{filename}.html"

            # Upload to storage
            stored_path = await self._store_report(filename, html_content.encode("utf-8"))

            return {
                "success": True,
                "format": "html",
                "file_path": stored_path,
                "file_name": filename,
                "file_size": len(html_content),
                "rows": len(df),
            }

        except Exception as e:
            logger.error(f"Failed to export to HTML: {e}")
            return {"success": False, "message": f"HTML export failed: {str(e)}", "error": str(e)}

    async def export_to_pdf(
        self, data: list[dict[str, Any]], filename: str | None = None, title: str = "Data Analysis Report"
    ) -> dict[str, Any]:
        """Export data to PDF format.

        Args:
            data: List of dictionaries containing data
            filename: Custom filename (default: auto-generated)
            title: Report title

        Returns:
            Dict with export info and file path
        """
        try:
            # First export to HTML, then convert to PDF
            # Note: This requires wkhtmltopdf or similar tool
            # For now, we'll return an error suggesting to use HTML export
            return {
                "success": False,
                "message": "PDF export requires additional setup. Please use HTML or Excel format instead.",
                "error": "PDF export not yet implemented. Install wkhtmltopdf or use HTML export.",
            }

        except Exception as e:
            logger.error(f"Failed to export to PDF: {e}")
            return {"success": False, "message": f"PDF export failed: {str(e)}", "error": str(e)}

    async def export_report(
        self, data: list[dict[str, Any]] | dict[str, Any], format: str = "csv", filename: str | None = None, **kwargs
    ) -> dict[str, Any]:
        """Export report in specified format.

        Args:
            data: Data to export
            format: Export format (csv, excel, json, html, pdf)
            filename: Custom filename
            **kwargs: Additional format-specific parameters

        Returns:
            Dict with export info
        """
        format = format.lower()

        if format == "csv":
            return await self.export_to_csv(data, filename)
        elif format in ["excel", "xlsx"]:
            return await self.export_to_excel(data, filename, **kwargs)
        elif format == "json":
            return await self.export_to_json(data, filename, **kwargs)
        elif format == "html":
            return await self.export_to_html(data, filename, **kwargs)
        elif format == "pdf":
            return await self.export_to_pdf(data, filename, **kwargs)
        else:
            return {
                "success": False,
                "message": f"Unsupported export format: {format}. Supported formats: csv, excel, json, html",
            }
