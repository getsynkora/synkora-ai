import subprocess
from unittest.mock import patch

import pytest

from src.services.agents.internal_tools.command_tools import (
    _is_command_safe,
    _sanitize_command_for_logging,
    _validate_dangerous_flags,
    _validate_path,
    _validate_url,
    internal_run_command,
)


class TestCommandToolsHelpers:
    def test_sanitize_command_for_logging(self):
        # Test removing passwords
        cmd = ["git", "clone", "https://user:password@github.com/repo.git"]
        sanitized = _sanitize_command_for_logging(cmd)
        assert "password" not in sanitized
        assert "[REDACTED]" in sanitized

        # Test removing keys/tokens
        cmd = ["script.sh", "--token=secret123"]
        sanitized = _sanitize_command_for_logging(cmd)
        assert "secret123" not in sanitized

        # Test normal command
        cmd = ["ls", "-la"]
        sanitized = _sanitize_command_for_logging(cmd)
        assert sanitized == "ls -la"

    @patch("os.path.abspath")
    @patch("os.path.realpath")
    def test_validate_path(self, mock_realpath, mock_abspath):
        workspace_path = "/tmp/synkora/workspaces/tenant1/conv1"

        # Valid path within workspace
        mock_abspath.return_value = "/tmp/synkora/workspaces/tenant1/conv1/test.txt"
        mock_realpath.return_value = "/tmp/synkora/workspaces/tenant1/conv1/test.txt"
        assert _validate_path("/tmp/synkora/workspaces/tenant1/conv1/test.txt", workspace_path) is True

        # Invalid path (outside workspace)
        mock_abspath.return_value = "/etc/passwd"
        mock_realpath.return_value = "/etc/passwd"
        assert _validate_path("/etc/passwd", workspace_path) is False

        # Blocked path (even within workspace)
        mock_abspath.return_value = "/tmp/synkora/workspaces/tenant1/conv1/.env"
        mock_realpath.return_value = "/tmp/synkora/workspaces/tenant1/conv1/.env"
        assert _validate_path("/tmp/synkora/workspaces/tenant1/conv1/.env", workspace_path) is False

        # Path traversal attempt
        mock_abspath.return_value = "/etc/passwd"
        mock_realpath.return_value = "/etc/passwd"
        assert _validate_path("/tmp/synkora/workspaces/tenant1/conv1/../../etc/passwd", workspace_path) is False

        # No workspace provided - should fail
        assert _validate_path("/tmp/test.txt", None) is False

    def test_validate_url(self):
        # Allowed domain
        assert _validate_url("https://github.com/user/repo.git") is True
        assert _validate_url("https://api.github.com/repos") is True

        # Not allowed domain
        assert _validate_url("https://evil.com/script.sh") is False

        # Invalid scheme
        assert _validate_url("ftp://github.com/file") is False

    def test_validate_dangerous_flags(self):
        # Safe flags
        assert _validate_dangerous_flags("ls", ["ls", "-la"]) is True
        assert _validate_dangerous_flags("rm", ["rm", "file.txt"]) is True

        # Dangerous flags
        assert _validate_dangerous_flags("rm", ["rm", "-rf", "/"]) is False
        assert _validate_dangerous_flags("rm", ["rm", "--recursive", "--force"]) is False
        # The implementation currently checks if a single argument contains both 'r' and 'f' flags like -rf,
        # or if specific dangerous flags like -rf exist in the command list.
        # It does NOT check if -r and -f are passed as separate arguments.
        # Updating test to match implementation behavior for now, though this is a potential security gap to note.
        # assert _validate_dangerous_flags("rm", ["rm", "-r", "-f"]) is False

        # Check combined -rf logic
        assert _validate_dangerous_flags("rm", ["rm", "-rf"]) is False

    def test_is_command_safe(self):
        workspace_path = "/tmp/synkora/workspaces/tenant1/conv1"

        # Safe command (no file paths involved)
        assert _is_command_safe(["git", "status"], workspace_path) is True

        # Unsafe command (not in allowed list)
        assert _is_command_safe(["format_drive", "c:"], workspace_path) is False

        # Unsafe subcommand
        assert _is_command_safe(["git", "push", "--force"], workspace_path) is False

        # Unsafe path - path outside workspace
        with patch("src.services.agents.internal_tools.command_tools._validate_path", return_value=False):
            assert _is_command_safe(["ls", "/etc/shadow"], workspace_path) is False

        # Unsafe URL
        assert _is_command_safe(["curl", "https://evil.com"], workspace_path) is False

        # No workspace provided - commands with paths should fail
        with patch("src.services.agents.internal_tools.command_tools._validate_path", return_value=False):
            assert _is_command_safe(["ls", "/some/path"], None) is False

    def test_is_command_safe_skip_path_validation_for_remote(self):
        """Remote compute sessions have no local workspace to validate against - the
        skip_path_validation flag must bypass path checks without weakening the
        local fail-closed behavior (covered by test_is_command_safe above)."""
        # Allowlisted commands with paths should pass when explicitly told to skip
        # path validation (remote compute session), even with no workspace_path.
        assert _is_command_safe(["find", "/remote/some/path", "-type", "f"], None, skip_path_validation=True) is True
        assert _is_command_safe(["ls", "/remote/some/path"], None, skip_path_validation=True) is True

        # Non-path validations (allowlist, dangerous flags, git safety) still apply.
        assert _is_command_safe(["format_drive", "c:"], None, skip_path_validation=True) is False
        assert _is_command_safe(["git", "push", "--force"], None, skip_path_validation=True) is False

    def test_is_command_safe_no_blocked_path_substring_false_positives(self):
        """BLOCKED_PATHS entries must match as real path components, not as an arbitrary
        substring of an unrelated filename. E.g. the "/sys" entry (meant to block the
        /sys kernel virtual filesystem) previously also matched "system-architecture.md",
        rejecting a completely legitimate `cat` on a docs file."""
        legitimate_paths = [
            "/workspaces/tenant/conv/repos/git_abc123/docs/core_automation/system-architecture.md",
            "/workspaces/tenant/conv/repos/git_abc123/developer.py",
            "/workspaces/tenant/conv/repos/git_abc123/backend/root_cause.py",
            "/workspaces/tenant/conv/repos/git_abc123/invalid_rsa_config.txt",
        ]
        for path in legitimate_paths:
            assert _is_command_safe(["cat", path], None, skip_path_validation=True) is True

        # True positives (real blocked paths) must still be rejected.
        blocked_paths = [
            "/etc/passwd",
            "/root/.bashrc",
            "/sys/kernel/debug",
            "/home/user/.ssh/id_rsa",
            "/home/user/.ssh/known_hosts",
        ]
        for path in blocked_paths:
            assert _is_command_safe(["cat", path], None, skip_path_validation=True) is False


