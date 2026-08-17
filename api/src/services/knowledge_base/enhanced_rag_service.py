"""
Enhanced Production-Grade RAG Service.

Implements best-in-class retrieval with:
- Query Enhancement: LLM-based query expansion and reformulation
- Hybrid Search: Vector similarity + keyword matching
- Reranking: Cross-encoder reranking for better relevance
- Caching: Embedding and result caching for performance
- Multi-KB Aggregation: Intelligent result fusion from multiple knowledge bases
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.models.knowledge_base import IngestionMode
from src.services.company_brain.search.factory import get_search_backend

logger = logging.getLogger(__name__)


class RetrievalStrategy(StrEnum):
    """RAG retrieval strategies."""

    VECTOR_ONLY = "vector_only"  # Standard vector search
    HYBRID = "hybrid"  # Vector + keyword
    HYBRID_RERANK = "hybrid_rerank"  # Hybrid + reranking (recommended)
    ADVANCED = "advanced"  # Full pipeline with query enhancement


@dataclass
class RAGConfig:
    """Configuration for enhanced RAG."""

    # Retrieval strategy
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID_RERANK

    # Vector search settings
    vector_top_k: int = 20  # Retrieve more for reranking
    min_score: float = 0.2  # Lower threshold, let reranker filter

    # Hybrid search settings
    keyword_weight: float = 0.3  # Weight for keyword score in hybrid
    use_bm25: bool = True  # Use BM25 for keyword scoring

    # Reranking settings
    enable_reranking: bool = True
    rerank_top_k: int = 5  # Final results after reranking
    rerank_score_weight: float = 0.3  # Original score weight

    # Query enhancement settings
    enable_query_expansion: bool = False  # LLM query expansion
    max_query_variations: int = 3

    # Caching settings
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour

    # Result settings
    max_context_tokens: int = 4000
    deduplicate_results: bool = True
    dedup_threshold: float = 0.9  # Similarity threshold for dedup


@dataclass
class RAGResult:
    """Single RAG retrieval result."""

    id: str
    text: str
    score: float
    vector_score: float
    keyword_score: float
    rerank_score: float | None
    source: str
    kb_name: str
    kb_id: int
    metadata: dict[str, Any] = field(default_factory=dict)
    rank: int = 0


@dataclass
class RAGResponse:
    """Complete RAG response."""

    results: list[RAGResult]
    context_text: str
    query_variations: list[str]
    total_retrieved: int
    retrieval_time_ms: float
    strategy_used: str
    cache_hit: bool = False


class EnhancedRAGService:
    """
    Production-grade RAG service with advanced retrieval features.

    Features:
    - Multi-strategy retrieval (vector, hybrid, reranked)
    - Query enhancement and expansion
    - Cross-encoder reranking
    - Result caching
    - Intelligent deduplication
    - Multi-KB fusion with Reciprocal Rank Fusion
    """

    def __init__(self, config: RAGConfig | None = None):
        """Initialize the enhanced RAG service."""
        self.config = config or RAGConfig()
        self._cache: dict[str, tuple[float, Any]] = {}  # query_hash -> (timestamp, results)
        self._embedding_cache: dict[str, list[float]] = {}  # text_hash -> embedding
        self._reranker = None

    def _get_reranker(self):
        """Lazy load reranker service."""
        if self._reranker is None and self.config.enable_reranking:
            try:
                from src.services.knowledge_base.reranker_service import (
                    RerankerProvider,
                    get_reranker,
                )

                self._reranker = get_reranker(provider=RerankerProvider.CROSS_ENCODER)
            except Exception as e:
                logger.warning(f"Failed to initialize reranker: {e}")
        return self._reranker

    def _cache_key(self, query: str, kb_ids: list[int]) -> str:
        """Generate cache key for query + KB combination."""
        kb_str = ",".join(str(id) for id in sorted(kb_ids))
        return hashlib.md5(f"{query}:{kb_str}".encode()).hexdigest()

    def _check_cache(self, cache_key: str) -> RAGResponse | None:
        """Check if results are cached and still valid."""
        if not self.config.enable_cache:
            return None

        if cache_key in self._cache:
            timestamp, results = self._cache[cache_key]
            if time.time() - timestamp < self.config.cache_ttl_seconds:
                logger.info(f"Cache HIT for RAG query (key: {cache_key[:8]}...)")
                results.cache_hit = True
                return results
            else:
                # Expired
                del self._cache[cache_key]

        return None

    def _set_cache(self, cache_key: str, response: RAGResponse) -> None:
        """Cache RAG results."""
        if self.config.enable_cache:
            self._cache[cache_key] = (time.time(), response)
            # Limit cache size
            if len(self._cache) > 1000:
                # Remove oldest entries
                oldest_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][0])[:100]
                for key in oldest_keys:
                    del self._cache[key]

    async def retrieve(
        self,
        query: str,
        knowledge_bases: list[Any],
        embedding_service: Any,
        vector_db_pool: Any,
        llm_client: Any | None = None,
        config_override: dict[str, Any] | None = None,
    ) -> RAGResponse:
        """
        Perform enhanced RAG retrieval.

        Args:
            query: The user's query (clean, without platform metadata)
            knowledge_bases: List of AgentKnowledgeBase objects
            embedding_service: Service for generating embeddings
            vector_db_pool: Connection pool for vector databases
            llm_client: Optional LLM client for query enhancement
            config_override: Override default config settings

        Returns:
            RAGResponse with ranked results and context
        """
        start_time = time.time()

        # Apply config overrides
        config = self.config
        if config_override:
            config = RAGConfig(**{**vars(config), **config_override})

        # Extract KB IDs for caching
        kb_ids = [akb.knowledge_base.id for akb in knowledge_bases]

        # Check cache
        cache_key = self._cache_key(query, kb_ids)
        cached = self._check_cache(cache_key)
        if cached:
            return cached

        # Query enhancement (if enabled and LLM available)
        query_variations = [query]
        if config.enable_query_expansion and llm_client:
            try:
                expanded = await self._expand_query(query, llm_client)
                query_variations = [query] + expanded[: config.max_query_variations - 1]
                logger.info(f"Expanded query into {len(query_variations)} variations")
            except Exception as e:
                logger.warning(f"Query expansion failed: {e}")

        # Retrieve from all knowledge bases
        all_results: list[RAGResult] = []
        total_retrieved = 0

        for agent_kb in knowledge_bases:
            kb = agent_kb.knowledge_base
            try:
                kb_results = await self._retrieve_from_kb(
                    query=query,
                    query_variations=query_variations,
                    kb=kb,
                    agent_kb=agent_kb,
                    embedding_service=embedding_service,
                    vector_db_pool=vector_db_pool,
                    config=config,
                )
                all_results.extend(kb_results)
                total_retrieved += len(kb_results)
                logger.info(f"Retrieved {len(kb_results)} results from KB '{kb.name}'")
            except Exception as e:
                logger.error(f"Error retrieving from KB {kb.id}: {e}")
                continue

        # Deduplicate results
        if config.deduplicate_results and len(all_results) > 1:
            all_results = self._deduplicate_results(all_results, config.dedup_threshold)
            logger.info(f"After deduplication: {len(all_results)} results")

        # Apply reranking
        if config.enable_reranking and len(all_results) > 0:
            all_results = await self._rerank_results(query, all_results, config)

        # Sort by final score and limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        final_results = all_results[: config.rerank_top_k]

        # Assign final ranks
        for i, result in enumerate(final_results):
            result.rank = i + 1

        # Build context text
        context_text = self._build_context_text(final_results, config.max_context_tokens)

        retrieval_time_ms = (time.time() - start_time) * 1000

        response = RAGResponse(
            results=final_results,
            context_text=context_text,
            query_variations=query_variations,
            total_retrieved=total_retrieved,
            retrieval_time_ms=retrieval_time_ms,
            strategy_used=config.strategy.value,
            cache_hit=False,
        )

        # Cache results
        self._set_cache(cache_key, response)

        logger.info(
            f"Enhanced RAG completed: {len(final_results)} results, "
            f"{retrieval_time_ms:.1f}ms, strategy={config.strategy.value}"
        )

        return response

    async def _retrieve_from_kb(
        self,
        query: str,
        query_variations: list[str],
        kb: Any,
        agent_kb: Any,
        embedding_service: Any,
        vector_db_pool: Any,
        config: RAGConfig,
    ) -> list[RAGResult]:
        """Retrieve results from a single knowledge base."""
        from src.services.knowledge_base.embedding_service import EmbeddingService

        # Get KB-specific config
        retrieval_config = agent_kb.retrieval_config or {}
        max_results = retrieval_config.get("max_results", config.vector_top_k)
        min_score = retrieval_config.get("min_score", config.min_score)

        # Initialize embedding service for this KB
        embedding_config = kb.get_embedding_config_decrypted()
        kb_embedding_service = EmbeddingService(
            provider=kb.embedding_provider.value if kb.embedding_provider else "sentence_transformers",
            model_name=kb.embedding_model or "all-MiniLM-L6-v2",
            config=embedding_config,
        )

        # Get vector DB config
        vector_db_config = kb.get_vector_db_config_decrypted()
        collection_name = vector_db_config.get("index_name") or vector_db_config.get("collection_name") or f"kb-{kb.id}"
        namespace = str(kb.id)

        # Generate query embedding(s)
        results_by_variation: dict[str, list[dict]] = {}

        is_advanced = getattr(kb, "ingestion_mode", None) == IngestionMode.ADVANCED
        search_backend = get_search_backend() if is_advanced else None

        for variation in query_variations:
            # Check embedding cache
            variation_hash = hashlib.md5(variation.encode()).hexdigest()
            if variation_hash in self._embedding_cache:
                query_embedding = self._embedding_cache[variation_hash]
            else:
                query_embedding = kb_embedding_service.embed_texts([variation])[0]
                self._embedding_cache[variation_hash] = query_embedding

            if is_advanced:
                cb_response = await search_backend.search(
                    tenant_id=str(kb.tenant_id),
                    knowledge_base_id=str(kb.id),
                    query=variation,
                    query_vector=query_embedding,
                    limit=max_results,
                )
                vector_results = [
                    {
                        "id": r.doc_id,
                        "score": r.score,
                        "keyword_score": r.keyword_score,
                        "payload": {
                            "text": r.content,
                            "title": r.title,
                            **(r.metadata or {}),
                        },
                    }
                    for r in cb_response.results
                    if r.score >= min_score
                ]
            else:
                with vector_db_pool.get_connection(
                    provider_type=kb.vector_db_provider,
                    config=vector_db_config,
                ) as vector_db:
                    vector_results = vector_db.search(
                        collection_name=collection_name,
                        namespace=namespace,
                        query_vector=query_embedding,
                        limit=max_results,
                        score_threshold=min_score,
                    )
            results_by_variation[variation] = vector_results

        # Merge results from all variations using RRF
        merged_results = self._reciprocal_rank_fusion(results_by_variation)

        # Apply hybrid scoring if enabled
        if config.strategy in [RetrievalStrategy.HYBRID, RetrievalStrategy.HYBRID_RERANK, RetrievalStrategy.ADVANCED]:
            merged_results = self._apply_hybrid_scoring(query, merged_results, config.keyword_weight)

        # Convert to RAGResult objects
        rag_results = []
        for result in merged_results:
            payload = result.get("payload", {})
            text = payload.get("text", "")

            rag_results.append(
                RAGResult(
                    id=result.get("id", ""),
                    text=text,
                    score=result.get("combined_score", result.get("score", 0)),
                    vector_score=result.get("score", 0),
                    keyword_score=result.get("keyword_score", 0),
                    rerank_score=None,
                    source=payload.get("title", payload.get("external_id", "Unknown")),
                    kb_name=kb.name,
                    kb_id=kb.id,
                    metadata={k: v for k, v in payload.items() if k not in ["text", "knowledge_base_id"]},
                )
            )

        return rag_results

    def _reciprocal_rank_fusion(
        self,
        results_by_variation: dict[str, list[dict]],
        k: int = 60,
    ) -> list[dict]:
        """
        Merge results from multiple queries using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank_i)) for each result list containing the item.
        """
        if len(results_by_variation) == 1:
            # Single query, no fusion needed
            return list(results_by_variation.values())[0]

        scores: dict[str, float] = {}
        result_data: dict[str, dict] = {}

        for _variation, results in results_by_variation.items():
            for rank, result in enumerate(results, 1):
                result_id = result.get("id", "")
                rrf_score = 1 / (k + rank)

                if result_id in scores:
                    scores[result_id] += rrf_score
                else:
                    scores[result_id] = rrf_score
                    result_data[result_id] = result

        # Sort by RRF score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        merged = []
        for result_id in sorted_ids:
            result = result_data[result_id].copy()
            result["rrf_score"] = scores[result_id]
            # Normalize RRF score to 0-1 range
            max_possible = len(results_by_variation) / (k + 1)
            result["combined_score"] = min(scores[result_id] / max_possible, 1.0)
            merged.append(result)

        return merged

    def _apply_hybrid_scoring(
        self,
        query: str,
        results: list[dict],
        keyword_weight: float,
    ) -> list[dict]:
        """
        Apply hybrid scoring combining vector and keyword scores.

        Uses BM25-like term frequency scoring for keyword component.
        """
        # Extract query terms
        query_terms = set(re.findall(r"\b\w{2,}\b", query.lower()))

        for result in results:
            text = result.get("payload", {}).get("text", "").lower()
            text_terms = re.findall(r"\b\w{2,}\b", text)
            term_freq = {}
            for term in text_terms:
                term_freq[term] = term_freq.get(term, 0) + 1

            # Calculate BM25-like score
            k1 = 1.2
            b = 0.75
            avg_dl = 500  # Approximate average document length
            dl = len(text_terms)

            bm25_score = 0
            for term in query_terms:
                if term in term_freq:
                    tf = term_freq[term]
                    # Simplified BM25 (without IDF for single-doc scoring)
                    score = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
                    bm25_score += score

            # Normalize to 0-1
            max_bm25 = len(query_terms) * (k1 + 1)
            keyword_score = bm25_score / max_bm25 if max_bm25 > 0 else 0

            # Exact phrase bonus
            if query.lower() in text:
                keyword_score = min(keyword_score + 0.3, 1.0)

            result["keyword_score"] = keyword_score

            # Combine scores
            vector_score = result.get("score", result.get("combined_score", 0))
            combined = (1 - keyword_weight) * vector_score + keyword_weight * keyword_score
            result["combined_score"] = combined

        # Re-sort by combined score
        results.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
        return results

    async def _rerank_results(
        self,
        query: str,
        results: list[RAGResult],
        config: RAGConfig,
    ) -> list[RAGResult]:
        """Apply cross-encoder reranking to results."""
        reranker = self._get_reranker()
        if not reranker:
            return results

        # Convert to format expected by reranker
        rerank_input = [
            {
                "id": r.id,
                "score": r.score,
                "payload": {"text": r.text, **r.metadata},
            }
            for r in results
        ]

        try:
            reranked = reranker.rerank(
                query=query,
                results=rerank_input,
                top_k=config.rerank_top_k,
                score_weight=config.rerank_score_weight,
            )

            # Map back to RAGResult
            result_map = {r.id: r for r in results}
            reranked_results = []
            for rr in reranked:
                if rr.id in result_map:
                    original = result_map[rr.id]
                    original.rerank_score = rr.rerank_score
                    original.score = rr.combined_score
                    reranked_results.append(original)

            logger.info(f"Reranked {len(results)} results to top {len(reranked_results)}")
            return reranked_results

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return results

    def _deduplicate_results(
        self,
        results: list[RAGResult],
        threshold: float,
    ) -> list[RAGResult]:
        """Remove near-duplicate results based on text similarity."""
        if len(results) <= 1:
            return results

        unique_results = []
        seen_texts: list[str] = []

        for result in results:
            is_duplicate = False
            for seen_text in seen_texts:
                # Simple Jaccard similarity
                result_words = set(result.text.lower().split())
                seen_words = set(seen_text.lower().split())
                if len(result_words | seen_words) > 0:
                    similarity = len(result_words & seen_words) / len(result_words | seen_words)
                    if similarity >= threshold:
                        is_duplicate = True
                        break

            if not is_duplicate:
                unique_results.append(result)
                seen_texts.append(result.text)

        return unique_results

    async def _expand_query(self, query: str, llm_client: Any) -> list[str]:
        """
        Expand query using LLM to generate variations.

        Generates alternative phrasings and related queries to improve recall.
        """
        prompt = f"""Generate 3 alternative search queries that could help find relevant information for the following question.
