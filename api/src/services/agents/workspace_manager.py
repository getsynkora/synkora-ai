"""
Workspace Manager for Agent Sessions.

Provides isolated sandbox environments per agent session with automatic
creation, directory structure management, and TTL-based cleanup.
"""

import json
import logging
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_WORKSPACE_BASE_PATH = "/tmp/synkora/workspaces"
DEFAULT_WORKSPACE_TTL_HOURS = 24
DEFAULT_WORKSPACE_MAX_SIZE_MB = 2000  # 2GB per workspace


class WorkspaceManager:
    """
    Manages isolated workspace environments for agent sessions.

    Each session gets an isolated directory structure:
    - {base_path}/{tenant_id}/{session_id}/repos/    - Git clones
    - {base_path}/{tenant_id}/{session_id}/files/    - General file operations
    - {base_path}/{tenant_id}/{session_id}/artifacts/ - Build outputs

    Workspaces are automatically created on first access and cleaned up
    after TTL expiration.
    """

    METADATA_FILE = ".workspace_meta.json"
    SUBDIRS = ["repos", "files", "artifacts"]

    def __init__(
        self,
        base_path: str | None = None,
        ttl_hours: int | None = None,
        max_size_mb: int | None = None,
    ):
        """
        Initialize the workspace manager.

        Args:
            base_path: Base directory for all workspaces
            ttl_hours: Workspace time-to-live in hours
            max_size_mb: Maximum workspace size in MB
        """
        self.base_path = base_path or self._get_base_path_from_settings()
        self.ttl_hours = ttl_hours or self._get_ttl_from_settings()
        self.max_size_mb = max_size_mb or self._get_max_size_from_settings()

    def _get_base_path_from_settings(self) -> str:
        """Get base path from settings or use default."""
        try:
            from src.config.settings import settings

            return getattr(settings, "workspace_base_path", DEFAULT_WORKSPACE_BASE_PATH)
        except Exception:
            return DEFAULT_WORKSPACE_BASE_PATH

    def _get_ttl_from_settings(self) -> int:
        """Get TTL from settings or use default."""
        try:
            from src.config.settings import settings

            return getattr(settings, "workspace_ttl_hours", DEFAULT_WORKSPACE_TTL_HOURS)
        except Exception:
            return DEFAULT_WORKSPACE_TTL_HOURS

    def _get_max_size_from_settings(self) -> int:
        """Get max size from settings or use default."""
        try:
            from src.config.settings import settings

            return getattr(settings, "workspace_max_size_mb", DEFAULT_WORKSPACE_MAX_SIZE_MB)
        except Exception:
            return DEFAULT_WORKSPACE_MAX_SIZE_MB

    def _get_workspace_path(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> Path:
        """
        Get the workspace path for a tenant/session.

        Args:
            tenant_id: Tenant UUID
            session_id: Session (conversation) UUID

        Returns:
            Path object for the workspace
        """
        return Path(self.base_path) / str(tenant_id) / str(session_id)

    def _create_metadata(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> dict[str, Any]:
        """
        Create workspace metadata.

        Args:
            tenant_id: Tenant UUID
            session_id: Session UUID

        Returns:
            Metadata dictionary
        """
        now = datetime.now(UTC).isoformat()
        return {
            "tenant_id": str(tenant_id),
            "session_id": str(session_id),
            "created_at": now,
            "last_accessed": now,
        }

    def _read_metadata(self, workspace_path: Path) -> dict[str, Any] | None:
        """
        Read workspace metadata.

        Args:
            workspace_path: Path to workspace

        Returns:
            Metadata dictionary or None if not found
        """
        metadata_file = workspace_path / self.METADATA_FILE
        if not metadata_file.exists():
            return None
        try:
            with open(metadata_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read workspace metadata: {e}")
            return None

    def _write_metadata(self, workspace_path: Path, metadata: dict[str, Any]) -> None:
        """
        Write workspace metadata.

        Args:
            workspace_path: Path to workspace
            metadata: Metadata dictionary
        """
        metadata_file = workspace_path / self.METADATA_FILE
        try:
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
        except OSError as e:
            logger.warning(f"Failed to write workspace metadata: {e}")

    def _update_last_accessed(self, workspace_path: Path) -> None:
        """
        Update the last_accessed timestamp in metadata.

        Args:
            workspace_path: Path to workspace
        """
        metadata = self._read_metadata(workspace_path)
        if metadata:
            metadata["last_accessed"] = datetime.now(UTC).isoformat()
            self._write_metadata(workspace_path, metadata)

    def get_or_create_workspace(self, tenant_id: uuid.UUID, session_id: uuid.UUID) -> str:
        """
        Get or create a workspace for the given tenant and session.

        Creates the workspace directory structure on first access.
        Updates the last_accessed timestamp on subsequent access.

        Args:
            tenant_id: Tenant UUID
            session_id: Session (conversation) UUID

        Returns:
            Absolute path to the workspace directory
        """
        workspace_path = self._get_workspace_path(tenant_id, session_id)

        if workspace_path.exists():
            # Update last accessed time
            self._update_last_accessed(workspace_path)
            logger.debug(f"Using existing workspace: {workspace_path}")
        else:
            # Create workspace directory structure
            workspace_path.mkdir(parents=True, exist_ok=True)

            # Create subdirectories
            for subdir in self.SUBDIRS:
                (workspace_path / subdir).mkdir(exist_ok=True)

            # Write metadata
            metadata = self._create_metadata(tenant_id, session_id)
            self._write_metadata(workspace_path, metadata)

            logger.info(f"Created new workspace: {workspace_path}")

        return str(workspace_path)

    def get_repos_path(self, workspace_path: str) -> str:
        """
        Get the repos subdirectory path.

        Args:
            workspace_path: Base workspace path

        Returns:
            Path to repos directory
        """
        return str(Path(workspace_path) / "repos")

    def get_files_path(self, workspace_path: str) -> str:
        """
        Get the files subdirectory path.

        Args:
            workspace_path: Base workspace path

        Returns:
            Path to files directory
        """
        return str(Path(workspace_path) / "files")

    def get_artifacts_path(self, workspace_path: str) -> str:
        """
        Get the artifacts subdirectory path.

        Args:
            workspace_path: Base workspace path

        Returns:
            Path to artifacts directory
        """
        return str(Path(workspace_path) / "artifacts")

    def get_repo_path(self, workspace_path: str, repo_name: str) -> str:
        """
        Get the full path for a named repository.

        Args:
            workspace_path: Base workspace path
            repo_name: Repository name (extracted from URL)

        Returns:
            Full path for the repository
        """
        # Sanitize repo name to prevent path traversal
        safe_name = repo_name.replace("/", "_").replace("..", "_").strip("._")
        return str(Path(workspace_path) / "repos" / safe_name)

    def repo_exists(self, workspace_path: str, repo_name: str) -> bool:
        """
        Check if a repository already exists in the workspace.

        Args:
            workspace_path: Base workspace path
            repo_name: Repository name

        Returns:
            True if repo exists, False otherwise
        """
        repo_path = Path(self.get_repo_path(workspace_path, repo_name))
        return repo_path.exists() and (repo_path / ".git").exists()

    def cleanup_workspace(self, workspace_path: str) -> bool:
        """
        Remove a workspace and all its contents.

        Args:
            workspace_path: Path to workspace to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            path = Path(workspace_path)
            if path.exists():
                shutil.rmtree(path)
                logger.info(f"Cleaned up workspace: {workspace_path}")

                # Try to remove empty parent (tenant) directory
                parent = path.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    logger.debug(f"Removed empty tenant directory: {parent}")

            return True
        except OSError as e:
            logger.error(f"Failed to cleanup workspace {workspace_path}: {e}")
            return False

    def cleanup_expired_workspaces(self, ttl_hours: int | None = None) -> dict[str, Any]:
        """
        Clean up all workspaces that have exceeded their TTL.

        Args:
            ttl_hours: Override default TTL (optional)

        Returns:
            Dictionary with cleanup statistics
        """
        ttl = ttl_hours or self.ttl_hours
        cutoff = datetime.now(UTC).timestamp() - (ttl * 3600)

        cleaned = 0
        failed = 0
        total_size = 0

        base = Path(self.base_path)
        if not base.exists():
            return {"cleaned": 0, "failed": 0, "total_size_mb": 0}

        # Iterate through tenant directories
        for tenant_dir in base.iterdir():
            if not tenant_dir.is_dir():
                continue

            # Iterate through session directories
            for session_dir in tenant_dir.iterdir():
                if not session_dir.is_dir():
                    continue

                # Read metadata to check last_accessed
                metadata = self._read_metadata(session_dir)
                if metadata:
                    try:
                        last_accessed = datetime.fromisoformat(metadata["last_accessed"]).timestamp()
                        if last_accessed < cutoff:
                            # Get size before cleanup
                            size = self._get_directory_size(session_dir)
                            total_size += size

                            if self.cleanup_workspace(str(session_dir)):
                                cleaned += 1
                            else:
                                failed += 1
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Invalid metadata for {session_dir}: {e}")
                        # If metadata is invalid, clean it up anyway
                        if self.cleanup_workspace(str(session_dir)):
                            cleaned += 1
                        else:
                            failed += 1

        logger.info(
            f"Workspace cleanup complete: {cleaned} cleaned, {failed} failed, {total_size / (1024 * 1024):.1f}MB freed"
        )
        return {
            "cleaned": cleaned,
            "failed": failed,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    def cleanup_tenant_workspaces(self, tenant_id: uuid.UUID) -> dict[str, Any]:
        """
        Clean up all workspaces for a specific tenant.

        Args:
            tenant_id: Tenant UUID

        Returns:
            Dictionary with cleanup statistics
        """
        tenant_path = Path(self.base_path) / str(tenant_id)
        if not tenant_path.exists():
            return {"cleaned": 0, "failed": 0, "total_size_mb": 0}

        cleaned = 0
        failed = 0
        total_size = 0

        for session_dir in tenant_path.iterdir():
            if session_dir.is_dir():
                size = self._get_directory_size(session_dir)
                total_size += size

                if self.cleanup_workspace(str(session_dir)):
                    cleaned += 1
                else:
                    failed += 1

        # Remove empty tenant directory
        if tenant_path.exists() and not any(tenant_path.iterdir()):
            try:
                tenant_path.rmdir()
            except OSError:
                pass

        return {
            "cleaned": cleaned,
            "failed": failed,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

    def _get_directory_size(self, path: Path) -> int:
        """
        Get the total size of a directory in bytes.

        Args:
            path: Directory path

        Returns:
            Total size in bytes
        """
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    total += entry.stat().st_size
        except OSError as e:
            logger.warning(f"Error calculating directory size: {e}")
        return total

    def get_workspace_info(self, workspace_path: str) -> dict[str, Any] | None:
        """
        Get information about a workspace.

        Args:
            workspace_path: Path to workspace

        Returns:
            Dictionary with workspace info or None if not found
        """
        path = Path(workspace_path)
        if not path.exists():
            return None

        metadata = self._read_metadata(path)
        size = self._get_directory_size(path)

        # Count repos
        repos_path = path / "repos"
        repos = []
        if repos_path.exists():
            repos = [d.name for d in repos_path.iterdir() if d.is_dir()]

        return {
            "path": workspace_path,
            "size_mb": round(size / (1024 * 1024), 2),
            "repos": repos,
            "repo_count": len(repos),
            "metadata": metadata,
        }

    def check_workspace_size(self, workspace_path: str) -> bool:
        """
        Check if workspace is within size limits.

        Args:
            workspace_path: Path to workspace

        Returns:
            True if within limits, False if exceeded
        """
        path = Path(workspace_path)
        if not path.exists():
            return True

        size_mb = self._get_directory_size(path) / (1024 * 1024)
        return size_mb <= self.max_size_mb


# Singleton instance
_workspace_manager: WorkspaceManager | None = None


def get_workspace_manager() -> WorkspaceManager:
    """
    Get the singleton workspace manager instance.

    Returns:
        WorkspaceManager instance
    """
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager


def get_workspace_path_from_config(config: dict | None) -> str | None:
    """
    Canonical helper used by all internal tools to resolve the workspace path.

    Resolution order:
    1. ``config["workspace_path"]`` — explicit override
    2. RuntimeContext from ``config["_runtime_context"]`` or the ContextVar
       - Uses ``conversation_id`` for interactive chat sessions
       - Falls back to a stable per-tenant UUID for Celery background tasks
         (where ``conversation_id`` is None)

    Returns the workspace path string, or None if unavailable.
    """
    import uuid as _uuid

    # 1. Explicit override in config
    if config and "workspace_path" in config:
        return config["workspace_path"]

    try:
        ctx = None
        if config and "_runtime_context" in config:
            ctx = config["_runtime_context"]
        else:
            from src.services.agents.runtime_context import get_runtime_context

            ctx = get_runtime_context()

        if ctx and ctx.tenant_id:
            # conversation_id is None in Celery tasks — use a stable per-tenant fallback
            # uuid5 requires a UUID object as namespace, not a string
            tenant_uuid = ctx.tenant_id if isinstance(ctx.tenant_id, _uuid.UUID) else _uuid.UUID(str(ctx.tenant_id))
            session_id = ctx.conversation_id or _uuid.uuid5(tenant_uuid, "background_tasks")
            return get_workspace_manager().get_or_create_workspace(ctx.tenant_id, session_id)

    except Exception as e:
        logger.debug(f"Could not resolve workspace path from RuntimeContext: {e}")

    return None
