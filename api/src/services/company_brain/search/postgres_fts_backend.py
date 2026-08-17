"""
PostgreSQL full-text search backend.

Zero extra infrastructure — uses the existing PostgreSQL instance with
GIN-indexed tsvector columns on data_source_documents.

Suitable for: deployments with <20M documents per tenant, or when running
without a dedicated vector database.

Env vars (all optional, defaults shown):
  COMPANY_BRAIN_FTS_LANGUAGE=english
  DATABASE_URL                         (already required by the app)
"""

import logging
import time
from typing import Any

from .base import BaseSearchBackend, SearchFilter, SearchResponse, SearchResult

logger = logging.getLogger(__name__)

_DEFAULT_LANG = "english"


class PostgresFTSBackend(BaseSearchBackend):
    """
    Full-text search via PostgreSQL ts_rank_cd + GIN tsvector index.

    The GIN index on data_source_documents.search_vector (a tsvector column
    added by migration 20260413_0002) makes queries fast at tens of millions
    of rows.  ts_rank_cd provides BM25-like scoring with cover density.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._lang = self._config.get("language", _DEFAULT_LANG)

    def _get_session(self) -> Any:
        from src.core.database import SessionLocal

        return SessionLocal()

    def _build_where(self, tenant_id: str, filters: SearchFilter | None) -> tuple[str, list[Any]]:
        """Build a parameterised WHERE clause from the filter."""
        clauses = ["dsd.tenant_id = $1"]
        params: list[Any] = [tenant_id]
        idx = 2

        if filters:
            if filters.source_types:
                placeholders = ", ".join(f"${i}" for i in range(idx, idx + len(filters.source_types)))
                clauses.append(f"ds.type IN ({placeholders})")
                params.extend(filters.source_types)
                idx += len(filters.source_types)

            if filters.time_from:
                clauses.append(f"dsd.source_created_at >= ${idx}")
                params.append(filters.time_from)
                idx += 1

            if filters.time_to:
                clauses.append(f"dsd.source_created_at <= ${idx}")
                params.append(filters.time_to)
                idx += 1

        return " AND ".join(clauses), params

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
        where, params = self._build_where(tenant_id, filters)
        params_with_query = [query] + params

        # Renumber WHERE params because $1 is now the query
        renumbered_where = where
        for i in range(len(params), 0, -1):
            renumbered_where = renumbered_where.replace(f"${i}", f"${i + 1}")

        sql = f"""
            SELECT
                dsd.id::text                                 AS doc_id,
                dsd.external_id,
                ds.type::text                                AS source_type,
                dsd.content,
                dsd.title,
                ts_rank_cd(dsd.search_vector,
                           plainto_tsquery('{self._lang}', $1)) AS score,
                dsd.doc_metadata,
                dsd.external_url,
                dsd.source_created_at::text                  AS occurred_at
            FROM data_source_documents dsd
            JOIN data_sources ds ON ds.id = dsd.data_source_id
            WHERE {renumbered_where}
              AND dsd.search_vector @@ plainto_tsquery('{self._lang}', $1)
            ORDER BY score DESC
            LIMIT {limit}
            OFFSET {offset}
        """

        try:
            import asyncpg

            from src.config.settings import get_settings

            settings = get_settings()
            conn = await asyncpg.connect(settings.database_url)
            try:
                rows = await conn.fetch(sql, *params_with_query)
            finally:
                await conn.close()
        except Exception as exc:
            logger.error("PostgresFTS search failed: %s", exc)
            return SearchResponse(results=[], total_found=0, took_ms=0, backend_used="postgres_fts")

        results = [
            SearchResult(
                doc_id=row["doc_id"],
                external_id=row["external_id"] or "",
                source_type=row["source_type"],
                content=row["content"] or "",
                title=row["title"],
                score=float(row["score"]),
                vector_score=None,
                keyword_score=float(row["score"]),
                metadata=dict(row["doc_metadata"] or {}),
                source_url=row["external_url"],
                occurred_at=row["occurred_at"],
            )
            for row in rows
        ]

        return SearchResponse(
            results=results,
            total_found=len(results),
            took_ms=(time.monotonic() - start) * 1000,
            backend_used="postgres_fts",
        )

    async def index_documents(
        self, tenant_id: str, knowledge_base_id: str, documents: list[dict[str, Any]]
    ) -> dict[str, int]:
        """
        PostgresFTS backend does not maintain a separate index.
        The tsvector column on data_source_documents is updated automatically
        by the database trigger installed in migration 20260413_0002.
        """
        return {"indexed": len(documents), "failed": 0}

    async def delete_documents(self, tenant_id: str, knowledge_base_id: str, doc_ids: list[str]) -> int:
        # Documents are deleted from data_source_documents by the caller; no separate index.
        return len(doc_ids)

    async def update_tier(
        self, tenant_id: str, knowledge_base_id: str, doc_ids: list[str], new_tier: str
    ) -> int:
        # Tier is stored in the data_source_documents row; update done by caller.
        return len(doc_ids)

    async def health_check(self) -> dict[str, Any]:
        try:
            import asyncpg

            from src.config.settings import get_settings

            settings = get_settings()
            conn = await asyncpg.connect(settings.database_url)
            await conn.fetchval("SELECT 1")
            await conn.close()
            return {"status": "ok", "backend": "postgres_fts"}
        except Exception as exc:
            return {"status": "down", "error": str(exc)}
