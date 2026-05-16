"""
Remote Agent Tool for calling external A2A or MCP agents.

Allows Synkora agents to delegate work to remote agents at external endpoints
using either the A2A message/send protocol or the MCP tools/call protocol.

SECURITY: All URLs are validated via SSRF check before making requests.
"""

import json
import logging
import socket
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60
MAX_RESPONSE_CHARS = 20000


def _same_origin_as_app_base(url: str, app_base: str) -> bool:
    """Return True only for an exact scheme/host/port match with APP_BASE_URL."""
    try:
        parsed_url = urlsplit(url)
        parsed_base = urlsplit(app_base)
        if parsed_url.username or parsed_url.password:
            return False
        return (
            parsed_url.scheme == parsed_base.scheme
            and parsed_url.hostname == parsed_base.hostname
            and (parsed_url.port or _default_port(parsed_url.scheme))
            == (parsed_base.port or _default_port(parsed_base.scheme))
        )
    except Exception:
        return False


def _default_port(scheme: str) -> int | None:
    return 443 if scheme == "https" else 80 if scheme == "http" else None


def _rewrite_app_base_to_internal(endpoint_url: str, app_base: str) -> str:
    """Rewrite only exact APP_BASE_URL origin requests to the internal API origin."""
    if not app_base or not _same_origin_as_app_base(endpoint_url, app_base):
        return endpoint_url

    parsed = urlsplit(endpoint_url)
    internal = urlsplit("http://synkora-api:5001")
    return urlunsplit((internal.scheme, internal.netloc, parsed.path, parsed.query, parsed.fragment))


def _is_url_safe(url: str) -> bool:
    """
    Validate URL for SSRF safety. Reuses web_tools logic.

    Allows only http/https with public IPs. Blocks private ranges,
    localhost, cloud metadata endpoints, etc.

    Exception: the configured APP_BASE_URL is always allowed — it is a
    known, server-controlled value and agents may call sibling agents on
    the same instance.
    """
    try:
        from src.config import settings

        app_base = (settings.app_base_url or "").rstrip("/")
        if app_base and _same_origin_as_app_base(url, app_base):
            return True

        from src.services.agents.internal_tools.web_tools import _is_ip_blocked

        parsed = urlsplit(url)
        if parsed.username or parsed.password:
            return False
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Resolve hostname to IP for SSRF check
        try:
            resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for _family, _, _, _, sockaddr in resolved:
                ip_str = sockaddr[0]
                if _is_ip_blocked(ip_str):
                    logger.warning(f"[SSRF] Blocked remote agent URL: {url} resolved to {ip_str}")
                    return False
        except socket.gaierror:
            return False

        return True
    except Exception as exc:
        logger.warning(f"[SSRF] URL safety check failed for {url}: {exc}")
        return False


async def call_remote_agent(
    endpoint_url: str,
    message: str,
    protocol: Literal["a2a", "mcp"] = "a2a",
    api_key: str | None = None,
    conversation_id: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT,
    **context: Any,
) -> dict:
    """
    Call a remote agent via A2A message/send or MCP tools/call.

    Args:
        endpoint_url: Remote agent endpoint URL.
            A2A: https://host/api/a2a/agents/{id}
            MCP: https://host/api/mcp/{id}
        message: The text message to send to the remote agent.
        protocol: "a2a" (default) or "mcp".
        api_key: Bearer token for the remote endpoint.
        conversation_id: Optional conversation/context ID for continuity.
        timeout_seconds: Request timeout (max 300).

    Returns:
        {"success": True, "result": "...response text..."} on success
        {"success": False, "error": "...description..."} on failure
    """
    if not endpoint_url or not message:
        return {"success": False, "error": "endpoint_url and message are required"}

    timeout_seconds = min(timeout_seconds, 300)

    if not _is_url_safe(endpoint_url):
        return {
            "success": False,
            "error": f"Endpoint URL is not allowed (SSRF protection): {endpoint_url}",
        }

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Replace APP_BASE_URL with internal service URL so Docker containers can
    # reach the API server directly without going through a public tunnel.
    from src.config import settings

    app_base = (settings.app_base_url or "").rstrip("/")
    endpoint_url = _rewrite_app_base_to_internal(endpoint_url, app_base)

    try:
        if protocol == "mcp":
            return await _call_mcp(endpoint_url, message, conversation_id, headers, timeout_seconds)
        else:
            return await _call_a2a(endpoint_url, message, conversation_id, headers, timeout_seconds)
    except httpx.TimeoutException:
        return {"success": False, "error": f"Request timed out after {timeout_seconds}s"}
    except Exception as exc:
        logger.warning(f"[RemoteAgent] Call to {endpoint_url} failed: {exc}")
        return {"success": False, "error": str(exc)}


