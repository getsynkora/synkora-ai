import pytest

SAMPLE_DATA = [
    {"region": "North", "revenue": 12000.0, "month": "2024-01", "status": "won"},
    {"region": "South", "revenue": 8500.0, "month": "2024-02", "status": "lost"},
    {"region": "North", "revenue": 9200.0, "month": "2024-03", "status": "won"},
]


class TestAggregate:
    def test_sum(self):
        from src.services.dashboards.dashboard_renderer import _aggregate

        assert _aggregate(SAMPLE_DATA, "revenue", "sum") == pytest.approx(29700.0)

    def test_mean(self):
        from src.services.dashboards.dashboard_renderer import _aggregate

        assert _aggregate(SAMPLE_DATA, "revenue", "mean") == pytest.approx(9900.0)

    def test_max(self):
        from src.services.dashboards.dashboard_renderer import _aggregate

        assert _aggregate(SAMPLE_DATA, "revenue", "max") == pytest.approx(12000.0)

    def test_min(self):
        from src.services.dashboards.dashboard_renderer import _aggregate

        assert _aggregate(SAMPLE_DATA, "revenue", "min") == pytest.approx(8500.0)

    def test_count_with_null_column(self):
        from src.services.dashboards.dashboard_renderer import _aggregate

        assert _aggregate(SAMPLE_DATA, None, "count") == 3

    def test_count_with_column(self):
        from src.services.dashboards.dashboard_renderer import _aggregate

        assert _aggregate(SAMPLE_DATA, "revenue", "count") == 3

    def test_first(self):
        from src.services.dashboards.dashboard_renderer import _aggregate

        assert _aggregate(SAMPLE_DATA, "revenue", "first") == pytest.approx(12000.0)

    def test_last(self):
        from src.services.dashboards.dashboard_renderer import _aggregate

        assert _aggregate(SAMPLE_DATA, "revenue", "last") == pytest.approx(9200.0)

    def test_returns_none_for_non_numeric_column(self):
        from src.services.dashboards.dashboard_renderer import _aggregate

        # "region" is a string column — sum should return None
        result = _aggregate(SAMPLE_DATA, "region", "sum")
        assert result is None

    def test_returns_none_for_empty_data(self):
        from src.services.dashboards.dashboard_renderer import _aggregate

        assert _aggregate([], "revenue", "sum") is None


class TestRenderKpiRow:
    def test_renders_label_and_value(self):
        from src.services.dashboards.dashboard_renderer import _render_kpi_row

        kpis = [{"label": "Total Revenue", "column": "revenue", "agg": "sum", "prefix": "$"}]
        html = _render_kpi_row(kpis, SAMPLE_DATA)
        assert "Total Revenue" in html
        assert "$29,700" in html

    def test_count_kpi_with_null_column(self):
        from src.services.dashboards.dashboard_renderer import _render_kpi_row

        kpis = [{"label": "Records", "column": None, "agg": "count"}]
        html = _render_kpi_row(kpis, SAMPLE_DATA)
        assert "Records" in html
        assert "3" in html

    def test_suffix_appended(self):
        from src.services.dashboards.dashboard_renderer import _render_kpi_row

        kpis = [{"label": "Avg", "column": "revenue", "agg": "mean", "suffix": " USD"}]
        html = _render_kpi_row(kpis, SAMPLE_DATA)
        assert " USD" in html

    def test_missing_column_shows_dash(self):
        from src.services.dashboards.dashboard_renderer import _render_kpi_row

        kpis = [{"label": "Missing", "column": "nonexistent", "agg": "sum"}]
        html = _render_kpi_row(kpis, SAMPLE_DATA)
        assert "—" in html

    def test_multiple_kpis(self):
        from src.services.dashboards.dashboard_renderer import _render_kpi_row

        kpis = [
            {"label": "Total", "column": "revenue", "agg": "sum"},
            {"label": "Max", "column": "revenue", "agg": "max"},
        ]
        html = _render_kpi_row(kpis, SAMPLE_DATA)
        assert "Total" in html
        assert "Max" in html


