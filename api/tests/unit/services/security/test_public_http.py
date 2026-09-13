import socket
from unittest.mock import AsyncMock

import httpx
import pytest

from src.services.mcp.http_transport import MCPHTTPTransport
from src.services.security import public_http


@pytest.mark.asyncio
@pytest.mark.parametrize("destination", ["127.0.0.1", "169.254.169.254", "10.0.0.1", "::1"])
async def test_private_post_never_reaches_network(monkeypatch, destination):
    import asyncio

    monkeypatch.setattr(
        asyncio.get_running_loop(),
        "getaddrinfo",
        AsyncMock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (destination, 80))]),
    )
    sent = AsyncMock()
    monkeypatch.setenv("MCP_ALLOWED_PRIVATE_HOSTS", "callback.example")
    monkeypatch.setattr(
        public_http, "MCPHTTPTransport", lambda url: MCPHTTPTransport(url, transport=httpx.MockTransport(sent))
    )
    with pytest.raises(ValueError):
        await public_http.post_public_json("http://callback.example", {"topic": "private"})
    sent.assert_not_called()


@pytest.mark.asyncio
async def test_callback_post_does_not_follow_redirects_or_leak_credentials(monkeypatch):
    import asyncio

    monkeypatch.setattr(
        asyncio.get_running_loop(),
        "getaddrinfo",
        AsyncMock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]),
    )
    sent = []

    async def redirect(request):
        sent.append(request)
        return httpx.Response(307, headers={"Location": "https://other.example"})

    monkeypatch.setattr(
        public_http, "MCPHTTPTransport", lambda url: MCPHTTPTransport(url, transport=httpx.MockTransport(redirect))
    )
    with pytest.raises(httpx.HTTPStatusError):
        await public_http.post_public_json(
            "https://callback.example", {"data": "private"}, headers={"Authorization": "Bearer secret"}
        )
    assert len(sent) == 1

    async def content(request):
        return httpx.Response(200, content=b"123456")

    monkeypatch.setattr(
        public_http, "MCPHTTPTransport", lambda url: MCPHTTPTransport(url, transport=httpx.MockTransport(content))
    )
    with pytest.raises(ValueError, match="size limit"):
        await public_http.post_public_json("https://callback.example", {}, max_bytes=5)
    assert (await public_http.post_public_json("https://callback.example", {}, max_bytes=6)).text == "123456"


@pytest.mark.asyncio
@pytest.mark.parametrize("destination", ["127.0.0.1", "169.254.169.254", "10.0.0.1", "::1"])
async def test_private_feed_never_reaches_network(monkeypatch, destination):
    import asyncio

    loop = asyncio.get_running_loop()
    monkeypatch.setattr(
        loop, "getaddrinfo", AsyncMock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (destination, 80))])
    )
    sent = AsyncMock()
    monkeypatch.setenv("MCP_ALLOWED_PRIVATE_HOSTS", "feed.example")
    monkeypatch.setattr(
        public_http, "MCPHTTPTransport", lambda url: MCPHTTPTransport(url, transport=httpx.MockTransport(sent))
    )
    with pytest.raises(ValueError):
        await public_http.fetch_public_url("http://feed.example")
    sent.assert_not_called()


@pytest.mark.asyncio
async def test_redirect_to_private_host_blocked_and_response_size_bounded(monkeypatch):
    import asyncio

    async def resolve(host, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1" if host == "private.example" else "8.8.8.8", 80))
        ]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolve)
    seen = []

    async def send(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "http://private.example/"})

    monkeypatch.setattr(
        public_http, "MCPHTTPTransport", lambda url: MCPHTTPTransport(url, transport=httpx.MockTransport(send))
    )
    with pytest.raises(ValueError):
        await public_http.fetch_public_url("http://public.example")
    assert len(seen) == 1

    async def content(request):
        return httpx.Response(200, content=b"123456")

    monkeypatch.setattr(
        public_http, "MCPHTTPTransport", lambda url: MCPHTTPTransport(url, transport=httpx.MockTransport(content))
    )
    with pytest.raises(ValueError, match="size limit"):
        await public_http.fetch_public_url("http://public.example", max_bytes=5)
    assert (await public_http.fetch_public_url("http://public.example", max_bytes=6)).text == "123456"