The queries should:
1. Use different words/synonyms
2. Focus on different aspects of the question
3. Be concise (under 15 words each)

Original question: {query}

Respond with ONLY the 3 queries, one per line, no numbering or explanation."""

        try:
            response = await llm_client.generate_content(prompt, max_tokens=200)
            variations = [
                line.strip() for line in response.strip().split("\n") if line.strip() and len(line.strip()) > 5
            ]
            return variations[:3]
        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")
            return []

    def _build_context_text(
        self,
        results: list[RAGResult],
        max_tokens: int,
    ) -> str:
        """Build formatted context text from results."""
        if not results:
            return ""

        context_parts = ["# Retrieved Context from Knowledge Bases\n"]
        total_chars = len(context_parts[0])
        max_chars = max_tokens * 4  # Approximate 4 chars per token

        for result in results:
            source_info = f"\n## Source {result.rank} (Relevance: {result.score:.2f}, KB: {result.kb_name})"
            if result.source:
                source_info += f"\n**Source:** {result.source}"

            entry = f"{source_info}\n{result.text}\n"

            if total_chars + len(entry) > max_chars:
                # Truncate to fit
                remaining = max_chars - total_chars - len(source_info) - 10
                if remaining > 100:
                    entry = f"{source_info}\n{result.text[:remaining]}...\n"
                else:
                    break

            context_parts.append(entry)
            total_chars += len(entry)

        return "\n".join(context_parts)


# Default instance
_enhanced_rag_service: EnhancedRAGService | None = None


def get_enhanced_rag_service(config: RAGConfig | None = None) -> EnhancedRAGService:
    """Get or create the enhanced RAG service."""
    global _enhanced_rag_service
    if _enhanced_rag_service is None:
        _enhanced_rag_service = EnhancedRAGService(config)
    return _enhanced_rag_service
