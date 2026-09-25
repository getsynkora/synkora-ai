"""
Unit tests for ADKToolRegistry.filter_tools (Task 3.2).
"""

import sys
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("httpx", MagicMock())

from src.services.agents.adk_tools import ADKToolRegistry


def _make_registry(*names: str) -> ADKToolRegistry:
    registry = object.__new__(ADKToolRegistry)
    registry.tools = {
        name: {"name": name, "description": f"Tool {name}", "parameters": {}}
        for name in names
    }
    registry._request_owned = False
    return registry


class TestFilterTools:
    def test_returns_only_allowed_tools(self):
        registry = _make_registry("slack_send", "web_search", "github_create_issue")
        filtered = registry.filter_tools(allowed_names={"slack_send", "github_create_issue"})
        assert set(filtered.tools.keys()) == {"slack_send", "github_create_issue"}

    def test_empty_allowed_names_returns_empty_registry(self):
        registry = _make_registry("slack_send", "web_search")
        filtered = registry.filter_tools(allowed_names=set())
        assert filtered.tools == {}

    def test_names_not_in_registry_silently_ignored(self):
        registry = _make_registry("slack_send")
        filtered = registry.filter_tools(allowed_names={"slack_send", "nonexistent_tool"})
        assert set(filtered.tools.keys()) == {"slack_send"}

    def test_always_include_bypasses_filter(self):
        registry = _make_registry("slack_send", "web_search", "mcp_tool_x")
        filtered = registry.filter_tools(
            allowed_names={"slack_send"},
            always_include={"mcp_tool_x"},
        )
        assert "slack_send" in filtered.tools
        assert "mcp_tool_x" in filtered.tools
        assert "web_search" not in filtered.tools

    def test_original_registry_not_mutated(self):
        registry = _make_registry("slack_send", "web_search")
        original_keys = set(registry.tools.keys())
        registry.filter_tools(allowed_names={"slack_send"})
        assert set(registry.tools.keys()) == original_keys

    def test_returns_new_registry_instance(self):
        registry = _make_registry("slack_send", "web_search")
        filtered = registry.filter_tools(allowed_names={"slack_send"})
        assert filtered is not registry

    def test_all_allowed_passes_everything(self):
        registry = _make_registry("a", "b", "c")
        filtered = registry.filter_tools(allowed_names={"a", "b", "c"})
        assert set(filtered.tools.keys()) == {"a", "b", "c"}

    def test_always_include_none_handled(self):
        registry = _make_registry("tool_a", "tool_b")
        filtered = registry.filter_tools(allowed_names={"tool_a"}, always_include=None)
        assert set(filtered.tools.keys()) == {"tool_a"}
