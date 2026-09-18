"""
Dashboard generation tool for autonomous agents.

Agents provide:
  - title: dashboard heading
  - sections: ordered list of section specs (kpi_row, chart, table, filter, text)
  - data: list of row dicts (from query_file_with_duckdb or a DB query tool)
  - visibility: "presigned" (default, 7-day private URL) or "public"

This tool renders the HTML and uploads to S3.  No LLM calls inside.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from src.services.storage.s3_storage import get_s3_storage

logger = logging.getLogger(__name__)

_MAX_DATA_ROWS = 50_000


async def internal_generate_dashboard(
    title: str,
    sections: list[dict],
    data: list[dict],
    visibility: str = "presigned",
    theme: str = "light",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate an interactive HTML dashboard, upload to S3, return URL.

    Args:
        title:      Dashboard heading displayed at the top of the page.
        sections:   Ordered list of section spec dicts.
        data:       List of row dicts (output of query_file_with_duckdb or similar).
        visibility: "presigned" -> 7-day signed URL (default).
                    "public"    -> permanent URL using public endpoint.
        theme:      Only "light" is supported.
        config:     Runtime config injected by adk_tools.py (contains tenant_id).

    Returns:
        {"success": True, "url": ..., "visibility": ..., "expires_at": ...}
        or {"success": False, "error": ...}
    """
    # --- Input validation ---
    if not title or not title.strip():
        return {"success": False, "error": "title is required"}
    if not sections:
        return {"success": False, "error": "sections must not be empty"}
    if not isinstance(data, list):
        return {"success": False, "error": "data must be an array of row objects"}
    if len(data) > _MAX_DATA_ROWS:
        return {"success": False, "error": f"data exceeds {_MAX_DATA_ROWS} row limit ({len(data)} rows given)"}
    if visibility not in ("presigned", "public"):
        return {"success": False, "error": "visibility must be 'presigned' or 'public'"}

    # --- Render HTML ---
    try:
        from src.services.dashboards.dashboard_renderer import render_dashboard

        html, render_warnings = render_dashboard(title.strip(), sections, data)
    except Exception as exc:
        logger.exception("Dashboard render failed")
        return {"success": False, "error": f"Render failed: {exc}"}

    # --- Upload to S3 ---
    tenant_id = (config or {}).get("tenant_id", "default")
    dashboard_id = uuid.uuid4().hex
    s3_key = f"dashboards/{tenant_id}/{dashboard_id}.html"

    try:
        s3 = get_s3_storage()
        s3.upload_file(
            file_content=html.encode("utf-8"),
            key=s3_key,
            content_type="text/html",
        )
    except Exception as exc:
        logger.exception("Dashboard S3 upload failed")
        return {"success": False, "error": f"Upload failed: {exc}"}

    # --- Generate URL ---
    try:
        if visibility == "presigned":
            url = s3.generate_presigned_url(key=s3_key, expiration=604800)
            expires_at = (datetime.now(UTC) + timedelta(days=7)).isoformat()
            result: dict[str, Any] = {
                "success": True,
                "url": url,
                "expires_at": expires_at,
                "visibility": "presigned",
            }
        else:
            # internal_endpoint_url is the S3 API endpoint used for signed requests, NOT a
            # publicly-readable file host — using it for an unsigned URL 403s unless the
            # bucket has a public-read policy. Only public_endpoint_url is safe to assume
            # is actually anonymous-readable; otherwise fall back to a long-lived signed URL.
            if s3.public_endpoint_url:
                url = f"{s3.public_endpoint_url.rstrip('/')}/{s3.bucket_name}/{s3_key}"
                result = {"success": True, "url": url, "visibility": "public"}
            else:
                url = s3.generate_presigned_url(key=s3_key, expiration=86400 * 365)
                result = {
                    "success": True,
                    "url": url,
                    "visibility": "public",
                    "expires_at": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
                    "note": "No public S3 endpoint configured — returned a 1-year signed URL instead of a permanent one.",
                }
    except Exception as exc:
        return {"success": False, "error": f"URL generation failed: {exc}"}

    if render_warnings:
        result["warnings"] = render_warnings

    return result
