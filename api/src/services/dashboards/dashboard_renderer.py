"""
Dashboard Renderer — generates self-contained interactive HTML dashboards.

The agent authors a JSON spec (sections: kpi_row, chart, table, filter, text).
This module renders the spec + data into a single standalone HTML file using
Plotly.js for interactive charts.  No server-side rendering at view time.
"""

from __future__ import annotations

import json  # used by section renderers added in this module
from typing import Any

_PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.32.0.min.js"

_D = {
    "bg": "#f5f0eb",
    "card_bg": "#ffffff",
    "card_border": "#e5dfd8",
    "accent": "#c2600a",
    "label_color": "#6b6660",
    "value_color": "#1a1917",
    "body_color": "#3d3936",
    "font": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
}

_AGG_FUNCS: dict[str, Any] = {
    "sum": sum,
    "mean": lambda v: sum(v) / len(v),
    "max": max,
    "min": min,
    "first": lambda v: v[0],
    "last": lambda v: v[-1],
}


def _safe_json(obj: Any) -> str:
    """Serialize obj to JSON safe for embedding inside HTML <script> blocks.

    json.dumps can produce '</script>' verbatim inside data values, which
    terminates the enclosing <script> tag and allows script injection.
    Replacing '</' with '<\\/' is the standard mitigation.
    """
    return json.dumps(obj).replace("</", "<\\/")


def _aggregate(data: list[dict], column: str | None, agg: str) -> float | int | None:
    """Aggregate a numeric column across all rows.  Returns None on failure."""
    if agg == "count":
        return len(data)
    if not data or not column:
        return None
    raw = [row.get(column) for row in data if row.get(column) is not None]
    try:
        nums = [float(v) for v in raw]
    except (TypeError, ValueError):
        return None
    if not nums:
        return None
    fn = _AGG_FUNCS.get(agg)
    if fn is None:
        return None
    try:
        return fn(nums)
    except (ArithmeticError, ValueError):
        return None


def _format_number(val: float | int | None) -> str:
    """Format a number for display: integers comma-separated, floats to 2dp."""
    if val is None:
        return "—"
    f = float(val)
    if f == int(f):
        return f"{int(f):,}"
    return f"{f:,.2f}"


def _render_kpi_row(kpis: list[dict], data: list[dict]) -> str:
    """Render a horizontal row of KPI metric cards."""
    cards = []
    for kpi in kpis:
        label = kpi.get("label", "")
        column = kpi.get("column")
        agg = kpi.get("agg", "sum")
        prefix = kpi.get("prefix", "")
        suffix = kpi.get("suffix", "")
        val = _aggregate(data, column, agg)
        display = f"{prefix}{_format_number(val)}{suffix}"
        cards.append(
            f'<div style="background:{_D["card_bg"]};border:1px solid {_D["card_border"]};'
            f'border-radius:10px;padding:20px 24px;flex:1;min-width:140px;">'
            f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:{_D["label_color"]};margin-bottom:8px;">{label}</div>'
            f'<div style="font-size:28px;font-weight:700;color:{_D["accent"]};">{display}</div>'
            f"</div>"
        )
    joined = "".join(cards)
    return (
        f'<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;">{joined}</div>'
    )


def _aggregate_for_chart(
    data: list[dict], x_col: str, y_col: str, agg: str | None
) -> tuple[list, list]:
    """Group data by x_col, aggregate y_col.  Returns (xs, ys) lists."""
    if not agg:
        return [row.get(x_col) for row in data], [row.get(y_col) for row in data]
    groups: dict[Any, list[float]] = {}
    for row in data:
        key = row.get(x_col)
        val = row.get(y_col)
        if key not in groups:
            groups[key] = []
        if val is not None:
            try:
                groups[key].append(float(val))
            except (TypeError, ValueError):
                pass
    fn = _AGG_FUNCS.get(agg, sum)
    xs = list(groups.keys())
    ys = [fn(groups[k]) if groups[k] else 0 for k in xs]
    return xs, ys


def _plotly_layout(extra: dict | None = None) -> dict:
    """Return a base Plotly layout dict with the dashboard design tokens."""
    base: dict[str, Any] = {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": _D["font"], "color": _D["body_color"]},
        "xaxis": {"gridcolor": _D["card_border"], "linecolor": _D["card_border"]},
        "yaxis": {"gridcolor": _D["card_border"], "linecolor": _D["card_border"]},
        "margin": {"t": 20, "r": 10, "b": 40, "l": 50},
    }
    if extra:
        base.update(extra)
    return base


