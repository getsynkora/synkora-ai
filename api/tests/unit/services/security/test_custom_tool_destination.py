"""Capture real executor requests without contacting external services."""

from unittest.mock import MagicMock

import httpx
import pytest

from src.services.agents.security import encrypt_value
from src.services.custom_tools import OpenAPIParser, ToolExecutor


def executor(path="/{record_id}"):
    schema = {
        "openapi": "3.0.0",
        "info": {"title": "Synthetic", "version": "1"},
        "paths": {
            path: {
                "get": {
                    "operationId": "read",
                    "parameters": [{"name": "record_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    return ToolExecutor(
        OpenAPIParser(schema, server_url="https://business.example.invalid"),
        "bearer",
        {"token": encrypt_value("synthetic-secret")},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        "123",
        "/attacker.example.invalid/collect",
        "//attacker.example.invalid",
        "https://attacker.example.invalid",
        "a/b",
        "a?query#fragment",
        "a b",
        "%2F%2Fattacker.example.invalid",
        "a\\b",
        "café",
    ],
)
async def test_path_values_remain_data_on_configured_host(monkeypatch, value):
    captured = []

    async def capture(request):
        captured.append(request)
        return httpx.Response(200, json={"ok": True})

    original = httpx.AsyncClient
    monkeypatch.setattr("src.services.custom_tools.tool_executor.validate_url", lambda *args, **kwargs: (True, None))
    monkeypatch.setattr(
        "src.services.custom_tools.tool_executor.httpx.AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(capture)),
    )
    result = await executor().execute("read", {"record_id": value})
    assert result["success"]
    assert len(captured) == 1
    request = captured[0]
    assert request.url.host == "business.example.invalid"
    assert request.url.query == b"" and request.url.fragment == ""
    assert request.headers["Authorization"] == "Bearer synthetic-secret"
    from urllib.parse import quote

    assert request.url.raw_path == ("/" + quote(value, safe="")).encode()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "//attacker.example.invalid/collect",
        "https://attacker.example.invalid/collect",
        "http://business.example.invalid/collect",
        "https://business.example.invalid:444/collect",
        "https://user:pass@business.example.invalid/collect",
    ],
)
async def test_origin_change_rejected_before_decryption_or_http(monkeypatch, path):
    tool = executor(path)
    headers = MagicMock(side_effect=AssertionError("Credentials must not be loaded"))
    client = MagicMock(side_effect=AssertionError("HTTP must not start"))
    monkeypatch.setattr(tool, "_build_headers", headers)
    monkeypatch.setattr("src.services.custom_tools.tool_executor.httpx.AsyncClient", client)
    result = await tool.execute("read", {"record_id": "123"})
    assert result["success"] is False
    headers.assert_not_called()
    client.assert_not_called()
