"""
Unit tests for entity extraction and upsert logic in company_brain_tasks.py.
No database required — upsert is tested with in-memory mock DB session.
"""

import sys
import uuid
from unittest.mock import MagicMock

import pytest

from src.tasks.company_brain_tasks import (
    _extract_entities_and_relationships_llm,
    _extract_entities_from_meta,
    _upsert_entity,
    _upsert_relationship,
)

TENANT_ID = str(uuid.uuid4())
KB_ID = 1


# ---------------------------------------------------------------------------
# _extract_entities_from_meta — Slack
# ---------------------------------------------------------------------------


def test_extract_slack_user_and_channel():
    meta = {"user": "U123ABC", "channel": "C456DEF"}
    entities = _extract_entities_from_meta("slack", meta)

    types = {e["entity_type"] for e in entities}
    assert "person" in types
    assert "channel" in types


def test_extract_slack_person_has_slack_user_id():
    meta = {"user": "U123ABC", "channel": "C456DEF"}
    entities = _extract_entities_from_meta("slack", meta)
    person = next(e for e in entities if e["entity_type"] == "person")
    assert person["identifiers"]["slack_user_id"] == "U123ABC"
    assert person["email"] is None


def test_extract_slack_channel_entity():
    meta = {"user": "U1", "channel": "C-general"}
    entities = _extract_entities_from_meta("slack", meta)
    channel = next(e for e in entities if e["entity_type"] == "channel")
    assert channel["canonical_name"] == "C-general"
    assert channel["identifiers"]["slack_channel_id"] == "C-general"


def test_extract_slack_no_user_no_channel():
    entities = _extract_entities_from_meta("slack", {})
    assert entities == []


def test_extract_slack_user_id_fallback():
    meta = {"user_id": "U999", "channel": "C1"}
    entities = _extract_entities_from_meta("slack", meta)
    person = next(e for e in entities if e["entity_type"] == "person")
    assert person["canonical_name"] == "U999"


# ---------------------------------------------------------------------------
# _extract_entities_from_meta — GitHub / GitLab
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source_type", ["github", "gitlab"])
def test_extract_github_author_and_repo(source_type):
    meta = {"author": "alice-dev", "author_email": "alice@corp.com", "repo": "corp/api"}
    entities = _extract_entities_from_meta(source_type, meta)

    types = {e["entity_type"] for e in entities}
    assert "person" in types
    assert "repo" in types


@pytest.mark.parametrize("source_type", ["github", "gitlab"])
def test_extract_github_person_email(source_type):
    meta = {"author": "alice-dev", "author_email": "alice@corp.com", "repo": "corp/api"}
    entities = _extract_entities_from_meta(source_type, meta)
    person = next(e for e in entities if e["entity_type"] == "person")
    assert person["email"] == "alice@corp.com"
    assert person["identifiers"][f"{source_type}_login"] == "alice-dev"


@pytest.mark.parametrize("source_type", ["github", "gitlab"])
def test_extract_github_repo_no_email(source_type):
    meta = {"author": "bob", "repo": "corp/frontend"}
    entities = _extract_entities_from_meta(source_type, meta)
    repo = next(e for e in entities if e["entity_type"] == "repo")
    assert repo["email"] is None
    assert repo["identifiers"][f"{source_type}_repo"] == "corp/frontend"


@pytest.mark.parametrize("source_type", ["github", "gitlab"])
def test_extract_github_no_author_no_repo(source_type):
    entities = _extract_entities_from_meta(source_type, {})
    assert entities == []


# ---------------------------------------------------------------------------
# _extract_entities_from_meta — Jira
# ---------------------------------------------------------------------------


def test_extract_jira_email_fields():
    meta = {
        "assignee_email": "alice@corp.com",
        "reporter_email": "bob@corp.com",
        "creator_email": "charlie@corp.com",
        "project_key": "PROJ",
    }
    entities = _extract_entities_from_meta("jira", meta)
    person_emails = {e["email"] for e in entities if e["entity_type"] == "person"}
    assert person_emails == {"alice@corp.com", "bob@corp.com", "charlie@corp.com"}


