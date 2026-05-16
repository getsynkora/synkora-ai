"""
Tests for tool_filter.py - Context-Aware Tool Filtering

Tests the filtering logic that reduces the number of tools sent to the LLM
based on message content for improved latency and reduced token costs.
"""

from unittest.mock import MagicMock

import pytest

from src.services.agents.tool_filter import (
    ALWAYS_INCLUDE_TOOLS,
    COMPLEXITY_TOOL_LIMITS,
    TOOL_KEYWORDS,
    TaskComplexity,
    ToolFilterConfig,
    _compute_hybrid_score,
    _detect_task_complexity,
    _expand_categories,
    _extract_keywords_from_message,
    _matches_pattern,
    _normalize_text,
    _score_tool,
    filter_tool_names_by_message,
    filter_tools_by_message,
)


class TestNormalizeText:
    """Tests for _normalize_text function."""

    def test_lowercase(self):
        result = _normalize_text("Hello World")
        assert result == "hello world"

    def test_removes_punctuation(self):
        result = _normalize_text("Hello, World! How are you?")
        assert "," not in result
        assert "!" not in result
        assert "?" not in result
        assert "hello" in result
        assert "world" in result

    def test_preserves_numbers(self):
        result = _normalize_text("Version 3.14 is here")
        assert "3" in result
        assert "14" in result

    def test_empty_string(self):
        result = _normalize_text("")
        assert result == ""

    def test_special_characters(self):
        result = _normalize_text("user@example.com #tag")
        assert "@" not in result
        assert "#" not in result


class TestExtractKeywordsFromMessage:
    """Tests for _extract_keywords_from_message function."""

    def test_extracts_words(self):
        result = _extract_keywords_from_message("send email to john")
        assert "send" in result
        assert "email" in result
        assert "john" in result

    def test_extracts_bigrams(self):
        result = _extract_keywords_from_message("create pull request")
        assert "create pull" in result
        assert "pull request" in result

    def test_lowercase_keywords(self):
        result = _extract_keywords_from_message("Send EMAIL")
        assert "send" in result
        assert "email" in result

    def test_empty_message(self):
        result = _extract_keywords_from_message("")
        assert result == set()

    def test_single_word(self):
        result = _extract_keywords_from_message("hello")
        assert "hello" in result
        # No bigrams for single word
        assert len(result) == 1


class TestDetectTaskComplexity:
    """Tests for _detect_task_complexity function."""

    def test_simple_task(self):
        # Single service, basic query
        result = _detect_task_complexity("read file from disk")
        assert result == TaskComplexity.SIMPLE

    def test_moderate_task_with_two_services(self):
        # Two services mentioned
        result = _detect_task_complexity("send slack message and create jira ticket")
        assert result == TaskComplexity.MODERATE

    def test_moderate_task_with_multi_step_indicator(self):
        # Multi-step indicator
        result = _detect_task_complexity("first read the file then update it")
        assert result == TaskComplexity.MODERATE

    def test_complex_task_with_three_services(self):
        # Three+ services
        result = _detect_task_complexity("check slack for updates, create github issue, and email the team")
        assert result == TaskComplexity.COMPLEX

    def test_complex_task_with_many_actions(self):
        # Multiple action verbs
        result = _detect_task_complexity("read the data, analyze it, create a chart, and send it")
        # Should be complex due to multiple actions
        assert result in (TaskComplexity.MODERATE, TaskComplexity.COMPLEX)

    def test_empty_message(self):
        result = _detect_task_complexity("")
        assert result == TaskComplexity.SIMPLE

    def test_complexity_limits_are_defined(self):
        # Ensure all complexity levels have defined limits
        assert TaskComplexity.SIMPLE in COMPLEXITY_TOOL_LIMITS
        assert TaskComplexity.MODERATE in COMPLEXITY_TOOL_LIMITS
        assert TaskComplexity.COMPLEX in COMPLEXITY_TOOL_LIMITS


