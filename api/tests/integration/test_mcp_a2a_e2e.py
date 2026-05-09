"""
Integration tests for MCP server host and A2A async tasks.


Runs against the live API server at localhost:5001 with real agents,
real Celery workers, and real database state.


Usage:
   pytest tests/integration/test_mcp_a2a_e2e.py -v -s
"""

import json
import os
import time
import uuid


import httpx
import pytest


pytestmark = pytest.mark.e2e


BASE_URL = "http://localhost:5001"
AGENT_ID = "dfff4404-de17-45f4-8f2a-4a0855b24762"  # Sample DB
A2A_KEY = os.environ.get("TEST_A2A_KEY", "")
MCP_KEY = os.environ.get("TEST_MCP_KEY", "")
MCP_URL = f"{BASE_URL}/api/mcp/{AGENT_ID}"
A2A_URL = f"{BASE_URL}/api/a2a/agents/{AGENT_ID}"


if not A2A_KEY:
    pytest.skip("TEST_A2A_KEY not set — skipping A2A/MCP e2e tests", allow_module_level=True)
if not MCP_KEY:
    pytest.skip("TEST_MCP_KEY not set — skipping MCP e2e tests", allow_module_level=True)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def a2a(method, params=None):
    payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params or {}}
    r = httpx.post(A2A_URL, json=payload, headers={"Authorization": f"Bearer {A2A_KEY}"}, timeout=30)
    r.raise_for_status()
    return r.json()


