"""Unit tests for mcp_tool_triage.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agents.mcp_tool_triage import (
    MAX_MCP_TOOL_QUESTIONS,
    filter_mcp_tools,
)


def _make_registry(tool_names: list[str], description: str = "Does something useful") -> MagicMock:
    registry = MagicMock()
    registry.get_tool = lambda name: {"name": name, "description": description}
    return registry


def _make_agent(description: str = "General purpose agent") -> MagicMock:
    agent = MagicMock()
    agent.description = description
    return agent


def _make_client(answers: dict) -> MagicMock:
    client = MagicMock()
    client.evaluate = AsyncMock(return_value={"answers": answers, "model": "jev-latest"})
    return client


@pytest.mark.asyncio
async def test_none_client_returns_all():
    names = ["tool_a", "tool_b"]
    result = await filter_mcp_tools(
        client=None,
        tool_names=names,
        registry=_make_registry(names),
        query="do something",
        agent=_make_agent(),
    )
    assert result == names


@pytest.mark.asyncio
async def test_empty_tool_names_returns_empty():
    result = await filter_mcp_tools(
        client=MagicMock(),
        tool_names=[],
        registry=_make_registry([]),
        query="do something",
        agent=_make_agent(),
    )
    assert result == []


@pytest.mark.asyncio
async def test_timeout_fails_open():
    names = ["tool_a", "tool_b"]
    client = MagicMock()
    client.evaluate = AsyncMock(side_effect=asyncio.TimeoutError)

    result = await filter_mcp_tools(
        client=client,
        tool_names=names,
        registry=_make_registry(names),
        query="do something",
        agent=_make_agent(),
        timeout=0.001,
    )
    assert result == names


@pytest.mark.asyncio
async def test_api_error_fails_open():
    names = ["tool_a", "tool_b"]
    client = MagicMock()
    client.evaluate = AsyncMock(return_value={"error": "upstream failure", "answers": {}})

    result = await filter_mcp_tools(
        client=client,
        tool_names=names,
        registry=_make_registry(names),
        query="do something",
        agent=_make_agent(),
    )
    assert result == names


@pytest.mark.asyncio
async def test_strict_threshold_filters_non_yes():
    names = ["tool_a", "tool_b", "tool_c"]
    answers = {
        "tool_tool_a": {"answer": "yes"},
        "tool_tool_b": {"answer": "no"},
        "tool_tool_c": {"answer": "unclear"},
    }
    client = _make_client(answers)

    result = await filter_mcp_tools(
        client=client,
        tool_names=names,
        registry=_make_registry(names),
        query="do something",
        agent=_make_agent(),
        threshold="yes",
    )
    # Only tool_a passes strict threshold
    assert result == ["tool_a"]


@pytest.mark.asyncio
async def test_permissive_threshold_includes_unclear():
    names = ["tool_a", "tool_b", "tool_c"]
    answers = {
        "tool_tool_a": {"answer": "yes"},
        "tool_tool_b": {"answer": "no"},
        "tool_tool_c": {"answer": "unclear"},
    }
    client = _make_client(answers)

    result = await filter_mcp_tools(
        client=client,
        tool_names=names,
        registry=_make_registry(names),
        query="do something",
        agent=_make_agent(),
        threshold="unclear",
    )
    # tool_a and tool_c pass permissive threshold
    assert set(result) == {"tool_a", "tool_c"}


@pytest.mark.asyncio
async def test_tools_beyond_cap_always_pass():
    # Create more tools than the cap
    names = [f"tool_{i}" for i in range(MAX_MCP_TOOL_QUESTIONS + 5)]
    # Answer "no" for all capped tools
    answers = {f"tool_tool_{i}": {"answer": "no"} for i in range(MAX_MCP_TOOL_QUESTIONS)}
    client = _make_client(answers)

    result = await filter_mcp_tools(
        client=client,
        tool_names=names,
        registry=_make_registry(names),
        query="do something",
        agent=_make_agent(),
        threshold="yes",
    )
    # The 5 beyond-cap tools always pass through even though all capped ones said "no"
    beyond_cap = names[MAX_MCP_TOOL_QUESTIONS:]
    for name in beyond_cap:
        assert name in result


@pytest.mark.asyncio
async def test_missing_answer_treated_as_no():
    names = ["tool_a", "tool_b"]
    # tool_b answer is absent
    answers = {"tool_tool_a": {"answer": "yes"}}
    client = _make_client(answers)

    result = await filter_mcp_tools(
        client=client,
        tool_names=names,
        registry=_make_registry(names),
        query="do something",
        agent=_make_agent(),
        threshold="yes",
    )
    assert result == ["tool_a"]
