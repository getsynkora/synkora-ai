"""
Unit tests for graph expansion in the Company Brain retriever.

_graph_expand resolves QueryIntent.entities against kb_entities and walks
kb_relationships to surface connected documents — the piece that lets
"who worked on X" style questions use the entity graph instead of falling
through to plain vector similarity.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.company_brain.query.retriever import _graph_expand, _merge_graph_results
from src.services.company_brain.query.router import QueryIntent
from src.services.company_brain.search.base import SearchResult

TENANT_ID = str(uuid.uuid4())


def _search_result(doc_id: str, score: float) -> SearchResult:
    return SearchResult(
        doc_id=doc_id,
        external_id=doc_id,
        source_type="slack",
        content="hello",
        title=None,
        score=score,
        vector_score=score,
        keyword_score=None,
        metadata={},
        source_url=None,
        occurred_at=None,
    )


# ---------------------------------------------------------------------------
# _merge_graph_results — pure logic, no DB
# ---------------------------------------------------------------------------


def test_merge_no_graph_results_returns_vector_results_capped():
    vector = [_search_result("1", 0.9), _search_result("2", 0.5)]
    merged = _merge_graph_results([], vector, limit=1)
    assert merged == vector[:1]


def test_merge_graph_results_take_priority_and_dedupe():
    graph = [_search_result("1", 0.95)]
    vector = [_search_result("1", 0.3), _search_result("2", 0.5)]
    merged = _merge_graph_results(graph, vector, limit=5)

    # doc "1" appears once (the graph version, not the lower-scored vector duplicate)
    assert [r.doc_id for r in merged] == ["1", "2"]
    assert merged[0].score == 0.95


def test_merge_respects_limit():
    graph = [_search_result("1", 0.95), _search_result("2", 0.94)]
    vector = [_search_result("3", 0.5)]
    merged = _merge_graph_results(graph, vector, limit=1)
    assert len(merged) == 1
    assert merged[0].doc_id == "1"


# ---------------------------------------------------------------------------
# _graph_expand — no-op paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_expand_noop_when_no_entities():
    intent = QueryIntent(entities=[])
    result = await _graph_expand(TENANT_ID, intent, db=MagicMock())
    assert result == []


@pytest.mark.asyncio
async def test_graph_expand_noop_when_no_db():
    intent = QueryIntent(entities=["alice"])
    result = await _graph_expand(TENANT_ID, intent, db=None)
    assert result == []


@pytest.mark.asyncio
async def test_graph_expand_noop_on_invalid_tenant_id():
    intent = QueryIntent(entities=["alice"])
    result = await _graph_expand("not-a-uuid", intent, db=MagicMock())
    assert result == []


@pytest.mark.asyncio
async def test_graph_expand_noop_when_no_matching_entities():
    db = MagicMock()
    no_entities_result = MagicMock()
    no_entities_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=no_entities_result)

    intent = QueryIntent(entities=["nobody-by-this-name"])
    result = await _graph_expand(TENANT_ID, intent, db)
    assert result == []


@pytest.mark.asyncio
async def test_graph_expand_noop_when_entity_has_no_relationships():
    from src.models.kb_brain import KBEntity

    entity = MagicMock(spec=KBEntity)
    entity.id = 7

    entities_result = MagicMock()
    entities_result.scalars.return_value.all.return_value = [entity]

    no_rels_result = MagicMock()
    no_rels_result.scalars.return_value.all.return_value = []

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[entities_result, no_rels_result])

    intent = QueryIntent(entities=["Alice"])
    result = await _graph_expand(TENANT_ID, intent, db)
    assert result == []


@pytest.mark.asyncio
async def test_graph_expand_swallows_db_errors():
    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("connection reset"))

    intent = QueryIntent(entities=["Alice"])
    result = await _graph_expand(TENANT_ID, intent, db)
    assert result == []


# ---------------------------------------------------------------------------
# _graph_expand — full path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_expand_resolves_entity_and_returns_connected_document():
    from src.models.data_source import DataSourceDocument, DataSourceType
    from src.models.kb_brain import KBEntity, KBRelationship

    entity = MagicMock(spec=KBEntity)
    entity.id = 7

    relationship = MagicMock(spec=KBRelationship)
    relationship.source_doc_id = 101

    doc = MagicMock(spec=DataSourceDocument)
    doc.id = 101
    doc.external_id = "ext-101"
    doc.content = "Alice authored the payments service."
    doc.title = "PR #99"
    doc.doc_metadata = {"repo": "corp/payments"}
    doc.external_url = "https://github.com/corp/payments/pull/99"
    doc.source_created_at = None
    doc.storage_tier = "hot"

    entities_result = MagicMock()
    entities_result.scalars.return_value.all.return_value = [entity]

    rel_result = MagicMock()
    rel_result.scalars.return_value.all.return_value = [relationship]

    docs_result = MagicMock()
    docs_result.all.return_value = [(doc, DataSourceType.GITHUB)]

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[entities_result, rel_result, docs_result])

    intent = QueryIntent(entities=["Alice"])
    results = await _graph_expand(TENANT_ID, intent, db)

    assert len(results) == 1
    result = results[0]
    assert result.doc_id == "101"
    assert result.source_type == "github"
    assert result.metadata["graph_match"] is True
    assert result.metadata["matched_entities"] == ["Alice"]
    assert result.metadata["repo"] == "corp/payments"
    assert result.score == 0.95


@pytest.mark.asyncio
async def test_graph_expand_noop_when_relationships_have_no_doc_ids():
    """Relationships between two entities with no attached document (source_doc_id=None)
    contribute no retrievable content — must not error, just return no results."""
    from src.models.kb_brain import KBEntity, KBRelationship

    entity = MagicMock(spec=KBEntity)
    entity.id = 7

    relationship = MagicMock(spec=KBRelationship)
    relationship.source_doc_id = None

    entities_result = MagicMock()
    entities_result.scalars.return_value.all.return_value = [entity]

    rel_result = MagicMock()
    rel_result.scalars.return_value.all.return_value = [relationship]

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[entities_result, rel_result])

    intent = QueryIntent(entities=["Alice"])
    result = await _graph_expand(TENANT_ID, intent, db)
    assert result == []
