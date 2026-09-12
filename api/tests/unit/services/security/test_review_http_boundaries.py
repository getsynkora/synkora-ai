"""Exercise real destination validation and pinned transport with modeled DNS/network."""

import asyncio
import json
import socket
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from src.controllers import custom_tools, monitoring_integrations
from src.services.mcp.http_transport import MCPHTTPTransport
from src.services.security import public_http
from src.services.security.monitoring_http import monitoring_request
from src.services.sso.okta_sso import OktaSSOService


def install_network(monkeypatch, ips, handler=None):
    dns = AsyncMock(return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ips])
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", dns)
    sent = []

    async def send(request):
        sent.append(request)
        return handler(request) if handler else httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(
        public_http, "MCPHTTPTransport", lambda url: MCPHTTPTransport(url, transport=httpx.MockTransport(send))
    )
    return dns, sent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ips",
    [["127.0.0.1"], ["10.0.0.1"], ["169.254.169.254"], ["::1"], ["::ffff:127.0.0.1"], ["8.8.8.8", "10.0.0.1"], []],
)
async def test_monitoring_blocks_private_and_failed_resolution(monkeypatch, ips):
    _, sent = install_network(monkeypatch, ips)
    monkeypatch.setenv("MCP_ALLOWED_PRIVATE_HOSTS", "metrics.example")
    monkeypatch.delenv("MONITORING_ALLOWED_PRIVATE_ORIGINS", raising=False)
    result = await monitoring_integrations._test_webhook({"url": "https://metrics.example", "method": "POST"})
    assert result[0] is False
    assert sent == []


@pytest.mark.asyncio
async def test_monitoring_private_policy_is_tenant_origin_scoped(monkeypatch):
    _, sent = install_network(monkeypatch, ["10.0.0.7"])
    tenant = uuid4()
    monkeypatch.setenv(
        "MONITORING_ALLOWED_PRIVATE_ORIGINS", json.dumps({str(tenant): ["https://metrics.internal:8443"]})
    )
    for who, url in [
        (uuid4(), "https://metrics.internal:8443"),
        (tenant, "https://metrics.internal"),
        (tenant, "http://metrics.internal:8443"),
        (tenant, "https://other.internal:8443"),
    ]:
        with pytest.raises(ValueError):
            await monitoring_request("POST", url, tenant_id=who, json={"test": True})
    assert sent == []
    assert (
        await monitoring_request("POST", "https://metrics.internal:8443/ingest", tenant_id=tenant)
    ).status_code == 200
    assert sent[0].url.host == "10.0.0.7"
    assert sent[0].headers["host"] == "metrics.internal:8443"
    # Even an explicit private approval cannot permit metadata destinations.
    for address in ("169.254.169.254", "fd00:ec2::254"):
        install_network(monkeypatch, [address])
        with pytest.raises(ValueError):
            await monitoring_request("POST", "https://metrics.internal:8443", tenant_id=tenant)


@pytest.mark.asyncio
async def test_monitoring_preserves_auth_without_following_redirects(monkeypatch):
    dns, sent = install_network(
        monkeypatch, ["8.8.8.8"], lambda req: httpx.Response(307, headers={"location": "http://127.0.0.1"})
    )
    result = await monitoring_integrations._test_webhook(
        {"url": "https://metrics.example", "headers": {"Authorization": "Bearer synthetic"}}
    )
    assert result[0] is False
    assert len(sent) == 1
    assert sent[0].headers["authorization"] == "Bearer synthetic"
    assert sent[0].url.host == "8.8.8.8"
    assert sent[0].extensions["sni_hostname"] == "metrics.example"
    dns.assert_awaited_once()


@pytest.mark.asyncio
async def test_monitoring_method_size_and_error_body_limits(monkeypatch):
    _, sent = install_network(monkeypatch, ["8.8.8.8"], lambda req: httpx.Response(403, text="private error content"))
    result = await monitoring_integrations._test_webhook({"url": "https://metrics.example", "method": "DELETE"})
    assert result[0] is False and not sent
    result = await monitoring_integrations._test_slack({"webhook_url": "https://metrics.example"})
    assert result[0] is False and "private error content" not in str(result)
    install_network(monkeypatch, ["8.8.8.8"], lambda req: httpx.Response(200, content=b"123456"))
    with pytest.raises(ValueError, match="size limit"):
        await monitoring_request("GET", "https://metrics.example", max_bytes=5)
    assert (await monitoring_request("GET", "https://metrics.example", max_bytes=6)).content == b"123456"


