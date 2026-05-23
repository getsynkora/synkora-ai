"""Mailisk inbox tools for browser-driven signup and login test flows."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

MAILISK_DEFAULT_BASE_URL = "https://api.mailisk.com"
MAILISK_DEFAULT_DOMAIN_SUFFIX = ".mailisk.net"
MAILISK_EMAIL_LIMIT_MIN = 1
MAILISK_EMAIL_LIMIT_MAX = 20


@dataclass(slots=True)
class MailiskConfig:
    """Resolved Mailisk configuration for a tenant or environment."""

    api_key: str
    namespace: str
    base_url: str = MAILISK_DEFAULT_BASE_URL


def _normalize_namespace(value: str | None) -> str | None:
    """Normalize a Mailisk namespace."""
    if not value:
        return None
    namespace = str(value).strip().lower()
    if namespace.endswith(MAILISK_DEFAULT_DOMAIN_SUFFIX):
        namespace = namespace[: -len(MAILISK_DEFAULT_DOMAIN_SUFFIX)]
    return namespace or None


def _slugify_local_part(value: str | None, fallback: str = "synkora") -> str:
    """Generate a safe email local-part prefix."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return (cleaned or fallback)[:48]


def _extract_local_part_and_namespace(email: str | None) -> tuple[str | None, str | None]:
    """Parse local part and namespace from a Mailisk email address."""
    if not email or "@" not in email:
        return None, None
    local_part, domain = email.strip().split("@", 1)
    if not local_part or not domain.endswith(MAILISK_DEFAULT_DOMAIN_SUFFIX):
        return local_part or None, None
    namespace = domain[: -len(MAILISK_DEFAULT_DOMAIN_SUFFIX)]
    return local_part, namespace or None


def _build_to_addr_prefix(recipient_email: str | None, to_addr_prefix: str | None) -> str | None:
    """Resolve Mailisk to_addr_prefix, preferring exact local-part matching for recipient_email."""
    if recipient_email:
        local_part, _ = _extract_local_part_and_namespace(recipient_email)
        if local_part:
            return f"{local_part}@"
    if not to_addr_prefix:
        return None
    return str(to_addr_prefix).strip()


def _parse_timeout_seconds(timeout_ms: int | None) -> float:
    """Convert tool timeout in milliseconds to a reasonable request timeout."""
    timeout = max(1_000, int(timeout_ms or 60_000))
    return timeout / 1000


def _extract_response_error(response: httpx.Response) -> str:
    """Turn a Mailisk HTTP error response into a concise message."""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            for key in ("message", "error", "detail"):
                if payload.get(key):
                    return str(payload[key])
    except Exception:
        pass
    body = response.text.strip()
    return body[:400] if body else f"Mailisk request failed with status {response.status_code}"