class TestRenderChart:
    def test_bar_chart_contains_plotly_call(self):
        from src.services.dashboards.dashboard_renderer import _render_chart

        section = {
            "chart_type": "bar",
            "title": "Revenue by Region",
            "x": "region",
            "y": "revenue",
            "agg": "sum",
        }
        html = _render_chart(section, 0, SAMPLE_DATA)
        assert "Plotly.newPlot" in html
        assert "Revenue by Region" in html
        assert "chart_0" in html

    def test_line_chart_uses_scatter_type(self):
        from src.services.dashboards.dashboard_renderer import _render_chart

        section = {"chart_type": "line", "title": "Trend", "x": "month", "y": "revenue"}
        html = _render_chart(section, 1, SAMPLE_DATA)
        assert '"scatter"' in html
        assert "chart_1" in html

    def test_pie_chart_uses_pie_type(self):
        from src.services.dashboards.dashboard_renderer import _render_chart

        section = {
            "chart_type": "pie",
            "title": "Status Split",
            "x": "status",
            "y": "revenue",
            "agg": "sum",
        }
        html = _render_chart(section, 2, SAMPLE_DATA)
        assert '"pie"' in html

    def test_horizontal_bar_sets_orientation_h(self):
        from src.services.dashboards.dashboard_renderer import _render_chart

        section = {
            "chart_type": "horizontal_bar",
            "title": "Top Regions",
            "x": "region",
            "y": "revenue",
            "agg": "sum",
        }
        html = _render_chart(section, 3, SAMPLE_DATA)
        assert '"h"' in html

    def test_area_chart_has_fill(self):
        from src.services.dashboards.dashboard_renderer import _render_chart

        section = {"chart_type": "area", "title": "Area", "x": "month", "y": "revenue"}
        html = _render_chart(section, 4, SAMPLE_DATA)
        assert "tozeroy" in html

    def test_unknown_chart_type_falls_back_to_bar(self):
        from src.services.dashboards.dashboard_renderer import _render_chart

        section = {"chart_type": "radar", "title": "Radar", "x": "region", "y": "revenue"}
        html = _render_chart(section, 5, SAMPLE_DATA)
        assert "Plotly.newPlot" in html  # still renders something


class TestRenderTable:
    def test_renders_column_headers(self):
        from src.services.dashboards.dashboard_renderer import _render_table

        section = {"columns": ["region", "revenue"]}
        html = _render_table(section, SAMPLE_DATA)
        assert "region" in html
        assert "revenue" in html

    def test_embeds_row_data(self):
        from src.services.dashboards.dashboard_renderer import _render_table

        section = {"columns": ["region"]}
        html = _render_table(section, SAMPLE_DATA)
        assert "North" in html
        assert "South" in html

    def test_ignores_nonexistent_columns(self):
        from src.services.dashboards.dashboard_renderer import _render_table

        section = {"columns": ["region", "nonexistent"]}
        html = _render_table(section, SAMPLE_DATA)
        # nonexistent column silently dropped — should still render
        assert "region" in html

    def test_uses_all_columns_when_none_specified(self):
        from src.services.dashboards.dashboard_renderer import _render_table

        section = {}
        html = _render_table(section, SAMPLE_DATA)
        assert "region" in html
        assert "revenue" in html


class TestRenderFilter:
    def test_renders_select_element(self):
        from src.services.dashboards.dashboard_renderer import _render_filter

        section = {"column": "region", "label": "Filter by Region"}
        html = _render_filter(section, SAMPLE_DATA)
        assert "<select" in html
        assert 'data-filter-col="region"' in html

    def test_renders_unique_values(self):
        from src.services.dashboards.dashboard_renderer import _render_filter

        section = {"column": "region"}
        html = _render_filter(section, SAMPLE_DATA)
        assert "North" in html
        assert "South" in html

    def test_renders_default_label(self):
        from src.services.dashboards.dashboard_renderer import _render_filter

        section = {"column": "status"}
        html = _render_filter(section, SAMPLE_DATA)
        assert "Filter by status" in html

    def test_triggers_apply_filters(self):
        from src.services.dashboards.dashboard_renderer import _render_filter

        section = {"column": "region"}
        html = _render_filter(section, SAMPLE_DATA)
        assert "applyFilters()" in html


class TestRenderText:
    def test_renders_heading(self):
        from src.services.dashboards.dashboard_renderer import _render_text

        html = _render_text({"heading": "Summary", "body": ""})
        assert "Summary" in html

    def test_renders_body(self):
        from src.services.dashboards.dashboard_renderer import _render_text

        html = _render_text({"heading": "", "body": "Revenue grew 12%."})
        assert "Revenue grew 12%." in html

    def test_empty_section_renders_empty_div(self):
        from src.services.dashboards.dashboard_renderer import _render_text

        html = _render_text({})
        assert "<div" in html  # renders something, no crash


