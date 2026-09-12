"""RAG (Retrieval Augmented Generation) service using Google ADK and external vector stores."""

import asyncio
import logging
from typing import Any

from google import genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.agent_knowledge_base import AgentKnowledgeBase
from src.models.document import Document
from src.models.knowledge_base import KnowledgeBase
from src.services.observability.langfuse_service import LangfuseService
from src.services.storage.s3_storage import S3StorageService

from .embedding_service import EmbeddingService
from .providers.vector_db_factory import VectorDBProviderFactory
from .text_processor import TextProcessor

logger = logging.getLogger(__name__)


class RAGService:
    """
    Service for Retrieval Augmented Generation.

    This service integrates external vector stores with Google ADK agents
    to provide context-aware responses using retrieved knowledge.
    """

    def __init__(self, db: AsyncSession, google_client: genai.Client):
        """
        Initialize RAG service.

        Args:
            db: Async database session
            google_client: Google GenAI client (kept for backward compatibility)
        """
        self.db = db
        self.google_client = google_client
        self.text_processor = TextProcessor()
        self._vector_db_cache: dict[int, Any] = {}
        self._embedding_service_cache: dict[int, EmbeddingService] = {}
        self.langfuse_service = LangfuseService()

    def get_vector_db(self, knowledge_base: KnowledgeBase) -> Any:
        """
        Get or create vector DB provider for a knowledge base.

        Args:
            knowledge_base: KnowledgeBase instance

        Returns:
            Vector DB provider instance
        """
        if knowledge_base.id in self._vector_db_cache:
            return self._vector_db_cache[knowledge_base.id]

        # Get decrypted vector DB config
        vector_db_config = knowledge_base.get_vector_db_config_decrypted()

        provider = VectorDBProviderFactory.create(
            provider_type=knowledge_base.vector_db_provider, config=vector_db_config
        )
        provider.connect()

        self._vector_db_cache[knowledge_base.id] = provider
        return provider

    def get_embedding_service(self, knowledge_base: KnowledgeBase) -> EmbeddingService:
        """
        Get or create embedding service for a knowledge base.

        Args:
            knowledge_base: KnowledgeBase instance

        Returns:
            EmbeddingService instance
        """
        if knowledge_base.id in self._embedding_service_cache:
            return self._embedding_service_cache[knowledge_base.id]

        # Get decrypted embedding config
        embedding_config = knowledge_base.get_embedding_config_decrypted()

        service = EmbeddingService(
            provider=knowledge_base.embedding_provider.value,
            model_name=knowledge_base.embedding_model,
            config=embedding_config,
        )

        self._embedding_service_cache[knowledge_base.id] = service
        return service

    async def generate_embedding(self, text: str, knowledge_base: KnowledgeBase) -> list[float]:
        """
        Generate embedding for text using configured embedding provider.

        Args:
            text: Text to embed
            knowledge_base: Knowledge base configuration

        Returns:
            Embedding vector
        """
        try:
            embedding_service = self.get_embedding_service(knowledge_base)
            # PERFORMANCE: embed_text() uses synchronous SDK calls that block the
            # event loop. Offload to a thread so other coroutines can proceed.
            return await asyncio.to_thread(embedding_service.embed_text, text)
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    async def _enrich_with_document_metadata(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Enrich vector search results with Document model metadata.

        Uses batch fetching to avoid N+1 query problem.

        Args:
            results: List of vector search results

        Returns:
            Enriched results with full document metadata
        """
        if not results:
            return []

        # Batch fetch: Collect all doc_ids first to avoid N+1 queries
        doc_ids = []
        for result in results:
            payload = result.get("payload", {})
            doc_id = payload.get("doc_id")
            if doc_id:
                doc_ids.append(doc_id)

        # Single query to fetch all documents at once
        documents_map: dict[Any, Document] = {}
        if doc_ids:
            try:
                result = await self.db.execute(select(Document).filter(Document.id.in_(doc_ids)))
                documents = list(result.scalars().all())
                documents_map = {doc.id: doc for doc in documents}
            except Exception as e:
                logger.error(f"Error batch fetching documents: {e}")

        # Initialize S3 service once (not per document)
        s3 = None
        try:
            s3 = S3StorageService()
        except Exception as e:
            logger.warning(f"Failed to initialize S3 service: {e}")

        # Enrich results with cached document data
        enriched_results = []
        for result in results:
            payload = result.get("payload", {})
            doc_id = payload.get("doc_id")

            if doc_id and doc_id in documents_map:
                document = documents_map[doc_id]
                # Add full document metadata
                result["document"] = {
                    "id": str(document.id),
                    "title": document.title,
                    "source_type": document.source_type,
                    "external_id": document.external_id,
                    "external_url": document.external_url,
                    "s3_bucket": document.s3_bucket,
                    "s3_key": document.s3_key,
                    "s3_url": document.s3_url,
                    "mime_type": document.mime_type,
                    "metadata": document.metadata,
                    "created_at": document.created_at.isoformat() if document.created_at else None,
                }

                # Generate presigned URL if S3 file exists
                if document.s3_key and s3:
                    try:
                        presigned_url = s3.generate_presigned_url(
                            key=document.s3_key,
                            expiration=3600,  # 1 hour
                        )
                        result["document"]["presigned_url"] = presigned_url
                    except Exception as e:
                        logger.warning(f"Failed to generate presigned URL for {doc_id}: {e}")

            enriched_results.append(result)

        return enriched_results

    async def retrieve_context(
        self,
        query: str,
        agent: Agent,
        limit: int | None = None,
        score_threshold: float | None = None,
        include_document_metadata: bool = True,
        trace_id: str | None = None,
        observability_config: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant context for a query from agent's knowledge bases.

        Args:
            query: Search query
            agent: Agent instance
            limit: Maximum number of results (overrides KB config)
            score_threshold: Minimum similarity score (overrides KB config)
            include_document_metadata: Whether to enrich with Document metadata
            trace_id: Optional Langfuse trace ID for observability
            observability_config: Optional observability configuration

        Returns:
            List of retrieved documents with metadata
        """
        # Check if RAG tracing is enabled
        should_trace = (
            observability_config
            and observability_config.get("trace_rag", True)
            and self.langfuse_service.should_trace(observability_config)
        )

        span_id = None
        if should_trace and trace_id:
            try:
                span_id = self.langfuse_service.create_span(
                    name="rag_retrieval",
                    input_data={
                        "query": query,
                        "agent_id": str(agent.id),
                        "agent_name": agent.name,
                        "limit": limit,
                        "score_threshold": score_threshold,
                    },
                    trace_id=trace_id,
                    metadata={
                        "operation": "retrieve_context",
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to create RAG span: {e}")

        all_results = []

        # Get all enabled knowledge bases for this agent
        # Use selectinload to prevent N+1 queries when accessing knowledge_base relationship
        from sqlalchemy.orm import selectinload

        result = await self.db.execute(
            select(AgentKnowledgeBase)
            .options(selectinload(AgentKnowledgeBase.knowledge_base))
            .filter(AgentKnowledgeBase.agent_id == agent.id, AgentKnowledgeBase.is_active)
        )
        agent_kbs = list(result.scalars().all())

        # PERFORMANCE: Search all KBs in parallel — each KB search (embedding +
        # vector query) is independent and typically network-bound.
        async def _search_single_kb(agent_kb):
            kb = agent_kb.knowledge_base
            # Generate query embedding (wrapped in to_thread below via generate_embedding)
            query_embedding = await self.generate_embedding(query, kb)

            # Get vector DB provider
            vector_db = self.get_vector_db(kb)

            # Determine search parameters from retrieval config
            config = agent_kb.retrieval_config or {}
            search_limit = limit or config.get("max_results", 5)
            search_threshold = score_threshold or config.get("min_score", 0.7)

            # Get collection/index name from vector_db_config
            collection_name = (
                kb.vector_db_config.get("index_name") or kb.vector_db_config.get("collection_name") or f"kb-{kb.id}"
            )

            # Use KB ID as namespace for Pinecone multi-tenancy
            namespace = str(kb.id)
            results = await asyncio.to_thread(
                vector_db.search,
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=search_limit,
                score_threshold=search_threshold,
                namespace=namespace,
            )

            # Add KB metadata to results
            for result in results:
                result["knowledge_base_id"] = kb.id
                result["knowledge_base_name"] = kb.name

            return results

        tasks = [_search_single_kb(agent_kb) for agent_kb in agent_kbs]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        for results in results_list:
            if isinstance(results, Exception):
                logger.error(f"KB search failed: {results}")
                continue
            all_results.extend(results)

        # Sort by score
        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Limit results
        if limit:
            all_results = all_results[:limit]

        # Enrich with Document metadata if requested
        if include_document_metadata:
            all_results = await self._enrich_with_document_metadata(all_results)

        # Update span with output
        if span_id:
            try:
                self.langfuse_service.create_span(
                    name="rag_retrieval",
                    output_data={
                        "num_results": len(all_results),
                        "knowledge_bases_searched": len(agent_kbs),
                        "top_scores": [r.get("score", 0) for r in all_results[:3]],
                    },
                    trace_id=trace_id,
                    metadata={
                        "operation": "retrieve_context",
                        "completed": True,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to update RAG span: {e}")

        return all_results

    def format_context_for_prompt(self, retrieved_docs: list[dict[str, Any]], max_tokens: int = 4000) -> str:
        """
        Format retrieved documents into context string for prompt.

        Args:
            retrieved_docs: List of retrieved documents
            max_tokens: Maximum tokens for context

        Returns:
            Formatted context string
        """
        if not retrieved_docs:
            return ""

        context_parts = ["# Retrieved Context\n"]
        current_tokens = 0

        for i, doc in enumerate(retrieved_docs, 1):
            payload = doc.get("payload", {})
            text = payload.get("text", "")
            source = payload.get("source", "Unknown")
            score = doc.get("score", 0)
            kb_name = doc.get("knowledge_base_name", "Unknown")

            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            doc_tokens = len(text) // 4

            if current_tokens + doc_tokens > max_tokens:
                break

            context_parts.append(
                f"\n## Source {i} (Relevance: {score:.2f}, KB: {kb_name})\n**Source:** {source}\n{text}\n"
            )
            current_tokens += doc_tokens

        return "\n".join(context_parts)

    def format_sources_for_response(self, retrieved_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Format retrieved documents as sources for API response.

        Args:
            retrieved_docs: List of retrieved documents with metadata

        Returns:
            List of formatted source objects
        """
        sources = []

        for i, doc in enumerate(retrieved_docs, 1):
            payload = doc.get("payload", {})
            document = doc.get("document", {})

            source = {
                "index": i,
                "score": doc.get("score", 0),
                "text_preview": payload.get("text", "")[:200],
                "knowledge_base": doc.get("knowledge_base_name", "Unknown"),
            }

            # Add document metadata if available
            if document:
                source.update(
                    {
                        "document_id": document.get("id"),
                        "title": document.get("title"),
                        "source_type": document.get("source_type"),
                        "external_url": document.get("external_url"),
                        "presigned_url": document.get("presigned_url"),
                        "mime_type": document.get("mime_type"),
                        "created_at": document.get("created_at"),
                        "metadata": document.get("metadata", {}),
                    }
                )

                # Format source-specific display
                if document.get("source_type") == "SLACK":
                    meta = document.get("metadata", {})
                    source["display"] = {
                        "type": "Slack Message",
                        "channel": meta.get("channel", "Unknown"),
                        "user": meta.get("user", "Unknown"),
                        "timestamp": meta.get("timestamp"),
                        "link": document.get("external_url"),
                    }
                elif document.get("source_type") == "GMAIL":
                    meta = document.get("metadata", {})
                    source["display"] = {
                        "type": "Email",
                        "from": meta.get("from", "Unknown"),
                        "subject": meta.get("subject", "No Subject"),
                        "timestamp": meta.get("timestamp"),
                        "link": document.get("external_url"),
                    }
                else:
                    source["display"] = {
                        "type": document.get("source_type", "Document").title(),
                        "title": document.get("title"),
                        "link": document.get("external_url"),
                    }
            else:
                source["display"] = {"type": "Document", "source": payload.get("source", "Unknown")}

            sources.append(source)

        return sources

    async def augment_prompt_with_context(
        self, query: str, agent: Agent, system_prompt: str | None = None, max_context_tokens: int = 4000
    ) -> dict[str, Any]:
        """
        Augment a prompt with retrieved context.

        Args:
            query: User query
            agent: Agent instance
            system_prompt: Optional system prompt
            max_context_tokens: Maximum tokens for context

        Returns:
            Dictionary with augmented_prompt, context, and formatted sources
        """
        # Retrieve relevant context with full metadata
        retrieved_docs = await self.retrieve_context(query, agent, include_document_metadata=True)

        # Format context for prompt
        context = self.format_context_for_prompt(retrieved_docs, max_tokens=max_context_tokens)

        # Format sources for response
        formatted_sources = self.format_sources_for_response(retrieved_docs)

        # Build augmented prompt
        if context:
            augmented_prompt = f"""{context}

# User Query
{query}

Please answer the user's query using the retrieved context above. If the context doesn't contain relevant information, you may use your general knowledge but indicate that."""
        else:
            augmented_prompt = query

        return {
            "augmented_prompt": augmented_prompt,
            "context": context,
            "num_sources": len(retrieved_docs),
            "sources": formatted_sources,
        }

    async def add_documents_to_knowledge_base(
        self, knowledge_base: KnowledgeBase, documents: list[dict[str, Any]], batch_size: int = 100
    ) -> dict[str, Any]:
        """
        Add documents to a knowledge base.

        Args:
            knowledge_base: KnowledgeBase instance
            documents: List of documents with structure:
                {
                    "text": "document text",
                    "metadata": {"source": "...", "timestamp": "...", ...}
                }
            batch_size: Batch size for processing

        Returns:
            Dictionary with processing statistics
        """
        vector_db = self.get_vector_db(knowledge_base)
        collection_name = knowledge_base.vector_db_config.get("collection_name", f"kb_{knowledge_base.id}")

        # Ensure collection exists
        if not vector_db.collection_exists(collection_name):
            vector_db.create_collection(
                collection_name=collection_name,
                dimension=knowledge_base.embedding_config.get("dimension", 768),
                distance_metric="cosine",
            )

        total_chunks = 0
        total_docs = 0

        for doc in documents:
            # Chunk the document
            chunks = self.text_processor.chunk_text(
                text=doc["text"], chunk_size=knowledge_base.chunk_size, chunk_overlap=knowledge_base.chunk_overlap
            )

            # Process in batches
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i : i + batch_size]

                # Generate embeddings using batch method for efficiency
                # PERFORMANCE: Offload synchronous embedding call to thread pool
                embedding_service = self.get_embedding_service(knowledge_base)
                embeddings = await asyncio.to_thread(embedding_service.embed_texts, batch_chunks)

                # Prepare vectors for insertion
                vectors = []
                for j, (chunk, embedding) in enumerate(zip(batch_chunks, embeddings, strict=False)):
                    vectors.append(
                        {
                            "vector": embedding,
                            "payload": {
                                "text": chunk,
                                "source": doc.get("metadata", {}).get("source", "Unknown"),
                                "doc_id": doc.get("id"),
                                "chunk_index": i + j,
                                **doc.get("metadata", {}),
                            },
                        }
                    )

                # Add to vector DB
                vector_db.add_vectors(collection_name, vectors)
                total_chunks += len(vectors)

            total_docs += 1

        # Update knowledge base statistics
        knowledge_base.total_documents += total_docs
        knowledge_base.total_chunks += total_chunks
        await self.db.commit()

        return {"documents_added": total_docs, "chunks_created": total_chunks, "knowledge_base_id": knowledge_base.id}

    def cleanup(self):
        """Cleanup resources and close connections."""
        for provider in self._vector_db_cache.values():
            try:
                provider.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting provider: {e}")
        self._vector_db_cache.clear()
        self._embedding_service_cache.clear()
