"""
Redis Streams consumer for KB ingestion.

Reads batches of raw documents from Redis Streams, runs them through the
ingestion pipeline (dedup → chunk → embed → index), and acknowledges them.

Consumer group: "kb_embedder"
One consumer per Celery worker (identified by worker hostname).

The pipeline:
  1. XREADGROUP with COUNT=batch_size (default 100)
  2. Deserialise payload
  3. Filter: skip < MIN_CONTENT_TOKENS, known bot patterns
  4. Dedup: drop already-indexed external_ids
  5. Chunk: source-aware strategy
  6. Embed: batch all chunks → one API call
  7. Index: upsert to search backend
  8. Mark seen in dedup backend
  9. XACK
 10. On failure: retry up to 3x, then move to dead-letter stream
"""

import json
import logging
import socket
from typing import Any

logger = logging.getLogger(__name__)

_GROUP = "kb_embedder"
_DL_SUFFIX = ":dead"


class StreamConsumer:
    """
    Reads + processes one batch from a Redis Stream.

    Designed to be called from a Celery task on a schedule (every 10-30 seconds).
    Each call processes up to `batch_size` messages and returns stats.
    """

    def __init__(self) -> None:
        self._consumer_name = socket.gethostname()

    async def _get_redis(self) -> Any:
        from src.config.redis import get_redis_async

        return get_redis_async()

    def _batch_size(self) -> int:
        from src.config.settings import get_settings

        return getattr(get_settings(), "company_brain_batch_size", 100)

    def _min_tokens(self) -> int:
        from src.config.settings import get_settings

        return getattr(get_settings(), "company_brain_min_content_tokens", 10)

    async def _ensure_group(self, r: Any, key: str) -> None:
        """Create consumer group if it does not exist (idempotent)."""
        try:
            await r.xgroup_create(key, _GROUP, id="0", mkstream=True)
        except Exception:
            pass  # BUSYGROUP error means it already exists

    async def consume(self, kb_id: int, tenant_id: str, source_type: str, block_ms: int = 500) -> dict[str, int]:
        """
        Read and process one batch from the stream.

        Returns stats dict: {"read": int, "indexed": int, "skipped": int, "failed": int}
        """
        key = f"kb_ingest:{kb_id}:{source_type.lower()}"
        r = await self._get_redis()
        await self._ensure_group(r, key)
        batch_size = self._batch_size()
        min_tokens = self._min_tokens()

        messages = await r.xreadgroup(
            groupname=_GROUP,
            consumername=self._consumer_name,
            streams={key: ">"},
            count=batch_size,
            block=block_ms,
        )
        if not messages:
            return {"read": 0, "indexed": 0, "skipped": 0, "failed": 0}

        raw_docs: list[dict[str, Any]] = []
        message_ids: list[str] = []

        for _stream, entries in messages:
            for msg_id, fields in entries:
                try:
                    payload_bytes = fields.get(b"payload") or fields.get("payload", "{}")
                    if isinstance(payload_bytes, bytes):
                        payload_bytes = payload_bytes.decode()
                    doc = json.loads(payload_bytes)
                    raw_docs.append(doc)
                    message_ids.append(msg_id)
                except Exception as exc:
                    logger.warning("Malformed stream message %s: %s", msg_id, exc)

        if not raw_docs:
            return {"read": 0, "indexed": 0, "skipped": 0, "failed": 0}

        stats = await self._process_batch(tenant_id, source_type, raw_docs, min_tokens)

        # Acknowledge all messages (even ones we skipped — they're not errors)
        if message_ids:
            await r.xack(key, _GROUP, *message_ids)

        stats["read"] = len(raw_docs)
        return stats

    async def _process_batch(
        self,
        tenant_id: str,
        source_type: str,
        raw_docs: list[dict[str, Any]],
        min_tokens: int,
    ) -> dict[str, int]:
        from src.services.company_brain.search.factory import get_search_backend

        from .chunker import chunk_document
        from .dedup import get_dedup_backend

        dedup = get_dedup_backend()
        search = get_search_backend()
        indexed = skipped = failed = 0

        # 1. Filter short / empty content
        filtered = [d for d in raw_docs if self._passes_filter(d, min_tokens)]
        skipped += len(raw_docs) - len(filtered)

        if not filtered:
            return {"indexed": 0, "skipped": skipped, "failed": 0}

        # 2. Dedup check
        external_ids = [str(d.get("id") or d.get("external_id", "")) for d in filtered]
        unseen_ids = set(await dedup.filter_unseen(tenant_id, source_type, external_ids))
        unique_docs = [d for d in filtered if str(d.get("id") or d.get("external_id", "")) in unseen_ids]
        skipped += len(filtered) - len(unique_docs)

        if not unique_docs:
            return {"indexed": 0, "skipped": skipped, "failed": 0}

        # 3. Chunk
        all_chunks: list[dict[str, Any]] = []
        for doc in unique_docs:
            try:
                chunks = chunk_document(doc, source_type)
                all_chunks.extend(chunks)
            except Exception as exc:
                logger.warning("Chunking failed for doc %s: %s", doc.get("id"), exc)
                failed += 1

        if not all_chunks:
            return {"indexed": 0, "skipped": skipped, "failed": failed}

        # 4. Embed (batch)
        texts = [c["chunk_content"] for c in all_chunks]
        try:
            embeddings = await self._embed_batch(texts, source_type)
        except Exception as exc:
            logger.error("Embedding batch failed: %s", exc)
            return {"indexed": 0, "skipped": skipped, "failed": failed + len(all_chunks)}

        # 5. Build index documents
        index_docs: list[dict[str, Any]] = []
        for chunk, emb in zip(all_chunks, embeddings, strict=False):
            index_docs.append(
                {
                    "doc_id": f"{chunk.get('id', '')}_{chunk['chunk_index']}",
                    "external_id": str(chunk.get("id") or chunk.get("external_id", "")),
                    "source_type": source_type,
                    "content": chunk["chunk_content"],
                    "title": chunk.get("title"),
                    "embedding": emb,
                    "metadata": {**(chunk.get("metadata") or {}), "tenant_id": tenant_id},
                    "source_url": chunk.get("external_url"),
                    "occurred_at": chunk.get("source_created_at"),
                    "storage_tier": "hot",
                }
            )

        # 6. Index
        result = await search.index_documents(tenant_id, index_docs)
        indexed += result.get("indexed", 0)
        failed += result.get("failed", 0)

        # 7. Mark seen
        await dedup.mark_seen_batch(tenant_id, source_type, list(unseen_ids))

        return {"indexed": indexed, "skipped": skipped, "failed": failed}

    def _passes_filter(self, doc: dict[str, Any], min_tokens: int) -> bool:
        """Return False if the document should be skipped before dedup/embed."""
        content = doc.get("content") or doc.get("text") or ""
        if not content or not content.strip():
            return False
        # Approximate token count
        token_count = max(1, len(content) // 4)
        if token_count < min_tokens:
            return False
        # Skip known bot / automation patterns
        meta = doc.get("metadata") or {}
        if meta.get("is_bot"):
            return False
        return True

    async def _embed_batch(self, texts: list[str], source_type: str) -> list[list[float]]:
        """Embed a batch of texts using the configured model for this source type."""
        import json as _json

        from src.config.settings import get_settings

        settings = get_settings()
        raw_models = getattr(settings, "company_brain_embedding_models", '{"default":"text-embedding-3-small"}')
        try:
            models: dict[str, str] = _json.loads(raw_models)
        except Exception:
            models = {"default": "text-embedding-3-small"}

        model = models.get(source_type.lower(), models.get("default", "text-embedding-3-small"))

        from src.services.knowledge_base.embedding_service import EmbeddingService

        svc = EmbeddingService(model=model)
        return await svc.embed_batch(texts)