def test_extract_jira_person_canonical_name_from_email():
    meta = {"assignee_email": "alice@corp.com"}
    entities = _extract_entities_from_meta("jira", meta)
    person = next(e for e in entities if e["entity_type"] == "person")
    assert person["canonical_name"] == "alice"


def test_extract_jira_project_key():
    meta = {"project_key": "BACKEND", "assignee_email": "a@b.com"}
    entities = _extract_entities_from_meta("jira", meta)
    project = next(e for e in entities if e["entity_type"] == "project")
    assert project["canonical_name"] == "BACKEND"
    assert project["identifiers"]["jira_project_key"] == "BACKEND"


def test_extract_jira_empty_meta():
    assert _extract_entities_from_meta("jira", {}) == []


# ---------------------------------------------------------------------------
# _extract_entities_from_meta — Linear
# ---------------------------------------------------------------------------


def test_extract_linear_assignee_and_creator():
    meta = {"assignee_email": "dev@company.io", "creator_email": "pm@company.io", "team_key": "BACKEND"}
    entities = _extract_entities_from_meta("linear", meta)
    person_emails = {e["email"] for e in entities if e["entity_type"] == "person"}
    assert person_emails == {"dev@company.io", "pm@company.io"}


def test_extract_linear_team():
    meta = {"team_key": "INFRA"}
    entities = _extract_entities_from_meta("linear", meta)
    team = next(e for e in entities if e["entity_type"] == "team")
    assert team["canonical_name"] == "INFRA"
    assert team["identifiers"]["linear_team_key"] == "INFRA"


def test_extract_linear_none_emails_ignored():
    meta = {"assignee_email": None, "team_key": "OPS"}
    entities = _extract_entities_from_meta("linear", meta)
    person_entities = [e for e in entities if e["entity_type"] == "person"]
    assert len(person_entities) == 0


# ---------------------------------------------------------------------------
# _extract_entities_from_meta — Notion
# ---------------------------------------------------------------------------


def test_extract_notion_page():
    meta = {"page_id": "abc-123-def", "title": "Architecture Notes"}
    entities = _extract_entities_from_meta("notion", meta)
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "page"
    assert entities[0]["canonical_name"] == "Architecture Notes"
    assert entities[0]["identifiers"]["notion_page_id"] == "abc-123-def"


def test_extract_notion_page_id_fallback_when_no_title():
    meta = {"page_id": "abc-123"}
    entities = _extract_entities_from_meta("notion", meta)
    assert entities[0]["canonical_name"] == "abc-123"


def test_extract_notion_no_page_id():
    assert _extract_entities_from_meta("notion", {}) == []


# ---------------------------------------------------------------------------
# _extract_entities_from_meta — unknown source
# ---------------------------------------------------------------------------


def test_extract_unknown_source_returns_empty():
    assert _extract_entities_from_meta("unknown_source", {"key": "value"}) == []


# ---------------------------------------------------------------------------
# _upsert_entity — create new entity
# ---------------------------------------------------------------------------


def _make_mock_db(existing=None):
    """Return a mock DB session for testing _upsert_entity."""
    db = MagicMock()
    query_mock = MagicMock()
    filter_mock = MagicMock()
    filter_mock.first = MagicMock(return_value=existing)
    query_mock.filter = MagicMock(return_value=filter_mock)
    db.query = MagicMock(return_value=query_mock)
    db.add = MagicMock()
    return db


def test_upsert_creates_new_entity_when_not_exists():
    db = _make_mock_db(existing=None)
    data = {
        "entity_type": "person",
        "canonical_name": "alice",
        "email": "alice@corp.com",
        "identifiers": {"slack_user_id": "U1"},
    }
    _upsert_entity(db, KB_ID, TENANT_ID, data)
    db.add.assert_called_once()
    entity_added = db.add.call_args[0][0]
    assert entity_added.canonical_name == "alice"
    assert entity_added.email == "alice@corp.com"
    assert entity_added.knowledge_base_id == KB_ID
    assert entity_added.display_names == ["alice"]


