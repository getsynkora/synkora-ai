"""
Abstract search backend for Company Brain.

All search providers implement BaseSearchBackend so the rest of the system
is decoupled from the underlying engine.  Swap backends by changing one env
var (COMPANY_BRAIN_SEARCH_BACKEND) — no code changes required.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SearchBackendType(StrEnum):
    QDRANT_HYBRID = "qdrant_hybrid"  # Dense + sparse vectors, RRF fusion (recommended)
    POSTGRES_FTS = "postgres_fts"  # PG tsvector + GIN index, zero extra infra
    ELASTICSEARCH = "elasticsearch"  # ES / OpenSearch kNN + BM25
    TYPESENSE = "typesense"  # Lightweight alternative (future)


@dataclass
class SearchFilter:
    """
    Generic pre-filter applied before the vector/keyword search.

    Each backend translates this into its own query language (Qdrant filter,
    WHERE clause, ES bool-filter, etc.).  Add fields here as needed — backends
    ignore fields they don't support via the `extra` passthrough dict.
    """

    source_types: list[str] = field(default_factory=list)  # e.g. ["slack", "github"]
    time_from: str | None = None  # ISO-8601 datetime string
    time_to: str | None = None
    entity_ids: list[str] = field(default_factory=list)  # canonical entity PKs (str)
    channels: list[str] = field(default_factory=list)  # Slack channels, Jira projects
    authors: list[str] = field(default_factory=list)  # email or display name
    storage_tiers: list[str] = field(default_factory=lambda: ["hot"])  # hot | warm | archive
    extra: dict[str, Any] = field(default_factory=dict)  # backend-specific passthrough


@dataclass
class SearchResult:
    """
    Unified search result — same shape regardless of backend.

    Scores are normalised to [0, 1] by each backend so callers can compare
    results across different engines and apply RRF fusion in the assembler.
    """

    doc_id: str  # Internal PK (data_source_documents.id as str)
    external_id: str  # Source-system ID (Slack ts, GitHub issue number, …)
    source_type: str  # "slack" | "github" | "jira" | …
    content: str  # The indexed text chunk
    title: str | None  # Message subject, PR title, ticket summary, …
    score: float  # Final combined score [0, 1]
    vector_score: float | None
    keyword_score: float | None
    metadata: dict[str, Any]  # Source-specific metadata (channel, author, url, …)
    source_url: str | None
    occurred_at: str | None  # ISO-8601 datetime from the source system
    storage_tier: str = "hot"


@dataclass
class SearchResponse:
    """Unified search response returned by every backend."""

    results: list[SearchResult]
    total_found: int  # Total matches before limit (best-effort for vector backends)
    took_ms: float
    backend_used: str  # Which backend produced this response
    cache_hit: bool = False


class BaseSearchBackend(ABC):
    """
    Abstract base class every Company Brain search backend must implement.

    Implementations live next to this file:
      qdrant_hybrid_backend.py
      postgres_fts_backend.py
      elasticsearch_backend.py
    """

    @abstractmethod
    async def search(
        self,
        tenant_id: str,
        knowledge_base_id: str,
        query: str,
        filters: SearchFilter | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> SearchResponse:
        """
        Run a hybrid search and return ranked results.

        Args:
            tenant_id:         Scopes the search to one tenant — never crosses tenants.
            knowledge_base_id: Scopes the search to one knowledge base within the tenant.
            query:             Natural-language query string.
            filters:           Optional metadata pre-filter applied before scoring.
            limit:             Max results to return.
            offset:            Pagination offset.

        Returns:
            SearchResponse with results sorted by descending score.
        """

    @abstractmethod
    async def index_documents(
        self,
        tenant_id: str,
        knowledge_base_id: str,
        documents: list[dict[str, Any]],
    ) -> dict[str, int]:
        """
        Index (upsert) a batch of documents.

        Each document dict must contain at minimum:
            {
              "doc_id": str,
              "external_id": str,
              "source_type": str,
              "content": str,
              "embedding": list[float],   # dense vector
              "sparse": dict,             # {"indices": [...], "values": [...]} or None
              "metadata": dict,
              "storage_tier": str,        # "hot" | "warm" | "archive"
            }

        Returns:
            {"indexed": int, "failed": int}
        """

    @abstractmethod
    async def delete_documents(
        self,
        tenant_id: str,
        knowledge_base_id: str,
        doc_ids: list[str],
    ) -> int:
        """Delete documents by internal doc_id. Returns count deleted."""

    @abstractmethod
    async def update_tier(
        self,
        tenant_id: str,
        knowledge_base_id: str,
        doc_ids: list[str],
        new_tier: str,
    ) -> int:
        """
        Move documents to a different storage tier (hot → warm → archive).
        Returns count updated.
        """

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Return {"status": "ok"|"degraded"|"down", ...details}."""
