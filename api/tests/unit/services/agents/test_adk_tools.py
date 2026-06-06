import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock external dependencies before importing the module under test
sys.modules["github"] = MagicMock()
sys.modules["googleapiclient"] = MagicMock()
sys.modules["googleapiclient.discovery"] = MagicMock()
sys.modules["googleapiclient.errors"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.credentials"] = MagicMock()
# Ensure serpapi mock has GoogleSearch
mock_serpapi = MagicMock()
sys.modules["serpapi"] = mock_serpapi
sys.modules["bs4"] = MagicMock()

# Import the module we want to patch
from src.services.agents.adk_tools import (
    ADKToolRegistry,
    github_composite,
    github_create_issue,
    github_get_repo,
    github_list_issues,
    github_list_my_repos,
    github_search_repos,
    web_crawl,
    web_search,
    youtube_get_video_info,
    youtube_search,
)


class TestADKToolRegistry:
    def test_register_default_tools(self):
        registry = ADKToolRegistry()
        assert len(registry.tools) > 0
        assert "internal_read_file" in registry.tools
        assert "internal_fetch_repository_files" in registry.tools

    # @pytest.mark.asyncio
    # async def test_wrapper_functions(self):
    #     # Patch the function on the imported module
    #     with patch.object(tutorial_gen, "internal_fetch_repository_files", new_callable=AsyncMock) as mock_impl:
    #         mock_impl.return_value = {"success": True}
    #
    #         # Create registry inside the patch context so it imports the patched function
    #         registry = ADKToolRegistry()
    #         wrapper = registry.tools["internal_fetch_repository_files"]["function"]
    #
    #         config = {"_runtime_context": "ctx"}
    #         await wrapper(config=config, repo_path="/tmp")
    #
    #         mock_impl.assert_called_once()
    #         call_kwargs = mock_impl.call_args[1]
    #         assert call_kwargs["runtime_context"] == "ctx"
    #         assert call_kwargs["repo_path"] == "/tmp"


class TestWebTools:
    @pytest.mark.asyncio
    async def test_web_search(self):
        # Patch where it is imported from
        with patch("serpapi.GoogleSearch") as MockSearch:
            mock_instance = MockSearch.return_value
            mock_instance.get_dict.return_value = {
                "organic_results": [{"title": "T1", "link": "url1", "snippet": "s1"}]
            }

            result = await web_search("query", config={"SERPAPI_KEY": "key"})

            assert len(result["results"]) == 1
            assert result["results"][0]["title"] == "T1"

    @pytest.mark.asyncio
    async def test_web_crawl(self):
        with (
            patch("httpx.AsyncClient") as MockClient,
            patch("bs4.BeautifulSoup") as MockBS,
        ):
            mock_client_instance = MockClient.return_value
            mock_client_instance.__aenter__.return_value.get.return_value.text = "<html></html>"

            mock_soup = MockBS.return_value
            mock_soup.get_text.return_value = "content"
            mock_soup.title.string = "Title"

            result = await web_crawl("http://test.com")

            assert result["title"] == "Title"
            assert result["content"] == "content"


class TestGitHubTools:
    @pytest.fixture
    def mock_github(self):
        with patch("github.Github") as MockGithub:
            yield MockGithub

    @pytest.mark.asyncio
    async def test_github_search_repos(self, mock_github):
        mock_instance = mock_github.return_value
        mock_repo = MagicMock()
        mock_repo.full_name = "owner/repo"
        mock_repo.stargazers_count = 10
        mock_instance.search_repositories.return_value = [mock_repo]

        result = await github_search_repos("query", config={"GITHUB_OAUTH_TOKEN": "token"})

        assert len(result["repositories"]) == 1
        assert result["repositories"][0]["name"] == "owner/repo"

    @pytest.mark.asyncio
    async def test_github_get_repo(self, mock_github):
        mock_instance = mock_github.return_value
        mock_repo = MagicMock()
        mock_repo.full_name = "owner/repo"
        mock_instance.get_repo.return_value = mock_repo

        result = await github_get_repo("owner", "repo", config={"GITHUB_OAUTH_TOKEN": "token"})

        assert result["name"] == "owner/repo"

    @pytest.mark.asyncio
    async def test_github_list_issues(self, mock_github):
        mock_instance = mock_github.return_value
        mock_issue = MagicMock()
        mock_issue.title = "Issue 1"
        mock_instance.get_repo.return_value.get_issues.return_value = [mock_issue]

        result = await github_list_issues("owner", "repo", config={"GITHUB_OAUTH_TOKEN": "token"})

        assert len(result["issues"]) == 1
        assert result["issues"][0]["title"] == "Issue 1"

    @pytest.mark.asyncio
    async def test_github_create_issue(self, mock_github):
        mock_instance = mock_github.return_value
        mock_issue = MagicMock()
        mock_issue.number = 1
        mock_issue.html_url = "url"
        mock_instance.get_repo.return_value.create_issue.return_value = mock_issue

        result = await github_create_issue("owner", "repo", "title", config={"GITHUB_OAUTH_TOKEN": "token"})

        assert result["issue"]["number"] == 1

    @pytest.mark.asyncio
    async def test_github_list_my_repos(self, mock_github):
        mock_instance = mock_github.return_value
        mock_repo = MagicMock()
        mock_repo.full_name = "my/repo"
        mock_instance.get_user.return_value.get_repos.return_value = [mock_repo]

        result = await github_list_my_repos(config={"GITHUB_OAUTH_TOKEN": "token"})

        assert len(result["repositories"]) == 1
        assert result["repositories"][0]["name"] == "my/repo"

    @pytest.mark.asyncio
    async def test_github_composite(self):
        with patch("src.services.agents.adk_tools.github_search_repos", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"ok": True}

            await github_composite("search_repos", query="q")
            mock_search.assert_called_once()


class TestGoogleTools:
    @pytest.fixture
    def mock_build(self):
        with patch("googleapiclient.discovery.build") as mock:
            yield mock

    @pytest.fixture
    def mock_creds(self):
        with patch("google.oauth2.credentials.Credentials") as mock:
            yield mock

    # Gmail tests removed - functions moved to internal_tools/gmail_tools.py with internal_gmail_* prefix

    @pytest.mark.asyncio
    async def test_youtube_search(self, mock_build):
        service = mock_build.return_value
        service.search.return_value.list.return_value.execute.return_value = {
            "items": [
                {"id": {"videoId": "vid1"}, "snippet": {"title": "Title", "description": "Desc", "channelTitle": "Ch"}}
            ]
        }

        result = await youtube_search("query", config={"YOUTUBE_API_KEY": "key"})

        assert len(result["videos"]) == 1
        assert result["videos"][0]["title"] == "Title"

    @pytest.mark.asyncio
    async def test_youtube_get_video_info(self, mock_build):
        service = mock_build.return_value
        service.videos.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "snippet": {"title": "Title", "description": "Desc", "channelTitle": "Ch", "publishedAt": "date"},
                    "statistics": {"viewCount": "100"},
                    "contentDetails": {"duration": "PT1M"},
                }
            ]
        }

        result = await youtube_get_video_info("vid1", config={"YOUTUBE_API_KEY": "key"})

        assert result["title"] == "Title"
        assert result["view_count"] == "100"