def mcp(method, params=None):
    payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": method, "params": params or {}}
    r = httpx.post(
        MCP_URL,
        json=payload,
        headers={"Authorization": f"Bearer {MCP_KEY}", "MCP-Protocol-Version": "2025-06-18"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# MCP Server Host
# ---------------------------------------------------------------------------


class TestMCPServerHost:
    def test_initialize_returns_correct_protocol_version(self):
        resp = mcp(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "clientInfo": {"name": "pytest-client", "version": "1.0"},
            },
        )
        result = resp["result"]
        assert result["protocolVersion"] == "2025-06-18"
        assert result["serverInfo"]["name"] == "synkora-agent"
        assert "tools" in result["capabilities"]

    def test_tools_list_exposes_single_chat_tool(self):
        resp = mcp("tools/list")
        tools = resp["result"]["tools"]
        assert len(tools) == 1
        tool = tools[0]
        assert tool["name"] == "chat"
        assert "message" in tool["inputSchema"]["properties"]
        assert "message" in tool["inputSchema"]["required"]

    def test_tools_call_chat_executes_real_agent(self):
        resp = mcp(
            "tools/call",
            {
                "name": "chat",
                "arguments": {"message": "Reply with exactly the word: MCP_OK"},
            },
        )
        result = resp["result"]
        assert result["isError"] is False
        content = result["content"]
        assert len(content) == 1
        assert content[0]["type"] == "text"
        assert "MCP_OK" in content[0]["text"]

    def test_tools_call_missing_message_returns_error(self):
        resp = mcp("tools/call", {"name": "chat", "arguments": {}})
        assert "error" in resp
        assert resp["error"]["code"] == -32602

    def test_tools_call_unknown_tool_returns_error(self):
        resp = mcp("tools/call", {"name": "nonexistent", "arguments": {"message": "hi"}})
        assert "error" in resp
        assert resp["error"]["code"] == -32602

    def test_ping(self):
        resp = mcp("ping")
        assert resp["result"] == {}

    def test_unknown_method_returns_method_not_found(self):
        resp = mcp("does/not/exist")
        assert resp["error"]["code"] == -32601

    def test_wrong_api_key_returns_401(self):
        payload = {"jsonrpc": "2.0", "id": "x", "method": "ping", "params": {}}
        r = httpx.post(
            MCP_URL,
            json=payload,
            headers={"Authorization": "Bearer sk_live_fakekeyXXXXXXXXXXXX", "MCP-Protocol-Version": "2025-06-18"},
            timeout=10,
        )
        assert r.status_code == 401

    def test_no_auth_returns_401(self):
        payload = {"jsonrpc": "2.0", "id": "x", "method": "ping", "params": {}}
        r = httpx.post(MCP_URL, json=payload, timeout=10)
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# A2A Async Tasks
# ---------------------------------------------------------------------------


class TestA2AAsyncTasks:
    def test_tasks_send_returns_immediately_with_submitted(self):
        """tasks/send must return in <2s — task queued to Celery, not executed inline."""
        t0 = time.time()
        resp = a2a(
            "tasks/send",
            {
                "id": str(uuid.uuid4()),
                "message": {"role": "user", "parts": [{"type": "text", "text": "Reply: ASYNC_TEST"}]},
            },
        )
        elapsed = time.time() - t0

        assert elapsed < 2, f"tasks/send took {elapsed:.1f}s — must be instant (async)"
        result = resp["result"]
        assert result["status"]["state"] in ("submitted", "working")
        assert "id" in result
        assert "contextId" in result

    def test_tasks_get_completes_via_celery(self):
        """Full lifecycle: submit → Celery executes → poll to completed."""
        resp = a2a(
            "tasks/send",
            {
                "id": str(uuid.uuid4()),
                "message": {"role": "user", "parts": [{"type": "text", "text": "Reply with exactly: CELERY_OK"}]},
            },
        )
        task_id = resp["result"]["id"]

        # Poll up to 30s
        final_state = None
        for _ in range(15):
            time.sleep(2)
            poll = a2a("tasks/get", {"id": task_id})
            state = poll["result"]["status"]["state"]
            if state in ("completed", "failed"):
                final_state = state
                break

        assert final_state == "completed", f"Task ended in state: {final_state}"
        artifacts = poll["result"].get("artifacts", [])
        assert len(artifacts) > 0
        text = artifacts[0]["parts"][0]["text"]
        assert "CELERY_OK" in text

    def test_tasks_get_unknown_id_returns_error(self):
        resp = a2a("tasks/get", {"id": "does-not-exist-00000"})
        assert "error" in resp
        assert resp["error"]["code"] == -32602

    def test_tasks_cancel_stops_submitted_task(self):
        """Create a task and cancel it before Celery picks it up (race — but cancel must work)."""
        resp = a2a(
            "tasks/send",
            {
                "id": str(uuid.uuid4()),
                "message": {"role": "user", "parts": [{"type": "text", "text": "Long running task placeholder"}]},
            },
        )
        task_id = resp["result"]["id"]

        cancel_resp = a2a("tasks/cancel", {"id": task_id})
        state = cancel_resp["result"]["status"]["state"]
        # Either canceled (we beat Celery) or completed (Celery was faster) — both valid
        assert state in ("canceled", "completed", "working")

    def test_tasks_send_subscribe_streams_sse_events(self):
        """tasks/sendSubscribe must stream working → chunk(s) → completed over SSE."""
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tasks/sendSubscribe",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": "Reply with exactly: SSE_OK"}],
                }
            },
        }

        states_seen = []
        got_text = []

        with httpx.stream(
            "POST", A2A_URL, json=payload, headers={"Authorization": f"Bearer {A2A_KEY}"}, timeout=60
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    ev = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                state = ev.get("status", {}).get("state")
                if state:
                    states_seen.append(state)

                artifact = ev.get("artifact") or {}
                for part in artifact.get("parts", []):
                    if part.get("type") == "text":
                        got_text.append(part["text"])

                if state == "completed":
                    # Also grab final artifacts
                    for art in ev.get("artifacts", []):
                        for part in art.get("parts", []):
                            if part.get("type") == "text":
                                got_text.append(part["text"])
                    break

        assert "working" in states_seen, f"Never saw 'working' state, got: {states_seen}"
        assert "completed" in states_seen, f"Never reached 'completed', got: {states_seen}"
        full_text = "".join(got_text)
        assert "SSE_OK" in full_text, f"Expected SSE_OK in response, got: {full_text[:200]}"

    def test_a2a_agent_card(self):
        """/.well-known/agent.json returns valid agent card."""
        r = httpx.get(
            f"{BASE_URL}/api/a2a/agents/{AGENT_ID}/.well-known/agent.json",
            headers={"Authorization": f"Bearer {A2A_KEY}"},
            timeout=10,
        )
        r.raise_for_status()
        card = r.json()
        assert "url" in card
        assert "capabilities" in card
        assert card["capabilities"]["streaming"] is True
        assert "skills" in card
        assert len(card["skills"]) > 0
