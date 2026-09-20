"""Unit tests for the pure-logic pieces of browser_autopilot.py: the
action-space builder, answer validation, and the pages_seen accumulator that
lets open-ended "browse and gather" goals (e.g. "find hotels and compare the
top 3 by price") report everything the run actually saw, not just wherever
it happened to end."""

import pytest

from src.services.agents.internal_tools.browser_autopilot import (
    _MAX_PAGES_SEEN,
    _page_content,
    _record_page_seen,
    build_action_space,
    validate_choice,
)


def _fill_action(node, label, value=""):
    return {"node": node, "kind": "fill", "id": f"e{node}", "label": label, "role": "textbox", "value": value}


def _click_action(node, label):
    return {"node": node, "kind": "click", "id": f"e{node}", "label": label, "role": "button", "value": ""}


def _select_actions(node, label, options):
    return [
        {
            "node": node,
            "kind": "select",
            "id": f"e{node}",
            "label": f"{label} → {opt}",
            "role": "combobox",
            "value": opt,
            "current_value": "",
        }
        for opt in options
    ]


@pytest.mark.unit
class TestBuildActionSpace:
    def test_dedupes_by_node_and_groups_operations(self):
        actions = [
            _fill_action(1, "Email"),
            _click_action(1, "Open Email"),  # same node as the fill above
            _click_action(2, "Submit"),
        ]
        elements, targets, controls = build_action_space(actions)

        assert len(elements) == 2
        email_el = next(e for e in elements if e["label"] == "Email")
        assert set(email_el["operations"]) == {"TYPE_TEXT", "CLICK"}
        assert targets["TYPE_TEXT"]["1"]["label"] == "Email"
        assert targets["CLICK"]["2"]["label"] == "Submit"

    def test_select_options_get_compound_target_ids(self):
        actions = _select_actions(1, "Country", ["us", "de"])
        elements, targets, controls = build_action_space(actions)

        assert len(elements) == 1
        assert elements[0]["options"] == [
            {"index": "1:1", "label": "Country → us", "value": "us"},
            {"index": "1:2", "label": "Country → de", "value": "de"},
        ]
        assert set(targets["SELECT"].keys()) == {"1:1", "1:2"}

    def test_non_operation_kinds_become_controls(self):
        actions = [{"id": "wait", "kind": "wait", "label": "Wait for the page to update"}]
        elements, targets, controls = build_action_space(actions)

        assert elements == []
        assert targets == {}
        assert "WAIT" in controls


@pytest.mark.unit
class TestValidateChoice:
    def _well_formed(self, choice, ids):
        probs = {i: (0.9 if i == choice else 0.1 / max(1, len(ids) - 1)) for i in ids}
        total = sum(probs.values())
        return {"choice": choice, "confidence": 0.9, "probabilities": {k: v / total for k, v in probs.items()}}

    def test_accepts_well_formed_answer(self):
        ids = ["1", "2", "3"]
        answer = self._well_formed("2", ids)
        assert validate_choice(answer, ids) is answer

    def test_rejects_choice_not_in_ids(self):
        answer = self._well_formed("2", ["1", "2"])
        answer["choice"] = "99"
        with pytest.raises(ValueError):
            validate_choice(answer, ["1", "2"])

    def test_rejects_probabilities_not_summing_to_one(self):
        answer = {"choice": "1", "confidence": 0.9, "probabilities": {"1": 0.9, "2": 0.9}}
        with pytest.raises(ValueError):
            validate_choice(answer, ["1", "2"])

    def test_rejects_choice_not_the_argmax(self):
        answer = {"choice": "1", "confidence": 0.9, "probabilities": {"1": 0.1, "2": 0.9}}
        with pytest.raises(ValueError):
            validate_choice(answer, ["1", "2"])

    def test_rejects_missing_fields(self):
        with pytest.raises(ValueError):
            validate_choice({}, ["1"])


@pytest.mark.unit
class TestPageContent:
    def test_extracts_title_and_text(self):
        snapshot = {"title": "Example", "text": "hello world", "url": "https://example.com"}
        assert _page_content(snapshot) == {"page_title": "Example", "page_text": "hello world"}


@pytest.mark.unit
class TestRecordPageSeen:
    def test_records_first_page(self):
        pages: list = []
        _record_page_seen(pages, {"url": "https://a.com", "title": "A", "text": "page a"})
        assert pages == [{"url": "https://a.com", "title": "A", "text": "page a"}]

    def test_dedupes_by_url(self):
        pages: list = []
        snapshot = {"url": "https://a.com", "title": "A", "text": "page a"}
        _record_page_seen(pages, snapshot)
        _record_page_seen(pages, snapshot)
        assert len(pages) == 1

    def test_multiple_distinct_pages_all_recorded_in_order(self):
        pages: list = []
        _record_page_seen(pages, {"url": "https://a.com", "title": "A", "text": "page a"})
        _record_page_seen(pages, {"url": "https://b.com", "title": "B", "text": "page b"})
        assert [p["url"] for p in pages] == ["https://a.com", "https://b.com"]

    def test_stops_recording_once_cap_reached(self):
        pages: list = [{"url": f"https://{i}.com", "title": "", "text": ""} for i in range(_MAX_PAGES_SEEN)]
        _record_page_seen(pages, {"url": "https://overflow.com", "title": "", "text": ""})
        assert len(pages) == _MAX_PAGES_SEEN
        assert not any(p["url"] == "https://overflow.com" for p in pages)
