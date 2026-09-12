"""Offline diagnostic probes; execute selected current source, with synthetic I/O.

Run: PYTHONPATH=api /private/tmp/synkora-harness-validation/bin/python \
    docs/reviews/probes/review_remaining_boundaries.py

AST extraction avoids unrelated application startup/native SAML dependencies.
It retains function bodies and annotations; route decorators are omitted.
These probes demonstrate boundary decisions, not live/browser exploitation.
"""
import ast
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[3]


def extract(path, names, namespace):
    tree = ast.parse((ROOT / path).read_text())
    nodes = [node for node in tree.body if getattr(node, "name", None) in names]
    assert len(nodes) == len(names)
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, "exec"), namespace)
    return namespace


async def main():
    results = {}
    from cryptography.fernet import Fernet
    os.environ.update(APP_ENV="test", SECRET_KEY="synthetic-review-key-0123456789abcdef",
                      JWT_SECRET_KEY="synthetic-review-jwt-0123456789abcdef",
                      ENCRYPTION_KEY=Fernet.generate_key().decode(),
                      CELERY_BROKER_URL="redis://localhost:6379/15",
                      CELERY_RESULT_BACKEND="redis://localhost:6379/15")
    # Real Okta mutation body, real SQLAlchemy model, synthetic DB/config.
    from src.models.okta_tenant import OktaTenant
    ns = dict(uuid=uuid, Depends=Depends, HTTPException=HTTPException,
              AsyncSession=AsyncSession, select=select, OktaTenant=OktaTenant,
              OktaTenantUpdate=SimpleNamespace, get_current_tenant_id=lambda: None,
              get_async_db=lambda: None, logger=logging.getLogger("probe"))
    extract("api/src/controllers/okta_sso.py", {"update_okta_config"}, ns)
    config = SimpleNamespace(domain="original.example.invalid", enabled="true")
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: config)
    data = SimpleNamespace(domain="attacker.example.invalid", client_id=None,
                           client_secret=None, issuer_url=None,
                           authorization_server_id=None,
                           jit_provisioning_enabled=None, enabled=False)
    await ns["update_okta_config"](data, uuid.uuid4(), db)
    results["okta_mutation_without_role_input"] = (
        config.domain == data.domain and config.enabled == "false"
        and db.commit.await_count == 1
    )

    # Actual monitoring helper forwards internal destination/method/headers.
    ns = extract("api/src/controllers/monitoring_integrations.py", {"_test_webhook", "_test_slack"}, {})
    with patch("requests.request", return_value=SimpleNamespace(status_code=200)) as request:
        await ns["_test_webhook"]({"url": "http://127.0.0.1:5002/v1/tools/initialize",
                                   "method": "DELETE", "headers": {"X-Probe": "synthetic"}})
        results["monitoring_internal_destination_forwarded"] = request.call_args.kwargs["url"]
        results["monitoring_arbitrary_method_forwarded"] = request.call_args.kwargs["method"]
    with patch("requests.post", return_value=SimpleNamespace(status_code=403, text="SYNTHETIC_INTERNAL_BODY")):
        _, message, _ = await ns["_test_slack"]({"webhook_url": "http://127.0.0.1/private"})
        results["monitoring_error_body_returned"] = "SYNTHETIC_INTERNAL_BODY" in message

    # Execute actual CORS class with a modeled valid widget lookup.
    ns = dict(ASGIApp=object, Scope=dict, Receive=object, Send=object, Message=dict,
              StarletteRequest=Request, Response=object, os=os)
    extract("api/src/middleware/cors_middleware.py", {"DynamicCORSMiddleware"}, ns)
    middleware = ns["DynamicCORSMiddleware"](None, dashboard_origins=["https://app.example.test"])
    origin = "https://untrusted.example.test"
    middleware._validate_widget_origin = AsyncMock(return_value=origin)
    request = Request({"type": "http", "path": "/console/api/auth/refresh",
                       "headers": [(b"x-widget-api-key", b"synthetic-valid-key")]})
    allowed = await middleware._get_allowed_origin(request, origin)
    headers = dict(middleware._build_cors_headers(allowed))
    results["widget_policy_applies_to_refresh_route"] = allowed == origin
    results["widget_policy_allows_credentials"] = headers[b"access-control-allow-credentials"] == b"true"
    results["dashboard_wrong_port_accepted"] = middleware._validate_dashboard_origin("https://app.example.test:8443") is not None
    results["dashboard_wrong_scheme_accepted"] = middleware._validate_dashboard_origin("http://app.example.test") is not None

    # Forged download capability when SECRET_KEY is provided only via settings.
    ns = dict(os=os, time=time, hmac=hmac, hashlib=hashlib, base64=base64, json=json,
              _TOKEN_MAX_AGE_SECONDS=3600, logger=logging.getLogger("probe"))
    extract("api/src/controllers/data_analysis.py", {"_verify_download_token"}, ns)
    path, ts = "/tmp/synthetic-other-tenant-report.csv", str(int(time.time()))
    signature = hmac.new(b"", f"{ts}:{path}".encode(), hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(json.dumps({"path": path, "ts": ts, "sig": signature}).encode()).decode()
    with patch.dict(os.environ):
        os.environ.pop("SECRET_KEY", None)
        results["empty_key_download_forgery_accepted"] = ns["_verify_download_token"](token) == path
    print(json.dumps(results, indent=2))
    assert all(value for value in results.values())


if __name__ == "__main__":
    asyncio.run(main())
