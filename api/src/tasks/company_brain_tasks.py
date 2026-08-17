"""
Celery tasks for KB ingestion pipeline.

Task inventory:
  kb_consume_stream_task               — read one batch from a Redis Stream and index it
  kb_process_batch_task                — direct indexing (used when queue_backend=celery_only)
  kb_extract_entities_task             — extract/upsert canonical entities into kb_entities
  company_brain_tier_migration_task    — promote hot->warm, warm->archive based on age thresholds

Note: fetching from external providers (Slack/GitHub/Notion/etc.) is handled by the single
"official" sync pathway in `src.tasks.data_source_tasks` (sync_data_source_task /
sync_all_data_sources_task), which uses an AsyncSession-compatible connector dispatch and
respects per-source `sync_frequency_minutes`. This module no longer duplicates that pathway —
a previous `company_brain_incremental_sync_task`/`company_brain_full_sync_task`/
`company_brain_sync_all_task` trio was a redundant beat-scheduled fan-out that instantiated
connectors with a synchronous `Session` (connectors expect `AsyncSession`), guaranteeing a
`TypeError` on every run and clobbering the correct status set by the real sync pathway.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from src.celery_app import celery_app
from src.core.database import SessionLocal

logger = logging.getLogger(__name__)

_CONSUME_TIME_BUDGET_SECONDS = 25


# ---------------------------------------------------------------------------
# Stream consumer task (runs every ~30s per active stream via beat)
# ---------------------------------------------------------------------------


@celery_app.task(
    name="kb_consume_stream_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="company_brain",
)
def kb_consume_stream_task(self, kb_id: int, tenant_id: str, source_type: str) -> dict[str, Any]:
    """
    Consume one batch from the Redis Stream for (kb_id, source_type).
    Designed to be called frequently (every 10-30 seconds per active stream).
    """
    import asyncio

    async def _run():
        from src.services.company_brain.ingestion.stream_consumer import StreamConsumer

        consumer = StreamConsumer()
        return await consumer.consume(kb_id=kb_id, tenant_id=tenant_id, source_type=source_type)

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("kb_consume_stream_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="company_brain_consume_active_streams_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="company_brain",
)
def company_brain_consume_active_streams_task(self) -> dict[str, Any]:
    """
    Consume one batch from every active Company Brain stream.

    kb_consume_stream_task needs runtime identifiers, so this dispatcher scans
    active data sources and drains one bounded batch per source. It is safe to
    run frequently because StreamConsumer.consume uses a short blocking read and
    returns quickly when a stream has no messages.
    """
    import asyncio

    from src.models.data_source import DataSource, DataSourceStatus

    db = SessionLocal()
    try:
        sources = (
            db.query(DataSource.id, DataSource.tenant_id, DataSource.knowledge_base_id, DataSource.type)
            .filter(
                DataSource.status == DataSourceStatus.ACTIVE,
                DataSource.sync_enabled.is_(True),
                DataSource.knowledge_base_id.isnot(None),
            )
            .all()
        )
    finally:
        db.close()

    async def _run() -> dict[str, Any]:
        import time

        from src.services.company_brain.ingestion.stream_consumer import StreamConsumer

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

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("company_brain_consume_active_streams_task failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Direct batch processing (celery_only queue backend)
# ---------------------------------------------------------------------------


@celery_app.task(
    name="kb_process_batch_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="company_brain",
)
def kb_process_batch_task(
    self,
    kb_id: int,
    tenant_id: str,
    source_type: str,
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """Directly process a batch of documents (no Redis Streams)."""
    import asyncio

    async def _run():
        from src.services.company_brain.ingestion.stream_consumer import StreamConsumer

        consumer = StreamConsumer()
        # Bypass the stream and call the processing pipeline directly
        return await consumer._process_batch(
            kb_id=kb_id,
            tenant_id=tenant_id,
            source_type=source_type,
            raw_docs=documents,
            min_tokens=10,
        )

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("kb_process_batch_task failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Tier migration task — promotes documents from hot → warm → archive
# ---------------------------------------------------------------------------


@celery_app.task(name="company_brain_tier_migration_task", queue="company_brain")
def company_brain_tier_migration_task() -> dict[str, Any]:
    """
    Nightly task: migrate documents that have exceeded the hot/warm age thresholds.

    hot  → warm:    docs older than COMPANY_BRAIN_HOT_DAYS
    warm → archive: docs older than COMPANY_BRAIN_WARM_DAYS (mark is_embedded=False,
                    remove from vector index — S3 archival handled by storage layer)
    """
    from src.config.settings import get_settings

    settings = get_settings()
    hot_days = getattr(settings, "company_brain_hot_days", 90)
    warm_days = getattr(settings, "company_brain_warm_days", 730)

    db = SessionLocal()
    promoted_to_warm = 0
    promoted_to_archive = 0

    try:
        from sqlalchemy import text

        now = datetime.now(UTC)
        hot_cutoff = now - timedelta(days=hot_days)
        warm_cutoff = now - timedelta(days=warm_days)

        # Find docs to promote hot → warm
        rows_to_warm = db.execute(
            text("""
                UPDATE data_source_documents
                SET storage_tier = 'warm'
                WHERE storage_tier = 'hot'
                  AND source_created_at < :cutoff
                RETURNING id, tenant_id::text
            """),
            {"cutoff": hot_cutoff},
        ).fetchall()
        promoted_to_warm = len(rows_to_warm)

        # Find docs to promote warm → archive (just update tier; vector removal async)
        rows_to_archive = db.execute(
            text("""
                UPDATE data_source_documents
                SET storage_tier = 'archive', is_embedded = false
                WHERE storage_tier = 'warm'
                  AND source_created_at < :cutoff
                RETURNING id, tenant_id::text
            """),
            {"cutoff": warm_cutoff},
        ).fetchall()
        promoted_to_archive = len(rows_to_archive)
        db.commit()

        logger.info(
            "Tier migration: hot→warm=%d, warm→archive=%d",
            promoted_to_warm,
            promoted_to_archive,
        )
        return {
            "promoted_to_warm": promoted_to_warm,
            "promoted_to_archive": promoted_to_archive,
        }
    except Exception as exc:
        db.rollback()
        logger.error("Tier migration failed: %s", exc)
        return {"error": str(exc)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Entity extractor task — runs after each batch is indexed
# ---------------------------------------------------------------------------


@celery_app.task(
    name="kb_extract_entities_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="company_brain",
)
def kb_extract_entities_task(
    self,
    knowledge_base_id: int,
    tenant_id: str,
    source_type: str,
    doc_ids: list[int],
) -> dict[str, Any]:
    """
    Extract canonical entities from newly indexed documents and upsert
    them into kb_entities, scoped to the given knowledge base.

    Args:
        knowledge_base_id: KnowledgeBase.id these documents belong to
        tenant_id:         Tenant UUID string
        source_type:       e.g. "slack", "github", "jira"
        doc_ids:           data_source_documents.id values just indexed
    """
    db = SessionLocal()
    try:
        from src.models.data_source import DataSourceDocument

        docs = (
            db.query(DataSourceDocument)
            .filter(DataSourceDocument.id.in_(doc_ids), DataSourceDocument.tenant_id == uuid.UUID(tenant_id))
            .limit(200)
            .all()
        )

        upserted = 0
        for doc in docs:
            meta = doc.doc_metadata or {}
            entities = _extract_entities_from_meta(source_type, meta)
            for entity_data in entities:
                _upsert_entity(db, knowledge_base_id, tenant_id, entity_data)
                upserted += 1

        db.commit()
        logger.info(
            "kb_extract_entities_task: upserted=%d for %d docs (source=%s, kb=%d)",
            upserted,
            len(docs),
            source_type,
            knowledge_base_id,
        )
        return {"upserted": upserted, "docs_processed": len(docs)}

    except Exception as exc:
        db.rollback()
        logger.error("Entity extraction failed: %s", exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


def _extract_entities_from_meta(source_type: str, meta: dict) -> list[dict]:
    """
    Rule-based entity extraction from document metadata.

    Returns a list of entity dicts ready for _upsert_entity:
      {entity_type, canonical_name, email, identifiers}
    """
    entities: list[dict] = []

    if source_type == "slack":
        user = meta.get("user") or meta.get("user_id")
        if user:
            entities.append(
                {
                    "entity_type": "person",
                    "canonical_name": user,
                    "email": None,
                    "identifiers": {"slack_user_id": user},
                }
            )
        channel = meta.get("channel")
        if channel:
            entities.append(
                {
                    "entity_type": "channel",
                    "canonical_name": channel,
                    "email": None,
                    "identifiers": {"slack_channel_id": channel},
                }
            )

    elif source_type in ("github", "gitlab"):
        author = meta.get("author") or meta.get("user")
        repo = meta.get("repo")
        if author:
            entities.append(
                {
                    "entity_type": "person",
                    "canonical_name": author,
                    "email": meta.get("author_email"),
                    "identifiers": {f"{source_type}_login": author},
                }
            )
        if repo:
            entities.append(
                {
                    "entity_type": "repo",
                    "canonical_name": repo,
                    "email": None,
                    "identifiers": {f"{source_type}_repo": repo},
                }
            )

    elif source_type == "jira":
        for field in ("assignee_email", "reporter_email", "creator_email"):
            email = meta.get(field)
            if email:
                entities.append(
                    {
                        "entity_type": "person",
                        "canonical_name": email.split("@")[0],
                        "email": email,
                        "identifiers": {},
                    }
                )
        project = meta.get("project_key")
        if project:
            entities.append(
                {
                    "entity_type": "project",
                    "canonical_name": project,
                    "email": None,
                    "identifiers": {"jira_project_key": project},
                }
            )

    elif source_type == "linear":
        assignee_email = meta.get("assignee_email")
        creator_email = meta.get("creator_email")
        for email in filter(None, [assignee_email, creator_email]):
            entities.append(
                {
                    "entity_type": "person",
                    "canonical_name": email.split("@")[0],
                    "email": email,
                    "identifiers": {},
                }
            )
        team_key = meta.get("team_key")
        if team_key:
            entities.append(
                {
                    "entity_type": "team",
                    "canonical_name": team_key,
                    "email": None,
                    "identifiers": {"linear_team_key": team_key},
                }
            )

    elif source_type == "notion":
        page_id = meta.get("page_id")
        if page_id:
            entities.append(
                {
                    "entity_type": "page",
                    "canonical_name": meta.get("title", page_id),
                    "email": None,
                    "identifiers": {"notion_page_id": page_id},
                }
            )

    return entities


def _upsert_entity(db: Any, knowledge_base_id: int, tenant_id: str, data: dict) -> None:
    """
    Upsert a KBEntity scoped to a KnowledgeBase.

    Dedup key:
      - If email is set: (knowledge_base_id, email) — uses the unique constraint
      - Otherwise: (knowledge_base_id, entity_type, canonical_name)
    """
    from src.models.kb_brain import KBEntity

    tid = uuid.UUID(tenant_id)
    email = data.get("email")
    entity_type = data["entity_type"]
    canonical_name = data["canonical_name"]
    new_identifiers = data.get("identifiers") or {}

    if email:
        existing = (
            db.query(KBEntity).filter(KBEntity.knowledge_base_id == knowledge_base_id, KBEntity.email == email).first()
        )
    else:
        existing = (
            db.query(KBEntity)
            .filter(
                KBEntity.knowledge_base_id == knowledge_base_id,
                KBEntity.entity_type == entity_type,
                KBEntity.canonical_name == canonical_name,
            )
            .first()
        )

    if existing:
        merged = {**(existing.identifiers or {}), **new_identifiers}
        existing.identifiers = merged
        names = list(set((existing.display_names or []) + [canonical_name]))
        existing.display_names = names
    else:
        entity = KBEntity(
            tenant_id=tid,
            knowledge_base_id=knowledge_base_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            email=email,
            identifiers=new_identifiers,
            display_names=[canonical_name],
        )
        db.add(entity)
