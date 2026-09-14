"""
synkora-sandbox — secure code execution microservice.


All agents share this service. Each agent gets an isolated workspace directory:
    /workspaces/{tenant_id}/{agent_id}/

Workspaces are ephemeral — no persistence, no S3. If the service restarts, workspaces
are gone. That is intentional.

Endpoints:
  POST   /v1/exec     — execute a command in agent workspace
  GET    /v1/files    — read a file
  PUT    /v1/files    — write a file
  GET    /v1/dir      — list a directory
  POST   /v1/dir      — create a directory
  GET    /v1/exists   — check file/dir existence
  DELETE /v1/workspace — remove workspace directory (called on session close)
  GET    /health      — liveness check

Auth: X-Sandbox-Key carries a short-lived tenant/workspace capability signed
with the mandatory SANDBOX_API_KEY. The signing key is never accepted as a token.
"""

import asyncio
import base64
import fcntl
import hashlib
import inspect
import signal
import stat
import tempfile
import uuid
from contextlib import asynccontextmanager
from functools import wraps
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from isolation import isolated_command, launcher_env
from capability import issue_capability, verify_capability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application):
    """Do not become ready on a host that cannot enforce execution isolation."""
    agent_id = uuid.uuid4().hex
    workspace = _workspace("startup-check", agent_id)
    try:
        result = await exec_command(
            ExecRequest(
                tenant_id="startup-check",
                agent_id=agent_id,
                command=["true"],
                timeout=5,
            ),
            issue_capability(SANDBOX_API_KEY, "startup-check", agent_id),
        )
        if not result["success"]:
            raise RuntimeError("Sandbox isolation self-test failed: " + result["error"])
    finally:
        if workspace.exists():
            shutil.rmtree(workspace)
    yield


app = FastAPI(title="synkora-sandbox", version="1.0.1", lifespan=lifespan)

WORKSPACES_BASE = Path(os.getenv("WORKSPACES_BASE", "/workspaces"))
SANDBOX_API_KEY = os.getenv("SANDBOX_API_KEY")
APP_ENV = os.getenv("APP_ENV", "development").lower()
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
MAX_CONCURRENT_EXEC = int(os.getenv("SANDBOX_MAX_CONCURRENT_EXEC", "4"))
# Default matches the reference code-execution service's own baked-in ceiling
# (CODE_EXECUTOR_MAX_COMMAND_TIMEOUT_SECONDS=3600) so any deployment that
# forgets to set SANDBOX_MAX_EXEC_TIMEOUT explicitly still allows genuinely
# long-running commands (e.g. full-history git clones) instead of silently
# reverting to a 5-minute cap.
MAX_EXEC_TIMEOUT = int(os.getenv("SANDBOX_MAX_EXEC_TIMEOUT", "3600"))
_exec_semaphore = asyncio.Semaphore(max(1, MAX_CONCURRENT_EXEC))
MAX_FILE_BYTES = 10 * 1024 * 1024


if (
    not SANDBOX_API_KEY
    or len(SANDBOX_API_KEY) < 32
    or SANDBOX_API_KEY.startswith("dev-")
):
    raise RuntimeError(
        "SANDBOX_API_KEY must be a nondefault secret of at least 32 characters"
    )


def _check_auth(key: str | None, tenant: str, workspace: str) -> None:
    if not verify_capability(key or "", SANDBOX_API_KEY or "", tenant, workspace):
        raise HTTPException(status_code=401, detail="Invalid workspace capability")


def _workspace(tenant_id: str, agent_id: str) -> Path:
    if not SAFE_ID_RE.fullmatch(tenant_id):
        raise HTTPException(status_code=400, detail="Invalid tenant_id")
    if not SAFE_ID_RE.fullmatch(agent_id):
        raise HTTPException(status_code=400, detail="Invalid agent_id")
    base = WORKSPACES_BASE.resolve()
    expected = base / tenant_id / agent_id
    if expected.resolve() != expected:
        raise HTTPException(status_code=400, detail="Workspace cannot contain symlinks")
    return expected


def _safe_path(workspace: Path, rel: str) -> Path:
    """Resolve path, ensuring it stays inside the workspace directory."""
    resolved_workspace = workspace.resolve()
    target = (
        Path(rel).resolve()
        if os.path.isabs(rel)
        else (resolved_workspace / rel).resolve()
    )
    try:
        target.relative_to(resolved_workspace)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path escapes workspace")
    return target


def _read_regular_file(target: Path) -> bytes:
    descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise HTTPException(400, "A regular file is required")
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File exceeds 10 MiB")
    return data


