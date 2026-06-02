"""
Infographic Renderer — modern, bold, data-driven SVG reports.

Theming is fully open. Pass:
  - A preset name string:   "aurora" | "midnight" | "carbon" | "sunset" | "emerald" | "daylight"
  - A full custom dict:     {"bg": "#fff", "palette": ["#f00", "#0f0"], ...}
  - A partial override:     {"preset": "midnight", "palette": ["#custom1", "#custom2"]}

All keys are optional — missing ones fall back to the "aurora" defaults.

Input schema
------------
{
  "title":    str,
  "subtitle": str,           # optional
  "date":     str,           # optional — pill badge in header
  "theme":    str | dict,    # see above
  "width":    int,           # optional, default 900
  "sections": [
    {"type": "kpi_row",         "items": [{"label", "value", "change"?, "trend"?: "up"|"down"}]},
    {"type": "bar_chart",       "title": str, "data": [{"label", "value", "color"?}]},
    {"type": "donut",           "title": str, "data": [{"label", "value", "color"?}]},
    {"type": "stories",         "title": str, "items": [{"headline", "body", "channel"?, "author"?}]},
    {"type": "heatmap",         "title": str, "data": [[24 ints] x 7], "row_labels"?: [str x 7]},
    {"type": "divider",         "label"?: str},
    {"type": "text",            "content": str},
    {"type": "sustainability_dashboard",
     "brand"?: str, "report_label"?: str, "title": str, "subtitle"?: str, "cta_label"?: str,
     "stats"?: [{"label", "value", "change"?, "icon_name"?}],
     "impacts"?: [{"title", "body"?, "value", "icon_name"?, "color"?}],
     "emissions"?: {"title"?: str, "subtitle"?: str, "value", "change"?, "filter_label"?,
                    "series": [number], "x_labels"?: [str]},
     "operations"?: {"title"?: str, "regions": [{"label", "value", "icon_name"?}]},
     "focus_areas"?: [{"title", "body"?, "icon_name"?}],
     "recognitions"?: [{"title", "subtitle"?, "icon_name"?, "color"?}],
     "quote"?: {"text": str, "author"?: str},
     "principles"?: [{"label", "icon_name"?}]},
    {"type": "assessment_scorecard",
     "badge"?: str, "title": str, "subtitle"?: str,
     "facts"?: [{"label", "value", "icon_name"?}],
     "score": number, "max_score"?: number, "status"?: str, "score_note"?: str,
     "delta"?: str, "delta_caption"?: str, "percentile_label"?: str, "percentile_value"?: str,
     "categories"?: [{"title", "body"?, "value", "status"?, "icon_name"?, "color"?}],
     "insights"?: [{"title", "body"?, "icon_name"?, "color"?}],
     "recommendation"?: {"title", "body"?, "icon_name"?},
     "footer"?: {"title"?: str, "body"?: str, "note"?: str, "icon_name"?: str}},
    {"type": "showcase_dashboard",
     "cards": [
       {"variant": "business_performance", "title", "subtitle"?, "overall"?: {"label"?, "value", "status"?},
        "stats"?: [{"label", "value", "change"?, "icon_name"?}],
        "trend"?: {"title"?, "series": [number], "x_labels"?: [str], "badge"?: str},
        "channels"?: {"title"?: str, "data": [{"label", "value", "color"?}]},
        "takeaway"?: {"title"?, "body"?}, "next_steps"?: {"title"?, "items"?: [str]}},
       {"variant": "sustainability_impact", "title", "subtitle"?, "stats"?: [{"label", "value", "change"?, "icon_name"?}],
        "metric"?: {"title"?, "value", "subtitle"?, "change"?, "series": [number], "x_labels"?: [str]},
        "focus_areas"?: [{"title", "body"?, "icon_name"?}], "quote"?: {"text", "author"?, "icon_name"?}},
       {"variant": "customer_satisfaction", "title", "subtitle"?, "score"?: {"value", "max"?, "label"?},
        "callout"?: {"title"?, "body"?, "icon_name"?}, "stats"?: [{"label", "value", "change"?, "icon_name"?}],
        "trend"?: {"title"?, "series": [number], "x_labels"?: [str], "badge"?: str},
        "feedback"?: {"title"?: str, "items"?: [str], "icon_name"?}},
       {"variant": "project_roadmap", "title", "subtitle"?, "progress"?: {"label"?, "value"},
        "phases"?: [{"phase"?, "title", "body"?, "status"?, "icon_name"?}],
        "milestones"?: {"title"?: str, "items"?: [{"label", "title", "status"?, "icon_name"?}]}},
       {"variant": "financial_highlights", "title", "subtitle"?, "series"?: {"labels"?: [str], "bars"?: [{"label", "values": [number], "color"?}]},
        "metrics"?: [{"label", "value", "change"?, "icon_name"?, "color"?}],
        "kpis"?: [{"label", "value", "change"?, "icon_name"?}]},
       {"variant": "employee_engagement", "title", "subtitle"?, "score"?: {"label"?, "value", "max"?, "status"?},
        "dimensions"?: [{"label", "value"}], "stats"?: [{"label", "value", "change"?}],
        "quote"?: {"text", "cta"?}}
     ]},
    # AntV-parity section types:
    {"type": "process_flow",    "title"?: str, "items": [{"title", "body"?}]},
    {"type": "circular_flow",   "title"?: str, "items": [{"title", "body"?, "icon"?, "icon_name"?}],
                                "center_label"?: str, "center_icon"?: str, "center_icon_name"?: str,
                                "side_note"?: {"title", "body"?, "icon"?, "icon_name"?},
                                "footer_panel"?: {"title", "body"?, "icon"?, "icon_name"?,
                                                  "steps"?: [{"label", "icon"?, "icon_name"?}]},
                                "quote"?: str, "quote_icon"?: str, "quote_icon_name"?: str},
    {"type": "staircase",       "title"?: str, "items": [{"label", "value"?}]},
    {"type": "pyramid",         "title"?: str, "items": [{"label", "body"?}]},
    {"type": "snake_path",      "title"?: str, "items": [{"label"}]},
    {"type": "bubble_chain",    "title"?: str, "items": [{"label", "value"}]},
    {"type": "timeline",        "title"?: str, "items": [{"label", "date"?, "body"?}]},
    {"type": "venn",            "title"?: str, "items": [{"label", "items"?: [str]}], "center_label"?: str},
    {"type": "comparison",      "title"?: str, "left": {"label", "items": [str]}, "right": {"label", "items": [str]}},
    {"type": "swot",            "title"?: str, "quadrants": [{"label", "items": [str]}]},
    {"type": "matrix_2x2",      "title"?: str, "cells": [{"label", "body"}], "x_label"?: str, "y_label"?: str},
    {"type": "quadrant_circle", "title"?: str, "quadrants": [{"label", "value"?}], "center_label"?: str},
    {"type": "card_grid",       "title"?: str, "items": [{"title", "body"}], "cols"?: int},
    {"type": "pill_list",       "title"?: str, "items": [{"label", "sub"?}]},
    {"type": "wheel",           "title"?: str, "data": [{"label", "value"?, "color"?}], "equal"?: bool, "center_label"?: str},
  ]
}
"""

from __future__ import annotations

import math
from xml.sax.saxutils import escape as _xml_escape

# ---------------------------------------------------------------------------
# Theme presets
# ---------------------------------------------------------------------------

_BASE: dict = {
    "bg": "#08070E",
    "header_from": "#1A0533",
    "header_to": "#0F0A1E",
    "card_bg": "#100E1A",
    "card_border": "#2D2550",
    "stroke_soft": "#3A305C",
    "text": "#F2EFFF",
    "muted": "#6E6A85",
    "palette": ["#8B5CF6", "#06B6D4", "#10B981", "#F59E0B", "#EF4444", "#EC4899"],
    "trend_up": "#10B981",
    "trend_down": "#EF4444",
    "font": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "font_display": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "font_ui": "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    "paper_tint": "#0B0814",
    "shadow_color": "#000000",
    "radius": 14,
    "bar_h": 28,
}

PRESETS: dict[str, dict] = {
    "aurora": {
        **_BASE,
        # deep violet/purple with cyan and green
    },
    "midnight": {
        **_BASE,
        "bg": "#050912",
        "header_from": "#081830",
        "header_to": "#050912",
        "card_bg": "#0C1525",
        "card_border": "#172B4A",
        "stroke_soft": "#203B62",
        "text": "#E5F0FF",
        "muted": "#4E6A8C",
        "palette": ["#06B6D4", "#3B82F6", "#8B5CF6", "#10B981", "#F59E0B", "#EF4444"],
        "trend_up": "#10B981",
        "trend_down": "#EF4444",
    },
    "carbon": {
        **_BASE,
        "bg": "#0B0B0D",
        "header_from": "#1C1C22",
        "header_to": "#0B0B0D",
        "card_bg": "#131316",
        "card_border": "#26262E",
        "stroke_soft": "#353542",
        "text": "#F5F5F7",
        "muted": "#68687A",
        "palette": ["#F97316", "#3B82F6", "#10B981", "#F59E0B", "#EC4899", "#8B5CF6"],
        "trend_up": "#10B981",
        "trend_down": "#EF4444",
    },
    "sunset": {
        **_BASE,
        "bg": "#0F0A06",
        "header_from": "#2C1206",
        "header_to": "#0F0A06",
        "card_bg": "#1C1008",
        "card_border": "#3A2016",
        "stroke_soft": "#503025",
        "text": "#FFF0E8",
        "muted": "#8A6A58",
        "palette": ["#F97316", "#EF4444", "#F59E0B", "#EC4899", "#8B5CF6", "#06B6D4"],
        "trend_up": "#F59E0B",
        "trend_down": "#EF4444",
    },
    "emerald": {
        **_BASE,
        "bg": "#050F09",
        "header_from": "#091E12",
        "header_to": "#050F09",
        "card_bg": "#0A1810",
        "card_border": "#163024",
        "stroke_soft": "#244937",
        "text": "#E8FFF4",
        "muted": "#4A7A60",
        "palette": ["#10B981", "#06B6D4", "#3B82F6", "#84CC16", "#8B5CF6", "#F59E0B"],
        "trend_up": "#10B981",
        "trend_down": "#EF4444",
    },
    "daylight": {
        **_BASE,
        "bg": "#F5F4F0",
        "header_from": "#F5F4F0",
        "header_to": "#F0EDE6",
        "card_bg": "#FFFFFF",
        "card_border": "#EBEBEB",
        "stroke_soft": "#E0DCDA",
        "text": "#1B1E23",
        "muted": "#6F726F",
        "palette": ["#54AE74", "#5E92EA", "#8A79EC", "#F18675", "#F0BE48", "#EE8BB4"],
        "trend_up": "#4BAF7D",
        "trend_down": "#E8614E",
        "font": "'Avenir Next', 'Helvetica Neue', 'Segoe UI', Arial, sans-serif",
        "font_display": "'Avenir Next', 'Helvetica Neue', 'Segoe UI', Arial, sans-serif",
        "font_ui": "'SF Pro Display', 'Avenir Next', 'Helvetica Neue', 'Segoe UI', Arial, sans-serif",
        "paper_tint": "#FAFAFA",
        "shadow_color": "#B0A898",
        "radius": 20,
        "bar_h": 26,
    },
}

DEFAULT_PRESET = "aurora"

# Layout constants
_PAD_H = 32
_PAD_V = 28
_GAP = 14
_SEC_GAP = 36


def resolve_theme(theme_input: str | dict | None) -> dict:
    """
    Resolve theme input to a complete theme dict.

    Accepts:
    - str: preset name  →  use that preset
    - dict with "preset" key  →  start from preset, override with remaining keys
    - dict without "preset"   →  start from default preset, override with provided keys
    - None / unknown           →  return default preset
    """
    base = {**PRESETS[DEFAULT_PRESET]}

    if isinstance(theme_input, str):
        preset = PRESETS.get(theme_input, PRESETS[DEFAULT_PRESET])
        return {**base, **preset}

    if isinstance(theme_input, dict):
        preset_name = theme_input.get("preset", DEFAULT_PRESET)
        preset = PRESETS.get(preset_name, PRESETS[DEFAULT_PRESET])
        merged = {**base, **preset}
        overrides = {k: v for k, v in theme_input.items() if k != "preset"}
        merged.update(overrides)
        return merged

    return base


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------


def _lighten(color: str, factor: float = 0.35) -> str:
    """Mix a #RRGGBB color toward white. Returns original on parse failure."""
    try:
        h = color.lstrip("#")
        if len(h) != 6:
            return color
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))
        return f"#{r:02X}{g:02X}{b:02X}"
    except Exception:
        return color


def _mix(color_a: str, color_b: str, factor: float = 0.5) -> str:
    """Mix two #RRGGBB colors. ``factor`` closer to 1 favors ``color_b``."""
    try:
        a = color_a.lstrip("#")
        b = color_b.lstrip("#")
        if len(a) != 6 or len(b) != 6:
            return color_a
        ar, ag, ab = int(a[0:2], 16), int(a[2:4], 16), int(a[4:6], 16)
        br, bg, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
        r = int(ar + (br - ar) * factor)
        g = int(ag + (bg - ag) * factor)
        b2 = int(ab + (bb - ab) * factor)
        return f"#{r:02X}{g:02X}{b2:02X}"
    except Exception:
        return color_a


def _alpha(color: str, opacity: float) -> str:
    """Return an rgba(...) string from a hex color and opacity."""
    try:
        h = color.lstrip("#")
        if len(h) != 6:
            return color
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{opacity:.2f})"
    except Exception:
        return color


# ---------------------------------------------------------------------------
# SVG primitive helpers
# ---------------------------------------------------------------------------


def _e(s: object) -> str:
    return _xml_escape(str(s))


def _attrs(**kw: object) -> str:
    parts = []
    for k, v in kw.items():
        if v is None:
            continue
        # Attribute values sit inside "…" — escape & < > and "
        safe = _xml_escape(str(v), {'"': "&quot;"})
        parts.append(f'{k.replace("_", "-")}="{safe}"')
    return " ".join(parts)


def _rect(x: float, y: float, w: float, h: float, rx: float = 0, **kw: object) -> str:
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" {_attrs(**kw)}/>'


def _text(x: float, y: float, content: str, **kw: object) -> str:
    return f'<text x="{x:.1f}" y="{y:.1f}" {_attrs(**kw)}>{_e(content)}</text>'


def _line(x1: float, y1: float, x2: float, y2: float, **kw: object) -> str:
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" {_attrs(**kw)}/>'


def _path(d: str, **kw: object) -> str:
    return f'<path d="{d}" {_attrs(**kw)}/>'


def _circle(cx: float, cy: float, r: float, **kw: object) -> str:
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" {_attrs(**kw)}/>'


def _group(content: str, **kw: object) -> str:
    return f"<g {_attrs(**kw)}>{content}</g>"