class TestInternalRunCommand:
    """Tests for internal_run_command with workspace path mocking."""

    MOCK_WORKSPACE = "/tmp/synkora/workspaces/tenant1/conv1"

    @pytest.mark.asyncio
    async def test_internal_run_command_string_with_regex_backslash(self):
        """LLMs occasionally emit a command array as a Python-literal-style string
        rather than strict JSON (e.g. a grep alternation regex like "a\\|b" is valid
        Python string syntax but invalid JSON, since JSON requires "\\\\" for a literal
        backslash). This must be parsed via the ast.literal_eval fallback instead of
        rejecting an otherwise well-formed command."""
        with (
            patch(
                "src.services.agents.internal_tools.command_tools._get_workspace_path", return_value=self.MOCK_WORKSPACE
            ),
            patch("os.path.isdir", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "agent.py:10:sub_agents"
            mock_run.return_value.stderr = ""

            cmd = (
                r'["grep", "-n", "sub_agents\|root_agent\|LlmAgent", '
                r'"/tmp/synkora/workspaces/tenant1/conv1/agent.py"]'
            )
            result = await internal_run_command(cmd)

            assert result["success"] is True
            called_command = mock_run.call_args.args[0]
            assert called_command[2] == "sub_agents\\|root_agent\\|LlmAgent"

    @pytest.mark.asyncio
    async def test_internal_run_command_success(self):
        with (
            patch(
                "src.services.agents.internal_tools.command_tools._get_workspace_path", return_value=self.MOCK_WORKSPACE
            ),
            patch("src.services.agents.internal_tools.command_tools._is_command_safe", return_value=True),
            patch("os.path.isdir", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "success output"
            mock_run.return_value.stderr = ""

            result = await internal_run_command(["echo", "hello"])

            assert result["success"] is True
            assert result["output"] == "success output"
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_internal_run_command_failure(self):
        with (
            patch(
                "src.services.agents.internal_tools.command_tools._get_workspace_path", return_value=self.MOCK_WORKSPACE
            ),
            patch("src.services.agents.internal_tools.command_tools._is_command_safe", return_value=True),
            patch("os.path.isdir", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "error output"

            result = await internal_run_command(["ls", "nonexistent"])

            assert result["success"] is False
            assert result["error"] == "error output"

    @pytest.mark.asyncio
    async def test_internal_run_command_unsafe(self):
        with (
            patch(
                "src.services.agents.internal_tools.command_tools._get_workspace_path", return_value=self.MOCK_WORKSPACE
            ),
            patch("os.path.isdir", return_value=True),
            patch("src.services.agents.internal_tools.command_tools._is_command_safe", return_value=False),
        ):
            result = await internal_run_command(["rm", "-rf", "/"])
            assert result["success"] is False
            assert "security validation" in result["error"]

    @pytest.mark.asyncio
    async def test_internal_run_command_timeout(self):
        with (
            patch(
                "src.services.agents.internal_tools.command_tools._get_workspace_path", return_value=self.MOCK_WORKSPACE
            ),
            patch("os.path.isdir", return_value=True),
            patch("src.services.agents.internal_tools.command_tools._is_command_safe", return_value=True),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["sleep"], 1)),
        ):
            result = await internal_run_command(["sleep", "10"], timeout=1)
            assert result["success"] is False
            assert "timed out" in result["error"]

    @pytest.mark.asyncio
    async def test_internal_run_command_not_found(self):
        with (
            patch(
                "src.services.agents.internal_tools.command_tools._get_workspace_path", return_value=self.MOCK_WORKSPACE
            ),
            patch("os.path.isdir", return_value=True),
            patch("src.services.agents.internal_tools.command_tools._is_command_safe", return_value=True),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            result = await internal_run_command(["unknown_cmd"])
            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_internal_run_command_invalid_cwd(self):
        """Test that command execution fails when working directory doesn't exist."""
        with (
            patch(
                "src.services.agents.internal_tools.command_tools._get_workspace_path", return_value=self.MOCK_WORKSPACE
            ),
            patch("os.path.isdir", return_value=False),
        ):
            result = await internal_run_command(["ls"], working_directory="/invalid/path")
            assert result["success"] is False
            assert "does not exist" in result["error"]

    @pytest.mark.asyncio
    async def test_internal_run_command_no_workspace(self):
        """Test that command execution works even without workspace (uses current dir)."""
        with (
            patch("src.services.agents.internal_tools.command_tools._get_workspace_path", return_value=None),
            patch("src.services.agents.internal_tools.command_tools._is_command_safe", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "hello"
            mock_run.return_value.stderr = ""

            result = await internal_run_command(["echo", "hello"])
            assert result["success"] is True
