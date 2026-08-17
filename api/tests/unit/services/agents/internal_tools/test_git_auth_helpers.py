"""Unit tests for GitHub and GitLab URL authentication helpers."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services.agents.internal_tools.github_auth_helper import (
    inject_token_into_url as github_inject,
)
from src.services.agents.internal_tools.github_auth_helper import (
    prepare_authenticated_git_url,
)
from src.services.agents.internal_tools.gitlab_auth_helper import (
    inject_token_into_url as gitlab_inject,
)
from src.services.agents.internal_tools.gitlab_auth_helper import (
    prepare_authenticated_gitlab_url,
)

# ---------------------------------------------------------------------------
# github inject_token_into_url
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGitHubInjectTokenIntoUrl:
    def test_injects_token_before_host(self):
        url = "https://github.com/user/repo.git"
        result = github_inject(url, "ghp_mytoken")
        # "x-access-token:" username prefix is required so git treats the token as a
        # password (not just a username), avoiding an interactive password prompt in
        # non-interactive environments. Works for both PATs and GitHub App tokens.
        assert result == "https://x-access-token:ghp_mytoken@github.com/user/repo.git"

    def test_preserves_path(self):
        url = "https://github.com/org/repo/tree/main"
        result = github_inject(url, "tok")
        assert "org/repo/tree/main" in result

    def test_non_https_returned_unchanged(self):
        url = "git@github.com:user/repo.git"
        result = github_inject(url, "tok")
        assert result == url

    def test_ssh_scheme_returned_unchanged(self):
        url = "ssh://git@github.com/user/repo.git"
        result = github_inject(url, "tok")
        assert result == url

    def test_empty_token_returns_url_unchanged(self):
        url = "https://github.com/user/repo.git"
        result = github_inject(url, "")
        assert result == url

    def test_none_token_returns_url_unchanged(self):
        url = "https://github.com/user/repo.git"
        result = github_inject(url, None)
        assert result == url

    def test_token_already_present_returns_unchanged(self):
        url = "https://existing_tok@github.com/user/repo.git"
        result = github_inject(url, "new_tok")
        assert result == url

    def test_url_starts_with_https(self):
        result = github_inject("https://github.com/u/r.git", "tok")
        assert result.startswith("https://")

    def test_token_placed_in_netloc(self):
        result = github_inject("https://github.com/u/r.git", "ABC123")
        assert "ABC123@github.com" in result

    def test_url_without_dotgit_suffix(self):
        url = "https://github.com/user/repo"
        result = github_inject(url, "tok")
        assert result == "https://x-access-token:tok@github.com/user/repo"


# ---------------------------------------------------------------------------
# gitlab inject_token_into_url  (uses oauth2:TOKEN@ format)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGitLabInjectTokenIntoUrl:
    def test_uses_oauth2_prefix(self):
        url = "https://gitlab.com/user/repo.git"
        result = gitlab_inject(url, "glpat-mytoken")
        assert result == "https://oauth2:glpat-mytoken@gitlab.com/user/repo.git"

    def test_non_https_returned_unchanged(self):
        url = "git@gitlab.com:user/repo.git"
        result = gitlab_inject(url, "tok")
        assert result == url

    def test_empty_token_returns_url_unchanged(self):
        url = "https://gitlab.com/user/repo.git"
        result = gitlab_inject(url, "")
        assert result == url

    def test_token_already_present_returns_unchanged(self):
        url = "https://oauth2:existing@gitlab.com/user/repo.git"
        result = gitlab_inject(url, "new_tok")
        assert result == url

    def test_preserves_path(self):
        url = "https://gitlab.example.com/group/project.git"
        result = gitlab_inject(url, "tok")
        assert "group/project.git" in result

    def test_format_is_oauth2_colon_token_at_host(self):
        result = gitlab_inject("https://gitlab.com/u/r.git", "MYTOKEN")
        assert "oauth2:MYTOKEN@" in result

    def test_self_hosted_gitlab_url(self):
        url = "https://git.mycompany.com/team/project.git"
        result = gitlab_inject(url, "tok")
        assert "oauth2:tok@git.mycompany.com" in result


# ---------------------------------------------------------------------------
# prepare_authenticated_git_url  (GitHub)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrepareAuthenticatedGitUrl:
    @pytest.mark.asyncio
    async def test_returns_url_and_false_without_context(self):
        url = "https://github.com/user/repo.git"
        result_url, used_token = await prepare_authenticated_git_url(url, runtime_context=None)
        assert result_url == url
        assert used_token is False

    @pytest.mark.asyncio
    async def test_converts_ssh_to_https(self):
        ssh_url = "git@github.com:user/repo.git"
        with patch(
            "src.services.agents.internal_tools.github_auth_helper.get_github_token_from_context",
            new=AsyncMock(return_value=None),
        ):
            result_url, used_token = await prepare_authenticated_git_url(ssh_url, runtime_context=None)
        assert result_url.startswith("https://")
        assert "github.com" in result_url
        assert used_token is False

    @pytest.mark.asyncio
    async def test_injects_token_when_available(self):
        url = "https://github.com/user/repo.git"
        with patch(
            "src.services.agents.internal_tools.github_auth_helper.get_github_token_from_context",
            new=AsyncMock(return_value="ghp_testtoken"),
        ):
            result_url, used_token = await prepare_authenticated_git_url(url, runtime_context=object())
        assert used_token is True
        assert "ghp_testtoken@" in result_url

    @pytest.mark.asyncio
    async def test_no_token_returns_original_url(self):
        url = "https://github.com/user/repo.git"
        with patch(
            "src.services.agents.internal_tools.github_auth_helper.get_github_token_from_context",
            new=AsyncMock(return_value=None),
        ):
            result_url, used_token = await prepare_authenticated_git_url(url, runtime_context=object())
        assert result_url == url
        assert used_token is False


# ---------------------------------------------------------------------------
# prepare_authenticated_gitlab_url
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPrepareAuthenticatedGitLabUrl:
    @pytest.mark.asyncio
    async def test_returns_url_and_false_without_context(self):
        url = "https://gitlab.com/user/repo.git"
        result_url, used_token = await prepare_authenticated_gitlab_url(url, runtime_context=None)
        assert result_url == url
        assert used_token is False

    @pytest.mark.asyncio
    async def test_converts_ssh_to_https(self):
        ssh_url = "git@gitlab.com:user/repo.git"
        with patch(
            "src.services.agents.internal_tools.gitlab_auth_helper.get_gitlab_token_from_context",
            new=AsyncMock(return_value=(None, None)),
        ):
            result_url, used_token = await prepare_authenticated_gitlab_url(ssh_url, runtime_context=None)
        assert result_url.startswith("https://")
        assert used_token is False

    @pytest.mark.asyncio
    async def test_injects_token_when_available(self):
        url = "https://gitlab.com/user/repo.git"
        with patch(
            "src.services.agents.internal_tools.gitlab_auth_helper.get_gitlab_token_from_context",
            new=AsyncMock(return_value=("glpat-abc", "https://gitlab.com")),
        ):
            result_url, used_token = await prepare_authenticated_gitlab_url(url, runtime_context=object())
        assert used_token is True
        assert "oauth2:glpat-abc@" in result_url

    @pytest.mark.asyncio
    async def test_no_token_returns_original_url(self):
        url = "https://gitlab.com/user/repo.git"
        with patch(
            "src.services.agents.internal_tools.gitlab_auth_helper.get_gitlab_token_from_context",
            new=AsyncMock(return_value=(None, None)),
        ):
            result_url, used_token = await prepare_authenticated_gitlab_url(url, runtime_context=object())
        assert result_url == url
        assert used_token is False
