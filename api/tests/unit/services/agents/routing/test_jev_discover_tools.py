"""
Unit tests for jev_discover_tools (Task 5.3).
All TypeSafe API calls are mocked — no real HTTP requests.
"""

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.modules.setdefault("httpx", MagicMock())

from src.services.agents.tool_registrations.tool_discovery_registry import jev_discover_tools


def _make_tools(*names):
    return [{"name": n, "description": f"Description of {n}"} for n in names]


def _make_client(answers: dict) -> MagicMock:
    client = MagicMock()
    client.evaluate = AsyncMock(return_value={"answers": answers})
    return client


class TestJevDiscoverTools:
    @pytest.mark.asyncio
    async def test_yes_threshold_only_yes_approved(self):
        tools = _make_tools("slack_send", "web_search", "github_create")
        answers = {
            "tool_slack_send": {"answer": "yes"},
            "tool_web_search": {"answer": "no"},
            "tool_github_create": {"answer": "unclear"},
        }
        client = _make_client(answers)
        result = await jev_discover_tools("send a slack message", tools, client, threshold="yes")
        names = [t["name"] for t in result]
        assert "slack_send" in names
        assert "web_search" not in names
        assert "github_create" not in names

    @pytest.mark.asyncio
    async def test_unclear_threshold_includes_yes_and_unclear(self):
        tools = _make_tools("slack_send", "web_search", "github_create")
        answers = {
            "tool_slack_send": {"answer": "yes"},
            "tool_web_search": {"answer": "no"},
            "tool_github_create": {"answer": "unclear"},
        }
        client = _make_client(answers)
        result = await jev_discover_tools("slack and github", tools, client, threshold="unclear")
        names = [t["name"] for t in result]
        assert "slack_send" in names
        assert "github_create" in names
        assert "web_search" not in names

    @pytest.mark.asyncio
    async def test_unanswered_tool_included_permissive(self):
        tools = _make_tools("my_tool")
        # JEV returns no answer for this tool
        client = _make_client({})
        result = await jev_discover_tools("do something", tools, client, threshold="yes")
        names = [t["name"] for t in result]
        assert "my_tool" in names

    @pytest.mark.asyncio
    async def test_api_error_returns_all_candidates(self):
        import httpx

        tools = _make_tools("slack_send", "web_search")
        client = MagicMock()
        client.evaluate = AsyncMock(side_effect=httpx.RequestError("connection refused"))
        result = await jev_discover_tools("test query", tools, client)
        assert len(result) == len(tools)

    @pytest.mark.asyncio
    async def test_api_error_field_returns_all_candidates(self):
        tools = _make_tools("slack_send", "web_search")
        client = MagicMock()
        client.evaluate = AsyncMock(return_value={"error": "invalid api key"})
        result = await jev_discover_tools("test query", tools, client)
        assert len(result) == len(tools)

    @pytest.mark.asyncio
    async def test_empty_candidates_returns_empty(self):
        client = MagicMock()
        result = await jev_discover_tools("test", [], client)
        assert result == []

    @pytest.mark.asyncio
    async def test_caps_at_50_tools(self):
        tools = _make_tools(*[f"tool_{i}" for i in range(60)])
        # All answers are "yes"
        answers = {f"tool_tool_{i}": {"answer": "yes"} for i in range(50)}
        client = _make_client(answers)
        result = await jev_discover_tools("query", tools, client)
        # Only up to 50 were asked; those 50 return yes, overflow 10 are included too
        assert len(result) <= 60
        assert len(result) >= 50  # all asked + overflow pass through
