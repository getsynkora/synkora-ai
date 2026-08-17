"""Unit tests for SandboxComputeSession response envelope normalization."""

from unittest.mock import MagicMock

import httpx
import pytest

from src.services.compute.backends.sandbox_backend import (
    SandboxComputeBackend,
    SandboxComputeSession,
    _parse_response,
)


def _make_response(status_code: int, json_data=None, text: str = "") -> httpx.Response:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text
    if json_data is None:
        resp.json.side_effect = ValueError("no json")
    else:
        resp.json.return_value = json_data
    return resp


@pytest.mark.unit
class TestParseResponse:
    def test_passes_through_app_level_success_envelope(self):
        resp = _make_response(200, {"success": True, "output": "hi"})
        result = _parse_response(resp, {"output": "", "return_code": -1})
        assert result == {"success": True, "output": "hi"}

    def test_passes_through_app_level_failure_envelope(self):
        resp = _make_response(400, {"success": False, "error": "bad request"})
        result = _parse_response(resp, {"output": "", "return_code": -1})
        assert result == {"success": False, "error": "bad request"}

    def test_normalizes_fastapi_detail_error_with_no_success_key(self):
        """Regression: a framework-level 404/500 (e.g. {"detail": "..."}) that never
        reached the sandbox's own success/error handler must not crash callers doing
        result["success"] with a bare KeyError."""
        resp = _make_response(404, {"detail": "Not Found"})
        result = _parse_response(resp, {"entries": []})
        assert result["success"] is False
        assert result["error"] == "Not Found"
        assert result["entries"] == []

    def test_normalizes_non_json_response_body(self):
        resp = _make_response(500, None, text="Internal Server Error")
        result = _parse_response(resp, {"content": "", "total_lines": 0})
        assert result["success"] is False
        assert result["error"] == "Internal Server Error"
        assert result["content"] == ""
        assert result["total_lines"] == 0

    def test_normalizes_empty_body_falls_back_to_status_code(self):
        resp = _make_response(502, None, text="")
        result = _parse_response(resp, {})
        assert result["success"] is False
        assert result["error"] == "HTTP 502"


@pytest.mark.unit
class TestSandboxComputeSessionListDir:
    @pytest.mark.asyncio
    async def test_list_dir_returns_success_key_on_framework_error(self, monkeypatch):
        """Regression for the circuit-breaker KeyError('success') bug: list_dir must
        never return a dict missing "success", even on a raw framework-level error."""
        backend = SandboxComputeBackend(tenant_id="t1", sandbox_url="http://sandbox")
        session = SandboxComputeSession(tenant_id="t1", agent_id="a1", backend=backend)

        resp = _make_response(404, {"detail": "Not Found"})

        async def fake_get(*args, **kwargs):
            return resp

        monkeypatch.setattr("src.services.compute.backends.sandbox_backend._client.get", fake_get)

        result = await session.list_dir(".")
        assert "success" in result
        assert result["success"] is False
        assert result["entries"] == []