def _render_chart(section: dict, chart_idx: int, data: list[dict]) -> str:
    """Render one chart section as an HTML card with inline Plotly init script."""
    chart_type = section.get("chart_type", "bar")
    title = section.get("title", "")
    x_col = section.get("x", "")
    y_col = section.get("y", "")
    # If y is a list (LLM mistake), take the first element so rendering doesn't crash
    if isinstance(y_col, list):
        y_col = y_col[0] if y_col else ""
    if isinstance(x_col, list):
        x_col = x_col[0] if x_col else ""
    agg = section.get("agg")
    div_id = f"chart_{chart_idx}"

    accent = _D["accent"]
    trace: dict[str, Any]
    layout: dict[str, Any]

    if chart_type in ("bar", "horizontal_bar"):
        xs, ys = _aggregate_for_chart(data, x_col, y_col, agg)
        orient = "h" if chart_type == "horizontal_bar" else "v"
        trace = {
            "type": "bar",
            "x": ys if orient == "h" else xs,
            "y": xs if orient == "h" else ys,
            "orientation": orient,
            "marker": {"color": accent, "opacity": 0.85},
        }
        layout = _plotly_layout()

    elif chart_type == "line":
        xs, ys = _aggregate_for_chart(data, x_col, y_col, agg)
        trace = {
            "type": "scatter",
            "mode": "lines+markers",
            "x": xs,
            "y": ys,
            "line": {"color": accent, "width": 2},
            "fill": "tozeroy",
            "fillcolor": "rgba(194,96,10,0.15)",
        }
        layout = _plotly_layout()

    elif chart_type == "area":
        xs, ys = _aggregate_for_chart(data, x_col, y_col, agg)
        trace = {
            "type": "scatter",
            "mode": "lines",
            "x": xs,
            "y": ys,
            "line": {"color": accent},
            "fill": "tozeroy",
            "fillcolor": "rgba(194,96,10,0.15)",
        }
        layout = _plotly_layout()

    elif chart_type == "pie":
        xs, ys = _aggregate_for_chart(data, x_col, y_col, agg)
        trace = {
            "type": "pie",
            "labels": xs,
            "values": ys,
            "marker": {"colors": [accent, "#e8956d", "#f0c4a0", "#d4451a", "#fad2b2"]},
        }
        layout = _plotly_layout({"xaxis": None, "yaxis": None, "margin": {"t": 20, "r": 10, "b": 20, "l": 10}})

    elif chart_type == "scatter":
        trace = {
            "type": "scatter",
            "mode": "markers",
            "x": [row.get(x_col) for row in data],
            "y": [row.get(y_col) for row in data],
            "marker": {"color": accent, "opacity": 0.7},
        }
        layout = _plotly_layout()

    elif chart_type == "heatmap":
        xs, ys = _aggregate_for_chart(data, x_col, y_col, agg)
        trace = {
            "type": "heatmap",
            "x": xs,
            "y": [y_col],
            "z": [ys],
            "colorscale": [[0, _D["bg"]], [1, accent]],
        }
        layout = _plotly_layout()

    else:
        # Unknown chart type — fall back to bar
        xs, ys = _aggregate_for_chart(data, x_col, y_col, agg)
        trace = {
            "type": "bar",
            "x": xs,
            "y": ys,
            "marker": {"color": accent, "opacity": 0.85},
        }
        layout = _plotly_layout()

    cfg = {"responsive": True, "displayModeBar": False}
    trace_json = _safe_json(trace)
    layout_json = _safe_json(layout)
    cfg_json = _safe_json(cfg)

    return (
        f'<div style="background:{_D["card_bg"]};border:1px solid {_D["card_border"]};'
        f'border-radius:10px;padding:20px 24px;margin-bottom:24px;">'
        f'<div style="font-size:13px;font-weight:600;color:{_D["value_color"]};margin-bottom:16px;">{title}</div>'
        f'<div id="{div_id}" style="height:280px;"></div>'
        f"<script>(function(){{"
        f"var t={trace_json};var l={layout_json};var c={cfg_json};"
        f"window.__charts=window.__charts||{{}};"
        f"window.__charts['{div_id}']={{trace:t,layout:l,config:c,"
        f"xCol:{json.dumps(x_col)},yCol:{json.dumps(y_col)},agg:{json.dumps(agg)}}};"
        f"Plotly.newPlot('{div_id}',[t],l,c);"
        f"}})();</script></div>"
    )


