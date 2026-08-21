from src.services.slack.slack_chart_renderer import normalize_chart_dict


class TestNormalizeChartDict:
    def test_passes_through_already_standard_shape(self):
        chart = {
            "chart_type": "bar",
            "library": "chartjs",
            "title": "My Chart",
            "data": {"labels": ["A", "B"], "datasets": [{"label": "S1", "data": [1, 2]}]},
        }
        normalized = normalize_chart_dict(chart)
        assert normalized["chart_type"] == "bar"
        assert normalized["title"] == "My Chart"
        assert normalized["data"] == {"labels": ["A", "B"], "datasets": [{"label": "S1", "data": [1, 2]}]}

    def test_normalizes_internal_generate_chart_event_shape(self):
        chart = {
            "chart_id": "abc",
            "chart_type": "line",
            "chart_config": {"type": "line", "title": "Config Title", "data": {"labels": ["X"], "datasets": []}},
            "chart_data": {},
        }
        normalized = normalize_chart_dict(chart)
        assert normalized["chart_type"] == "line"
        assert normalized["library"] == "chartjs"
        assert normalized["title"] == "Config Title"
        assert normalized["data"] == {"labels": ["X"], "datasets": []}

    def test_prefers_chart_data_over_nested_config_data_when_present(self):
        chart = {
            "chart_config": {"type": "bar", "data": {"labels": ["nested"], "datasets": []}},
            "chart_data": {"labels": ["direct"], "datasets": [{"label": "S", "data": [1]}]},
        }
        normalized = normalize_chart_dict(chart)
        assert normalized["data"] == {"labels": ["direct"], "datasets": [{"label": "S", "data": [1]}]}

    def test_defaults_chart_type_to_bar_when_missing(self):
        chart = {"chart_config": {}, "chart_data": {}}
        normalized = normalize_chart_dict(chart)
        assert normalized["chart_type"] == "bar"
