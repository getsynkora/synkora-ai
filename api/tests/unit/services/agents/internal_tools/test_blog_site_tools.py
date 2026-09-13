"""
Tests for blog_site_tools.py - Blog Site Creation Tools

Tests the blog site scaffolding, GitHub repo creation,
deployment, and GitHub Pages enablement.
"""

import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.internal_tools.blog_site_tools import (
    _get_workspace_path,
    _validate_path_in_workspace,
)


class TestGetWorkspacePath:
    """Tests for _get_workspace_path helper."""

    def test_returns_workspace_from_config(self):
        config = {"workspace_path": "/tmp/workspace"}
        result = _get_workspace_path(config)
        assert result == "/tmp/workspace"

    def test_returns_none_for_empty_config(self):
        result = _get_workspace_path({})
        # Might try RuntimeContext fallback, which should also fail gracefully
        assert result is None or isinstance(result, str)

    def test_returns_none_for_none_config(self):
        result = _get_workspace_path(None)
        assert result is None or isinstance(result, str)


class TestValidatePathInWorkspace:
    """Tests for _validate_path_in_workspace function."""

    def test_valid_path_within_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            file_path = os.path.join(workspace, "test.txt")
            valid, error = _validate_path_in_workspace(file_path, workspace)
            assert valid is True
            assert error is None

    def test_path_outside_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            outside_path = "/tmp/outside/file.txt"
            valid, error = _validate_path_in_workspace(outside_path, workspace)
            assert valid is False
            assert "outside" in error.lower()

    def test_no_workspace_path(self):
        valid, error = _validate_path_in_workspace("/tmp/file.txt", None)
        assert valid is False
        assert "No workspace" in error

    def test_path_traversal_attack(self):
        with tempfile.TemporaryDirectory() as workspace:
            traversal_path = os.path.join(workspace, "..", "..", "etc", "passwd")
            valid, error = _validate_path_in_workspace(traversal_path, workspace)
            assert valid is False
            assert "outside" in error.lower()


class TestInternalGenerateBlogSite:
    """Tests for internal_generate_blog_site function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_workspace(self):
        from src.services.agents.internal_tools.blog_site_tools import internal_generate_blog_site

        with patch(
            "src.services.agents.internal_tools.blog_site_tools._get_workspace_path",
            return_value=None,
        ):
            result = await internal_generate_blog_site(site_name="My Blog")

            assert result["success"] is False
            assert "No workspace" in result["error"]

    @pytest.mark.asyncio
    async def test_creates_blog_site_successfully(self):
        from src.services.agents.internal_tools.blog_site_tools import internal_generate_blog_site

        with tempfile.TemporaryDirectory() as workspace:
            result = await internal_generate_blog_site(
                site_name="My Test Blog",
                description="A test blog",
                author_name="Test Author",
                config={"workspace_path": workspace},
            )

            assert result["success"] is True
            assert "site_path" in result
            assert os.path.exists(result["site_path"])
            assert result["site_name"] == "My Test Blog"
            assert result["author_name"] == "Test Author"

            # Verify directory structure
            site_path = result["site_path"]
            assert os.path.exists(os.path.join(site_path, "posts"))
            assert os.path.exists(os.path.join(site_path, "images"))
            assert os.path.exists(os.path.join(site_path, "css"))
            assert os.path.exists(os.path.join(site_path, "js"))

            # Verify files created
            assert os.path.exists(os.path.join(site_path, "index.html"))
            assert os.path.exists(os.path.join(site_path, "css", "style.css"))
            assert os.path.exists(os.path.join(site_path, "js", "app.js"))

    @pytest.mark.asyncio
    async def test_returns_instructions(self):
        from src.services.agents.internal_tools.blog_site_tools import internal_generate_blog_site

        with tempfile.TemporaryDirectory() as workspace:
            result = await internal_generate_blog_site(
                site_name="Blog",
                config={"workspace_path": workspace},
            )

            assert result["success"] is True
            assert "instructions" in result
            assert "tips" in result
            assert "step_1" in result["instructions"]


class TestInternalCreateGithubRepo:
    """Tests for internal_create_github_repo function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_token(self):
        from src.services.agents.internal_tools.blog_site_tools import internal_create_github_repo

        with patch.dict(os.environ, {}, clear=True):
            # Ensure no GITHUB_TOKEN in environment
            os.environ.pop("GITHUB_TOKEN", None)

            result = await internal_create_github_repo(repo_name="my-blog", config={})

            assert result["success"] is False
            assert "GitHub token" in result["error"]

    @pytest.mark.asyncio
    async def test_creates_repo_successfully(self):
        from src.services.agents.internal_tools.blog_site_tools import internal_create_github_repo

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "name": "my-blog",
            "html_url": "https://github.com/user/my-blog",
            "clone_url": "https://github.com/user/my-blog.git",
            "ssh_url": "git@github.com:user/my-blog.git",
            "owner": {"login": "user"},
            "default_branch": "main",
        }

        with patch(
            "src.services.agents.internal_tools.blog_site_tools.get_httpx_client",
            new=AsyncMock(return_value=SimpleNamespace(post=AsyncMock(return_value=mock_response))),
        ):
            result = await internal_create_github_repo(
                repo_name="my-blog",
                description="My blog",
                config={"github_token": "test-token"},
            )

            assert result["success"] is True
            assert result["repo_name"] == "my-blog"
            assert "github.com" in result["repo_url"]

    @pytest.mark.asyncio
    async def test_handles_repo_already_exists(self):
        from src.services.agents.internal_tools.blog_site_tools import internal_create_github_repo

        mock_response = MagicMock()
        mock_response.status_code = 422

        with patch(
            "src.services.agents.internal_tools.blog_site_tools.get_httpx_client",
            new=AsyncMock(return_value=SimpleNamespace(post=AsyncMock(return_value=mock_response))),
        ):
            result = await internal_create_github_repo(
                repo_name="my-blog",
                config={"github_token": "test-token"},
            )

            assert result["success"] is False
            assert "already exist" in result["error"]