def _render_table(section: dict, data: list[dict]) -> str:
    """Render a sortable, client-side-paginated data table."""
    title = section.get("title", "")
    requested_cols = section.get("columns")
    page_size = int(section.get("page_size") or 20)

    all_cols = list(data[0].keys()) if data else []
    if requested_cols:
        valid_cols = [c for c in requested_cols if c in all_cols]
    else:
        valid_cols = all_cols

    header_cells = "".join(
        f'<th onclick="sortTable(this)" style="padding:10px 12px;text-align:left;'
        f'font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;'
        f'color:{_D["label_color"]};cursor:pointer;user-select:none;'
        f'border-bottom:1px solid {_D["card_border"]};">{c} ↕</th>'
        for c in valid_cols
    )

    rows_json = _safe_json([[str(row.get(c, "")) for c in valid_cols] for row in data])
    uid = str(id(section) % 10**8)
    tbody_id = f"tb_{uid}"
    pag_id = f"pg_{uid}"

    title_html = (
        f'<div style="font-size:13px;font-weight:600;color:{_D["value_color"]};margin-bottom:16px;">{title}</div>'
        if title
        else ""
    )

    return (
        f'<div style="background:{_D["card_bg"]};border:1px solid {_D["card_border"]};'
        f'border-radius:10px;padding:20px 24px;margin-bottom:24px;">'
        f"{title_html}"
        f'<div style="overflow-x:auto;">'
        f'<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f'<tbody id="{tbody_id}"></tbody>'
        f"</table></div>"
        f'<div id="{pag_id}" style="display:flex;gap:8px;align-items:center;margin-top:12px;'
        f'font-size:12px;color:{_D["label_color"]};"></div>'
        f"<script>(function(){{"
        f"var ROWS={rows_json};"
        f"var PS={page_size};"
        f"var tbodyId='{tbody_id}',pagId='{pag_id}';"
        f"var curPage=0,curRows=ROWS;"
        f"window.__tables=window.__tables||{{}};"
        f"window.__tables['{tbody_id}']={{allRows:ROWS,cols:{_safe_json(valid_cols)},ps:PS}};"
        f"function render(rows,pg){{"
        f"var tb=document.getElementById(tbodyId);"
        f"var sl=rows.slice(pg*PS,(pg+1)*PS);"
        f"tb.innerHTML=sl.map(function(r){{"
        f"return '<tr>'+r.map(function(c){{"
        f'return \'<td style="padding:10px 12px;border-bottom:1px solid {_D["card_border"]};\'+'
        f'\'color:{_D["body_color"]};">\'+(c||\'\')+\'</td>\';'
        f"}}).join('')+'</tr>';"
        f"}}).join('');"
        f"var pages=Math.ceil(rows.length/PS);"
        f"var pag=document.getElementById(pagId);pag.innerHTML='';"
        f"if(pages>1){{for(var i=0;i<pages;i++){{"
        f"var b=document.createElement('button');"
        f"b.textContent=i+1;"
        f"b.style.cssText='padding:4px 10px;border:1px solid {_D['card_border']};border-radius:6px;"
        f"cursor:pointer;background:'+(i===pg?'{_D['accent']}':'#fff')+"
        f"';color:'+(i===pg?'#fff':'{_D['body_color']}')+"
        f"';font-size:12px;margin-right:4px;';"
        f"(function(pg2){{b.onclick=function(){{curPage=pg2;render(curRows,pg2);}};"
        f"}})(i);pag.appendChild(b);}}}}}}"
        f"render(ROWS,0);"
        f"}})();</script></div>"
    )


