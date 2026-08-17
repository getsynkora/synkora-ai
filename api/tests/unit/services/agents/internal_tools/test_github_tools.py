import subprocess
from unittest.mock import patch

import pytest

from src.services.agents.internal_tools.git_branch_tools import (
    internal_git_create_branch,
    internal_git_list_branches,
    internal_git_pull_changes,
    internal_git_switch_branch,
)
from src.services.agents.internal_tools.git_commit_tools import (
    internal_git_cherry_pick,
    internal_git_commit_and_push,
    internal_git_get_commit_history,
    internal_git_get_diff,
    internal_git_get_status,
    internal_git_revert_commit,
)
from src.services.agents.internal_tools.git_helpers import (
    MAX_REPO_SIZE_MB,
    _convert_https_to_ssh,
    _get_repo_size,
    _run_git_command,
    _sanitize_output,
    _validate_input,
)
from src.services.agents.internal_tools.git_repo_tools import (
    internal_git_add_remote,
    internal_git_cleanup_repo,
    internal_git_clone_repo,
)


class TestGitHubToolsHelpers:
    def test_validate_input(self):
        assert _validate_input("main", "branch_name")["valid"] is True
        assert _validate_input("feature/new-feat", "branch_name")["valid"] is True
        assert _validate_input("invalid char!", "branch_name")["valid"] is False

        assert _validate_input("https://github.com/user/repo.git", "repo_url")["valid"] is True
        assert _validate_input("git@github.com:user/repo.git", "repo_url")["valid"] is True
        assert _validate_input("ftp://github.com/repo", "repo_url")["valid"] is False

        # Blocked patterns
        assert _validate_input("rm -rf /", "branch_name")["valid"] is False
        assert _validate_input("$(ls)", "commit_message")["valid"] is False

    def test_sanitize_output(self):
        output = "token=123456\npassword: secret\nssh-rsa AAAA..."
        sanitized = _sanitize_output(output)
        assert "123456" not in sanitized
        assert "secret" not in sanitized
        assert "[REDACTED]" in sanitized

    @patch("subprocess.run")
    def test_run_git_command(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "output"
        mock_run.return_value.stderr = ""

        result = _run_git_command(["git", "status"], "/tmp")
        assert result["success"] is True
        assert result["output"] == "output"

        # Timeout
        mock_run.side_effect = subprocess.TimeoutExpired(["git"], 1)
        result = _run_git_command(["git", "status"], "/tmp")
        assert result["success"] is False
        assert "timed out" in result["error"]

        # Exception
        mock_run.side_effect = Exception("error")
        result = _run_git_command(["git", "status"], "/tmp")
        assert result["success"] is False
        assert "error" in result["error"]

    def test_convert_https_to_ssh(self):
        url = "https://github.com/user/repo.git"
        assert _convert_https_to_ssh(url) == "git@github.com:user/repo.git"

        url = "git@github.com:user/repo.git"
        assert _convert_https_to_ssh(url) == url

    @patch("os.walk")
    @patch("os.path.getsize")
    @patch("os.path.exists")
    def test_get_repo_size(self, mock_exists, mock_getsize, mock_walk):
        mock_walk.return_value = [("/tmp", [], ["file1", "file2"])]
        mock_exists.return_value = True
        mock_getsize.return_value = 1024 * 1024  # 1MB

        size = _get_repo_size("/tmp")
        assert size == 2.0  # 2MB


class TestInternalGitHubTools:
    """Test GitHub tools with workspace path mocking."""

    MOCK_WORKSPACE = "/tmp/synkora/workspaces/tenant1/conv1"
    MOCK_REPO_PATH = "/tmp/synkora/workspaces/tenant1/conv1/repos/git_abc123"

    @pytest.mark.asyncio
    async def test_internal_git_clone_repo(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_repo_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch("os.makedirs"),
            patch("src.services.agents.internal_tools.git_repo_tools.async_run_git_command") as mock_run,
            patch("src.services.agents.internal_tools.git_repo_tools.async_get_repo_size", return_value=10.0),
            patch("src.services.agents.internal_tools.git_repo_tools.uuid.uuid4") as mock_uuid,
            patch(
                "src.services.agents.internal_tools.github_auth_helper.prepare_authenticated_git_url",
                return_value=("https://github.com/user/repo.git", False),
            ),
        ):
            mock_uuid.return_value.hex = "abc123456789"
            mock_run.return_value = {"success": True}

            result = await internal_git_clone_repo("https://github.com/user/repo.git")
            assert result["success"] is True
            assert self.MOCK_WORKSPACE in result["repo_path"]

            # Fail clone
            mock_run.return_value = {"success": False, "error": "failed"}
            result = await internal_git_clone_repo("https://github.com/user/repo.git")
            assert result["success"] is False

            # Too large
            mock_run.return_value = {"success": True}
            with patch(
                "src.services.agents.internal_tools.git_repo_tools.async_get_repo_size",
                return_value=MAX_REPO_SIZE_MB + 1,
            ):
                with patch("shutil.rmtree"):
                    result = await internal_git_clone_repo("https://github.com/user/repo.git")
                    assert result["success"] is False
                    assert "exceeds maximum" in result["error"]

    @pytest.mark.asyncio
    async def test_internal_git_clone_repo_defaults_to_shallow_clone(self):
        """A single, long-lived full-clone HTTP transfer is fragile to mid-stream
        network failures on large repos (confirmed via core-automation's own
        clone_repository tool, which defaults to depth=1). We match that default."""
        with (
            patch(
                "src.services.agents.internal_tools.git_repo_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch("os.makedirs"),
            patch("src.services.agents.internal_tools.git_repo_tools.async_run_git_command") as mock_run,
            patch("src.services.agents.internal_tools.git_repo_tools.async_get_repo_size", return_value=10.0),
            patch("src.services.agents.internal_tools.git_repo_tools.uuid.uuid4") as mock_uuid,
            patch(
                "src.services.agents.internal_tools.github_auth_helper.prepare_authenticated_git_url",
                return_value=("https://github.com/user/repo.git", False),
            ),
        ):
            mock_uuid.return_value.hex = "abc123456789"
            mock_run.return_value = {"success": True}

            result = await internal_git_clone_repo("https://github.com/user/repo.git")
            assert result["success"] is True

            clone_cmd = mock_run.call_args_list[0].args[0]
            assert clone_cmd[:2] == ["git", "clone"]
            assert "--depth" in clone_cmd
            assert clone_cmd[clone_cmd.index("--depth") + 1] == "1"

    @pytest.mark.asyncio
    async def test_internal_git_clone_repo_depth_zero_is_full_clone(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_repo_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch("os.makedirs"),
            patch("src.services.agents.internal_tools.git_repo_tools.async_run_git_command") as mock_run,
            patch("src.services.agents.internal_tools.git_repo_tools.async_get_repo_size", return_value=10.0),
            patch("src.services.agents.internal_tools.git_repo_tools.uuid.uuid4") as mock_uuid,
            patch(
                "src.services.agents.internal_tools.github_auth_helper.prepare_authenticated_git_url",
                return_value=("https://github.com/user/repo.git", False),
            ),
        ):
            mock_uuid.return_value.hex = "abc123456789"
            mock_run.return_value = {"success": True}

            result = await internal_git_clone_repo("https://github.com/user/repo.git", depth=0)
            assert result["success"] is True

            clone_cmd = mock_run.call_args_list[0].args[0]
            assert "--depth" not in clone_cmd

    @pytest.mark.asyncio
    async def test_internal_git_clone_repo_with_branch(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_repo_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch("os.makedirs"),
            patch("src.services.agents.internal_tools.git_repo_tools.async_run_git_command") as mock_run,
            patch("src.services.agents.internal_tools.git_repo_tools.async_get_repo_size", return_value=10.0),
            patch("src.services.agents.internal_tools.git_repo_tools.uuid.uuid4") as mock_uuid,
            patch(
                "src.services.agents.internal_tools.github_auth_helper.prepare_authenticated_git_url",
                return_value=("https://github.com/user/repo.git", False),
            ),
        ):
            mock_uuid.return_value.hex = "abc123456789"
            mock_run.return_value = {"success": True}

            result = await internal_git_clone_repo("https://github.com/user/repo.git", branch="develop")
            assert result["success"] is True

            clone_cmd = mock_run.call_args_list[0].args[0]
            assert "--branch" in clone_cmd
            assert clone_cmd[clone_cmd.index("--branch") + 1] == "develop"

    @pytest.mark.asyncio
    async def test_internal_git_create_branch(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_branch_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_branch_tools.async_validate_repo_path",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_branch_tools.async_run_git_command") as mock_run,
        ):
            mock_run.return_value = {"success": True}

            result = await internal_git_create_branch(self.MOCK_REPO_PATH, "feature-1")
            assert result["success"] is True
            assert result["branch"] == "feature-1"

    @pytest.mark.asyncio
    async def test_internal_git_get_status(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_commit_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_commit_tools.async_validate_repo_path",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_commit_tools.async_run_git_command") as mock_run,
        ):
            mock_run.return_value = {"success": True, "output": "M  modified.txt\nA  added.txt\n?? untracked.txt"}

            result = await internal_git_get_status(self.MOCK_REPO_PATH)
            assert result["success"] is True
            assert "modified.txt" in result["staged_files"]
            assert "added.txt" in result["staged_files"]
            assert "untracked.txt" in result["untracked_files"]
            assert result["has_changes"] is True

    @pytest.mark.asyncio
    async def test_internal_git_switch_branch(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_branch_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_branch_tools.async_validate_repo_path",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_branch_tools.async_run_git_command") as mock_run,
        ):
            mock_run.return_value = {"success": True}
            result = await internal_git_switch_branch(self.MOCK_REPO_PATH, "main")
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_internal_git_switch_branch_widens_fetch_for_shallow_clone(self):
        """Shallow clones default to single-branch mode, so a branch other than
        the one cloned isn't fetched yet. switch_branch should widen the fetch
        and retry instead of failing outright."""
        with (
            patch(
                "src.services.agents.internal_tools.git_branch_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_branch_tools.async_validate_repo_path",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_branch_tools.async_run_git_command") as mock_run,
        ):
            call_log: list[list[str]] = []

            async def _fake_run(command, *_args, **_kwargs):
                call_log.append(command)
                if command[:2] == ["git", "checkout"] and len(call_log) == 1:
                    return {"success": False, "error": "pathspec 'feature' did not match"}
                return {"success": True}

            mock_run.side_effect = _fake_run

            result = await internal_git_switch_branch(self.MOCK_REPO_PATH, "feature")
            assert result["success"] is True
            assert ["git", "fetch", "origin", "feature"] in call_log
            assert call_log.count(["git", "checkout", "feature"]) == 2

    @pytest.mark.asyncio
    async def test_internal_git_list_branches(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_branch_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_branch_tools.async_validate_repo_path",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_branch_tools.async_run_git_command") as mock_run,
        ):
            mock_run.return_value = {"success": True, "output": "* main\n  feature"}

            result = await internal_git_list_branches(self.MOCK_REPO_PATH)
            assert result["success"] is True
            assert "main" in result["branches"]
            assert result["current_branch"] == "main"

    @pytest.mark.asyncio
    async def test_internal_git_pull_changes(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_branch_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_branch_tools.async_validate_repo_path",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_branch_tools.async_run_git_command") as mock_run,
        ):
            mock_run.return_value = {"success": True, "output": "Updated"}
            result = await internal_git_pull_changes(self.MOCK_REPO_PATH)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_internal_git_get_diff(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_commit_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_commit_tools.async_validate_repo_path",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_commit_tools.async_run_git_command") as mock_run,
        ):
            mock_run.return_value = {"success": True, "output": "diff content"}
            result = await internal_git_get_diff(self.MOCK_REPO_PATH)
            assert result["success"] is True
            assert result["has_changes"] is True

    @pytest.mark.asyncio
    async def test_internal_git_get_commit_history(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_commit_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_commit_tools.async_validate_repo_path",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_commit_tools.async_run_git_command") as mock_run,
        ):
            mock_run.return_value = {"success": True, "output": "abc1234 Initial commit\ndef5678 Second commit"}

            result = await internal_git_get_commit_history(self.MOCK_REPO_PATH)
            assert result["success"] is True
            assert len(result["commits"]) == 2
            assert result["commits"][0]["hash"] == "abc1234"

    @pytest.mark.asyncio
    async def test_internal_git_cherry_pick(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_commit_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_commit_tools.async_validate_repo_path",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_commit_tools.async_run_git_command") as mock_run,
        ):
            mock_run.return_value = {"success": True}
            result = await internal_git_cherry_pick(self.MOCK_REPO_PATH, "abc1234")
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_internal_git_revert_commit(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_commit_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_commit_tools.async_validate_repo_path",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_commit_tools.async_run_git_command") as mock_run,
        ):
            mock_run.return_value = {"success": True}
            result = await internal_git_revert_commit(self.MOCK_REPO_PATH, "abc1234")
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_internal_git_commit_and_push(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_commit_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_commit_tools.async_validate_repo_path",
                return_value=(True, None),
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_commit_tools.async_run_git_command") as mock_run,
        ):
            mock_run.side_effect = [
                {"success": True},  # git config user.email
                {"success": True},  # git config user.name
                {"success": True},  # add
                {"success": True},  # commit
                {"success": True},  # push
            ]

            result = await internal_git_commit_and_push(self.MOCK_REPO_PATH, "main", "msg")
            assert result["success"] is True
            assert result["pushed"] is True

            # No changes to commit
            mock_run.side_effect = [
                {"success": True},  # git config user.email
                {"success": True},  # git config user.name
                {"success": True},  # add
                {"success": False, "output": "nothing to commit", "error": ""},  # commit fail but nothing to commit
            ]
            result = await internal_git_commit_and_push(self.MOCK_REPO_PATH, "main", "msg")
            assert result["success"] is True
            assert result["committed"] is False

    @pytest.mark.asyncio
    async def test_internal_git_add_remote(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_repo_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_repo_tools.async_validate_repo_path", return_value=(True, None)
            ),
            patch("os.path.exists", return_value=True),
            patch("src.services.agents.internal_tools.git_repo_tools.async_run_git_command") as mock_run,
        ):
            # Remote doesn't exist, add it
            mock_run.side_effect = [
                {"success": False},  # get-url
                {"success": True},  # add
            ]
            result = await internal_git_add_remote(self.MOCK_REPO_PATH, "origin", "url")
            assert result["success"] is True

            # Remote exists, match
            mock_run.side_effect = [
                {"success": True, "output": "url"},  # get-url
            ]
            result = await internal_git_add_remote(self.MOCK_REPO_PATH, "origin", "url")
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_internal_git_cleanup_repo(self):
        with (
            patch(
                "src.services.agents.internal_tools.git_repo_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_repo_tools.async_validate_repo_path", return_value=(True, None)
            ),
            patch("os.path.exists", return_value=True),
            patch("shutil.rmtree") as mock_rm,
        ):
            # Safe path within workspace
            result = await internal_git_cleanup_repo(self.MOCK_REPO_PATH)
            assert result["success"] is True
            mock_rm.assert_called_with(self.MOCK_REPO_PATH, ignore_errors=True)

        # Unsafe path outside workspace
        with (
            patch(
                "src.services.agents.internal_tools.git_repo_tools._get_workspace_path",
                return_value=self.MOCK_WORKSPACE,
            ),
            patch(
                "src.services.agents.internal_tools.git_repo_tools.async_validate_repo_path",
                return_value=(False, "Path outside workspace"),
            ),
            patch("os.path.exists", return_value=True),
        ):
            result = await internal_git_cleanup_repo("/etc/repo")
            assert result["success"] is False
            assert "workspace" in result["error"]