class TestADKToolRegistryExecution:
    @pytest.fixture
    def registry(self):
        return ADKToolRegistry()

    @pytest.mark.asyncio
    async def test_execute_tool_tutorial_generator(self):
        with patch(
            "src.services.agents.internal_tools.tutorial_generator.internal_fetch_repository_files",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = {"files": []}

            # Create registry inside patch context
            registry = ADKToolRegistry()

            result = await registry.execute_tool(
                "internal_fetch_repository_files", {"repo_path": "/tmp/repo"}, config={"_runtime_context": MagicMock()}
            )

            assert result == {"files": []}
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_s3_upload(self):
        with patch(
            "src.services.agents.internal_tools.storage_tools.internal_s3_upload_file", new_callable=AsyncMock
        ) as mock_upload:
            mock_upload.return_value = {"url": "s3://url"}

            # Create registry inside patch context
            registry = ADKToolRegistry()

            result = await registry.execute_tool(
                "internal_s3_upload_file",
                {"file_path": "file.txt", "s3_key": "key"},
                config={},
            )

            assert result == {"url": "s3://url"}
            mock_upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_git_clone(self):
        # Patch the name in the module where it is imported from (the registry wrapper)
        with patch(
            "src.services.agents.internal_tools.git_repo_tools.internal_git_clone_repo", new_callable=AsyncMock
        ) as mock_clone:
            mock_clone.return_value = {"path": "/tmp/repo"}

            # Create registry inside patch context
            registry = ADKToolRegistry()

            result = await registry.execute_tool(
                "internal_git_clone_repo", {"repo_url": "http://git"}, config={"_runtime_context": MagicMock()}
            )

            assert result == {"path": "/tmp/repo"}
            mock_clone.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_database_query(self):
        # Patch the name in the package where it is imported from
        with patch("src.services.agents.internal_tools.internal_query_database", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [{"id": 1}]

            # Create registry inside patch context
            registry = ADKToolRegistry()

            mock_runtime_context = MagicMock()
            mock_runtime_context.allowed_database_connections = ["conn1"]

            result = await registry.execute_tool(
                "internal_query_database",
                {"connection_id": "conn1", "query": "SELECT *"},
                config={"_runtime_context": mock_runtime_context},
            )

            assert result == [{"id": 1}]
            mock_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_agent_custom_tools(self, registry):
        mock_db = AsyncMock()

        # Mock AgentTool
        mock_agent_tool = MagicMock()
        mock_agent_tool.custom_tool_id = "tool1"
        mock_agent_tool.operation_id = "op1"
        mock_agent_tool.tool_name = "custom_tool_op1"
        mock_agent_tool.config = {}
        mock_agent_tool.enabled = True

        # Mock CustomTool
        mock_custom_tool = MagicMock()
        mock_custom_tool.id = "tool1"
        mock_custom_tool.name = "Custom Tool"
        mock_custom_tool.openapi_schema = {"openapi": "3.0.0"}
        mock_custom_tool.server_url = "http://api.test"
        mock_custom_tool.auth_type = "none"
        mock_custom_tool.auth_config = {}
        mock_custom_tool.enabled = True

        # Setup mock db.execute with side_effect for different queries
        call_count = [0]

        def execute_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            call_count[0] += 1
            # First call: query AgentTool
            if call_count[0] == 1:
                mock_result.scalars.return_value.all.return_value = [mock_agent_tool]
            # Second call: batch query CustomTool by IDs
            else:
                mock_result.scalars.return_value.all.return_value = [mock_custom_tool]
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        with patch("src.services.custom_tools.ToolExecutor") as MockExecutor:
            mock_exec = MockExecutor.return_value
            # execute is awaited, so it must be AsyncMock
            mock_exec.execute = AsyncMock(return_value="result")

            # Need to mock OpenAPIParser too since it's used
            with patch("src.services.custom_tools.OpenAPIParser") as MockParser:
                mock_parser = MockParser.return_value
                mock_parser.get_tool_definition.return_value = {"description": "desc"}

                await registry.load_agent_custom_tools("00000000-0000-0000-0000-000000000000", mock_db)

                assert "custom_tool_op1" in registry.tools

                # Execute it
                result = await registry.execute_tool("custom_tool_op1", {})
                assert result == "result"
                mock_exec.execute.assert_called()

    @pytest.mark.asyncio
    async def test_load_agent_mcp_tools(self):
        mock_db = AsyncMock()
        mock_server = MagicMock()
        mock_server.name = "server1"
        mock_server.config = {"url": "http://mcp"}

        mock_assoc = MagicMock()
        mock_assoc.mcp_server = mock_server
        mock_assoc.mcp_config = {"enabled_tools": ["mcp_tool"]}

        # Setup mock db.execute result - code uses result.scalars().all()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_assoc]
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Patch mcp_client_manager in the module where it is defined
        with patch("src.services.mcp.mcp_client_manager") as mock_manager:
            mock_client = AsyncMock(name="mock_client")
            # get_agent_client is awaited, so it must be async or return a coroutine
            mock_manager.get_agent_client = AsyncMock(name="get_agent_client", return_value=mock_client)

            mock_tool = MagicMock()
            mock_tool.name = "mcp_tool"
            mock_tool.description = "desc"
            mock_tool.inputSchema = {"type": "object"}

            mock_client.discover_tools.return_value = [mock_tool]

            # execute_tool is awaited, so it must be async
            mock_result = MagicMock()
            mock_content = MagicMock()
            mock_content.type = "text"
            mock_content.text = "result"
            mock_result.content = [mock_content]
            mock_result.isError = False

            # Important: adk_tools calls execute_tool on the MCPClient wrapper, not call_tool directly
            mock_client.execute_tool = AsyncMock(name="execute_tool", return_value=mock_result)

            # Create registry inside patch context
            registry = ADKToolRegistry()

            await registry.load_agent_mcp_tools("00000000-0000-0000-0000-000000000000", mock_db)

            assert "mcp_tool" in registry.tools

            # Execute it
            result = await registry.execute_tool("mcp_tool", {})

            # The wrapper logic tries to parse as JSON, if fails returns {"result": text}
            # "result" is not valid JSON

            assert result == {"result": "result"}
            mock_client.execute_tool.assert_called()

    def test_list_tools(self, registry):
        tools = registry.list_tools()
        assert len(tools) > 0
        assert any(t["name"] == "internal_read_file" for t in tools)

    def test_get_tool(self, registry):
        tool = registry.get_tool("internal_read_file")
        assert tool is not None
        assert tool["name"] == "internal_read_file"

        assert registry.get_tool("non_existent") is None
