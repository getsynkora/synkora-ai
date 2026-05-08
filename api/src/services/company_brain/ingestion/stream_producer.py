"""
Redis Streams producer for KB ingestion.

Every real-time data source webhook calls push() to enqueue raw events.
The consumer worker reads them in batches, deduplicates, chunks, embeds, and indexes.

Stream key schema:
  kb_ingest:{kb_id}:{source_type}

MAXLEN is approximate (~) to avoid blocking on trim.

If COMPANY_BRAIN_QUEUE_BACKEND=celery_only the producer falls back to dispatching
Celery tasks directly without using Redis Streams.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _stream_key(kb_id: int, source_type: str) -> str:
    return f"kb_ingest:{kb_id}:{source_type.lower()}"


class StreamProducer:
    """
    Enqueues raw documents into a per-KB-per-source Redis Stream.

    Usage:
        producer = StreamProducer()
        await producer.push(kb_id=1, tenant_id="abc", source_type="slack", documents=[...])
    """

    def __init__(self) -> None:
        self._redis: Any | None = None

    async def _get_redis(self) -> Any:
        if self._redis is None:
            from src.config.redis import get_redis_async

            self._redis = get_redis_async()
        return self._redis

    def _max_len(self) -> int:
        from src.config.settings import get_settings

        return getattr(get_settings(), "company_brain_stream_maxlen", 500_000)

    def _use_streams(self) -> bool:
        from src.config.settings import get_settings

        backend = getattr(get_settings(), "company_brain_queue_backend", "redis_streams")
        return backend == "redis_streams"

    async def push(
        self,
        kb_id: int,
        tenant_id: str,
        source_type: str,
        documents: list[dict[str, Any]],
    ) -> dict[str, int]:
        """
        Enqueue a list of raw documents.

        Each document must have at minimum:
          {"id": str, "content": str, "metadata": dict}

        Returns {"queued": int, "skipped": int}
        """
        if not documents:
            return {"queued": 0, "skipped": 0}

        if not self._use_streams():
            return await self._push_via_celery(kb_id, tenant_id, source_type, documents)

        return await self._push_to_stream(kb_id, tenant_id, source_type, documents)

    async def _push_to_stream(
        self,
        kb_id: int,
        tenant_id: str,
        source_type: str,
        documents: list[dict[str, Any]],
    ) -> dict[str, int]:
        r = await self._get_redis()
        key = _stream_key(kb_id, source_type)
        max_len = self._max_len()
        queued = 0
        skipped = 0

        for doc in documents:
            try:
                payload = json.dumps(doc, default=str)
                await r.xadd(
                    key,
                    {
                        "kb_id": str(kb_id),
                        "tenant_id": tenant_id,
                        "source_type": source_type,
                        "payload": payload,
                    },
                    maxlen=max_len,
                    approximate=True,
                )
                queued += 1
            except Exception as exc:
                logger.warning("Failed to push doc %s to stream: %s", doc.get("id"), exc)
                skipped += 1

        logger.debug("StreamProducer: queued=%d skipped=%d key=%s", queued, skipped, key)
        return {"queued": queued, "skipped": skipped}

    async def _push_via_celery(
        self,
        kb_id: int,
        tenant_id: str,
        source_type: str,
        documents: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Dispatch Celery task directly. Used when company_brain_queue_backend != 'redis_streams'."""
        try:
            from src.tasks.company_brain_tasks import kb_process_batch_task

            kb_process_batch_task.delay(
                kb_id=kb_id,
                tenant_id=tenant_id,
                source_type=source_type,
                documents=documents,
            )
            return {"queued": len(documents), "skipped": 0}
        except Exception as exc:
            logger.error("Failed to dispatch Celery task: %s", exc)
            return {"queued": 0, "skipped": len(documents)}

    async def stream_length(self, kb_id: int, source_type: str) -> int:
        """Return current length of the stream (monitoring / health check)."""
        try:
            r = await self._get_redis()
            return await r.xlen(_stream_key(kb_id, source_type))
        except Exception:
            return -1

    async def pending_count(self, kb_id: int, source_type: str) -> int:
        """Return count of pending (not yet acknowledged) messages."""
        try:
            r = await self._get_redis()
            group = "kb_embedder"
            info = await r.xpending(_stream_key(kb_id, source_type), group)
            return int(info.get("pending", 0)) if isinstance(info, dict) else 0
        except Exception:
            return -1