def test_upsert_merges_existing_entity_identifiers():
    from src.models.kb_brain import KBEntity

    existing = MagicMock(spec=KBEntity)
    existing.identifiers = {"slack_user_id": "U1"}
    existing.display_names = ["alice"]

    db = _make_mock_db(existing=existing)
    data = {
        "entity_type": "person",
        "canonical_name": "alice-dev",
        "email": "alice@corp.com",
        "identifiers": {"github_login": "alice-dev"},
    }
    _upsert_entity(db, KB_ID, TENANT_ID, data)

    # db.add should NOT be called (we updated existing)
    db.add.assert_not_called()
    # identifiers merged
    assert "slack_user_id" in existing.identifiers
    assert "github_login" in existing.identifiers


def test_upsert_merges_display_names_deduped():
    from src.models.kb_brain import KBEntity

    existing = MagicMock(spec=KBEntity)
    existing.identifiers = {}
    existing.display_names = ["alice"]

    db = _make_mock_db(existing=existing)
    data = {"entity_type": "person", "canonical_name": "alice", "email": None, "identifiers": {}}
    _upsert_entity(db, KB_ID, TENANT_ID, data)

    # Display names deduped — "alice" appears only once
    assert existing.display_names.count("alice") == 1


def test_upsert_no_email_uses_type_name_dedup():
    db = _make_mock_db(existing=None)
    data = {"entity_type": "channel", "canonical_name": "C-general", "email": None, "identifiers": {}}
    _upsert_entity(db, KB_ID, TENANT_ID, data)

    # Query should use entity_type + canonical_name (no email filter)
    # The filter is called — just verify entity was created
    db.add.assert_called_once()


def test_upsert_new_entity_has_correct_kb_id():
    db = _make_mock_db(existing=None)
    data = {
        "entity_type": "repo",
        "canonical_name": "corp/api",
        "email": None,
        "identifiers": {"github_repo": "corp/api"},
    }
    _upsert_entity(db, 99, TENANT_ID, data)
    entity = db.add.call_args[0][0]
    assert entity.knowledge_base_id == 99


# ---------------------------------------------------------------------------
# _upsert_entity — return value (needed by callers to build kb_relationships)
# ---------------------------------------------------------------------------


def test_upsert_existing_entity_returns_its_id():
    from src.models.kb_brain import KBEntity

    existing = MagicMock(spec=KBEntity)
    existing.id = 42
    existing.identifiers = {}
    existing.display_names = ["alice"]

    db = _make_mock_db(existing=existing)
    data = {"entity_type": "person", "canonical_name": "alice", "email": None, "identifiers": {}}
    result = _upsert_entity(db, KB_ID, TENANT_ID, data)

    assert result == 42


def test_upsert_new_entity_flushes_so_id_is_available():
    db = _make_mock_db(existing=None)
    data = {"entity_type": "person", "canonical_name": "carol", "email": None, "identifiers": {}}
    _upsert_entity(db, KB_ID, TENANT_ID, data)

    # Without a flush, a freshly-added row has no PK yet — callers need the id
    # in the same transaction to attach kb_relationships rows to it.
    db.flush.assert_called_once()


# ---------------------------------------------------------------------------
# _upsert_relationship
# ---------------------------------------------------------------------------


def test_upsert_relationship_creates_new_edge():
    db = _make_mock_db(existing=None)
    created = _upsert_relationship(
        db, KB_ID, TENANT_ID, source_entity_id=1, target_entity_id=2, relation_type="authored", source_doc_id=10
    )

    assert created is True
    db.add.assert_called_once()
    rel = db.add.call_args[0][0]
    assert rel.source_entity_id == 1
    assert rel.target_entity_id == 2
    assert rel.relation_type == "authored"
    assert rel.source_doc_id == 10
    assert rel.knowledge_base_id == KB_ID


