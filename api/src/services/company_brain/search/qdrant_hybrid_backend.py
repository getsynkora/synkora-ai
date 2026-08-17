"""
Qdrant hybrid search backend (dense + sparse vectors, RRF fusion).

Requires qdrant-client >= 1.7 (sparse vector support).
Connection reuses VectorDBConfig (QDRANT_URL, QDRANT_API_KEY).

Collection naming:
  cb_{tenant_id}_hot    — last COMPANY_BRAIN_HOT_DAYS days
  cb_{tenant_id}_warm   — older up to COMPANY_BRAIN_WARM_DAYS days

Both collections use the same schema: one dense + one sparse named vector.
The "query" API runs both in parallel and fuses with built-in RRF.
"""

import logging
import time
import uuid
from typing import Any

from src.config.settings import get_settings

from .base import BaseSearchBackend, SearchFilter, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

_DENSE_VECTOR_NAME = "dense"
_SPARSE_VECTOR_NAME = "sparse"
_PAYLOAD_FIELDS = [
    "doc_id",
    "external_id",
    "source_type",
    "title",
    "content",
    "metadata",
    "source_url",
    "occurred_at",
    "storage_tier",
]


def _point_id(doc_id: str) -> str:
    """Derive a valid Qdrant point ID from an arbitrary business doc_id.

    Qdrant point IDs must be an unsigned integer or a UUID — arbitrary strings
    (e.g. Slack message-derived doc_ids like "C0B0ENY8UNQ_1786959431.976139_0")
    are rejected with 400 Bad Request. Using uuid5 keeps the mapping
    deterministic (same doc_id always upserts to the same point instead of
    duplicating) while the original doc_id remains stored in the payload.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, doc_id))


def _collection_name(tenant_id: str, knowledge_base_id: str, tier: str) -> str:
    """Deterministic, tenant+KB-scoped collection name."""
    safe_tid = str(tenant_id).replace("-", "")[:32]
    return f"cb_{safe_tid}_{knowledge_base_id}_{tier}"


class QdrantHybridBackend(BaseSearchBackend):
    """
    Qdrant backend: dense (semantic) + sparse (BM25-equivalent) with RRF.

    Config (all from env / VectorDBConfig):
      QDRANT_URL      — e.g. http://localhost:6333
      QDRANT_API_KEY  — optional
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import AsyncQdrantClient

            settings = get_settings()
            url = self._config.get("url") or settings.qdrant_url or "http://localhost:6333"
            api_key = self._config.get("api_key") or settings.qdrant_api_key
            self._client = AsyncQdrantClient(url=url, api_key=api_key)
        except Exception as exc:
            logger.error("Failed to initialise Qdrant client: %s", exc)
            raise
        return self._client

    async def _ensure_collection(
        self, tenant_id: str, knowledge_base_id: str, tier: str, dense_dim: int = 1536
    ) -> None:
        """Create collection if it does not exist (idempotent)."""
        from qdrant_client.models import (
            Distance,
            SparseIndexParams,
            SparseVectorParams,
            VectorParams,
        )

        client = self._get_client()
        name = _collection_name(tenant_id, knowledge_base_id, tier)
        try:
            await client.get_collection(name)
        except Exception:
            # NOTE: qdrant_client.models.VectorsConfig is a `typing.Union[VectorParams,
            # Dict[str, VectorParams]]` type alias, not a constructible class — pass
            # a plain dict for named vectors instead.
            await client.create_collection(
                collection_name=name,
                vectors_config={
                    _DENSE_VECTOR_NAME: VectorParams(size=dense_dim, distance=Distance.COSINE),
                },
                sparse_vectors_config={
                    _SPARSE_VECTOR_NAME: SparseVectorParams(index=SparseIndexParams(on_disk=False)),
                },
            )
            logger.info("Created Qdrant collection: %s", name)

    def _build_filter(self, tenant_id: str, filters: SearchFilter | None) -> Any | None:
        """Convert SearchFilter to a Qdrant Filter object."""
        if not filters:
            return None
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, Range

            must: list[Any] = [FieldCondition(key="metadata.tenant_id", match=MatchValue(value=tenant_id))]

            if filters.source_types:
                must.append(FieldCondition(key="source_type", match=MatchAny(any=filters.source_types)))
            if filters.channels:
                must.append(FieldCondition(key="metadata.channel", match=MatchAny(any=filters.channels)))
            if filters.authors:
                must.append(FieldCondition(key="metadata.author", match=MatchAny(any=filters.authors)))
            if filters.time_from or filters.time_to:
                range_kw: dict[str, Any] = {}
                if filters.time_from:
                    range_kw["gte"] = filters.time_from
                if filters.time_to:
                    range_kw["lte"] = filters.time_to
                must.append(FieldCondition(key="occurred_at", range=Range(**range_kw)))

            return Filter(must=must) if must else None
        except Exception as exc:
            logger.warning("Failed to build Qdrant filter: %s", exc)
            return None

    def _collections_for_tiers(self, tenant_id: str, knowledge_base_id: str, tiers: list[str]) -> list[str]:
        return [_collection_name(tenant_id, knowledge_base_id, t) for t in tiers if t != "archive"]

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
        collections = self._collections_for_tiers(tenant_id, knowledge_base_id, tiers)
        qdrant_filter = self._build_filter(tenant_id, filters)

        all_results: list[SearchResult] = []

        for collection in collections:
            try:
                results = await self._search_collection(
                    collection,
                    query_vector=query_vector,
                    qdrant_filter=qdrant_filter,
                    limit=limit,
                )
                all_results.extend(results)
            except Exception as exc:
                logger.warning("Qdrant search failed for collection %s: %s", collection, exc)

        # Sort by score descending, apply limit
        all_results.sort(key=lambda r: r.score, reverse=True)
        all_results = all_results[:limit]

        return SearchResponse(
            results=all_results,
            total_found=len(all_results),
            took_ms=(time.monotonic() - start) * 1000,
            backend_used="qdrant_hybrid",
        )

    async def _search_collection(
        self,
        collection: str,
        query_vector: list[float] | None,
        qdrant_filter: Any | None,
        limit: int,
    ) -> list[SearchResult]:
        """Run dense-only search. Requires a precomputed embedding — this collection has no
        server-side inference model configured, so Qdrant rejects raw query text with a 400
        (confirmed: "Expected some form of vector, id, or a type of query").
        For full hybrid (dense + sparse), callers should use search_with_vectors()."""

        if query_vector is None:
            logger.warning("Qdrant search for %s called without a query_vector; skipping", collection)
            return []

        client = self._get_client()

        response = await client.query_points(
            collection_name=collection,
            query=query_vector,
            using=_DENSE_VECTOR_NAME,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True,
        )

        return [self._point_to_result(p) for p in response.points]

    async def search_with_vectors(
        self,
        tenant_id: str,
        knowledge_base_id: str,
        dense_vector: list[float],
        sparse_indices: list[int] | None,
        sparse_values: list[float] | None,
        filters: SearchFilter | None = None,
        limit: int = 20,
    ) -> SearchResponse:
        """
        Full hybrid search: dense + sparse with Qdrant's built-in RRF fusion.
        Call this from the retriever when you have pre-computed embeddings.
        """
        from qdrant_client.models import Prefetch, Query, SparseVector

        start = time.monotonic()
        tiers = (filters.storage_tiers if filters else None) or ["hot"]
        collections = self._collections_for_tiers(tenant_id, knowledge_base_id, tiers)
        qdrant_filter = self._build_filter(tenant_id, filters)
        client = self._get_client()
        all_results: list[SearchResult] = []

        for collection in collections:
            try:
                prefetch = [Prefetch(query=dense_vector, using=_DENSE_VECTOR_NAME, limit=limit * 2)]
                if sparse_indices and sparse_values:
                    prefetch.append(
                        Prefetch(
                            query=SparseVector(indices=sparse_indices, values=sparse_values),
                            using=_SPARSE_VECTOR_NAME,
                            limit=limit * 2,
                        )
                    )
                response = await client.query_points(
                    collection_name=collection,
                    prefetch=prefetch,
                    query=Query(fusion="rrf"),
                    query_filter=qdrant_filter,
                    limit=limit,
                    with_payload=True,
                )
                all_results.extend([self._point_to_result(p) for p in response.points])
            except Exception as exc:
                logger.warning("Qdrant hybrid search failed for %s: %s", collection, exc)

        all_results.sort(key=lambda r: r.score, reverse=True)
        return SearchResponse(
            results=all_results[:limit],
            total_found=len(all_results),
            took_ms=(time.monotonic() - start) * 1000,
            backend_used="qdrant_hybrid",
        )

    def _point_to_result(self, point: Any) -> SearchResult:
        p = point.payload or {}
        meta = p.get("metadata") or {}
        return SearchResult(
            doc_id=str(p.get("doc_id", point.id)),
            external_id=str(p.get("external_id", "")),
            source_type=p.get("source_type", "unknown"),
            content=p.get("content", ""),
            title=p.get("title"),
            score=float(getattr(point, "score", 0.0)),
            vector_score=None,
            keyword_score=None,
            metadata=meta,
            source_url=p.get("source_url"),
            occurred_at=p.get("occurred_at"),
            storage_tier=p.get("storage_tier", "hot"),
        )

    async def index_documents(
        self, tenant_id: str, knowledge_base_id: str, documents: list[dict[str, Any]]
    ) -> dict[str, int]:
        from qdrant_client.models import PointStruct, SparseVector

        client = self._get_client()
        indexed = 0
        failed = 0

        # Group by tier
        by_tier: dict[str, list[dict]] = {}
        for doc in documents:
            tier = doc.get("storage_tier", "hot")
            by_tier.setdefault(tier, []).append(doc)

        for tier, tier_docs in by_tier.items():
            if tier == "archive":
                continue  # archive goes to S3, not Qdrant

            dense_dim = len(tier_docs[0].get("embedding") or []) or 1536
            await self._ensure_collection(tenant_id, knowledge_base_id, tier, dense_dim)
            collection = _collection_name(tenant_id, knowledge_base_id, tier)

            points: list[PointStruct] = []
            for doc in tier_docs:
                emb = doc.get("embedding")
                if not emb:
                    failed += 1
                    continue

                vectors: dict[str, Any] = {_DENSE_VECTOR_NAME: emb}
                sp_idx = doc.get("sparse_indices")
                sp_val = doc.get("sparse_values")
                if sp_idx and sp_val:
                    vectors[_SPARSE_VECTOR_NAME] = SparseVector(indices=sp_idx, values=sp_val)

                payload = {
                    "doc_id": doc["doc_id"],
                    "external_id": doc.get("external_id", ""),
                    "source_type": doc.get("source_type", ""),
                    "title": doc.get("title"),
                    "content": doc.get("content", ""),
                    "metadata": {**(doc.get("metadata") or {}), "tenant_id": tenant_id},
                    "source_url": doc.get("source_url"),
                    "occurred_at": doc.get("occurred_at"),
                    "storage_tier": tier,
                }
                points.append(PointStruct(id=_point_id(doc["doc_id"]), vector=vectors, payload=payload))

            if points:
                try:
                    await client.upsert(collection_name=collection, points=points)
                    indexed += len(points)
                except Exception as exc:
                    logger.error("Qdrant upsert failed for %s: %s", collection, exc)
                    failed += len(points)

        return {"indexed": indexed, "failed": failed}

    async def delete_documents(self, tenant_id: str, knowledge_base_id: str, doc_ids: list[str]) -> int:
        from qdrant_client.models import PointIdsList

        client = self._get_client()
        deleted = 0
        for tier in ["hot", "warm"]:
            collection = _collection_name(tenant_id, knowledge_base_id, tier)
            try:
                point_ids = [_point_id(d) for d in doc_ids]
                await client.delete(collection_name=collection, points_selector=PointIdsList(points=point_ids))
                deleted += len(doc_ids)
            except Exception:
                pass
        return deleted

    async def update_tier(self, tenant_id: str, knowledge_base_id: str, doc_ids: list[str], new_tier: str) -> int:
        # Qdrant doesn't support moving between collections natively.
        # Retrieve from old tier, re-insert into new tier collection, delete from old.
        # For now, just update the payload field (simpler, avoids re-embedding).

        client = self._get_client()
        updated = 0
        for tier in ["hot", "warm"]:
            if tier == new_tier:
                continue
            collection = _collection_name(tenant_id, knowledge_base_id, tier)
            try:
                await client.set_payload(
                    collection_name=collection,
                    payload={"storage_tier": new_tier},
                    points=[_point_id(d) for d in doc_ids],
                )
                updated += len(doc_ids)
            except Exception:
                pass
        return updated

    async def health_check(self) -> dict[str, Any]:
        try:
            client = self._get_client()
            info = await client.get_collections()
            return {"status": "ok", "collections": len(info.collections)}
        except Exception as exc:
            return {"status": "down", "error": str(exc)}
