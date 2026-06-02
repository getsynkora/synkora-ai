"""
Infographic generation tools for autonomous agents.

Agents provide a structured data spec; this tool renders it to SVG (and
optionally PNG), uploads to S3, and returns a public/presigned URL that can
be posted to Slack or embedded anywhere.

The data-aggregation work (reading Slack KB, counting messages, extracting
top stories, etc.) is done by the agent using the existing KB query and Slack
tools *before* calling this tool.  This tool only handles rendering.

Spec schema — see ``services/diagrams/infographic_renderer.py`` for the full
reference.  Quick example::

    {
      "title":    "Daily Operations Briefing",
      "subtitle": "Engineering · Sales · Ops",
      "date":     "Apr 16, 2026",
      "theme":    "midnight",
      "sections": [
        {
          "type": "kpi_row",
          "items": [
            {"label": "Messages today", "value": 342, "change": "+12%", "trend": "up"},
            {"label": "Active users",   "value": 18},
            {"label": "Channels",       "value": 9}
          ]
        },
        {
          "type":  "bar_chart",
          "title": "Channel Activity",
          "data": [
            {"label": "#engineering", "value": 120},
            {"label": "#sales",       "value": 80},
            {"label": "#general",     "value": 60}
          ]
        },
        {
          "type":  "stories",
          "title": "Top Stories",
          "items": [
            {
              "headline": "PR #412 merged — new auth system live",
              "body":     "The 3-week auth overhaul landed. Login latency dropped 40%.",
              "channel":  "#engineering",
              "author":   "Alice"
            }
          ]
        }
      ]
    }
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Maximum spec size accepted (prevents runaway SVG generation)
_MAX_SPEC_BYTES = 256 * 1024  # 256 KB

_THEME_ALIASES = {
    "dark": "midnight",
    "light": "daylight",
    "glass": "aurora",
}


def _normalize_infographic_theme(theme: str | None) -> str:
    if not theme:
        return "midnight"
    return _THEME_ALIASES.get(theme.strip().lower(), theme)


async def internal_generate_infographic(
    spec: str,
    output_format: str = "svg",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a data-driven infographic from a structured JSON spec.

    The infographic is rendered as SVG by a pure-Python engine (no browser,
    no external dependencies).  If ``cairosvg`` is installed the result can
    also be exported as a high-resolution PNG.

    Args:
        spec:
            JSON string matching the infographic spec schema.  Must contain
            at least ``"title"`` and ``"sections"``.
        output_format:
            ``"svg"`` (default) · ``"png"`` · ``"both"``.
            PNG export requires ``cairosvg`` to be installed.
        config:
            Runtime tool config (injected by adk_tools.py).  Used to derive
            ``tenant_id`` for S3 key namespacing.

    Returns:
        ``{"success": True, "svg_url": ..., "png_url": ..., "svg_content": ...}``
        or ``{"success": False, "error": ...}``.
    """
    # 1. Validate input size
    if len(spec.encode()) > _MAX_SPEC_BYTES:
        return {"success": False, "error": "Spec too large (max 256 KB)"}

    # 2. Parse JSON
    try:
        spec_dict = json.loads(spec)
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"Invalid JSON spec: {exc}"}

    if not isinstance(spec_dict, dict):
        return {"success": False, "error": "Spec must be a JSON object"}

    if not spec_dict.get("title"):
        return {"success": False, "error": "Spec must include a 'title' field"}

    if not spec_dict.get("width"):
        sections = spec_dict.get("sections") or []
        if (
            len(sections) == 1
            and isinstance(sections[0], dict)
            and sections[0].get("type") == "assessment_scorecard"
            and sections[0].get("layout") != "classic"
        ):
            spec_dict["width"] = 820

    # 3. Render SVG
    try:
        from src.services.diagrams.infographic_renderer import render_infographic

        svg_content = render_infographic(spec_dict)
    except Exception as exc:
        logger.exception("Infographic SVG render failed")
        return {"success": False, "error": f"Render failed: {exc}"}

    # 4. Upload SVG to S3
    svg_url: str | None = None
    png_url: str | None = None

    tenant_id = (config or {}).get("tenant_id", "default")
    date_path = datetime.now(UTC).strftime("%Y-%m-%d")
    file_id = uuid.uuid4().hex[:12]
    svg_s3_key = f"infographics/{tenant_id}/{date_path}/{file_id}.svg"

    try:
        from src.services.storage.s3_storage import get_s3_storage

        s3 = get_s3_storage()
        s3.upload_file(file_content=svg_content.encode(), key=svg_s3_key, content_type="image/svg+xml")
        svg_url = s3.generate_presigned_url(key=svg_s3_key, expiration=86400 * 7)
    except Exception:
        logger.debug("S3 SVG upload skipped (not configured or unavailable)")

    # 5. Optional PNG conversion
    if output_format in ("png", "both"):
        try:
            import cairosvg  # type: ignore[import-untyped]

            png_bytes = cairosvg.svg2png(
                bytestring=svg_content.encode(),
                output_width=int(spec_dict.get("width", 900)) * 2,  # 2x for retina
            )
            png_s3_key = svg_s3_key.replace(".svg", ".png")

            from src.services.storage.s3_storage import get_s3_storage

            _s3 = get_s3_storage()
            _s3.upload_file(file_content=png_bytes, key=png_s3_key, content_type="image/png")
            png_url = _s3.generate_presigned_url(key=png_s3_key, expiration=86400 * 7)
        except ImportError:
            logger.debug("cairosvg not installed — PNG export skipped")
        except Exception as exc:
            logger.warning(f"PNG conversion failed: {exc}")

    # 6. Return result
    # Keep more SVGs inline so chat renders the exact vector output instead of
    # falling back to a raster/image tag for medium-complexity infographics.
    inline_svg = svg_content if len(svg_content) < 160_000 else None

    return {
        "success": True,
        "title": spec_dict.get("title"),
        "theme": spec_dict.get("theme", "midnight"),
        "svg_url": svg_url,
        "png_url": png_url,
        "svg_content": inline_svg,
        "note": (
            "To post to Slack: use internal_slack_post_blocks with an image block containing png_url. "
            "Slack image blocks require PNG — do NOT use svg_url in an image block. "
            "If png_url is null, use internal_slack_upload_file with svg_content as a fallback."
        ),
    }


