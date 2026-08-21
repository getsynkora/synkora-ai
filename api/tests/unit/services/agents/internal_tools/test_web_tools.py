"""
Tests for web_tools.py - Web Tools for Synkora Agents.

Tests SSRF protection and the raw-bytes URL download helper used by tools
(e.g. Slack file upload) that need to re-host a URL's content.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class _FakeStream:
    """Fake async context manager mimicking httpx.AsyncClient.stream()."""

    def __init__(self, response=None, aenter_exception=None):
        self._response = response
        self._aenter_exception = aenter_exception

    async def __aenter__(self):
        if self._aenter_exception:
            raise self._aenter_exception
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _make_response(*, is_redirect=False, status_code=200, headers=None, chunks=()):
    response = MagicMock()
    response.is_redirect = is_redirect
    response.status_code = status_code
    response.reason_phrase = "Not Found"
    response.headers = headers or {}

    async def _aiter_bytes(chunk_size=None):
        for chunk in chunks:
            yield chunk

    response.aiter_bytes = _aiter_bytes
    return response


class TestInternalDownloadUrlBytes:
    """Tests for internal_download_url_bytes."""

    @pytest.mark.asyncio
    async def test_rejects_non_http_url(self):
        from src.services.agents.internal_tools.web_tools import internal_download_url_bytes

        result = await internal_download_url_bytes("ftp://example.com/file.png")

        assert "error" in result
        assert "Invalid URL" in result["error"]

    @pytest.mark.asyncio
    async def test_blocks_unsafe_url_via_ssrf_check(self):
        from src.services.agents.internal_tools.web_tools import internal_download_url_bytes

        with patch("src.services.agents.internal_tools.web_tools._is_url_safe", new_callable=AsyncMock) as mock_safe:
            mock_safe.return_value = (False, "Blocked hostname: localhost")

            result = await internal_download_url_bytes("http://localhost/evil.png")

            assert "error" in result
            assert "blocked" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_downloads_bytes_successfully(self):
        from src.services.agents.internal_tools.web_tools import internal_download_url_bytes

        response = _make_response(headers={"content-type": "image/png"}, chunks=[b"\x89PNG raw bytes"])

        with (
            patch("src.services.agents.internal_tools.web_tools._is_url_safe", new_callable=AsyncMock) as mock_safe,
            patch("httpx.AsyncClient.stream", return_value=_FakeStream(response)),
        ):
            mock_safe.return_value = (True, None)

            result = await internal_download_url_bytes("https://s3.example.com/screenshot.png")

            assert result["content"] == b"\x89PNG raw bytes"
            assert result["content_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_rejects_redirect_response(self):
        from src.services.agents.internal_tools.web_tools import internal_download_url_bytes

        response = _make_response(is_redirect=True)

        with (
            patch("src.services.agents.internal_tools.web_tools._is_url_safe", new_callable=AsyncMock) as mock_safe,
            patch("httpx.AsyncClient.stream", return_value=_FakeStream(response)),
        ):
            mock_safe.return_value = (True, None)

            result = await internal_download_url_bytes("https://example.com/redirect")

            assert "error" in result
            assert "Redirect" in result["error"]

    @pytest.mark.asyncio
    async def test_rejects_http_error_status(self):
        from src.services.agents.internal_tools.web_tools import internal_download_url_bytes

        response = _make_response(status_code=404)

        with (
            patch("src.services.agents.internal_tools.web_tools._is_url_safe", new_callable=AsyncMock) as mock_safe,
            patch("httpx.AsyncClient.stream", return_value=_FakeStream(response)),
        ):
            mock_safe.return_value = (True, None)

            result = await internal_download_url_bytes("https://example.com/missing.png")

            assert "error" in result
            assert "404" in result["error"]

    @pytest.mark.asyncio
    async def test_rejects_content_exceeding_max_bytes(self):
        from src.services.agents.internal_tools.web_tools import internal_download_url_bytes

        response = _make_response(headers={"content-type": "image/png"}, chunks=[b"x" * 100])

        with (
            patch("src.services.agents.internal_tools.web_tools._is_url_safe", new_callable=AsyncMock) as mock_safe,
            patch("httpx.AsyncClient.stream", return_value=_FakeStream(response)),
        ):
            mock_safe.return_value = (True, None)

            result = await internal_download_url_bytes("https://example.com/huge.png", max_bytes=50)

            assert "error" in result
            assert "exceeds" in result["error"]

    @pytest.mark.asyncio
    async def test_aborts_streaming_early_without_reading_entire_body(self):
        """A response exceeding max_bytes should stop pulling chunks early, not buffer it all first."""
        from src.services.agents.internal_tools.web_tools import internal_download_url_bytes

        chunks_yielded = []

        async def _endless_chunks(chunk_size=None):
            for _ in range(10_000):
                chunks_yielded.append(1)
                yield b"x" * 1024

        response = MagicMock()
        response.is_redirect = False
        response.status_code = 200
        response.headers = {"content-type": "application/octet-stream"}
        response.aiter_bytes = _endless_chunks

        with (
            patch("src.services.agents.internal_tools.web_tools._is_url_safe", new_callable=AsyncMock) as mock_safe,
            patch("httpx.AsyncClient.stream", return_value=_FakeStream(response)),
        ):
            mock_safe.return_value = (True, None)

            result = await internal_download_url_bytes("https://example.com/huge.bin", max_bytes=2048)

            assert "error" in result
            assert "exceeds" in result["error"]
            # Should abort within a couple chunks past the cap, not consume all 10,000
            assert len(chunks_yielded) < 10

    @pytest.mark.asyncio
    async def test_handles_timeout(self):
        from src.services.agents.internal_tools.web_tools import internal_download_url_bytes

        with (
            patch("src.services.agents.internal_tools.web_tools._is_url_safe", new_callable=AsyncMock) as mock_safe,
            patch(
                "httpx.AsyncClient.stream",
                return_value=_FakeStream(aenter_exception=httpx.TimeoutException("timed out")),
            ),
        ):
            mock_safe.return_value = (True, None)

            result = await internal_download_url_bytes("https://example.com/slow.png")

            assert "error" in result
            assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_blocks_domain_via_platform_blocklist(self):
        from src.services.agents.internal_tools.web_tools import internal_download_url_bytes

        with (
            patch("src.services.agents.internal_tools.web_tools._is_url_safe", new_callable=AsyncMock) as mock_safe,
            patch(
                "src.services.agents.internal_tools.web_tools._load_platform_blocked_domains",
                return_value=["evil.com"],
            ),
        ):
            mock_safe.return_value = (True, None)

            result = await internal_download_url_bytes("https://evil.com/file.png")

            assert "error" in result
            assert "blocked" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_blocks_domain_via_config_blocklist(self):
        from src.services.agents.internal_tools.web_tools import internal_download_url_bytes

        with patch("src.services.agents.internal_tools.web_tools._is_url_safe", new_callable=AsyncMock) as mock_safe:
            mock_safe.return_value = (True, None)

            result = await internal_download_url_bytes(
                "https://evil.com/file.png", config={"blocked_domains": ["evil.com"]}
            )

            assert "error" in result
            assert "blocked" in result["error"].lower()
