"""MCP HTTP egress: same-origin requests, checked/pinned DNS, no redirects."""

import asyncio
import ipaddress
import os
import socket
from collections.abc import Callable

import httpx


def validate_mcp_url(url: str) -> httpx.URL:
    parsed = httpx.URL(url)
    if parsed.scheme not in {"http", "https"} or not parsed.host or parsed.userinfo:
        raise ValueError("MCP requires an HTTP(S) URL without embedded credentials")
    return parsed


class MCPHTTPTransport(httpx.AsyncBaseTransport):
    def __init__(self, url: str, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.endpoint = validate_mcp_url(url)
        self.transport = transport or httpx.AsyncHTTPTransport(retries=0)
        # Deployment-owned allowlist. Tenants cannot override it through server metadata.
        self.private_hosts = {
            host.strip().lower() for host in os.getenv("MCP_ALLOWED_PRIVATE_HOSTS", "").split(",") if host.strip()
        }

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        endpoint = self.endpoint
        if (request.url.scheme, request.url.host, request.url.port) != (endpoint.scheme, endpoint.host, endpoint.port):
            raise ValueError("MCP requests cannot change the configured origin")
        loop = asyncio.get_running_loop()
        addresses = await loop.getaddrinfo(
            endpoint.host, endpoint.port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
        )
        ips = list(dict.fromkeys(item[4][0] for item in addresses))
        if not ips:
            raise ValueError("MCP destination did not resolve")
        for address in ips:
            ip = ipaddress.ip_address(address)
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
                ip = ip.ipv4_mapped
            # Unconditional blocks — never overridable by private_hosts allowlist
            if ip.is_loopback or ip.is_reserved:
                raise ValueError("MCP destination resolves to a loopback or reserved address")
            if ip.is_link_local or ip.is_multicast or ip.is_unspecified or str(ip) == "fd00:ec2::254":
                raise ValueError("MCP destination is forbidden")
            if not ip.is_global and endpoint.host.lower() not in self.private_hosts:
                raise ValueError("Private MCP destinations require the deployment's explicit hostname allowlist")

        # Connect to the checked address, not a second DNS lookup (rebinding).
        # Preserve the original HTTP Host and TLS certificate/SNI hostname.
        headers = request.headers.copy()
        headers["Host"] = endpoint.netloc.decode("ascii")
        pinned = httpx.Request(
            request.method,
            request.url.copy_with(host=ips[0]),
            headers=headers,
            stream=request.stream,
            extensions={**request.extensions, "sni_hostname": endpoint.host},
        )
        return await self.transport.handle_async_request(pinned)

    async def aclose(self) -> None:
        await self.transport.aclose()


def mcp_http_client_factory(url: str) -> Callable[..., httpx.AsyncClient]:
    validate_mcp_url(url)

    def create(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
        # fastmcp's StreamableHttpTransport calls custom httpx_client_factory
        # implementations with follow_redirects explicitly (fastmcp>=3), which
        # isn't part of mcp's McpHttpClientFactory protocol. Accept it rather
        # than raising. Safe to honor either way: MCPHTTPTransport rejects any
        # request whose origin differs from the configured endpoint, so a
        # followed redirect can't escape to an unpinned host regardless of
        # this flag.
        follow_redirects: bool = False,
    ) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=headers,
            timeout=timeout or httpx.Timeout(30, read=120),
            auth=auth,
            transport=MCPHTTPTransport(url),
            follow_redirects=follow_redirects,
            trust_env=False,
        )

    return create
