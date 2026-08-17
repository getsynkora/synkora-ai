"""
Tests for git_helpers.py — shared path resolution used by git_repo_tools, git_branch_tools,
git_commit_tools, and gitlab_tools.

Regression coverage for: git clone succeeding at a path outside a remote ComputeSession's
own workspace root, causing every subsequent remote path-validated operation (exists/list/
read/write) to reject that same path as "escaping the workspace" (surfaced to callers as
"Repository path does not exist").
"""

from unittest.mock import MagicMock

from src.services.agents.internal_tools.git_helpers import _get_workspace_path


class TestGetWorkspacePathRemoteSession:
    """_get_workspace_path must use the active remote ComputeSession's own workspace root,
    not the local WorkspaceManager path, when a remote session is active."""

    def test_returns_remote_session_base_path_when_active(self):
        remote_session = MagicMock()
        remote_session.is_remote = True
        remote_session.base_path = "/workspaces/tenant-1/agent-1"

        config = {"_compute_session": remote_session}
        result = _get_workspace_path(config)

        assert result == "/workspaces/tenant-1/agent-1"

    def test_ignores_non_remote_compute_session(self):
        local_session = MagicMock()
        local_session.is_remote = False
        local_session.base_path = "/should/not/be/used"

        config = {"_compute_session": local_session, "workspace_path": "/tmp/local-workspace"}
        result = _get_workspace_path(config)

        assert result == "/tmp/local-workspace"

    def test_remote_session_without_base_path_falls_back_to_local(self):
        remote_session = MagicMock()
        remote_session.is_remote = True
        remote_session.base_path = None

        config = {"_compute_session": remote_session, "workspace_path": "/tmp/local-workspace"}
        result = _get_workspace_path(config)

        assert result == "/tmp/local-workspace"

    def test_falls_back_to_local_workspace_when_no_remote_session(self):
        config = {"workspace_path": "/tmp/local-workspace"}
        result = _get_workspace_path(config)

        assert result == "/tmp/local-workspace"

    def test_returns_none_for_empty_config(self):
        assert _get_workspace_path({}) is None

    def test_returns_none_for_none_config(self):
        assert _get_workspace_path(None) is None