def _render_filter(section: dict, data: list[dict]) -> str:
    """Render a dropdown filter that triggers `applyFilters()` on change."""
    column = section.get("column", "")
    label = section.get("label") or f"Filter by {column}"
    values = sorted({str(row.get(column, "")) for row in data if row.get(column) is not None})
    options = '<option value="">All</option>' + "".join(
        f'<option value="{v}">{v}</option>' for v in values
    )
    return (
        f'<div style="display:inline-flex;flex-direction:column;gap:4px;">'
        f'<label style="font-size:10px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:{_D["label_color"]};">{label}</label>'
        f'<select data-filter-col="{column}" onchange="applyFilters()" '
        f'style="padding:6px 12px;border:1px solid {_D["card_border"]};border-radius:8px;'
        f'font-size:13px;color:{_D["body_color"]};background:#fff;outline:none;">'
        f"{options}</select></div>"
    )


def _render_text(section: dict) -> str:
    """Render a heading + body text block."""
    heading = section.get("heading", "")
    body = section.get("body", "")
    h = (
        f'<h2 style="font-size:18px;font-weight:700;color:{_D["value_color"]};margin:0 0 8px 0;">{heading}</h2>'
        if heading
        else ""
    )
    p = (
        f'<p style="font-size:14px;color:{_D["body_color"]};margin:0;line-height:1.6;">{body}</p>'
        if body
        else ""
    )
    return f'<div style="margin-bottom:24px;">{h}{p}</div>'


def render_dashboard(
    title: str, sections: list[dict], data: list[dict]
) -> tuple[str, list[str]]:
    """
    Render a complete self-contained interactive HTML dashboard.

    Returns:
        (html_string, warnings) — warnings is a list of non-fatal issues
        (e.g. unknown section type, missing column).  HTML is always returned.
    """
    warnings: list[str] = []

    filter_sections = [s for s in sections if s.get("type") == "filter"]
    content_sections = [s for s in sections if s.get("type") != "filter"]

    filter_html = ""
    if filter_sections:
        items = "".join(_render_filter(s, data) for s in filter_sections)
        filter_html = (
            f'<div style="display:flex;gap:16px;flex-wrap:wrap;'
            f'background:{_D["card_bg"]};border:1px solid {_D["card_border"]};'
            f'border-radius:10px;padding:16px 24px;margin-bottom:24px;">{items}</div>'
        )

    content_parts: list[str] = []
    chart_idx = 0
    for section in content_sections:
        stype = section.get("type")
        try:
            if stype == "kpi_row":
                content_parts.append(_render_kpi_row(section.get("kpis") or [], data))
            elif stype == "chart":
                content_parts.append(_render_chart(section, chart_idx, data))
                chart_idx += 1
            elif stype == "table":
                content_parts.append(_render_table(section, data))
            elif stype == "text":
                content_parts.append(_render_text(section))
            else:
                warnings.append(f"Unknown section type: {stype!r} — skipped")
        except Exception as exc:
            warnings.append(f"Section {stype!r} render error: {exc} — skipped")

    filter_cols_json = _safe_json([s.get("column") for s in filter_sections if s.get("column")])
    data_json = _safe_json(data)
    content_html = "".join(content_parts)

    html = _build_full_html(title, filter_html, content_html, data_json, filter_cols_json)
    return html, warnings


def _build_full_html(
    title: str,
    filter_html: str,
    content_html: str,
    data_json: str,
    filter_cols_json: str,
) -> str:
    d = _D
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script src="{_PLOTLY_CDN}"></script>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
    body{{font-family:{d['font']};background:{d['bg']};color:{d['body_color']};padding:32px 16px 48px;}}
    .dash-container{{max-width:1100px;margin:0 auto;}}
    h1{{font-size:22px;font-weight:700;color:{d['value_color']};margin-bottom:24px;}}
    .dash-footer{{margin-top:32px;padding-top:16px;border-top:1px solid {d['card_border']};display:flex;align-items:center;justify-content:center;gap:8px;}}
    .dash-footer-logo{{width:18px;height:18px;border-radius:4px;background:{d['accent']};display:flex;align-items:center;justify-content:center;flex-shrink:0;}}
    .dash-footer-logo svg{{width:11px;height:11px;}}
    .dash-footer-text{{font-size:11px;color:{d['label_color']};letter-spacing:0.02em;}}
    .dash-footer-text strong{{color:{d['body_color']};font-weight:600;}}
  </style>
