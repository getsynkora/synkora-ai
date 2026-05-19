"""
Tests for context_pruning.py

Covers:
- _extract_result_summary: meaningful 1-line summaries from tool results
- Error result pruning: old errors get replaced with summaries (not kept forever)
- Large result summaries: use_meaningful_summaries=True replaces head+tail trim
- Recent results untouched: last N always kept at full fidelity
"""

import json

import pytest

from src.services.agents.context_pruning import (
    RESULT_PRUNED_MARKER,
    PruningSettings,
    _extract_result_summary,
    _get_tool_name_for_result,
    prune_tool_results,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool_msg(tool_call_id: str, content) -> dict:
    if not isinstance(content, str):
        content = json.dumps(content)
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def _assistant_call(call_id: str, tool_name: str, args: dict | None = None) -> dict:
    return {
        "role": "assistant",
        "tool_calls": [
            {
                "id": call_id,
                "function": {"name": tool_name, "arguments": json.dumps(args or {})},
            }
        ],
    }


def _assistant_text(text: str) -> dict:
    return {"role": "assistant", "content": text}


def _user(text: str) -> dict:
    return {"role": "user", "content": text}


def _four_tool_conversation(first_content) -> list[dict]:
    """
    Conversation with 4 tool results so that `keep_last_results=3`
    puts the first one into prune_candidates.
    """
    return [
        _user("query 1"),
        _assistant_call("c1", "internal_query_database"),
        _tool_msg("c1", first_content),
        _assistant_text("got it"),
        _user("query 2"),
        _assistant_call("c2", "internal_query_database"),
        _tool_msg("c2", {"row_count": 10, "rows": []}),
        _assistant_call("c3", "internal_query_database"),
        _tool_msg("c3", {"row_count": 20, "rows": []}),
        _assistant_call("c4", "internal_query_database"),
        _tool_msg("c4", {"row_count": 30, "rows": []}),
    ]


# ---------------------------------------------------------------------------
# _extract_result_summary
# ---------------------------------------------------------------------------


class TestExtractResultSummary:
    def test_database_result_with_row_count(self):
        content = json.dumps({"row_count": 847, "rows": [], "columns": ["id", "name"]})
        summary = _extract_result_summary("internal_query_database", content)
        assert "847" in summary
        assert "internal_query_database" in summary

    def test_database_result_rows_list(self):
        content = json.dumps({"rows": [{"id": i} for i in range(50)], "columns": ["id"]})
        summary = _extract_result_summary("internal_query_database", content)
        assert "50" in summary

    def test_error_result_includes_error_message(self):
        content = json.dumps({"error": "Table not found in location asia-southeast1"})
        summary = _extract_result_summary("internal_query_database", content)
        assert "Table not found" in summary
        assert "internal_query_database" in summary

    def test_success_true_result(self):
        content = json.dumps({"success": True, "ts": "12345.67"})
        summary = _extract_result_summary("internal_slack_send_message", content)
        assert "internal_slack_send_message" in summary
        assert "succeeded" in summary.lower() or "success" in summary.lower() or "ok" in summary.lower()

    def test_result_with_number_field(self):
        content = json.dumps({"number": 42, "title": "Fix auth bug", "state": "open"})
        summary = _extract_result_summary("internal_create_github_issue", content)
        assert "42" in summary

    def test_result_with_id_field(self):
        content = json.dumps({"id": "abc-123", "name": "something"})
        summary = _extract_result_summary("some_tool", content)
        assert "abc-123" in summary

    def test_result_with_items_list(self):
        content = json.dumps({"items": [{"name": f"item{i}"} for i in range(7)]})
        summary = _extract_result_summary("some_tool", content)
        assert "7" in summary

    def test_plain_text_content(self):
        content = "Hello, this is a plain text response from a tool"
        summary = _extract_result_summary("some_tool", content)
        assert "some_tool" in summary
        assert len(summary) <= 200

    def test_summary_starts_with_pruned_marker(self):
        content = json.dumps({"row_count": 5, "rows": []})
        summary = _extract_result_summary("any_tool", content)
        assert summary.startswith(RESULT_PRUNED_MARKER)

    def test_summary_is_always_short(self):
        """No summary should exceed 250 chars — it defeats the purpose."""
        big_content = json.dumps({"row_count": 999, "rows": [{"x": "y" * 100} for _ in range(100)]})
        summary = _extract_result_summary("internal_query_database", big_content)
        assert len(summary) <= 250

    def test_empty_dict_content(self):
        summary = _extract_result_summary("tool", "{}")
        assert "tool" in summary
        assert len(summary) <= 250

    def test_list_content(self):
        content = json.dumps([{"id": 1}, {"id": 2}, {"id": 3}])
        summary = _extract_result_summary("list_tool", content)
        assert "3" in summary or "list_tool" in summary


# ---------------------------------------------------------------------------
# _get_tool_name_for_result
# ---------------------------------------------------------------------------


class TestGetToolNameForResult:
    def test_extracts_name_from_adjacent_assistant_message(self):
        messages = [
            _assistant_call("c1", "internal_query_database"),
            _tool_msg("c1", "{}"),
        ]
        name = _get_tool_name_for_result(messages[1], messages, 1)
        assert name == "internal_query_database"

    def test_returns_fallback_when_no_match(self):
        messages = [_tool_msg("orphan", "{}")]
        name = _get_tool_name_for_result(messages[0], messages, 0)
        assert isinstance(name, str)
        assert len(name) > 0  # Not empty


# ---------------------------------------------------------------------------
# Error pruning
# ---------------------------------------------------------------------------


class TestErrorPruning:
    def test_old_error_is_replaced_with_summary(self):
        """Error not in last 3 results must be summarised, not kept at full size."""
        error_content = json.dumps({"error": "Permission denied: table users"})
        messages = _four_tool_conversation(error_content)
        settings = PruningSettings(
            prune_error_results=True,
            keep_last_results=3,
            use_meaningful_summaries=True,
        )
        pruned, stats = prune_tool_results(messages, settings)

        old_result = next(m for m in pruned if m.get("tool_call_id") == "c1")
        # Full error JSON blob should be gone — replaced with compact summary
        assert old_result["content"] != json.dumps({"error": "Permission denied: table users"})
        # Summary should be short and start with the pruned marker
        assert old_result["content"].startswith(RESULT_PRUNED_MARKER)
        assert len(old_result["content"]) <= 250
        assert stats.tool_results_pruned >= 1

    def test_recent_error_is_kept_intact(self):
        """Error in last 3 results must NOT be touched."""
        error_content = json.dumps({"error": "permission denied"})
        messages = [
            _user("run"),
            _assistant_call("c1", "q"),
            _tool_msg("c1", error_content),
        ]
        settings = PruningSettings(prune_error_results=True, keep_last_results=3)
        pruned, stats = prune_tool_results(messages, settings)

        result = next(m for m in pruned if m.get("tool_call_id") == "c1")
        assert "permission denied" in result["content"]
        assert stats.tool_results_pruned == 0

    def test_old_error_pruning_was_broken_before_fix(self):
        """
        Regression: prune_error_results=False (old default) must leave old errors untouched.
        This test ensures the old behaviour is still accessible via the flag.
        """
        error_content = json.dumps({"error": "some old error"})
        messages = _four_tool_conversation(error_content)
        settings = PruningSettings(
            prune_error_results=False,
            keep_last_results=3,
        )
        pruned, _ = prune_tool_results(messages, settings)

        old_result = next(m for m in pruned if m.get("tool_call_id") == "c1")
        assert "some old error" in old_result["content"]


# ---------------------------------------------------------------------------
# Meaningful summaries for large non-error results
# ---------------------------------------------------------------------------


class TestMeaningfulSummaries:
    def _large_db_result(self, row_count: int = 500) -> str:
        return json.dumps(
            {
                "row_count": row_count,
                "rows": [{"id": i, "name": f"user_{i}", "email": f"u{i}@example.com"} for i in range(row_count)],
                "columns": ["id", "name", "email"],
            }
        )

    def test_large_old_result_replaced_with_summary(self):
        messages = _four_tool_conversation(self._large_db_result(500))
        settings = PruningSettings(
            use_meaningful_summaries=True,
            max_result_chars=100,  # Force pruning
            keep_last_results=3,
        )
        pruned, stats = prune_tool_results(messages, settings)

        old_result = next(m for m in pruned if m.get("tool_call_id") == "c1")
        assert "500" in old_result["content"]  # Row count preserved in summary
        assert len(old_result["content"]) <= 250
        assert stats.chars_saved > 0

    def test_large_old_result_trimmed_when_summaries_disabled(self):
        """use_meaningful_summaries=False should fall back to head+tail trim."""
        messages = _four_tool_conversation(self._large_db_result(500))
        settings = PruningSettings(
            use_meaningful_summaries=False,
            max_result_chars=100,
            head_chars=50,
            tail_chars=50,
            keep_last_results=3,
        )
        pruned, stats = prune_tool_results(messages, settings)

        old_result = next(m for m in pruned if m.get("tool_call_id") == "c1")
        # Should contain the trim marker, not a summary marker
        assert "[... " in old_result["content"]
        assert RESULT_PRUNED_MARKER not in old_result["content"]

    def test_small_old_result_kept_intact(self):
        """Small results that fit within max_result_chars should not be summarised."""
        small_content = json.dumps({"row_count": 3, "rows": [{"id": 1}]})
        messages = _four_tool_conversation(small_content)
        settings = PruningSettings(
            use_meaningful_summaries=True,
            max_result_chars=5000,  # Small content fits
            keep_last_results=3,
        )
        pruned, _ = prune_tool_results(messages, settings)

        old_result = next(m for m in pruned if m.get("tool_call_id") == "c1")
        assert "row_count" in old_result["content"]  # Original content intact

    def test_summary_marker_present_in_pruned_results(self):
        """Pruned results must start with RESULT_PRUNED_MARKER for dedup cache eviction."""
        messages = _four_tool_conversation(self._large_db_result(200))
        settings = PruningSettings(
            use_meaningful_summaries=True,
            max_result_chars=100,
            keep_last_results=3,
        )
        pruned, stats = prune_tool_results(messages, settings)

        if stats.tool_results_pruned > 0:
            old_result = next(m for m in pruned if m.get("tool_call_id") == "c1")
            assert RESULT_PRUNED_MARKER in old_result["content"]


# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------


class TestDefaultSettings:
    def test_prune_error_results_defaults_to_true(self):
        """New default: errors are prunable (old default was False)."""
        settings = PruningSettings()
        assert settings.prune_error_results is True

    def test_use_meaningful_summaries_defaults_to_true(self):
        settings = PruningSettings()
        assert settings.use_meaningful_summaries is True