def _check_write_target(target: Path) -> None:
    if target.exists() and not stat.S_ISREG(target.stat().st_mode):
        raise HTTPException(400, "A regular file is required")


_BLOCKED_ENV_VARS = {
    "PATH", "LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH", "HOME", "TMPDIR",
    "SHELL", "ENV", "BASH_ENV", "CDPATH", "IFS", "PYTHONSTARTUP", "PYTHONHOME",
}


def _exec_env(extra_env: dict[str, str] | None) -> dict[str, str]:
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
        "LANG": "C.UTF-8",
    }
    if extra_env:
        filtered_env = {str(k): str(v) for k, v in extra_env.items() if k.upper() not in _BLOCKED_ENV_VARS}
        env.update(filtered_env)
    return env


def exclusive_workspace(fn):
    """Serialize host file operations with execution, including other workers.

    Programs may create symlinks while running. A lock prevents path-check/use
    races; the PID namespace removes descendants before the lock is released.
    Lock files live outside all exposed workspaces.
    """
    signature = inspect.signature(fn)

    @wraps(fn)
    async def wrapped(*args, **kwargs):
        values = signature.bind(*args, **kwargs).arguments
        req = values.get("req")
        tenant = req.tenant_id if req else values["tenant_id"]
        agent = req.agent_id if req else values["agent_id"]
        _check_auth(values.get("x_sandbox_key"), tenant, agent)
        workspace = _workspace(tenant, agent)
        lock_root = Path(tempfile.gettempdir()) / "synkora-sandbox-locks"
        lock_root.mkdir(mode=0o700, exist_ok=True)
        name = hashlib.sha256(str(workspace).encode()).hexdigest()
        with (lock_root / name).open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise HTTPException(
                    503, "Workspace is busy", headers={"Retry-After": "2"}
                )
            try:
                return await fn(*args, **kwargs)
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    return wrapped


# ─────────────────────────────────────────────────────────────────────────────
# Request models
# ─────────────────────────────────────────────────────────────────────────────


class ExecRequest(BaseModel):
    tenant_id: str
    agent_id: str
    command: list[str] = Field(min_length=1, max_length=256)
    cwd: str | None = None
    timeout: int = 300
    env: dict[str, str] | None = None


class FileWriteRequest(BaseModel):
    tenant_id: str
    agent_id: str
    path: str
    content: str = Field(max_length=10 * 1024 * 1024)


class DirRequest(BaseModel):
    tenant_id: str
    agent_id: str
    path: str = "."


class BinaryWriteRequest(BaseModel):
    tenant_id: str
    agent_id: str
    path: str
    content_base64: str = Field(max_length=14 * 1024 * 1024)


@app.get("/v1/files/binary")
@exclusive_workspace
async def read_binary(
    tenant_id: str,
    agent_id: str,
    path: str,
    x_sandbox_key: str | None = Header(default=None),
):
    workspace = _workspace(tenant_id, agent_id)
    target = _safe_path(workspace, path)
    data = _read_regular_file(target)
    return {"success": True, "content_base64": base64.b64encode(data).decode("ascii")}


@app.put("/v1/files/binary")
@exclusive_workspace
async def write_binary(
    req: BinaryWriteRequest, x_sandbox_key: str | None = Header(default=None)
):
    workspace = _workspace(req.tenant_id, req.agent_id)
    target = _safe_path(workspace, req.path)
    try:
        data = base64.b64decode(req.content_base64, validate=True)
    except ValueError as exc:
        raise HTTPException(400, "Invalid base64 content") from exc
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File exceeds 10 MiB")
    _check_write_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/v1/exec")
