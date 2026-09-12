"""Monitoring egress policy, scoped to a tenant and an exact operator-approved origin."""

import json
import os
from uuid import UUID

from src.services.mcp.http_transport import validate_mcp_url
from src.services.security.origins import http_origin
from src.services.security.public_http import request_checked_url


async def monitoring_request(method: str, url: str, *, tenant_id: UUID | None = None, **kwargs):
    endpoint = validate_mcp_url(url)
    private_hosts = set()
    # This is process configuration, never a tenant-supplied integration field.
    policy = json.loads(os.getenv("MONITORING_ALLOWED_PRIVATE_ORIGINS", "{}"))
    if not isinstance(policy, dict):
        raise ValueError("Invalid monitoring egress policy")
    origins = policy.get(str(tenant_id), []) if tenant_id is not None else []
    if not isinstance(origins, list):
        raise ValueError("Invalid monitoring egress policy")
    destination = (endpoint.scheme, endpoint.host.lower(), endpoint.port)
    if any(http_origin(origin) == destination for origin in origins):
        private_hosts.add(endpoint.host.lower())
    return await request_checked_url(method, url, private_hosts=private_hosts, **kwargs)
