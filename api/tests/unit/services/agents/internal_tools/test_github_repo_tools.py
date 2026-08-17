from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.internal_tools.github_repo_tools import (
    _make_github_request,
    internal_github_get_file_content,
)


class TestMakeGithubRequest:
    """Tests for _make_github_request helper function."""

    @pytest.mark.asyncio
    async def test_follows_redirects(self):
        """api.github.com is a fixed, trusted host - redirects (e.g. for normalized
        contents paths) must be followed rather than returned as an empty 3xx body."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client_instance = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client_instance
            mock_client_instance.request.return_value = mock_response

            result = await _make_github_request("GET", "/repos/owner/repo", "token")

            assert result == {"id": 1}
            mock_client_cls.assert_called_once_with(follow_redirects=True)


class TestInternalGithubGetFileContent:
    """Tests for internal_github_get_file_content."""

    @pytest.mark.asyncio
    async def test_strips_trailing_slash_from_path(self):
        """path='/' (or any trailing-slash path) must not produce a malformed
        '/contents//' endpoint - it must be normalized like internal_github_list_repo_contents."""
        with (
            patch(
                "src.services.agents.internal_tools.github_repo_tools._get_github_token",
                return_value="token",
            ),
            patch(
                "src.services.agents.internal_tools.github_repo_tools._make_github_request",
                new_callable=AsyncMock,
            ) as mock_request,
        ):
            mock_request.return_value = {
                "name": "repo",
                "path": "",
                "sha": "abc",
                "size": 0,
                "html_url": "https://github.com/owner/repo",
                "download_url": None,
                "content": "",
                "encoding": "base64",
            }

            await internal_github_get_file_content(owner="owner", repo="repo", path="/")

            called_endpoint = mock_request.call_args.args[1]
            assert called_endpoint == "/repos/owner/repo/contents"
            assert not called_endpoint.endswith("//")
