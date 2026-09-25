"""
Unit tests for jev_router.py

All TypeSafe API calls are mocked — no real HTTP requests.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Mock heavy imports so the module can be imported in isolation ──────────
sys.modules.setdefault("httpx", MagicMock())

from src.services.agents.routing.jev_router import (
    JevRoutingError,
    JevRoutingResult,
    _MAX_TOOL_QUESTIONS,
    build_jev_questions,
    parse_jev_answers,
    run_jev_routing,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(id_: str, is_default: bool = False, enabled: bool = True, model_name: str = "sonnet"):
    c = MagicMock()
    c.id = id_
    c.is_default = is_default
    c.enabled = enabled
    c.model_name = model_name
    return c


@pytest.fixture()
def llm_configs():
    return [
        _make_config("haiku-uuid", is_default=False, model_name="haiku"),
        _make_config("sonnet-uuid", is_default=True, model_name="sonnet"),
        _make_config("opus-uuid", is_default=False, model_name="opus"),
    ]


@pytest.fixture()
def tool_list():
    return [
        {"name": "web_search", "description": "Search the web"},
        {"name": "slack_get_messages", "description": "Fetch Slack messages"},
        {"name": "github_create_issue", "description": "Create GitHub issue"},
    ]


@pytest.fixture()
def model_tier_map():
    return {
        "fast": "haiku-uuid",
        "standard": "sonnet-uuid",
        "heavy": "opus-uuid",
    }


@pytest.fixture()
def full_features():
    return {"model_routing": True, "tool_filtering": True}


@pytest.fixture()
def db_agent():
    agent = MagicMock()
    agent.agent_name = "test-agent"
    agent.description = "A test agent for JEV routing"
    return agent


@pytest.fixture()
def typesafe_client():
    client = MagicMock()
    client.evaluate = AsyncMock(
        return_value={
            "answers": {
                "model_tier": {"choice": "standard"},
                "tool_web_search": {"answer": "no"},
                "tool_slack_get_messages": {"answer": "yes"},
                "tool_github_create_issue": {"answer": "yes"},
                "complexity": {"answer": "moderate"},
            }
        }
    )
    return client


# ---------------------------------------------------------------------------
# build_jev_questions
# ---------------------------------------------------------------------------


class TestBuildJevQuestions:
    def test_model_routing_enabled_produces_model_tier_question(self, tool_list, model_tier_map, full_features):
        questions = build_jev_questions(full_features, tool_list, model_tier_map)
        assert "model_tier" in questions
        assert questions["model_tier"]["type"] == "choice"
        assert set(questions["model_tier"]["options"]) == {"fast", "standard", "heavy"}

    def test_model_routing_disabled_no_model_tier_question(self, tool_list, model_tier_map):
        features = {"model_routing": False, "tool_filtering": True}
        questions = build_jev_questions(features, tool_list, model_tier_map)
        assert "model_tier" not in questions

    def test_empty_model_tier_map_no_model_tier_question(self, tool_list, full_features):
        questions = build_jev_questions(full_features, tool_list, {})
        assert "model_tier" not in questions

    def test_tool_filtering_enabled_produces_noul_per_tool(self, tool_list, model_tier_map, full_features):
        questions = build_jev_questions(full_features, tool_list, model_tier_map)
        for tool in tool_list:
            key = f"tool_{tool['name']}"
            assert key in questions
            assert questions[key]["type"] == "noul"

    def test_tool_filtering_disabled_no_tool_questions(self, tool_list, model_tier_map):
        features = {"model_routing": True, "tool_filtering": False}
        questions = build_jev_questions(features, tool_list, model_tier_map)
        tool_keys = [k for k in questions if k.startswith("tool_")]
        assert tool_keys == []

    def test_complexity_always_present(self, tool_list, model_tier_map, full_features):
        questions = build_jev_questions(full_features, tool_list, model_tier_map)
        assert "complexity" in questions
        assert questions["complexity"]["type"] == "score"
        assert "expert" in questions["complexity"]["levels"]

    def test_tool_cap_at_max(self, model_tier_map, full_features):
        big_tool_list = [{"name": f"tool_{i}", "description": f"desc {i}"} for i in range(60)]
        questions = build_jev_questions(full_features, big_tool_list, model_tier_map)
        tool_keys = [k for k in questions if k.startswith("tool_")]
        assert len(tool_keys) == _MAX_TOOL_QUESTIONS

    def test_description_truncated(self, model_tier_map, full_features):
        long_desc = "x" * 500
        tools = [{"name": "mytool", "description": long_desc}]
        questions = build_jev_questions(full_features, tools, model_tier_map)
        q_text = questions["tool_mytool"]["question"]
        assert len(q_text) < 500  # description was truncated


# ---------------------------------------------------------------------------
# parse_jev_answers
# ---------------------------------------------------------------------------


class TestParseJevAnswers:
    def test_standard_tier_maps_to_correct_config(self, tool_list, model_tier_map, full_features, llm_configs):
        answers = {
            "model_tier": {"choice": "standard"},
            "tool_web_search": {"answer": "no"},
            "tool_slack_get_messages": {"answer": "yes"},
            "tool_github_create_issue": {"answer": "yes"},
            "complexity": {"answer": "moderate"},
        }
        result = parse_jev_answers(answers, full_features, tool_list, model_tier_map, llm_configs)
        assert result.config_id == "sonnet-uuid"
        assert result.model_tier == "standard"
        assert result.complexity == "moderate"

    def test_expert_complexity_overrides_to_heavy(self, tool_list, model_tier_map, full_features, llm_configs):
        answers = {
            "model_tier": {"choice": "fast"},
            "tool_web_search": {"answer": "no"},
            "tool_slack_get_messages": {"answer": "yes"},
            "tool_github_create_issue": {"answer": "yes"},
            "complexity": {"answer": "expert"},
        }
        result = parse_jev_answers(answers, full_features, tool_list, model_tier_map, llm_configs)
        assert result.config_id == "opus-uuid"
        assert result.model_tier == "heavy"

    def test_tool_filter_yes_only_strict(self, tool_list, model_tier_map, full_features, llm_configs):
        answers = {
            "model_tier": {"choice": "standard"},
            "tool_web_search": {"answer": "no"},
            "tool_slack_get_messages": {"answer": "yes"},
            "tool_github_create_issue": {"answer": "unclear"},
            "complexity": {"answer": "moderate"},
        }
        result = parse_jev_answers(answers, full_features, tool_list, model_tier_map, llm_configs, threshold="yes")
        assert result.allowed_tool_names == {"slack_get_messages"}

    def test_tool_filter_unclear_threshold_permissive(self, tool_list, model_tier_map, full_features, llm_configs):
        answers = {
            "model_tier": {"choice": "standard"},
            "tool_web_search": {"answer": "no"},
            "tool_slack_get_messages": {"answer": "yes"},
            "tool_github_create_issue": {"answer": "unclear"},
            "complexity": {"answer": "moderate"},
        }
        result = parse_jev_answers(answers, full_features, tool_list, model_tier_map, llm_configs, threshold="unclear")
        assert "slack_get_messages" in result.allowed_tool_names
        assert "github_create_issue" in result.allowed_tool_names
        assert "web_search" not in result.allowed_tool_names

    def test_tool_filtering_disabled_allowed_tool_names_is_none(self, tool_list, model_tier_map, llm_configs):
        features = {"model_routing": True, "tool_filtering": False}
        answers = {"complexity": {"answer": "moderate"}}
        result = parse_jev_answers(answers, features, tool_list, model_tier_map, llm_configs)
        assert result.allowed_tool_names is None

    def test_missing_tier_in_map_falls_back_to_default(self, tool_list, full_features, llm_configs):
        tier_map = {"fast": "haiku-uuid"}  # "standard" and "heavy" not mapped
        answers = {
            "model_tier": {"choice": "standard"},  # not in map
            "complexity": {"answer": "moderate"},
        }
        result = parse_jev_answers(answers, full_features, tool_list, tier_map, llm_configs)
        # Should fall back to default config (sonnet-uuid)
        assert result.config_id == "sonnet-uuid"

    def test_fallback_chain_excludes_primary(self, tool_list, model_tier_map, full_features, llm_configs):
        answers = {"model_tier": {"choice": "standard"}, "complexity": {"answer": "simple"}}
        result = parse_jev_answers(answers, full_features, tool_list, model_tier_map, llm_configs)
        assert result.config_id not in result.fallback_config_ids

    def test_tool_not_asked_about_is_included(self, model_tier_map, full_features, llm_configs):
        tool_list = [{"name": "my_tool", "description": "desc"}]
        answers = {"model_tier": {"choice": "fast"}, "complexity": {"answer": "trivial"}}
        # tool_my_tool not in answers
        result = parse_jev_answers(answers, full_features, tool_list, model_tier_map, llm_configs)
        assert "my_tool" in (result.allowed_tool_names or set())


# ---------------------------------------------------------------------------
# run_jev_routing (async)
# ---------------------------------------------------------------------------


class TestRunJevRouting:
    @pytest.mark.asyncio
    async def test_successful_routing(self, db_agent, typesafe_client, llm_configs, tool_list):
        jev_config = {
            "model": "jev-latest",
            "features": {"model_routing": True, "tool_filtering": True},
            "model_tier_map": {
                "fast": "haiku-uuid",
                "standard": "sonnet-uuid",
                "heavy": "opus-uuid",
            },
            "tool_filtering_threshold": "yes",
        }

        with patch(
            "src.services.agents.adk_tools.get_tool_registry"
        ) as mock_registry:
            mock_registry.return_value.list_tools.return_value = tool_list
            result = await run_jev_routing(
                db_agent=db_agent,
                query="Summarize my Slack messages",
                history=[],
                llm_configs=llm_configs,
                typesafe_client=typesafe_client,
                jev_config=jev_config,
            )

        assert isinstance(result, JevRoutingResult)
        assert result.config_id == "sonnet-uuid"
        assert "slack_get_messages" in (result.allowed_tool_names or set())
        assert "github_create_issue" in (result.allowed_tool_names or set())
        assert "web_search" not in (result.allowed_tool_names or set())

    @pytest.mark.asyncio
    async def test_api_error_raises_jev_routing_error(self, db_agent, llm_configs, tool_list):
        import httpx

        bad_client = MagicMock()
        bad_client.evaluate = AsyncMock(side_effect=httpx.RequestError("connection refused"))

        jev_config = {
            "features": {"model_routing": True, "tool_filtering": True},
            "model_tier_map": {"standard": "sonnet-uuid"},
        }

        with patch(
            "src.services.agents.adk_tools.get_tool_registry"
        ) as mock_registry:
            mock_registry.return_value.list_tools.return_value = tool_list
            with pytest.raises(JevRoutingError):
                await run_jev_routing(
                    db_agent=db_agent,
                    query="test",
                    history=None,
                    llm_configs=llm_configs,
                    typesafe_client=bad_client,
                    jev_config=jev_config,
                )

    @pytest.mark.asyncio
    async def test_api_returns_error_field_raises_jev_routing_error(self, db_agent, llm_configs, tool_list):
        error_client = MagicMock()
        error_client.evaluate = AsyncMock(return_value={"error": "invalid api key"})

        jev_config = {
            "features": {"model_routing": True, "tool_filtering": True},
            "model_tier_map": {"standard": "sonnet-uuid"},
        }

        with patch(
            "src.services.agents.adk_tools.get_tool_registry"
        ) as mock_registry:
            mock_registry.return_value.list_tools.return_value = tool_list
            with pytest.raises(JevRoutingError, match="JEV API returned error"):
                await run_jev_routing(
                    db_agent=db_agent,
                    query="test",
                    history=None,
                    llm_configs=llm_configs,
                    typesafe_client=error_client,
                    jev_config=jev_config,
                )

    @pytest.mark.asyncio
    async def test_all_features_disabled_raises_jev_routing_error(self, db_agent, llm_configs, tool_list):
        empty_client = MagicMock()
        jev_config = {
            "features": {"model_routing": False, "tool_filtering": False},
            "model_tier_map": {},
        }

        with patch(
            "src.services.agents.adk_tools.get_tool_registry"
        ) as mock_registry:
            mock_registry.return_value.list_tools.return_value = tool_list
            with pytest.raises(JevRoutingError, match="all features disabled"):
                await run_jev_routing(
                    db_agent=db_agent,
                    query="test",
                    history=None,
                    llm_configs=llm_configs,
                    typesafe_client=empty_client,
                    jev_config=jev_config,
                )
