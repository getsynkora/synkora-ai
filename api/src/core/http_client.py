"""Shared httpx.AsyncClient factory with connection pooling.

Avoids creating a new TCP connection pool on every HTTP call — the default
``async with httpx.AsyncClient() as client:`` pattern tears down and
re-establishes connections each time, adding latency and wasting sockets.
"""

import httpx

_clients: dict[str, httpx.AsyncClient] = {}


def get_http_client(
    base_url: str = "",
    timeout: float = 30.0,
    key: str | None = None,
) -> httpx.AsyncClient:
    """Get or create a shared httpx.AsyncClient with connection pooling.

    Args:
        base_url: Base URL for all requests made through this client.
        timeout: Default timeout in seconds.
        key: Cache key for the client instance.  Defaults to *base_url*
             (or ``"_default"`` when both *key* and *base_url* are empty).

    Returns:
        A long-lived ``httpx.AsyncClient`` that reuses connections.
    """
    cache_key = key or base_url or "_default"
    client = _clients.get(cache_key)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=False,
        )
        _clients[cache_key] = client
    return client


async def close_all_clients() -> None:
    """Close all shared clients.  Call during application shutdown."""
    for client in _clients.values():
        await client.aclose()
    _clients.clear()