def _extract_payload_items(payload: Any) -> list[Any]:
    """Normalize Mailisk payloads that may be wrapped or returned directly as a list."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
    return []


async def _mailisk_get(
    config: MailiskConfig,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    timeout_s: float = 60.0,
) -> dict[str, Any]:
    """Execute a GET request against the Mailisk REST API."""
    headers = {"Accept": "application/json", "X-Api-Key": config.api_key}
    async with httpx.AsyncClient(base_url=config.base_url.rstrip("/"), headers=headers, timeout=timeout_s) as client:
        try:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise ValueError("Timed out waiting for Mailisk response") from exc
        except httpx.HTTPStatusError as exc:
            message = _extract_response_error(exc.response)
            raise ValueError(message) from exc


async def _resolve_mailisk_oauth_app(runtime_context: Any, tool_name: str) -> dict[str, Any]:
    """Resolve the linked Mailisk OAuth app for the executing agent tool."""
    from sqlalchemy import select

    from src.core.database import get_async_session_factory
    from src.models.agent_tool import AgentTool
    from src.models.oauth_app import OAuthApp

    if not runtime_context or not getattr(runtime_context, "agent_id", None):
        raise ValueError("Mailisk tools require runtime context with agent_id.")

    async with get_async_session_factory()() as db:
        result = await db.execute(
            select(AgentTool).filter(
                AgentTool.agent_id == runtime_context.agent_id,
                AgentTool.tool_name == tool_name,
                AgentTool.enabled,
            )
        )
        agent_tool = result.scalar_one_or_none()
        if not agent_tool or not agent_tool.oauth_app_id:
            raise ValueError(
                f"No Mailisk integration configured for tool '{tool_name}'. "
                "Attach a Mailisk OAuth app in Agent Tools settings."
            )

        result = await db.execute(
            select(OAuthApp).filter(
                OAuthApp.id == agent_tool.oauth_app_id,
                OAuthApp.provider.ilike("mailisk"),
                OAuthApp.is_active,
            )
        )
        oauth_app = result.scalar_one_or_none()
        if not oauth_app:
            raise ValueError("No active Mailisk integration found. Check your tenant integrations.")

        return {
            "id": oauth_app.id,
            "provider": oauth_app.provider,
            "is_active": oauth_app.is_active,
            "is_default": oauth_app.is_default,
            "api_token": oauth_app.api_token,
            "config": oauth_app.config or {},
        }


async def _resolve_mailisk_config(
    runtime_context: Any,
    tool_name: str,
    namespace: str | None = None,
    *,
    require_namespace: bool = True,
) -> MailiskConfig:
    """Resolve Mailisk API credentials from the linked agent tool integration."""
    app = await _resolve_mailisk_oauth_app(runtime_context, tool_name)

    app_config = app.get("config") or {}
    resolved_namespace = _normalize_namespace(namespace) or _normalize_namespace(app_config.get("namespace"))
    resolved_base_url = str(app_config.get("base_url") or MAILISK_DEFAULT_BASE_URL).rstrip("/")
    resolved_api_key = None

    api_token = app.get("api_token")
    if api_token:
        from src.services.agents.security import decrypt_value

        resolved_api_key = decrypt_value(api_token)

    if not resolved_api_key:
        raise ValueError("Mailisk API key not configured on the tenant integration.")
    if require_namespace and not resolved_namespace:
        raise ValueError("Mailisk namespace not configured. Set config.namespace on the tenant Mailisk integration.")

    return MailiskConfig(
        api_key=resolved_api_key,
        namespace=resolved_namespace or "",
        base_url=resolved_base_url or MAILISK_DEFAULT_BASE_URL,
    )


def _normalize_email_record(email: dict[str, Any]) -> dict[str, Any]:
    """Return a stable, LLM-friendly Mailisk email shape."""
    return {
        "id": email.get("id"),
        "from": email.get("from") or {},
        "from_address": (email.get("from") or {}).get("address"),
        "from_name": (email.get("from") or {}).get("name"),
        "to": email.get("to") or [],
        "to_addresses": [item.get("address") for item in email.get("to") or [] if item.get("address")],
        "subject": email.get("subject"),
        "text": email.get("text"),
        "html": email.get("html"),
        "received_date": email.get("received_date"),
        "received_timestamp": email.get("received_timestamp"),
        "expires_timestamp": email.get("expires_timestamp"),
        "headers": email.get("headers") or {},
        "attachments": email.get("attachments") or [],
    }


def _extract_text_content(text: str | None, html: str | None) -> str:
    """Combine plain text and HTML content into one searchable body."""
    text_parts: list[str] = []
    if text:
        text_parts.append(str(text))
    if html:
        soup = BeautifulSoup(str(html), "html.parser")
        html_text = soup.get_text(" ", strip=True)
        if html_text:
            text_parts.append(html_text)
    return "\n".join(part for part in text_parts if part).strip()


def _extract_links_from_email(text: str | None, html: str | None) -> list[str]:
    """Extract unique absolute links from email text and HTML."""
    links: list[str] = []
    seen: set[str] = set()

    if html:
        soup = BeautifulSoup(str(html), "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = unescape(anchor["href"]).strip()
            if href and href not in seen and href.startswith(("http://", "https://")):
                seen.add(href)
                links.append(href)

    combined_text = "\n".join(part for part in [text, html] if part)
    for match in re.finditer(r"https?://[^\s\"'<>]+", combined_text or ""):
        url = unescape(match.group(0)).rstrip(").,;!?]")
        if url and url not in seen:
            seen.add(url)
            links.append(url)

    return links


def _extract_verification_code(
    text: str | None,
    html: str | None,
    *,
    code_length: int = 6,
    regex: str | None = None,
) -> str | None:
    """Extract a verification code from email content."""
    content = _extract_text_content(text, html)
    if not content:
        return None

    patterns: list[str] = []
    if regex:
        patterns.append(regex)
    if code_length > 0:
        patterns.append(rf"(?<!\d)(\d{{{code_length}}})(?!\d)")
    patterns.extend(
        [
            r"(?i)\b(?:verification|security|login|otp|code|passcode)\D{0,20}(\d{4,8})\b",
            r"(?<!\d)(\d{6})(?!\d)",
            r"(?<!\d)(\d{4})(?!\d)",
        ]
    )

    for pattern in patterns:
        match = re.search(pattern, content)
        if not match:
            continue
        if match.groups():
            return next((group for group in match.groups() if group), match.group(0))
        return match.group(0)
    return None


def _pick_matching_link(
    links: list[str],
    *,
    domain_includes: str | None = None,
    url_includes: str | None = None,
    prefer_https: bool = True,
) -> str | None:
    """Select the most relevant link from extracted links."""
    candidates = links

    if domain_includes:
        fragment = domain_includes.lower()
        candidates = [link for link in candidates if fragment in urlparse(link).netloc.lower()]
    if url_includes:
        fragment = url_includes.lower()
        candidates = [link for link in candidates if fragment in link.lower()]
    if prefer_https:
        https_candidates = [link for link in candidates if link.startswith("https://")]
        if https_candidates:
            candidates = https_candidates
    return candidates[0] if candidates else None


async def internal_mailisk_list_namespaces(
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """List namespaces available to the configured Mailisk API key."""
    try:
        tool_name = (config or {}).get("_tool_name", "internal_mailisk_list_namespaces")
        resolved = await _resolve_mailisk_config(runtime_context, tool_name, require_namespace=False)
        payload = await _mailisk_get(
            resolved,
            "/api/namespaces",
            timeout_s=15.0,
        )
        namespaces = _extract_payload_items(payload)
        return {
            "success": True,
            "count": len(namespaces),
            "namespaces": namespaces,
            "default_namespace": _normalize_namespace(resolved.namespace),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def internal_mailisk_generate_test_email(
    local_part_prefix: str = "synkora",
    namespace: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """Generate a unique Mailisk inbox address for a signup or login test run."""
    try:
        tool_name = (config or {}).get("_tool_name", "internal_mailisk_generate_test_email")
        resolved = await _resolve_mailisk_config(runtime_context, tool_name, namespace=namespace)
        prefix = _slugify_local_part(local_part_prefix)
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        unique_suffix = secrets.token_hex(3)
        local_part = f"{prefix}-{timestamp}-{unique_suffix}"
        email_address = f"{local_part}@{resolved.namespace}{MAILISK_DEFAULT_DOMAIN_SUFFIX}"
        return {
            "success": True,
            "email": email_address,
            "address": email_address,
            "local_part": local_part,
            "namespace": resolved.namespace,
            "domain": f"{resolved.namespace}{MAILISK_DEFAULT_DOMAIN_SUFFIX}",
            "to_addr_prefix": f"{local_part}@",
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def internal_mailisk_wait_for_email(
    recipient_email: str | None = None,
    to_addr_prefix: str | None = None,
    from_addr_includes: str | None = None,
    subject_includes: str | None = None,
    namespace: str | None = None,
    timeout_ms: int = 60_000,
    limit: int = 10,
    wait: bool = True,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """Wait for and fetch matching emails from a Mailisk inbox."""
    try:
        derived_namespace = namespace
        if recipient_email and not derived_namespace:
            _, derived_namespace = _extract_local_part_and_namespace(recipient_email)

        tool_name = (config or {}).get("_tool_name", "internal_mailisk_wait_for_email")
        resolved = await _resolve_mailisk_config(runtime_context, tool_name, namespace=derived_namespace)
        params: dict[str, Any] = {
            "limit": max(MAILISK_EMAIL_LIMIT_MIN, min(int(limit), MAILISK_EMAIL_LIMIT_MAX)),
        }
        resolved_prefix = _build_to_addr_prefix(recipient_email, to_addr_prefix)
        if resolved_prefix:
            params["to_addr_prefix"] = resolved_prefix
        if from_addr_includes:
            params["from_addr_includes"] = from_addr_includes
        if subject_includes:
            params["subject_includes"] = subject_includes
        if wait:
            params["wait"] = "true"

        payload = await _mailisk_get(
            resolved,
            f"/api/emails/{resolved.namespace}/inbox",
            params=params,
            timeout_s=_parse_timeout_seconds(timeout_ms),
        )
        emails = [_normalize_email_record(item) for item in _extract_payload_items(payload)]
        return {
            "success": True,
            "namespace": resolved.namespace,
            "count": len(emails),
            "total_count": payload.get("total_count", len(emails)) if isinstance(payload, dict) else len(emails),
            "emails": emails,
            "latest_email": emails[0] if emails else None,
            "query": {
                "recipient_email": recipient_email,
                "to_addr_prefix": resolved_prefix,
                "from_addr_includes": from_addr_includes,
                "subject_includes": subject_includes,
                "wait": wait,
            },
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def internal_mailisk_wait_for_verification_code(
    recipient_email: str | None = None,
    to_addr_prefix: str | None = None,
    from_addr_includes: str | None = None,
    subject_includes: str | None = None,
    namespace: str | None = None,
    timeout_ms: int = 60_000,
    code_length: int = 6,
    regex: str | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """Wait for an email and extract a verification code from it."""
    email_result = await internal_mailisk_wait_for_email(
        recipient_email=recipient_email,
        to_addr_prefix=to_addr_prefix,
        from_addr_includes=from_addr_includes,
        subject_includes=subject_includes,
        namespace=namespace,
        timeout_ms=timeout_ms,
        limit=10,
        wait=True,
        config=config,
        runtime_context=runtime_context,
    )
    if not email_result.get("success"):
        return email_result

    latest_email = email_result.get("latest_email")
    if not latest_email:
        return {"success": False, "error": "No matching email found."}

    code = _extract_verification_code(
        latest_email.get("text"),
        latest_email.get("html"),
        code_length=code_length,
        regex=regex,
    )
    if not code:
        return {
            "success": False,
            "error": "Matching email received, but no verification code could be extracted.",
            "email": latest_email,
        }

    return {
        "success": True,
        "code": code,
        "code_length": len(code),
        "namespace": email_result.get("namespace"),
        "email": latest_email,
    }


async def internal_mailisk_wait_for_verification_link(
    recipient_email: str | None = None,
    to_addr_prefix: str | None = None,
    from_addr_includes: str | None = None,
    subject_includes: str | None = None,
    namespace: str | None = None,
    timeout_ms: int = 60_000,
    domain_includes: str | None = None,
    url_includes: str | None = None,
    prefer_https: bool = True,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """Wait for an email and extract the most relevant verification link."""
    email_result = await internal_mailisk_wait_for_email(
        recipient_email=recipient_email,
        to_addr_prefix=to_addr_prefix,
        from_addr_includes=from_addr_includes,
        subject_includes=subject_includes,
        namespace=namespace,
        timeout_ms=timeout_ms,
        limit=10,
        wait=True,
        config=config,
        runtime_context=runtime_context,
    )
    if not email_result.get("success"):
        return email_result

    latest_email = email_result.get("latest_email")
    if not latest_email:
        return {"success": False, "error": "No matching email found."}

    links = _extract_links_from_email(latest_email.get("text"), latest_email.get("html"))
    selected = _pick_matching_link(
        links,
        domain_includes=domain_includes,
        url_includes=url_includes,
        prefer_https=prefer_https,
    )
    if not selected:
        return {
            "success": False,
            "error": "Matching email received, but no verification link could be extracted.",
            "email": latest_email,
            "links": links,
        }

    return {
        "success": True,
        "link": selected,
        "links": links,
        "namespace": email_result.get("namespace"),
        "email": latest_email,
    }
