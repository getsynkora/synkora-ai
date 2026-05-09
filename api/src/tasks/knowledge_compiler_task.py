"""
Celery tasks for scheduled Knowledge Autopilot compilation.

Periodically compiles knowledge bases that have autopilot enabled,
generating and updating wiki articles from source documents.
"""

import asyncio
import concurrent.futures
import logging
from collections.abc import Coroutine
from typing import Any

from src.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Run an async coroutine from a Celery (sync) task.

    Runs in a dedicated thread so the coroutine gets a completely fresh event
    loop and greenlet context. This prevents two classes of errors:

    1. MissingGreenlet — Celery's worker thread can have leftover greenlet /
       asyncio state that breaks SQLAlchemy's _AsyncIoGreenlet bridge.
       A new thread starts clean, so await_only() always finds the right
       greenlet.

    2. RuntimeError('Event loop is closed') — httpx/litellm schedule
       connection-pool teardown as background Tasks. We drain those before
       closing the loop so they finish cleanly.
    """

    def _in_thread() -> Any:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            loop.close()
            asyncio.set_event_loop(None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_in_thread).result()


@celery_app.task(name="tasks.compile_knowledge_wikis", bind=True, max_retries=1)
def compile_knowledge_wikis(self):
    """
    Periodic task: find all knowledge bases with wiki articles and recompile.

    Runs daily to detect new/updated documents and refresh wiki articles.
    """
    _run_async(_compile_all_wikis())


@celery_app.task(name="tasks.compile_single_knowledge_wiki", bind=True, max_retries=1)
def compile_single_knowledge_wiki(self, kb_id: int, tenant_id: str, llm_config_id: str | None = None):
    """
    On-demand task: compile a single knowledge base wiki triggered by the user.
    """
    _run_async(_compile_single_wiki(kb_id, tenant_id, llm_config_id))


async def _compile_all_wikis():
    from sqlalchemy import select

    from src.core.database import create_celery_async_session
    from src.models.wiki_article import WikiArticle, WikiCompilationJob
    from src.services.knowledge_autopilot.compiler import KnowledgeCompiler

    async with create_celery_async_session()() as db:
        # Find all knowledge bases that have at least one wiki article (autopilot active)
        result = await db.execute(
            select(WikiArticle.knowledge_base_id, WikiArticle.tenant_id).group_by(
                WikiArticle.knowledge_base_id, WikiArticle.tenant_id
            )
        )
        kb_tenants = result.all()

        if not kb_tenants:
            logger.info("No knowledge bases with wiki articles found, skipping compilation")
            return

        compiler = KnowledgeCompiler(db)
        compiled = 0
        failed = 0

        for kb_id, tenant_id in kb_tenants:
            # Look up the llm_config_id from the most recent successful compilation job
            job_result = await db.execute(
                select(WikiCompilationJob)
                .filter(
                    WikiCompilationJob.knowledge_base_id == kb_id,
                    WikiCompilationJob.status == "completed",
                )
                .order_by(WikiCompilationJob.completed_at.desc())
                .limit(1)
            )
            last_job = job_result.scalar_one_or_none()
            llm_config_id = None
            if last_job and last_job.compilation_metadata:
                llm_config_id = last_job.compilation_metadata.get("llm_config_id")

            if not llm_config_id:
                logger.warning(
                    f"KB {kb_id}: no llm_config_id found in previous compilation jobs — skipping scheduled recompile. "
                    "Run a manual compilation from the UI to set it."
                )
                failed += 1
                continue

            try:
                result = await compiler.compile(
                    knowledge_base_id=kb_id,
                    tenant_id=str(tenant_id),
                    llm_config_id=llm_config_id,
                )
                if result.get("status") == "completed":
                    compiled += 1
                else:
                    failed += 1
                logger.info(f"Compiled KB {kb_id}: {result.get('status')}")
            except Exception as e:
                failed += 1
                logger.error(f"Failed to compile KB {kb_id}: {e}")

        logger.info(f"Knowledge wiki compilation complete: {compiled} succeeded, {failed} failed")


async def _compile_single_wiki(kb_id: int, tenant_id: str, llm_config_id: str | None = None):
    from src.core.database import create_celery_async_session
    from src.services.knowledge_autopilot.compiler import KnowledgeCompiler

    async with create_celery_async_session()() as db:
        compiler = KnowledgeCompiler(db)
        result = await compiler.compile(knowledge_base_id=kb_id, tenant_id=tenant_id, llm_config_id=llm_config_id)
        logger.info(f"On-demand compilation KB {kb_id}: {result.get('status')}")


@celery_app.task(name="tasks.embed_wiki_documents", bind=True, max_retries=1)
def embed_wiki_documents(self, kb_id: int, tenant_id: str):
    """
    Embed compiled wiki articles into the KB vector store so agents can retrieve them via RAG.

    Triggered automatically after each wiki compilation run.
    """
    try:
        _run_async(_embed_wiki_documents(kb_id, tenant_id))
    except Exception as exc:
        logger.error(f"embed_wiki_documents failed for KB {kb_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc)


async def _embed_wiki_documents(kb_id: int, tenant_id: str) -> None:
    """Embed all published wiki articles for a knowledge base into its vector store."""
    import uuid as _uuid

    from sqlalchemy import select

    from src.core.database import create_celery_async_session
    from src.models.document import Document, DocumentStatus
    from src.models.document_segment import DocumentSegment
    from src.models.knowledge_base import KnowledgeBase
    from src.models.wiki_article import WikiArticle
    from src.services.knowledge_base.embedding_service import EmbeddingService
    from src.services.knowledge_base.providers.vector_db_factory import VectorDBProviderFactory
    from src.services.knowledge_base.text_processor import TextProcessor

    async with create_celery_async_session()() as db:
        kb_result = await db.execute(select(KnowledgeBase).filter(KnowledgeBase.id == kb_id))
        kb = kb_result.scalar_one_or_none()
        if not kb:
            logger.warning(f"KB {kb_id} not found — skipping wiki embedding")
            return

        articles_result = await db.execute(
            select(WikiArticle).filter(
                WikiArticle.knowledge_base_id == kb_id,
                WikiArticle.status == "published",
            )
        )
        articles = articles_result.scalars().all()
        if not articles:
            return

        # Initialise embedding + vector store using KB's own config
        embedding_config = kb.get_embedding_config_decrypted()
        embedding_service = EmbeddingService(
            provider=kb.embedding_provider.value,
            model_name=kb.embedding_model,
            config=embedding_config,
        )
        vector_db_config = kb.get_vector_db_config_decrypted()
        vector_db = VectorDBProviderFactory.create(provider_type=kb.vector_db_provider, config=vector_db_config)
        vector_db.connect()
        collection_name = (
            kb.vector_db_config.get("index_name") or kb.vector_db_config.get("collection_name") or f"kb-{kb.id}"
        )
        namespace = str(kb.id)

        text_processor = TextProcessor()
        embedded = 0

        for article in articles:
            try:
                external_id = f"wiki:{article.slug}"
                full_content = f"# {article.title}\n\n{article.content}"

                # Upsert Document record (source_type="wiki", no data_source)
                existing_result = await db.execute(
                    select(Document).filter(
                        Document.knowledge_base_id == kb_id,
                        Document.external_id == external_id,
                    )
                )
                kb_doc = existing_result.scalar_one_or_none()
                if kb_doc:
                    kb_doc.name = article.title
                    kb_doc.content = full_content
                    kb_doc.word_count = len(full_content.split())
                    kb_doc.char_count = len(full_content)
                    # Remove stale segments — vectors use deterministic IDs so they'll be overwritten
                    stale_segs = await db.execute(
                        select(DocumentSegment).filter(DocumentSegment.document_id == kb_doc.id)
                    )
                    for seg in stale_segs.scalars().all():
                        await db.delete(seg)
                else:
                    kb_doc = Document(
                        id=_uuid.uuid4(),
                        tenant_id=article.tenant_id,
                        knowledge_base_id=kb_id,
                        data_source_id=None,
                        name=article.title,
                        external_id=external_id,
                        source_type="wiki",
                        content=full_content,
                        content_type="markdown",
                        word_count=len(full_content.split()),
                        char_count=len(full_content),
                        upload_source="wiki",
                    )
                    db.add(kb_doc)
                await db.flush()

                # Chunk and embed
                chunks = text_processor.chunk_text(
                    text=full_content,
                    chunk_size=kb.chunk_size,
                    chunk_overlap=kb.chunk_overlap,
                    strategy=kb.chunking_strategy,
                    min_chunk_size=kb.min_chunk_size,
                    max_chunk_size=kb.max_chunk_size,
                    chunking_config=kb.chunking_config,
                    metadata={"title": article.title, "category": article.category, "source_type": "wiki"},
                )
                if not chunks:
                    continue

                embeddings = embedding_service.embed_texts([c["text"] for c in chunks])

                vectors = []
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
                    node_id = f"wiki-{kb_id}-{article.id}-seg-{i}"
                    seg = DocumentSegment(
                        id=_uuid.uuid4(),
                        tenant_id=article.tenant_id,
                        dataset_id=None,
                        document_id=kb_doc.id,
                        position=i,
                        content=chunk["text"],
                        word_count=len(chunk["text"].split()),
                        tokens=len(chunk["text"]) // 4,
                        index_node_id=node_id,
                        index_node_hash=f"hash-{article.id}-{i}",
                        created_by=article.tenant_id,
                    )
                    db.add(seg)
                    await db.flush()

                    vectors.append(
                        {
                            "id": node_id,
                            "vector": embedding,
                            "payload": {
                                "knowledge_base_id": kb_id,
                                "document_id": str(kb_doc.id),
                                "segment_id": str(seg.id),
                                "external_id": external_id,
                                "chunk_index": i,
                                "text": chunk["text"],
                                "source_type": "wiki",
                                "title": article.title,
                                "category": article.category,
                            },
                        }
                    )

                if vectors:
                    vector_db.add_vectors(collection_name=collection_name, vectors=vectors, namespace=namespace)

                kb_doc.status = DocumentStatus.COMPLETED
                await db.commit()
                embedded += 1
                logger.info(f"Embedded wiki article '{article.title}' ({len(vectors)} chunks) into KB {kb_id}")

            except Exception as e:
                logger.error(f"Failed to embed wiki article '{article.title}': {e}", exc_info=True)
                try:
                    await db.rollback()
                except Exception:
                    pass

        vector_db.disconnect()
        logger.info(f"Wiki embedding complete for KB {kb_id}: {embedded}/{len(articles)} articles embedded")