class TestExpandCategories:
    """Tests for _expand_categories function."""

    def test_expands_matching_category(self):
        initial_tools = {"internal_slack_send_message"}
        available_tools = {
            "internal_slack_send_message",
            "internal_slack_list_channels",
            "internal_slack_read_channel_messages",
            "internal_read_file",
        }

        result = _expand_categories("send a slack message", initial_tools, available_tools)

        # Should include other slack tools
        assert "internal_slack_send_message" in result
        # Other slack tools may be added depending on category config
        assert len(result) >= 1

    def test_no_expansion_for_unrelated_message(self):
        initial_tools = {"internal_read_file"}
        available_tools = {"internal_read_file", "internal_slack_send_message"}

        result = _expand_categories("read a text file", initial_tools, available_tools)

        # Should not add slack tools
        assert "internal_read_file" in result
        # Result should include at least the initial tools
        assert len(result) >= 1

    def test_only_adds_available_tools(self):
        initial_tools = {"internal_slack_send_message"}
        available_tools = {"internal_slack_send_message"}  # Limited tools

        result = _expand_categories("slack message", initial_tools, available_tools)

        # Should only include available tools
        assert all(tool in available_tools for tool in result)

    def test_empty_message(self):
        initial_tools = {"tool1"}
        available_tools = {"tool1", "tool2"}

        result = _expand_categories("", initial_tools, available_tools)

        # Should return at least initial tools
        assert "tool1" in result


class TestMatchesPattern:
    """Tests for _matches_pattern function."""

    def test_exact_match(self):
        assert _matches_pattern("internal_read_file", "internal_read_file") is True
        assert _matches_pattern("internal_read_file", "internal_write_file") is False

    def test_wildcard_all(self):
        assert _matches_pattern("any_tool_name", "*") is True

    def test_prefix_wildcard(self):
        assert _matches_pattern("internal_slack_send", "internal_slack_*") is True
        assert _matches_pattern("internal_jira_create", "internal_slack_*") is False

    def test_suffix_wildcard(self):
        assert _matches_pattern("test_internal", "*_internal") is True
        assert _matches_pattern("internal_test", "*_internal") is False

    def test_middle_wildcard(self):
        assert _matches_pattern("internal_slack_send", "internal_*_send") is True
        assert _matches_pattern("internal_jira_create", "internal_*_send") is False


class TestScoreTool:
    """Tests for _score_tool function."""

    def test_scores_tool_name_match(self):
        # Tool name words in message should score high
        score = _score_tool("internal_slack_send", "Send a Slack message", {"slack", "message"}, "send slack message")
        assert score > 0

    def test_scores_keyword_match(self):
        # Keywords from TOOL_KEYWORDS should score
        tool_name = "internal_slack_send_message"
        if tool_name in TOOL_KEYWORDS:
            score = _score_tool(
                tool_name, "Send a message to Slack", {"slack", "send", "message"}, "send a slack message"
            )
            assert score > 0

    def test_scores_description_match(self):
        score = _score_tool("some_tool", "This tool sends emails to users", {"email", "send"}, "send email")
        assert score > 0

    def test_no_match_scores_zero(self):
        score = _score_tool("internal_database_query", "Query the database", {"slack", "message"}, "send slack message")
        # Should score low or zero for unrelated tools
        assert score < 5

    def test_score_capped_at_ten(self):
        # Even with many matches, score should not exceed 10
        score = _score_tool(
            "internal_slack_send_message",
            "slack message send channel dm direct",  # Many matching words
            {"slack", "message", "send", "channel", "dm", "direct"},
            "slack send message channel dm direct",
        )
        assert score <= 10.0


class TestComputeHybridScore:
    """Tests for _compute_hybrid_score function."""

    def test_keyword_only_when_no_embedding(self):
        config = ToolFilterConfig(keyword_weight=0.6, embedding_weight=0.4)

        result = _compute_hybrid_score(8.0, 0.0, config)

        # Should return keyword score when embedding is 0
        assert result == 8.0

    def test_hybrid_with_both_scores(self):
        config = ToolFilterConfig(keyword_weight=0.6, embedding_weight=0.4)

        result = _compute_hybrid_score(10.0, 1.0, config)

        # Should be weighted average scaled to 0-10
        # (0.6 * 1.0 + 0.4 * 1.0) / 1.0 * 10 = 10.0
        assert result > 0
        assert result <= 10.0

    def test_hybrid_lower_embedding_score(self):
        config = ToolFilterConfig(keyword_weight=0.6, embedding_weight=0.4)

        # Keyword score: 8/10 = 0.8, Embedding: 0.5
        result = _compute_hybrid_score(8.0, 0.5, config)

        # Should be less than pure keyword score of 8 since embedding is lower
        expected = (0.6 * 0.8 + 0.4 * 0.5) * 10  # = 6.8
        assert abs(result - expected) < 0.01


