"""
Eval Dataset Service

CRUD for EvalDataset and EvalCase documents stored in Elasticsearch.
These are the golden test cases used by the on-demand judge runner.
"""

import logging
import uuid
from datetime import UTC, datetime
from uuid import UUID

logger = logging.getLogger(__name__)

_es_client = None


async def _get_es_client():
    global _es_client
    if _es_client is not None:
        return _es_client
    from elasticsearch import AsyncElasticsearch

    from src.config.settings import settings

    _es_client = AsyncElasticsearch(
        [settings.elasticsearch_url],
        basic_auth=(settings.elasticsearch_username, settings.elasticsearch_password),
        verify_certs=False,
        request_timeout=10,
    )
    return _es_client


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Dataset CRUD
# ---------------------------------------------------------------------------


async def create_dataset(*, agent_id: UUID, tenant_id: UUID, name: str, description: str = "") -> dict:
    """Create a new EvalDataset document. Returns the created document."""
    from src.config.settings import settings

    es = await _get_es_client()
    dataset_id = str(uuid.uuid4())
    doc = {
        "dataset_id": dataset_id,
        "agent_id": str(agent_id),
        "tenant_id": str(tenant_id),
        "name": name,
        "description": description,
        "case_count": 0,
        "@timestamp": _now_iso(),
        "doc_type": "dataset",
    }
    await es.index(
        index=settings.agent_eval_datasets_index, id=f"dataset:{dataset_id}", document=doc, refresh="wait_for"
    )
    return doc


async def get_dataset(*, dataset_id: str, tenant_id: UUID) -> dict | None:
    """Get a dataset by ID, verifying tenant ownership."""
    from elasticsearch import NotFoundError

    from src.config.settings import settings

    es = await _get_es_client()
    try:
        result = await es.get(index=settings.agent_eval_datasets_index, id=f"dataset:{dataset_id}")
        doc = result["_source"]
        if doc.get("tenant_id") != str(tenant_id):
            return None
        return doc
    except NotFoundError:
        return None


async def list_datasets(*, agent_id: UUID, tenant_id: UUID) -> list[dict]:
    """List all datasets for an agent."""
    from elasticsearch import NotFoundError

    from src.config.settings import settings

    es = await _get_es_client()
    body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"agent_id.keyword": str(agent_id)}},
                    {"term": {"tenant_id.keyword": str(tenant_id)}},
                    {"term": {"doc_type.keyword": "dataset"}},
                ]
            }
        },
        "size": 100,
        "sort": [{"@timestamp": {"order": "desc"}}],
    }
    try:
        resp = await es.search(index=settings.agent_eval_datasets_index, body=body)
        return [hit["_source"] for hit in resp["hits"]["hits"]]
    except NotFoundError:
        return []


async def update_dataset(
    *, dataset_id: str, tenant_id: UUID, name: str | None = None, description: str | None = None
) -> dict | None:
    """Update dataset name/description. Returns updated doc or None if not found."""
    from src.config.settings import settings

    es = await _get_es_client()
    existing = await get_dataset(dataset_id=dataset_id, tenant_id=tenant_id)
    if not existing:
        return None
    updates: dict = {}
    if name is not None:
        updates["name"] = name
    if description is not None:
        updates["description"] = description
    if updates:
        await es.update(
            index=settings.agent_eval_datasets_index,
            id=f"dataset:{dataset_id}",
            body={"doc": updates},
        )
        existing.update(updates)
    return existing


async def delete_dataset(*, dataset_id: str, tenant_id: UUID) -> bool:
    """Delete a dataset and all its cases. Returns True if deleted."""
    from src.config.settings import settings

    es = await _get_es_client()
    existing = await get_dataset(dataset_id=dataset_id, tenant_id=tenant_id)
    if not existing:
        return False
    # Delete all cases for this dataset (conflicts="proceed" handles already-deleted docs)
    await es.delete_by_query(
        index=settings.agent_eval_datasets_index,
        conflicts="proceed",
        body={
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"dataset_id.keyword": dataset_id}},
                        {"term": {"doc_type.keyword": "case"}},
                    ]
                }
            }
        },
    )
    await es.delete(index=settings.agent_eval_datasets_index, id=f"dataset:{dataset_id}")
    return True


# ---------------------------------------------------------------------------
# Case CRUD
# ---------------------------------------------------------------------------


async def create_case(
    *,
    dataset_id: str,
    agent_id: UUID,
    tenant_id: UUID,
    input: str,
    expected_criteria: str,
    tags: list[str] | None = None,
) -> dict:
    """Create an EvalCase document and increment dataset case_count."""
    from src.config.settings import settings

    es = await _get_es_client()
    case_id = str(uuid.uuid4())
    doc = {
        "case_id": case_id,
        "dataset_id": dataset_id,
        "agent_id": str(agent_id),
        "tenant_id": str(tenant_id),
        "input": input,
        "expected_criteria": expected_criteria,
        "tags": tags or [],
        "@timestamp": _now_iso(),
        "doc_type": "case",
    }
    await es.index(index=settings.agent_eval_datasets_index, id=f"case:{case_id}", document=doc, refresh="wait_for")
    try:
        await es.update(
            index=settings.agent_eval_datasets_index,
            id=f"dataset:{dataset_id}",
            body={"script": {"source": "ctx._source.case_count += 1", "lang": "painless"}},
        )
    except Exception as e:
        logger.warning("Failed to increment case_count: %s", e)
    return doc


async def list_cases(*, dataset_id: str, tenant_id: UUID) -> list[dict]:
    """List all cases for a dataset."""
    from elasticsearch import NotFoundError

    from src.config.settings import settings

    es = await _get_es_client()
    body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"dataset_id.keyword": dataset_id}},
                    {"term": {"tenant_id.keyword": str(tenant_id)}},
                    {"term": {"doc_type.keyword": "case"}},
                ]
            }
        },
        "size": 500,
        "sort": [{"@timestamp": {"order": "asc"}}],
    }
    try:
        resp = await es.search(index=settings.agent_eval_datasets_index, body=body)
        return [hit["_source"] for hit in resp["hits"]["hits"]]
    except NotFoundError:
        return []


async def delete_case(*, case_id: str, tenant_id: UUID) -> bool:
    """Delete a single case and decrement dataset case_count. Returns True if deleted."""
    from elasticsearch import NotFoundError

    from src.config.settings import settings

    es = await _get_es_client()
    try:
        result = await es.get(index=settings.agent_eval_datasets_index, id=f"case:{case_id}")
        doc = result["_source"]
        if doc.get("tenant_id") != str(tenant_id):
            return False
        await es.delete(index=settings.agent_eval_datasets_index, id=f"case:{case_id}")
        try:
            await es.update(
                index=settings.agent_eval_datasets_index,
                id=f"dataset:{doc['dataset_id']}",
                body={
                    "script": {
                        "source": "if (ctx._source.case_count > 0) { ctx._source.case_count -= 1 }",
                        "lang": "painless",
                    }
                },
            )
        except Exception as e:
            logger.warning("Failed to decrement case_count: %s", e)
        return True
    except NotFoundError:
        return False