def test_upsert_relationship_dedupes_existing_edge():
    from src.models.kb_brain import KBRelationship

    existing = MagicMock(spec=KBRelationship)
    existing.source_doc_id = 5

    db = _make_mock_db(existing=existing)
    created = _upsert_relationship(
        db, KB_ID, TENANT_ID, source_entity_id=1, target_entity_id=2, relation_type="authored", source_doc_id=99
    )

    assert created is False
    db.add.assert_not_called()
    # Refreshed to the newer document that evidenced the same edge
    assert existing.source_doc_id == 99


def test_upsert_relationship_keeps_prior_doc_when_new_one_is_none():
    from src.models.kb_brain import KBRelationship

    existing = MagicMock(spec=KBRelationship)
    existing.source_doc_id = 5

    db = _make_mock_db(existing=existing)
    _upsert_relationship(
        db, KB_ID, TENANT_ID, source_entity_id=1, target_entity_id=2, relation_type="authored", source_doc_id=None
    )

    assert existing.source_doc_id == 5


# ---------------------------------------------------------------------------
# _extract_entities_and_relationships_llm
# ---------------------------------------------------------------------------


def _mock_litellm(content: str) -> MagicMock:
    fake_litellm = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    fake_litellm.completion.return_value = response
    return fake_litellm


def _make_doc(content: str, title: str = "Untitled") -> MagicMock:
    doc = MagicMock()
    doc.content = content
    doc.title = title
    return doc


def test_extract_llm_parses_entities_and_relationships():
    fake_litellm = _mock_litellm(
        '{"entities": [{"name": "Alice", "type": "person"}, {"name": "payments-api", "type": "repo"}], '
        '"relationships": [{"source": "Alice", "relation_type": "authored", "target": "payments-api"}]}'
    )
    doc = _make_doc("Alice authored the payments-api service.")

    with pytest.MonkeyPatch().context() as mp:
        mp.setitem(sys.modules, "litellm", fake_litellm)
        entities, relationships = _extract_entities_and_relationships_llm(doc, "test-model")

    assert {e["canonical_name"] for e in entities} == {"Alice", "payments-api"}
    assert {e["entity_type"] for e in entities} == {"person", "repo"}
    assert relationships == [{"source": "Alice", "relation_type": "authored", "target": "payments-api"}]


def test_extract_llm_strips_markdown_code_fences():
    fake_litellm = _mock_litellm('```json\n{"entities": [], "relationships": []}\n```')
    doc = _make_doc("nothing interesting here")

    with pytest.MonkeyPatch().context() as mp:
        mp.setitem(sys.modules, "litellm", fake_litellm)
        entities, relationships = _extract_entities_and_relationships_llm(doc, "test-model")

    assert entities == []
    assert relationships == []


def test_extract_llm_drops_invalid_entity_and_relation_types():
    fake_litellm = _mock_litellm(
        '{"entities": [{"name": "Alice", "type": "person"}, {"name": "Weird", "type": "not_a_real_type"}], '
        '"relationships": [{"source": "Alice", "relation_type": "not_a_real_relation", "target": "Weird"}]}'
    )
    doc = _make_doc("some content")

    with pytest.MonkeyPatch().context() as mp:
        mp.setitem(sys.modules, "litellm", fake_litellm)
        entities, relationships = _extract_entities_and_relationships_llm(doc, "test-model")

    assert [e["canonical_name"] for e in entities] == ["Alice"]
    assert relationships == []


def test_extract_llm_empty_response_returns_empty_lists():
    fake_litellm = _mock_litellm("{}")
    doc = _make_doc("some content")

    with pytest.MonkeyPatch().context() as mp:
        mp.setitem(sys.modules, "litellm", fake_litellm)
        entities, relationships = _extract_entities_and_relationships_llm(doc, "test-model")

    assert entities == []
    assert relationships == []