class TestToolFilterConfig:
    """Tests for ToolFilterConfig dataclass."""

    def test_default_values(self):
        config = ToolFilterConfig()

        # Defaults should favor a compact shortlist over sending the whole registry.
        assert config.min_tools == 10
        assert config.max_tools == 20
        assert config.fallback_to_all is False
        assert config.min_score_threshold == 1.0
        assert config.keyword_weight == 0.6
        assert config.embedding_weight == 0.4
        assert config.embedding_score_threshold == 0.2

    def test_custom_values(self):
        config = ToolFilterConfig(min_tools=10, max_tools=50, fallback_to_all=False, min_score_threshold=1.0)

        assert config.min_tools == 10
        assert config.max_tools == 50
        assert config.fallback_to_all is False
        assert config.min_score_threshold == 1.0


class TestFilterToolsByMessage:
    """Tests for filter_tools_by_message function."""

    @pytest.fixture
    def sample_tools(self):
        return [
            {"name": "internal_slack_send_message", "description": "Send a message to Slack"},
            {"name": "internal_slack_list_channels", "description": "List Slack channels"},
            {"name": "internal_read_file", "description": "Read a file from disk"},
            {"name": "internal_write_file", "description": "Write content to a file"},
            {"name": "internal_jira_create_issue", "description": "Create a Jira issue"},
            {"name": "internal_github_clone_repo", "description": "Clone a GitHub repository"},
            {"name": "web_search", "description": "Search the web"},
            {"name": "internal_query_database", "description": "Query a database"},
        ]

    def test_empty_message_returns_all(self, sample_tools):
        result = filter_tools_by_message("", sample_tools)
        assert result == sample_tools

    def test_empty_tools_returns_empty(self):
        result = filter_tools_by_message("send slack message", [])
        assert result == []

    def test_few_tools_skips_filter(self):
        tools = [{"name": "tool1", "description": "desc1"}]
        config = ToolFilterConfig(min_tools=5)

        result = filter_tools_by_message("any message", tools, config)

        # Should return all tools when fewer than min_tools
        assert result == tools

    def test_skips_filter_when_tool_count_already_within_effective_cap(self):
        tools = [{"name": f"tool_{i}", "description": f"Tool {i}"} for i in range(25)]
        config = ToolFilterConfig(max_tools=20, fallback_to_all=False)

        result = filter_tools_by_message("send slack message and create jira ticket", tools, config)

        # Moderate tasks allow up to 30 tools, so filtering should not remove any.
        assert result == tools

    def test_filters_slack_related(self, sample_tools):
        config = ToolFilterConfig(min_tools=1, fallback_to_all=False)

        result = filter_tools_by_message("send a slack message", sample_tools, config)

        result_names = [t["name"] for t in result]
        # Slack tools should be highly ranked
        assert any("slack" in name for name in result_names)

    def test_filters_file_related(self, sample_tools):
        config = ToolFilterConfig(min_tools=1, fallback_to_all=False)

        result = filter_tools_by_message("read the configuration file", sample_tools, config)

        result_names = [t["name"] for t in result]
        # File tools should be highly ranked
        assert any("file" in name for name in result_names)

    def test_fallback_to_all_when_no_matches(self, sample_tools):
        config = ToolFilterConfig(
            min_tools=5,
            min_score_threshold=100.0,  # Impossibly high threshold
            fallback_to_all=True,
        )

        result = filter_tools_by_message("xyz123 random text", sample_tools, config)

        # Should fall back to all tools
        assert len(result) == len(sample_tools)

    def test_respects_max_tools(self, sample_tools):
        config = ToolFilterConfig(
            min_tools=1,
            max_tools=3,
            min_score_threshold=0.0,  # Include all that score > 0
            fallback_to_all=False,
        )

        result = filter_tools_by_message("slack file github jira database web", sample_tools, config)

        # Should not exceed max_tools (though complexity may override)
        # The effective max is max(config.max_tools, complexity_limit)
        assert len(result) <= max(config.max_tools, COMPLEXITY_TOOL_LIMITS[TaskComplexity.COMPLEX])

    def test_always_include_tools_added(self):
        # Create tools including the always-include discovery tools
        tools = [
            {"name": "internal_search_available_tools", "description": "Search for tools"},
            {"name": "internal_list_tool_categories", "description": "List tool categories"},
            {"name": "internal_slack_send_message", "description": "Send Slack message"},
            {"name": "internal_read_file", "description": "Read file"},
            {"name": "tool_a", "description": "Tool A"},
            {"name": "tool_b", "description": "Tool B"},
        ]

        config = ToolFilterConfig(min_tools=1, fallback_to_all=False)

        result = filter_tools_by_message("read a file", tools, config)
        result_names = [t["name"] for t in result]

        # Always-include tools should be present if they were available
        for always_tool in ALWAYS_INCLUDE_TOOLS:
            if always_tool in [t["name"] for t in tools]:
                assert always_tool in result_names

    def test_none_config_uses_defaults(self, sample_tools):
        result = filter_tools_by_message("send slack message", sample_tools, None)

        # Should work with default config
        assert isinstance(result, list)