def _wrap_text(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        words = paragraph.split()
        if not words:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines or [""]


def _is_light_theme(t: dict) -> bool:
    color = str(t.get("bg", "#000000")).lstrip("#")
    if len(color) != 6:
        return False
    r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return luminance >= 0.72


def _num(value: object, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            cleaned = value.strip().replace("%", "").replace(",", "")
            if not cleaned:
                return default
            return float(cleaned)
        return float(value)
    except Exception:
        return default


_ICON_ALIASES: dict[str, str] = {
    "activity": "shoe",
    "arrow": "arrow-right",
    "book-open": "book",
    "breathe": "mindfulness",
    "care": "heart",
    "calendar": "calendar",
    "code": "code",
    "crescent": "moon",
    "drink": "glass",
    "globe": "globe",
    "focus": "mindfulness",
    "growth": "leaf",
    "habit": "leaf",
    "hydrate": "glass",
    "learn": "book",
    "layers": "layers",
    "lightbulb": "lightbulb",
    "meditate": "mindfulness",
    "mind": "mindfulness",
    "mindful": "mindfulness",
    "moon": "sleep",
    "move": "shoe",
    "night": "sleep",
    "progress": "mountain",
    "read": "book",
    "rest": "sleep",
    "shoe": "shoe",
    "sleep": "sleep",
    "small-step": "plant",
    "spark": "spark",
    "server": "server",
    "shield": "shield",
    "sun": "sun",
    "sunlight": "sun",
    "target": "target",
    "tree": "tree",
    "trophy": "trophy",
    "user": "user",
    "walk": "shoe",
    "water": "glass",
}


def _normalize_icon_name(name: str | None) -> str | None:
    if not name:
        return None
    normalized = str(name).strip().lower().replace("_", "-").replace(" ", "-")
    return _ICON_ALIASES.get(normalized, normalized)


def _infer_icon_name(*texts: object) -> str | None:
    haystack = " ".join(str(text).lower() for text in texts if text)
    keyword_map = [
        ("glass", ["hydrate", "water", "drink", "hydration"]),
        ("calendar", ["date", "calendar", "assessment date"]),
        ("user", ["assessed for", "client", "company", "organization"]),
        ("mindfulness", ["mind", "breath", "reflect", "calm", "meditat", "focus"]),
        ("shoe", ["move", "walk", "run", "exercise", "activity", "fitness"]),
        ("sun", ["sun", "light", "morning", "daylight"]),
        ("book", ["learn", "study", "read", "curious", "knowledge"]),
        ("sleep", ["sleep", "rest", "night", "recovery"]),
        ("server", ["infrastructure", "reliability", "it infrastructure"]),
        ("shield", ["security", "protection", "governance", "compliance"]),
        ("layers", ["scalability", "scale", "stack"]),
        ("code", ["developer", "code", "engineering"]),
        ("spark", ["automation", "innovation", "improve"]),
        ("target", ["recommendation", "goal", "focus"]),
        ("globe", ["impact", "global", "operate", "world"]),
        ("lightbulb", ["insight", "idea"]),
        ("trophy", ["award", "recognition", "leader"]),
        ("leaf", ["habit", "better", "growth", "wellness", "health"]),
        ("heart", ["care", "consistency", "love", "body"]),
        ("mountain", ["progress", "improve", "showing up", "effort"]),
        ("plant", ["start", "small", "seed"]),
        ("tree", ["change", "result", "outcome"]),
    ]
    for icon_name, keywords in keyword_map:
        if any(keyword in haystack for keyword in keywords):
            return icon_name
    return None


def _render_named_icon(name: str, cx: float, cy: float, size: float, color: str, stroke_width: float = 2.0) -> str:
    icon_name = _normalize_icon_name(name)
    if not icon_name:
        return ""

    s = size / 24.0

    def px(n: float) -> float:
        return cx + (n - 12) * s

    def py(n: float) -> float:
        return cy + (n - 12) * s

    shared = {
        "fill": "none",
        "stroke": color,
        "stroke_width": f"{stroke_width * s:.2f}",
        "stroke_linecap": "round",
        "stroke_linejoin": "round",
    }

    parts: list[str] = []

    if icon_name == "glass":
        parts.extend(
            [
                _path(
                    f"M {px(7):.1f} {py(5):.1f} L {px(17):.1f} {py(5):.1f} "
                    f"L {px(15):.1f} {py(19):.1f} L {px(9):.1f} {py(19):.1f} Z",
                    **shared,
                ),
                _path(f"M {px(9):.1f} {py(12):.1f} Q {px(12):.1f} {py(10.5):.1f} {px(15):.1f} {py(12):.1f}", **shared),
            ]
        )
    elif icon_name == "mindfulness":
        parts.extend(
            [
                _circle(px(12), py(6.5), 2.6 * s, **shared),
                _path(
                    f"M {px(8):.1f} {py(13):.1f} C {px(8.4):.1f} {py(10.2):.1f} {px(10.1):.1f} {py(9):.1f} "
                    f"{px(12):.1f} {py(9):.1f} C {px(13.9):.1f} {py(9):.1f} {px(15.6):.1f} {py(10.2):.1f} "
                    f"{px(16):.1f} {py(13):.1f}",
                    **shared,
                ),
                _path(
                    f"M {px(5.2):.1f} {py(17):.1f} C {px(7.6):.1f} {py(14.3):.1f} {px(9.2):.1f} {py(13.2):.1f} "
                    f"{px(12):.1f} {py(13.2):.1f} C {px(14.8):.1f} {py(13.2):.1f} {px(16.4):.1f} {py(14.3):.1f} "
                    f"{px(18.8):.1f} {py(17):.1f}",
                    **shared,
                ),
                _line(px(8.5), py(17.2), px(15.5), py(17.2), **shared),
            ]
        )
    elif icon_name == "shoe":
        parts.extend(
            [
                _path(
                    f"M {px(4.5):.1f} {py(15.5):.1f} C {px(7.2):.1f} {py(14.6):.1f} {px(9.3):.1f} {py(12.4):.1f} "
                    f"{px(11.3):.1f} {py(9.5):.1f} L {px(15.5):.1f} {py(11.6):.1f} "
                    f"C {px(16.3):.1f} {py(13.9):.1f} {px(18.2):.1f} {py(15.1):.1f} {px(20.2):.1f} {py(15.4):.1f} "
                    f"L {px(20.2):.1f} {py(18.1):.1f} L {px(4.5):.1f} {py(18.1):.1f} Z",
                    **shared,
                ),
                _line(px(10), py(12.3), px(12.4), py(13.2), **shared),
                _line(px(8.4), py(14.3), px(10.9), py(15.2), **shared),
            ]
        )
    elif icon_name == "sun":
        parts.extend(
            [
                _circle(px(12), py(12), 4.2 * s, **shared),
                _line(px(12), py(2.8), px(12), py(6), **shared),
                _line(px(12), py(18), px(12), py(21.2), **shared),
                _line(px(2.8), py(12), px(6), py(12), **shared),
                _line(px(18), py(12), px(21.2), py(12), **shared),
                _line(px(5.2), py(5.2), px(7.5), py(7.5), **shared),
                _line(px(16.5), py(16.5), px(18.8), py(18.8), **shared),
                _line(px(18.8), py(5.2), px(16.5), py(7.5), **shared),
                _line(px(7.5), py(16.5), px(5.2), py(18.8), **shared),
            ]
        )
    elif icon_name == "book":
        parts.extend(
            [
                _path(
                    f"M {px(5):.1f} {py(6.5):.1f} C {px(7):.1f} {py(5.4):.1f} {px(9.2):.1f} {py(5):.1f} "
                    f"{px(11):.1f} {py(5):.1f} C {px(12.5):.1f} {py(5):.1f} {px(13.6):.1f} {py(5.4):.1f} "
                    f"{px(14.8):.1f} {py(6):.1f} L {px(14.8):.1f} {py(18.2):.1f} "
                    f"C {px(13.4):.1f} {py(17.2):.1f} {px(12.4):.1f} {py(17):.1f} {px(11):.1f} {py(17):.1f} "
                    f"C {px(9):.1f} {py(17):.1f} {px(7):.1f} {py(17.5):.1f} {px(5):.1f} {py(18.4):.1f} Z",
                    **shared,
                ),
                _path(
                    f"M {px(19):.1f} {py(6.5):.1f} C {px(17):.1f} {py(5.4):.1f} {px(14.8):.1f} {py(5):.1f} "
                    f"{px(13):.1f} {py(5):.1f} C {px(11.5):.1f} {py(5):.1f} {px(10.4):.1f} {py(5.4):.1f} "
                    f"{px(9.2):.1f} {py(6):.1f} L {px(9.2):.1f} {py(18.2):.1f} "
                    f"C {px(10.6):.1f} {py(17.2):.1f} {px(11.6):.1f} {py(17):.1f} {px(13):.1f} {py(17):.1f} "
                    f"C {px(15):.1f} {py(17):.1f} {px(17):.1f} {py(17.5):.1f} {px(19):.1f} {py(18.4):.1f} Z",
                    **shared,
                ),
                _line(px(12), py(6), px(12), py(18), **shared),
            ]
        )
    elif icon_name == "sleep":
        parts.extend(
            [
                _path(
                    f"M {px(14.8):.1f} {py(4.2):.1f} A {4.9 * s:.1f} {4.9 * s:.1f} 0 1 0 {px(17.1):.1f} {py(13.4):.1f} "
                    f"A {5.8 * s:.1f} {5.8 * s:.1f} 0 1 1 {px(14.8):.1f} {py(4.2):.1f}",
                    **shared,
                ),
                _path(
                    f"M {px(17.9):.1f} {py(6.8):.1f} L {px(18.6):.1f} {py(8.2):.1f} "
                    f"L {px(20):.1f} {py(8.9):.1f} L {px(18.6):.1f} {py(9.6):.1f} "
                    f"L {px(17.9):.1f} {py(11):.1f} L {px(17.2):.1f} {py(9.6):.1f} "
                    f"L {px(15.8):.1f} {py(8.9):.1f} L {px(17.2):.1f} {py(8.2):.1f} Z",
                    **shared,
                ),
                _path(
                    f"M {px(19.8):.1f} {py(12.4):.1f} L {px(20.2):.1f} {py(13.3):.1f} "
                    f"L {px(21.1):.1f} {py(13.7):.1f} L {px(20.2):.1f} {py(14.1):.1f} "
                    f"L {px(19.8):.1f} {py(15):.1f} L {px(19.3):.1f} {py(14.1):.1f} "
                    f"L {px(18.4):.1f} {py(13.7):.1f} L {px(19.3):.1f} {py(13.3):.1f} Z",
                    **shared,
                ),
            ]
        )
    elif icon_name == "leaf":
        parts.extend(
            [
                _path(
                    f"M {px(12):.1f} {py(18.8):.1f} C {px(11):.1f} {py(13.4):.1f} {px(12.2):.1f} {py(9.5):.1f} "
                    f"{px(15.8):.1f} {py(6.2):.1f} C {px(18):.1f} {py(4.3):.1f} {px(20.2):.1f} {py(3.3):.1f} "
                    f"{px(20):.1f} {py(6.6):.1f} C {px(19.6):.1f} {py(12.2):.1f} {px(17):.1f} {py(16.8):.1f} "
                    f"{px(12):.1f} {py(18.8):.1f} Z",
                    **shared,
                ),
                _path(
                    f"M {px(12):.1f} {py(19):.1f} C {px(10.1):.1f} {py(15.4):.1f} {px(7.5):.1f} {py(12.5):.1f} "
                    f"{px(4.5):.1f} {py(12.3):.1f} C {px(4.1):.1f} {py(9.7):.1f} {px(5.6):.1f} {py(7.2):.1f} "
                    f"{px(8.1):.1f} {py(6.3):.1f} C {px(11):.1f} {py(5.2):.1f} {px(12.7):.1f} {py(7.3):.1f} "
                    f"{px(12):.1f} {py(19):.1f} Z",
                    **shared,
                ),
                _path(
                    f"M {px(12):.1f} {py(18.8):.1f} C {px(13.3):.1f} {py(13.6):.1f} {px(15.2):.1f} {py(10.2):.1f} {px(18):.1f} {py(7.6):.1f}",
                    **shared,
                ),
            ]
        )
    elif icon_name == "heart":
        parts.append(
            _path(
                f"M {px(12):.1f} {py(19):.1f} C {px(5.6):.1f} {py(15):.1f} {px(3.8):.1f} {py(11.2):.1f} "
                f"{px(3.8):.1f} {py(8.3):.1f} C {px(3.8):.1f} {py(5.9):.1f} {px(5.7):.1f} {py(4.2):.1f} "
                f"{px(8):.1f} {py(4.2):.1f} C {px(9.8):.1f} {py(4.2):.1f} {px(11.1):.1f} {py(5.2):.1f} "
                f"{px(12):.1f} {py(6.4):.1f} C {px(12.9):.1f} {py(5.2):.1f} {px(14.2):.1f} {py(4.2):.1f} "
                f"{px(16):.1f} {py(4.2):.1f} C {px(18.3):.1f} {py(4.2):.1f} {px(20.2):.1f} {py(5.9):.1f} "
                f"{px(20.2):.1f} {py(8.3):.1f} C {px(20.2):.1f} {py(11.2):.1f} {px(18.4):.1f} {py(15):.1f} "
                f"{px(12):.1f} {py(19):.1f} Z",
                **shared,
            )
        )
    elif icon_name == "mountain":
        parts.extend(
            [
                _path(
                    f"M {px(4):.1f} {py(18.3):.1f} L {px(9.2):.1f} {py(12.2):.1f} L {px(12.1):.1f} {py(14.8):.1f} "
                    f"L {px(16.9):.1f} {py(8.2):.1f} L {px(20.4):.1f} {py(18.3):.1f} Z",
                    **shared,
                ),
                _line(px(4), py(20.2), px(20.5), py(20.2), **shared),
                _line(px(16), py(6), px(20.2), py(6), **shared),
                _line(px(20.2), py(6), px(20.2), py(10.2), **shared),
            ]
        )
    elif icon_name == "plant":
        parts.extend(
            [
                _line(px(12), py(6.3), px(12), py(19.2), **shared),
                _path(
                    f"M {px(12):.1f} {py(9.4):.1f} C {px(10.5):.1f} {py(7.5):.1f} {px(8.1):.1f} {py(6.8):.1f} "
                    f"{px(5.8):.1f} {py(7.4):.1f} C {px(5.9):.1f} {py(10.1):.1f} {px(7.4):.1f} {py(12.4):.1f} "
                    f"{px(12):.1f} {py(12):.1f} Z",
                    **shared,
                ),
                _path(
                    f"M {px(12):.1f} {py(11):.1f} C {px(13.7):.1f} {py(8.4):.1f} {px(16.1):.1f} {py(7.5):.1f} "
                    f"{px(18.8):.1f} {py(7.8):.1f} C {px(18.5):.1f} {py(10.8):.1f} {px(16.6):.1f} {py(13.2):.1f} "
                    f"{px(12):.1f} {py(13):.1f} Z",
                    **shared,
                ),
                _line(px(7.5), py(20.4), px(16.5), py(20.4), **shared),
            ]
        )
    elif icon_name == "tree":
        parts.extend(
            [
                _line(px(12), py(12.2), px(12), py(19.6), **shared),
                _path(
                    f"M {px(12):.1f} {py(4.2):.1f} C {px(8.5):.1f} {py(4.2):.1f} {px(6.2):.1f} {py(6.4):.1f} "
                    f"{px(6.2):.1f} {py(9.1):.1f} C {px(4.4):.1f} {py(9.6):.1f} {px(3.2):.1f} {py(11.1):.1f} "
                    f"{px(3.2):.1f} {py(13):.1f} C {px(3.2):.1f} {py(15.6):.1f} {px(5.4):.1f} {py(17.8):.1f} "
                    f"{px(8.4):.1f} {py(17.8):.1f} H {px(15.6):.1f} C {px(18.6):.1f} {py(17.8):.1f} {px(20.8):.1f} {py(15.6):.1f} "
                    f"{px(20.8):.1f} {py(13):.1f} C {px(20.8):.1f} {py(11.1):.1f} {px(19.6):.1f} {py(9.6):.1f} "
                    f"{px(17.8):.1f} {py(9.1):.1f} C {px(17.8):.1f} {py(6.4):.1f} {px(15.5):.1f} {py(4.2):.1f} "
                    f"{px(12):.1f} {py(4.2):.1f} Z",
                    **shared,
                ),
                _line(px(8.2), py(21), px(15.8), py(21), **shared),
            ]
        )
    elif icon_name == "arrow-right":
        parts.extend(
            [
                _line(px(4), py(12), px(19.5), py(12), **shared),
                _path(
                    f"M {px(14.5):.1f} {py(7):.1f} L {px(19.5):.1f} {py(12):.1f} L {px(14.5):.1f} {py(17):.1f}",
                    **shared,
                ),
            ]
        )
    elif icon_name == "server":
        parts.extend(
            [
                _rect(px(5), py(5), 14 * s, 4.2 * s, rx=1.6 * s, **shared),
                _rect(px(5), py(10), 14 * s, 4.2 * s, rx=1.6 * s, **shared),
                _rect(px(5), py(15), 14 * s, 4.2 * s, rx=1.6 * s, **shared),
                _circle(px(8), py(7.1), 0.7 * s, fill=color),
                _circle(px(8), py(12.1), 0.7 * s, fill=color),
                _circle(px(8), py(17.1), 0.7 * s, fill=color),
            ]
        )
    elif icon_name == "shield":
        parts.extend(
            [
                _path(
                    f"M {px(12):.1f} {py(4.3):.1f} L {px(18.4):.1f} {py(6.7):.1f} "
                    f"L {px(18.4):.1f} {py(11.3):.1f} C {px(18.4):.1f} {py(15.8):.1f} {px(15.6):.1f} {py(19):.1f} "
                    f"{px(12):.1f} {py(20.5):.1f} C {px(8.4):.1f} {py(19):.1f} {px(5.6):.1f} {py(15.8):.1f} "
                    f"{px(5.6):.1f} {py(11.3):.1f} L {px(5.6):.1f} {py(6.7):.1f} Z",
                    **shared,
                ),
                _path(
                    f"M {px(9.4):.1f} {py(12.2):.1f} L {px(11.2):.1f} {py(14):.1f} L {px(15.2):.1f} {py(10):.1f}",
                    **shared,
                ),
            ]
        )
    elif icon_name == "layers":
        parts.extend(
            [
                _path(
                    f"M {px(12):.1f} {py(4.5):.1f} L {px(19.5):.1f} {py(8.5):.1f} L {px(12):.1f} {py(12.5):.1f} L {px(4.5):.1f} {py(8.5):.1f} Z",
                    **shared,
                ),
                _path(
                    f"M {px(12):.1f} {py(10):.1f} L {px(19.5):.1f} {py(14):.1f} L {px(12):.1f} {py(18):.1f} L {px(4.5):.1f} {py(14):.1f} Z",
                    **shared,
                ),
                _path(
                    f"M {px(12):.1f} {py(15.5):.1f} L {px(19.5):.1f} {py(19.5):.1f} L {px(12):.1f} {py(23.5):.1f} L {px(4.5):.1f} {py(19.5):.1f} Z",
                    **shared,
                ),
            ]
        )
    elif icon_name == "code":
        parts.extend(
            [
                _path(
                    f"M {px(8.5):.1f} {py(8):.1f} L {px(4.5):.1f} {py(12):.1f} L {px(8.5):.1f} {py(16):.1f}", **shared
                ),
                _path(
                    f"M {px(15.5):.1f} {py(8):.1f} L {px(19.5):.1f} {py(12):.1f} L {px(15.5):.1f} {py(16):.1f}",
                    **shared,
                ),
                _line(px(13.3), py(6), px(10.7), py(18), **shared),
            ]
        )
    elif icon_name == "spark":
        parts.extend(
            [
                _path(
                    f"M {px(12):.1f} {py(4.5):.1f} L {px(13.7):.1f} {py(9.6):.1f} L {px(18.8):.1f} {py(11.3):.1f} L {px(13.7):.1f} {py(13):.1f} L {px(12):.1f} {py(18.1):.1f} L {px(10.3):.1f} {py(13):.1f} L {px(5.2):.1f} {py(11.3):.1f} L {px(10.3):.1f} {py(9.6):.1f} Z",
                    **shared,
                ),
                _line(px(12), py(2.5), px(12), py(5), **shared),
                _line(px(20), py(11.3), px(22.5), py(11.3), **shared),
            ]
        )
    elif icon_name == "globe":
        parts.extend(
            [
                _circle(px(12), py(12), 8 * s, **shared),
                _line(px(4), py(12), px(20), py(12), **shared),
                _path(
                    f"M {px(12):.1f} {py(4):.1f} C {px(8.8):.1f} {py(7.2):.1f} {px(8.8):.1f} {py(16.8):.1f} {px(12):.1f} {py(20):.1f}",
                    **shared,
                ),
                _path(
                    f"M {px(12):.1f} {py(4):.1f} C {px(15.2):.1f} {py(7.2):.1f} {px(15.2):.1f} {py(16.8):.1f} {px(12):.1f} {py(20):.1f}",
                    **shared,
                ),
                _path(
                    f"M {px(6):.1f} {py(8):.1f} C {px(9):.1f} {py(9.5):.1f} {px(15):.1f} {py(9.5):.1f} {px(18):.1f} {py(8):.1f}",
                    **shared,
                ),
                _path(
                    f"M {px(6):.1f} {py(16):.1f} C {px(9):.1f} {py(14.5):.1f} {px(15):.1f} {py(14.5):.1f} {px(18):.1f} {py(16):.1f}",
                    **shared,
                ),
            ]
        )
    elif icon_name == "calendar":
        parts.extend(
            [
                _rect(px(5), py(6), 14 * s, 13 * s, rx=2 * s, **shared),
                _line(px(5), py(10), px(19), py(10), **shared),
                _line(px(9), py(4), px(9), py(8), **shared),
                _line(px(15), py(4), px(15), py(8), **shared),
            ]
        )
    elif icon_name == "user":
        parts.extend(
            [
                _circle(px(12), py(8), 3 * s, **shared),
                _path(
                    f"M {px(6):.1f} {py(18.5):.1f} C {px(6.7):.1f} {py(13.7):.1f} {px(9.2):.1f} {py(12):.1f} {px(12):.1f} {py(12):.1f} C {px(14.8):.1f} {py(12):.1f} {px(17.3):.1f} {py(13.7):.1f} {px(18):.1f} {py(18.5):.1f}",
                    **shared,
                ),
            ]
        )
    elif icon_name == "lightbulb":
        parts.extend(
            [
                _path(
                    f"M {px(12):.1f} {py(4.2):.1f} C {px(8.2):.1f} {py(4.2):.1f} {px(5.5):.1f} {py(7):.1f} {px(5.5):.1f} {py(10.4):.1f} C {px(5.5):.1f} {py(12.9):.1f} {px(6.8):.1f} {py(14.7):.1f} {px(8.5):.1f} {py(16.1):.1f} L {px(8.5):.1f} {py(18):.1f} H {px(15.5):.1f} L {px(15.5):.1f} {py(16.1):.1f} C {px(17.2):.1f} {py(14.7):.1f} {px(18.5):.1f} {py(12.9):.1f} {px(18.5):.1f} {py(10.4):.1f} C {px(18.5):.1f} {py(7):.1f} {px(15.8):.1f} {py(4.2):.1f} {px(12):.1f} {py(4.2):.1f} Z",
                    **shared,
                ),
                _line(px(9.5), py(21), px(14.5), py(21), **shared),
            ]
        )
    elif icon_name == "target":
        parts.extend(
            [
                _circle(px(12), py(12), 8 * s, **shared),
                _circle(px(12), py(12), 5 * s, **shared),
                _circle(px(12), py(12), 2 * s, **shared),
                _path(f"M {px(12):.1f} {py(12):.1f} L {px(18.5):.1f} {py(5.5):.1f}", **shared),
                _path(
                    f"M {px(18.5):.1f} {py(5.5):.1f} L {px(18):.1f} {py(9.5):.1f} L {px(14):.1f} {py(10):.1f} Z",
                    **shared,
                ),
            ]
        )
    elif icon_name == "trophy":
        parts.extend(
            [
                _path(
                    f"M {px(8):.1f} {py(5):.1f} H {px(16):.1f} V {py(9):.1f} C {px(16):.1f} {py(12.5):.1f} {px(14):.1f} {py(15):.1f} {px(12):.1f} {py(15):.1f} C {px(10):.1f} {py(15):.1f} {px(8):.1f} {py(12.5):.1f} {px(8):.1f} {py(9):.1f} Z",
                    **shared,
                ),
                _path(
                    f"M {px(8):.1f} {py(7):.1f} H {px(5.5):.1f} C {px(5.5):.1f} {py(10.5):.1f} {px(7):.1f} {py(12.5):.1f} {px(9.4):.1f} {py(12.5):.1f}",
                    **shared,
                ),
                _path(
                    f"M {px(16):.1f} {py(7):.1f} H {px(18.5):.1f} C {px(18.5):.1f} {py(10.5):.1f} {px(17):.1f} {py(12.5):.1f} {px(14.6):.1f} {py(12.5):.1f}",
                    **shared,
                ),
                _line(px(12), py(15), px(12), py(18.5), **shared),
                _line(px(9), py(20.5), px(15), py(20.5), **shared),
            ]
        )

    return "".join(parts)


def _render_icon(
    *,
    icon: str | None,
    icon_name: str | None,
    title: str = "",
    body: str = "",
    cx: float,
    cy: float,
    size: float,
    color: str,
    font_family: str,
) -> str:
    resolved_name = _normalize_icon_name(icon_name) or _normalize_icon_name(icon)
    if resolved_name:
        named_icon = _render_named_icon(resolved_name, cx, cy, size, color)
        if named_icon:
            return named_icon

    if icon and not icon.isascii():
        return _text(
            cx,
            cy + size * 0.18,
            icon,
            fill=color,
            font_size=str(int(size * 0.74)),
            text_anchor="middle",
            font_family=font_family,
        )

    inferred_name = _infer_icon_name(icon, title, body)
    if inferred_name:
        return _render_named_icon(inferred_name, cx, cy, size, color)

    return ""


# ---------------------------------------------------------------------------
# Donut arc math
# ---------------------------------------------------------------------------


def _donut_segment(
    cx: float,
    cy: float,
    r_out: float,
    r_in: float,
    start_deg: float,
    end_deg: float,
) -> str:
    s = math.radians(start_deg - 90)
    e = math.radians(end_deg - 90)
    ox1, oy1 = cx + r_out * math.cos(s), cy + r_out * math.sin(s)
    ox2, oy2 = cx + r_out * math.cos(e), cy + r_out * math.sin(e)
    ix1, iy1 = cx + r_in * math.cos(e), cy + r_in * math.sin(e)
    ix2, iy2 = cx + r_in * math.cos(s), cy + r_in * math.sin(s)
    large = 1 if (end_deg - start_deg) > 180 else 0
    return (
        f"M {ox1:.2f} {oy1:.2f} "
        f"A {r_out} {r_out} 0 {large} 1 {ox2:.2f} {oy2:.2f} "
        f"L {ix1:.2f} {iy1:.2f} "
        f"A {r_in} {r_in} 0 {large} 0 {ix2:.2f} {iy2:.2f} Z"
    )


def _arc_path(cx: float, cy: float, r: float, start_deg: float, end_deg: float) -> str:
    s = math.radians(start_deg - 90)
    e = math.radians(end_deg - 90)
    x1, y1 = cx + r * math.cos(s), cy + r * math.sin(s)
    x2, y2 = cx + r * math.cos(e), cy + r * math.sin(e)
    large = 1 if abs(end_deg - start_deg) > 180 else 0
    sweep = 1 if end_deg >= start_deg else 0
    return f"M {x1:.2f} {y1:.2f} A {r:.2f} {r:.2f} 0 {large} {sweep} {x2:.2f} {y2:.2f}"


# ---------------------------------------------------------------------------
# Global SVG defs (gradients, filters, patterns) — generated once per render
# ---------------------------------------------------------------------------


def _build_defs(t: dict, width: int) -> str:
    palette = t["palette"]
    is_light = _is_light_theme(t)
    shadow_color = t.get("shadow_color", "#000000")
    parts: list[str] = ["<defs>"]

    # Header gradient
    parts.append(
        f'<linearGradient id="g_hdr" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="{t["header_from"]}"/>'
        f'<stop offset="100%" stop-color="{t["header_to"]}"/>'
        f"</linearGradient>"
    )

    # Dot pattern — subtle texture for header
    parts.append(
        '<pattern id="g_dots" x="0" y="0" width="22" height="22" patternUnits="userSpaceOnUse">'
        '<circle cx="1.5" cy="1.5" r="1" fill="rgba(255,255,255,0.035)"/>'
        "</pattern>"
    )

    # Card shadow filter — light themes are completely flat (no shadows)
    parts.append(
        '<filter id="g_shadow" x="-10%" y="-12%" width="124%" height="136%">'
        f'<feDropShadow dx="0" dy="{0 if is_light else 3}" stdDeviation="{0 if is_light else 7}" '
        f'flood-color="{shadow_color}" flood-opacity="{0 if is_light else 0.42}"/>'
        "</filter>"
    )
    parts.append(
        '<filter id="g_shadow_soft" x="-12%" y="-16%" width="128%" height="144%">'
        f'<feDropShadow dx="0" dy="{0 if is_light else 4}" stdDeviation="{0 if is_light else 10}" '
        f'flood-color="{shadow_color}" flood-opacity="{0 if is_light else 0.32}"/>'
        "</filter>"
    )
    parts.append(
        '<filter id="g_blur_blob" x="-20%" y="-20%" width="140%" height="140%">'
        '<feGaussianBlur stdDeviation="42"/>'
        "</filter>"
    )
    parts.append(
        f'<radialGradient id="g_center_card" cx="50%" cy="38%" r="70%">'
        f'<stop offset="0%" stop-color="{_lighten(t["card_bg"], 0.02)}"/>'
        f'<stop offset="100%" stop-color="{_mix(t["card_bg"], t["paper_tint"], 0.35 if is_light else 0.08)}"/>'
        f"</radialGradient>"
    )
    parts.append(
        f'<linearGradient id="g_orbit_ring" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{_alpha(t["palette"][0], 0.34 if is_light else 0.24)}"/>'
        f'<stop offset="100%" stop-color="{_alpha(t["stroke_soft"], 0.8 if is_light else 0.6)}"/>'
        f"</linearGradient>"
    )

    # Bar gradient per palette slot (left = full colour, right = lightened)
    for i, color in enumerate(palette[:8]):
        light = _lighten(color, 0.34 if is_light else 0.28)
        parts.append(
            f'<linearGradient id="g_bar_{i}" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0%" stop-color="{color}"/>'
            f'<stop offset="100%" stop-color="{light}"/>'
            f"</linearGradient>"
        )

    # Heatmap cell gradient (vertical, adds depth)
    parts.append(
        f'<linearGradient id="g_cell" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{palette[0]}"/>'
        f'<stop offset="100%" stop-color="{_lighten(palette[0], 0.2)}"/>'
        f"</linearGradient>"
    )

    parts.append("</defs>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Component renderers — each returns (svg_fragment: str, height: float)
# ---------------------------------------------------------------------------


def _render_canvas_backdrop(width: int, height: int, t: dict) -> str:
    if not _is_light_theme(t):
        return ""

    palette = t["palette"]
    return "\n".join(
        [
            _rect(0, 0, width, height, fill=t.get("paper_tint", t["bg"])),
            _group(
                "".join(
                    [
                        _circle(width * 0.18, 180, 110, fill=_alpha(palette[0], 0.08)),
                        _circle(width * 0.78, 260, 150, fill=_alpha(palette[1], 0.06)),
                        _circle(width * 0.58, height * 0.72, 180, fill=_alpha(palette[4], 0.06)),
                    ]
                ),
                filter="url(#g_blur_blob)",
            ),
            _rect(0, 0, width, height, fill="rgba(255,255,255,0.48)"),
        ]
    )


def _render_header(spec: dict, width: int, t: dict) -> tuple[str, float]:
    title = spec.get("title", "Report")
    sub = spec.get("subtitle", "")
    date = spec.get("date", "")
    color0 = t["palette"][0]
    is_light = _is_light_theme(t)

    if is_light:
        # Big editorial title stack with breathing room and a quiet rule.
        title_words = title.split()
        mid = max(1, len(title_words) // 2)
        line1 = " ".join(title_words[:mid])
        line2 = " ".join(title_words[mid:])
        has_two_lines = bool(line2)
        subtitle_lines = _wrap_text(sub, 34)[:3] if sub else []
        pad = float(_PAD_H) + 8

        parts: list[str] = [
            _text(
                pad,
                74,
                line1,
                fill=t["text"],
                font_size="58",
                font_weight="750",
                font_family=t.get("font_display", t["font"]),
                letter_spacing="-2.0",
            ),
        ]
        if has_two_lines:
            parts.append(
                _text(
                    pad,
                    130,
                    line2,
                    fill=t["text"],
                    font_size="58",
                    font_weight="750",
                    font_family=t.get("font_display", t["font"]),
                    letter_spacing="-2.0",
                )
            )

        sub_y = 168 if has_two_lines else 112
        if subtitle_lines:
            for i, line in enumerate(subtitle_lines[:3]):
                parts.append(
                    _text(
                        pad,
                        sub_y + i * 20,
                        line,
                        fill=t["muted"],
                        font_size="16",
                        font_weight="400",
                        font_family=t.get("font_ui", t["font"]),
                    )
                )
            rule_y = sub_y + len(subtitle_lines) * 20 + 14
        else:
            rule_y = 164 if has_two_lines else 122

        h = max(188.0 if has_two_lines else 144.0, rule_y + 18)

        if date:
            badge_w = len(date) * 7.2 + 24
            bx = width - _PAD_H - badge_w
            parts.append(
                _group(
                    "".join(
                        [
                            _rect(bx, 28, badge_w, 28, rx=14, fill=_alpha(color0, 0.09)),
                            _rect(
                                bx,
                                28,
                                badge_w,
                                28,
                                rx=14,
                                fill="none",
                                stroke=_alpha(color0, 0.24),
                                stroke_width="1",
                            ),
                            _text(
                                bx + badge_w / 2,
                                46,
                                date,
                                fill=color0,
                                font_size="11",
                                font_weight="600",
                                font_family=t.get("font_ui", t["font"]),
                                text_anchor="middle",
                                letter_spacing="0.3",
                            ),
                        ]
                    ),
                    filter="url(#g_shadow)",
                )
            )

        parts += [
            _line(pad, rule_y, pad + 40, rule_y, stroke=color0, stroke_width="2"),
            _line(pad + 48, rule_y, width - _PAD_H, rule_y, stroke=t["card_border"], stroke_width="1"),
        ]

        return "\n".join(parts), h

    # ── Original dark header ──────────────────────────────────────────────────
    h = 148.0
    parts: list[str] = [
        _rect(0, 0, width, h, rx=0, fill="url(#g_hdr)"),
        _rect(0, 0, width, h, rx=0, fill="url(#g_dots)"),
        f'<rect x="0" y="0" width="5" height="{h:.0f}" fill="{color0}"/>',
        f'<circle cx="{width - 40:.0f}" cy="30" r="80" fill="{color0}" opacity="0.04"/>',
        f'<circle cx="{width - 40:.0f}" cy="30" r="55" fill="{color0}" opacity="0.04"/>',
        _text(
            _PAD_H + 20,
            65,
            title,
            fill=t["text"],
            font_size="32",
            font_weight="800",
            font_family=t.get("font_display", t["font"]),
            letter_spacing="-0.5",
        ),
    ]

    if sub:
        parts.append(
            _text(
                _PAD_H + 20,
                91,
                sub,
                fill=t["muted"],
                font_size="14",
                font_weight="400",
                font_family=t.get("font_ui", t["font"]),
            )
        )

    if date:
        badge_w = len(date) * 7.8 + 24
        bx = width - _PAD_H - badge_w
        parts += [
            _rect(bx, 22, badge_w, 26, rx=13, fill=color0, opacity="0.18"),
            _rect(bx, 22, badge_w, 26, rx=13, fill="none", stroke=color0, stroke_width="1", opacity="0.4"),
            _text(
                bx + badge_w / 2,
                39,
                date,
                fill=color0,
                font_size="11",
                font_weight="700",
                font_family=t.get("font_ui", t["font"]),
                text_anchor="middle",
                letter_spacing="0.4",
            ),
        ]

    parts.append(_line(0, h - 1, width, h - 1, stroke=color0, stroke_width="1", opacity="0.25"))
    return "\n".join(parts), h


def _section_title(label: str, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    h = 42.0
    color0 = t["palette"][0]
    muted = t["muted"] if not _is_light_theme(t) else _mix(t["muted"], t["text"], 0.18)
    parts = [
        # Left accent pip
        _rect(x, y + 5, 3, 22, rx=1.5, fill=color0),
        _text(
            x + 14,
            y + 22,
            label.upper(),
            fill=muted,
            font_size="11",
            font_weight="700",
            letter_spacing="2",
            font_family=t.get("font_ui", t["font"]),
        ),
        _line(x, y + h - 2, x + width, y + h - 2, stroke=t["card_border"], stroke_width="1"),
    ]
    return "\n".join(parts), h


def _render_kpi_row(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    items = section.get("items", [])
    n = max(len(items), 1)
    card_w = (width - _GAP * (n - 1)) / n
    card_h = 116.0
    r = t.get("radius", 14)
    is_light = _is_light_theme(t)
    parts: list[str] = []

    for i, item in enumerate(items):
        cx = x + i * (card_w + _GAP)
        label = item.get("label", "")
        value = str(item.get("value", "—"))
        change = item.get("change", "")
        trend = item.get("trend", "")
        color = t["palette"][i % len(t["palette"])]

        # Base card — no shadow for light themes (flat editorial look)
        card_filter = None if is_light else "url(#g_shadow)"
        parts += [
            _rect(cx, y, card_w, card_h, rx=r, fill=t["card_bg"], filter=card_filter),
            # Subtle colour wash — top half only, fades
            _rect(cx, y, card_w, card_h * 0.55, rx=r, fill=color, opacity="0.07"),
            # Mask bottom of wash with a card-coloured rect
            _rect(cx, y + card_h * 0.4, card_w, card_h * 0.2, fill=t["card_bg"], opacity="0.85"),
            # Card border in accent colour
            _rect(cx, y, card_w, card_h, rx=r, fill="none", stroke=color, stroke_width="1", opacity="0.35"),
            # Top accent bar
            _rect(cx + r, y, card_w - r * 2, 3, rx=1.5, fill=color),
        ]

        # Big value — in accent colour, bold
        parts.append(
            _text(cx + 20, y + 62, value, fill=color, font_size="38", font_weight="800", font_family=t["font"])
        )
        # Label
        parts.append(
            _text(
                cx + 20,
                y + 84,
                label,
                fill=t["muted"],
                font_size="11",
                font_weight="500",
                font_family=t["font"],
                letter_spacing="0.3",
            )
        )

        # Change badge — pill in top-right corner
        if change:
            trend_color = t["trend_up"] if trend == "up" else t["trend_down"] if trend == "down" else t["muted"]
            arrow = "▲ " if trend == "up" else "▼ " if trend == "down" else ""
            badge_label = f"{arrow}{change}"
            bw = len(badge_label) * 7 + 18
            bx = cx + card_w - bw - 14
            by = y + 14
            parts += [
                _rect(bx, by, bw, 20, rx=10, fill=trend_color, opacity="0.15"),
                _text(
                    bx + bw / 2,
                    by + 13,
                    badge_label,
                    fill=trend_color,
                    font_size="10",
                    font_weight="700",
                    font_family=t["font"],
                    text_anchor="middle",
                ),
            ]

    return "\n".join(parts), card_h


def _render_bar_chart(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    title = section.get("title", "")
    data = section.get("data", [])
    parts: list[str] = []
    cur_y = y

    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    if not data:
        return "", 0.0

    max_val = max((d.get("value", 0) for d in data), default=1) or 1
    label_w = 155.0
    val_w = 52.0
    bar_area = width - label_w - val_w
    bh = float(t.get("bar_h", 28))
    row_h = bh + 18.0
    r = bh / 2

    for i, item in enumerate(data):
        label = item.get("label", "")
        value = item.get("value", 0)
        pct = value / max_val
        fill_w = max(pct * bar_area, 4.0)
        ry = cur_y + i * row_h
        slot = i % len(t["palette"])

        parts += [
            # Row label
            _text(x, ry + bh - 7, label, fill=t["text"], font_size="13", font_weight="500", font_family=t["font"]),
            # Track
            _rect(x + label_w, ry, bar_area, bh, rx=r, fill=t["card_border"]),
            # Filled bar — gradient
            _rect(x + label_w, ry, fill_w, bh, rx=r, fill=f"url(#g_bar_{slot})"),
        ]

        # Percentage label inside bar if wide enough, otherwise after
        pct_str = f"{round(pct * 100)}%"
        if fill_w > 44:
            parts.append(
                _text(
                    x + label_w + fill_w - 12,
                    ry + bh - 8,
                    pct_str,
                    fill="rgba(255,255,255,0.75)",
                    font_size="10",
                    font_weight="700",
                    font_family=t["font"],
                    text_anchor="end",
                )
            )
        else:
            parts.append(
                _text(
                    x + label_w + fill_w + 8,
                    ry + bh - 8,
                    pct_str,
                    fill=t["muted"],
                    font_size="10",
                    font_family=t["font"],
                )
            )

        # Raw value
        parts.append(
            _text(
                x + label_w + bar_area + 10,
                ry + bh - 7,
                str(value),
                fill=t["text"],
                font_size="12",
                font_weight="600",
                font_family=t["font"],
            )
        )

    return "\n".join(parts), (cur_y - y) + len(data) * row_h


def _render_donut(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    title = section.get("title", "")
    data = section.get("data", [])
    parts: list[str] = []
    cur_y = y

    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    if not data:
        return "", 0.0

    total = sum(d.get("value", 0) for d in data) or 1
    r_out = 75.0
    r_in = 50.0  # thinner ring = more modern
    chart_d = r_out * 2 + 20
    dcx = x + r_out + 10
    dcy = cur_y + r_out + 10

    # Background track circle
    parts.append(_circle(dcx, dcy, r_out, fill="none", stroke=t["card_border"], stroke_width="1"))

    # Segments
    angle = 0.0
    for i, item in enumerate(data):
        val = item.get("value", 0)
        color = item.get("color") or t["palette"][i % len(t["palette"])]
        sweep = (val / total) * 360
        if sweep < 1:
            angle += sweep
            continue
        d = _donut_segment(dcx, dcy, r_out, r_in, angle, angle + sweep)
        parts.append(_path(d, fill=color))
        angle += sweep

    # Centre — total value in accent colour
    parts += [
        _text(
            dcx,
            dcy - 8,
            str(total),
            fill=t["palette"][0],
            font_size="24",
            font_weight="800",
            font_family=t["font"],
            text_anchor="middle",
        ),
        _text(
            dcx,
            dcy + 13,
            "TOTAL",
            fill=t["muted"],
            font_size="9",
            font_weight="700",
            font_family=t["font"],
            text_anchor="middle",
            letter_spacing="1.5",
        ),
    ]

    # Legend — right of donut, vertically centred
    lx = x + chart_d + 28
    lrh = 38.0
    n = len(data)
    loff = max(0.0, (chart_d - n * lrh) / 2)
    ly = cur_y + 10 + loff

    for i, item in enumerate(data):
        label = item.get("label", "")
        val = item.get("value", 0)
        color = item.get("color") or t["palette"][i % len(t["palette"])]
        pct = round(val / total * 100)
        iy = ly + i * lrh

        # Colour indicator
        parts.append(_rect(lx, iy + 3, 14, 14, rx=3, fill=color))
        parts.append(
            _text(lx + 22, iy + 13, label, fill=t["text"], font_size="13", font_weight="500", font_family=t["font"])
        )
        parts.append(
            _text(lx + 22, iy + 27, f"{val:,}  ·  {pct}%", fill=t["muted"], font_size="11", font_family=t["font"])
        )

    total_h = (cur_y - y) + max(chart_d, n * lrh) + 20
    return "\n".join(parts), total_h


def _render_stories(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    title = section.get("title", "")
    items = section.get("items", [])
    parts: list[str] = []
    cur_y = y
    r = t.get("radius", 14)

    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 8

    body_chars = int((width - 64) / 7.0)

    for i, story in enumerate(items):
        headline = story.get("headline", "")
        body = story.get("body", "")
        channel = story.get("channel", "")
        author = story.get("author", "")
        color = t["palette"][i % len(t["palette"])]
        body_lines = _wrap_text(body, body_chars)
        card_h = 46.0 + len(body_lines) * 20 + 30

        parts += [
            # Card shadow + bg
            _rect(x, cur_y, width, card_h, rx=r, fill=t["card_bg"], filter="url(#g_shadow)"),
            # Colour tint on left
            _rect(x, cur_y, width * 0.35, card_h, rx=r, fill=color, opacity="0.04"),
            # Mask right edge of tint bleed
            _rect(x + width * 0.35 - 8, cur_y, 12, card_h, fill=t["card_bg"]),
            # Card border
            _rect(x, cur_y, width, card_h, rx=r, fill="none", stroke=t["card_border"], stroke_width="1"),
            # Left accent stripe
            _rect(x, cur_y, 4, card_h, rx=2, fill=color),
            # Number bubble
            _circle(x + 28, cur_y + 26, 13, fill=color, opacity="0.18"),
            _text(
                x + 28,
                cur_y + 31,
                str(i + 1),
                fill=color,
                font_size="12",
                font_weight="800",
                font_family=t["font"],
                text_anchor="middle",
            ),
            # Headline — in accent colour for boldness
            _text(x + 52, cur_y + 30, headline, fill=color, font_size="14", font_weight="700", font_family=t["font"]),
        ]

        # Body lines
        for li, line in enumerate(body_lines):
            parts.append(
                _text(x + 52, cur_y + 50 + li * 20, line, fill=t["muted"], font_size="12", font_family=t["font"])
            )

        # Meta (channel · author)
        meta_parts = []
        if channel:
            meta_parts.append(channel)
        if author:
            meta_parts.append(f"by {author}")
        if meta_parts:
            meta_y = cur_y + card_h - 11
            meta_str = "  ·  ".join(meta_parts)
            # pill background
            pw = len(meta_str) * 6.8 + 16
            parts += [
                _rect(x + 50, meta_y - 12, pw, 16, rx=8, fill=color, opacity="0.12"),
                _text(
                    x + 58,
                    meta_y,
                    meta_str,
                    fill=color,
                    font_size="10",
                    font_weight="600",
                    font_family=t["font"],
                    opacity="0.85",
                ),
            ]

        cur_y += card_h + 12

    return "\n".join(parts), cur_y - y


def _render_heatmap(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    title = section.get("title", "")
    data = section.get("data", [])
    row_labels = section.get("row_labels", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    parts: list[str] = []
    cur_y = y

    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 14

    if not data:
        return "", 0.0

    label_w = 36.0
    cell_gap = 3
    cell_sz = max(10, int((width - label_w - cell_gap * 23) / 24))
    row_h = cell_sz + cell_gap

    flat = [v for row in data for v in row]
    max_val = max(flat) if flat else 1
    if max_val == 0:
        max_val = 1

    # Hour axis
    for hr in [0, 3, 6, 9, 12, 15, 18, 21, 23]:
        hx = x + label_w + hr * (cell_sz + cell_gap) + cell_sz / 2
        parts.append(
            _text(hx, cur_y - 5, str(hr), fill=t["muted"], font_size="9", font_family=t["font"], text_anchor="middle")
        )

    for ri, row in enumerate(data[:7]):
        ry = cur_y + ri * row_h
        day = row_labels[ri] if ri < len(row_labels) else ""

        parts.append(_text(x, ry + cell_sz - 2, day, fill=t["muted"], font_size="9", font_family=t["font"]))

        for ci, val in enumerate(row[:24]):
            opacity = max(0.06, val / max_val)
            cx2 = x + label_w + ci * (cell_sz + cell_gap)
            # Background cell
            parts.append(_rect(cx2, ry, cell_sz, cell_sz, rx=2, fill=t["card_border"]))
            # Active cell using gradient
            parts.append(_rect(cx2, ry, cell_sz, cell_sz, rx=2, fill="url(#g_cell)", opacity=f"{opacity:.2f}"))

    total_h = (cur_y - y) + 7 * row_h + 10
    return "\n".join(parts), total_h


def _render_divider(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    label = section.get("label", "")
    h = 36.0
    mid = y + h / 2

    if label:
        half_lw = len(label) * 3.8 + 14
        cx = x + width / 2
        color0 = t["palette"][0]
        parts = [
            _line(x, mid, cx - half_lw - 10, mid, stroke=t["card_border"], stroke_width="1"),
            _rect(cx - half_lw - 2, mid - 10, (half_lw + 2) * 2, 20, rx=10, fill=t["card_bg"]),
            _text(
                cx,
                mid + 4,
                label,
                fill=color0,
                font_size="11",
                font_weight="600",
                font_family=t["font"],
                text_anchor="middle",
                letter_spacing="0.5",
            ),
            _line(cx + half_lw + 10, mid, x + width, mid, stroke=t["card_border"], stroke_width="1"),
        ]
    else:
        parts = [
            _line(x, mid, x + width, mid, stroke=t["card_border"], stroke_width="1", opacity="0.6"),
        ]

    return "\n".join(parts), h


def _render_text_block(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    content = section.get("content", "")
    chars = int(width / 7.4)
    lines = _wrap_text(content, chars)
    lh = 22.0
    r = t.get("radius", 14)
    card_h = len(lines) * lh + 32

    parts = [
        _rect(x, y, width, card_h, rx=r, fill=t["card_bg"], stroke=t["card_border"], stroke_width="1"),
        _rect(x, y, 4, card_h, rx=2, fill=t["palette"][0]),
    ]
    for i, line in enumerate(lines):
        parts.append(_text(x + 18, y + 20 + i * lh, line, fill=t["muted"], font_size="13", font_family=t["font"]))
    return "\n".join(parts), card_h + 4


# ---------------------------------------------------------------------------
# AntV-parity section renderers
# ---------------------------------------------------------------------------


def _render_process_flow(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Numbered step cards connected by arrows (horizontal, wraps to next row)."""
    items = section.get("items", [])
    title = section.get("title", "")
    n = len(items)
    if not n:
        return "", 0.0

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    max_per_row = min(n, 4)
    arrow_w = 26.0
    gap = 10.0
    card_w = (width - (max_per_row - 1) * (arrow_w + gap)) / max_per_row
    card_h = 124.0
    r = t.get("radius", 10)
    start_y = cur_y

    for i, item in enumerate(items):
        col = i % max_per_row
        row = i // max_per_row
        cx2 = x + col * (card_w + arrow_w + gap)
        cy2 = start_y + row * (card_h + 40)
        color = t["palette"][i % len(t["palette"])]

        # Card
        parts += [
            _rect(cx2, cy2, card_w, card_h, rx=r, fill=t["card_bg"], filter="url(#g_shadow)"),
            _rect(cx2, cy2, card_w, card_h, rx=r, fill="none", stroke=t["card_border"], stroke_width="1"),
            _rect(cx2 + r, cy2, card_w - r * 2, 3, rx=1.5, fill=color),
        ]
        # Number circle
        parts += [
            _circle(cx2 + card_w / 2, cy2 + 32, 18, fill=color, opacity="0.18"),
            _circle(cx2 + card_w / 2, cy2 + 32, 18, fill="none", stroke=color, stroke_width="1.5"),
            _text(
                cx2 + card_w / 2,
                cy2 + 37,
                str(i + 1),
                fill=color,
                font_size="14",
                font_weight="800",
                font_family=t["font"],
                text_anchor="middle",
            ),
        ]
        # Title + body
        title_txt = item.get("title", "")
        body_txt = item.get("body", "")
        parts.append(
            _text(
                cx2 + card_w / 2,
                cy2 + 64,
                title_txt,
                fill=t["text"],
                font_size="12",
                font_weight="700",
                font_family=t["font"],
                text_anchor="middle",
            )
        )
        for li, line in enumerate(_wrap_text(body_txt, int(card_w / 6.6))[:2]):
            parts.append(
                _text(
                    cx2 + card_w / 2,
                    cy2 + 82 + li * 18,
                    line,
                    fill=t["muted"],
                    font_size="10",
                    font_family=t["font"],
                    text_anchor="middle",
                )
            )

        # Arrow to next item on same row
        if col < max_per_row - 1 and i < n - 1:
            ax = cx2 + card_w + gap
            ay = cy2 + card_h / 2
            aend = ax + arrow_w - 2
            parts += [
                _line(ax, ay, aend, ay, stroke=t["muted"], stroke_width="1.5", opacity="0.45"),
                _path(
                    f"M {aend:.0f} {ay:.0f} L {aend - 8:.0f} {ay - 5:.0f} L {aend - 8:.0f} {ay + 5:.0f} Z",
                    fill=t["muted"],
                    opacity="0.45",
                ),
            ]

    rows = (n - 1) // max_per_row + 1
    total_h = rows * card_h + (rows - 1) * 40 + (cur_y - y) + 8
    return "\n".join(parts), total_h


def _render_circular_flow(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """
    Editorial orbital infographic layout:
    - Large center card with icon + label
    - Soft pastel bubbles around a thin orbit ring
    - Title + description text blocks outside each bubble
    - Optional side note, footer journey panel, and quote line for poster-like layouts
    """
    items = section.get("items", [])
    title_str = section.get("title", "")
    center_label = section.get("center_label", "")
    center_icon = section.get("center_icon", "")
    center_icon_name = section.get("center_icon_name", "")
    side_note = section.get("side_note") or {}
    footer_panel = section.get("footer_panel") or {}
    quote_text = section.get("quote", "")
    quote_icon = section.get("quote_icon", "")
    quote_icon_name = section.get("quote_icon_name", "")
    n = len(items)
    if n < 2:
        return "", 0.0

    parts: list[str] = []
    cur_y = y
    is_light = _is_light_theme(t)

    if title_str:
        s, dh = _section_title(title_str, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + (14 if is_light else 10)

    orbit_size = min(float(width) * (0.82 if is_light else 0.72), 560.0 if is_light else 480.0)
    r_orbit = orbit_size * (0.42 if is_light else 0.44)
    bubble_r = orbit_size * (0.098 if is_light else 0.115)
    center_r = orbit_size * (0.245 if is_light else 0.22)
    cx_c = x + width * (0.57 if is_light and side_note else 0.5)
    cy_c = cur_y + orbit_size / 2 + (10 if is_light else 0)

    text_color = t["text"]
    muted_color = t["muted"]

    if is_light:
        parts.append(_circle(cx_c, cy_c, r_orbit + 18, fill=_alpha(t["palette"][0], 0.03), filter="url(#g_blur_blob)"))

    parts.append(
        _circle(
            cx_c,
            cy_c,
            r_orbit,
            fill="none",
            stroke="url(#g_orbit_ring)" if is_light else _alpha(t["palette"][0], 0.25),
            stroke_width="1.4" if is_light else "1.2",
        )
    )

    positions: list[tuple[float, float, float, float]] = []
    for i in range(n):
        angle = math.radians(-88 + 360 * i / n)
        ax = math.cos(angle)
        ay = math.sin(angle)
        positions.append((cx_c + r_orbit * ax, cy_c + r_orbit * ay, ax, ay))

    if is_light and side_note:
        note_x = x
        note_y = cur_y + orbit_size * 0.18
        note_color = side_note.get("color") or t["palette"][0]
        note_title = side_note.get("title", "")
        note_body = side_note.get("body", "")
        parts.extend(
            [
                _group(
                    "".join(
                        [
                            _circle(note_x + 18, note_y + 18, 14, fill=_alpha(note_color, 0.10)),
                            _render_icon(
                                icon=side_note.get("icon", ""),
                                icon_name=side_note.get("icon_name", ""),
                                title=note_title,
                                body=note_body,
                                cx=note_x + 18,
                                cy=note_y + 18,
                                size=18,
                                color=note_color,
                                font_family=t.get("font_ui", t["font"]),
                            ),
                        ]
                    ),
                    filter="url(#g_shadow)",
                ),
                _text(
                    note_x + 48,
                    note_y + 20,
                    note_title,
                    fill=text_color,
                    font_size="14",
                    font_weight="700",
                    font_family=t.get("font_display", t["font"]),
                ),
            ]
        )
        note_lines = _wrap_text(note_body, 28)
        for i, line in enumerate(note_lines[:3]):
            parts.append(
                _text(
                    note_x + 48,
                    note_y + 44 + i * 18,
                    line,
                    fill=muted_color,
                    font_size="12",
                    font_family=t.get("font_ui", t["font"]),
                )
            )
        parts.append(
            _line(
                note_x,
                note_y - 20,
                note_x + min(180, width * 0.22),
                note_y - 20,
                stroke=t["card_border"],
                stroke_width="1",
            )
        )

    for i, (nx, ny, ax, ay) in enumerate(positions):
        color = items[i].get("color") or t["palette"][i % len(t["palette"])]
        parts.append(
            _circle(nx, ny, 5.5 if is_light else 5, fill=color, stroke=t["bg"], stroke_width="3" if is_light else "0")
        )

        bubble_fill = _mix(t["card_bg"], color, 0.12) if is_light else _alpha(color, 0.18)
        bubble_stroke = _alpha(color, 0.24) if is_light else color
        parts.append(
            _group(
                "".join(
                    [
                        _circle(nx, ny, bubble_r, fill=bubble_fill, opacity="0.98" if is_light else "1"),
                        _circle(
                            nx,
                            ny,
                            bubble_r,
                            fill="none",
                            stroke=bubble_stroke,
                            stroke_width="1.2",
                            opacity="0.95" if is_light else "0.55",
                        ),
                    ]
                ),
                filter="url(#g_shadow)" if is_light else None,
            )
        )

        icon_svg = _render_icon(
            icon=items[i].get("icon", ""),
            icon_name=items[i].get("icon_name", ""),
            title=items[i].get("title", items[i].get("label", "")),
            body=items[i].get("body", ""),
            cx=nx,
            cy=ny,
            size=bubble_r * 0.94,
            color=color,
            font_family=t.get("font_ui", t["font"]),
        )
        if icon_svg:
            parts.append(icon_svg)

        push = bubble_r + (30 if is_light else 14)
        if ax > 0.25:
            anchor = "start"
            tx = nx + push
        elif ax < -0.25:
            anchor = "end"
            tx = nx - push
        else:
            anchor = "middle"
            tx = nx

        item_title = items[i].get("title", items[i].get("label", ""))
        item_body = items[i].get("body", "")
        num_str = f"0{i + 1}" if i < 9 else str(i + 1)
        num_y = ny - push * 0.46 if ay < -0.1 else ny + push * 0.46 + 8
        parts.append(
            _text(
                tx,
                num_y,
                num_str,
                fill=color,
                font_size="12" if is_light else "11",
                font_weight="700",
                font_family=t.get("font_ui", t["font"]),
                text_anchor=anchor,
                letter_spacing="0.6",
            )
        )

        title_y = num_y + 20
        parts.append(
            _text(
                tx,
                title_y,
                item_title,
                fill=text_color,
                font_size="14" if is_light else "13",
                font_weight="700",
                font_family=t.get("font_display", t["font"]),
                text_anchor=anchor,
            )
        )

        body_chars = 25 if abs(ax) > 0.28 else 18
        for li, line in enumerate(_wrap_text(item_body, body_chars)[:3]):
            parts.append(
                _text(
                    tx,
                    title_y + 18 + li * 16,
                    line,
                    fill=muted_color,
                    font_size="11.5" if is_light else "11",
                    font_family=t.get("font_ui", t["font"]),
                    text_anchor=anchor,
                )
            )

    c0 = t["palette"][0]
    center_parts = [
        _circle(cx_c, cy_c, center_r, fill="url(#g_center_card)" if is_light else _alpha(c0, 0.18)),
        _circle(
            cx_c,
            cy_c,
            center_r,
            fill="none",
            stroke=_alpha(c0, 0.18) if is_light else c0,
            stroke_width="1.2",
            opacity="0.9" if is_light else "0.35",
        ),
    ]
    parts.append(_group("".join(center_parts), filter="url(#g_shadow_soft)" if is_light else "url(#g_shadow)"))

    center_icon_svg = _render_icon(
        icon=center_icon,
        icon_name=center_icon_name,
        title=center_label,
        body="",
        cx=cx_c,
        cy=cy_c - (22 if center_label else 0),
        size=center_r * 0.62,
        color=c0,
        font_family=t.get("font_ui", t["font"]),
    )
    if center_icon_svg:
        parts.append(center_icon_svg)

    if center_label:
        c_lines = _wrap_text(center_label, 18)
        c_start_y = cy_c + (28 if center_icon_svg else -6 * (len(c_lines) - 1))
        for li, line in enumerate(c_lines[:3]):
            parts.append(
                _text(
                    cx_c,
                    c_start_y + 17 * li,
                    line,
                    fill=text_color,
                    font_size="13.5" if is_light else "12",
                    font_weight="600",
                    font_family=t.get("font_display", t["font"]),
                    text_anchor="middle",
                )
            )

    footer_h = 0.0
    footer_y = cur_y + orbit_size + (54 if is_light else 28)
    footer_title = footer_panel.get("title", "")
    footer_body = footer_panel.get("body", "")
    footer_steps = footer_panel.get("steps", []) or []

    if footer_title or footer_body or footer_steps:
        footer_h = 136.0 if is_light else 124.0
        radius = max(t.get("radius", 16), 18 if is_light else 14)
        left_w = width * (0.48 if footer_steps else 1.0)
        divider_x = x + left_w
        footer_color = footer_panel.get("color") or t["palette"][0]

        footer_box = [
            _rect(x, footer_y, width, footer_h, rx=radius, fill=t["card_bg"]),
            _rect(x, footer_y, width, footer_h, rx=radius, fill="none", stroke=t["card_border"], stroke_width="1"),
        ]
        parts.append(_group("".join(footer_box), filter="url(#g_shadow)" if is_light else "url(#g_shadow)"))

        icon_cx = x + 42
        icon_cy = footer_y + footer_h / 2
        parts.extend(
            [
                _group(
                    _circle(
                        icon_cx,
                        icon_cy,
                        28,
                        fill=_mix("#FFFFFF", footer_color, 0.24) if is_light else _alpha(footer_color, 0.18),
                    ),
                    filter="url(#g_shadow)",
                ),
                _render_icon(
                    icon=footer_panel.get("icon", ""),
                    icon_name=footer_panel.get("icon_name", ""),
                    title=footer_title,
                    body=footer_body,
                    cx=icon_cx,
                    cy=icon_cy,
                    size=26,
                    color=footer_color,
                    font_family=t.get("font_ui", t["font"]),
                ),
                _text(
                    x + 92,
                    footer_y + 44,
                    footer_title,
                    fill=text_color,
                    font_size="15.5" if is_light else "14",
                    font_weight="700",
                    font_family=t.get("font_display", t["font"]),
                ),
            ]
        )
        for i, line in enumerate(_wrap_text(footer_body, 34)[:2]):
            parts.append(
                _text(
                    x + 92,
                    footer_y + 72 + i * 18,
                    line,
                    fill=muted_color,
                    font_size="12.5" if is_light else "11.5",
                    font_family=t.get("font_ui", t["font"]),
                )
            )

        if footer_steps:
            parts.append(
                _line(
                    divider_x,
                    footer_y + 22,
                    divider_x,
                    footer_y + footer_h - 22,
                    stroke=t["card_border"],
                    stroke_width="1",
                )
            )
            step_count = len(footer_steps)
            right_x = divider_x + 30
            right_w = width - left_w - 46
            segment = right_w / max(step_count, 1)
            for i, step in enumerate(footer_steps):
                scx = right_x + segment * i + segment / 2
                scy = footer_y + 48
                s_color = step.get("color") or t["palette"][min(i, len(t["palette"]) - 1)]
                parts.extend(
                    [
                        _render_icon(
                            icon=step.get("icon", ""),
                            icon_name=step.get("icon_name", ""),
                            title=step.get("label", ""),
                            body="",
                            cx=scx,
                            cy=scy,
                            size=24,
                            color=s_color,
                            font_family=t.get("font_ui", t["font"]),
                        ),
                        _text(
                            scx,
                            footer_y + 92,
                            step.get("label", ""),
                            fill=muted_color if is_light else text_color,
                            font_size="11.5" if is_light else "11",
                            font_family=t.get("font_ui", t["font"]),
                            text_anchor="middle",
                        ),
                    ]
                )
                if i < step_count - 1:
                    arrow_start = scx + 30
                    arrow_end = right_x + segment * (i + 1) + segment / 2 - 30
                    parts.append(
                        _line(arrow_start, scy + 1, arrow_end, scy + 1, stroke=t["stroke_soft"], stroke_width="1.2")
                    )
                    parts.append(
                        _render_named_icon(
                            "arrow-right",
                            (arrow_start + arrow_end) / 2,
                            scy + 1,
                            16,
                            _mix(t["muted"], t["text"], 0.3),
                            stroke_width=1.7,
                        )
                    )

    quote_h = 0.0
    if quote_text:
        quote_y = footer_y + footer_h + 44
        quote_color = (
            quote_icon_name and t["palette"][0] or _infer_icon_name(quote_text) and t["palette"][0] or t["palette"][0]
        )
        quote_icon_svg = _render_icon(
            icon=quote_icon,
            icon_name=quote_icon_name,
            title=quote_text,
            body="",
            cx=x + width * 0.18,
            cy=quote_y - 2,
            size=18,
            color=quote_color,
            font_family=t.get("font_ui", t["font"]),
        )
        if quote_icon_svg:
            parts.append(quote_icon_svg)
            quote_text_x = x + width * 0.215
        else:
            quote_text_x = x + width * 0.18
        parts.append(
            _text(
                quote_text_x,
                quote_y + 4,
                quote_text,
                fill=text_color,
                font_size="15" if is_light else "14",
                font_weight="500",
                font_family=t.get("font_display", t["font"]),
            )
        )
        quote_h = 30.0

    total_h = orbit_size + footer_h + quote_h + (108 if footer_h else 26)
    return "\n".join(parts), total_h


def _render_staircase(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Ascending color steps — bottom-aligned, each step taller than the last."""
    items = section.get("items", [])
    title = section.get("title", "")
    n = len(items)
    if not n:
        return "", 0.0

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    max_h = 210.0
    base_y = cur_y + max_h
    gap = 4.0
    step_w = (width - (n - 1) * gap) / n
    r = 6

    for i, item in enumerate(items):
        label = item.get("label", "")
        value = item.get("value")
        color = t["palette"][i % len(t["palette"])]
        slot = i % len(t["palette"])
        step_h = max_h * (i + 1) / n
        sx = x + i * (step_w + gap)
        sy = base_y - step_h

        # Full gradient fill
        parts.append(_rect(sx, sy, step_w, step_h, rx=r, fill=f"url(#g_bar_{slot})"))
        # Cancel bottom rounding (keep top rounded only)
        parts.append(_rect(sx, sy + step_h - r, step_w, r, fill=color))

        # Step number at top
        parts.append(
            _text(
                sx + step_w / 2,
                sy + 22,
                str(i + 1),
                fill="rgba(255,255,255,0.9)",
                font_size="16",
                font_weight="800",
                font_family=t["font"],
                text_anchor="middle",
            )
        )
        if value is not None:
            parts.append(
                _text(
                    sx + step_w / 2,
                    sy + 42,
                    str(value),
                    fill="rgba(255,255,255,0.85)",
                    font_size="13",
                    font_weight="700",
                    font_family=t["font"],
                    text_anchor="middle",
                )
            )
        # Label at base of step
        chars = max(4, int(step_w / 6.5))
        wrapped = _wrap_text(label, chars)
        for li, line in enumerate(reversed(wrapped)):
            parts.append(
                _text(
                    sx + step_w / 2,
                    base_y - 8 - li * 14,
                    line,
                    fill="rgba(255,255,255,0.85)",
                    font_size="10",
                    font_weight="600",
                    font_family=t["font"],
                    text_anchor="middle",
                )
            )

    return "\n".join(parts), max_h + (cur_y - y) + 10


def _render_pyramid(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Layered trapezoid pyramid — narrow top, wide bottom."""
    items = section.get("items", [])
    title = section.get("title", "")
    n = len(items)
    if not n:
        return "", 0.0

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    layer_h = 46.0
    gap = 3.0
    pyr_w = width * 0.48
    cx_c = x + pyr_w / 2 + _PAD_H * 0.5
    label_x = x + pyr_w + 28

    for i, item in enumerate(items):
        label = item.get("label", "")
        body = item.get("body", "")
        slot = i % len(t["palette"])
        color = t["palette"][slot]

        frac_top = (i + 0.3) / n
        frac_bot = (i + 1.0) / n
        half_top = pyr_w * 0.5 * frac_top
        half_bot = pyr_w * 0.5 * min(frac_bot, 1.0)
        ty = cur_y + i * (layer_h + gap)
        by = ty + layer_h

        d = (
            f"M {cx_c - half_top:.1f} {ty:.1f} "
            f"L {cx_c + half_top:.1f} {ty:.1f} "
            f"L {cx_c + half_bot:.1f} {by:.1f} "
            f"L {cx_c - half_bot:.1f} {by:.1f} Z"
        )
        parts.append(_path(d, fill=f"url(#g_bar_{slot})"))

        # Level number centred in layer
        parts.append(
            _text(
                cx_c,
                ty + layer_h / 2 + 5,
                str(i + 1),
                fill="rgba(255,255,255,0.9)",
                font_size="14",
                font_weight="800",
                font_family=t["font"],
                text_anchor="middle",
            )
        )

        # Label right side with dashed connector
        mid_y = ty + layer_h / 2
        con_x = cx_c + half_top + 6
        parts += [
            _line(
                con_x,
                mid_y,
                label_x - 4,
                mid_y,
                stroke=t["muted"],
                stroke_width="1",
                stroke_dasharray="3 3",
                opacity="0.5",
            ),
            _text(label_x, mid_y + 4, label, fill=color, font_size="13", font_weight="700", font_family=t["font"]),
        ]
        if body:
            parts.append(_text(label_x, mid_y + 18, body, fill=t["muted"], font_size="10", font_family=t["font"]))

    total_h = n * (layer_h + gap) + (cur_y - y)
    return "\n".join(parts), total_h + 10


def _render_snake_path(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Serpentine numbered path — odd rows reverse direction."""
    items = section.get("items", [])
    title = section.get("title", "")
    n = len(items)
    if not n:
        return "", 0.0

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    cols = min(n, 4)
    node_r = 28.0
    node_gap = (width - cols * node_r * 2) / max(cols - 1, 1)
    row_h = node_r * 2 + 52.0

    def _node_pos(idx: int) -> tuple[float, float]:
        col = idx % cols
        row = idx // cols
        if row % 2 == 1:
            col = cols - 1 - col
        nx = x + col * (node_r * 2 + node_gap) + node_r
        ny = cur_y + row * row_h + node_r
        return nx, ny

    for i, item in enumerate(items):
        nx, ny = _node_pos(i)
        color = t["palette"][i % len(t["palette"])]
        label = item.get("label", "")

        parts += [
            _circle(nx, ny, node_r, fill=t["card_bg"], filter="url(#g_shadow)"),
            _circle(nx, ny, node_r, fill=color, opacity="0.18"),
            _circle(nx, ny, node_r, fill="none", stroke=color, stroke_width="2"),
            _text(
                nx,
                ny + 6,
                str(i + 1),
                fill=color,
                font_size="16",
                font_weight="800",
                font_family=t["font"],
                text_anchor="middle",
            ),
        ]
        for li, line in enumerate(_wrap_text(label, int(node_r * 2 / 5.5))):
            parts.append(
                _text(
                    nx,
                    ny + node_r + 16 + li * 13,
                    line,
                    fill=t["text"],
                    font_size="10",
                    font_weight="500",
                    font_family=t["font"],
                    text_anchor="middle",
                )
            )

        # Connector to next
        if i < n - 1:
            nnx, nny = _node_pos(i + 1)
            row_cur = i // cols
            row_nxt = (i + 1) // cols
            if row_nxt == row_cur:
                # Same row — simple horizontal
                parts.append(_line(nx + node_r, ny, nnx - node_r, nny, stroke=color, stroke_width="1.5", opacity="0.3"))
            else:
                # Wrap — arc down then across
                parts.append(
                    _line(
                        nx,
                        ny + node_r,
                        nnx,
                        nny - node_r,
                        stroke=color,
                        stroke_width="1.5",
                        opacity="0.25",
                        stroke_dasharray="4 3",
                    )
                )

    rows = (n - 1) // cols + 1
    return "\n".join(parts), rows * row_h + (cur_y - y) + 10


def _render_bubble_chain(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Horizontally connected circles sized by value."""
    items = section.get("items", [])
    title = section.get("title", "")
    n = len(items)
    if not n:
        return "", 0.0

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    max_val = max((item.get("value", 1) for item in items), default=1) or 1
    min_r = 18.0
    max_r = 52.0
    radii = [min_r + (item.get("value", 0) / max_val) * (max_r - min_r) for item in items]

    connector = 16.0
    total_w = sum(r * 2 for r in radii) + (n - 1) * connector
    scale = min(1.0, width / total_w) if total_w > width else 1.0
    radii = [r * scale for r in radii]
    conn_s = connector * scale

    max_r_val = max(radii, default=max_r)
    cy_center = cur_y + max_r_val + 20
    offset_x = x + (width - sum(r * 2 for r in radii) - (n - 1) * conn_s) / 2

    cur_x = offset_x
    for i, item in enumerate(items):
        rv = radii[i]
        label = item.get("label", "")
        value = item.get("value", "")
        color = t["palette"][i % len(t["palette"])]
        bx = cur_x + rv

        if i < n - 1:
            nrv = radii[i + 1]
            next_x = bx + rv + conn_s + nrv
            parts.append(
                _line(bx + rv, cy_center, next_x - nrv, cy_center, stroke=t["muted"], stroke_width="1", opacity="0.3")
            )

        parts += [
            _circle(bx, cy_center, rv, fill=color, opacity="0.15"),
            _circle(bx, cy_center, rv, fill="none", stroke=color, stroke_width="2"),
            _text(
                bx,
                cy_center - 4,
                str(value),
                fill=color,
                font_size=f"{max(9, int(rv * 0.42))}",
                font_weight="800",
                font_family=t["font"],
                text_anchor="middle",
            ),
            _text(
                bx,
                cy_center + max_r_val + 16,
                label,
                fill=t["text"],
                font_size="11",
                font_weight="500",
                font_family=t["font"],
                text_anchor="middle",
            ),
        ]
        cur_x += rv * 2 + conn_s

    return "\n".join(parts), max_r_val * 2 + 50 + (cur_y - y)


def _render_timeline(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Horizontal timeline with alternating above/below event labels."""
    items = section.get("items", [])
    title = section.get("title", "")
    n = len(items)
    if not n:
        return "", 0.0

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    above_h = 72.0
    below_h = 72.0
    line_y = cur_y + above_h

    # Timeline rail
    parts.append(_rect(x, line_y - 2, width, 4, rx=2, fill=t["card_border"]))

    for i, item in enumerate(items):
        label = item.get("label", "")
        date_txt = item.get("date", "")
        body = item.get("body", "")
        color = t["palette"][i % len(t["palette"])]
        px = x + (i + 0.5) * width / n

        parts += [
            _circle(px, line_y, 6, fill=color),
            _circle(px, line_y, 11, fill=color, opacity="0.2"),
        ]

        if i % 2 == 0:
            # Above
            parts += [
                _line(px, line_y - 7, px, line_y - 18, stroke=color, stroke_width="1", opacity="0.4"),
                _text(
                    px,
                    line_y - 24,
                    label,
                    fill=t["text"],
                    font_size="12",
                    font_weight="700",
                    font_family=t["font"],
                    text_anchor="middle",
                ),
            ]
            if date_txt:
                parts.append(
                    _text(
                        px,
                        line_y - 38,
                        date_txt,
                        fill=color,
                        font_size="10",
                        font_weight="600",
                        font_family=t["font"],
                        text_anchor="middle",
                    )
                )
            if body:
                parts.append(
                    _text(
                        px,
                        line_y - 52,
                        body,
                        fill=t["muted"],
                        font_size="10",
                        font_family=t["font"],
                        text_anchor="middle",
                    )
                )
        else:
            # Below
            parts += [
                _line(px, line_y + 7, px, line_y + 18, stroke=color, stroke_width="1", opacity="0.4"),
                _text(
                    px,
                    line_y + 30,
                    label,
                    fill=t["text"],
                    font_size="12",
                    font_weight="700",
                    font_family=t["font"],
                    text_anchor="middle",
                ),
            ]
            if date_txt:
                parts.append(
                    _text(
                        px,
                        line_y + 44,
                        date_txt,
                        fill=color,
                        font_size="10",
                        font_weight="600",
                        font_family=t["font"],
                        text_anchor="middle",
                    )
                )
            if body:
                parts.append(
                    _text(
                        px,
                        line_y + 58,
                        body,
                        fill=t["muted"],
                        font_size="10",
                        font_family=t["font"],
                        text_anchor="middle",
                    )
                )

    return "\n".join(parts), above_h + below_h + (cur_y - y) + 10


def _render_venn(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """2–3 overlapping Venn circles with optional intersection label."""
    items = section.get("items", [])
    center_label = section.get("center_label", "")
    title = section.get("title", "")
    n = min(len(items), 3)
    if n < 2:
        return "", 0.0

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    h = 240.0
    r_circ = h * 0.36
    cx_c = x + width / 2
    cy_c = cur_y + h / 2
    offset = r_circ * 0.48

    if n == 2:
        centers: list[tuple[float, float]] = [
            (cx_c - offset, cy_c),
            (cx_c + offset, cy_c),
        ]
    else:
        centers = [
            (cx_c, cy_c - offset),
            (cx_c - offset * 0.88, cy_c + offset * 0.52),
            (cx_c + offset * 0.88, cy_c + offset * 0.52),
        ]

    for i in range(n):
        ccx, ccy = centers[i]
        color = t["palette"][i % len(t["palette"])]
        parts += [
            _circle(ccx, ccy, r_circ, fill=color, opacity="0.12"),
            _circle(ccx, ccy, r_circ, fill="none", stroke=color, stroke_width="2", opacity="0.65"),
        ]
        # Label positioned toward outer edge
        dx = ccx - cx_c
        dy = ccy - cy_c
        norm = math.sqrt(dx * dx + dy * dy) or 1
        lx = ccx + (dx / norm) * r_circ * 0.52
        ly = ccy + (dy / norm) * r_circ * 0.52

        item = items[i]
        lbl = item.get("label", "")
        sub_list = item.get("items", [])
        anchor = "middle"
        if dx < -10:
            anchor = "end"
        elif dx > 10:
            anchor = "start"

        parts.append(
            _text(lx, ly, lbl, fill=color, font_size="13", font_weight="700", font_family=t["font"], text_anchor=anchor)
        )
        for si, sub in enumerate(sub_list[:3]):
            parts.append(
                _text(
                    lx,
                    ly + 15 + si * 13,
                    sub,
                    fill=t["muted"],
                    font_size="10",
                    font_family=t["font"],
                    text_anchor=anchor,
                )
            )

    if center_label:
        parts.append(
            _text(
                cx_c,
                cy_c + 5,
                center_label,
                fill=t["text"],
                font_size="12",
                font_weight="700",
                font_family=t["font"],
                text_anchor="middle",
            )
        )

    return "\n".join(parts), h + (cur_y - y) + 10


def _render_comparison(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Two-column VS comparison with labelled item lists."""
    left = section.get("left", {"label": "Option A", "items": []})
    right = section.get("right", {"label": "Option B", "items": []})
    title = section.get("title", "")

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    vs_w = 64.0
    col_w = (width - vs_w) / 2
    r = t.get("radius", 14)
    l_items = left.get("items", [])
    r_items = right.get("items", [])
    max_items = max(len(l_items), len(r_items), 1)
    card_h = max_items * 34 + 58

    # Left card
    c0 = t["palette"][0]
    parts += [
        _rect(x, cur_y, col_w, card_h, rx=r, fill=t["card_bg"], stroke=c0, stroke_width="1.5", filter="url(#g_shadow)"),
        _rect(x, cur_y, col_w, 46, rx=r, fill=c0, opacity="0.2"),
        _rect(x, cur_y + 46 - r, col_w, r, fill=c0, opacity="0.2"),
        _text(
            x + col_w / 2,
            cur_y + 30,
            left.get("label", ""),
            fill=c0,
            font_size="16",
            font_weight="800",
            font_family=t["font"],
            text_anchor="middle",
        ),
    ]
    for ii, it in enumerate(l_items):
        parts.append(
            _text(x + 16, cur_y + 60 + ii * 34, f"• {it}", fill=t["text"], font_size="12", font_family=t["font"])
        )

    # VS badge center
    vsx = x + col_w + vs_w / 2
    vsy = cur_y + card_h / 2
    parts += [
        _circle(vsx, vsy, 24, fill=t["card_bg"]),
        _circle(vsx, vsy, 24, fill="none", stroke=t["muted"], stroke_width="1"),
        _text(
            vsx,
            vsy + 5,
            "VS",
            fill=t["muted"],
            font_size="13",
            font_weight="800",
            font_family=t["font"],
            text_anchor="middle",
        ),
    ]

    # Right card
    c1 = t["palette"][1 % len(t["palette"])]
    rx2 = x + col_w + vs_w
    parts += [
        _rect(
            rx2, cur_y, col_w, card_h, rx=r, fill=t["card_bg"], stroke=c1, stroke_width="1.5", filter="url(#g_shadow)"
        ),
        _rect(rx2, cur_y, col_w, 46, rx=r, fill=c1, opacity="0.2"),
        _rect(rx2, cur_y + 46 - r, col_w, r, fill=c1, opacity="0.2"),
        _text(
            rx2 + col_w / 2,
            cur_y + 30,
            right.get("label", ""),
            fill=c1,
            font_size="16",
            font_weight="800",
            font_family=t["font"],
            text_anchor="middle",
        ),
    ]
    for ii, it in enumerate(r_items):
        parts.append(
            _text(rx2 + 16, cur_y + 60 + ii * 34, f"• {it}", fill=t["text"], font_size="12", font_family=t["font"])
        )

    return "\n".join(parts), card_h + (cur_y - y) + 10


def _render_swot(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """S/W/O/T 2×2 analysis grid with coloured headers."""
    quadrants = section.get(
        "quadrants",
        [
            {"label": "Strengths", "items": []},
            {"label": "Weaknesses", "items": []},
            {"label": "Opportunities", "items": []},
            {"label": "Threats", "items": []},
        ],
    )
    title = section.get("title", "")

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    letters = ["S", "W", "O", "T"]
    gap = 8.0
    cell_w = (width - gap) / 2
    max_items = max((len(q.get("items", [])) for q in quadrants[:4]), default=3)
    cell_h = max_items * 22 + 62
    r = t.get("radius", 10)

    for i, q in enumerate(quadrants[:4]):
        col = i % 2
        row = i // 2
        qx = x + col * (cell_w + gap)
        qy = cur_y + row * (cell_h + gap)
        color = t["palette"][i % len(t["palette"])]
        lbl = q.get("label", letters[i])
        items = q.get("items", [])

        parts += [
            _rect(qx, qy, cell_w, cell_h, rx=r, fill=t["card_bg"], stroke=t["card_border"], stroke_width="1"),
            _rect(qx, qy, cell_w, 48, rx=r, fill=color, opacity="0.22"),
            _rect(qx, qy + 48 - r, cell_w, r, fill=color, opacity="0.22"),
            # Big initial letter
            _text(qx + 18, qy + 34, letters[i], fill=color, font_size="22", font_weight="900", font_family=t["font"]),
            # Label next to letter
            _text(qx + 44, qy + 34, lbl, fill=color, font_size="13", font_weight="700", font_family=t["font"]),
        ]
        for ii, it in enumerate(items[:max_items]):
            parts.append(
                _text(qx + 14, qy + 62 + ii * 22, f"• {it}", fill=t["text"], font_size="11", font_family=t["font"])
            )

    return "\n".join(parts), 2 * cell_h + gap + (cur_y - y) + 10


def _render_matrix_2x2(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Generic 2×2 colour-coded grid with optional axis labels."""
    cells = section.get(
        "cells",
        [
            {"label": "", "body": ""},
            {"label": "", "body": ""},
            {"label": "", "body": ""},
            {"label": "", "body": ""},
        ],
    )
    x_label = section.get("x_label", "")
    y_label = section.get("y_label", "")
    title = section.get("title", "")

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    margin = 26.0
    gap = 8.0
    cell_w = (width - gap - margin) / 2
    chars = int(cell_w / 6.5)
    max_lines = max((len(_wrap_text(c.get("body", ""), chars)) for c in cells[:4]), default=2)
    cell_h = max_lines * 18 + 58
    r = t.get("radius", 10)

    # X-axis label (top)
    if x_label:
        parts.append(
            _text(
                x + margin + width / 2 - margin / 2,
                cur_y - 6,
                x_label,
                fill=t["muted"],
                font_size="10",
                font_weight="600",
                font_family=t["font"],
                text_anchor="middle",
                letter_spacing="1",
            )
        )

    # Y-axis label (rotated, left side)
    if y_label:
        yx = x + 10
        yy = cur_y + cell_h + gap / 2
        parts.append(
            f'<text x="{yx:.0f}" y="{yy:.0f}" '
            f'fill="{t["muted"]}" font-size="10" font-weight="600" '
            f'font-family="{t["font"]}" text-anchor="middle" '
            f'transform="rotate(-90 {yx:.0f} {yy:.0f})">{_e(y_label)}</text>'
        )

    for i, cell in enumerate(cells[:4]):
        col = i % 2
        row = i // 2
        cx2 = x + margin + col * (cell_w + gap)
        cy2 = cur_y + row * (cell_h + gap)
        color = t["palette"][i % len(t["palette"])]
        lbl = cell.get("label", "")
        body = cell.get("body", "")

        parts += [
            _rect(cx2, cy2, cell_w, cell_h, rx=r, fill=color, opacity="0.1"),
            _rect(cx2, cy2, cell_w, cell_h, rx=r, fill="none", stroke=color, stroke_width="1.5", opacity="0.4"),
            _rect(cx2 + r, cy2, cell_w - r * 2, 4, rx=2, fill=color),
            _text(cx2 + 14, cy2 + 28, lbl, fill=color, font_size="14", font_weight="700", font_family=t["font"]),
        ]
        for li, line in enumerate(_wrap_text(body, chars)):
            parts.append(
                _text(cx2 + 14, cy2 + 46 + li * 18, line, fill=t["muted"], font_size="11", font_family=t["font"])
            )

    return "\n".join(parts), 2 * cell_h + gap + (cur_y - y) + 10


def _render_quadrant_circle(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Circle divided into 4 equal coloured sectors with labels."""
    quadrants = section.get("quadrants", [])
    center_label = section.get("center_label", "")
    title = section.get("title", "")

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    h = min(float(width) * 0.75, 300.0)
    r_outer = h / 2 - 10
    r_inner = r_outer * 0.24
    cx_c = x + width / 2
    cy_c = cur_y + h / 2

    for i in range(4):
        start_deg = i * 90 - 90
        end_deg = start_deg + 89.5  # small gap between sectors
        color = t["palette"][i % len(t["palette"])]
        d = _donut_segment(cx_c, cy_c, r_outer, r_inner, start_deg, end_deg)
        parts += [
            _path(d, fill=color, opacity="0.28"),
            _path(d, fill="none", stroke=t["bg"], stroke_width="2"),
        ]

        if i < len(quadrants):
            q = quadrants[i]
            lbl = q.get("label", "")
            val_str = str(q.get("value", "")) if q.get("value") is not None else ""
            mid_angle = math.radians(start_deg + 45)
            lx = cx_c + (r_inner + (r_outer - r_inner) * 0.56) * math.cos(mid_angle)
            ly = cy_c + (r_inner + (r_outer - r_inner) * 0.56) * math.sin(mid_angle)
            parts.append(
                _text(
                    lx,
                    ly - 5,
                    lbl,
                    fill=color,
                    font_size="12",
                    font_weight="700",
                    font_family=t["font"],
                    text_anchor="middle",
                )
            )
            if val_str:
                parts.append(
                    _text(
                        lx,
                        ly + 10,
                        val_str,
                        fill=t["text"],
                        font_size="11",
                        font_family=t["font"],
                        text_anchor="middle",
                    )
                )

    # Dividing lines
    parts += [
        _line(cx_c - r_outer, cy_c, cx_c + r_outer, cy_c, stroke=t["bg"], stroke_width="3"),
        _line(cx_c, cy_c - r_outer, cx_c, cy_c + r_outer, stroke=t["bg"], stroke_width="3"),
    ]
    # Centre disc
    parts.append(_circle(cx_c, cy_c, r_inner, fill=t["card_bg"]))
    if center_label:
        parts.append(
            _text(
                cx_c,
                cy_c + 5,
                center_label,
                fill=t["text"],
                font_size="11",
                font_weight="700",
                font_family=t["font"],
                text_anchor="middle",
            )
        )

    return "\n".join(parts), h + (cur_y - y) + 10


def _render_card_grid(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Flexible-column card grid with top accent stripe."""
    items = section.get("items", [])
    cols = int(section.get("cols", 3))
    title = section.get("title", "")
    n = len(items)
    if not n:
        return "", 0.0

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    cols = min(cols, n, 4)
    gap = 12.0
    card_w = (width - (cols - 1) * gap) / cols
    r = t.get("radius", 12)
    chars = int(card_w / 6.5)

    max_lines = max(
        (len(_wrap_text(item.get("body", ""), chars)) for item in items),
        default=2,
    )
    card_h = max_lines * 18 + 72

    start_y = cur_y
    for i, item in enumerate(items):
        col = i % cols
        row = i // cols
        cx2 = x + col * (card_w + gap)
        cy2 = start_y + row * (card_h + gap)
        color = t["palette"][i % len(t["palette"])]
        lbl = item.get("title", "")
        body = item.get("body", "")

        parts += [
            _rect(cx2, cy2, card_w, card_h, rx=r, fill=t["card_bg"], filter="url(#g_shadow)"),
            _rect(cx2, cy2, card_w, card_h, rx=r, fill="none", stroke=t["card_border"], stroke_width="1"),
            # Top accent bar (sits inside the rounded corners)
            _rect(cx2 + r, cy2, card_w - r * 2, 4, rx=2, fill=color),
            # Number badge
            _circle(cx2 + 20, cy2 + 30, 13, fill=color, opacity="0.2"),
            _text(
                cx2 + 20,
                cy2 + 35,
                str(i + 1),
                fill=color,
                font_size="11",
                font_weight="800",
                font_family=t["font"],
                text_anchor="middle",
            ),
            # Card title
            _text(cx2 + 40, cy2 + 34, lbl, fill=t["text"], font_size="13", font_weight="700", font_family=t["font"]),
        ]
        for li, line in enumerate(_wrap_text(body, chars)[:max_lines]):
            parts.append(
                _text(cx2 + 14, cy2 + 52 + li * 18, line, fill=t["muted"], font_size="11", font_family=t["font"])
            )

    rows = (n - 1) // cols + 1
    total_h = rows * (card_h + gap) + (cur_y - y)
    return "\n".join(parts), total_h


def _render_pill_list(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Horizontal coloured pill steps connected by arrows."""
    items = section.get("items", [])
    title = section.get("title", "")
    n = len(items)
    if not n:
        return "", 0.0

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    arrow_w = 22.0
    pill_h = 42.0
    pill_r = pill_h / 2
    gap = arrow_w
    pill_w = (width - (n - 1) * gap) / n

    for i, item in enumerate(items):
        label = item.get("label", "")
        sub = item.get("sub", "")
        slot = i % len(t["palette"])
        px = x + i * (pill_w + gap)
        py = cur_y

        # Pill background gradient
        parts.append(_rect(px, py, pill_w, pill_h, rx=pill_r, fill=f"url(#g_bar_{slot})"))

        # Number circle on left
        parts += [
            _circle(px + pill_r, py + pill_h / 2, pill_r * 0.58, fill="rgba(0,0,0,0.22)"),
            _text(
                px + pill_r,
                py + pill_h / 2 + 5,
                str(i + 1),
                fill="white",
                font_size="12",
                font_weight="800",
                font_family=t["font"],
                text_anchor="middle",
            ),
        ]

        # Label (right portion of pill)
        text_x = px + pill_r + 18 + (pill_w - pill_r - 22) / 2
        parts.append(
            _text(
                text_x,
                py + pill_h / 2 + 5,
                label,
                fill="white",
                font_size="11",
                font_weight="700",
                font_family=t["font"],
                text_anchor="middle",
            )
        )

        if sub:
            parts.append(
                _text(
                    px + pill_w / 2,
                    py + pill_h + 17,
                    sub,
                    fill=t["muted"],
                    font_size="10",
                    font_family=t["font"],
                    text_anchor="middle",
                )
            )

        # Arrow to next
        if i < n - 1:
            ax = px + pill_w + 3
            ay = py + pill_h / 2
            aend = ax + arrow_w - 4
            parts += [
                _line(ax, ay, aend, ay, stroke=t["muted"], stroke_width="1.5", opacity="0.45"),
                _path(
                    f"M {aend:.0f} {ay:.0f} L {aend - 7:.0f} {ay - 4:.0f} L {aend - 7:.0f} {ay + 4:.0f} Z",
                    fill=t["muted"],
                    opacity="0.45",
                ),
            ]

    return "\n".join(parts), pill_h + 30 + (cur_y - y)


def _render_wheel(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    """Segmented wheel/donut — equal-size or value-proportional slices."""
    data = section.get("data", [])
    equal = bool(section.get("equal", False))
    center_label = section.get("center_label", "")
    title = section.get("title", "")
    n = len(data)
    if not n:
        return "", 0.0

    parts: list[str] = []
    cur_y = y
    if title:
        s, dh = _section_title(title, x, cur_y, width, t)
        parts.append(s)
        cur_y += dh + 10

    h = min(float(width) * 0.72, 270.0)
    r_outer = h / 2 - 10
    r_inner = r_outer * 0.38
    cx_c = x + width / 2
    cy_c = cur_y + h / 2

    total = n if equal else (sum(d.get("value", 1) for d in data) or n)
    angle = 0.0

    for i, item in enumerate(data):
        val = 1 if equal else item.get("value", 1)
        sweep = (val / total) * 360
        color = item.get("color") or t["palette"][i % len(t["palette"])]
        label = item.get("label", "")

        d = _donut_segment(cx_c, cy_c, r_outer, r_inner, angle, angle + sweep - 0.8)
        parts += [
            _path(d, fill=color, opacity="0.82"),
            _path(d, fill="none", stroke=t["bg"], stroke_width="2"),
        ]

        if sweep > 16:
            mid_a = math.radians(angle + sweep / 2 - 90)
            lx = cx_c + (r_inner + (r_outer - r_inner) * 0.6) * math.cos(mid_a)
            ly = cy_c + (r_inner + (r_outer - r_inner) * 0.6) * math.sin(mid_a)
            parts.append(
                _text(
                    lx,
                    ly + 4,
                    label,
                    fill="white",
                    font_size="11",
                    font_weight="700",
                    font_family=t["font"],
                    text_anchor="middle",
                )
            )

        angle += sweep

    # Centre disc
    parts.append(_circle(cx_c, cy_c, r_inner, fill=t["card_bg"]))
    if center_label:
        parts.append(
            _text(
                cx_c,
                cy_c + 5,
                center_label,
                fill=t["text"],
                font_size="13",
                font_weight="700",
                font_family=t["font"],
                text_anchor="middle",
            )
        )

    # Legend row below wheel
    legend_y = cur_y + h + 12
    legend_gap = min(130.0, width / n)
    start_lx = x + (width - n * legend_gap) / 2

    for i, item in enumerate(data):
        color = item.get("color") or t["palette"][i % len(t["palette"])]
        lbl = item.get("label", "")
        val = item.get("value", "")
        lx = start_lx + i * legend_gap
        parts += [
            _rect(lx, legend_y, 12, 12, rx=2, fill=color),
            _text(lx + 16, legend_y + 10, lbl, fill=t["text"], font_size="11", font_family=t["font"]),
        ]
        if val and not equal:
            parts.append(
                _text(lx + 16, legend_y + 22, str(val), fill=t["muted"], font_size="10", font_family=t["font"])
            )

    return "\n".join(parts), h + 50 + (cur_y - y)


def _render_sustainability_dashboard(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    brand = section.get("brand", "EcoFuture")
    report_label = section.get("report_label", "Sustainability Report")
    title = section.get("title", "Building a Sustainable Tomorrow")
    subtitle = section.get("subtitle", "")
    cta_label = section.get("cta_label", "Our Commitment")
    stats = section.get("stats", [])
    impacts = section.get("impacts", [])
    emissions = section.get("emissions", {})
    operations = section.get("operations", {})
    focus_areas = section.get("focus_areas", [])
    recognitions = section.get("recognitions", [])
    quote = section.get("quote", {})
    principles = section.get("principles", [])
    is_light = _is_light_theme(t)

    parts: list[str] = []
    cur_y = y
    gap = 14.0
    hero_h = 520.0
    parts.append(
        _group(
            _rect(x, cur_y, width, hero_h, rx=28, fill=t["card_bg"]),
            filter="url(#g_shadow_soft)" if is_light else "url(#g_shadow)",
        )
    )
    parts.append(_rect(x, cur_y, width, hero_h, rx=28, fill="none", stroke=t["card_border"], stroke_width="1"))

    logo_x = x + 24
    logo_y = cur_y + 30
    parts.append(
        _render_icon(
            icon=None,
            icon_name="leaf",
            title=brand,
            body="",
            cx=logo_x,
            cy=logo_y,
            size=24,
            color=t["palette"][0],
            font_family=t.get("font_ui", t["font"]),
        )
    )
    parts.append(
        _text(
            logo_x + 26,
            logo_y + 5,
            brand,
            fill=t["text"],
            font_size="18",
            font_weight="700",
            font_family=t.get("font_display", t["font"]),
        )
    )
    report_x = x + width - 200
    parts.append(
        _text(
            report_x,
            logo_y + 4,
            report_label,
            fill=t["text"],
            font_size="12",
            font_weight="500",
            font_family=t.get("font_ui", t["font"]),
        )
    )
    parts.append(_circle(x + width - 24, logo_y, 4, fill=t["palette"][0]))

    left_x = x + 24
    title_lines = _wrap_text(title, 15)
    for i, line in enumerate(title_lines[:4]):
        parts.append(
            _text(
                left_x,
                cur_y + 110 + i * 58,
                line,
                fill=t["text"],
                font_size="46",
                font_weight="760",
                font_family=t.get("font_display", t["font"]),
                letter_spacing="-1.6",
            )
        )

    subtitle_y = cur_y + 110 + len(title_lines[:4]) * 58 + 18
    for i, line in enumerate(_wrap_text(subtitle, 34)[:3]):
        parts.append(
            _text(
                left_x,
                subtitle_y + i * 24,
                line,
                fill=t["muted"],
                font_size="16",
                font_family=t.get("font_ui", t["font"]),
            )
        )

    cta_w = max(160, len(cta_label) * 8 + 44)
    cta_y = cur_y + hero_h - 118
    parts += [
        _rect(left_x, cta_y, cta_w, 40, rx=20, fill=_mix(t["paper_tint"], t["palette"][0], 0.06)),
        _rect(left_x, cta_y, cta_w, 40, rx=20, fill="none", stroke=t["card_border"], stroke_width="1"),
        _text(
            left_x + 20,
            cta_y + 26,
            cta_label,
            fill=t["text"],
            font_size="12",
            font_weight="500",
            font_family=t.get("font_ui", t["font"]),
        ),
    ]
    parts.append(
        _render_named_icon("arrow-right", left_x + cta_w - 28, cta_y + 20, 14, t["palette"][0], stroke_width=1.8)
    )

    visual_x = x + width * 0.36
    visual_y = cur_y + 52
    visual_w = width * 0.60
    visual_h = 270.0
    parts.append(
        _group(
            _rect(visual_x, visual_y, visual_w, visual_h, rx=26, fill=_mix("#FFFFFF", t["palette"][1], 0.05)),
            filter="url(#g_shadow)",
        )
    )
    parts.append(
        _rect(visual_x, visual_y, visual_w, visual_h, rx=26, fill="none", stroke=t["card_border"], stroke_width="1")
    )
    parts.append(
        _circle(
            visual_x + visual_w * 0.56,
            visual_y + 86,
            140,
            fill=_alpha(t["palette"][1], 0.08),
            filter="url(#g_blur_blob)",
        )
    )
    parts.append(
        _rect(
            visual_x + 18,
            visual_y + visual_h - 68,
            visual_w - 36,
            52,
            rx=26,
            fill=_mix("#FFFFFF", t["palette"][0], 0.12),
        )
    )
    parts.append(
        _path(
            f"M {visual_x + 18:.1f} {visual_y + visual_h - 44:.1f} C {visual_x + 100:.1f} {visual_y + visual_h - 92:.1f} {visual_x + 160:.1f} {visual_y + visual_h - 20:.1f} {visual_x + 242:.1f} {visual_y + visual_h - 52:.1f} S {visual_x + 420:.1f} {visual_y + visual_h - 84:.1f} {visual_x + visual_w - 18:.1f} {visual_y + visual_h - 40:.1f} L {visual_x + visual_w - 18:.1f} {visual_y + visual_h + 8:.1f} L {visual_x + 18:.1f} {visual_y + visual_h + 8:.1f} Z",
            fill=_mix("#FFFFFF", t["palette"][0], 0.18),
        )
    )
    parts.append(
        _path(
            f"M {visual_x + 18:.1f} {visual_y + visual_h - 28:.1f} C {visual_x + 110:.1f} {visual_y + visual_h - 76:.1f} {visual_x + 180:.1f} {visual_y + visual_h - 6:.1f} {visual_x + 270:.1f} {visual_y + visual_h - 38:.1f} S {visual_x + 420:.1f} {visual_y + visual_h - 62:.1f} {visual_x + visual_w - 18:.1f} {visual_y + visual_h - 18:.1f} L {visual_x + visual_w - 18:.1f} {visual_y + visual_h + 8:.1f} L {visual_x + 18:.1f} {visual_y + visual_h + 8:.1f} Z",
            fill=_mix("#FFFFFF", t["palette"][4], 0.2),
        )
    )
    for tx in (visual_x + 130, visual_x + 250):
        parts.append(
            _line(tx, visual_y + 98, tx, visual_y + 182, stroke=_alpha(t["palette"][0], 0.35), stroke_width="2")
        )
        parts.append(
            _path(
                f"M {tx:.1f} {visual_y + 98:.1f} L {tx - 26:.1f} {visual_y + 116:.1f} L {tx:.1f} {visual_y + 111:.1f} L {tx + 26:.1f} {visual_y + 116:.1f} Z",
                fill=_alpha(t["palette"][0], 0.28),
            )
        )
    for sx in (visual_x + visual_w * 0.58, visual_x + visual_w * 0.68, visual_x + visual_w * 0.77):
        bh = 52 + (sx % 40)
        parts.append(_rect(sx, visual_y + visual_h - 140 - bh * 0.3, 20, bh, rx=4, fill=_alpha(t["palette"][1], 0.18)))
    parts.append(
        _line(
            visual_x + 40,
            visual_y + visual_h - 52,
            visual_x + visual_w - 40,
            visual_y + visual_h - 52,
            stroke=_alpha(t["palette"][0], 0.25),
            stroke_width="2",
        )
    )
    parts.append(
        _circle(
            visual_x + visual_w - 92,
            visual_y + visual_h - 80,
            44,
            fill=_alpha(t["palette"][0], 0.10),
            filter="url(#g_shadow)",
        )
    )
    parts.append(
        _render_named_icon(
            "tree", visual_x + visual_w - 92, visual_y + visual_h - 82, 58, t["palette"][0], stroke_width=1.8
        )
    )

    if stats:
        strip_x = visual_x - 18
        strip_y = visual_y + visual_h - 8
        strip_w = width - (strip_x - x) - 18
        strip_h = 150.0
        parts.append(
            _group(_rect(strip_x, strip_y, strip_w, strip_h, rx=24, fill=t["card_bg"]), filter="url(#g_shadow_soft)")
        )
        parts.append(
            _rect(strip_x, strip_y, strip_w, strip_h, rx=24, fill="none", stroke=t["card_border"], stroke_width="1")
        )
        item_w = strip_w / max(len(stats), 1)
        for i, stat in enumerate(stats[:4]):
            sx = strip_x + i * item_w
            color = stat.get("color") or t["palette"][i % len(t["palette"])]
            if i > 0:
                parts.append(
                    _line(sx, strip_y + 28, sx, strip_y + strip_h - 28, stroke=t["card_border"], stroke_width="1")
                )
            icon_cx = sx + 56
            parts.append(_circle(icon_cx, strip_y + 54, 28, fill=_mix("#FFFFFF", color, 0.12)))
            parts.append(
                _render_icon(
                    icon=stat.get("icon", ""),
                    icon_name=stat.get("icon_name", ""),
                    title=stat.get("label", ""),
                    body="",
                    cx=icon_cx,
                    cy=strip_y + 54,
                    size=24,
                    color=color,
                    font_family=t.get("font_ui", t["font"]),
                )
            )
            parts += [
                _text(
                    sx + 28,
                    strip_y + 118,
                    str(stat.get("value", "")),
                    fill=t["text"],
                    font_size="28",
                    font_weight="760",
                    font_family=t.get("font_display", t["font"]),
                ),
                _text(
                    sx + 28,
                    strip_y + 145,
                    stat.get("label", ""),
                    fill=t["text"],
                    font_size="12",
                    font_weight="500",
                    font_family=t.get("font_ui", t["font"]),
                ),
            ]
            if stat.get("change"):
                parts.append(
                    _text(
                        sx + 28,
                        strip_y + 170,
                        str(stat.get("change")),
                        fill=color,
                        font_size="11",
                        font_weight="600",
                        font_family=t.get("font_ui", t["font"]),
                    )
                )
        cur_y = strip_y + strip_h + 28
    else:
        cur_y += hero_h + 24

    row_h = 410.0
    left_w = width * 0.54
    right_w = width - left_w - gap
    left_x = x
    right_x = x + left_w + gap

    parts.append(_group(_rect(left_x, cur_y, left_w, row_h, rx=24, fill=t["card_bg"]), filter="url(#g_shadow)"))
    parts.append(_rect(left_x, cur_y, left_w, row_h, rx=24, fill="none", stroke=t["card_border"], stroke_width="1"))
    parts.append(
        _text(
            left_x + 28,
            cur_y + 44,
            section.get("impact_title", "Our Impact in 2024"),
            fill=t["text"],
            font_size="18",
            font_weight="700",
            font_family=t.get("font_display", t["font"]),
        )
    )
    for i, item in enumerate(impacts[:4]):
        iy = cur_y + 88 + i * 86
        color = item.get("color") or t["palette"][i % len(t["palette"])]
        parts.append(_circle(left_x + 50, iy + 10, 24, fill=_mix("#FFFFFF", color, 0.12)))
        parts.append(
            _render_icon(
                icon=item.get("icon", ""),
                icon_name=item.get("icon_name", ""),
                title=item.get("title", ""),
                body=item.get("body", ""),
                cx=left_x + 50,
                cy=iy + 10,
                size=22,
                color=color,
                font_family=t.get("font_ui", t["font"]),
            )
        )
        parts += [
            _text(
                left_x + 98,
                iy + 2,
                item.get("title", ""),
                fill=t["text"],
                font_size="14",
                font_weight="600",
                font_family=t.get("font_display", t["font"]),
            ),
            _text(
                left_x + left_w - 28,
                iy + 20,
                str(item.get("value", "")),
                fill=color,
                font_size="18",
                font_weight="700",
                font_family=t.get("font_display", t["font"]),
                text_anchor="end",
            ),
        ]
        for li, line in enumerate(_wrap_text(item.get("body", ""), 34)[:2]):
            parts.append(
                _text(
                    left_x + 98,
                    iy + 24 + li * 16,
                    line,
                    fill=t["muted"],
                    font_size="11.5",
                    font_family=t.get("font_ui", t["font"]),
                )
            )
        bar_y = iy + 38
        parts += [
            _rect(left_x + 98, bar_y, left_w - 190, 6, rx=3, fill=_mix(t["paper_tint"], t["card_border"], 0.45)),
            _rect(
                left_x + 98,
                bar_y,
                (left_w - 190) * max(0.0, min(1.0, _num(item.get("value", 0)) / 100.0)),
                6,
                rx=3,
                fill=f"url(#g_bar_{i % len(t['palette'])})",
            ),
        ]

    parts.append(_group(_rect(right_x, cur_y, right_w, row_h, rx=24, fill=t["card_bg"]), filter="url(#g_shadow)"))
    parts.append(_rect(right_x, cur_y, right_w, row_h, rx=24, fill="none", stroke=t["card_border"], stroke_width="1"))
    emission_title = emissions.get("title", "Emissions Reduced")
    emission_subtitle = emissions.get("subtitle", "Metric tons of CO2 equivalent")
    parts += [
        _text(
            right_x + 28,
            cur_y + 44,
            emission_title,
            fill=t["text"],
            font_size="18",
            font_weight="700",
            font_family=t.get("font_display", t["font"]),
        ),
        _text(
            right_x + 28,
            cur_y + 68,
            emission_subtitle,
            fill=t["muted"],
            font_size="12",
            font_family=t.get("font_ui", t["font"]),
        ),
        _text(
            right_x + 28,
            cur_y + 128,
            str(emissions.get("value", "")),
            fill=t["palette"][0],
            font_size="40",
            font_weight="760",
            font_family=t.get("font_display", t["font"]),
        ),
    ]
    if emissions.get("change"):
        parts.append(
            _text(
                right_x + 28,
                cur_y + 156,
                str(emissions.get("change")),
                fill=t["palette"][0],
                font_size="14",
                font_weight="600",
                font_family=t.get("font_ui", t["font"]),
            )
        )
    filter_label = emissions.get("filter_label", "Annual")
    fl_w = max(78, len(filter_label) * 8 + 24)
    parts += [
        _rect(right_x + right_w - fl_w - 22, cur_y + 96, fl_w, 36, rx=10, fill=t["card_bg"]),
        _rect(
            right_x + right_w - fl_w - 22,
            cur_y + 96,
            fl_w,
            36,
            rx=10,
            fill="none",
            stroke=t["card_border"],
            stroke_width="1",
        ),
        _text(
            right_x + right_w - fl_w / 2 - 22,
            cur_y + 119,
            filter_label,
            fill=t["text"],
            font_size="12",
            font_family=t.get("font_ui", t["font"]),
            text_anchor="middle",
        ),
    ]
    series = emissions.get("series", [])
    x_labels = emissions.get("x_labels", [])
    chart_x = right_x + 28
    chart_y = cur_y + 200
    chart_w = right_w - 56
    chart_h = 150.0
    max_val = max((_num(v) for v in series), default=1) or 1
    for j in range(5):
        gy = chart_y + chart_h - j * (chart_h / 4)
        parts.append(
            _line(chart_x + 28, gy, chart_x + chart_w, gy, stroke=_alpha(t["card_border"], 0.7), stroke_width="1")
        )
    if series:
        pts = []
        for i, val in enumerate(series):
            px2 = chart_x + 40 + i * ((chart_w - 56) / max(len(series) - 1, 1))
            py2 = chart_y + chart_h - (_num(val) / max_val) * (chart_h - 12)
            pts.append((px2, py2))
        area_path = (
            f"M {pts[0][0]:.1f} {chart_y + chart_h:.1f} L "
            + " L ".join(f"{px2:.1f} {py2:.1f}" for px2, py2 in pts)
            + f" L {pts[-1][0]:.1f} {chart_y + chart_h:.1f} Z"
        )
        parts.append(_path(area_path, fill=_alpha(t["palette"][0], 0.12)))
        line_path = "M " + " L ".join(f"{px2:.1f} {py2:.1f}" for px2, py2 in pts)
        parts.append(_path(line_path, fill="none", stroke=t["palette"][0], stroke_width="2.5"))
        for px2, py2 in pts:
            parts += [
                _circle(px2, py2, 4.5, fill=t["card_bg"]),
                _circle(px2, py2, 4.5, fill="none", stroke=t["palette"][0], stroke_width="2"),
            ]
        for i, label in enumerate(x_labels[: len(series)]):
            lx = chart_x + 40 + i * ((chart_w - 56) / max(len(series) - 1, 1))
            parts.append(
                _text(
                    lx,
                    chart_y + chart_h + 24,
                    label,
                    fill=t["muted"],
                    font_size="11",
                    font_family=t.get("font_ui", t["font"]),
                    text_anchor="middle",
                )
            )

    cur_y += row_h + 22

    card_h = 330.0
    col_gap = 14.0
    col_w = (width - col_gap * 2) / 3
    cards = [
        ("operations", operations.get("title", "Where We Operate")),
        ("focus", section.get("focus_title", "Our 2024 Focus Areas")),
        ("recognition", section.get("recognition_title", "Recognition")),
    ]
    for idx, (_, heading) in enumerate(cards):
        cx2 = x + idx * (col_w + col_gap)
        parts.append(_group(_rect(cx2, cur_y, col_w, card_h, rx=24, fill=t["card_bg"]), filter="url(#g_shadow)"))
        parts.append(_rect(cx2, cur_y, col_w, card_h, rx=24, fill="none", stroke=t["card_border"], stroke_width="1"))
        parts.append(
            _text(
                cx2 + 28,
                cur_y + 44,
                heading,
                fill=t["text"],
                font_size="18",
                font_weight="700",
                font_family=t.get("font_display", t["font"]),
            )
        )

    op_x = x
    regions = operations.get("regions", [])
    parts.append(_rect(op_x + 36, cur_y + 82, col_w - 72, 136, rx=16, fill=_mix("#FFFFFF", t["palette"][1], 0.05)))
    blobs = [
        (op_x + 84, cur_y + 150, 28, 18),
        (op_x + 150, cur_y + 130, 34, 22),
        (op_x + 220, cur_y + 160, 30, 20),
        (op_x + 284, cur_y + 174, 22, 14),
    ]
    for bx, by, bw, bh in blobs:
        parts.append(_rect(bx, by, bw, bh, rx=bh / 2, fill=_alpha(t["card_border"], 0.55)))
    for i, region in enumerate(regions[:4]):
        mx = op_x + 64 + i * 68
        my = cur_y + 158 - (i % 2) * 16
        parts += [
            _circle(mx, my, 11, fill=_alpha(t["palette"][0], 0.15)),
            _circle(mx, my, 4, fill=t["palette"][0]),
        ]
        rx2 = op_x + 22 + i * (col_w - 44) / max(len(regions[:4]), 1)
        parts.append(
            _text(
                rx2 + 20,
                cur_y + 274,
                region.get("label", ""),
                fill=t["muted"],
                font_size="11",
                font_family=t.get("font_ui", t["font"]),
                text_anchor="middle",
            )
        )
        parts.append(
            _text(
                rx2 + 20,
                cur_y + 300,
                str(region.get("value", "")),
                fill=t["palette"][0],
                font_size="16",
                font_weight="700",
                font_family=t.get("font_display", t["font"]),
                text_anchor="middle",
            )
        )

    fx = x + col_w + col_gap
    for i, item in enumerate(focus_areas[:4]):
        iy = cur_y + 86 + i * 58
        color = item.get("color") or t["palette"][i % len(t["palette"])]
        parts += [
            _circle(fx + 48, iy + 8, 20, fill=_mix("#FFFFFF", color, 0.12)),
            _render_icon(
                icon=item.get("icon", ""),
                icon_name=item.get("icon_name", ""),
                title=item.get("title", ""),
                body=item.get("body", ""),
                cx=fx + 48,
                cy=iy + 8,
                size=18,
                color=color,
                font_family=t.get("font_ui", t["font"]),
            ),
            _text(
                fx + 82,
                iy + 0,
                item.get("title", ""),
                fill=t["text"],
                font_size="13.5",
                font_weight="600",
                font_family=t.get("font_display", t["font"]),
            ),
        ]
        for li, line in enumerate(_wrap_text(item.get("body", ""), 24)[:2]):
            parts.append(
                _text(
                    fx + 82,
                    iy + 18 + li * 15,
                    line,
                    fill=t["muted"],
                    font_size="11",
                    font_family=t.get("font_ui", t["font"]),
                )
            )

    rx = x + 2 * (col_w + col_gap)
    for i, item in enumerate(recognitions[:3]):
        iy = cur_y + 92 + i * 72
        color = item.get("color") or t["palette"][i % len(t["palette"])]
        parts.append(_circle(rx + 48, iy + 4, 22, fill=_mix("#FFFFFF", color, 0.1)))
        parts.append(
            _render_icon(
                icon=item.get("icon", ""),
                icon_name=item.get("icon_name", "trophy"),
                title=item.get("title", ""),
                body=item.get("subtitle", ""),
                cx=rx + 48,
                cy=iy + 4,
                size=20,
                color=color,
                font_family=t.get("font_ui", t["font"]),
            )
        )
        parts += [
            _text(
                rx + 82,
                iy + 2,
                item.get("title", ""),
                fill=t["text"],
                font_size="13.5",
                font_weight="600",
                font_family=t.get("font_display", t["font"]),
            ),
            _text(
                rx + 82,
                iy + 24,
                item.get("subtitle", ""),
                fill=t["muted"],
                font_size="11.5",
                font_family=t.get("font_ui", t["font"]),
            ),
        ]

    cur_y += card_h + 22

    banner_h = 116.0
    parts.append(
        _group(
            _rect(x, cur_y, width, banner_h, rx=24, fill=_mix(t["paper_tint"], t["palette"][1], 0.06)),
            filter="url(#g_shadow)",
        )
    )
    parts.append(_rect(x, cur_y, width, banner_h, rx=24, fill="none", stroke=t["card_border"], stroke_width="1"))
    quote_text = quote.get("text", "")
    quote_author = quote.get("author", "")
    parts.append(
        _text(
            x + 48,
            cur_y + 66,
            "“",
            fill=_alpha(t["palette"][0], 0.6),
            font_size="68",
            font_weight="700",
            font_family=t.get("font_display", t["font"]),
        )
    )
    for i, line in enumerate(_wrap_text(quote_text, 34)[:2]):
        parts.append(
            _text(
                x + 100,
                cur_y + 42 + i * 28,
                line,
                fill=t["text"],
                font_size="17",
                font_weight="500",
                font_family=t.get("font_display", t["font"]),
            )
        )
    if quote_author:
        parts.append(
            _text(
                x + 100,
                cur_y + 88,
                f"– {quote_author}",
                fill=t["muted"],
                font_size="12",
                font_family=t.get("font_ui", t["font"]),
            )
        )
    if principles:
        start_x = x + width * 0.58
        step_w = (width * 0.36) / max(len(principles), 1)
        for i, item in enumerate(principles[:4]):
            pcx = start_x + i * step_w + step_w / 2
            color = item.get("color") or t["palette"][i % len(t["palette"])]
            parts.append(_circle(pcx, cur_y + 52, 22, fill=t["card_bg"]))
            parts.append(
                _render_icon(
                    icon=item.get("icon", ""),
                    icon_name=item.get("icon_name", ""),
                    title=item.get("label", ""),
                    body="",
                    cx=pcx,
                    cy=cur_y + 52,
                    size=18,
                    color=color,
                    font_family=t.get("font_ui", t["font"]),
                )
            )
            for li, line in enumerate(_wrap_text(item.get("label", ""), 10)[:2]):
                parts.append(
                    _text(
                        pcx,
                        cur_y + 90 + li * 14,
                        line,
                        fill=t["text"],
                        font_size="11",
                        font_family=t.get("font_ui", t["font"]),
                        text_anchor="middle",
                    )
                )

    return "\n".join(parts), cur_y + banner_h - y


def _assessment_panel_shell(x: float, y: float, w: float, h: float, *, fill: str, border: str, rx: float = 18) -> str:
    return "".join(
        [
            _rect(x, y, w, h, rx=rx, fill=fill),
            _rect(x, y, w, h, rx=rx, fill="none", stroke=border, stroke_width="1"),
        ]
    )


def _assessment_status_color(label: object, t: dict, fallback: str | None = None) -> str:
    lowered = str(label or "").strip().lower()
    if any(word in lowered for word in ("critical", "severe", "urgent")):
        return "#E8614E"
    if any(word in lowered for word in ("high", "elevated")):
        return "#F18675"
    if any(word in lowered for word in ("medium", "moderate", "watch")):
        return "#F0BE48"
    if any(word in lowered for word in ("low", "excellent", "strong", "ready", "safe")):
        return "#54AE74"
    if any(word in lowered for word in ("good", "stable")):
        return "#5E92EA"
    if "very good" in lowered:
        return "#8A79EC"
    return fallback or t["palette"][0]


def _assessment_value_text(value: object) -> str:
    if isinstance(value, (int, float)):
        numeric = float(value)
        return str(int(numeric)) if numeric.is_integer() else f"{numeric:g}"

    raw = str(value or "").strip()
    if not raw:
        return ""

    try:
        numeric = float(raw.replace(",", "").replace("%", ""))
        if raw.endswith("%"):
            return raw
        return str(int(numeric)) if numeric.is_integer() else f"{numeric:g}"
    except Exception:
        return raw


def _render_assessment_scorecard_certificate(
    section: dict, x: float, y: float, width: float, t: dict
) -> tuple[str, float]:
    badge = section.get("badge", "Assessment Scorecard")
    title = section.get("title", "AI Threat Assessment")
    subtitle = section.get("subtitle", "")
    facts = section.get("facts", [])
    score = _num(section.get("score", 0))
    max_score = _num(section.get("max_score", 100), 100.0)
    status = section.get("status", "")
    score_note = section.get("score_note", "")
    delta = section.get("delta", "")
    delta_caption = section.get("delta_caption", "")
    percentile_label = section.get("percentile_label", "Percentile Rank")
    percentile_value = section.get("percentile_value", "")
    footer = section.get("footer", {})
    recommendation = section.get("recommendation", {})
    raw_items = section.get("risk_items") or section.get("tasks") or section.get("categories") or []
    raw_insights = section.get("key_insights") or section.get("insights") or []
    risk_drivers = section.get("risk_drivers") or []
    tools = section.get("tools") or []
    summary_cards = section.get("summary_cards") or []
    is_light = _is_light_theme(t)

    panel_fill = t["card_bg"] if not is_light else _mix("#FFFFFF", t.get("paper_tint", t["bg"]), 0.08)
    band_fill = _mix("#FFFFFF", t["palette"][0], 0.04) if is_light else _mix(t["card_bg"], t["palette"][0], 0.08)
    border = t["card_border"] if not is_light else _mix(t["card_border"], t["text"], 0.06)
    divider = _alpha(border, 0.95) if is_light else border
    font_display = t.get("font_display", t["font"])
    font_ui = t.get("font_ui", t["font"])

    if isinstance(recommendation, str):
        recommendation = {"title": recommendation}
    if isinstance(footer, str):
        footer = {"title": footer}

    items: list[dict] = []
    for index, item in enumerate(raw_items[:6]):
        if not isinstance(item, dict):
            continue
        label = item.get("title") or item.get("label") or item.get("name") or ""
        value_raw = item.get("score", item.get("value", ""))
        status_text = item.get("status") or item.get("level") or ""
        color = item.get("color") or _assessment_status_color(
            status_text or value_raw, t, t["palette"][index % len(t["palette"])]
        )
        items.append(
            {
                "label": label,
                "body": item.get("body", "") or item.get("description", ""),
                "value": _assessment_value_text(value_raw),
                "status": status_text,
                "color": color,
            }
        )

    insights: list[dict] = []
    for index, item in enumerate(raw_insights[:4]):
        if isinstance(item, str):
            insights.append({"title": item, "body": "", "color": t["palette"][index % len(t["palette"])]})
        elif isinstance(item, dict):
            insights.append(
                {
                    "title": item.get("title") or item.get("label") or "",
                    "body": item.get("body", ""),
                    "icon_name": item.get("icon_name", ""),
                    "color": item.get("color") or t["palette"][index % len(t["palette"])],
                }
            )

    risk_label = section.get("risk_label") or section.get("summary_value") or ""
    if not risk_label:
        lowered = status.lower()
        if any(word in lowered for word in ("critical", "high", "low", "moderate")):
            risk_label = status
        elif status:
            risk_label = status
        elif delta:
            risk_label = str(delta)
        else:
            risk_label = "Needs Review"

    summary_title = section.get("summary_title") or (
        "Risk Outlook" if section.get("risk_label") else "Assessment Summary"
    )
    summary_body = section.get("risk_body") or section.get("summary_body") or score_note or delta_caption
    summary_color = _assessment_status_color(risk_label or status, t, t["palette"][0])
    summary_stats = section.get("summary_metrics") or []
    if not summary_stats:
        if delta:
            summary_stats.append(
                {"label": section.get("delta_label", "Change"), "value": str(delta), "note": delta_caption}
            )
        if percentile_value:
            summary_stats.append({"label": percentile_label, "value": percentile_value})
    summary_stats = [item for item in summary_stats[:2] if isinstance(item, dict)]

    parts: list[str] = []
    cur_y = y

    badge_w = len(badge) * 7.1 + 30
    parts += [
        _rect(x, cur_y, badge_w, 28, rx=14, fill=band_fill),
        _rect(x, cur_y, badge_w, 28, rx=14, fill="none", stroke=divider, stroke_width="1"),
        _render_icon(
            icon=None,
            icon_name=section.get("badge_icon_name", "spark"),
            title=badge,
            body="",
            cx=x + 16,
            cy=cur_y + 14,
            size=10,
            color=summary_color,
            font_family=font_ui,
        ),
        _text(
            x + 30,
            cur_y + 19,
            badge.upper(),
            fill=t["muted"],
            font_size="11",
            font_weight="700",
            font_family=font_ui,
            letter_spacing="0.45",
        ),
    ]

    left_w = width * 0.41
    gauge_w = width * 0.27
    gap = 16.0
    right_w = width - left_w - gauge_w - gap * 2
    risk_label_lines = _wrap_text(str(risk_label), 14 if right_w < 250 else 16)[:2]
    risk_label_font_size = (
        26
        if len(risk_label_lines) == 1 and len(risk_label_lines[0]) <= 12
        else 22
        if len(risk_label_lines) == 1
        else 18
    )
    risk_label_line_gap = 20
    top_y = cur_y + 38
    left_x = x
    gauge_x = left_x + left_w + gap
    right_x = gauge_x + gauge_w + gap
    top_h = 216.0

    title_lines = _wrap_text(title, 16)[:3]
    for index, line in enumerate(title_lines):
        parts.append(
            _text(
                left_x + 6,
                top_y + 42 + index * 34,
                line,
                fill=t["text"],
                font_size="31",
                font_weight="760",
                font_family=font_display,
                letter_spacing="-1.05",
            )
        )

    subtitle_y = top_y + 42 + len(title_lines) * 34 + 8
    for index, line in enumerate(_wrap_text(subtitle, 34)[:2]):
        parts.append(
            _text(left_x + 6, subtitle_y + index * 18, line, fill=t["muted"], font_size="13", font_family=font_ui)
        )

    fact_y = top_y + 162
    fact_w = max(124.0, (left_w - 10) / max(len(facts[:2]), 1))
    for index, fact in enumerate(facts[:2]):
        fx = left_x + index * fact_w
        parts.append(_circle(fx + 16, fact_y, 12, fill=band_fill))
        parts.append(
            _render_icon(
                icon=fact.get("icon", ""),
                icon_name=fact.get("icon_name", ""),
                title=fact.get("label", ""),
                body=fact.get("value", ""),
                cx=fx + 16,
                cy=fact_y,
                size=10,
                color=t["muted"],
                font_family=font_ui,
            )
        )
        parts += [
            _text(fx + 36, fact_y - 3, fact.get("label", ""), fill=t["muted"], font_size="11", font_family=font_ui),
            _text(
                fx + 36,
                fact_y + 14,
                fact.get("value", ""),
                fill=t["text"],
                font_size="13",
                font_weight="600",
                font_family=font_display,
            ),
        ]

    gauge_cx = gauge_x + gauge_w / 2
    gauge_cy = top_y + 82
    gauge_r = 64
    progress = max(0.0, min(1.0, score / max_score if max_score else 0))
    gauge_color = _assessment_status_color(status or risk_label, t, t["palette"][0])
    parts += [
        _circle(gauge_cx, gauge_cy, gauge_r, fill="none", stroke=_alpha(border, 0.65), stroke_width="9"),
        _path(
            _arc_path(gauge_cx, gauge_cy, gauge_r, -132, -132 + 264 * progress),
            fill="none",
            stroke=gauge_color,
            stroke_width="9",
            stroke_linecap="round",
        ),
        _text(
            gauge_cx,
            top_y + 8,
            section.get("score_label", "OVERALL SCORE"),
            fill=t["muted"],
            font_size="11",
            font_weight="700",
            font_family=font_ui,
            text_anchor="middle",
            letter_spacing="0.4",
        ),
        _text(
            gauge_cx,
            gauge_cy + 10,
            f"{int(score)}",
            fill=t["text"],
            font_size="46",
            font_weight="760",
            font_family=font_display,
            text_anchor="middle",
        ),
        _text(
            gauge_cx + 38, gauge_cy + 10, f"/ {int(max_score)}", fill=t["muted"], font_size="17", font_family=font_ui
        ),
    ]
    if status:
        pill_w = max(72, len(status) * 6.9 + 22)
        parts += [
            _rect(gauge_cx - pill_w / 2, gauge_cy + 26, pill_w, 22, rx=11, fill=_alpha(gauge_color, 0.12)),
            _text(
                gauge_cx,
                gauge_cy + 41,
                status,
                fill=gauge_color,
                font_size="12",
                font_weight="700",
                font_family=font_ui,
                text_anchor="middle",
            ),
        ]
    for index, line in enumerate(_wrap_text(score_note, 24)[:2]):
        parts.append(
            _text(
                gauge_cx,
                top_y + 168 + index * 14,
                line,
                fill=t["muted"],
                font_size="11",
                font_family=font_ui,
                text_anchor="middle",
            )
        )

    summary_h = 176.0
    parts.append(_assessment_panel_shell(right_x, top_y + 2, right_w, summary_h, fill=panel_fill, border=border, rx=16))
    parts.append(
        _text(
            right_x + 14,
            top_y + 24,
            summary_title,
            fill=t["muted"],
            font_size="11",
            font_weight="700",
            font_family=font_ui,
            letter_spacing="0.4",
        )
    )
    for index, line in enumerate(risk_label_lines):
        parts.append(
            _text(
                right_x + 14,
                top_y + 68 + index * risk_label_line_gap,
                line,
                fill=summary_color,
                font_size=str(risk_label_font_size),
                font_weight="760",
                font_family=font_display,
            )
        )
    summary_body_y = top_y + 90 + max(0, len(risk_label_lines) - 1) * risk_label_line_gap
    for index, line in enumerate(_wrap_text(str(summary_body), 17)[:2]):
        parts.append(
            _text(right_x + 14, summary_body_y + index * 14, line, fill=t["muted"], font_size="11", font_family=font_ui)
        )
    stat_base_y = top_y + 128 + max(0, len(risk_label_lines) - 1) * risk_label_line_gap
    for index, stat in enumerate(summary_stats[:2]):
        sy = stat_base_y + index * 28
        if index > 0:
            parts.append(
                _line(right_x + 14, sy - 14, right_x + right_w - 14, sy - 14, stroke=divider, stroke_width="1")
            )
        parts += [
            _text(
                right_x + 14,
                sy,
                stat.get("label", ""),
                fill=t["muted"],
                font_size="11",
                font_weight="600",
                font_family=font_ui,
            ),
            _text(
                right_x + right_w - 14,
                sy,
                stat.get("value", ""),
                fill=t["text"],
                font_size="12.5",
                font_weight="700",
                font_family=font_display,
                text_anchor="end",
            ),
        ]

    cur_y = top_y + top_h

    if items:
        col_w = width / 2
        cell_h = 74.0
        rows = math.ceil(len(items) / 2)
        matrix_h = rows * cell_h
        parts.append(_assessment_panel_shell(x, cur_y, width, matrix_h, fill=panel_fill, border=border, rx=18))
        if len(items) > 1:
            parts.append(
                _line(x + col_w, cur_y + 10, x + col_w, cur_y + matrix_h - 10, stroke=divider, stroke_width="1")
            )
        for row in range(1, rows):
            py = cur_y + row * cell_h
            parts.append(_line(x + 14, py, x + width - 14, py, stroke=divider, stroke_width="1"))
        for index, item in enumerate(items):
            col = index % 2
            row = index // 2
            cell_x = x + col * col_w
            cell_y = cur_y + row * cell_h
            parts += [
                _text(
                    cell_x + 14,
                    cell_y + 24,
                    item["label"],
                    fill=t["text"],
                    font_size="15",
                    font_weight="700",
                    font_family=font_display,
                ),
                _text(
                    cell_x + col_w - 14,
                    cell_y + 25,
                    item["value"],
                    fill=item["color"],
                    font_size="22",
                    font_weight="760",
                    font_family=font_display,
                    text_anchor="end",
                ),
                _text(
                    cell_x + col_w - 14,
                    cell_y + 43,
                    item["status"],
                    fill=item["color"],
                    font_size="11.5",
                    font_weight="700",
                    font_family=font_ui,
                    text_anchor="end",
                ),
            ]
            for line_index, line in enumerate(_wrap_text(item["body"], 28)[:1]):
                parts.append(
                    _text(
                        cell_x + 14,
                        cell_y + 44 + line_index * 14,
                        line,
                        fill=t["muted"],
                        font_size="11",
                        font_family=font_ui,
                    )
                )
        cur_y += matrix_h + 10

    if insights or recommendation:
        left_panel_w = width * 0.49
        right_panel_w = width - left_panel_w - 12
        panel_h = 196.0
        panels_y = cur_y

        if insights:
            parts.append(
                _assessment_panel_shell(x, panels_y, left_panel_w, panel_h, fill=panel_fill, border=border, rx=18)
            )
            parts += [
                _text(
                    x + 18,
                    panels_y + 24,
                    section.get("insights_title", "Key Insights"),
                    fill=t["text"],
                    font_size="16",
                    font_weight="700",
                    font_family=font_display,
                ),
                _text(
                    x + 18,
                    panels_y + 40,
                    section.get("insights_subtitle", ""),
                    fill=t["muted"],
                    font_size="11",
                    font_family=font_ui,
                ),
            ]
            for index, item in enumerate(insights[:4]):
                iy = panels_y + 64 + index * 30
                if index > 0:
                    parts.append(
                        _line(x + 16, iy - 14, x + left_panel_w - 16, iy - 14, stroke=divider, stroke_width="1")
                    )
                parts.append(_circle(x + 22, iy - 4, 5, fill=item["color"]))
                parts.append(
                    _text(
                        x + 36,
                        iy,
                        item["title"],
                        fill=t["text"],
                        font_size="12.5",
                        font_weight="600",
                        font_family=font_display,
                    )
                )
                if item.get("body"):
                    for line_index, line in enumerate(_wrap_text(item["body"], 38)[:1]):
                        parts.append(
                            _text(
                                x + 36,
                                iy + 14 + line_index * 14,
                                line,
                                fill=t["muted"],
                                font_size="11",
                                font_family=font_ui,
                            )
                        )

        if recommendation:
            rx2 = x + left_panel_w + 12 if insights else x
            rw2 = right_panel_w if insights else width
            parts.append(_assessment_panel_shell(rx2, panels_y, rw2, panel_h, fill=panel_fill, border=border, rx=18))
            parts += [
                _text(
                    rx2 + 18,
                    panels_y + 24,
                    section.get("recommendation_title", "Recommendation"),
                    fill=t["text"],
                    font_size="16",
                    font_weight="700",
                    font_family=font_display,
                ),
                _text(
                    rx2 + 18,
                    panels_y + 40,
                    section.get("recommendation_subtitle", ""),
                    fill=t["muted"],
                    font_size="11",
                    font_family=font_ui,
                ),
            ]
            ill_cx = rx2 + rw2 - 64
            ill_cy = panels_y + 68
            parts.append(_circle(ill_cx, ill_cy, 30, fill=_alpha(t["palette"][1], 0.10)))
            for radius in (22, 15, 8):
                parts.append(
                    _circle(ill_cx, ill_cy, radius, fill="none", stroke=_alpha(t["palette"][1], 0.28), stroke_width="3")
                )
            parts.append(_render_named_icon("target", ill_cx, ill_cy, 24, t["palette"][0], stroke_width=1.7))
            rec_title_y = panels_y + 102
            for index, line in enumerate(_wrap_text(recommendation.get("title", ""), 28)[:2]):
                parts.append(
                    _text(
                        rx2 + 18,
                        rec_title_y + index * 22,
                        line,
                        fill=t["text"],
                        font_size="16",
                        font_weight="700",
                        font_family=font_display,
                    )
                )
            for index, line in enumerate(_wrap_text(recommendation.get("body", ""), 32)[:2]):
                parts.append(
                    _text(
                        rx2 + 18,
                        panels_y + 160 + index * 14,
                        line,
                        fill=t["muted"],
                        font_size="11",
                        font_family=font_ui,
                    )
                )

        cur_y += panel_h + 10

    if footer and any(footer.get(key) for key in ("title", "body", "note")):
        strip_h = 54.0
        parts.append(_assessment_panel_shell(x, cur_y, width, strip_h, fill=band_fill, border=border, rx=16))
        footer_icon = footer.get("icon_name", "trophy")
        parts.append(_circle(x + 24, cur_y + 27, 10, fill=_alpha(summary_color, 0.14)))
        parts.append(
            _render_icon(
                icon=None,
                icon_name=footer_icon,
                title=footer.get("title", ""),
                body="",
                cx=x + 24,
                cy=cur_y + 27,
                size=9,
                color=summary_color,
                font_family=font_ui,
            )
        )
        parts += [
            _text(
                x + 42,
                cur_y + 23,
                footer.get("title", ""),
                fill=t["text"],
                font_size="12.5",
                font_weight="700",
                font_family=font_display,
            ),
            _text(x + 42, cur_y + 38, footer.get("body", ""), fill=t["muted"], font_size="10.5", font_family=font_ui),
            _text(
                x + width - 18,
                cur_y + 31,
                footer.get("note", ""),
                fill=t["muted"],
                font_size="10.5",
                font_family=font_ui,
                text_anchor="end",
            ),
        ]
        cur_y += strip_h + 10

    if risk_drivers:
        divider_label = section.get("risk_drivers_title", "Key Risk Drivers")
        divider_svg, divider_h = _render_divider({"label": divider_label}, x, cur_y, width, t)
        parts.append(divider_svg)
        cur_y += divider_h + 2

        rows = min(len(risk_drivers), 5)
        box_h = rows * 29 + 20
        parts.append(_assessment_panel_shell(x, cur_y, width, box_h, fill=panel_fill, border=border, rx=16))
        for index, item in enumerate(risk_drivers[:5]):
            if not isinstance(item, dict):
                continue
            iy = cur_y + 20 + index * 29
            label = item.get("title") or item.get("label") or item.get("name") or ""
            value_raw = item.get("score", item.get("value", ""))
            value = _num(value_raw, 0.0)
            display_value = _assessment_value_text(value_raw)
            color = item.get("color") or _assessment_status_color(
                item.get("status", value_raw), t, t["palette"][index % len(t["palette"])]
            )
            parts += [
                _text(x + 14, iy, label, fill=t["text"], font_size="11.5", font_weight="600", font_family=font_display),
                _text(
                    x + width - 14,
                    iy,
                    display_value,
                    fill=color,
                    font_size="12.5",
                    font_weight="700",
                    font_family=font_display,
                    text_anchor="end",
                ),
                _rect(x + 14, iy + 8, width - 94, 4, rx=2, fill=_mix(t.get("paper_tint", t["bg"]), border, 0.35)),
                _rect(x + 14, iy + 8, (width - 94) * max(0.0, min(1.0, value / 100.0)), 4, rx=2, fill=color),
            ]
        cur_y += box_h + 10

    if tools:
        divider_svg, divider_h = _render_divider(
            {"label": section.get("tools_title", "AI Tools Already Doing It")}, x, cur_y, width, t
        )
        parts.append(divider_svg)
        cur_y += divider_h + 2

        cols = 6 if len(tools) <= 6 else 3
        rows = math.ceil(len(tools[:6]) / cols)
        cell_w = (width - (cols - 1) * 10) / cols
        cell_h = 48.0
        box_h = rows * cell_h + (rows - 1) * 10
        for index, item in enumerate(tools[:6]):
            col = index % cols
            row = index // cols
            tx = x + col * (cell_w + 10)
            ty = cur_y + row * (cell_h + 10)
            tool_name = (
                item if isinstance(item, str) else item.get("label") or item.get("name") or item.get("title") or ""
            )
            icon_name = item.get("icon_name", "spark") if isinstance(item, dict) else "spark"
            tool_color = item.get("color") if isinstance(item, dict) else None
            color = tool_color or t["palette"][index % len(t["palette"])]
            parts.append(_assessment_panel_shell(tx, ty, cell_w, cell_h, fill=panel_fill, border=border, rx=14))
            parts.append(_circle(tx + 18, ty + 24, 10, fill=_alpha(color, 0.12)))
            parts.append(
                _render_icon(
                    icon=None,
                    icon_name=icon_name,
                    title=tool_name,
                    body="",
                    cx=tx + 18,
                    cy=ty + 24,
                    size=8,
                    color=color,
                    font_family=font_ui,
                )
            )
            parts.append(
                _text(
                    tx + 34,
                    ty + 28,
                    tool_name,
                    fill=t["text"],
                    font_size="11.5",
                    font_weight="600",
                    font_family=font_display,
                )
            )
        cur_y += box_h + 10

    if summary_cards:
        cols = min(len(summary_cards[:3]), 3) or 1
        gap_w = 10.0
        card_w = (width - (cols - 1) * gap_w) / cols
        card_h = 68.0
        for index, item in enumerate(summary_cards[:3]):
            if not isinstance(item, dict):
                continue
            sx = x + index * (card_w + gap_w)
            value = item.get("value", "")
            label = item.get("label", "")
            accent = item.get("color") or _assessment_status_color(
                label or value, t, t["palette"][index % len(t["palette"])]
            )
            parts.append(_assessment_panel_shell(sx, cur_y, card_w, card_h, fill=panel_fill, border=border, rx=16))
            parts += [
                _text(
                    sx + 14,
                    cur_y + 24,
                    str(value),
                    fill=accent,
                    font_size="24",
                    font_weight="760",
                    font_family=font_display,
                ),
                _text(
                    sx + 14,
                    cur_y + 44,
                    label,
                    fill=t["muted"],
                    font_size="11.5",
                    font_weight="600",
                    font_family=font_ui,
                ),
            ]
        cur_y += card_h

    return "\n".join(parts), cur_y - y


def _render_assessment_scorecard_classic(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    badge = section.get("badge", "Assessment Scorecard")
    title = section.get("title", "AI Readiness Assessment")
    subtitle = section.get("subtitle", "")
    facts = section.get("facts", [])
    score = _num(section.get("score", 0))
    max_score = _num(section.get("max_score", 100), 100.0)
    status = section.get("status", "")
    score_note = section.get("score_note", "")
    delta = section.get("delta", "")
    delta_caption = section.get("delta_caption", "")
    percentile_label = section.get("percentile_label", "Percentile Rank")
    percentile_value = section.get("percentile_value", "")
    categories = section.get("categories", [])
    insights = section.get("insights", [])
    recommendation = section.get("recommendation", {})
    footer = section.get("footer", {})

    parts: list[str] = []
    cur_y = y

    badge_w = len(badge) * 8 + 42
    parts += [
        _rect(x + 20, cur_y + 8, badge_w, 38, rx=19, fill=t["card_bg"]),
        _rect(x + 20, cur_y + 8, badge_w, 38, rx=19, fill="none", stroke=t["card_border"], stroke_width="1"),
        _render_icon(
            icon=None,
            icon_name="spark",
            title=badge,
            body="",
            cx=x + 44,
            cy=cur_y + 27,
            size=14,
            color=t["palette"][2],
            font_family=t.get("font_ui", t["font"]),
        ),
        _text(
            x + 66,
            cur_y + 32,
            badge.upper(),
            fill=t["muted"],
            font_size="11",
            font_weight="600",
            font_family=t.get("font_ui", t["font"]),
            letter_spacing="0.6",
        ),
    ]

    left_w = width * 0.33
    mid_w = width * 0.37
    right_w = width - left_w - mid_w - 20
    top_h = 360.0
    left_x = x + 28
    mid_x = x + left_w + 26
    right_x = mid_x + mid_w + 18

    for i, line in enumerate(_wrap_text(title, 14)[:4]):
        parts.append(
            _text(
                left_x,
                cur_y + 110 + i * 56,
                line,
                fill=t["text"],
                font_size="44",
                font_weight="760",
                font_family=t.get("font_display", t["font"]),
                letter_spacing="-1.5",
            )
        )
    sub_y = cur_y + 110 + len(_wrap_text(title, 14)[:4]) * 56 + 10
    for i, line in enumerate(_wrap_text(subtitle, 31)[:3]):
        parts.append(
            _text(
                left_x, sub_y + i * 24, line, fill=t["muted"], font_size="16", font_family=t.get("font_ui", t["font"])
            )
        )

    fact_y = cur_y + top_h - 92
    fact_w = (left_w - 24) / max(len(facts[:2]), 1)
    for i, fact in enumerate(facts[:2]):
        fx = left_x + i * fact_w
        parts.append(_circle(fx + 18, fact_y + 18, 20, fill=t["card_bg"]))
        parts.append(_rect(fx, fact_y, fact_w - 14, 52, rx=12, fill="none", stroke=t["card_border"], stroke_width="0"))
        parts.append(
            _render_icon(
                icon=fact.get("icon", ""),
                icon_name=fact.get("icon_name", ""),
                title=fact.get("label", ""),
                body=fact.get("value", ""),
                cx=fx + 18,
                cy=fact_y + 18,
                size=18,
                color=t["muted"],
                font_family=t.get("font_ui", t["font"]),
            )
        )
        parts += [
            _text(
                fx + 40,
                fact_y + 8,
                fact.get("label", ""),
                fill=t["muted"],
                font_size="11",
                font_family=t.get("font_ui", t["font"]),
            ),
            _text(
                fx + 40,
                fact_y + 30,
                fact.get("value", ""),
                fill=t["text"],
                font_size="14",
                font_weight="600",
                font_family=t.get("font_display", t["font"]),
            ),
        ]

    gauge_cx = mid_x + mid_w / 2
    gauge_cy = cur_y + 170
    gauge_r = 124
    progress = max(0.0, min(1.0, score / max_score if max_score else 0))
    parts.append(
        _circle(gauge_cx, gauge_cy, gauge_r, fill="none", stroke=_alpha(t["card_border"], 0.5), stroke_width="18")
    )
    parts.append(
        _path(
            _arc_path(gauge_cx, gauge_cy, gauge_r, -130, -130 + 260 * progress),
            fill="none",
            stroke=_mix("#B9F6D1", t["palette"][0], 0.55),
            stroke_width="18",
            stroke_linecap="round",
        )
    )
    parts += [
        _text(
            gauge_cx,
            cur_y + 118,
            "OVERALL SCORE",
            fill=t["muted"],
            font_size="12",
            font_weight="600",
            font_family=t.get("font_ui", t["font"]),
            text_anchor="middle",
        ),
        _text(
            gauge_cx,
            gauge_cy + 18,
            f"{int(score)}",
            fill=t["text"],
            font_size="88",
            font_weight="760",
            font_family=t.get("font_display", t["font"]),
            text_anchor="middle",
        ),
        _text(
            gauge_cx + 74,
            gauge_cy + 18,
            f"/ {int(max_score)}",
            fill=t["muted"],
            font_size="28",
            font_family=t.get("font_ui", t["font"]),
        ),
    ]
    if status:
        pill_w = max(92, len(status) * 8 + 26)
        parts += [
            _rect(gauge_cx - pill_w / 2, gauge_cy + 42, pill_w, 32, rx=16, fill=_mix("#FFFFFF", t["palette"][0], 0.10)),
            _text(
                gauge_cx,
                gauge_cy + 63,
                status,
                fill=t["palette"][0],
                font_size="14",
                font_weight="700",
                font_family=t.get("font_ui", t["font"]),
                text_anchor="middle",
            ),
        ]
    if score_note:
        for i, line in enumerate(_wrap_text(score_note, 28)[:2]):
            parts.append(
                _text(
                    gauge_cx,
                    cur_y + 322 + i * 18,
                    line,
                    fill=t["muted"],
                    font_size="12",
                    font_family=t.get("font_ui", t["font"]),
                    text_anchor="middle",
                )
            )

    parts.append(_group(_rect(right_x, cur_y + 34, right_w, 264, rx=22, fill=t["card_bg"]), filter="url(#g_shadow)"))
    parts.append(
        _rect(right_x, cur_y + 34, right_w, 264, rx=22, fill="none", stroke=t["card_border"], stroke_width="1")
    )
    parts.append(_circle(right_x + 56, cur_y + 88, 28, fill=_mix("#FFFFFF", t["palette"][0], 0.10)))
    parts.append(
        _render_icon(
            icon=None,
            icon_name="spark",
            title=delta,
            body="",
            cx=right_x + 56,
            cy=cur_y + 88,
            size=18,
            color=t["palette"][0],
            font_family=t.get("font_ui", t["font"]),
        )
    )
    parts.append(
        _text(
            right_x + 28,
            cur_y + 172,
            str(delta),
            fill=t["palette"][0],
            font_size="36",
            font_weight="760",
            font_family=t.get("font_display", t["font"]),
        )
    )
    for i, line in enumerate(_wrap_text(delta_caption, 18)[:2]):
        parts.append(
            _text(
                right_x + 28,
                cur_y + 198 + i * 18,
                line,
                fill=t["muted"],
                font_size="12",
                font_family=t.get("font_ui", t["font"]),
            )
        )
    parts.append(
        _line(right_x + 24, cur_y + 240, right_x + right_w - 24, cur_y + 240, stroke=t["card_border"], stroke_width="1")
    )
    parts += [
        _text(
            right_x + 28,
            cur_y + 286,
            percentile_label,
            fill=t["muted"],
            font_size="12",
            font_family=t.get("font_ui", t["font"]),
        ),
        _text(
            right_x + 28,
            cur_y + 316,
            percentile_value,
            fill=t["text"],
            font_size="22",
            font_weight="700",
            font_family=t.get("font_display", t["font"]),
        ),
    ]

    cur_y += top_h + 20
    cat_h = 422.0
    parts.append(_group(_rect(x, cur_y, width, cat_h, rx=24, fill=t["card_bg"]), filter="url(#g_shadow)"))
    parts.append(_rect(x, cur_y, width, cat_h, rx=24, fill="none", stroke=t["card_border"], stroke_width="1"))
    col_w = width / 2
    for i, item in enumerate(categories[:6]):
        col = i % 2
        row = i // 2
        cx2 = x + col * col_w
        cy2 = cur_y + row * 126
        if row > 0:
            parts.append(_line(cx2 + 24, cy2, cx2 + col_w - 24, cy2, stroke=t["card_border"], stroke_width="1"))
        if col == 1:
            parts.append(_line(cx2, cy2 + 20, cx2, cy2 + 106, stroke=t["card_border"], stroke_width="1"))
        color = item.get("color") or t["palette"][i % len(t["palette"])]
        parts.append(_circle(cx2 + 40, cy2 + 62, 28, fill=_mix("#FFFFFF", color, 0.12)))
        parts.append(
            _render_icon(
                icon=item.get("icon", ""),
                icon_name=item.get("icon_name", ""),
                title=item.get("title", ""),
                body=item.get("body", ""),
                cx=cx2 + 40,
                cy=cy2 + 62,
                size=22,
                color=color,
                font_family=t.get("font_ui", t["font"]),
            )
        )
        parts += [
            _text(
                cx2 + 92,
                cy2 + 38,
                item.get("title", ""),
                fill=t["text"],
                font_size="14",
                font_weight="700",
                font_family=t.get("font_display", t["font"]),
            ),
            _text(
                cx2 + col_w - 48,
                cy2 + 62,
                str(item.get("value", "")),
                fill=color,
                font_size="18",
                font_weight="700",
                font_family=t.get("font_display", t["font"]),
                text_anchor="end",
            ),
            _text(
                cx2 + col_w - 48,
                cy2 + 88,
                item.get("status", ""),
                fill=t["muted"],
                font_size="11.5",
                font_family=t.get("font_ui", t["font"]),
                text_anchor="end",
            ),
        ]
        for li, line in enumerate(_wrap_text(item.get("body", ""), 34)[:2]):
            parts.append(
                _text(
                    cx2 + 92,
                    cy2 + 62 + li * 18,
                    line,
                    fill=t["muted"],
                    font_size="11.5",
                    font_family=t.get("font_ui", t["font"]),
                )
            )
        parts += [
            _rect(cx2 + 92, cy2 + 98, col_w - 210, 6, rx=3, fill=_mix(t["paper_tint"], t["card_border"], 0.45)),
            _rect(
                cx2 + 92,
                cy2 + 98,
                (col_w - 210) * max(0.0, min(1.0, _num(item.get("value", 0)) / 100.0)),
                6,
                rx=3,
                fill=f"url(#g_bar_{i % len(t['palette'])})",
            ),
        ]
        parts.append(_render_named_icon("arrow-right", cx2 + col_w - 20, cy2 + 62, 12, t["muted"], stroke_width=1.6))

    cur_y += cat_h + 24
    left_w2 = width * 0.49
    right_w2 = width - left_w2 - 14
    card_h = 442.0

    parts.append(_group(_rect(x, cur_y, left_w2, card_h, rx=24, fill=t["card_bg"]), filter="url(#g_shadow)"))
    parts.append(_rect(x, cur_y, left_w2, card_h, rx=24, fill="none", stroke=t["card_border"], stroke_width="1"))
    parts.append(
        _text(
            x + 66,
            cur_y + 48,
            "Key Insights",
            fill=t["text"],
            font_size="18",
            font_weight="700",
            font_family=t.get("font_display", t["font"]),
        )
    )
    parts.append(_circle(x + 36, cur_y + 44, 16, fill=_mix("#FFFFFF", t["palette"][1], 0.10)))
    parts.append(
        _render_icon(
            icon=None,
            icon_name="lightbulb",
            title="Key Insights",
            body="",
            cx=x + 36,
            cy=cur_y + 44,
            size=14,
            color=t["palette"][2],
            font_family=t.get("font_ui", t["font"]),
        )
    )
    for i, item in enumerate(insights[:4]):
        iy = cur_y + 104 + i * 86
        color = item.get("color") or t["palette"][i % len(t["palette"])]
        if i > 0:
            parts.append(_line(x + 28, iy - 28, x + left_w2 - 28, iy - 28, stroke=t["card_border"], stroke_width="1"))
        parts.append(_circle(x + 56, iy, 20, fill=_mix("#FFFFFF", color, 0.16)))
        parts.append(
            _render_icon(
                icon=item.get("icon", ""),
                icon_name=item.get("icon_name", ""),
                title=item.get("title", ""),
                body=item.get("body", ""),
                cx=x + 56,
                cy=iy,
                size=16,
                color=color,
                font_family=t.get("font_ui", t["font"]),
            )
        )
        parts += [
            _text(
                x + 96,
                iy - 6,
                item.get("title", ""),
                fill=t["text"],
                font_size="13.5",
                font_weight="600",
                font_family=t.get("font_display", t["font"]),
            ),
        ]
        for li, line in enumerate(_wrap_text(item.get("body", ""), 42)[:2]):
            parts.append(
                _text(
                    x + 96,
                    iy + 18 + li * 18,
                    line,
                    fill=t["muted"],
                    font_size="11.5",
                    font_family=t.get("font_ui", t["font"]),
                )
            )
    parts.append(
        _text(
            x + 34,
            cur_y + card_h - 28,
            section.get("insights_cta", "View detailed analysis"),
            fill=t["text"],
            font_size="12",
            font_weight="500",
            font_family=t.get("font_ui", t["font"]),
        )
    )
    parts.append(_render_named_icon("arrow-right", x + 172, cur_y + card_h - 34, 14, t["muted"], stroke_width=1.6))

    rx2 = x + left_w2 + 14
    parts.append(_group(_rect(rx2, cur_y, right_w2, card_h, rx=24, fill=t["card_bg"]), filter="url(#g_shadow)"))
    parts.append(_rect(rx2, cur_y, right_w2, card_h, rx=24, fill="none", stroke=t["card_border"], stroke_width="1"))
    parts.append(
        _text(
            rx2 + 66,
            cur_y + 48,
            "Recommendation",
            fill=t["text"],
            font_size="18",
            font_weight="700",
            font_family=t.get("font_display", t["font"]),
        )
    )
    parts.append(_circle(rx2 + 36, cur_y + 44, 16, fill=_mix("#FFFFFF", t["palette"][2], 0.10)))
    parts.append(
        _render_icon(
            icon=None,
            icon_name="spark",
            title="Recommendation",
            body="",
            cx=rx2 + 36,
            cy=cur_y + 44,
            size=14,
            color=t["palette"][2],
            font_family=t.get("font_ui", t["font"]),
        )
    )
    illo_x = rx2 + 44
    illo_y = cur_y + 82
    illo_w = right_w2 - 88
    illo_h = 168
    parts.append(_rect(illo_x, illo_y, illo_w, illo_h, rx=34, fill=_mix("#FFFFFF", t["palette"][1], 0.06)))
    parts.append(_circle(illo_x + illo_w * 0.62, illo_y + 84, 72, fill=_alpha(t["palette"][1], 0.12)))
    for rr in (58, 40, 22):
        parts.append(
            _circle(
                illo_x + illo_w * 0.62,
                illo_y + 84,
                rr,
                fill="none",
                stroke=_alpha(t["palette"][1], 0.35),
                stroke_width="10" if rr == 58 else "8",
            )
        )
    parts.append(
        _render_named_icon("target", illo_x + illo_w * 0.62, illo_y + 84, 62, t["palette"][0], stroke_width=1.8)
    )
    rec = recommendation or {}
    for i, line in enumerate(_wrap_text(rec.get("title", ""), 30)[:2]):
        parts.append(
            _text(
                rx2 + 54,
                cur_y + 296 + i * 42,
                line,
                fill=t["text"],
                font_size="22",
                font_weight="700",
                font_family=t.get("font_display", t["font"]),
            )
        )
    for i, line in enumerate(_wrap_text(rec.get("body", ""), 40)[:3]):
        parts.append(
            _text(
                rx2 + 54,
                cur_y + 380 + i * 18,
                line,
                fill=t["muted"],
                font_size="12.5",
                font_family=t.get("font_ui", t["font"]),
            )
        )
    parts.append(
        _text(
            rx2 + 34,
            cur_y + card_h - 28,
            section.get("recommendation_cta", "View recommendations"),
            fill=t["text"],
            font_size="12",
            font_weight="500",
            font_family=t.get("font_ui", t["font"]),
        )
    )
    parts.append(_render_named_icon("arrow-right", rx2 + 190, cur_y + card_h - 34, 14, t["muted"], stroke_width=1.6))

    cur_y += card_h + 22
    footer_h = 90.0
    parts.append(_group(_rect(x, cur_y, width, footer_h, rx=22, fill=t["card_bg"]), filter="url(#g_shadow)"))
    parts.append(_rect(x, cur_y, width, footer_h, rx=22, fill="none", stroke=t["card_border"], stroke_width="1"))
    footer_icon = footer.get("icon_name", "trophy")
    parts.append(_circle(x + 40, cur_y + 45, 20, fill=_mix("#FFFFFF", t["palette"][0], 0.10)))
    parts.append(
        _render_icon(
            icon=None,
            icon_name=footer_icon,
            title=footer.get("title", ""),
            body="",
            cx=x + 40,
            cy=cur_y + 45,
            size=16,
            color=t["palette"][0],
            font_family=t.get("font_ui", t["font"]),
        )
    )
    parts += [
        _text(
            x + 74,
            cur_y + 40,
            footer.get("title", ""),
            fill=t["text"],
            font_size="15",
            font_weight="600",
            font_family=t.get("font_display", t["font"]),
        ),
        _text(
            x + 74,
            cur_y + 64,
            footer.get("body", ""),
            fill=t["muted"],
            font_size="12",
            font_family=t.get("font_ui", t["font"]),
        ),
        _text(
            x + width - 220,
            cur_y + 58,
            footer.get("note", ""),
            fill=t["muted"],
            font_size="12",
            font_family=t.get("font_ui", t["font"]),
        ),
    ]
    parts.append(_circle(x + width - 34, cur_y + 45, 18, fill=_mix("#FFFFFF", t["card_border"], 0.25)))
    parts.append(
        _render_icon(
            icon=None,
            icon_name="calendar",
            title="calendar",
            body="",
            cx=x + width - 34,
            cy=cur_y + 45,
            size=14,
            color=t["muted"],
            font_family=t.get("font_ui", t["font"]),
        )
    )

    return "\n".join(parts), cur_y + footer_h - y


def _render_assessment_scorecard(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    if section.get("layout") == "classic":
        return _render_assessment_scorecard_classic(section, x, y, width, t)
    return _render_assessment_scorecard_certificate(section, x, y, width, t)


def _showcase_card_shell(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    bg: str,
    border: str,
    shadow: str = "url(#g_shadow_soft)",
) -> str:
    return "".join(
        [
            _group(_rect(x, y, w, h, rx=22, fill=bg), filter=shadow),
            _rect(x, y, w, h, rx=22, fill="none", stroke=border, stroke_width="1"),
        ]
    )


def _showcase_mini_line_chart(
    x: float,
    y: float,
    w: float,
    h: float,
    series: list[object],
    *,
    line_color: str,
    area_color: str,
    grid_color: str,
    badge: str = "",
    x_labels: list[str] | None = None,
    font_ui: str,
    muted: str,
    badge_fill: str | None = None,
) -> str:
    values = [_num(v, 0.0) for v in series]
    if not values:
        return ""

    max_val = max(values) or 1
    points: list[tuple[float, float]] = []
    for i, val in enumerate(values):
        px = x + i * (w / max(len(values) - 1, 1))
        py = y + h - (val / max_val) * (h - 12)
        points.append((px, py))

    parts: list[str] = []
    for i in range(4):
        gy = y + h - i * (h / 3)
        parts.append(_line(x, gy, x + w, gy, stroke=grid_color, stroke_width="1"))

    area_path = f"M {points[0][0]:.1f} {y + h:.1f} L " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in points)
    area_path += f" L {points[-1][0]:.1f} {y + h:.1f} Z"
    line_path = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in points)
    parts.append(_path(area_path, fill=area_color))
    parts.append(_path(line_path, fill="none", stroke=line_color, stroke_width="2.5"))
    for px, py in points:
        parts += [
            _circle(px, py, 3.5, fill="white"),
            _circle(px, py, 3.5, fill="none", stroke=line_color, stroke_width="1.6"),
        ]

    if badge:
        bx, by = points[-1]
        bw = max(54, len(badge) * 7 + 18)
        parts += [
            _rect(bx - bw / 2, by - 28, bw, 20, rx=10, fill=badge_fill or line_color),
            _text(
                bx,
                by - 14,
                badge,
                fill="white",
                font_size="10",
                font_weight="700",
                font_family=font_ui,
                text_anchor="middle",
            ),
        ]

    if x_labels:
        for i, label in enumerate(x_labels[: len(points)]):
            lx = x + i * (w / max(len(points) - 1, 1))
            parts.append(
                _text(lx, y + h + 18, label, fill=muted, font_size="10", font_family=font_ui, text_anchor="middle")
            )

    return "".join(parts)


def _showcase_progress_ring(
    cx: float,
    cy: float,
    r: float,
    pct: float,
    *,
    color: str,
    track: str,
    thickness: float,
    value: str,
    sub: str = "",
    font_display: str,
    font_ui: str,
    text_color: str,
    muted: str,
) -> str:
    pct = max(0.0, min(1.0, pct))
    parts = [
        _circle(cx, cy, r, fill="none", stroke=track, stroke_width=str(thickness)),
        _path(
            _arc_path(cx, cy, r, -130, -130 + 260 * pct),
            fill="none",
            stroke=color,
            stroke_width=str(thickness),
            stroke_linecap="round",
        ),
        _text(
            cx,
            cy + 10,
            value,
            fill=text_color,
            font_size=str(int(r * 0.82)),
            font_weight="760",
            font_family=font_display,
            text_anchor="middle",
        ),
    ]
    if sub:
        parts.append(
            _text(cx, cy + r * 0.54, sub, fill=muted, font_size="12", font_family=font_ui, text_anchor="middle")
        )
    return "".join(parts)


def _showcase_simple_donut(
    cx: float,
    cy: float,
    r_out: float,
    r_in: float,
    data: list[dict],
    *,
    track: str,
) -> str:
    total = sum(_num(item.get("value", 0), 0.0) for item in data) or 1
    angle = 0.0
    parts = [_circle(cx, cy, r_out, fill="none", stroke=track, stroke_width="1")]
    for item in data:
        sweep = (_num(item.get("value", 0), 0.0) / total) * 360
        color = item.get("color", "#5E92EA")
        parts.append(_path(_donut_segment(cx, cy, r_out, r_in, angle, angle + max(sweep - 1.2, 1.2)), fill=color))
        angle += sweep
    return "".join(parts)


def _render_showcase_business_performance_card(card: dict, x: float, y: float, w: float, h: float, t: dict) -> str:
    parts = [
        _showcase_card_shell(x, y, w, h, bg="#0A1450", border=_alpha("#7C8DFF", 0.16), shadow="url(#g_shadow_soft)"),
        _circle(x + w * 0.18, y + h - 34, 140, fill=_alpha("#6C4CFF", 0.34), filter="url(#g_blur_blob)"),
        _circle(x + w * 0.74, y + h * 0.12, 90, fill=_alpha("#45D4FF", 0.14), filter="url(#g_blur_blob)"),
    ]
    font_display = t.get("font_display", t["font"])
    font_ui = t.get("font_ui", t["font"])
    title = card.get("title", "Q2 Business Performance")
    subtitle = card.get("subtitle", "")
    for i, line in enumerate(_wrap_text(title, 13)[:3]):
        parts.append(
            _text(
                x + 28,
                y + 58 + i * 44,
                line,
                fill="white",
                font_size="30",
                font_weight="760",
                font_family=font_display,
                letter_spacing="-1.2",
            )
        )
    if subtitle:
        parts.append(_text(x + 28, y + 148, subtitle, fill=_alpha("#FFFFFF", 0.8), font_size="14", font_family=font_ui))

    overall = card.get("overall", {})
    obx, oby, obw, obh = x + w - 154, y + 24, 132, 108
    parts += [
        _rect(obx, oby, obw, obh, rx=18, fill=_alpha("#2032A4", 0.72)),
        _rect(obx, oby, obw, obh, rx=18, fill="none", stroke=_alpha("#7AA3FF", 0.22), stroke_width="1"),
        _text(
            obx + 18,
            oby + 22,
            overall.get("label", "Overall Performance"),
            fill=_alpha("#FFFFFF", 0.88),
            font_size="11",
            font_weight="600",
            font_family=font_ui,
        ),
        _text(
            obx + obw / 2,
            oby + 66,
            overall.get("value", "87%"),
            fill="white",
            font_size="34",
            font_weight="760",
            font_family=font_display,
            text_anchor="middle",
        ),
        _text(
            obx + obw / 2,
            oby + 88,
            overall.get("status", "Excellent"),
            fill="white",
            font_size="14",
            font_weight="600",
            font_family=font_ui,
            text_anchor="middle",
        ),
        _showcase_mini_line_chart(
            obx + 18,
            oby + 86,
            obw - 22,
            16,
            [2, 3, 3, 4, 4, 3, 5, 5, 7],
            line_color="#5DE2FF",
            area_color=_alpha("#5DE2FF", 0.10),
            grid_color="none",
            font_ui=font_ui,
            muted="#AFC3FF",
        ),
    ]

    stats = card.get("stats", [])
    strip_x, strip_y, strip_h = x + 20, y + 156, 122
    parts += [
        _group(_rect(strip_x, strip_y, w - 40, strip_h, rx=18, fill="white"), filter="url(#g_shadow)"),
        _rect(strip_x, strip_y, w - 40, strip_h, rx=18, fill="none", stroke=_alpha("#DBE4FF", 0.9), stroke_width="1"),
    ]
    stat_w = (w - 40) / max(len(stats[:4]), 1)
    icon_colors = ["#7A49F3", "#2E6BF5", "#1FBF6B", "#FF962E"]
    for i, stat in enumerate(stats[:4]):
        sx = strip_x + i * stat_w
        if i > 0:
            parts.append(_line(sx, strip_y + 18, sx, strip_y + strip_h - 18, stroke="#E7ECF9", stroke_width="1"))
        color = stat.get("color") or icon_colors[i % len(icon_colors)]
        parts += [
            _circle(sx + 54, strip_y + 38, 18, fill=color),
            _render_icon(
                icon=stat.get("icon", ""),
                icon_name=stat.get("icon_name", ""),
                title=stat.get("label", ""),
                body="",
                cx=sx + 54,
                cy=strip_y + 38,
                size=16,
                color="white",
                font_family=font_ui,
            ),
            _text(
                sx + 34,
                strip_y + 74,
                stat.get("label", ""),
                fill="#1B2340",
                font_size="11",
                font_weight="600",
                font_family=font_ui,
            ),
            _text(
                sx + 34,
                strip_y + 98,
                str(stat.get("value", "")),
                fill="#17213F",
                font_size="18",
                font_weight="760",
                font_family=font_display,
            ),
            _text(
                sx + 34,
                strip_y + 118,
                stat.get("change", ""),
                fill=color,
                font_size="10.5",
                font_weight="600",
                font_family=font_ui,
            ),
        ]

    box_y = y + 292
    box_h = 162
    trend_w = (w - 52) * 0.56
    channel_w = w - 52 - trend_w
    trend_x = x + 20
    channel_x = trend_x + trend_w + 12
    parts += [
        _group(_rect(trend_x, box_y, trend_w, box_h, rx=18, fill="white"), filter="url(#g_shadow)"),
        _group(_rect(channel_x, box_y, channel_w, box_h, rx=18, fill="white"), filter="url(#g_shadow)"),
        _text(
            trend_x + 18,
            box_y + 24,
            card.get("trend", {}).get("title", "Revenue Trend"),
            fill="#1B2340",
            font_size="13",
            font_weight="700",
            font_family=font_display,
        ),
        _text(
            channel_x + 18,
            box_y + 24,
            card.get("channels", {}).get("title", "Top Performing Channels"),
            fill="#1B2340",
            font_size="13",
            font_weight="700",
            font_family=font_display,
        ),
    ]
    parts.append(
        _showcase_mini_line_chart(
            trend_x + 30,
            box_y + 56,
            trend_w - 50,
            78,
            card.get("trend", {}).get("series", [5, 7, 7, 9, 8.5, 10.5]),
            line_color="#8D55FF",
            area_color=_alpha("#8D55FF", 0.12),
            grid_color="#EEF1FA",
            badge=card.get("trend", {}).get("badge", "$12.8M"),
            x_labels=card.get("trend", {}).get("x_labels", ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]),
            font_ui=font_ui,
            muted="#7A83A4",
            badge_fill="#8D55FF",
        )
    )
    channel_data = card.get("channels", {}).get("data", [])
    parts.append(
        _showcase_simple_donut(
            channel_x + 72,
            box_y + 86,
            34,
            16,
            channel_data
            or [
                {"label": "Web", "value": 42, "color": "#5E5BFF"},
                {"label": "Mobile", "value": 28, "color": "#4BA8FF"},
                {"label": "Email", "value": 18, "color": "#30C975"},
                {"label": "Social", "value": 12, "color": "#7D4BFF"},
            ],
            track="#EEF1FA",
        )
    )
    for i, item in enumerate(
        (
            channel_data
            or [
                {"label": "Web", "value": 42, "color": "#5E5BFF"},
                {"label": "Mobile", "value": 28, "color": "#4BA8FF"},
                {"label": "Email", "value": 18, "color": "#30C975"},
                {"label": "Social", "value": 12, "color": "#7D4BFF"},
            ]
        )[:4]
    ):
        ly = box_y + 58 + i * 24
        color = item.get("color", icon_colors[i % len(icon_colors)])
        parts += [
            _circle(channel_x + 128, ly - 4, 4, fill=color),
            _text(channel_x + 140, ly, item.get("label", ""), fill="#1B2340", font_size="10.5", font_family=font_ui),
            _text(
                channel_x + channel_w - 18,
                ly,
                f"{item.get('value', '')}%",
                fill="#1B2340",
                font_size="10.5",
                font_weight="600",
                font_family=font_ui,
                text_anchor="end",
            ),
        ]

    takeaway = card.get("takeaway", {})
    next_steps = card.get("next_steps", {})
    bottom_y = y + h - 118
    left_box_w = (w - 52) / 2
    parts += [
        _group(_rect(x + 20, bottom_y, left_box_w, 94, rx=18, fill=_alpha("#5C5BFF", 0.68)), filter="url(#g_shadow)"),
        _group(
            _rect(x + 32 + left_box_w, bottom_y, left_box_w, 94, rx=18, fill=_alpha("#3C4DFF", 0.56)),
            filter="url(#g_shadow)",
        ),
        _text(
            x + 38,
            bottom_y + 24,
            takeaway.get("title", "Key Takeaway"),
            fill="#FFD78A",
            font_size="12",
            font_weight="700",
            font_family=font_ui,
        ),
    ]
    for i, line in enumerate(
        _wrap_text(
            takeaway.get(
                "body", "Strong growth across all major metrics driven by increased demand and optimized campaigns."
            ),
            28,
        )[:3]
    ):
        parts.append(_text(x + 38, bottom_y + 48 + i * 17, line, fill="white", font_size="11", font_family=font_ui))
    parts.append(
        _render_named_icon("arrow-right", x + 20 + left_box_w - 22, bottom_y + 76, 16, "white", stroke_width=1.8)
    )
    parts.append(
        _text(
            x + 50 + left_box_w,
            bottom_y + 24,
            next_steps.get("title", "Next Steps"),
            fill="#C7D7FF",
            font_size="12",
            font_weight="700",
            font_family=font_ui,
        )
    )
    for i, item in enumerate(
        next_steps.get(
            "items", ["Invest in high-performing channels", "Optimize customer retention", "Expand product offerings"]
        )[:3]
    ):
        yy = bottom_y + 48 + i * 18
        parts += [
            _circle(x + 50 + left_box_w, yy - 3, 5, fill="none", stroke="#A9C8FF", stroke_width="1.5"),
            _text(x + 64 + left_box_w, yy, item, fill="white", font_size="11", font_family=font_ui),
        ]
    return "".join(parts)


def _render_showcase_sustainability_impact_card(card: dict, x: float, y: float, w: float, h: float, t: dict) -> str:
    font_display = t.get("font_display", t["font"])
    font_ui = t.get("font_ui", t["font"])
    parts = [
        _showcase_card_shell(x, y, w, h, bg="#FDFEFD", border="#E7F0EA"),
        _circle(x + w - 84, y + 88, 100, fill=_alpha("#77D6E8", 0.18), filter="url(#g_blur_blob)"),
    ]
    title = card.get("title", "Sustainability Impact Report 2024")
    for i, line in enumerate(_wrap_text(title, 16)[:3]):
        parts.append(
            _text(
                x + 28,
                y + 58 + i * 42,
                line,
                fill="#17354B",
                font_size="30",
                font_weight="760",
                font_family=font_display,
                letter_spacing="-1.1",
            )
        )
    for i, line in enumerate(_wrap_text(card.get("subtitle", ""), 22)[:2]):
        parts.append(_text(x + 28, y + 126 + i * 22, line, fill="#53697B", font_size="14", font_family=font_ui))
    ill_x, ill_y, ill_w, ill_h = x + w * 0.46, y + 20, w * 0.50, 212
    parts += [
        _rect(ill_x, ill_y, ill_w, ill_h, rx=22, fill=_mix("#FFFFFF", "#B8F2F8", 0.16)),
        _path(
            f"M {ill_x:.1f} {ill_y + ill_h - 44:.1f} C {ill_x + 70:.1f} {ill_y + 128:.1f} {ill_x + 110:.1f} {ill_y + ill_h - 10:.1f} {ill_x + 188:.1f} {ill_y + 138:.1f} S {ill_x + 290:.1f} {ill_y + 122:.1f} {ill_x + ill_w:.1f} {ill_y + ill_h - 50:.1f} L {ill_x + ill_w:.1f} {ill_y + ill_h:.1f} L {ill_x:.1f} {ill_y + ill_h:.1f} Z",
            fill="#A8DD6A",
        ),
        _path(
            f"M {ill_x:.1f} {ill_y + ill_h - 26:.1f} C {ill_x + 90:.1f} {ill_y + 148:.1f} {ill_x + 170:.1f} {ill_y + 196:.1f} {ill_x + 256:.1f} {ill_y + 154:.1f} S {ill_x + 320:.1f} {ill_y + 170:.1f} {ill_x + ill_w:.1f} {ill_y + ill_h - 18:.1f} L {ill_x + ill_w:.1f} {ill_y + ill_h:.1f} L {ill_x:.1f} {ill_y + ill_h:.1f} Z",
            fill="#55B85C",
        ),
    ]
    for tx in (ill_x + 92, ill_x + 166):
        parts.append(_line(tx, ill_y + 96, tx, ill_y + 164, stroke="#A7C7D7", stroke_width="2"))
        parts.append(
            _path(
                f"M {tx:.1f} {ill_y + 96:.1f} L {tx - 20:.1f} {ill_y + 112:.1f} L {tx:.1f} {ill_y + 107:.1f} L {tx + 20:.1f} {ill_y + 112:.1f} Z",
                fill="#CFE5EE",
            )
        )
    parts.append(_circle(ill_x + ill_w - 56, ill_y + 82, 34, fill=_alpha("#8ED14D", 0.22), filter="url(#g_shadow)"))
    parts.append(_render_named_icon("tree", ill_x + ill_w - 56, ill_y + 82, 48, "#69B74A", stroke_width=1.8))

    stats = card.get("stats", [])
    strip_y = y + 194
    parts += [
        _group(_rect(x + 14, strip_y, w - 28, 112, rx=18, fill="#0D5A49"), filter="url(#g_shadow_soft)"),
        _rect(x + 14, strip_y, w - 28, 112, rx=18, fill="none", stroke=_alpha("#49C89D", 0.18), stroke_width="1"),
    ]
    stat_w = (w - 28) / max(len(stats[:4]), 1)
    stat_colors = ["#B3FF81", "#79D6FF", "#C69BFF", "#FFB14D"]
    for i, stat in enumerate(stats[:4]):
        sx = x + 14 + i * stat_w
        color = stat.get("color") or stat_colors[i % len(stat_colors)]
        if i > 0:
            parts.append(_line(sx, strip_y + 18, sx, strip_y + 94, stroke=_alpha("#FFFFFF", 0.14), stroke_width="1"))
        parts += [
            _circle(sx + 52, strip_y + 32, 16, fill=_alpha("#FFFFFF", 0.10)),
            _render_icon(
                icon=stat.get("icon", ""),
                icon_name=stat.get("icon_name", ""),
                title=stat.get("label", ""),
                body="",
                cx=sx + 52,
                cy=strip_y + 32,
                size=14,
                color=color,
                font_family=font_ui,
            ),
            _text(
                sx + 26,
                strip_y + 70,
                str(stat.get("value", "")),
                fill="white",
                font_size="18",
                font_weight="760",
                font_family=font_display,
            ),
            _text(
                sx + 26,
                strip_y + 90,
                stat.get("label", ""),
                fill=_alpha("#FFFFFF", 0.85),
                font_size="10.5",
                font_family=font_ui,
            ),
            _text(sx + 26, strip_y + 108, stat.get("change", ""), fill=color, font_size="10", font_family=font_ui),
        ]

    metric = card.get("metric", {})
    chart_y = y + 326
    parts += [
        _group(_rect(x + 20, chart_y, w - 40, 148, rx=18, fill="white"), filter="url(#g_shadow)"),
        _text(
            x + 34,
            chart_y + 30,
            metric.get("title", "Carbon Footprint Reduced"),
            fill="#17354B",
            font_size="13.5",
            font_weight="700",
            font_family=font_display,
        ),
        _text(
            x + 34,
            chart_y + 64,
            str(metric.get("value", "19,876")),
            fill="#1D8A50",
            font_size="28",
            font_weight="760",
            font_family=font_display,
        ),
        _text(
            x + 34,
            chart_y + 86,
            metric.get("subtitle", "Metric tons of CO2 equivalent"),
            fill="#5D7081",
            font_size="11",
            font_family=font_ui,
        ),
        _text(
            x + 34,
            chart_y + 106,
            metric.get("change", "+19% vs 2023"),
            fill="#2AAA62",
            font_size="11",
            font_weight="600",
            font_family=font_ui,
        ),
    ]
    parts.append(
        _showcase_mini_line_chart(
            x + w * 0.46,
            chart_y + 34,
            w * 0.42,
            86,
            metric.get("series", [6, 10, 13, 16, 20]),
            line_color="#29B34E",
            area_color=_alpha("#29B34E", 0.12),
            grid_color="#EDF3ED",
            x_labels=metric.get("x_labels", ["2020", "2021", "2022", "2023", "2024"]),
            font_ui=font_ui,
            muted="#6E7E8A",
        )
    )

    focus = card.get("focus_areas", [])
    quote = card.get("quote", {})
    bottom_y = y + h - 166
    left_w = w * 0.48
    parts += [
        _group(_rect(x + 18, bottom_y, left_w, 132, rx=18, fill="white"), filter="url(#g_shadow)"),
        _text(
            x + 34,
            bottom_y + 24,
            card.get("focus_title", "Focus Areas"),
            fill="#17354B",
            font_size="13.5",
            font_weight="700",
            font_family=font_display,
        ),
    ]
    for i, item in enumerate(focus[:3]):
        iy = bottom_y + 46 + i * 28
        color = item.get("color") or ["#3BB75F", "#7158FF", "#78A8FF"][i % 3]
        parts += [
            _circle(x + 46, iy, 12, fill=_mix("#FFFFFF", color, 0.12)),
            _render_icon(
                icon=item.get("icon", ""),
                icon_name=item.get("icon_name", ""),
                title=item.get("title", ""),
                body=item.get("body", ""),
                cx=x + 46,
                cy=iy,
                size=12,
                color=color,
                font_family=font_ui,
            ),
            _text(
                x + 68,
                iy - 2,
                item.get("title", ""),
                fill="#17354B",
                font_size="10.8",
                font_weight="600",
                font_family=font_display,
            ),
            _text(
                x + 68,
                iy + 12,
                _wrap_text(item.get("body", ""), 20)[0] if item.get("body") else "",
                fill="#667B88",
                font_size="10",
                font_family=font_ui,
            ),
        ]

    qx = x + left_w + 30
    qw = w - left_w - 48
    parts += [
        _group(_rect(qx, bottom_y, qw, 132, rx=18, fill="#2CA857"), filter="url(#g_shadow)"),
        _circle(qx + qw - 34, bottom_y + 94, 44, fill=_alpha("#8EF57E", 0.14), filter="url(#g_blur_blob)"),
        _render_named_icon("leaf", qx + qw - 34, bottom_y + 92, 42, "#88F168", stroke_width=1.8),
        _text(
            qx + 24,
            bottom_y + 34,
            "❝",
            fill=_alpha("#FFFFFF", 0.78),
            font_size="26",
            font_weight="700",
            font_family=font_display,
        ),
    ]
    for i, line in enumerate(_wrap_text(quote.get("text", "Sustainability is not a goal, it's a commitment."), 17)[:3]):
        parts.append(
            _text(
                qx + 24,
                bottom_y + 58 + i * 28,
                line,
                fill="white",
                font_size="17",
                font_weight="600",
                font_family=font_display,
            )
        )
    if quote.get("author"):
        parts.append(
            _text(
                qx + 24,
                bottom_y + 112,
                f"— {quote.get('author')}",
                fill=_alpha("#FFFFFF", 0.82),
                font_size="11",
                font_family=font_ui,
            )
        )
    return "".join(parts)


def _render_showcase_customer_satisfaction_card(card: dict, x: float, y: float, w: float, h: float, t: dict) -> str:
    font_display = t.get("font_display", t["font"])
    font_ui = t.get("font_ui", t["font"])
    parts = [_showcase_card_shell(x, y, w, h, bg="#FFFDFC", border="#F3E6E6")]
    title = card.get("title", "Customer Satisfaction Overview")
    for i, line in enumerate(_wrap_text(title, 12)[:3]):
        parts.append(
            _text(
                x + 28,
                y + 54 + i * 34,
                line,
                fill="#1B2340",
                font_size="26",
                font_weight="760",
                font_family=font_display,
                letter_spacing="-1.0",
            )
        )
    parts.append(
        _text(x + 28, y + 144, card.get("subtitle", "2024 Report"), fill="#6C738B", font_size="13", font_family=font_ui)
    )
    score = card.get("score", {})
    score_val = _num(score.get("value", 4.7), 4.7)
    score_max = _num(score.get("max", 5), 5)
    parts += [
        _group(_rect(x + w - 214, y + 20, 184, 150, rx=24, fill="white"), filter="url(#g_shadow)"),
        _showcase_progress_ring(
            x + w - 122,
            y + 86,
            60,
            score_val / score_max if score_max else 0,
            color="#FFB246",
            track="#FBE5E5",
            thickness=10,
            value=str(score.get("value", "4.7")),
            sub=score.get("label", "out of 5"),
            font_display=font_display,
            font_ui=font_ui,
            text_color="#1B2340",
            muted="#6C738B",
        ),
        _text(x + w - 122, y + 138, "★★★★★", fill="#FFB246", font_size="14", font_family=font_ui, text_anchor="middle"),
    ]
    callout = card.get("callout", {})
    parts += [
        _group(_rect(x + 22, y + 190, 168, 54, rx=18, fill="#FFF5F7"), filter="url(#g_shadow)"),
        _circle(x + 52, y + 217, 16, fill="#FFD9E5"),
        _render_icon(
            icon=callout.get("icon", ""),
            icon_name=callout.get("icon_name", "heart"),
            title=callout.get("title", ""),
            body="",
            cx=x + 52,
            cy=y + 217,
            size=14,
            color="#FF5D8F",
            font_family=font_ui,
        ),
        _text(
            x + 82,
            y + 212,
            callout.get("title", "Your customers"),
            fill="#1B2340",
            font_size="11.5",
            font_weight="600",
            font_family=font_ui,
        ),
        _text(
            x + 82,
            y + 228,
            callout.get("body", "love what you do!"),
            fill="#1B2340",
            font_size="11.5",
            font_weight="600",
            font_family=font_ui,
        ),
    ]
    stats = card.get("stats", [])
    stats_y = y + 262
    parts += [_group(_rect(x + 20, stats_y, w - 40, 108, rx=18, fill="white"), filter="url(#g_shadow)")]
    stat_w = (w - 40) / max(len(stats[:4]), 1)
    stat_colors = ["#FF7BAE", "#FF9C45", "#39C177", "#A958F6"]
    for i, stat in enumerate(stats[:4]):
        sx = x + 20 + i * stat_w
        color = stat.get("color") or stat_colors[i % len(stat_colors)]
        if i > 0:
            parts.append(_line(sx, stats_y + 18, sx, stats_y + 90, stroke="#EDF0F6", stroke_width="1"))
        parts += [
            _circle(sx + 38, stats_y + 34, 16, fill=_mix("#FFFFFF", color, 0.16)),
            _render_icon(
                icon=stat.get("icon", ""),
                icon_name=stat.get("icon_name", ""),
                title=stat.get("label", ""),
                body="",
                cx=sx + 38,
                cy=stats_y + 34,
                size=14,
                color=color,
                font_family=font_ui,
            ),
            _text(
                sx + 20,
                stats_y + 72,
                str(stat.get("value", "")),
                fill="#1B2340",
                font_size="17",
                font_weight="760",
                font_family=font_display,
            ),
            _text(sx + 20, stats_y + 92, stat.get("label", ""), fill="#5D667D", font_size="10.5", font_family=font_ui),
        ]
    box_y = y + h - 132
    left_w = (w - 52) * 0.58
    parts += [
        _group(_rect(x + 20, box_y, left_w, 112, rx=18, fill="white"), filter="url(#g_shadow)"),
        _group(_rect(x + 32 + left_w, box_y, w - 52 - left_w, 112, rx=18, fill="white"), filter="url(#g_shadow)"),
        _text(
            x + 34,
            box_y + 22,
            card.get("trend", {}).get("title", "Satisfaction Trend"),
            fill="#1B2340",
            font_size="12",
            font_weight="700",
            font_family=font_display,
        ),
        _text(
            x + 44 + left_w,
            box_y + 22,
            card.get("feedback", {}).get("title", "Top Positive Feedback"),
            fill="#1B2340",
            font_size="12",
            font_weight="700",
            font_family=font_display,
        ),
    ]
    parts.append(
        _showcase_mini_line_chart(
            x + 34,
            box_y + 38,
            left_w - 28,
            48,
            card.get("trend", {}).get("series", [3.2, 3.7, 4.4, 4.5, 4.7, 4.7]),
            line_color="#FF5D8F",
            area_color=_alpha("#FF5D8F", 0.10),
            grid_color="#F3E9EE",
            badge=card.get("trend", {}).get("badge", "4.7"),
            x_labels=card.get("trend", {}).get("x_labels", ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]),
            font_ui=font_ui,
            muted="#7A83A4",
            badge_fill="#FF5D8F",
        )
    )
    for i, item in enumerate(
        card.get("feedback", {}).get(
            "items", ['"Great product!"', '"Excellent support"', '"Easy to use"', '"Highly recommend"']
        )[:4]
    ):
        parts.append(
            _text(
                x + 54 + left_w, box_y + 42 + i * 16, f"• {item}", fill="#6B7688", font_size="10.5", font_family=font_ui
            )
        )
    parts.append(_circle(x + w - 48, box_y + 72, 26, fill="#FF7BAE"))
    parts.append(
        _render_icon(
            icon=None,
            icon_name="heart",
            title="love",
            body="",
            cx=x + w - 48,
            cy=box_y + 72,
            size=20,
            color="white",
            font_family=font_ui,
        )
    )
    return "".join(parts)


def _render_showcase_project_roadmap_card(card: dict, x: float, y: float, w: float, h: float, t: dict) -> str:
    font_display = t.get("font_display", t["font"])
    font_ui = t.get("font_ui", t["font"])
    parts = [_showcase_card_shell(x, y, w, h, bg="#FCFEFF", border="#E6EFF8")]
    parts += [
        _text(
            x + 28,
            y + 48,
            card.get("title", "Project Roadmap"),
            fill="#17354B",
            font_size="28",
            font_weight="760",
            font_family=font_display,
        ),
        _text(
            x + 28,
            y + 72,
            card.get("subtitle", "Our journey to build the future"),
            fill="#60758B",
            font_size="12",
            font_family=font_ui,
        ),
    ]
    progress = card.get("progress", {})
    pct = _num(progress.get("value", 76), 76.0) / 100.0
    parts += [
        _text(
            x + w - 96,
            y + 54,
            progress.get("label", "Progress"),
            fill="#657C91",
            font_size="11",
            font_family=font_ui,
            text_anchor="middle",
        ),
        _showcase_progress_ring(
            x + w - 62,
            y + 56,
            28,
            pct,
            color="#2E7CF7",
            track="#E6EDF8",
            thickness=6,
            value=str(progress.get("value", "76")) + "%",
            font_display=font_display,
            font_ui=font_ui,
            text_color="#1B2340",
            muted="#657C91",
        ),
    ]
    phases = card.get("phases", [])
    card_y = y + 104
    phase_w = (w - 52) / max(len(phases[:4]), 1)
    parts.append(
        _line(x + 44, card_y + 10, x + w - 44, card_y + 10, stroke="#C9DCF2", stroke_width="2", stroke_dasharray="4 4")
    )
    phase_colors = ["#7C4DFF", "#3A8CFF", "#FF9A29", "#33B66D"]
    for i, phase in enumerate(phases[:4]):
        px = x + 20 + i * phase_w
        color = phase.get("color") or phase_colors[i % len(phase_colors)]
        parts += [
            _circle(px + phase_w / 2, card_y + 10, 16, fill=color),
            _render_icon(
                icon=phase.get("icon", ""),
                icon_name=phase.get("icon_name", ""),
                title=phase.get("title", ""),
                body=phase.get("body", ""),
                cx=px + phase_w / 2,
                cy=card_y + 10,
                size=14,
                color="white",
                font_family=font_ui,
            ),
            _group(_rect(px + 8, card_y + 20, phase_w - 16, 164, rx=16, fill="white"), filter="url(#g_shadow)"),
            _text(
                px + phase_w / 2,
                card_y + 48,
                phase.get("phase", f"Phase {i + 1}"),
                fill=color,
                font_size="11",
                font_weight="700",
                font_family=font_ui,
                text_anchor="middle",
            ),
        ]
        for li, line in enumerate(_wrap_text(phase.get("title", ""), 12)[:2]):
            parts.append(
                _text(
                    px + phase_w / 2,
                    card_y + 72 + li * 20,
                    line,
                    fill="#1B2340",
                    font_size="14",
                    font_weight="700",
                    font_family=font_display,
                    text_anchor="middle",
                )
            )
        body_lines = _wrap_text(phase.get("body", ""), 16)[:3]
        for li, line in enumerate(body_lines):
            parts.append(
                _text(
                    px + 22, card_y + 108 + li * 16, f"✓ {line}", fill="#587192", font_size="10.5", font_family=font_ui
                )
            )
        status = phase.get("status", "")
        if status:
            fill = _mix("#FFFFFF", color, 0.10)
            parts += [
                _rect(px + phase_w / 2 - 34, card_y + 154, 68, 22, rx=11, fill=fill),
                _text(
                    px + phase_w / 2,
                    card_y + 169,
                    status,
                    fill=color,
                    font_size="10",
                    font_weight="700",
                    font_family=font_ui,
                    text_anchor="middle",
                ),
            ]
    mile = card.get("milestones", {})
    my = y + h - 106
    parts += [
        _group(_rect(x + 20, my, w - 40, 86, rx=18, fill="white"), filter="url(#g_shadow)"),
        _text(
            x + 34,
            my + 22,
            mile.get("title", "Key Milestones"),
            fill="#3A57FF",
            font_size="12",
            font_weight="700",
            font_family=font_ui,
        ),
        _line(x + 64, my + 44, x + w - 64, my + 44, stroke="#DCE5F3", stroke_width="1.5"),
    ]
    items = mile.get("items", [])
    for i, item in enumerate(items[:4]):
        px = x + 64 + i * ((w - 128) / max(len(items[:4]) - 1, 1))
        color = item.get("color") or phase_colors[i % len(phase_colors)]
        parts += [
            _circle(px, my + 44, 12, fill=color),
            _render_icon(
                icon=item.get("icon", ""),
                icon_name=item.get("icon_name", ""),
                title=item.get("title", ""),
                body="",
                cx=px,
                cy=my + 44,
                size=10,
                color="white",
                font_family=font_ui,
            ),
            _text(
                px,
                my + 68,
                item.get("label", ""),
                fill="#6D7A8F",
                font_size="10",
                font_family=font_ui,
                text_anchor="middle",
            ),
            _text(
                px,
                my + 84,
                item.get("title", ""),
                fill="#1B2340",
                font_size="10.5",
                font_weight="600",
                font_family=font_ui,
                text_anchor="middle",
            ),
        ]
    return "".join(parts)


def _render_showcase_financial_highlights_card(card: dict, x: float, y: float, w: float, h: float, t: dict) -> str:
    font_display = t.get("font_display", t["font"])
    font_ui = t.get("font_ui", t["font"])
    parts = [
        _showcase_card_shell(x, y, w, h, bg="#081B4A", border=_alpha("#58A7FF", 0.18), shadow="url(#g_shadow_soft)"),
        _circle(x + 60, y + h - 40, 90, fill=_alpha("#2347FF", 0.22), filter="url(#g_blur_blob)"),
    ]
    parts += [
        _text(
            x + 24,
            y + 42,
            card.get("title", "Financial Highlights"),
            fill="white",
            font_size="24",
            font_weight="760",
            font_family=font_display,
        ),
        _text(
            x + 24,
            y + 66,
            card.get("subtitle", "FY 2024"),
            fill=_alpha("#FFFFFF", 0.78),
            font_size="12",
            font_family=font_ui,
        ),
    ]
    series = card.get("series", {})
    labels = series.get("labels", ["Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024"])
    bars = series.get(
        "bars",
        [
            {"label": "Revenue", "values": [18, 24, 26, 30], "color": "#4A6FFF"},
            {"label": "Profit", "values": [14, 13, 12, 17], "color": "#4FD17A"},
            {"label": "Expenses", "values": [7, 9, 8, 11], "color": "#FF5AA0"},
        ],
    )
    chart_x, chart_y, chart_w, chart_h = x + 28, y + 98, w * 0.52, 116
    for i, item in enumerate(bars[:3]):
        parts += [
            _circle(chart_x + i * 74, y + 86, 4, fill=item.get("color", "#4A6FFF")),
            _text(
                chart_x + 10 + i * 74,
                y + 90,
                item.get("label", ""),
                fill=_alpha("#FFFFFF", 0.84),
                font_size="10",
                font_family=font_ui,
            ),
        ]
    max_val = max((_num(v) for item in bars[:3] for v in item.get("values", [])), default=1) or 1
    for i in range(5):
        gy = chart_y + chart_h - i * (chart_h / 4)
        parts.append(_line(chart_x, gy, chart_x + chart_w, gy, stroke=_alpha("#FFFFFF", 0.14), stroke_width="1"))
        if i < 4:
            parts.append(
                _text(
                    chart_x - 6,
                    gy + 4,
                    f"${i * 5}M" if i > 0 else "$0",
                    fill=_alpha("#FFFFFF", 0.58),
                    font_size="9",
                    font_family=font_ui,
                    text_anchor="end",
                )
            )
    groups = len(labels)
    group_w = chart_w / max(groups, 1)
    bar_w = group_w / 5
    for gi, label in enumerate(labels[:groups]):
        base_x = chart_x + gi * group_w + group_w * 0.16
        for bi, item in enumerate(bars[:3]):
            val = _num(item.get("values", [0] * groups)[gi], 0.0)
            bh = (val / max_val) * (chart_h - 8)
            parts.append(
                _rect(
                    base_x + bi * (bar_w + 6),
                    chart_y + chart_h - bh,
                    bar_w,
                    bh,
                    rx=2,
                    fill=item.get("color", "#4A6FFF"),
                )
            )
        parts.append(
            _text(
                chart_x + gi * group_w + group_w / 2,
                chart_y + chart_h + 18,
                label,
                fill=_alpha("#FFFFFF", 0.7),
                font_size="9",
                font_family=font_ui,
                text_anchor="middle",
            )
        )

    metrics = card.get("metrics", [])
    metric_x = x + w * 0.64
    metric_w = w - (metric_x - x) - 24
    metric_colors = ["#5377FF", "#45D47A", "#FF5EA5"]
    for i, item in enumerate(metrics[:3]):
        iy = y + 24 + i * 66
        color = item.get("color") or metric_colors[i % len(metric_colors)]
        parts += [
            _group(_rect(metric_x, iy, metric_w, 56, rx=14, fill=_alpha(color, 0.24)), filter="url(#g_shadow)"),
            _circle(metric_x + 24, iy + 28, 16, fill=_alpha("#FFFFFF", 0.12)),
            _render_icon(
                icon=item.get("icon", ""),
                icon_name=item.get("icon_name", ""),
                title=item.get("label", ""),
                body="",
                cx=metric_x + 24,
                cy=iy + 28,
                size=14,
                color="white",
                font_family=font_ui,
            ),
            _text(
                metric_x + 48,
                iy + 18,
                item.get("label", ""),
                fill=_alpha("#FFFFFF", 0.78),
                font_size="10.5",
                font_family=font_ui,
            ),
            _text(
                metric_x + 48,
                iy + 38,
                str(item.get("value", "")),
                fill="white",
                font_size="16",
                font_weight="760",
                font_family=font_display,
            ),
            _text(
                metric_x + 48,
                iy + 52,
                item.get("change", ""),
                fill=_alpha("#FFFFFF", 0.82),
                font_size="9.5",
                font_family=font_ui,
            ),
        ]
    kpi_y = y + h - 86
    parts += [_group(_rect(x + 16, kpi_y, w - 32, 64, rx=16, fill=_alpha("#021536", 0.72)), filter="url(#g_shadow)")]
    kpis = card.get("kpis", [])
    kpi_w = (w - 32) / max(len(kpis[:4]), 1)
    kpi_colors = ["#456DFF", "#2BC06F", "#FF942E", "#FF4D78"]
    for i, item in enumerate(kpis[:4]):
        kx = x + 16 + i * kpi_w
        color = item.get("color") or kpi_colors[i % len(kpi_colors)]
        if i > 0:
            parts.append(_line(kx, kpi_y + 12, kx, kpi_y + 52, stroke=_alpha("#FFFFFF", 0.08), stroke_width="1"))
        parts += [
            _circle(kx + 24, kpi_y + 22, 12, fill=color),
            _render_icon(
                icon=item.get("icon", ""),
                icon_name=item.get("icon_name", ""),
                title=item.get("label", ""),
                body="",
                cx=kx + 24,
                cy=kpi_y + 22,
                size=10,
                color="white",
                font_family=font_ui,
            ),
            _text(
                kx + 44,
                kpi_y + 20,
                item.get("label", ""),
                fill=_alpha("#FFFFFF", 0.72),
                font_size="9.5",
                font_family=font_ui,
            ),
            _text(
                kx + 44,
                kpi_y + 40,
                str(item.get("value", "")),
                fill="white",
                font_size="15",
                font_weight="700",
                font_family=font_display,
            ),
            _text(kx + 44, kpi_y + 54, item.get("change", ""), fill=color, font_size="9.5", font_family=font_ui),
        ]
    return "".join(parts)


def _render_showcase_employee_engagement_card(card: dict, x: float, y: float, w: float, h: float, t: dict) -> str:
    font_display = t.get("font_display", t["font"])
    font_ui = t.get("font_ui", t["font"])
    parts = [
        _showcase_card_shell(x, y, w, h, bg="#4D13C9", border=_alpha("#D6A8FF", 0.16), shadow="url(#g_shadow_soft)"),
        _circle(x + w - 110, y + 74, 96, fill=_alpha("#3ED1FF", 0.18), filter="url(#g_blur_blob)"),
    ]
    parts += [
        _text(
            x + 28,
            y + 48,
            card.get("title", "Employee Engagement"),
            fill="white",
            font_size="26",
            font_weight="760",
            font_family=font_display,
        ),
        _text(
            x + 28,
            y + 72,
            card.get("subtitle", "2024 Overview"),
            fill=_alpha("#FFFFFF", 0.78),
            font_size="12",
            font_family=font_ui,
        ),
    ]
    dims = card.get("dimensions", [])
    dim_colors = ["#F4A5FF", "#78C6FF", "#FF8EA3", "#FFCA73"]
    for i, item in enumerate(dims[:4]):
        iy = y + 102 + i * 28
        color = dim_colors[i % len(dim_colors)]
        parts += [
            _circle(x + 42, iy - 2, 10, fill=_alpha("#FFFFFF", 0.14)),
            _render_icon(
                icon=item.get("icon", ""),
                icon_name=item.get("icon_name", "spark"),
                title=item.get("label", ""),
                body="",
                cx=x + 42,
                cy=iy - 2,
                size=10,
                color=color,
                font_family=font_ui,
            ),
            _text(x + 62, iy + 2, item.get("label", ""), fill="white", font_size="11.5", font_family=font_ui),
            _text(
                x + 178,
                iy + 2,
                str(item.get("value", "")),
                fill=_alpha("#FFFFFF", 0.88),
                font_size="11.5",
                font_weight="700",
                font_family=font_ui,
            ),
        ]
    score = card.get("score", {})
    parts.append(
        _showcase_progress_ring(
            x + w - 118,
            y + 74,
            54,
            _num(score.get("value", 89), 89) / max(_num(score.get("max", 100), 100), 1),
            color="#53E69C",
            track=_alpha("#FFFFFF", 0.16),
            thickness=9,
            value=str(score.get("value", "89")),
            sub=score.get("status", "Excellent"),
            font_display=font_display,
            font_ui=font_ui,
            text_color="white",
            muted=_alpha("#FFFFFF", 0.78),
        )
    )
    parts.append(
        _text(
            x + w - 118,
            y + 28,
            score.get("label", "Engagement Score"),
            fill=_alpha("#FFFFFF", 0.78),
            font_size="11",
            font_family=font_ui,
            text_anchor="middle",
        )
    )
    parts.append(
        _path(
            f"M {x + w * 0.58:.1f} {y + 154:.1f} C {x + w * 0.66:.1f} {y + 120:.1f} {x + w * 0.74:.1f} {y + 188:.1f} {x + w * 0.82:.1f} {y + 134:.1f} S {x + w - 34:.1f} {y + 176:.1f} {x + w - 18:.1f} {y + 120:.1f} L {x + w - 18:.1f} {y + 208:.1f} L {x + w * 0.58:.1f} {y + 208:.1f} Z",
            fill=_alpha("#FF8BE7", 0.26),
        )
    )
    stats = card.get("stats", [])
    stats_y = y + 188
    box_w = (w - 48) / max(len(stats[:4]), 1)
    for i, item in enumerate(stats[:4]):
        bx = x + 16 + i * box_w
        parts += [
            _group(_rect(bx, stats_y, box_w - 8, 66, rx=14, fill=_alpha("#281566", 0.44)), filter="url(#g_shadow)"),
            _text(
                bx + 14,
                stats_y + 18,
                item.get("label", ""),
                fill=_alpha("#FFFFFF", 0.68),
                font_size="9.5",
                font_family=font_ui,
            ),
            _text(
                bx + 14,
                stats_y + 42,
                str(item.get("value", "")),
                fill="white",
                font_size="18",
                font_weight="760",
                font_family=font_display,
            ),
            _text(bx + 14, stats_y + 58, item.get("change", ""), fill="#6AF3A2", font_size="9.5", font_family=font_ui),
        ]
    quote = card.get("quote", {})
    qy = y + h - 74
    parts += [
        _group(_rect(x + 18, qy, w - 36, 54, rx=16, fill=_alpha("#2B166C", 0.54)), filter="url(#g_shadow)"),
        _text(x + 32, qy + 23, "❝", fill="#FFE38F", font_size="22", font_family=font_display),
        _text(
            x + 62,
            qy + 25,
            _wrap_text(quote.get("text", "Great teams are built on connection, purpose, and trust."), 30)[0],
            fill="white",
            font_size="12.5",
            font_family=font_ui,
        ),
        _rect(x + w - 152, qy + 10, 118, 34, rx=14, fill=_alpha("#5B3BEB", 0.82)),
        _text(
            x + w - 93,
            qy + 32,
            quote.get("cta", "Let's keep growing together!"),
            fill="white",
            font_size="10.5",
            font_weight="600",
            font_family=font_ui,
            text_anchor="middle",
        ),
    ]
    return "".join(parts)


def _render_showcase_dashboard(section: dict, x: float, y: float, width: float, t: dict) -> tuple[str, float]:
    cards = section.get("cards", [])
    if not cards:
        return "", 0.0

    gap = 16.0
    col_w = (width - gap) / 2
    row_heights = [688.0, 468.0, 322.0]
    renderers = {
        "business_performance": _render_showcase_business_performance_card,
        "sustainability_impact": _render_showcase_sustainability_impact_card,
        "customer_satisfaction": _render_showcase_customer_satisfaction_card,
        "project_roadmap": _render_showcase_project_roadmap_card,
        "financial_highlights": _render_showcase_financial_highlights_card,
        "employee_engagement": _render_showcase_employee_engagement_card,
    }

    parts: list[str] = []
    cur_y = y
    y_offsets = [cur_y, cur_y + row_heights[0] + gap, cur_y + row_heights[0] + row_heights[1] + gap * 2]
    for idx, card in enumerate(cards[:6]):
        row = idx // 2
        col = idx % 2
        cx = x + col * (col_w + gap)
        cy = y_offsets[row]
        ch = row_heights[row]
        renderer = renderers.get(card.get("variant", ""))
        if renderer:
            parts.append(renderer(card, cx, cy, col_w, ch, t))

    total_h = sum(row_heights) + gap * 2
    return "\n".join(parts), total_h


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

_RENDERERS: dict = {
    "kpi_row": _render_kpi_row,
    "bar_chart": _render_bar_chart,
    "donut": _render_donut,
    "stories": _render_stories,
    "heatmap": _render_heatmap,
    "divider": _render_divider,
    "text": _render_text_block,
    "sustainability_dashboard": _render_sustainability_dashboard,
    "assessment_scorecard": _render_assessment_scorecard,
    "showcase_dashboard": _render_showcase_dashboard,
    # AntV-parity types
    "process_flow": _render_process_flow,
    "circular_flow": _render_circular_flow,
    "staircase": _render_staircase,
    "pyramid": _render_pyramid,
    "snake_path": _render_snake_path,
    "bubble_chain": _render_bubble_chain,
    "timeline": _render_timeline,
    "venn": _render_venn,
    "comparison": _render_comparison,
    "swot": _render_swot,
    "matrix_2x2": _render_matrix_2x2,
    "quadrant_circle": _render_quadrant_circle,
    "card_grid": _render_card_grid,
    "pill_list": _render_pill_list,
    "wheel": _render_wheel,
}


def _should_render_global_header(spec: dict) -> bool:
    if spec.get("hide_header") is True:
        return False

    sections = spec.get("sections") or []
    if len(sections) != 1 or not isinstance(sections[0], dict):
        return True

    section = sections[0]
    section_type = section.get("type", "")
    if section_type in {"sustainability_dashboard", "showcase_dashboard"}:
        return False
    if section_type == "assessment_scorecard" and section.get("layout") != "classic":
        return False

    return True


class InfographicRenderer:
    """
    Renders a data-driven infographic as a standalone SVG string.

    Usage::

        renderer = InfographicRenderer()
        svg = renderer.render(spec_dict)

    The ``theme`` field in the spec can be:
    - A preset name (str):  ``"aurora"`` | ``"midnight"`` | ``"carbon"`` | ``"sunset"`` | ``"emerald"`` | ``"daylight"``
    - A full custom dict with any subset of theme keys
    - A partial override:   ``{"preset": "midnight", "palette": ["#FF0", "#0FF"]}``
    """

    def render(self, spec: dict) -> str:
        t = resolve_theme(spec.get("theme"))
        width = int(spec.get("width", 900))
        cx = float(_PAD_H)
        cw = float(width - _PAD_H * 2)

        body_parts: list[str] = []
        cur_y = 0.0

        header_svg = ""
        if _should_render_global_header(spec):
            header_svg, header_h = _render_header(spec, width, t)
            cur_y += header_h + _SEC_GAP
        else:
            cur_y += 10.0

        # Sections
        for section in spec.get("sections", []):
            renderer = _RENDERERS.get(section.get("type", ""))
            if renderer is None:
                continue
            frag, consumed = renderer(section, cx, cur_y, cw, t)
            if frag:
                body_parts.append(frag)
            cur_y += consumed + _SEC_GAP

        total_h = int(cur_y + _PAD_V)

        # Build final SVG
        defs_svg = _build_defs(t, width)
        backdrop_svg = _render_canvas_backdrop(width, total_h, t)

        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg"'
            f' width="{width}" height="{total_h}"'
            f' viewBox="0 0 {width} {total_h}">',
            defs_svg,
            _rect(0, 0, width, total_h, fill=t["bg"]),
            backdrop_svg,
            header_svg,
            *body_parts,
            "</svg>",
        ]
        return "\n".join(lines)


def render_infographic(spec: dict) -> str:
    """Convenience wrapper: ``render_infographic(spec)`` → SVG string."""
    return InfographicRenderer().render(spec)
