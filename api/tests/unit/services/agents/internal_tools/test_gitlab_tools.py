"""
Tests for gitlab_tools.py - GitLab API Tools

Tests the GitLab tools for repository and project management including:
- User/project information
- Merge request management
- Issue management
- Repository operations
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.internal_tools.git_helpers import (
    _run_git_command,
    async_get_repo_size,
)
from src.services.agents.internal_tools.gitlab_tools import (
    _get_workspace_path,
    _make_gitlab_request,
    internal_gitlab_approve_mr,
    internal_gitlab_clone_repo,
    internal_gitlab_close_mr,
    internal_gitlab_create_issue,
    internal_gitlab_create_merge_request,
    internal_gitlab_get_file,
    internal_gitlab_get_issue,
    internal_gitlab_get_merge_request,
    internal_gitlab_get_mr_diff,
    internal_gitlab_get_project,
    internal_gitlab_get_user,
    internal_gitlab_list_branches,
    internal_gitlab_list_issues,
    internal_gitlab_list_merge_requests,
    internal_gitlab_list_projects,
    internal_gitlab_merge_mr,
    internal_gitlab_post_issue_comment,
    internal_gitlab_post_mr_comment,
    internal_gitlab_update_issue,
)


class TestGetWorkspacePath:
    """Tests for _get_workspace_path helper function."""

    def test_returns_workspace_from_config(self):
        config = {"workspace_path": "/tmp/workspace"}
        result = _get_workspace_path(config)
        assert result == "/tmp/workspace"

    def test_returns_none_for_empty_config(self):
        result = _get_workspace_path({})
        # Will return None since RuntimeContext won't have valid data
        assert result is None

    def test_returns_none_for_none_config(self):
        result = _get_workspace_path(None)
        assert result is None


class TestMakeGitlabRequest:
    """Tests for _make_gitlab_request helper function."""

    @pytest.mark.asyncio
    async def test_get_request_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"id": 1}'
        mock_response.json.return_value = {"id": 1}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            credentials = {"access_token": "test_token", "base_url": "https://gitlab.com"}
            result = await _make_gitlab_request("/user", credentials=credentials)

            assert result == {"id": 1}

    @pytest.mark.asyncio
    async def test_post_request_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = b'{"id": 1}'
        mock_response.json.return_value = {"id": 1}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.post.return_value = mock_response

            credentials = {"access_token": "test_token", "base_url": "https://gitlab.com"}
            result = await _make_gitlab_request(
                "/projects/1/issues", method="POST", credentials=credentials, json_data={"title": "Test"}
            )

            assert result == {"id": 1}

    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            credentials = {"access_token": "bad_token", "base_url": "https://gitlab.com"}

            with pytest.raises(ValueError) as exc_info:
                await _make_gitlab_request("/user", credentials=credentials)

            assert "authentication failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_404_raises_not_found(self):
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.get.return_value = mock_response

            credentials = {"access_token": "token", "base_url": "https://gitlab.com"}

            with pytest.raises(ValueError) as exc_info:
                await _make_gitlab_request("/projects/999", credentials=credentials)

            assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_204_returns_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.content = b""
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.delete.return_value = mock_response

            credentials = {"access_token": "token", "base_url": "https://gitlab.com"}
            result = await _make_gitlab_request("/projects/1/issues/1", method="DELETE", credentials=credentials)

            assert result == {"success": True}


class TestInternalGitlabGetUser:
    """Tests for internal_gitlab_get_user function."""

    @pytest.mark.asyncio
    async def test_requires_runtime_context(self):
        result = await internal_gitlab_get_user()
        assert result["success"] is False
        assert "Runtime context is required" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_user_info(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 1,
                "username": "testuser",
                "name": "Test User",
                "email": "test@example.com",
                "avatar_url": "https://gitlab.com/avatar.png",
                "web_url": "https://gitlab.com/testuser",
                "state": "active",
                "is_admin": False,
            }

            result = await internal_gitlab_get_user(runtime_context=mock_runtime_context)

            assert result["success"] is True
            assert result["user"]["username"] == "testuser"
            assert result["user"]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_handles_error(self):
        mock_runtime_context = MagicMock()

        with patch(
            "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
        ) as mock_creds:
            mock_creds.side_effect = ValueError("No token available")

            result = await internal_gitlab_get_user(runtime_context=mock_runtime_context)

            assert result["success"] is False
            assert "No token available" in result["error"]


class TestInternalGitlabListProjects:
    """Tests for internal_gitlab_list_projects function."""

    @pytest.mark.asyncio
    async def test_requires_runtime_context(self):
        result = await internal_gitlab_list_projects()
        assert result["success"] is False
        assert "Runtime context is required" in result["error"]

    @pytest.mark.asyncio
    async def test_lists_projects(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = [
                {
                    "id": 1,
                    "name": "Project 1",
                    "path_with_namespace": "user/project1",
                    "description": "Test project",
                    "web_url": "https://gitlab.com/user/project1",
                    "default_branch": "main",
                },
                {
                    "id": 2,
                    "name": "Project 2",
                    "path_with_namespace": "user/project2",
                    "default_branch": "master",
                },
            ]

            result = await internal_gitlab_list_projects(runtime_context=mock_runtime_context)

            assert result["success"] is True
            assert result["count"] == 2
            assert len(result["projects"]) == 2
            assert result["projects"][0]["name"] == "Project 1"


class TestInternalGitlabGetProject:
    """Tests for internal_gitlab_get_project function."""

    @pytest.mark.asyncio
    async def test_requires_runtime_context(self):
        result = await internal_gitlab_get_project(project_id="123")
        assert result["success"] is False
        assert "Runtime context is required" in result["error"]

    @pytest.mark.asyncio
    async def test_requires_project_id(self):
        mock_runtime_context = MagicMock()
        result = await internal_gitlab_get_project(project_id=None, runtime_context=mock_runtime_context)
        assert result["success"] is False
        assert "Project ID is required" in result["error"]

    @pytest.mark.asyncio
    async def test_gets_project_details(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 123,
                "name": "My Project",
                "path_with_namespace": "user/my-project",
                "description": "Project description",
                "web_url": "https://gitlab.com/user/my-project",
                "default_branch": "main",
                "visibility": "private",
                "namespace": {"full_path": "user"},
            }

            result = await internal_gitlab_get_project(project_id="123", runtime_context=mock_runtime_context)

            assert result["success"] is True
            assert result["project"]["id"] == 123
            assert result["project"]["name"] == "My Project"


class TestInternalGitlabCreateMergeRequest:
    """Tests for internal_gitlab_create_merge_request function."""

    @pytest.mark.asyncio
    async def test_requires_runtime_context(self):
        result = await internal_gitlab_create_merge_request(
            project_id="123", source_branch="feature", target_branch="main", title="Test MR"
        )
        assert result["success"] is False
        assert "Runtime context is required" in result["error"]

    @pytest.mark.asyncio
    async def test_requires_all_fields(self):
        mock_runtime_context = MagicMock()
        result = await internal_gitlab_create_merge_request(
            project_id="123", source_branch="", target_branch="main", title="Test", runtime_context=mock_runtime_context
        )
        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_creates_merge_request(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 1,
                "iid": 1,
                "title": "Test MR",
                "state": "opened",
                "web_url": "https://gitlab.com/user/project/-/merge_requests/1",
                "source_branch": "feature",
                "target_branch": "main",
                "author": {"username": "testuser"},
            }

            result = await internal_gitlab_create_merge_request(
                project_id="123",
                source_branch="feature",
                target_branch="main",
                title="Test MR",
                runtime_context=mock_runtime_context,
            )

            assert result["success"] is True
            assert result["merge_request"]["iid"] == 1
            assert result["merge_request"]["title"] == "Test MR"


class TestInternalGitlabListMergeRequests:
    """Tests for internal_gitlab_list_merge_requests function."""

    @pytest.mark.asyncio
    async def test_lists_merge_requests(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = [
                {
                    "id": 1,
                    "iid": 1,
                    "title": "MR 1",
                    "state": "opened",
                    "source_branch": "feature1",
                    "target_branch": "main",
                    "author": {"username": "user1"},
                },
            ]

            result = await internal_gitlab_list_merge_requests(project_id="123", runtime_context=mock_runtime_context)

            assert result["success"] is True
            assert result["count"] == 1
            assert result["merge_requests"][0]["title"] == "MR 1"


class TestInternalGitlabGetMergeRequest:
    """Tests for internal_gitlab_get_merge_request function."""

    @pytest.mark.asyncio
    async def test_requires_project_id_and_iid(self):
        mock_runtime_context = MagicMock()
        result = await internal_gitlab_get_merge_request(
            project_id="", merge_request_iid=0, runtime_context=mock_runtime_context
        )
        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_gets_merge_request_details(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 1,
                "iid": 1,
                "title": "Test MR",
                "description": "Description",
                "state": "opened",
                "web_url": "https://gitlab.com/user/project/-/merge_requests/1",
                "source_branch": "feature",
                "target_branch": "main",
                "author": {"username": "testuser"},
                "assignee": {"username": "reviewer"},
                "has_conflicts": False,
                "changes_count": "5",
            }

            result = await internal_gitlab_get_merge_request(
                project_id="123", merge_request_iid=1, runtime_context=mock_runtime_context
            )

            assert result["success"] is True
            assert result["merge_request"]["has_conflicts"] is False


class TestInternalGitlabListIssues:
    """Tests for internal_gitlab_list_issues function."""

    @pytest.mark.asyncio
    async def test_lists_issues(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = [
                {
                    "id": 1,
                    "iid": 1,
                    "title": "Bug fix",
                    "state": "opened",
                    "labels": ["bug"],
                    "author": {"username": "reporter"},
                },
            ]

            result = await internal_gitlab_list_issues(project_id="123", runtime_context=mock_runtime_context)

            assert result["success"] is True
            assert result["count"] == 1
            assert result["issues"][0]["labels"] == ["bug"]


class TestInternalGitlabCreateIssue:
    """Tests for internal_gitlab_create_issue function."""

    @pytest.mark.asyncio
    async def test_requires_project_id_and_title(self):
        mock_runtime_context = MagicMock()
        result = await internal_gitlab_create_issue(project_id="", title="", runtime_context=mock_runtime_context)
        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_creates_issue(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 1,
                "iid": 1,
                "title": "New Bug",
                "state": "opened",
                "web_url": "https://gitlab.com/user/project/-/issues/1",
                "author": {"username": "testuser"},
            }

            result = await internal_gitlab_create_issue(
                project_id="123", title="New Bug", description="Bug description", runtime_context=mock_runtime_context
            )

            assert result["success"] is True
            assert result["issue"]["title"] == "New Bug"


class TestInternalGitlabListBranches:
    """Tests for internal_gitlab_list_branches function."""

    @pytest.mark.asyncio
    async def test_lists_branches(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = [
                {
                    "name": "main",
                    "merged": False,
                    "protected": True,
                    "default": True,
                    "commit": {
                        "id": "abc123",
                        "message": "Initial commit",
                        "author_name": "Author",
                    },
                },
                {
                    "name": "feature",
                    "merged": False,
                    "protected": False,
                    "default": False,
                    "commit": {
                        "id": "def456",
                        "message": "Feature commit",
                        "author_name": "Author",
                    },
                },
            ]

            result = await internal_gitlab_list_branches(project_id="123", runtime_context=mock_runtime_context)

            assert result["success"] is True
            assert result["count"] == 2
            assert result["branches"][0]["name"] == "main"
            assert result["branches"][0]["protected"] is True


class TestInternalGitlabGetFile:
    """Tests for internal_gitlab_get_file function."""

    @pytest.mark.asyncio
    async def test_requires_project_id_and_file_path(self):
        mock_runtime_context = MagicMock()
        result = await internal_gitlab_get_file(project_id="", file_path="", runtime_context=mock_runtime_context)
        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_gets_file_content(self):
        mock_runtime_context = MagicMock()
        import base64

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "file_name": "README.md",
                "file_path": "README.md",
                "size": 100,
                "encoding": "base64",
                "ref": "main",
                "content": base64.b64encode(b"# Hello World").decode("utf-8"),
                "last_commit_id": "abc123",
            }

            result = await internal_gitlab_get_file(
                project_id="123", file_path="README.md", runtime_context=mock_runtime_context
            )

            assert result["success"] is True
            assert result["file"]["file_name"] == "README.md"
            assert "# Hello World" in result["file"]["content"]


class TestInternalGitlabCloneRepo:
    """Tests for internal_gitlab_clone_repo function."""

    @pytest.mark.asyncio
    async def test_requires_repo_url(self):
        result = await internal_gitlab_clone_repo(repo_url="")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_requires_workspace_path(self):
        result = await internal_gitlab_clone_repo(repo_url="https://gitlab.com/user/repo.git", config={})
        assert result["success"] is False
        assert "workspace" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_defaults_to_shallow_clone(self):
        """Matches core-automation's own clone_repository default (depth=1):
        a full clone is a single long-lived, large HTTP transfer, which is
        fragile to mid-stream network failures regardless of repo size."""
        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_workspace_path",
                return_value="/tmp/synkora/workspaces/tenant1/conv1",
            ),
            patch("src.services.agents.internal_tools.gitlab_tools.async_makedirs"),
            patch("src.services.agents.internal_tools.gitlab_tools.async_run_git_command") as mock_run,
            patch("src.services.agents.internal_tools.gitlab_tools.async_get_repo_size", return_value=10.0),
            patch("src.services.agents.internal_tools.gitlab_tools.uuid.uuid4") as mock_uuid,
        ):
            mock_uuid.return_value.hex = "abc123456789"
            mock_run.return_value = {"success": True}

            result = await internal_gitlab_clone_repo(repo_url="https://gitlab.com/user/repo.git")
            assert result["success"] is True

            clone_cmd = mock_run.call_args_list[0].args[0]
            assert "--depth" in clone_cmd
            assert clone_cmd[clone_cmd.index("--depth") + 1] == "1"

    @pytest.mark.asyncio
    async def test_depth_zero_is_full_clone(self):
        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_workspace_path",
                return_value="/tmp/synkora/workspaces/tenant1/conv1",
            ),
            patch("src.services.agents.internal_tools.gitlab_tools.async_makedirs"),
            patch("src.services.agents.internal_tools.gitlab_tools.async_run_git_command") as mock_run,
            patch("src.services.agents.internal_tools.gitlab_tools.async_get_repo_size", return_value=10.0),
            patch("src.services.agents.internal_tools.gitlab_tools.uuid.uuid4") as mock_uuid,
        ):
            mock_uuid.return_value.hex = "abc123456789"
            mock_run.return_value = {"success": True}

            result = await internal_gitlab_clone_repo(repo_url="https://gitlab.com/user/repo.git", depth=0)
            assert result["success"] is True

            clone_cmd = mock_run.call_args_list[0].args[0]
            assert "--depth" not in clone_cmd


class TestInternalGitlabComments:
    """Tests for GitLab comment tools."""

    @pytest.mark.asyncio
    async def test_post_mr_comment(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 1,
                "body": "Test comment",
                "author": {"username": "testuser"},
                "created_at": "2024-01-01T00:00:00Z",
            }

            result = await internal_gitlab_post_mr_comment(
                project_id="123", merge_request_iid=1, body="Test comment", runtime_context=mock_runtime_context
            )

            assert result["success"] is True
            assert result["comment"]["body"] == "Test comment"

    @pytest.mark.asyncio
    async def test_post_issue_comment(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 1,
                "body": "Issue comment",
                "author": {"username": "testuser"},
                "created_at": "2024-01-01T00:00:00Z",
            }

            result = await internal_gitlab_post_issue_comment(
                project_id="123", issue_iid=1, body="Issue comment", runtime_context=mock_runtime_context
            )

            assert result["success"] is True
            assert result["comment"]["body"] == "Issue comment"


class TestInternalGitlabMRManagement:
    """Tests for GitLab MR management tools."""

    @pytest.mark.asyncio
    async def test_merge_mr(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 1,
                "iid": 1,
                "title": "Test MR",
                "state": "merged",
                "merged_at": "2024-01-01T00:00:00Z",
                "merged_by": {"username": "merger"},
                "web_url": "https://gitlab.com/user/project/-/merge_requests/1",
            }

            result = await internal_gitlab_merge_mr(
                project_id="123", merge_request_iid=1, runtime_context=mock_runtime_context
            )

            assert result["success"] is True
            assert result["merge_request"]["state"] == "merged"

    @pytest.mark.asyncio
    async def test_close_mr(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 1,
                "iid": 1,
                "title": "Test MR",
                "state": "closed",
                "web_url": "https://gitlab.com/user/project/-/merge_requests/1",
            }

            result = await internal_gitlab_close_mr(
                project_id="123", merge_request_iid=1, runtime_context=mock_runtime_context
            )

            assert result["success"] is True
            assert result["merge_request"]["state"] == "closed"

    @pytest.mark.asyncio
    async def test_approve_mr(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {"success": True}

            result = await internal_gitlab_approve_mr(
                project_id="123", merge_request_iid=1, runtime_context=mock_runtime_context
            )

            assert result["success"] is True


class TestInternalGitlabIssueManagement:
    """Tests for GitLab issue management tools."""

    @pytest.mark.asyncio
    async def test_get_issue(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 1,
                "iid": 1,
                "title": "Bug Issue",
                "description": "Description",
                "state": "opened",
                "labels": ["bug"],
                "assignees": [{"username": "dev"}],
                "author": {"username": "reporter"},
                "web_url": "https://gitlab.com/user/project/-/issues/1",
            }

            result = await internal_gitlab_get_issue(
                project_id="123", issue_iid=1, runtime_context=mock_runtime_context
            )

            assert result["success"] is True
            assert result["issue"]["title"] == "Bug Issue"
            assert result["issue"]["labels"] == ["bug"]

    @pytest.mark.asyncio
    async def test_update_issue(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 1,
                "iid": 1,
                "title": "Updated Title",
                "state": "opened",
                "labels": ["bug", "priority"],
                "assignees": [{"username": "dev"}],
                "web_url": "https://gitlab.com/user/project/-/issues/1",
            }

            result = await internal_gitlab_update_issue(
                project_id="123",
                issue_iid=1,
                title="Updated Title",
                labels="bug,priority",
                runtime_context=mock_runtime_context,
            )

            assert result["success"] is True
            assert result["issue"]["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_issue_no_fields(self):
        mock_runtime_context = MagicMock()

        with patch(
            "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
        ) as mock_creds:
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}

            result = await internal_gitlab_update_issue(
                project_id="123", issue_iid=1, runtime_context=mock_runtime_context
            )

            assert result["success"] is False
            assert "No fields to update" in result["error"]


class TestInternalGitlabGetMRDiff:
    """Tests for internal_gitlab_get_mr_diff function."""

    @pytest.mark.asyncio
    async def test_gets_mr_diff(self):
        mock_runtime_context = MagicMock()

        with (
            patch(
                "src.services.agents.internal_tools.gitlab_tools._get_gitlab_credentials", new_callable=AsyncMock
            ) as mock_creds,
            patch(
                "src.services.agents.internal_tools.gitlab_tools._make_gitlab_request", new_callable=AsyncMock
            ) as mock_request,
        ):
            mock_creds.return_value = {"access_token": "token", "base_url": "https://gitlab.com"}
            mock_request.return_value = {
                "id": 1,
                "iid": 1,
                "title": "Test MR",
                "changes": [
                    {
                        "old_path": "file.py",
                        "new_path": "file.py",
                        "new_file": False,
                        "renamed_file": False,
                        "deleted_file": False,
                        "diff": "@@ -1,3 +1,4 @@\n+# New line\n",
                    },
                ],
            }

            result = await internal_gitlab_get_mr_diff(
                project_id="123", merge_request_iid=1, runtime_context=mock_runtime_context
            )

            assert result["success"] is True
            assert result["changes_count"] == 1
            assert result["changes"][0]["old_path"] == "file.py"


class TestGitHelpers:
    """Tests for git helper functions."""

    def test_run_git_command_success(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")

            result = _run_git_command(["git", "status"])

            assert result["success"] is True
            assert result["output"] == "output"

    def test_run_git_command_failure(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error message")

            result = _run_git_command(["git", "clone", "invalid"])

            assert result["success"] is False
            assert "error message" in result["error"]

    def test_run_git_command_timeout(self):
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["git"], timeout=300)

            result = _run_git_command(["git", "clone", "repo"], timeout=300)

            assert result["success"] is False
            assert "timed out" in result["error"].lower()

    async def test_get_repo_size(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("a" * 1024)  # 1KB file

            size = await async_get_repo_size(tmpdir)

            assert size > 0
            assert size < 1  # Should be less than 1MB
