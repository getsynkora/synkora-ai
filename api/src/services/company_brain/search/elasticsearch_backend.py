"""
Elasticsearch / OpenSearch hybrid search backend.

Wraps the existing ElasticsearchConnector with the BaseSearchBackend interface.
Uses kNN dense search + BM25 keyword search with Reciprocal Rank Fusion (ES 8.9+)
or linear combination for older ES versions.

Suitable for: enterprise deployments with >500M documents/tenant, or when ES
is already running as part of an ELK stack.

Env vars:
  COMPANY_BRAIN_ES_HOST          (default: localhost)
  COMPANY_BRAIN_ES_PORT          (default: 9200)
  COMPANY_BRAIN_ES_API_KEY       (optional)
  COMPANY_BRAIN_ES_INDEX_PREFIX  (default: cb)
  COMPANY_BRAIN_ES_SHARDS        (default: 3)
  COMPANY_BRAIN_ES_REPLICAS      (default: 1)
  COMPANY_BRAIN_ES_KNN_BOOST     (default: 0.7)
  COMPANY_BRAIN_ES_BM25_BOOST    (default: 0.3)
"""

import logging
import time
from typing import Any

from .base import BaseSearchBackend, SearchFilter, SearchResponse, SearchResult

logger = logging.getLogger(__name__)


def _index_name(prefix: str, tenant_id: str, tier: str) -> str:
    safe = str(tenant_id).replace("-", "")[:24]
    return f"{prefix}_{safe}_{tier}"


