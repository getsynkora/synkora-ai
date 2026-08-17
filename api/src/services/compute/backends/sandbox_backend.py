"""
SandboxComputeBackend — delegates all compute to the synkora-sandbox service over HTTP.

No persistence. Workspaces are created fresh each conversation and deleted on close.
If the sandbox restarts, workspaces are gone — that is fine by design.
"""

import logging
from typing import Any

import httpx

from src.services.compute.backends.base import ComputeBackend

logger = logging.getLogger(__name__)

# Shared persistent client — reuses TCP connections across all sandbox calls.
_client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    timeout=httpx.Timeout(connect=5.0, read=310.0, write=30.0, pool=5.0),
)


def _parse_response(resp: httpx.Response, defaults: dict[str, Any]) -> dict[str, Any]:
    """
    Parse a sandbox HTTP response into the {"success": bool, ...} envelope callers expect.

    The sandbox service returns {"success": bool, ...} on its own 2xx/4xx responses, but a
    non-2xx response from the underlying ASGI framework itself (e.g. a 404/500 that never
    reached the sandbox's own handler) can have a completely different shape (FastAPI's
    default {"detail": "..."}) with no "success" key at all. Without this normalization,
    callers doing result["success"] get an unhandled KeyError instead of a clean error dict.
    """
    try:
        data = resp.json()
    except Exception:
        data = None

    if isinstance(data, dict) and "success" in data:
        return data

    error = data.get("detail") if isinstance(data, dict) else None
    return {**defaults, "success": False, "error": error or resp.text or f"HTTP {resp.status_code}"}


class SandboxComputeBackend(ComputeBackend):
    def __init__(
        self,
        tenant_id: str,
        sandbox_url: str,
        sandbox_api_key: str | None = None,
    ) -> None:
        self._tenant_id = str(tenant_id)
        self._sandbox_url = sandbox_url.rstrip("/")
        self._sandbox_api_key = sandbox_api_key

    @property
    def backend_type(self) -> str:
        return "sandbox"

    def _headers(self) -> dict:
        if self._sandbox_api_key:
            return {"X-Sandbox-Key": self._sandbox_api_key}
        return {}

    async def checkout_session(
        self,
        agent_id: str,
        tenant_id: str,
        conversation_id: str,
    ) -> "SandboxComputeSession":
        # No setup needed — workspace is created lazily on first use inside the sandbox.
        return SandboxComputeSession(
            tenant_id=self._tenant_id,
            agent_id=str(agent_id),
            backend=self,
        )

    async def return_session(self, session: "SandboxComputeSession") -> None:
        # Clean up workspace directory. Fire-and-forget — disk space is reclaimed,
        # but a failure here is non-critical.
        try:
            await _client.delete(
                f"{self._sandbox_url}/v1/workspace",
                params={"tenant_id": self._tenant_id, "agent_id": session.agent_id},
                headers=self._headers(),
            )
        except Exception as e:
            logger.warning(f"Workspace cleanup failed for agent {session.agent_id[:8]}: {e}")


class SandboxComputeSession:
    def __init__(self, tenant_id: str, agent_id: str, backend: SandboxComputeBackend) -> None:
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self._backend = backend

    @property
    def base_path(self) -> str | None:
        return f"/workspaces/{self.tenant_id}/{self.agent_id}"

    @property
    def is_remote(self) -> bool:
        return True

    def _url(self, path: str) -> str:
        return f"{self._backend._sandbox_url}{path}"

    def _h(self) -> dict:
        return self._backend._headers()

    def _base(self) -> dict:
        return {"tenant_id": self.tenant_id, "agent_id": self.agent_id}

    async def exec_command(
        self,
        command: list[str],
        cwd: str | None = None,
        timeout: int = 300,
        input_text: str | None = None,
    ) -> dict[str, Any]:
        try:
            resp = await _client.post(
                self._url("/v1/exec"),
                json={**self._base(), "command": command, "cwd": cwd, "timeout": timeout},
                headers=self._h(),
                timeout=timeout + 10,
            )
            return _parse_response(resp, {"output": "", "return_code": -1})
        except Exception as e:
            logger.error(f"exec_command error: {e}")
            return {"success": False, "output": "", "error": str(e), "return_code": -1}

    async def read_file(self, path: str, start_line: int = 1, max_lines: int = 200) -> dict[str, Any]:
        try:
            resp = await _client.get(
                self._url("/v1/files"),
                params={**self._base(), "path": path, "start_line": start_line, "max_lines": max_lines},
                headers=self._h(),
            )
            return _parse_response(resp, {"content": "", "total_lines": 0})
        except Exception as e:
            return {"success": False, "content": "", "total_lines": 0, "error": str(e)}

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        try:
            resp = await _client.put(
                self._url("/v1/files"),
                json={**self._base(), "path": path, "content": content},
                headers=self._h(),
            )
            return _parse_response(resp, {})
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def list_dir(self, path: str = ".") -> dict[str, Any]:
        try:
            resp = await _client.get(
                self._url("/v1/dir"),
                params={**self._base(), "path": path},
                headers=self._h(),
            )
            return _parse_response(resp, {"entries": []})
        except Exception as e:
            return {"success": False, "entries": [], "error": str(e)}

    async def create_dir(self, path: str) -> dict[str, Any]:
        try:
            resp = await _client.post(
                self._url("/v1/dir"),
                json={**self._base(), "path": path},
                headers=self._h(),
            )
            return _parse_response(resp, {})
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def write_file_bytes(self, path: str, content: bytes) -> dict[str, Any]:
        """Write binary content to a file in the sandbox using base64 encoding."""
        import base64 as _b64

        b64 = _b64.b64encode(content).decode("ascii")
        tmp = path + ".__b64__"
        wr = await self.write_file(tmp, b64)
        if not wr.get("success"):
            return wr
        result = await self.exec_command(
            [
                "python3",
                "-c",
                f"import base64,pathlib; p=pathlib.Path('{path}'); p.parent.mkdir(parents=True,exist_ok=True); "
                f"p.write_bytes(base64.b64decode(pathlib.Path('{tmp}').read_text())); pathlib.Path('{tmp}').unlink()",
            ]
        )
        return (
            result if result.get("success") else {"success": False, "error": result.get("error", "Binary write failed")}
        )

    async def read_file_bytes(self, path: str) -> bytes | None:
        """Read binary file content from the sandbox using base64 encoding."""
        import base64 as _b64

        result = await self.exec_command(["base64", "-w", "0", path])
        if not result.get("success") or not result.get("output"):
            return None
        try:
            return _b64.b64decode(result["output"].strip())
        except Exception:
            return None

    async def file_exists(self, path: str) -> bool:
        try:
            resp = await _client.get(
                self._url("/v1/exists"),
                params={**self._base(), "path": path},
                headers=self._h(),
            )
            return resp.json().get("exists", False)
        except Exception:
            return False

    async def close(self) -> None:
        try:
            await self._backend.return_session(self)
        except Exception as e:
            logger.error(f"SandboxComputeSession.close error: {e}")
