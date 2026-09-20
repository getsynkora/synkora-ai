"""Unit tests for the pure-logic pieces of browser_autopilot.py: the
action-space builder, answer validation, and the pages_seen accumulator that
lets open-ended "browse and gather" goals (e.g. "find hotels and compare the
top 3 by price") report everything the run actually saw, not just wherever
it happened to end."""

import base64
import tempfile
from pathlib import Path

import pytest

from src.services.agents.internal_tools.browser_autopilot import (
    _MAX_PAGES_SEEN,
    _page_content,
    _read_workspace_files,
    _record_page_seen,
    build_action_space,
    validate_choice,
)


class _FakeRuntimeContext:
    tenant_id = "11111111-1111-1111-1111-111111111111"
    compute_session = None


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

    def test_press_controls_become_controls_too(self):
        actions = [{"id": "press_enter", "kind": "press", "key": "Enter", "label": "Press Enter"}]
        _elements, _targets, controls = build_action_space(actions)
        assert "PRESS_ENTER" in controls
        assert controls["PRESS_ENTER"]["key"] == "Enter"

    def test_upload_kind_maps_to_upload_file_operation(self):
        actions = [
            {
                "node": 1,
                "kind": "upload",
                "id": "e1",
                "label": "Resume",
                "role": "button",
                "value": "",
                "accept": ".pdf",
            }
        ]
        elements, targets, _controls = build_action_space(actions)
        assert "UPLOAD_FILE" in targets
        assert targets["UPLOAD_FILE"]["1"]["accept"] == ".pdf"
        assert "UPLOAD_FILE" in elements[0]["operations"]

    def test_same_node_id_in_different_frames_are_not_merged(self):
        """node ids are only unique WITHIN a frame — the same integer in the main
        page and inside an embedded iframe must be treated as two distinct elements,
        not merged into one (the exact bug this test guards against: iframe support
        introduced node-id collisions since every frame's own snapshot restarts its
        counter from 1)."""
        actions = [
            {**_fill_action(1, "Main page field"), "frame_index": 0},
            {**_fill_action(1, "Iframe field"), "frame_index": 1},
        ]
        elements, targets, _controls = build_action_space(actions)

        assert len(elements) == 2, "same node id in two different frames must not be merged"
        labels = {e["label"] for e in elements}
        assert labels == {"Main page field", "Iframe field"}
        assert set(targets["TYPE_TEXT"].keys()) == {"1", "2"}

    def test_missing_frame_index_defaults_to_main_frame(self):
        """Actions without an explicit frame_index (e.g. plain unit-test fixtures
        elsewhere in this file) must still behave exactly as before frame support
        was added — defaulting to frame_index=0, not crashing or misbehaving."""
        actions = [_fill_action(1, "Email")]
        elements, _targets, _controls = build_action_space(actions)
        assert len(elements) == 1


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


@pytest.mark.unit
class TestReadWorkspaceFiles:
    """UPLOAD_FILE must only ever read from the agent's own owned workspace, the exact
    same secure mechanism internal_browser_upload_file already uses — never an arbitrary
    path on the scraper's own filesystem."""

    async def test_reads_a_real_file_and_base64_encodes_it(self):
        with tempfile.TemporaryDirectory() as workspace:
            (Path(workspace) / "resume.txt").write_bytes(b"hello resume content")

            files = await _read_workspace_files(["resume.txt"], _FakeRuntimeContext(), {"workspace_path": workspace})

        assert len(files) == 1
        assert files[0]["name"] == "resume.txt"
        assert files[0]["mime_type"] == "text/plain"
        assert base64.b64decode(files[0]["content_base64"]) == b"hello resume content"

    async def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as workspace:
            with pytest.raises(ValueError):
                await _read_workspace_files(["../../etc/passwd"], _FakeRuntimeContext(), {"workspace_path": workspace})

    async def test_rejects_more_than_ten_files(self):
        with pytest.raises(ValueError, match="between one and ten"):
            await _read_workspace_files(
                [f"file{i}.txt" for i in range(11)], _FakeRuntimeContext(), {"workspace_path": "/tmp"}
            )

    async def test_rejects_empty_file_list(self):
        with pytest.raises(ValueError):
            await _read_workspace_files([], _FakeRuntimeContext(), {"workspace_path": "/tmp"})

    async def test_requires_a_workspace_root(self):
        with pytest.raises(ValueError, match="owned workspace"):
            await _read_workspace_files(["a.txt"], _FakeRuntimeContext(), {})