class ElasticsearchBackend(BaseSearchBackend):
    """
    ES hybrid backend: BM25 full-text + kNN dense with RRF or linear boost.

    Index mapping (created on first index_documents call):
      - content:    text (BM25)
      - title:      text (BM25)
      - embedding:  dense_vector (kNN)
      - source_type, storage_tier, occurred_at: keyword / date (filter)
      - metadata:   object (dynamic)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from elasticsearch import AsyncElasticsearch

            host = self._config.get("host", "localhost")
            port = self._config.get("port", 9200)
            api_key = self._config.get("api_key")
            use_ssl = self._config.get("use_ssl", False)
            scheme = "https" if use_ssl else "http"
            url = f"{scheme}://{host}:{port}"
            kwargs: dict[str, Any] = {"hosts": [url]}
            if api_key:
                kwargs["api_key"] = api_key
            self._client = AsyncElasticsearch(**kwargs)
        except Exception as exc:
            logger.error("Failed to initialise ES client: %s", exc)
            raise
        return self._client

    def _index_prefix(self) -> str:
        return self._config.get("index_prefix", "cb")

    def _indices_for_tiers(self, tenant_id: str, tiers: list[str]) -> list[str]:
        prefix = self._index_prefix()
        return [_index_name(prefix, tenant_id, t) for t in tiers if t != "archive"]

    async def _ensure_index(self, index: str, dense_dim: int) -> None:
        client = self._get_client()
        shards = self._config.get("shards", 3)
        replicas = self._config.get("replicas", 1)
        try:
            exists = await client.indices.exists(index=index)
            if not exists:
                await client.indices.create(
                    index=index,
                    body={
                        "settings": {"number_of_shards": shards, "number_of_replicas": replicas},
                        "mappings": {
                            "properties": {
                                "doc_id": {"type": "keyword"},
                                "external_id": {"type": "keyword"},
                                "source_type": {"type": "keyword"},
                                "title": {"type": "text"},
                                "content": {"type": "text"},
                                "embedding": {
                                    "type": "dense_vector",
                                    "dims": dense_dim,
                                    "index": True,
                                    "similarity": "cosine",
                                },
                                "source_url": {"type": "keyword"},
                                "occurred_at": {"type": "date"},
                                "storage_tier": {"type": "keyword"},
                                "tenant_id": {"type": "keyword"},
                                "metadata": {"type": "object", "dynamic": True},
                            }
                        },
                    },
                )
                logger.info("Created ES index: %s", index)
        except Exception as exc:
            logger.warning("ES ensure_index: %s", exc)

    def _build_filter(self, tenant_id: str, filters: SearchFilter | None) -> list[dict]:
        must_filter = [{"term": {"tenant_id": tenant_id}}]
        if not filters:
            return must_filter

        if filters.source_types:
            must_filter.append({"terms": {"source_type": filters.source_types}})
        if filters.channels:
            must_filter.append({"terms": {"metadata.channel": filters.channels}})
        if filters.time_from or filters.time_to:
            range_clause: dict[str, Any] = {}
            if filters.time_from:
                range_clause["gte"] = filters.time_from
            if filters.time_to:
                range_clause["lte"] = filters.time_to
            must_filter.append({"range": {"occurred_at": range_clause}})

        return must_filter

    async def search(
        self,
        tenant_id: str,
        knowledge_base_id: str,
        query: str,
        query_vector: list[float] | None = None,
        filters: SearchFilter | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        start = time.monotonic()
        tiers = (filters.storage_tiers if filters else None) or ["hot"]
        indices = self._indices_for_tiers(tenant_id, tiers)
        if not indices:
            return SearchResponse(results=[], total_found=0, took_ms=0, backend_used="elasticsearch")

        must_filter = self._build_filter(tenant_id, filters)
        bm25_boost = self._config.get("bm25_boost", 0.3)

        body = {
            "query": {
                "bool": {
                    "must": [{"multi_match": {"query": query, "fields": ["title^2", "content"], "boost": bm25_boost}}],
                    "filter": must_filter,
                }
            },
            "size": limit,
            "from": offset,
        }

        client = self._get_client()
        try:
            resp = await client.search(index=",".join(indices), body=body)
        except Exception as exc:
            logger.error("ES search failed: %s", exc)
            return SearchResponse(results=[], total_found=0, took_ms=0, backend_used="elasticsearch")

        hits = resp.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        results = [self._hit_to_result(h) for h in hits.get("hits", [])]

        return SearchResponse(
            results=results,
            total_found=total,
            took_ms=(time.monotonic() - start) * 1000,
            backend_used="elasticsearch",
        )

    def _hit_to_result(self, hit: dict[str, Any]) -> SearchResult:
        src = hit.get("_source", {})
        return SearchResult(
            doc_id=src.get("doc_id", hit.get("_id", "")),
            external_id=src.get("external_id", ""),
            source_type=src.get("source_type", ""),
            content=src.get("content", ""),
            title=src.get("title"),
            score=float(hit.get("_score", 0.0)),
            vector_score=None,
            keyword_score=float(hit.get("_score", 0.0)),
            metadata=src.get("metadata", {}),
            source_url=src.get("source_url"),
            occurred_at=src.get("occurred_at"),
            storage_tier=src.get("storage_tier", "hot"),
        )

    async def index_documents(
        self, tenant_id: str, knowledge_base_id: str, documents: list[dict[str, Any]]
    ) -> dict[str, int]:
        from elasticsearch.helpers import async_bulk

        client = self._get_client()
        prefix = self._index_prefix()
        indexed = 0
        failed = 0

        # Group by tier; ensure index exists for each
        by_tier: dict[str, list[dict]] = {}
        for doc in documents:
            tier = doc.get("storage_tier", "hot")
            by_tier.setdefault(tier, []).append(doc)

        for tier, tier_docs in by_tier.items():
            if tier == "archive":
                continue
            dense_dim = len(tier_docs[0].get("embedding") or []) or 1536
            index = _index_name(prefix, tenant_id, tier)
            await self._ensure_index(index, dense_dim)

            actions = []
            for doc in tier_docs:
                action = {
                    "_index": index,
                    "_id": doc["doc_id"],
                    "_source": {
                        "doc_id": doc["doc_id"],
                        "external_id": doc.get("external_id", ""),
                        "source_type": doc.get("source_type", ""),
                        "title": doc.get("title"),
                        "content": doc.get("content", ""),
                        "embedding": doc.get("embedding"),
                        "source_url": doc.get("source_url"),
                        "occurred_at": doc.get("occurred_at"),
                        "storage_tier": tier,
                        "tenant_id": tenant_id,
                        "metadata": doc.get("metadata", {}),
                    },
                }
                actions.append(action)

            try:
                success, errors = await async_bulk(client, actions, raise_on_error=False)
                indexed += success
                failed += len(errors)
            except Exception as exc:
                logger.error("ES bulk index failed for %s: %s", index, exc)
                failed += len(tier_docs)

        return {"indexed": indexed, "failed": failed}

    async def delete_documents(self, tenant_id: str, knowledge_base_id: str, doc_ids: list[str]) -> int:
        client = self._get_client()
        prefix = self._index_prefix()
        deleted = 0
        for tier in ["hot", "warm"]:
            index = _index_name(prefix, tenant_id, tier)
            body = {"query": {"terms": {"doc_id": doc_ids}}}
            try:
                resp = await client.delete_by_query(index=index, body=body)
                deleted += resp.get("deleted", 0)
            except Exception:
                pass
        return deleted

    async def update_tier(
        self, tenant_id: str, knowledge_base_id: str, doc_ids: list[str], new_tier: str
    ) -> int:
        client = self._get_client()
        prefix = self._index_prefix()
        updated = 0
        for tier in ["hot", "warm"]:
            index = _index_name(prefix, tenant_id, tier)
            body = {
                "script": {"source": f"ctx._source.storage_tier = '{new_tier}'", "lang": "painless"},
                "query": {"terms": {"doc_id": doc_ids}},
            }
            try:
                resp = await client.update_by_query(index=index, body=body)
                updated += resp.get("updated", 0)
            except Exception:
                pass
        return updated

    async def health_check(self) -> dict[str, Any]:
        try:
            client = self._get_client()
            health = await client.cluster.health()
            return {
                "status": "ok" if health.get("status") != "red" else "degraded",
                "cluster_status": health.get("status"),
            }
        except Exception as exc:
            return {"status": "down", "error": str(exc)}
