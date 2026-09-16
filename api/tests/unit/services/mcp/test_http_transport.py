import asyncio
import socket
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.mcp.http_transport import MCPHTTPTransport, mcp_http_client_factory, validate_mcp_url


def resolved(*ips):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ips]


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://user:secret@example.com", "ftp://example.com", ""])
def test_invalid_destination(url):
    with pytest.raises(ValueError):
        validate_mcp_url(url)


@pytest.mark.asyncio
@pytest.mark.parametrize("ips", [("127.0.0.1",), ("169.254.169.254",), ("8.8.8.8", "10.0.0.1")])
async def test_forbidden_resolution_never_connects(ips, monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_PRIVATE_HOSTS", raising=False)
    inner = AsyncMock(spec=httpx.AsyncBaseTransport)
    transport = MCPHTTPTransport("https://tools.example.com/mcp", transport=inner)
    with patch.object(asyncio.get_running_loop(), "getaddrinfo", AsyncMock(return_value=resolved(*ips))):
        with pytest.raises(ValueError):
            await transport.handle_async_request(httpx.Request("POST", "https://tools.example.com/mcp"))
    inner.handle_async_request.assert_not_called()


@pytest.mark.asyncio
async def test_connection_is_pinned_and_tls_identity_preserved():
    inner = AsyncMock(spec=httpx.AsyncBaseTransport)
    transport = MCPHTTPTransport("https://tools.example.com/mcp", transport=inner)
    dns = AsyncMock(return_value=resolved("8.8.8.8"))
    with patch.object(asyncio.get_running_loop(), "getaddrinfo", dns):
        await transport.handle_async_request(httpx.Request("POST", "https://tools.example.com/mcp", content=b"hello"))
    sent = inner.handle_async_request.call_args.args[0]
    assert sent.url.host == "8.8.8.8"
    assert sent.headers["host"] == "tools.example.com"
    assert sent.extensions["sni_hostname"] == "tools.example.com"
    dns.assert_awaited_once()


@pytest.mark.asyncio
async def test_private_allowlist_is_exact_and_metadata_stays_blocked(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_PRIVATE_HOSTS", "tools.internal")
    inner = AsyncMock(spec=httpx.AsyncBaseTransport)
    transport = MCPHTTPTransport("https://tools.internal/mcp", transport=inner)
    with patch.object(asyncio.get_running_loop(), "getaddrinfo", AsyncMock(return_value=resolved("10.0.0.5"))):
        await transport.handle_async_request(httpx.Request("POST", "https://tools.internal/mcp"))
    with patch.object(asyncio.get_running_loop(), "getaddrinfo", AsyncMock(return_value=resolved("169.254.169.254"))):
        with pytest.raises(ValueError):
            await transport.handle_async_request(httpx.Request("POST", "https://tools.internal/mcp"))
    assert inner.handle_async_request.await_count == 1


@pytest.mark.asyncio
async def test_origin_change_is_rejected_before_dns():
    transport = MCPHTTPTransport("https://tools.example.com/mcp", transport=AsyncMock())
    with patch.object(asyncio.get_running_loop(), "getaddrinfo", AsyncMock()) as dns:
        with pytest.raises(ValueError):
            await transport.handle_async_request(httpx.Request("POST", "https://elsewhere.example.com/mcp"))
    dns.assert_not_called()


@pytest.mark.asyncio
async def test_client_does_not_follow_redirects():
    async with mcp_http_client_factory("https://tools.example.com/mcp")() as client:
        assert client.follow_redirects is False
        assert client.trust_env is False


@pytest.mark.asyncio
async def test_factory_accepts_follow_redirects_kwarg_from_fastmcp():
    # fastmcp's StreamableHttpTransport calls custom httpx_client_factory
    # implementations with an explicit follow_redirects kwarg that isn't part
    # of mcp's McpHttpClientFactory protocol. The factory must accept it
    # instead of raising TypeError, and honor the requested value: a followed
    # redirect can't escape to an unpinned host anyway, since
    # MCPHTTPTransport rejects any request whose origin differs from the
    # configured endpoint regardless of this flag.
    async with mcp_http_client_factory("https://tools.example.com/mcp")(follow_redirects=True) as client:
        assert client.follow_redirects is True