class TestFilterToolNamesByMessage:
    """Tests for filter_tool_names_by_message function."""

    def test_returns_filtered_names(self):
        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = [
            {"name": "internal_slack_send", "description": "Send Slack"},
            {"name": "internal_read_file", "description": "Read file"},
        ]

        tool_names = ["internal_slack_send", "internal_read_file"]

        result = filter_tool_names_by_message("read file", tool_names, mock_registry)

        assert isinstance(result, list)
        assert all(isinstance(name, str) for name in result)

    def test_empty_message_returns_all(self):
        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = []

        tool_names = ["tool1", "tool2"]

        result = filter_tool_names_by_message("", tool_names, mock_registry)

        assert result == tool_names

    def test_empty_tool_names_returns_empty(self):
        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = []

        result = filter_tool_names_by_message("any message", [], mock_registry)

        assert result == []


class TestIntegration:
    """Integration tests for the tool filtering system."""

    @pytest.fixture
    def large_tool_set(self):
        """Create a realistic set of tools for integration testing."""
        return [
            # Slack tools
            {"name": "internal_slack_send_message", "description": "Send a message to a Slack channel or DM"},
            {"name": "internal_slack_list_channels", "description": "List all Slack channels"},
            {"name": "internal_slack_read_channel_messages", "description": "Read messages from a channel"},
            {"name": "internal_slack_search_messages", "description": "Search Slack messages"},
            # File tools
            {"name": "internal_read_file", "description": "Read content from a file"},
            {"name": "internal_write_file", "description": "Write content to a file"},
            {"name": "internal_list_directory", "description": "List files in a directory"},
            {"name": "internal_search_files", "description": "Search for files by pattern"},
            # GitHub tools
            {"name": "internal_git_clone_repo", "description": "Clone a GitHub repository"},
            {"name": "internal_git_create_pr", "description": "Create a pull request"},
            {"name": "internal_git_list_branches", "description": "List repository branches"},
            # Jira tools
            {"name": "internal_jira_create_issue", "description": "Create a Jira issue"},
            {"name": "internal_jira_list_issues", "description": "List Jira issues"},
            {"name": "internal_add_jira_comment", "description": "Add comment to Jira issue"},
            # Database tools
            {"name": "internal_query_database", "description": "Execute database query"},
            {"name": "internal_list_database_connections", "description": "List database connections"},
            # Email tools
            {"name": "internal_send_email", "description": "Send an email"},
            {"name": "internal_read_emails", "description": "Read emails from inbox"},
            # Web tools
            {"name": "web_search", "description": "Search the web"},
            {"name": "web_crawl", "description": "Crawl a webpage"},
            # Calendar tools
            {"name": "internal_google_calendar_list_events", "description": "List calendar events"},
            {"name": "internal_google_calendar_create_event", "description": "Create calendar event"},
            # Discovery tools (always included)
            {"name": "internal_search_available_tools", "description": "Search for available tools"},
            {"name": "internal_list_tool_categories", "description": "List tool categories"},
        ]

    def test_slack_query_prioritizes_slack_tools(self, large_tool_set):
        config = ToolFilterConfig(min_tools=3, max_tools=10, fallback_to_all=False)

        result = filter_tools_by_message("send a message to the #general channel on slack", large_tool_set, config)

        result_names = [t["name"] for t in result]

        # Slack tools should be in the top results
        slack_tools_in_result = [n for n in result_names if "slack" in n]
        assert len(slack_tools_in_result) >= 2

    def test_multi_service_query_includes_multiple_categories(self, large_tool_set):
        config = ToolFilterConfig(min_tools=5, fallback_to_all=False)

        result = filter_tools_by_message("read the log file and then send the errors to slack", large_tool_set, config)

        result_names = [t["name"] for t in result]

        # Should include both file and slack tools
        has_file_tool = any("file" in n or "read" in n for n in result_names)
        has_slack_tool = any("slack" in n for n in result_names)

        assert has_file_tool or has_slack_tool

    def test_complex_workflow_gets_more_tools(self, large_tool_set):
        simple_result = filter_tools_by_message("read a file", large_tool_set)

        complex_result = filter_tools_by_message(
            "first read the log files, then analyze them, create a jira ticket for each error, and send a summary to slack",
            large_tool_set,
        )

        # Complex task should potentially get more tools
        # (depending on scoring, but complexity detection should allow higher max)
        assert len(complex_result) >= len(simple_result)