@pytest.mark.asyncio
@pytest.mark.parametrize("status,location", [(302, "https://private.example"), (307, "http://public.example")])
async def test_import_revalidates_redirects_and_forbids_https_downgrade(monkeypatch, status, location):
    dns, sent = install_network(
        monkeypatch, ["8.8.8.8"], lambda req: httpx.Response(status, headers={"location": location})
    )
    dns.side_effect = [
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 443))],
    ]
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await custom_tools.import_from_url(custom_tools.ImportFromURLRequest(url="https://public.example"), uuid4(), db)
    assert exc.value.status_code == 400
    assert len(sent) == 1
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_connection_uses_only_checked_dns_answer(monkeypatch):
    # A second lookup would return a private address. The socket transport receives
    # the already-checked literal IP and never resolves the original hostname again.
    dns, sent = install_network(monkeypatch, ["8.8.8.8"], lambda req: httpx.Response(200, json={"openapi": "3.0.0"}))
    dns.side_effect = [
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 443))],
    ]
    assert (await public_http.fetch_public_url("https://schema.example", https_only=True)).json()["openapi"] == "3.0.0"
    dns.assert_awaited_once()
    assert sent[0].url.host == "8.8.8.8"
    assert sent[0].headers["host"] == "schema.example"


@pytest.mark.asyncio
async def test_okta_never_sends_secrets_to_private_or_redirected_destinations(monkeypatch):
    _, sent = install_network(monkeypatch, ["127.0.0.1"])
    client = OktaSSOService("org.okta.com", "client", "synthetic-secret", "https://app.example/callback")
    with pytest.raises(ValueError):
        await client.get_oidc_access_token("code")
    assert not sent
    _, sent = install_network(
        monkeypatch, ["8.8.8.8"], lambda req: httpx.Response(307, headers={"location": "https://evil.example"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.get_oidc_access_token("code")
    assert len(sent) == 1
    assert sent[0].headers["host"] == "org.okta.com"


@pytest.mark.parametrize("provider", ["datadog", "otlp", "grafana", "webhook"])
def test_background_exports_use_tenant_scoped_checked_transport(monkeypatch, provider):
    from src.services.security import monitoring_http
    from src.tasks import load_testing_tasks

    tenant = uuid4()
    run = SimpleNamespace(
        tenant_id=tenant,
        id=uuid4(),
        load_test_id=uuid4(),
        summary_metrics={"requests": 1},
        completed_at=datetime.now(UTC),
        started_at=None,
        status=SimpleNamespace(value="completed"),
        peak_vus=1,
        total_requests=1,
    )
    send = AsyncMock(return_value=httpx.Response(202))
    monkeypatch.setattr(monitoring_http, "monitoring_request", send)
    config = {
        "url": "https://metrics.example",
        "endpoint": "https://metrics.example",
        "prometheus_url": "https://metrics.example",
        "username": "user",
        "api_key": "synthetic",
    }
    result = getattr(load_testing_tasks, f"_export_to_{provider}")(run, config, {})
    assert result["success"]
    assert send.call_args.kwargs["tenant_id"] == tenant
    send.assert_awaited_once()


def test_background_export_never_uses_destructive_test_method(monkeypatch):
    from src.tasks import load_testing_tasks

    send = MagicMock()
    monkeypatch.setattr(load_testing_tasks, "_monitoring_export_request", send)
    assert not load_testing_tasks._export_to_webhook(None, {"method": "DELETE"}, {})["success"]
    send.assert_not_called()


@pytest.mark.asyncio
async def test_valid_public_openapi_import_succeeds_with_pinned_connection(monkeypatch):
    schema = {
        "openapi": "3.0.0",
        "info": {"title": "Public API", "version": "1"},
        "servers": [{"url": "https://schema.example"}],
        "paths": {},
    }
    dns, sent = install_network(monkeypatch, ["8.8.8.8"], lambda req: httpx.Response(200, json=schema))
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)

    async def refresh(tool):
        tool.id, tool.created_at, tool.updated_at = uuid4(), datetime.now(UTC), datetime.now(UTC)

    db.refresh.side_effect = refresh
    result = await custom_tools.import_from_url(
        custom_tools.ImportFromURLRequest(url="https://schema.example"), uuid4(), db
    )
    assert result.name == "Public API"
    assert sent[0].url.host == "8.8.8.8"
    dns.assert_awaited_once()
    db.commit.assert_awaited_once()