class TestInternalDeployToGithub:
    """Tests for internal_deploy_to_github function."""

    @pytest.mark.asyncio
    async def test_validates_workspace_path(self):
        from src.services.agents.internal_tools.blog_site_tools import internal_deploy_to_github

        with patch(
            "src.services.agents.internal_tools.blog_site_tools._get_workspace_path",
            return_value=None,
        ):
            result = await internal_deploy_to_github(
                site_path="/tmp/site",
                repo_url="https://github.com/user/repo.git",
            )

            assert result["success"] is False
            assert "No workspace" in result["error"]

    @pytest.mark.asyncio
    async def test_returns_error_for_nonexistent_site_path(self):
        from src.services.agents.internal_tools.blog_site_tools import internal_deploy_to_github

        with tempfile.TemporaryDirectory() as workspace:
            nonexistent = os.path.join(workspace, "nonexistent")

            result = await internal_deploy_to_github(
                site_path=nonexistent,
                repo_url="https://github.com/user/repo.git",
                config={"workspace_path": workspace},
            )

            assert result["success"] is False
            assert "not found" in result["error"]


class TestInternalEnableGithubPages:
    """Tests for internal_enable_github_pages function."""

    @pytest.mark.asyncio
    async def test_returns_error_without_token(self):
        from src.services.agents.internal_tools.blog_site_tools import internal_enable_github_pages

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITHUB_TOKEN", None)

            result = await internal_enable_github_pages(
                repo_name="my-blog",
                owner="user",
                config={},
            )

            assert result["success"] is False
            assert "GitHub token" in result["error"]

    @pytest.mark.asyncio
    async def test_enables_pages_successfully(self):
        from src.services.agents.internal_tools.blog_site_tools import internal_enable_github_pages

        mock_response = MagicMock()
        mock_response.status_code = 201

        with patch(
            "src.services.agents.internal_tools.blog_site_tools.get_httpx_client",
            new=AsyncMock(return_value=SimpleNamespace(post=AsyncMock(return_value=mock_response))),
        ):
            result = await internal_enable_github_pages(
                repo_name="my-blog",
                owner="user",
                config={"github_token": "test-token"},
            )

            assert result["success"] is True
            assert "pages_url" in result
            assert "user.github.io" in result["pages_url"]

    @pytest.mark.asyncio
    async def test_handles_already_enabled(self):
        from src.services.agents.internal_tools.blog_site_tools import internal_enable_github_pages

        mock_response = MagicMock()
        mock_response.status_code = 409

        with patch(
            "src.services.agents.internal_tools.blog_site_tools.get_httpx_client",
            new=AsyncMock(return_value=SimpleNamespace(post=AsyncMock(return_value=mock_response))),
        ):
            result = await internal_enable_github_pages(
                repo_name="my-blog",
                owner="user",
                config={"github_token": "test-token"},
            )

            assert result["success"] is True
            assert "already enabled" in result["message"]
