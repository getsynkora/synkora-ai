"""
ComputeSession — abstract interface for agent compute backends.

All command and file-system tools route through a ComputeSession.
The platform resolves the correct backend (local workspace or remote SSH)
based on the agent's AgentCompute configuration.

Backends:
  LocalComputeSession   — wraps the existing workspace manager (backward-compatible).
  RemoteSSHComputeSession — executes on a remote server over SSH (see remote_backend.py).
"""

import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ComputeSession(ABC):
    """
    Abstract compute session.

    Provides a uniform interface for command execution and file-system
    operations regardless of whether the compute is local or remote.
    """

    @abstractmethod
    async def exec_command(
        self,
        command: list[str],
        cwd: str | None = None,
        timeout: int = 300,
        input_text: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a command on the compute target.

        Returns dict with keys: success (bool), output (str), error (str), return_code (int).
        """

    @abstractmethod
    async def read_file(
        self,
        path: str,
        start_line: int = 1,
        max_lines: int = 200,
    ) -> dict[str, Any]:
        """
        Read file content from the compute target.

        Returns dict with keys: success (bool), content (str), total_lines (int), error (str).
        """

    @abstractmethod
    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """
        Write content to a file on the compute target.

        Returns dict with keys: success (bool), error (str).
        """

    @abstractmethod
    async def list_dir(self, path: str) -> dict[str, Any]:
        """
        List directory contents on the compute target.

        Returns dict with keys: success (bool), entries (list[dict]), error (str).
        Each entry has: name (str), is_dir (bool), size (int).
        """

    @abstractmethod
    async def create_dir(self, path: str) -> dict[str, Any]:
        """
        Create a directory (and parents) on the compute target.

        Returns dict with keys: success (bool), error (str).
        """

    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """Return True if path exists on the compute target."""

    @property
    @abstractmethod
    def base_path(self) -> str | None:
        """Working base path for this session (equivalent to workspace path)."""

    @property
    @abstractmethod
    def is_remote(self) -> bool:
        """True if compute is on a remote host."""

    @abstractmethod
    async def close(self) -> None:
        """Release any resources held by this session (connection, etc.)."""


class LocalComputeSession(ComputeSession):
    """
    Local compute session — wraps the existing workspace.

    Compatibility adapter for local files. Command execution is forbidden;
    tenant commands require an isolated compute session.
    """

    def __init__(self, workspace_path: str | None, max_output_chars: int = 8000) -> None:
        self._workspace_path = workspace_path
        self._max_output_chars = max_output_chars

    @property
    def base_path(self) -> str | None:
        return self._workspace_path

    @property
    def is_remote(self) -> bool:
        return False

    async def exec_command(
        self,
        command: list[str],
        cwd: str | None = None,
        timeout: int = 300,
        input_text: str | None = None,
    ) -> dict[str, Any]:
        """Local application-process execution is forbidden for tenant commands."""
        return {
            "success": False,
            "output": "",
            "return_code": -1,
            "error": "Isolated compute is required for command execution",
        }

    async def read_file(
        self,
        path: str,
        start_line: int = 1,
        max_lines: int = 200,
    ) -> dict[str, Any]:
        """Read file lines locally."""
        try:
            if self._workspace_path:
                resolved = Path(path).resolve()
                workspace = Path(self._workspace_path).resolve()
                if not resolved.is_relative_to(workspace):
                    return {"success": False, "content": "", "total_lines": 0, "error": "Path escapes workspace"}
            with open(path, encoding="utf-8", errors="replace") as fh:
                all_lines = fh.readlines()
            selected = all_lines[start_line - 1 : start_line - 1 + max_lines]
            return {
                "success": True,
                "content": "".join(selected),
                "total_lines": len(all_lines),
                "error": "",
            }
        except FileNotFoundError:
            return {"success": False, "content": "", "total_lines": 0, "error": f"File not found: {path}"}
        except Exception as e:
            return {"success": False, "content": "", "total_lines": 0, "error": str(e)}

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Write content to a local file."""
        try:
            if self._workspace_path:
                resolved = Path(path).resolve()
                workspace = Path(self._workspace_path).resolve()
                if not resolved.is_relative_to(workspace):
                    return {"success": False, "error": "Path escapes workspace"}
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            return {"success": True, "error": ""}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def list_dir(self, path: str) -> dict[str, Any]:
        """List local directory contents."""
        try:
            entries = []
            for entry in os.scandir(path):
                entries.append(
                    {
                        "name": entry.name,
                        "is_dir": entry.is_dir(),
                        "size": entry.stat().st_size if entry.is_file() else 0,
                    }
                )
            return {"success": True, "entries": entries, "error": ""}
        except Exception as e:
            return {"success": False, "entries": [], "error": str(e)}

    async def create_dir(self, path: str) -> dict[str, Any]:
        """Create a local directory."""
        try:
            os.makedirs(path, exist_ok=True)
            return {"success": True, "error": ""}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def file_exists(self, path: str) -> bool:
        return os.path.exists(path)

    async def close(self) -> None:
        """The compatibility adapter owns no external resources."""