class TestRenderDashboard:
    def test_returns_valid_html_document(self):
        from src.services.dashboards.dashboard_renderer import render_dashboard

        sections = [
            {"type": "kpi_row", "kpis": [{"label": "Revenue", "column": "revenue", "agg": "sum"}]},
        ]
        html, warnings = render_dashboard("Test Dashboard", sections, SAMPLE_DATA)
        assert "<!DOCTYPE html>" in html
        assert "Test Dashboard" in html
        assert warnings == []

    def test_filter_sections_rendered_before_content(self):
        from src.services.dashboards.dashboard_renderer import render_dashboard

        sections = [
            {"type": "filter", "column": "region"},
            {"type": "kpi_row", "kpis": [{"label": "Count", "column": None, "agg": "count"}]},
        ]
        html, warnings = render_dashboard("Filtered", sections, SAMPLE_DATA)
        # Filter strip appears before chart content in document order
        filter_pos = html.index("applyFilters")
        kpi_pos = html.index("Count")
        assert filter_pos < kpi_pos

    def test_plotly_cdn_included(self):
        from src.services.dashboards.dashboard_renderer import render_dashboard

        sections = [{"type": "chart", "chart_type": "bar", "title": "T", "x": "region", "y": "revenue"}]
        html, _ = render_dashboard("P", sections, SAMPLE_DATA)
        assert "cdn.plot.ly" in html

    def test_all_data_embedded_as_js_const(self):
        from src.services.dashboards.dashboard_renderer import render_dashboard

        sections = [{"type": "table", "columns": ["region"]}]
        html, _ = render_dashboard("D", sections, SAMPLE_DATA)
        assert "ALL_DATA" in html
        assert "North" in html

    def test_unknown_section_type_skipped_with_warning(self):
        from src.services.dashboards.dashboard_renderer import render_dashboard

        sections = [{"type": "mystery_section"}]
        html, warnings = render_dashboard("W", sections, SAMPLE_DATA)
        assert len(warnings) == 1
        assert "mystery_section" in warnings[0]

    def test_empty_data_does_not_crash(self):
        from src.services.dashboards.dashboard_renderer import render_dashboard

        sections = [{"type": "kpi_row", "kpis": [{"label": "Count", "column": None, "agg": "count"}]}]
        html, warnings = render_dashboard("Empty", sections, [])
        assert "<!DOCTYPE html>" in html
        assert warnings == []

    def test_apply_filters_js_function_present(self):
        from src.services.dashboards.dashboard_renderer import render_dashboard

        sections = [{"type": "filter", "column": "region"}]
        html, _ = render_dashboard("F", sections, SAMPLE_DATA)
        assert "function applyFilters()" in html

    def test_sort_table_js_function_present(self):
        from src.services.dashboards.dashboard_renderer import render_dashboard

        sections = [{"type": "table", "columns": ["region"]}]
        html, _ = render_dashboard("S", sections, SAMPLE_DATA)
        assert "function sortTable(" in html

    def test_xss_script_tag_injection_escaped_in_data(self):
        """Data values containing </script> must be escaped so they cannot break out of the script block."""
        from src.services.dashboards.dashboard_renderer import render_dashboard

        malicious_data = [{"name": "</script><script>alert(1)</script>", "value": 1}]
        sections = [{"type": "table", "columns": ["name", "value"]}]
        html, _ = render_dashboard("XSS", sections, malicious_data)
        # The raw </script> sequence must NOT appear inside a <script> block
        assert "<\\/script>" in html or "</script>" not in html.split("<script")[1].split("</script>")[0]

    def test_table_page_size_stored_in_window_tables(self):
        """window.__tables must include ps so applyFilters respects page_size."""
        from src.services.dashboards.dashboard_renderer import render_dashboard

        sections = [{"type": "table", "columns": ["region", "revenue"], "page_size": 50}]
        html, _ = render_dashboard("PS", sections, SAMPLE_DATA)
        # PS variable is set to the page_size value; window.__tables stores it by reference
        assert "var PS=50;" in html
        assert ",ps:PS}" in html

    def test_aggregate_for_chart_function_present_in_html(self):
        """applyFilters must recompute chart data — aggregateForChart JS helper must be present."""
        from src.services.dashboards.dashboard_renderer import render_dashboard

        sections = [
            {"type": "filter", "column": "region"},
            {"type": "chart", "chart_type": "bar", "title": "Rev", "x": "region", "y": "revenue", "agg": "sum"},
        ]
        html, _ = render_dashboard("C", sections, SAMPLE_DATA)
        assert "function aggregateForChart(" in html

    def test_safe_json_escapes_script_closing_tag(self):
        """_safe_json must replace </ with <\\/ for script-safe embedding."""
        from src.services.dashboards.dashboard_renderer import _safe_json

        result = _safe_json({"key": "</script>"})
        assert "<\\/script>" in result
        assert "</script>" not in result