@exclusive_workspace
async def exec_command(
    req: ExecRequest,
    x_sandbox_key: str | None = Header(default=None),
):
    workspace = _workspace(req.tenant_id, req.agent_id)
    workspace.mkdir(parents=True, exist_ok=True)

    cwd = str(_safe_path(workspace, req.cwd)) if req.cwd else str(workspace)
    env = _exec_env(req.env)
    try:
        command = isolated_command(workspace, Path(cwd), req.command, env)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(503, str(exc)) from exc

    timeout = max(1, min(req.timeout, MAX_EXEC_TIMEOUT))

    acquired = False
    try:
        try:
            await asyncio.wait_for(_exec_semaphore.acquire(), timeout=1.0)
            acquired = True
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sandbox executor is at capacity",
                headers={"Retry-After": "2"},
            )

        proc = await asyncio.create_subprocess_exec(
            *command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=launcher_env(),
            start_new_session=True,
        )

        async def drain():
            captured = bytearray()
            truncated = False
            while chunk := await proc.stdout.read(65536):
                remaining = max(0, 8000 - len(captured))
                captured.extend(chunk[:remaining])
                truncated |= len(chunk) > remaining
            await proc.wait()
            return captured.decode("utf-8", errors="replace") + (
                "\n[OUTPUT TRUNCATED]" if truncated else ""
            )

        output = await asyncio.wait_for(drain(), timeout=timeout)
        return_code = proc.returncode or 0
        return {
            "success": return_code == 0,
            "output": output if return_code == 0 else "",
            "error": output if return_code != 0 else "",
            "return_code": return_code,
        }
    except asyncio.TimeoutError:
        if "proc" in locals() and proc.returncode is None:
            os.killpg(proc.pid, signal.SIGKILL)
            await proc.wait()
        return {
            "success": False,
            "output": "",
            "error": f"Command timed out after {timeout}s",
            "return_code": -1,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"exec error: {e}")
        return {"success": False, "output": "", "error": "Command execution failed", "return_code": -1}
    finally:
        if "proc" in locals() and proc.returncode is None:
            os.killpg(proc.pid, signal.SIGKILL)
            await proc.wait()
        if acquired:
            _exec_semaphore.release()


@app.get("/v1/files")
@exclusive_workspace
async def read_file(
    tenant_id: str,
    agent_id: str,
    path: str,
    start_line: int = 1,
    max_lines: int = 200,
    x_sandbox_key: str | None = Header(default=None),
):
    workspace = _workspace(tenant_id, agent_id)
    target = _safe_path(workspace, path)
    try:
        content = _read_regular_file(target).decode("utf-8", errors="replace")
        lines = content.splitlines(keepends=True)
        selected = lines[start_line - 1 : start_line - 1 + max_lines]
        return {
            "success": True,
            "content": "".join(selected),
            "total_lines": len(lines),
            "error": "",
        }
    except Exception as e:
        logger.error(f"read_file error: {e}")
        return {"success": False, "content": "", "total_lines": 0, "error": "File read failed"}


@app.put("/v1/files")
@exclusive_workspace
async def write_file(
    req: FileWriteRequest,
    x_sandbox_key: str | None = Header(default=None),
):
    workspace = _workspace(req.tenant_id, req.agent_id)
    target = _safe_path(workspace, req.path)
    try:
        _check_write_target(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(req.content, encoding="utf-8")
        return {"success": True, "error": ""}
    except Exception as e:
        logger.error(f"write_file error: {e}")
        return {"success": False, "error": "File write failed"}


@app.get("/v1/dir")
@exclusive_workspace
async def list_dir(
    tenant_id: str,
    agent_id: str,
    path: str = ".",
    x_sandbox_key: str | None = Header(default=None),
):
    workspace = _workspace(tenant_id, agent_id)
    target = _safe_path(workspace, path)
    try:
        entries = [
            {
                "name": item.name,
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else 0,
            }
            for item in sorted(target.iterdir())
            if not item.is_symlink()
        ]
        return {"success": True, "entries": entries, "error": ""}
    except Exception as e:
        logger.error(f"list_dir error: {e}")
        return {"success": False, "entries": [], "error": "Directory listing failed"}


@app.post("/v1/dir")
@exclusive_workspace
async def create_dir(
    req: DirRequest,
    x_sandbox_key: str | None = Header(default=None),
):
    workspace = _workspace(req.tenant_id, req.agent_id)
    target = _safe_path(workspace, req.path)
    try:
        target.mkdir(parents=True, exist_ok=True)
        return {"success": True, "error": ""}
    except Exception as e:
        logger.error(f"create_dir error: {e}")
        return {"success": False, "error": "Directory creation failed"}


@app.get("/v1/exists")
@exclusive_workspace
async def file_exists(
    tenant_id: str,
    agent_id: str,
    path: str,
    x_sandbox_key: str | None = Header(default=None),
):
    workspace = _workspace(tenant_id, agent_id)
    target = _safe_path(workspace, path)
    return {"exists": target.exists()}


@app.delete("/v1/workspace")
@exclusive_workspace
async def workspace_delete(
    tenant_id: str,
    agent_id: str,
    x_sandbox_key: str | None = Header(default=None),
):
    """Remove agent workspace directory. Called on session close."""
    workspace = _workspace(tenant_id, agent_id)
    try:
        if workspace.exists():
            shutil.rmtree(workspace)
        return {"success": True}
    except Exception as e:
        logger.error(f"workspace_delete error: {e}")
        return {"success": False, "error": "Workspace deletion failed"}