async def _call_a2a(
    endpoint_url: str,
    message: str,
    conversation_id: str | None,
    headers: dict,
    timeout: int,
) -> dict:
    """Call remote agent via A2A message/send."""
    import uuid

    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": message}],
            },
        },
    }
    if conversation_id:
        payload["params"]["contextId"] = conversation_id

    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout) as client:
        response = await client.post(endpoint_url, json=payload, headers=headers)

    if response.status_code != 200:
        return {
            "success": False,
            "error": f"Remote agent returned HTTP {response.status_code}: {response.text[:500]}",
        }

    try:
        data = response.json()
    except json.JSONDecodeError:
        return {"success": False, "error": "Remote agent returned invalid JSON"}

    if "error" in data:
        err = data["error"]
        return {"success": False, "error": f"{err.get('message', 'Unknown error')} (code={err.get('code')})"}

    result = data.get("result", {})

    # Extract text from artifacts
    text_parts = []
    for artifact in result.get("artifacts", []):
        for part in artifact.get("parts", []):
            if part.get("type") == "text":
                text_parts.append(part.get("text", ""))

    if not text_parts:
        # Fallback: check status message
        status_obj = result.get("status", {})
        message_obj = status_obj.get("message", {})
        for part in message_obj.get("parts", []):
            if part.get("type") == "text":
                text_parts.append(part.get("text", ""))

    response_text = " ".join(text_parts)[:MAX_RESPONSE_CHARS]
    return {"success": True, "result": response_text, "task_id": result.get("id")}


async def _call_mcp(
    endpoint_url: str,
    message: str,
    conversation_id: str | None,
    headers: dict,
    timeout: int,
) -> dict:
    """Call remote agent via MCP tools/call."""
    import uuid

    headers = {**headers, "MCP-Protocol-Version": "2025-06-18"}

    # Initialize
    init_payload = {
        "jsonrpc": "2.0",
        "id": "init",
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "clientInfo": {"name": "synkora-agent", "version": "1.0.0"}},
    }

    arguments: dict = {"message": message}
    if conversation_id:
        arguments["conversation_id"] = conversation_id

    tools_call_payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {"name": "chat", "arguments": arguments},
    }

    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout) as client:
        # Initialize session
        init_resp = await client.post(endpoint_url, json=init_payload, headers=headers)
        if init_resp.status_code != 200:
            return {
                "success": False,
                "error": f"MCP initialize failed: HTTP {init_resp.status_code}",
            }

        # Call tool
        resp = await client.post(endpoint_url, json=tools_call_payload, headers=headers)

    if resp.status_code != 200:
        return {
            "success": False,
            "error": f"MCP tools/call failed: HTTP {resp.status_code}: {resp.text[:500]}",
        }

    try:
        data = resp.json()
    except json.JSONDecodeError:
        return {"success": False, "error": "MCP server returned invalid JSON"}

    if "error" in data:
        err = data["error"]
        return {"success": False, "error": f"{err.get('message', 'Unknown error')} (code={err.get('code')})"}

    result = data.get("result", {})
    text_parts = []
    for content_item in result.get("content", []):
        if content_item.get("type") == "text":
            text_parts.append(content_item.get("text", ""))

    response_text = " ".join(text_parts)[:MAX_RESPONSE_CHARS]
    return {"success": True, "result": response_text}
