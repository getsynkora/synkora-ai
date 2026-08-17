# Company Brain Advanced Ingestion Mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Company Brain's streaming ingestion/search engine an opt-in `ingestion_mode` on
`KnowledgeBase` (`STANDARD` = today's synchronous `DocumentProcessor` path, `ADVANCED` = Company
Brain's Redis-Streams + Qdrant-hybrid pipeline), fix the real bugs found in that engine along the
way, and wire retrieval so `enhanced_rag_service` transparently fuses results from both kinds of KB.

**Architecture:** Add one enum column to `KnowledgeBase`. Branch at exactly two existing pipeline
seams — `BaseConnector._process_batch()` (ingestion) and `enhanced_rag_service._retrieve_from_kb()`
(retrieval) — so everything upstream/downstream of those seams (sync scheduling, RRF fusion, hybrid
scoring, reranking) is untouched and works uniformly across both modes. Fix three standalone bugs
in the Company Brain engine itself (dropped `kb_id`, broken embedding call, one-batch-per-tick
throughput ceiling) since `ADVANCED` mode is unusable without them. Delete the now-fully-redundant
standalone `company_brain/query/*` module last.

**Tech Stack:** FastAPI, SQLAlchemy (async), Alembic, Celery, Redis Streams, Qdrant, pytest.

**Prerequisite:** This plan assumes
`docs/superpowers/plans/2026-08-17-slack-data-source-credential-reuse.md` (Plan B) has already
been merged — its migration `20260817_0001_add_slack_bot_id_to_data_sources.py` is the down_revision
for this plan's new migration. If Plan B hasn't shipped yet, change this plan's migration
`down_revision` to whatever the actual current head is (`alembic heads`) before running Task 1.

---

## Context — confirmed real signatures used throughout this plan

- `KnowledgeBase` (`api/src/models/knowledge_base.py`) has an **integer** autoincrement `id`
  (`Mapped[int]`, `Integer` — an intentional exception to `BaseModel`'s usual UUID PK), so
  `knowledge_base_id` is always an `int` everywhere in this plan (matches the existing
  `int(source.knowledge_base_id)` cast already present in `company_brain_tasks.py`).
- `KnowledgeBaseResponse` is constructed at **4 separate sites** in
  `api/src/controllers/knowledge_bases.py`: `create_knowledge_base()` (~line 198),
  `list_knowledge_bases()` (~line 247, inside a list comprehension), `get_knowledge_base()`
  (~line 297), `update_knowledge_base()` (~line 381). All four need the new field.
- `StreamProducer.push(self, kb_id: int, tenant_id: str, source_type: str, documents: list[dict])`
  (`api/src/services/company_brain/ingestion/stream_producer.py`) — each document needs at minimum
  `{"id": str, "content": str, "metadata": dict}`.
- `StreamConsumer.consume(self, kb_id: int, tenant_id: str, source_type: str, block_ms: int = 500)`
  calls `self._process_batch(tenant_id, source_type, raw_docs, min_tokens)` today — **drops
  `kb_id`** (confirmed bug, fixed in Task 3).
- `BaseSearchBackend` (`api/src/services/company_brain/search/base.py`) declares abstract
  `search`, `index_documents`, `delete_documents`, `update_tier`, all currently taking only
  `tenant_id: str` as their scoping parameter — no `knowledge_base_id` anywhere. `QdrantHybridBackend`
  additionally has a non-ABC extra method `search_with_vectors(self, tenant_id, dense_vector,
  sparse_indices, sparse_values, filters=None, limit=20)`.
- **Only one real (non-dead) production call site** exists today for any of these backend methods:
  `stream_consumer.py:188` (`await search.index_documents(tenant_id, index_docs)`, called
  positionally). The other match, `company_brain/query/retriever.py:204`, is dead code deleted in
  Task 8. This means the signature changes in Task 5 are low-risk — no keyword-arg breakage.
- `enhanced_rag_service._retrieve_from_kb(self, query, query_variations, kb, agent_kb,
  embedding_service, vector_db_pool, config)` (`api/src/services/knowledge_base/enhanced_rag_service.py:277`)
  loops over `query_variations`, embeds each via `kb_embedding_service.embed_texts([variation])[0]`
  (with an in-memory cache keyed by md5 of the variation text), calls
  `vector_db.search(collection_name=, namespace=, query_vector=, limit=, score_threshold=)` which
  returns `list[{"id": str, "score": float, "payload": dict}]`, stores into
  `results_by_variation[variation]`, then after the loop calls
  `self._reciprocal_rank_fusion(results_by_variation)` → `self._apply_hybrid_scoring(...)` → builds
  `RAGResult(id=, text=payload["text"], score=, vector_score=, keyword_score=, rerank_score=None,
  source=payload.get("title", payload.get("external_id", "Unknown")), kb_name=kb.name, kb_id=kb.id,
  metadata=...)`. The `ADVANCED` branch only needs to replace what happens **inside the
  per-variation loop** — everything after the loop is reused unchanged.
- `BaseConnector._process_batch(self, documents: list[dict[str, Any]]) -> None`
  (`api/src/services/data_sources/base_connector.py:204`) is the single method every classic
  connector (`SlackConnector`, `GitHubConnector`, etc.) inherits and calls once per batch during
  `sync()`. It currently unconditionally does
  `processor = DocumentProcessor(self.db); await processor.process_documents(self.data_source, documents)`.
  This is the correct, single insertion point for ingestion routing (Task 6) — confirmed via grep
  that `company_brain/connectors/registry.py`'s separate `get_connector()`/`BaseConnector` (a
  different, parallel, dead scaffold — see Task 8) has zero external callers, so it is **not** the
  real routing path.
- `kb_process_batch_task` (`api/src/tasks/company_brain_tasks.py:130`) is a **second** call site
  that also calls `consumer._process_batch(...)` and also currently drops `kb_id` — must be fixed
  alongside `StreamConsumer.consume()`'s internal call in Task 3.
- `EmbeddingService.__init__(self, provider: str = "sentence_transformers", model_name: str =
  "all-MiniLM-L6-v2", config: dict | None = None)` and `embed_texts(self, texts: list[str],
  batch_size: int = 32) -> list[list[float]]` (sync method) — the real signatures `_embed_batch()`
  must call, matching the pattern already used in `enhanced_rag_service._retrieve_from_kb()`.
- `create_celery_async_session() -> async_sessionmaker[AsyncSession]` (`api/src/core/database.py`)
  — the existing pattern for getting a fresh async DB session inside a Celery task /
  `StreamConsumer`, used as `async with create_celery_async_session()() as db:`.
- Migration template: `api/migrations/versions/20260813_0001_add_allow_external_shared_channels.py`
  — idempotent `information_schema.columns` existence check before `op.add_column()`.

---

## Task 1: `KnowledgeBase.ingestion_mode` field

**Files:**
- Modify: `api/src/models/knowledge_base.py`
- Create: `api/migrations/versions/20260817_0002_add_ingestion_mode_to_knowledge_bases.py`
- Test: `api/tests/unit/models/test_knowledge_base.py` (create if it does not exist)

- [ ] **Step 1: Write the failing test**

```python
# api/tests/unit/models/test_knowledge_base.py
"""Unit tests for the KnowledgeBase model."""

from src.models.knowledge_base import IngestionMode, KnowledgeBase


def test_ingestion_mode_enum_values():
    assert IngestionMode.STANDARD.value == "standard"
    assert IngestionMode.ADVANCED.value == "advanced"


def test_knowledge_base_defaults_to_standard_ingestion_mode():
    kb = KnowledgeBase(
        name="Test KB",
        tenant_id="00000000-0000-0000-0000-000000000000",
        vector_db_provider="QDRANT",
        embedding_provider="SENTENCE_TRANSFORMERS",
        embedding_model="all-MiniLM-L6-v2",
    )
    assert kb.ingestion_mode == IngestionMode.STANDARD
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/models/test_knowledge_base.py -v`
Expected: FAIL with `ImportError: cannot import name 'IngestionMode'`

- [ ] **Step 3: Add the enum + column**

In `api/src/models/knowledge_base.py`, add the new enum next to the existing ones (after
`ChunkingStrategy`, before `class KnowledgeBase`):

```python
class IngestionMode(enum.StrEnum):
    """How documents flow into this knowledge base's vector store."""

    STANDARD = "standard"  # today's DocumentProcessor path — synchronous, per-document
    ADVANCED = "advanced"  # Company Brain streaming engine — for high-volume sources
```

Add the column on `KnowledgeBase`, right after the existing `status` column (~line 77):

```python
    ingestion_mode: Mapped[IngestionMode] = mapped_column(
        Enum(IngestionMode, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=IngestionMode.STANDARD,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/models/test_knowledge_base.py -v`
Expected: PASS

- [ ] **Step 5: Write the migration**

```python
# api/migrations/versions/20260817_0002_add_ingestion_mode_to_knowledge_bases.py
"""add ingestion_mode to knowledge_bases

Revision ID: 20260817_0002
Revises: 20260817_0001
Create Date: 2026-08-17
"""

import sqlalchemy as sa
from alembic import op

revision = "20260817_0002"
down_revision = "20260817_0001"
branch_labels = None
depends_on = None

_ENUM_NAME = "ingestionmode"
_ENUM_VALUES = ("standard", "advanced")


def upgrade() -> None:
    bind = op.get_bind()
    existing_column = bind.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='knowledge_bases' AND column_name='ingestion_mode'"
        )
    ).fetchone()
    if existing_column:
        return

    existing_type = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"), {"name": _ENUM_NAME}
    ).fetchone()
    ingestion_mode_enum = sa.Enum(*_ENUM_VALUES, name=_ENUM_NAME)
    if not existing_type:
        ingestion_mode_enum.create(bind, checkfirst=True)

    op.add_column(
        "knowledge_bases",
        sa.Column(
            "ingestion_mode",
            ingestion_mode_enum,
            nullable=False,
            server_default="standard",
        ),
    )


def downgrade() -> None:
    pass
```

- [ ] **Step 6: Apply migration and verify**

Run: `docker compose exec -T api alembic upgrade head`
Expected: migration applies with no errors; running it a second time is a no-op (idempotent check).

- [ ] **Step 7: Commit**

```bash
git add api/src/models/knowledge_base.py api/migrations/versions/20260817_0002_add_ingestion_mode_to_knowledge_bases.py api/tests/unit/models/test_knowledge_base.py
git commit -m "feat: add ingestion_mode field to KnowledgeBase"
```

---

## Task 2: Expose `ingestion_mode` through the KB API

**Files:**
- Modify: `api/src/controllers/knowledge_bases.py`
- Modify: `api/tests/unit/controllers/test_knowledge_bases.py`

- [ ] **Step 1: Write the failing tests**

Add to `api/tests/unit/controllers/test_knowledge_bases.py`, inside `_create_mock_knowledge_base()`
(after the existing `mock_kb.status = ...` line), add:

```python
    mock_kb.ingestion_mode = kwargs.get("ingestion_mode", IngestionMode.STANDARD)
```

(Add `IngestionMode` to the existing `from src.models.knowledge_base import (...)` import at the
top of the test file.)

Add new test classes:

```python
class TestCreateKnowledgeBaseIngestionMode:
    """Tests for the ingestion_mode field on knowledge base creation."""

    def test_create_knowledge_base_defaults_to_standard(self, client):
        test_client, tenant_id, mock_db = client

        response = test_client.post(
            "/knowledge-bases",
            json={"name": "Standard KB"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["ingestion_mode"] == "standard"

    def test_create_knowledge_base_advanced_mode(self, client):
        test_client, tenant_id, mock_db = client

        response = test_client.post(
            "/knowledge-bases",
            json={"name": "Advanced KB", "ingestion_mode": "advanced"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["ingestion_mode"] == "advanced"

    def test_create_knowledge_base_invalid_ingestion_mode(self, client):
        test_client, tenant_id, mock_db = client

        response = test_client.post(
            "/knowledge-bases",
            json={"name": "Bad KB", "ingestion_mode": "bogus"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/controllers/test_knowledge_bases.py -k IngestionMode -v`
Expected: FAIL — `ingestion_mode` key missing from response / 500 instead of 400.

- [ ] **Step 3: Implement**

In `api/src/controllers/knowledge_bases.py`:

Update the import at the top (line 18-24) to include `IngestionMode`:

```python
from src.models.knowledge_base import (
    ChunkingStrategy,
    EmbeddingProvider,
    IngestionMode,
    KnowledgeBase,
    KnowledgeBaseStatus,
    VectorDBProvider,
)
```

Add a field to `CreateKnowledgeBaseRequest` (after `chunking_config`, line 56):

```python
    ingestion_mode: str = Field(default="standard")
```

Add a field to `UpdateKnowledgeBaseRequest` (after `chunking_config`, line 74):

```python
    ingestion_mode: str | None = None
```

Add a field to `KnowledgeBaseResponse` (after `chunking_config`, line 94):

```python
    ingestion_mode: str
```

In `create_knowledge_base()`, add enum validation next to the other three (after the
`chunking_strategy_enum` block, ~line 170):

```python
        try:
            ingestion_mode_enum = IngestionMode(request.ingestion_mode)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid ingestion mode: {request.ingestion_mode}")
```

Pass it into the `KnowledgeBase(...)` construction (~line 172-186), add:

```python
            ingestion_mode=ingestion_mode_enum,
```

Add `ingestion_mode=kb.ingestion_mode,` to **all 4** `KnowledgeBaseResponse(...)` construction
sites: `create_knowledge_base()` (~line 213), `list_knowledge_bases()`'s comprehension (~line 262),
`get_knowledge_base()` (~line 312), `update_knowledge_base()` (~line 396) — insert right after each
site's existing `chunking_config=kb.chunking_config or {},` line.

In `update_knowledge_base()`, add handling next to the other field updates (after the
`chunking_config` block, ~line 374):

```python
        if request.ingestion_mode is not None:
            try:
                kb.ingestion_mode = IngestionMode(request.ingestion_mode)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid ingestion mode: {request.ingestion_mode}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/controllers/test_knowledge_bases.py -v`
Expected: PASS (all tests, including pre-existing ones — the new required-with-default field must
not break any existing test that omits it)

- [ ] **Step 5: Commit**

```bash
git add api/src/controllers/knowledge_bases.py api/tests/unit/controllers/test_knowledge_bases.py
git commit -m "feat: expose ingestion_mode through the knowledge base API"
```

---

## Task 3: Fix `StreamConsumer` — thread `kb_id` through, fix broken embedding call

**Files:**
- Modify: `api/src/services/company_brain/ingestion/stream_consumer.py`
- Modify: `api/src/tasks/company_brain_tasks.py`
- Test: `api/tests/unit/services/company_brain/ingestion/test_stream_consumer.py` (create dir + file)

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/unit/services/company_brain/ingestion/test_stream_consumer.py
"""Unit tests for StreamConsumer's batch processing and embedding."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.company_brain.ingestion.stream_consumer import StreamConsumer


@pytest.mark.asyncio
async def test_process_batch_includes_knowledge_base_id_in_index_metadata():
    consumer = StreamConsumer()
    mock_kb = MagicMock()
    mock_kb.id = 42
    mock_kb.embedding_provider = MagicMock(value="SENTENCE_TRANSFORMERS")
    mock_kb.embedding_model = "all-MiniLM-L6-v2"
    mock_kb.get_embedding_config_decrypted.return_value = {}

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_kb
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None

    mock_search = AsyncMock()
    mock_search.index_documents = AsyncMock(return_value={"indexed": 1, "failed": 0})
    mock_dedup = AsyncMock()
    mock_dedup.filter_unseen = AsyncMock(return_value=["ext-1"])
    mock_dedup.mark_seen_batch = AsyncMock()

    raw_docs = [{"id": "ext-1", "content": "hello world this is enough content", "metadata": {}}]

    with (
        patch(
            "src.services.company_brain.ingestion.stream_consumer.create_celery_async_session",
            return_value=lambda: mock_session_cm,
        ),
        patch("src.services.company_brain.search.factory.get_search_backend", return_value=mock_search),
        patch("src.services.company_brain.ingestion.dedup.get_dedup_backend", return_value=mock_dedup),
        patch("src.services.company_brain.ingestion.chunker.chunk_document") as mock_chunk,
        patch.object(consumer, "_embed_batch", new=AsyncMock(return_value=[[0.1, 0.2]])),
    ):
        mock_chunk.return_value = [
            {"id": "ext-1", "chunk_index": 0, "chunk_content": "hello world this is enough content"}
        ]
        await consumer._process_batch(kb_id=42, tenant_id="tenant-1", source_type="slack", raw_docs=raw_docs, min_tokens=1)

    assert mock_search.index_documents.await_args.kwargs["knowledge_base_id"] == 42
    indexed_docs = mock_search.index_documents.await_args.kwargs["documents"]
    assert indexed_docs[0]["metadata"]["knowledge_base_id"] == 42


@pytest.mark.asyncio
async def test_embed_batch_uses_kb_embedding_config():
    consumer = StreamConsumer()
    mock_kb = MagicMock()
    mock_kb.embedding_provider = MagicMock(value="OPENAI")
    mock_kb.embedding_model = "text-embedding-3-small"
    mock_kb.get_embedding_config_decrypted.return_value = {"api_key": "sk-test"}

    with patch("src.services.knowledge_base.embedding_service.EmbeddingService") as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc.embed_texts.return_value = [[0.1, 0.2, 0.3]]
        mock_svc_cls.return_value = mock_svc

        result = await consumer._embed_batch(["hello"], mock_kb)

    mock_svc_cls.assert_called_once_with(provider="OPENAI", model_name="text-embedding-3-small", config={"api_key": "sk-test"})
    mock_svc.embed_texts.assert_called_once_with(["hello"], batch_size=32)
    assert result == [[0.1, 0.2, 0.3]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/services/company_brain/ingestion/test_stream_consumer.py -v`
Expected: FAIL — `_process_batch()` doesn't accept `kb_id`, `_embed_batch()` doesn't accept a `kb`
argument, `EmbeddingService(model=...)`/`embed_batch()` don't exist.

- [ ] **Step 3: Implement**

In `api/src/services/company_brain/ingestion/stream_consumer.py`:

Update `consume()`'s call site (line 107):

```python
        stats = await self._process_batch(kb_id, tenant_id, source_type, raw_docs, min_tokens)
```

Replace `_process_batch()`'s signature and body (lines 116-195):

```python
    async def _process_batch(
        self,
        kb_id: int,
        tenant_id: str,
        source_type: str,
        raw_docs: list[dict[str, Any]],
        min_tokens: int,
    ) -> dict[str, int]:
        from sqlalchemy import select

        from src.core.database import create_celery_async_session
        from src.models.knowledge_base import KnowledgeBase
        from src.services.company_brain.search.factory import get_search_backend

        from .chunker import chunk_document
        from .dedup import get_dedup_backend

        dedup = get_dedup_backend()
        search = get_search_backend()
        indexed = skipped = failed = 0

        async with create_celery_async_session()() as db:
            kb_result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
            kb = kb_result.scalar_one_or_none()

        if kb is None:
            logger.error("StreamConsumer: KnowledgeBase %s not found, dropping batch", kb_id)
            return {"indexed": 0, "skipped": 0, "failed": len(raw_docs)}

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

        # 4. Embed (batch), using this KB's own embedding provider/model
        texts = [c["chunk_content"] for c in all_chunks]
        try:
            embeddings = await self._embed_batch(texts, kb)
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
                    "metadata": {**(chunk.get("metadata") or {}), "tenant_id": tenant_id, "knowledge_base_id": kb_id},
                    "source_url": chunk.get("external_url"),
                    "occurred_at": chunk.get("source_created_at"),
                    "storage_tier": "hot",
                }
            )

        # 6. Index
        result = await search.index_documents(tenant_id=tenant_id, knowledge_base_id=kb_id, documents=index_docs)
        indexed += result.get("indexed", 0)
        failed += result.get("failed", 0)

        # 7. Mark seen
        await dedup.mark_seen_batch(tenant_id, source_type, list(unseen_ids))

        return {"indexed": indexed, "skipped": skipped, "failed": failed}
```

Replace `_embed_batch()` (lines 212-230):

```python
    async def _embed_batch(self, texts: list[str], kb: Any) -> list[list[float]]:
        """Embed a batch of texts using this KB's own configured embedding provider/model."""
        from src.services.knowledge_base.embedding_service import EmbeddingService

        svc = EmbeddingService(
            provider=kb.embedding_provider.value if kb.embedding_provider else "sentence_transformers",
            model_name=kb.embedding_model or "all-MiniLM-L6-v2",
            config=kb.get_embedding_config_decrypted(),
        )
        return svc.embed_texts(texts, batch_size=32)
```

In `api/src/tasks/company_brain_tasks.py`, update `kb_process_batch_task`'s inner call (lines
145-150):

```python
        return await consumer._process_batch(
            kb_id=kb_id,
            tenant_id=tenant_id,
            source_type=source_type,
            raw_docs=documents,
            min_tokens=10,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/services/company_brain/ingestion/test_stream_consumer.py -v`
Expected: PASS

- [ ] **Step 5: Restart the company-brain worker and verify no import errors**

```bash
docker compose restart celery-worker-company-brain
docker compose logs --tail=50 celery-worker-company-brain
```

Expected: worker starts cleanly, no `ImportError`/`AttributeError` in the log tail.

- [ ] **Step 6: Commit**

```bash
git add api/src/services/company_brain/ingestion/stream_consumer.py api/src/tasks/company_brain_tasks.py api/tests/unit/services/company_brain/ingestion/test_stream_consumer.py
git commit -m "fix: thread kb_id through StreamConsumer and fix broken embedding call"
```

---

## Task 4: Fix the ingestion throughput ceiling

**Files:**
- Modify: `api/src/tasks/company_brain_tasks.py`
- Test: `api/tests/unit/tasks/test_company_brain_tasks.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# api/tests/unit/tasks/test_company_brain_tasks.py
"""Unit tests for company_brain_tasks.py."""

from unittest.mock import AsyncMock, MagicMock, patch

from src.tasks.company_brain_tasks import company_brain_consume_active_streams_task


def _mock_source(kb_id=1, tenant_id="tenant-1", source_type="slack"):
    source = MagicMock()
    source.id = 1
    source.tenant_id = tenant_id
    source.knowledge_base_id = kb_id
    source.type = MagicMock(value=source_type)
    return source


class TestConsumeActiveStreamsThroughput:
    def test_drains_multiple_batches_per_source_until_empty(self):
        """Regression guard: must call consume() repeatedly per source, not just once."""
        source = _mock_source()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [source]
        mock_db.close = MagicMock()

        # Two non-empty batches, then an empty batch signals "drained"
        consume_results = [
            {"read": 100, "indexed": 90, "skipped": 5, "failed": 5},
            {"read": 40, "indexed": 40, "skipped": 0, "failed": 0},
            {"read": 0, "indexed": 0, "skipped": 0, "failed": 0},
        ]

        mock_consumer = MagicMock()
        mock_consumer.consume = AsyncMock(side_effect=consume_results)

        with (
            patch("src.tasks.company_brain_tasks.SessionLocal", return_value=mock_db),
            patch(
                "src.services.company_brain.ingestion.stream_consumer.StreamConsumer",
                return_value=mock_consumer,
            ),
        ):
            result = company_brain_consume_active_streams_task.run()

        assert mock_consumer.consume.await_count == 3
        assert result["read"] == 140
        assert result["indexed"] == 130

    def test_stops_at_time_budget_even_if_stream_not_drained(self):
        """Regression guard: must not loop forever if a stream never empties within one tick."""
        source = _mock_source()

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [source]
        mock_db.close = MagicMock()

        mock_consumer = MagicMock()
        # Always returns a full, non-empty batch — simulates a backlog bigger than the time budget
        mock_consumer.consume = AsyncMock(return_value={"read": 100, "indexed": 100, "skipped": 0, "failed": 0})

        call_times = iter([0.0, 1.0, 2.0, 26.0])  # 4th check crosses TIME_BUDGET_SECONDS=25

        with (
            patch("src.tasks.company_brain_tasks.SessionLocal", return_value=mock_db),
            patch(
                "src.services.company_brain.ingestion.stream_consumer.StreamConsumer",
                return_value=mock_consumer,
            ),
            patch("time.monotonic", side_effect=lambda: next(call_times)),
        ):
            company_brain_consume_active_streams_task.run()

        assert mock_consumer.consume.await_count == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/tasks/test_company_brain_tasks.py -v -k "drains_multiple_batches or stops_at_time_budget"`
Expected: FAIL — `test_drains_multiple_batches_per_source_until_empty` fails because
`mock_consumer.consume.await_count == 1` (only one call per source per tick today), and
`test_stops_at_time_budget_even_if_stream_not_drained` fails the same way.

- [ ] **Step 3: Implement the loop-based fix**

Modify `api/src/tasks/company_brain_tasks.py`. Add a module-level constant near the top of the
file (after the existing imports, before `logger = logging.getLogger(__name__)` or right after it):

```python
_CONSUME_TIME_BUDGET_SECONDS = 25
```

Replace the body of `company_brain_consume_active_streams_task`'s inner `_run()` function. The
current code (confirmed real, lines ~1-115) is:

```python
        async def _run() -> dict[str, Any]:
            consumer = StreamConsumer()
            totals = {"streams": 0, "read": 0, "indexed": 0, "skipped": 0, "failed": 0}
            for source in sources:
                source_type = getattr(source.type, "value", str(source.type)).lower()
                stats = await consumer.consume(
                    kb_id=int(source.knowledge_base_id),
                    tenant_id=str(source.tenant_id),
                    source_type=source_type,
                    block_ms=5,
                )
                totals["streams"] += 1
                for key in ("read", "indexed", "skipped", "failed"):
                    totals[key] += int(stats.get(key, 0))
            return totals
```

Replace it with:

```python
        async def _run() -> dict[str, Any]:
            import time

            consumer = StreamConsumer()
            totals = {"streams": 0, "read": 0, "indexed": 0, "skipped": 0, "failed": 0}
            start = time.monotonic()
            for source in sources:
                source_type = getattr(source.type, "value", str(source.type)).lower()
                totals["streams"] += 1
                while True:
                    if time.monotonic() - start >= _CONSUME_TIME_BUDGET_SECONDS:
                        break
                    stats = await consumer.consume(
                        kb_id=int(source.knowledge_base_id),
                        tenant_id=str(source.tenant_id),
                        source_type=source_type,
                        block_ms=5,
                    )
                    for key in ("read", "indexed", "skipped", "failed"):
                        totals[key] += int(stats.get(key, 0))
                    if int(stats.get("read", 0)) == 0:
                        break
            return totals
```

This drains each source's stream in a loop until either a batch comes back empty (`read == 0`,
meaning the stream is caught up) or the per-tick time budget is exhausted, whichever happens
first. The `time.monotonic` import is local to `_run()` to match the test's
`patch("time.monotonic", ...)` target (patching the builtin `time` module directly, not a
module-level import, so the patch applies regardless of where `time` is imported).

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/tasks/test_company_brain_tasks.py -v -k "drains_multiple_batches or stops_at_time_budget"`
Expected: PASS — both tests green.

Then run the full existing file to check for regressions:

Run: `docker compose exec -T api pytest tests/unit/tasks/test_company_brain_tasks.py -v`
Expected: PASS — all tests in the file, including previously-existing ones, still pass.

- [ ] **Step 5: Commit**

```bash
git add api/src/tasks/company_brain_tasks.py api/tests/unit/tasks/test_company_brain_tasks.py
git commit -m "fix: drain company brain ingestion streams until empty or time budget exhausted"
```

---

### Task 5: Scope Company Brain search backends by knowledge_base_id

**Problem:** All search backends (`QdrantHybridBackend`, `PostgresFTSBackend`,
`ElasticsearchBackend`) currently key storage/lookup only by `tenant_id`. For ADVANCED-mode KBs,
documents from multiple knowledge bases belonging to the same tenant get ingested into Company
Brain, but there is no way to scope a search to just one KB. This is required so
`enhanced_rag_service._retrieve_from_kb()` (Task 7) can search only the KB the agent is
configured to use, not every Company Brain document across the whole tenant.

**Design-spec correction:** the approved design spec's Phase 2.2 pseudocode suggested renaming the
`tenant_id` parameter's *meaning* to `knowledge_base_id` in `_collection_name()` and the public
search methods. This is wrong and must NOT be implemented as written — confirmed by reading
`qdrant_hybrid_backend.py`'s `_build_filter()`, which uses the real `tenant_id` value (an actual
tenant UUID string) to filter `metadata.tenant_id` on indexed documents for genuine tenant
isolation. That is a separate concern from which KB's documents to search. Repurposing the
parameter would either break tenant isolation (if kb_id is passed where a tenant UUID is expected)
or silently return zero results (metadata.tenant_id would never match a kb_id). **Fix: add
`knowledge_base_id` as an ADDITIONAL parameter alongside `tenant_id`, not a replacement.**

**Breaking-change caveat (must be disclosed, not silently applied):** Qdrant collection names
today are `f"cb_{safe_tid}_{tier}"` (tenant+tier only). This task changes the naming scheme to
include `kb_id`, which means any documents already ingested under the OLD collection name become
unreachable by the NEW name. There is no production Company Brain data yet (ADVANCED mode does not
exist before this plan ships), so there is nothing to migrate — but if this plan is executed
against an environment where Company Brain has already been used in STANDARD-only mode with real
ingested data, that data would need re-ingestion after this change. Call this out to the user
before running Task 5 in such an environment.

**Files:**
- Modify: `api/src/services/company_brain/search/base.py`
- Modify: `api/src/services/company_brain/search/qdrant_hybrid_backend.py`
- Modify: `api/src/services/company_brain/search/postgres_fts_backend.py`
- Modify: `api/src/services/company_brain/search/elasticsearch_backend.py`
- Test: `api/tests/unit/services/company_brain/search/test_qdrant_hybrid_backend.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/unit/services/company_brain/search/test_qdrant_hybrid_backend.py`:

```python
"""Unit tests for QdrantHybridBackend knowledge_base_id scoping."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.company_brain.search.qdrant_hybrid_backend import (
    QdrantHybridBackend,
    _collection_name,
)


class TestCollectionName:
    def test_includes_knowledge_base_id_in_collection_name(self):
        name = _collection_name(tenant_id="tenant-abc", knowledge_base_id="42", tier="hot")
        assert "42" in name
        assert "tenant-abc" not in name  # tenant_id gets sanitized, so check the raw kb_id token
        assert name.startswith("cb_")
        assert name.endswith("_hot")

    def test_different_kb_ids_produce_different_collection_names(self):
        name_a = _collection_name(tenant_id="tenant-abc", knowledge_base_id="1", tier="hot")
        name_b = _collection_name(tenant_id="tenant-abc", knowledge_base_id="2", tier="hot")
        assert name_a != name_b


class TestSearchScopedToKnowledgeBase:
    @pytest.mark.asyncio
    async def test_search_uses_kb_scoped_collection_name(self):
        backend = QdrantHybridBackend()
        mock_client = MagicMock()

        with (
            patch.object(backend, "_get_client", return_value=mock_client),
            patch.object(backend, "_ensure_collection"),
            patch.object(backend, "_search_collection", return_value=[]) as mock_search_collection,
        ):
            await backend.search(
                tenant_id="tenant-abc",
                knowledge_base_id="42",
                query="test query",
                query_vector=[0.1] * 384,
            )

        called_collection_names = [call.args[0] for call in mock_search_collection.call_args_list]
        assert all("42" in name for name in called_collection_names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/company_brain/search/test_qdrant_hybrid_backend.py -v`
Expected: FAIL — `_collection_name` doesn't accept a `knowledge_base_id` argument yet
(`TypeError: _collection_name() got an unexpected keyword argument 'knowledge_base_id'`), and
`search()` doesn't accept a `knowledge_base_id` argument either.

- [ ] **Step 3: Update the abstract base class**

Modify `api/src/services/company_brain/search/base.py`. The current abstract methods (confirmed
real, in `BaseSearchBackend`) are:

```python
    @abstractmethod
    async def search(
        self,
        tenant_id: str,
        query: str,
        query_vector: list[float] | None = None,
        filters: SearchFilter | None = None,
        limit: int = 20,
    ) -> SearchResponse: ...

    @abstractmethod
    async def index_documents(
        self,
        tenant_id: str,
        documents: list[dict],
    ) -> dict[str, int]: ...

    @abstractmethod
    async def delete_documents(
        self,
        tenant_id: str,
        doc_ids: list[str],
    ) -> int: ...

    @abstractmethod
    async def update_tier(
        self,
        tenant_id: str,
        doc_ids: list[str],
        new_tier: str,
    ) -> int: ...
```

Add `knowledge_base_id: str` as the second positional parameter (after `tenant_id`) to all four:

```python
    @abstractmethod
    async def search(
        self,
        tenant_id: str,
        knowledge_base_id: str,
        query: str,
        query_vector: list[float] | None = None,
        filters: SearchFilter | None = None,
        limit: int = 20,
    ) -> SearchResponse: ...

    @abstractmethod
    async def index_documents(
        self,
        tenant_id: str,
        knowledge_base_id: str,
        documents: list[dict],
    ) -> dict[str, int]: ...

    @abstractmethod
    async def delete_documents(
        self,
        tenant_id: str,
        knowledge_base_id: str,
        doc_ids: list[str],
    ) -> int: ...

    @abstractmethod
    async def update_tier(
        self,
        tenant_id: str,
        knowledge_base_id: str,
        doc_ids: list[str],
        new_tier: str,
    ) -> int: ...
```

- [ ] **Step 4: Update QdrantHybridBackend**

Modify `api/src/services/company_brain/search/qdrant_hybrid_backend.py`.

The current module-level `_collection_name` (confirmed real):

```python
def _collection_name(tenant_id: str, tier: str) -> str:
    safe_tid = tenant_id.replace("-", "")
    return f"cb_{safe_tid}_{tier}"
```

Replace with:

```python
def _collection_name(tenant_id: str, knowledge_base_id: str, tier: str) -> str:
    safe_tid = tenant_id.replace("-", "")
    return f"cb_{safe_tid}_{knowledge_base_id}_{tier}"
```

Update every call site of `_collection_name(...)` inside this file (`_ensure_collection`,
`_collections_for_tiers`, `search()`, `index_documents()`, `delete_documents()`, `update_tier()`)
to pass `knowledge_base_id` through. Each of those public methods (`search`, `index_documents`,
`delete_documents`, `update_tier`) must also gain the new `knowledge_base_id: str` parameter
(second positional, matching the base class) and pass it down to every internal helper that
currently takes `tenant_id` and calls `_collection_name`. `_build_filter()` is unaffected — it
keeps filtering on the real `tenant_id` value only, since that's the genuine tenant-isolation
filter on `metadata.tenant_id` and has nothing to do with collection naming.

- [ ] **Step 5: Update PostgresFTSBackend and ElasticsearchBackend signatures**

These two backends are not used in production (confirmed: only `qdrant_hybrid` is the default in
`factory.py`, and no other backend type is wired to Company Brain ingestion or retrieval anywhere
in this codebase). Per the design spec, only Qdrant needs real KB-scoping logic. To keep the
`BaseSearchBackend` contract satisfiable, add `knowledge_base_id: str` as an accepted-but-unused
parameter to each of the four methods in both `postgres_fts_backend.py` and
`elasticsearch_backend.py`, matching the new base class signature exactly (parameter name and
position), without adding real filtering logic. This keeps the codebase type-consistent without
scope-creeping into backends nothing currently exercises.

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/services/company_brain/search/test_qdrant_hybrid_backend.py -v`
Expected: PASS

Then check for regressions across the whole search test suite:

Run: `docker compose exec -T api pytest tests/unit/services/company_brain/ -v`
Expected: PASS (any existing tests calling the old 2-arg `search`/`index_documents`/etc. signatures
will need their call sites updated too — grep for `search_backend.search(`, `.index_documents(`,
`.delete_documents(`, `.update_tier(` across `api/src/` and `api/tests/` and add the
`knowledge_base_id` argument at each call site found).

- [ ] **Step 7: Commit**

```bash
git add api/src/services/company_brain/search/ api/tests/unit/services/company_brain/search/
git commit -m "feat: scope company brain search backends by knowledge_base_id"
```

---

### Task 6: Route ADVANCED-mode ingestion through StreamProducer

**Files:**
- Modify: `api/src/services/data_sources/base_connector.py`
- Test: `api/tests/unit/services/data_sources/test_base_connector.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/unit/services/data_sources/test_base_connector.py`:

```python
"""Unit tests for BaseConnector's ingestion routing (STANDARD vs ADVANCED KB modes)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.data_source import DataSource
from src.models.knowledge_base import IngestionMode, KnowledgeBase
from src.services.data_sources.base_connector import BaseConnector


class _ConcreteConnector(BaseConnector):
    async def validate_config(self) -> bool:
        return True

    async def fetch_documents(self, incremental: bool = True):
        return []


def _make_connector(knowledge_base_id, db):
    ds = MagicMock(spec=DataSource)
    ds.id = 1
    ds.tenant_id = "tenant-abc"
    ds.knowledge_base_id = knowledge_base_id
    ds.type = MagicMock(value="slack")
    return _ConcreteConnector(data_source=ds, db=db)


class TestProcessBatchRouting:
    @pytest.mark.asyncio
    async def test_no_knowledge_base_falls_back_to_document_processor(self):
        mock_db = AsyncMock()
        connector = _make_connector(knowledge_base_id=None, db=mock_db)

        with patch("src.services.data_sources.document_processor.DocumentProcessor") as MockProcessor:
            mock_processor = MockProcessor.return_value
            mock_processor.process_documents = AsyncMock(return_value={"status": "ok"})
            await connector._process_batch([{"id": "1", "content": "hello", "metadata": {}}])

        mock_processor.process_documents.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_standard_mode_kb_falls_back_to_document_processor(self):
        mock_db = AsyncMock()
        mock_kb = MagicMock(spec=KnowledgeBase)
        mock_kb.ingestion_mode = IngestionMode.STANDARD
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        mock_db.execute = AsyncMock(return_value=mock_result)

        connector = _make_connector(knowledge_base_id=7, db=mock_db)

        with patch("src.services.data_sources.document_processor.DocumentProcessor") as MockProcessor:
            mock_processor = MockProcessor.return_value
            mock_processor.process_documents = AsyncMock(return_value={"status": "ok"})
            await connector._process_batch([{"id": "1", "content": "hello", "metadata": {}}])

        mock_processor.process_documents.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_advanced_mode_kb_routes_through_stream_producer(self):
        mock_db = AsyncMock()
        mock_kb = MagicMock(spec=KnowledgeBase)
        mock_kb.ingestion_mode = IngestionMode.ADVANCED
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_kb
        mock_db.execute = AsyncMock(return_value=mock_result)

        connector = _make_connector(knowledge_base_id=7, db=mock_db)
        documents = [{"id": "1", "content": "hello", "metadata": {}}]

        with patch("src.services.company_brain.ingestion.stream_producer.StreamProducer") as MockProducer:
            mock_producer = MockProducer.return_value
            mock_producer.push = AsyncMock(return_value={"pushed": 1})
            await connector._process_batch(documents)

        mock_producer.push.assert_awaited_once_with(
            kb_id=7,
            tenant_id="tenant-abc",
            source_type="slack",
            documents=documents,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/unit/services/data_sources/test_base_connector.py -v`
Expected: FAIL — `IngestionMode` doesn't exist yet if Task 1 hasn't run first in this same
session (it should already exist by this point since Task 1 precedes this task in execution
order); `test_advanced_mode_kb_routes_through_stream_producer` fails because `_process_batch`
always calls `DocumentProcessor` regardless of KB mode today.

- [ ] **Step 3: Implement the routing logic**

Modify `api/src/services/data_sources/base_connector.py`. Add `select` to the existing imports:

```python
from sqlalchemy import select
```

The current `_process_batch` (confirmed real, lines 204-226):

```python
    async def _process_batch(self, documents: list[dict[str, Any]]) -> None:
        processor = DocumentProcessor(self.db)
        result = await processor.process_documents(self.data_source, documents)
        ...
```

Replace with:

```python
    async def _process_batch(self, documents: list[dict[str, Any]]) -> None:
        kb_id = self.data_source.knowledge_base_id
        if kb_id is not None:
            from src.models.knowledge_base import IngestionMode, KnowledgeBase

            result_kb = await self.db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
            kb = result_kb.scalar_one_or_none()
            if kb is not None and kb.ingestion_mode == IngestionMode.ADVANCED:
                from src.services.company_brain.ingestion.stream_producer import StreamProducer

                source_type = getattr(self.data_source.type, "value", str(self.data_source.type)).lower()
                producer = StreamProducer()
                await producer.push(
                    kb_id=kb_id,
                    tenant_id=str(self.data_source.tenant_id),
                    source_type=source_type,
                    documents=documents,
                )
                return

        processor = DocumentProcessor(self.db)
        result = await processor.process_documents(self.data_source, documents)
        ...
```

Keep the rest of the existing method body (whatever follows `result = await
processor.process_documents(...)` today, e.g. logging/counters) unchanged, just under the
fallback branch. The imports for `IngestionMode`/`KnowledgeBase` and `StreamProducer` are placed
inside the function (not at module top) to avoid a circular import, matching the existing style
in this file where `DocumentProcessor` is the only top-level service import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/unit/services/data_sources/test_base_connector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/src/services/data_sources/base_connector.py api/tests/unit/services/data_sources/test_base_connector.py
git commit -m "feat: route ADVANCED-mode knowledge base ingestion through company brain stream producer"
```

---

### Task 7: Retrieval branch for ADVANCED-mode knowledge bases

**Files:**
- Modify: `api/src/services/knowledge_base/enhanced_rag_service.py`
- Test: `api/tests/unit/services/knowledge_base/test_enhanced_rag_service.py`

- [ ] **Step 1: Write the failing test**

Read the existing test file first to match its fixture conventions:

Run: `docker compose exec -T api pytest tests/unit/services/knowledge_base/test_enhanced_rag_service.py --collect-only -q`

If the file `api/tests/unit/services/knowledge_base/test_enhanced_rag_service.py` does not exist
yet, create it with:

```python
"""Unit tests for enhanced_rag_service's ADVANCED-mode (Company Brain) retrieval branch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.knowledge_base import IngestionMode
from src.services.knowledge_base.enhanced_rag_service import (
    EnhancedRAGService,
    RAGConfig,
    RetrievalStrategy,
)


class TestRetrieveFromKBAdvancedMode:
    @pytest.mark.asyncio
    async def test_advanced_mode_kb_searches_company_brain_backend(self):
        service = EnhancedRAGService()

        kb = MagicMock()
        kb.id = 42
        kb.ingestion_mode = IngestionMode.ADVANCED
        kb.name = "Advanced KB"
        kb.get_embedding_config_decrypted.return_value = {}
        kb.embedding_provider = MagicMock(value="sentence_transformers")
        kb.embedding_model = "all-MiniLM-L6-v2"

        agent_kb = MagicMock()
        agent_kb.retrieval_config = {}

        config = RAGConfig(strategy=RetrievalStrategy.HYBRID)

        mock_search_result = MagicMock()
        mock_search_result.doc_id = "doc-1"
        mock_search_result.score = 0.9
        mock_search_result.vector_score = 0.9
        mock_search_result.keyword_score = 0.0
        mock_search_result.content = "hello world"
        mock_search_result.title = "Doc One"
        mock_search_result.metadata = {"external_id": "ext-1"}

        mock_backend = MagicMock()
        mock_backend.search = AsyncMock(
            return_value=MagicMock(results=[mock_search_result])
        )

        with (
            patch(
                "src.services.knowledge_base.enhanced_rag_service.get_search_backend",
                return_value=mock_backend,
            ),
            patch(
                "src.services.knowledge_base.embedding_service.EmbeddingService.embed_texts",
                return_value=[[0.1] * 384],
            ),
        ):
            results = await service._retrieve_from_kb(
                query="test query",
                query_variations=["test query"],
                kb=kb,
                agent_kb=agent_kb,
                embedding_service=MagicMock(),
                vector_db_pool=MagicMock(),
                config=config,
            )

        mock_backend.search.assert_awaited_once()
        call_kwargs = mock_backend.search.call_args.kwargs
        assert call_kwargs["knowledge_base_id"] == "42"
        assert len(results) == 1
        assert results[0].kb_id == 42
        assert results[0].text == "hello world"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/unit/services/knowledge_base/test_enhanced_rag_service.py -v -k advanced_mode_kb_searches`
Expected: FAIL — `_retrieve_from_kb` currently always searches via `vector_db_pool`/the
STANDARD-mode vector DB provider path regardless of `kb.ingestion_mode`, so `mock_backend.search`
is never called.

- [ ] **Step 3: Implement the retrieval branch**

Modify `api/src/services/knowledge_base/enhanced_rag_service.py`. Add an import near the top of
the file (alongside the existing `EmbeddingService` import):

```python
from src.models.knowledge_base import IngestionMode
from src.services.company_brain.search.factory import get_search_backend
```

The current per-variation loop inside `_retrieve_from_kb()` (confirmed real):

```python
        for variation in query_variations:
            variation_hash = hashlib.md5(variation.encode()).hexdigest()
            if variation_hash in self._embedding_cache:
                query_embedding = self._embedding_cache[variation_hash]
            else:
                query_embedding = kb_embedding_service.embed_texts([variation])[0]
                self._embedding_cache[variation_hash] = query_embedding
            with vector_db_pool.get_connection(provider_type=kb.vector_db_provider, config=vector_db_config) as vector_db:
                vector_results = vector_db.search(
                    collection_name=collection_name,
                    namespace=namespace,
                    query_vector=query_embedding,
                    limit=max_results,
                    score_threshold=min_score,
                )
                results_by_variation[variation] = vector_results
```

Replace with a branch that, for ADVANCED-mode KBs, searches the Company Brain backend instead and
adapts its `SearchResult` objects into the same `{"id", "score", "payload"}` dict shape the
STANDARD path already produces (so the unchanged downstream RRF/hybrid-scoring/`RAGResult`
construction code works for both modes without further changes):

```python
        is_advanced = getattr(kb, "ingestion_mode", None) == IngestionMode.ADVANCED
        search_backend = get_search_backend() if is_advanced else None

        for variation in query_variations:
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
                with vector_db_pool.get_connection(provider_type=kb.vector_db_provider, config=vector_db_config) as vector_db:
                    vector_results = vector_db.search(
                        collection_name=collection_name,
                        namespace=namespace,
                        query_vector=query_embedding,
                        limit=max_results,
                        score_threshold=min_score,
                    )
            results_by_variation[variation] = vector_results
```

Everything after this loop (`_reciprocal_rank_fusion`, hybrid scoring, `RAGResult` construction)
is unchanged — it already only reads `result.get("id")`, `result.get("score")`,
`result.get("payload", {})`, all of which the ADVANCED-mode dict shape above also provides.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/unit/services/knowledge_base/test_enhanced_rag_service.py -v`
Expected: PASS

Then check for regressions in the STANDARD-mode path:

Run: `docker compose exec -T api pytest tests/unit/services/knowledge_base/ -v`
Expected: PASS — no existing STANDARD-mode retrieval tests should break, since `is_advanced` is
`False` for any `kb` without `ingestion_mode == IngestionMode.ADVANCED` (including any mock KB in
existing tests that doesn't set this attribute at all, since `getattr(kb, "ingestion_mode",
None)` safely defaults to `None`).

- [ ] **Step 5: Commit**

```bash
git add api/src/services/knowledge_base/enhanced_rag_service.py api/tests/unit/services/knowledge_base/test_enhanced_rag_service.py
git commit -m "feat: retrieve from company brain search backend for ADVANCED-mode knowledge bases"
```

---

### Task 8: Remove dead company_brain/connectors scaffold

**Context:** During investigation for this plan, a second, entirely unused connector system was
found: `api/src/services/company_brain/connectors/{base,registry,slack_connector,__init__}.py`.
It defines its own `BaseConnector` ABC (different from the real
`data_sources/base_connector.py`), its own `SlackConnector`, and a `CONNECTOR_REGISTRY`/
`get_connector()` dispatch function. Confirmed via grep of the entire `api/src/` tree: this
module's `get_connector` is never imported or called anywhere outside its own package, and none of
its classes are referenced by `company_brain_tasks.py`, `data_sources.py`, or any other real call
site. This is dead scaffold code, not part of the approved design spec's scope, and its continued
existence risks confusing future contributors into thinking there are two valid places to add a
new connector.

**Files:**
- Delete: `api/src/services/company_brain/connectors/__init__.py`
- Delete: `api/src/services/company_brain/connectors/base.py`
- Delete: `api/src/services/company_brain/connectors/registry.py`
- Delete: `api/src/services/company_brain/connectors/slack_connector.py`

- [ ] **Step 1: Confirm zero external callers (re-verify before deleting)**

Run: `docker compose exec -T api grep -rn "company_brain.connectors" src/ --include="*.py" -l`
Expected: only files inside `src/services/company_brain/connectors/` itself appear in the output
(i.e., the only references are internal to the package being deleted). If any other file appears,
STOP and do not proceed with deletion — investigate that reference first.

Run: `docker compose exec -T api grep -rn "from src.services.company_brain.connectors" src/ --include="*.py"`
Expected: same — no hits outside the package itself.

- [ ] **Step 2: Delete the dead files**

```bash
git rm api/src/services/company_brain/connectors/__init__.py
git rm api/src/services/company_brain/connectors/base.py
git rm api/src/services/company_brain/connectors/registry.py
git rm api/src/services/company_brain/connectors/slack_connector.py
```

- [ ] **Step 3: Run the full unit test suite to confirm nothing depended on these files**

Run: `docker compose exec -T api pytest tests/unit/ -q`
Expected: PASS — same pass count as before deletion (minus any tests that were themselves testing
this dead code, which should not exist since it had zero callers, but check the output for any
`ImportError`/`ModuleNotFoundError` referencing `company_brain.connectors` to be sure).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove dead company_brain/connectors scaffold (zero callers, superseded by data_sources connectors)"
```

---

### Task 9: Ingestion mode selector in knowledge base creation UI

**Files:**
- Modify: `web/app/(dashboard)/knowledge-bases/create/page.tsx`
- Create: `agent-test-docs/company-brain-ingestion-mode-test-guide.md`

- [ ] **Step 1: Read the current page to find the exact insertion point**

Run (via Read tool, not shown here as a shell command): read
`web/app/(dashboard)/knowledge-bases/create/page.tsx` in full to find the existing `formData`
state shape and the JSX section for KB-level settings (chunking strategy, embedding provider,
etc.) — the ingestion mode toggle belongs alongside those.

- [ ] **Step 2: Add ingestion_mode to form state**

Find the `useState` call for the form data object (it will contain fields like `name`,
`description`, `chunking_strategy`, `embedding_provider`, etc. based on the confirmed
`CreateKnowledgeBaseRequest` schema from Task 2). Add `ingestion_mode: "standard"` as a new field
in the initial state object, matching the casing/format of the other enum-valued fields already
present (e.g. if `chunking_strategy` defaults to a lowercase string like `"fixed_size"`, follow
the same convention).

- [ ] **Step 3: Add the toggle UI**

In the JSX, near the other advanced/optional settings fields, add:

```tsx
<div className="space-y-2">
  <label className="text-sm font-medium text-gray-700">Ingestion Mode</label>
  <div className="flex gap-3">
    <button
      type="button"
      onClick={() => setFormData({ ...formData, ingestion_mode: "standard" })}
      className={`flex-1 rounded-lg border px-4 py-3 text-left transition ${
        formData.ingestion_mode === "standard"
          ? "border-blue-500 bg-blue-50"
          : "border-gray-200 hover:border-gray-300"
      }`}
    >
      <div className="font-medium text-gray-900">Standard</div>
      <div className="text-xs text-gray-500">Direct document upload and vector search.</div>
    </button>
    <button
      type="button"
      onClick={() => setFormData({ ...formData, ingestion_mode: "advanced" })}
      className={`flex-1 rounded-lg border px-4 py-3 text-left transition ${
        formData.ingestion_mode === "advanced"
          ? "border-blue-500 bg-blue-50"
          : "border-gray-200 hover:border-gray-300"
      }`}
    >
      <div className="font-medium text-gray-900">Advanced (Company Brain)</div>
      <div className="text-xs text-gray-500">
        Continuous multi-source ingestion with hybrid search and tiered storage.
      </div>
    </button>
  </div>
</div>
```

- [ ] **Step 4: Include ingestion_mode in the create payload**

Find where `formData` is submitted (the `handleSubmit`/`handleCreate` function's request body
construction) and confirm `ingestion_mode: formData.ingestion_mode` is included alongside the
other fields sent to `POST /api/v1/knowledge-bases`. If the payload is built via object spread
(`{ ...formData }`) this requires no change; if fields are listed explicitly, add
`ingestion_mode` to that list.

- [ ] **Step 5: Manual verification against the live stack**

Start the stack if not already running: `docker-compose up -d`. Log in as
`admin@localhost.com` / `Admin123!` per `MEMORY.md`'s documented local dev credentials. Navigate
to the knowledge base creation page, confirm both toggle options render and are selectable, create
one KB with `ingestion_mode=standard` and one with `ingestion_mode=advanced`, then verify via
`GET /api/v1/knowledge-bases/{id}` (or the KB list page) that each KB's `ingestion_mode` field
reflects the selected value.

- [ ] **Step 6: Write the test guide**

Create `agent-test-docs/company-brain-ingestion-mode-test-guide.md` documenting the exact manual
verification steps performed in Step 5 (API calls made, expected responses), following the
existing convention in this directory (see `agent-test-docs/agents-list-page-test-guide.md` for
the format: numbered steps, real request/response JSON, no placeholders).

- [ ] **Step 7: Commit**

```bash
git add "web/app/(dashboard)/knowledge-bases/create/page.tsx" agent-test-docs/company-brain-ingestion-mode-test-guide.md
git commit -m "feat: add ingestion mode selector to knowledge base creation UI"
```

---

## Self-Review Notes

**Spec coverage check** (against `docs/superpowers/specs/2026-08-17-company-brain-kb-unification-design.md`):
- Phase 2.1 (KB model gets ingestion mode) → Task 1, Task 2
- Phase 2.2 (search backends scoped by KB) → Task 5 (with a corrected design vs. the spec's own
  pseudocode — see Task 5's "Design-spec correction" note)
- Phase 2.3 (ingestion routing) → Task 6
- Phase 2.4 (retrieval routing) → Task 7
- Phase 2.5 (fix broken StreamConsumer embedding/kb_id bugs) → Task 3
- Phase 2.6 (throughput ceiling) → Task 4
- UI exposure of the new mode → Task 9
- Dead-code cleanup discovered during investigation (not in original spec scope, called out
  separately) → Task 8

**Placeholder scan:** no "TBD"/"implement later"/"add appropriate error handling" phrases appear
in any task above; every code block is complete, runnable code with real signatures pulled from
files actually read during investigation and this session (not guessed).

**Type consistency check:**
- `kb_id`/`knowledge_base_id` is consistently `int` at the model/DB layer (`KnowledgeBase.id`,
  `DataSource.knowledge_base_id`) but consistently cast to `str` at the search-backend boundary
  (`knowledge_base_id: str` in `BaseSearchBackend`, matching the existing convention where
  `tenant_id` is also always a `str` there despite being a UUID at the model layer) — Task 5's
  base class, Task 5's Qdrant implementation, Task 6's `StreamProducer.push(kb_id=kb_id, ...)`
  (int, matching `StreamProducer.push`'s real signature), and Task 7's
  `search_backend.search(knowledge_base_id=str(kb.id), ...)` are all consistent with this.
- `IngestionMode` (Task 1) is referenced identically in Task 6 (`kb.ingestion_mode ==
  IngestionMode.ADVANCED`) and Task 7 (`getattr(kb, "ingestion_mode", None) ==
  IngestionMode.ADVANCED`) — same enum, same import path (`src.models.knowledge_base`).
- `StreamProducer.push` signature used in Task 6 (`kb_id=`, `tenant_id=`, `source_type=`,
  `documents=`) matches the real confirmed signature from investigation exactly.

## Execution Handoff

This is the third of three plans covering the Company Brain / KB unification design:
- Plan A: `docs/superpowers/plans/2026-08-17-data-source-auto-sync-scheduling.md` (complete)
- Plan B: `docs/superpowers/plans/2026-08-17-slack-data-source-credential-reuse.md` (complete)
- Plan C: this document

**Prerequisite reminder:** this plan's Task 1 migration is chained with
`down_revision="20260817_0001"`, which is Plan B's migration ID. Confirm Plan B's migration has
either already been applied (`alembic heads` shows `20260817_0001` as current) or will be applied
immediately before this plan's Task 1, otherwise Task 1's migration will fail to find its parent
revision.

All three plans are now complete and self-reviewed. Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks,
fast iteration.

**2. Inline Execution** - execute tasks in this session using executing-plans, batch execution
with checkpoints.

Which approach?
