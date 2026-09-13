"""Bounded fetching of untrusted public URLs with DNS pinning on every redirect."""

import asyncio

import httpx

from src.services.mcp.http_transport import MCPHTTPTransport, validate_mcp_url


async def request_checked_url(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    json: dict | None = None,
    data: dict | None = None,
    content: bytes | None = None,
    auth: tuple[str, str] | None = None,
    timeout: float = 10,
    max_bytes: int = 1024 * 1024,
    private_hosts: set[str] | None = None,
) -> httpx.Response:
    """One bounded, pinned request. Private hosts must come from operator policy.

    Do not follow redirects, forward proxy environment settings, or reuse a
    caller-supplied Host header. Callers decide how to handle HTTP error statuses.
    """
    method = method.upper()
    if method not in {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValueError("Unsupported HTTP method")
    validate_mcp_url(url)
    transport = MCPHTTPTransport(url)
    transport.private_hosts = private_hosts or set()
    clean_headers = {
        k: v
        for k, v in (headers or {}).items()
        if k.lower() not in {"host", "connection", "content-length", "transfer-encoding", "proxy-authorization"}
    }
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=timeout,
        ) as client:
            async with client.stream(
                method, url, headers=clean_headers, json=json, data=data, content=content, auth=auth
            ) as response:
                content = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    content.extend(chunk)
                    if len(content) > max_bytes:
                        raise ValueError("Response exceeds size limit")
                return httpx.Response(response.status_code, content=bytes(content), request=response.request)


async def post_public_json(
    url: str, payload: dict, *, timeout: float = 15, headers: dict | None = None, max_bytes: int = 1024 * 1024
) -> httpx.Response:
    """POST to a pinned public destination. Never redirect a credential or payload."""
    validate_mcp_url(url)
    transport = MCPHTTPTransport(url)
    transport.private_hosts = set()
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(
            transport=transport, trust_env=False, follow_redirects=False, timeout=timeout
        ) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    content.extend(chunk)
                    if len(content) > max_bytes:
                        raise ValueError("Public response exceeds size limit")
                return httpx.Response(response.status_code, content=bytes(content), request=response.request)


async def fetch_public_url(
    url: str,
    *,
    timeout: float = 15,
    headers: dict | None = None,
    max_bytes: int = 5 * 1024 * 1024,
    https_only: bool = False,
) -> httpx.Response:
    async with asyncio.timeout(timeout):
        for _ in range(6):
            parsed = validate_mcp_url(url)
            if https_only and parsed.scheme != "https":
                raise ValueError("HTTPS is required")
            transport = MCPHTTPTransport(url)
            # Public content must never inherit the MCP private-service allowlist.
            transport.private_hosts = set()
            async with httpx.AsyncClient(
                transport=transport, trust_env=False, follow_redirects=False, timeout=timeout
            ) as client:
                async with client.stream("GET", url, headers=headers) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ValueError("Redirect has no destination")
                        url = str(httpx.URL(url).join(location))
                        continue
                    content = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        content.extend(chunk)
                        if len(content) > max_bytes:
                            raise ValueError("Public response exceeds size limit")
                    # Content is already decoded; do not decode compressed headers twice.
                    result = httpx.Response(response.status_code, content=bytes(content), request=response.request)
                    result.encoding = response.encoding
                    return result
        raise ValueError("Too many redirects")
