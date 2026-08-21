"""Builders for Slack Block Kit block types not covered by formatters.py.

Pure functions, no side effects — same style as formatters.py. Covers the
`card`, `video`, and `data_visualization` blocks documented at
https://docs.slack.dev/reference/block-kit.
"""

from __future__ import annotations

from src.services.slack.slack_chart_renderer import normalize_chart_dict

CARD_TITLE_MAX = 150
CARD_SUBTITLE_MAX = 150
CARD_BODY_MAX = 200
CARD_MAX_ACTIONS = 3

VIDEO_TITLE_MAX = 200
VIDEO_DESCRIPTION_MAX = 200

DATA_VIZ_TITLE_MAX = 50
DATA_VIZ_LABEL_MAX = 20
DATA_VIZ_MAX_SERIES = 12
DATA_VIZ_MAX_POINTS_PER_SERIES = 20
DATA_VIZ_MAX_BLOCKS_PER_MESSAGE = 2
_DATA_VIZ_NATIVE_TYPES = {"bar", "line", "area", "pie"}


def _truncate(text: str, max_len: int) -> str:
    return text[:max_len]


def build_card_block(
    title: str,
    body: str | None = None,
    subtitle: str | None = None,
    hero_image_url: str | None = None,
    icon_url: str | None = None,
    actions: list[dict] | None = None,
    block_id: str | None = None,
) -> dict:
    block: dict = {
        "type": "card",
        "title": {"type": "mrkdwn", "text": _truncate(title, CARD_TITLE_MAX), "verbatim": False},
    }
    if block_id is not None:
        block["block_id"] = block_id
    if icon_url is not None:
        block["icon"] = {"type": "image", "image_url": icon_url, "alt_text": "icon"}
    if subtitle is not None:
        block["subtitle"] = {"type": "mrkdwn", "text": _truncate(subtitle, CARD_SUBTITLE_MAX), "verbatim": False}
    if hero_image_url is not None:
        block["hero_image"] = {
            "type": "image",
            "image_url": hero_image_url,
            "alt_text": _truncate(title, CARD_TITLE_MAX),
        }
    if body is not None:
        block["body"] = {"type": "mrkdwn", "text": _truncate(body, CARD_BODY_MAX), "verbatim": False}
    if actions is not None:
        block["actions"] = actions[:CARD_MAX_ACTIONS]
    return block


def build_video_block(
    video_url: str,
    thumbnail_url: str,
    title: str,
    title_url: str | None = None,
    description: str | None = None,
    author_name: str | None = None,
) -> dict:
    truncated_title = _truncate(title, VIDEO_TITLE_MAX)
    block: dict = {
        "type": "video",
        "video_url": video_url,
        "thumbnail_url": thumbnail_url,
        "title": {"type": "plain_text", "text": truncated_title, "emoji": True},
        "alt_text": truncated_title,
        "provider_name": "YouTube",
    }
    if title_url is not None:
        block["title_url"] = title_url
    if description is not None:
        block["description"] = {
            "type": "plain_text",
            "text": _truncate(description, VIDEO_DESCRIPTION_MAX),
            "emoji": True,
        }
    if author_name is not None:
        block["author_name"] = author_name
    return block


def _build_pie_chart(labels: list, datasets: list) -> dict | None:
    values = datasets[0].get("data") or [] if datasets else []
    segments = [
        {"label": _truncate(str(label), DATA_VIZ_LABEL_MAX), "value": value}
        for label, value in zip(labels, values, strict=False)
    ]
    if not segments or len(segments) > DATA_VIZ_MAX_SERIES:
        return None
    return {"type": "pie", "segments": segments}


def _build_series_chart(chart_type: str, labels: list, datasets: list) -> dict | None:
    if not datasets or len(datasets) > DATA_VIZ_MAX_SERIES:
        return None
    series = []
    for dataset in datasets:
        values = dataset.get("data") or []
        if len(values) == 0 or len(values) > DATA_VIZ_MAX_POINTS_PER_SERIES:
            return None
        name = _truncate(str(dataset.get("label") or ""), DATA_VIZ_LABEL_MAX)
        data_points = [
            {"label": _truncate(str(label), DATA_VIZ_LABEL_MAX), "value": value}
            for label, value in zip(labels, values, strict=False)
        ]
        series.append({"name": name, "data": data_points})
    categories = [_truncate(str(label), DATA_VIZ_LABEL_MAX) for label in labels]
    return {"type": chart_type, "series": series, "axis_config": {"categories": categories}}


def build_data_visualization_block(chart: dict) -> dict | None:
    normalized = normalize_chart_dict(chart)
    chart_type = (normalized.get("chart_type") or "").lower()
    if chart_type not in _DATA_VIZ_NATIVE_TYPES:
        return None

    data = normalized.get("data") or {}
    labels = data.get("labels") or []
    datasets = data.get("datasets") or []

    if chart_type == "pie":
        native_chart = _build_pie_chart(labels, datasets)
    else:
        native_chart = _build_series_chart(chart_type, labels, datasets)

    if native_chart is None:
        return None

    return {
        "type": "data_visualization",
        "title": _truncate(str(normalized.get("title") or ""), DATA_VIZ_TITLE_MAX),
        "chart": native_chart,
    }