async def internal_generate_slack_infographic(
    title: str,
    date: str,
    kpis: str,
    bar_chart_title: str,
    bar_chart_data: str,
    stories: str,
    theme: str = "midnight",
    heatmap_data: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """High-level helper that builds the spec and calls internal_generate_infographic.

    This is easier for agents to call than constructing the full spec JSON,
    as each section is a separate parameter.

    Args:
        title:
            Infographic headline, e.g. ``"Daily Operations Briefing"``.
        date:
            Date string shown in header badge, e.g. ``"Apr 16, 2026"``.
        kpis:
            JSON array of KPI items::

                [{"label": "Messages", "value": 342, "change": "+12%", "trend": "up"}]

        bar_chart_title:
            Title for the channel-activity bar chart.
        bar_chart_data:
            JSON array of bar entries::

                [{"label": "#engineering", "value": 120}]

        stories:
            JSON array of story items::

                [{"headline": "...", "body": "...", "channel": "#eng", "author": "Alice"}]

        theme:
            Named preset. Recommended: ``"midnight"`` for briefings and
            ``"daylight"`` for clean editorial/lifestyle infographics.
            Legacy aliases ``"dark"``, ``"light"``, and ``"glass"`` still work.
        heatmap_data:
            Optional JSON array of 7 arrays (days) × 24 ints (hours) for an
            activity heatmap section.
        config:
            Runtime tool config (injected by adk_tools.py).

    Returns:
        Same shape as ``internal_generate_infographic``.
    """
    try:
        kpis_list = json.loads(kpis)
        bar_data_list = json.loads(bar_chart_data)
        stories_list = json.loads(stories)
    except json.JSONDecodeError as exc:
        return {"success": False, "error": f"Invalid JSON parameter: {exc}"}

    sections: list[dict] = [
        {"type": "kpi_row", "items": kpis_list},
        {"type": "divider"},
        {"type": "bar_chart", "title": bar_chart_title, "data": bar_data_list},
        {"type": "divider"},
        {"type": "stories", "title": "Top Stories", "items": stories_list},
    ]

    if heatmap_data:
        try:
            hm = json.loads(heatmap_data)
            sections.append({"type": "divider"})
            sections.append(
                {
                    "type": "heatmap",
                    "title": "Hourly Activity (this week)",
                    "data": hm,
                }
            )
        except json.JSONDecodeError:
            logger.warning("heatmap_data is not valid JSON — skipping heatmap section")

    spec_dict = {
        "title": title,
        "date": date,
        "theme": _normalize_infographic_theme(theme),
        "sections": sections,
    }

    return await internal_generate_infographic(
        spec=json.dumps(spec_dict),
        output_format="both",
        config=config,
    )
