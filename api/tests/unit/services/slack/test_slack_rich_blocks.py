from src.services.slack.slack_rich_blocks import (
    build_card_block,
    build_data_visualization_block,
    build_video_block,
)


class TestBuildCardBlock:
    def test_minimal_title_only(self):
        block = build_card_block(title="Lumon Industries")
        assert block == {
            "type": "card",
            "title": {"type": "mrkdwn", "text": "Lumon Industries", "verbatim": False},
        }

    def test_all_fields(self):
        actions = [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Open", "emoji": False},
                "action_id": "open_action",
                "url": "https://example.com",
            }
        ]
        block = build_card_block(
            title="Lumon Industries",
            body="Please enjoy each card equally.",
            subtitle="Committed to work-life balance",
            hero_image_url="https://picsum.photos/400/300",
            icon_url="https://picsum.photos/36/36",
            actions=actions,
            block_id="card_1",
        )
        assert block == {
            "type": "card",
            "block_id": "card_1",
            "icon": {"type": "image", "image_url": "https://picsum.photos/36/36", "alt_text": "icon"},
            "title": {"type": "mrkdwn", "text": "Lumon Industries", "verbatim": False},
            "subtitle": {"type": "mrkdwn", "text": "Committed to work-life balance", "verbatim": False},
            "hero_image": {
                "type": "image",
                "image_url": "https://picsum.photos/400/300",
                "alt_text": "Lumon Industries",
            },
            "body": {"type": "mrkdwn", "text": "Please enjoy each card equally.", "verbatim": False},
            "actions": actions,
        }

    def test_title_truncated_to_150_chars(self):
        block = build_card_block(title="a" * 200)
        assert block["title"]["text"] == "a" * 150

    def test_subtitle_truncated_to_150_chars(self):
        block = build_card_block(title="Title", subtitle="b" * 200)
        assert block["subtitle"]["text"] == "b" * 150

    def test_body_truncated_to_200_chars(self):
        block = build_card_block(title="Title", body="c" * 300)
        assert block["body"]["text"] == "c" * 200

    def test_actions_truncated_to_3_buttons(self):
        actions = [{"type": "button", "text": {"type": "plain_text", "text": f"B{i}"}} for i in range(5)]
        block = build_card_block(title="Title", actions=actions)
        assert len(block["actions"]) == 3
        assert block["actions"] == actions[:3]

    def test_omits_optional_fields_when_not_provided(self):
        block = build_card_block(title="Title")
        assert "body" not in block
        assert "subtitle" not in block
        assert "hero_image" not in block
        assert "icon" not in block
        assert "actions" not in block
        assert "block_id" not in block


class TestBuildVideoBlock:
    def test_minimal_required_fields(self):
        block = build_video_block(
            video_url="https://www.youtube.com/embed/8876OZV_Yy0",
            thumbnail_url="https://i.ytimg.com/vi/8876OZV_Yy0/hqdefault.jpg",
            title="Use the Events API to create a dynamic App Home",
        )
        assert block == {
            "type": "video",
            "video_url": "https://www.youtube.com/embed/8876OZV_Yy0",
            "thumbnail_url": "https://i.ytimg.com/vi/8876OZV_Yy0/hqdefault.jpg",
            "title": {
                "type": "plain_text",
                "text": "Use the Events API to create a dynamic App Home",
                "emoji": True,
            },
            "alt_text": "Use the Events API to create a dynamic App Home",
            "provider_name": "YouTube",
        }

    def test_all_fields(self):
        block = build_video_block(
            video_url="https://www.youtube.com/embed/8876OZV_Yy0",
            thumbnail_url="https://i.ytimg.com/vi/8876OZV_Yy0/hqdefault.jpg",
            title="Title",
            title_url="https://www.youtube.com/watch?v=8876OZV_Yy0",
            description="Slack sure is nifty!",
            author_name="Slack",
        )
        assert block["title_url"] == "https://www.youtube.com/watch?v=8876OZV_Yy0"
        assert block["description"] == {"type": "plain_text", "text": "Slack sure is nifty!", "emoji": True}
        assert block["author_name"] == "Slack"
        assert block["provider_name"] == "YouTube"

    def test_title_truncated_to_200_chars(self):
        block = build_video_block(
            video_url="https://www.youtube.com/embed/x",
            thumbnail_url="https://i.ytimg.com/vi/x/hqdefault.jpg",
            title="t" * 300,
        )
        assert block["title"]["text"] == "t" * 200
        assert block["alt_text"] == "t" * 200

    def test_description_truncated_to_200_chars(self):
        block = build_video_block(
            video_url="https://www.youtube.com/embed/x",
            thumbnail_url="https://i.ytimg.com/vi/x/hqdefault.jpg",
            title="Title",
            description="d" * 300,
        )
        assert block["description"]["text"] == "d" * 200

    def test_omits_optional_fields_when_not_provided(self):
        block = build_video_block(
            video_url="https://www.youtube.com/embed/x",
            thumbnail_url="https://i.ytimg.com/vi/x/hqdefault.jpg",
            title="Title",
        )
        assert "title_url" not in block
        assert "description" not in block
        assert "author_name" not in block


