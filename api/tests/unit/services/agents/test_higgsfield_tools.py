"""Unit tests for Higgsfield image/video generation tools."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.agents.internal_tools import higgsfield_tools as hf

CFG = {
    "token": "id:secret",
    "tenant_id": "t1",
    "image_model": hf.DEFAULT_IMAGE_MODEL,
    "video_model": hf.DEFAULT_VIDEO_MODEL,
    "image_to_video_model": hf.DEFAULT_IMAGE_TO_VIDEO_MODEL,
    "timeout": 5.0,
}


def _mock_transport(handler):
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    return patch.object(hf.httpx, "AsyncClient", factory)


@pytest.fixture(autouse=True)
def _fast_poll(monkeypatch):
    monkeypatch.setattr(hf, "_POLL_INTERVAL_S", 0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_image_generation_polls_until_completed():
    calls = {"polls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Key id:secret"
        if request.method == "POST":
            return httpx.Response(
                200, json={"request_id": "r1", "status_url": "https://api.higgsfield.ai/requests/r1/status"}
            )
        calls["polls"] += 1
        if calls["polls"] < 2:
            return httpx.Response(200, json={"status": "in_progress"})
        return httpx.Response(200, json={"status": "completed", "images": [{"url": "https://cdn/x.png"}]})

    with (
        _mock_transport(handler),
        patch.object(hf, "_get_higgsfield_config", AsyncMock(return_value=CFG)),
        patch.object(hf, "_persist", AsyncMock(side_effect=lambda url, *_a: url)),
    ):
        result = await hf.internal_higgsfield_generate_image("a cat", runtime_context=object())

    assert result["success"] is True
    assert result["url"] == "https://cdn/x.png"
    assert result["request_id"] == "r1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_video_uses_image_to_video_endpoint_without_aspect_ratio():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            seen["path"] = request.url.path
            seen["body"] = request.read().decode()
            return httpx.Response(200, json={"request_id": "r2"})
        return httpx.Response(200, json={"status": "completed", "video": {"url": "https://cdn/v.mp4"}})

    with (
        _mock_transport(handler),
        patch.object(hf, "_get_higgsfield_config", AsyncMock(return_value=CFG)),
        patch.object(hf, "_persist", AsyncMock(side_effect=lambda url, *_a: url)),
    ):
        result = await hf.internal_higgsfield_generate_video(
            "pan left", image_url="https://img/a.png", aspect_ratio="9:16", duration=99, runtime_context=object()
        )

    assert result["video_url"] == "https://cdn/v.mp4"
    assert seen["path"].endswith("image-to-video")
    assert "aspect_ratio" not in seen["body"]
    assert '"duration":15' in seen["body"].replace(" ", "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_nsfw_and_http_error_are_reported():
    def nsfw(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"request_id": "r3"})
        return httpx.Response(200, json={"status": "nsfw"})

    with _mock_transport(nsfw), patch.object(hf, "_get_higgsfield_config", AsyncMock(return_value=CFG)):
        result = await hf.internal_higgsfield_generate_image("x", runtime_context=object())
    assert result["success"] is False and "moderation" in result["error"]

    def bad(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    with _mock_transport(bad), patch.object(hf, "_get_higgsfield_config", AsyncMock(return_value=CFG)):
        result = await hf.internal_higgsfield_generate_image("x", runtime_context=object())
    assert result["success"] is False and "401" in result["error"]