</head>
<body>
  <div class="dash-container">
  <h1>{title}</h1>
  {filter_html}
  {content_html}
  <footer class="dash-footer">
    <div class="dash-footer-logo">
      <svg viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="6" cy="6" r="4" stroke="white" stroke-width="1.5"/>
        <circle cx="6" cy="6" r="1.5" fill="white"/>
      </svg>
    </div>
    <span class="dash-footer-text">Generated by <strong>Synkora</strong></span>
  </footer>
  </div>
  <script>
    const ALL_DATA={data_json};
    const FILTER_COLS={filter_cols_json};
    function getFilteredData(){{
      var d=ALL_DATA;
      FILTER_COLS.forEach(function(col){{
        var el=document.querySelector('[data-filter-col="'+col+'"]');
        if(el&&el.value)d=d.filter(function(r){{return String(r[col])===el.value;}});
      }});
      return d;
    }}
    function aggregateForChart(rows,xCol,yCol,agg){{
      if(!agg)return{{xs:rows.map(function(r){{return r[xCol];}}),ys:rows.map(function(r){{return r[yCol];}})}};
      var groups={{}},order=[];
      rows.forEach(function(r){{
        var k=String(r[xCol]!==undefined?r[xCol]:'');
        var v=parseFloat(r[yCol]);
        if(!(k in groups)){{groups[k]=[];order.push(k);}}
        if(!isNaN(v))groups[k].push(v);
      }});
      var ys=order.map(function(k){{
        var v=groups[k];if(!v.length)return 0;
        if(agg==='sum')return v.reduce(function(a,b){{return a+b;}},0);
        if(agg==='mean')return v.reduce(function(a,b){{return a+b;}},0)/v.length;
        if(agg==='max')return Math.max.apply(null,v);
        if(agg==='min')return Math.min.apply(null,v);
        if(agg==='first')return v[0];if(agg==='last')return v[v.length-1];
        return v.reduce(function(a,b){{return a+b;}},0);
      }});
      return{{xs:order,ys:ys}};
    }}
    function applyFilters(){{
      var filtered=getFilteredData();
      var charts=window.__charts||{{}};
      Object.keys(charts).forEach(function(id){{
        var cfg=charts[id];
        if(!document.getElementById(id))return;
        var nt=JSON.parse(JSON.stringify(cfg.trace));
        if(cfg.xCol&&cfg.yCol){{
          var r=aggregateForChart(filtered,cfg.xCol,cfg.yCol,cfg.agg);
          if(cfg.trace.type==='pie'){{nt.labels=r.xs;nt.values=r.ys;}}
          else if(cfg.trace.orientation==='h'){{nt.x=r.ys;nt.y=r.xs;}}
          else{{nt.x=r.xs;nt.y=r.ys;}}
        }}
        Plotly.react(id,[nt],cfg.layout,cfg.config);
      }});
      var tables=window.__tables||{{}};
      Object.keys(tables).forEach(function(tbodyId){{
        var tb=document.getElementById(tbodyId);
        if(!tb)return;
        var tbl=tables[tbodyId];
        var ps=tbl.ps||20;
        var rows=filtered.map(function(r){{return tbl.cols.map(function(c){{return r[c]!==undefined?String(r[c]):'';}})}});
        tb.innerHTML=rows.slice(0,ps).map(function(r){{
          return '<tr>'+r.map(function(c){{return '<td style="padding:10px 12px;border-bottom:1px solid {d['card_border']};color:{d['body_color']};">'+c+'</td>';}}).join('')+'</tr>';
        }}).join('');
      }});
    }}
    function sortTable(th){{
      var table=th.closest('table');
      var tbody=table.querySelector('tbody');
      var rows=Array.from(tbody.querySelectorAll('tr'));
      var idx=Array.from(th.parentNode.children).indexOf(th);
      var asc=th.dataset.asc!=='true';
      th.dataset.asc=asc;
      rows.sort(function(a,b){{
        var av=a.cells[idx].textContent,bv=b.cells[idx].textContent;
        var an=parseFloat(av),bn=parseFloat(bv);
        if(!isNaN(an)&&!isNaN(bn))return asc?an-bn:bn-an;
        return asc?av.localeCompare(bv):bv.localeCompare(av);
      }});
      rows.forEach(function(r){{tbody.appendChild(r);}});
    }}
  </script>
</body>
</html>"""