def _bar_chart(labels, datasets, title="Chart", chart_type="bar"):
    return {
        "chart_type": chart_type,
        "library": "chartjs",
        "title": title,
        "data": {"labels": labels, "datasets": datasets},
    }


def _pie_chart(labels, values, title="Pie Chart"):
    return {
        "chart_type": "pie",
        "library": "chartjs",
        "title": title,
        "data": {"labels": labels, "datasets": [{"data": values}]},
    }


class TestBuildDataVisualizationBlock:
    def test_builds_bar_chart(self):
        chart = _bar_chart(["A", "B"], [{"label": "S1", "data": [1, 2]}])
        block = build_data_visualization_block(chart)
        assert block == {
            "type": "data_visualization",
            "title": "Chart",
            "chart": {
                "type": "bar",
                "series": [{"name": "S1", "data": [{"label": "A", "value": 1}, {"label": "B", "value": 2}]}],
                "axis_config": {"categories": ["A", "B"]},
            },
        }

    def test_builds_line_chart(self):
        chart = _bar_chart(["A", "B"], [{"label": "S1", "data": [1, 2]}], chart_type="line")
        block = build_data_visualization_block(chart)
        assert block["chart"]["type"] == "line"

    def test_builds_area_chart(self):
        chart = _bar_chart(["A", "B"], [{"label": "S1", "data": [1, 2]}], chart_type="area")
        block = build_data_visualization_block(chart)
        assert block["chart"]["type"] == "area"

    def test_builds_multi_series_bar_chart(self):
        chart = _bar_chart(["A", "B"], [{"label": "S1", "data": [1, 2]}, {"label": "S2", "data": [3, 4]}])
        block = build_data_visualization_block(chart)
        assert len(block["chart"]["series"]) == 2
        assert block["chart"]["series"][1]["name"] == "S2"

    def test_builds_pie_chart(self):
        chart = _pie_chart(["Kit Kat", "Twix"], [45, 28])
        block = build_data_visualization_block(chart)
        assert block == {
            "type": "data_visualization",
            "title": "Pie Chart",
            "chart": {
                "type": "pie",
                "segments": [{"label": "Kit Kat", "value": 45}, {"label": "Twix", "value": 28}],
            },
        }

    def test_returns_none_for_doughnut(self):
        chart = _pie_chart(["A"], [1])
        chart["chart_type"] = "doughnut"
        assert build_data_visualization_block(chart) is None

    def test_returns_none_for_scatter(self):
        chart = _bar_chart(["A"], [{"label": "S1", "data": [1]}], chart_type="scatter")
        assert build_data_visualization_block(chart) is None

    def test_returns_none_for_horizontalbar(self):
        chart = _bar_chart(["A"], [{"label": "S1", "data": [1]}], chart_type="horizontalBar")
        assert build_data_visualization_block(chart) is None

    def test_returns_none_when_series_has_zero_points(self):
        chart = _bar_chart(["A"], [{"label": "S1", "data": []}])
        assert build_data_visualization_block(chart) is None

    def test_returns_none_when_series_has_more_than_20_points(self):
        labels = [f"L{i}" for i in range(21)]
        chart = _bar_chart(labels, [{"label": "S1", "data": list(range(21))}])
        assert build_data_visualization_block(chart) is None

    def test_returns_none_when_more_than_12_series(self):
        datasets = [{"label": f"S{i}", "data": [1]} for i in range(13)]
        chart = _bar_chart(["A"], datasets)
        assert build_data_visualization_block(chart) is None

    def test_returns_none_when_more_than_12_pie_segments(self):
        labels = [f"L{i}" for i in range(13)]
        values = list(range(1, 14))
        chart = _pie_chart(labels, values)
        assert build_data_visualization_block(chart) is None

    def test_returns_none_for_empty_pie_segments(self):
        chart = _pie_chart([], [])
        assert build_data_visualization_block(chart) is None

    def test_title_truncated_to_50_chars(self):
        chart = _bar_chart(["A"], [{"label": "S1", "data": [1]}], title="t" * 100)
        block = build_data_visualization_block(chart)
        assert block["title"] == "t" * 50

    def test_series_name_truncated_to_20_chars(self):
        chart = _bar_chart(["A"], [{"label": "s" * 30, "data": [1]}])
        block = build_data_visualization_block(chart)
        assert block["chart"]["series"][0]["name"] == "s" * 20

    def test_category_label_truncated_to_20_chars(self):
        chart = _bar_chart(["l" * 30], [{"label": "S1", "data": [1]}])
        block = build_data_visualization_block(chart)
        assert block["chart"]["axis_config"]["categories"] == ["l" * 20]
        assert block["chart"]["series"][0]["data"][0]["label"] == "l" * 20

    def test_pie_segment_label_truncated_to_20_chars(self):
        chart = _pie_chart(["l" * 30], [1])
        block = build_data_visualization_block(chart)
        assert block["chart"]["segments"][0]["label"] == "l" * 20
