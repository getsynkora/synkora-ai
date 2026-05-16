"""
Company Brain domain service.

Handles CRUD for BrainDomain records and auto-creates the two permissions
(brain.{slug}.query, brain.{slug}.admin) in the existing permissions table
whenever a new domain is created — no separate RBAC infrastructure needed.

Tenant admins then assign these permissions to roles exactly as they do today.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.brain_domain import BrainDomain
from src.models.permission import Permission

logger = logging.getLogger(__name__)

# TTL for domain config Redis cache (seconds)
_DOMAIN_CACHE_TTL = 300  # 5 minutes
_DOMAIN_CACHE_KEY = "brain:domains:{tenant_id}"


async def list_domains(tenant_id: UUID, db: AsyncSession) -> list[BrainDomain]:
    result = await db.execute(select(BrainDomain).where(BrainDomain.tenant_id == tenant_id).order_by(BrainDomain.name))
    return list(result.scalars().all())


async def get_domain(domain_id: UUID, tenant_id: UUID, db: AsyncSession) -> BrainDomain | None:
    result = await db.execute(
        select(BrainDomain).where(
            BrainDomain.id == domain_id,
            BrainDomain.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def get_domain_by_slug(slug: str, tenant_id: UUID, db: AsyncSession) -> BrainDomain | None:
    result = await db.execute(
        select(BrainDomain).where(
            BrainDomain.slug == slug,
            BrainDomain.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_domain(
    tenant_id: UUID,
    name: str,
    slug: str,
    description: str | None,
    rerank_weight: float,
    is_active: bool,
    db: AsyncSession,
    knowledge_base_id: int | None = None,
) -> BrainDomain:
    """
    Create a BrainDomain and auto-insert two permissions into the existing
    permissions table:
      brain.{slug}.query  — can search this domain
      brain.{slug}.admin  — can configure this domain

    Permissions are system-level (not tenant-scoped) so they're available
    across the platform and can be assigned to any tenant's roles.
    """
    domain = BrainDomain(
        tenant_id=tenant_id,
        name=name,
        slug=slug,
        description=description,
        rerank_weight=rerank_weight,
        is_active=is_active,
        knowledge_base_id=knowledge_base_id,
    )
    db.add(domain)
    await db.flush()  # get domain.id before permission creation

    await _ensure_domain_permissions(slug, db)
    await db.commit()
    await db.refresh(domain)

    await _invalidate_domain_cache(str(tenant_id))
    logger.info("Created BrainDomain slug=%s tenant=%s", slug, tenant_id)
    return domain


async def update_domain(
    domain: BrainDomain,
    updates: dict,
    db: AsyncSession,
) -> BrainDomain:
    for key, value in updates.items():
        if hasattr(domain, key):
            setattr(domain, key, value)
    await db.commit()
    await db.refresh(domain)
    await _invalidate_domain_cache(str(domain.tenant_id))
    return domain


async def delete_domain(domain: BrainDomain, db: AsyncSession) -> None:
    """
    Delete a domain. Associated DataSource rows have brain_domain_id SET NULL
    (handled by FK constraint), so sources are not deleted — just undomained.
    The auto-created permissions are NOT deleted so existing role assignments
    remain intact (admins can clean up manually if desired).
    """
    await db.delete(domain)
    await db.commit()
    await _invalidate_domain_cache(str(domain.tenant_id))


async def assign_data_source(
    data_source_id: int,
    domain_id: UUID | None,
    tenant_id: UUID,
    db: AsyncSession,
) -> bool:
    """Assign or unassign a data source to/from a domain. Returns True if found."""
    from src.models.data_source import DataSource

    result = await db.execute(
        select(DataSource).where(
            DataSource.id == data_source_id,
            DataSource.tenant_id == tenant_id,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        return False

    source.brain_domain_id = domain_id
    await db.commit()
    await _invalidate_domain_cache(str(tenant_id))
    return True


async def get_domains_cached(tenant_id: str, db: AsyncSession) -> list[dict]:
    """
    Return the tenant's active domains as plain dicts, Redis-cached for 5 minutes.
    Used by the query router and retriever — avoids a DB hit on every agent query.
    """
    try:
        import json

        from src.config.redis import get_redis_async

        redis = get_redis_async()
        key = _DOMAIN_CACHE_KEY.format(tenant_id=tenant_id)
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)
    except Exception as exc:
        logger.debug("Domain cache read failed (%s) — falling back to DB", exc)

    domains = await list_domains(UUID(tenant_id), db)
    result = [
        {
            "id": str(d.id),
            "slug": d.slug,
            "name": d.name,
            "description": d.description or "",
            "rerank_weight": d.rerank_weight,
            "is_active": d.is_active,
            "knowledge_base_id": d.knowledge_base_id,
        }
        for d in domains
        if d.is_active
    ]

    try:
        import json

        from src.config.redis import get_redis_async

        redis = get_redis_async()
        key = _DOMAIN_CACHE_KEY.format(tenant_id=tenant_id)
        await redis.setex(key, _DOMAIN_CACHE_TTL, json.dumps(result))
    except Exception as exc:
        logger.debug("Domain cache write failed (%s)", exc)

    return result


async def get_domain_source_types(domain_id: str, tenant_id: str, db: AsyncSession) -> list[str]:
    """
    Return the list of source_type values for all active data sources that
    belong to this domain's knowledge base (preferred) or are directly tagged
    with this domain via brain_domain_id (fallback for legacy assignments).

    Priority:
      1. domain.knowledge_base_id is set  → all active DataSources for that KB
      2. domain.knowledge_base_id is None → DataSources tagged with brain_domain_id
    """
    from src.models.data_source import DataSource, DataSourceStatus

    # Resolve the domain row to get its knowledge_base_id
    domain = await get_domain(UUID(domain_id), UUID(tenant_id), db)
    if not domain:
        return []

    if domain.knowledge_base_id is not None:
        # Primary path: search the KB that IS this domain
        result = await db.execute(
            select(DataSource.type).where(
                DataSource.knowledge_base_id == domain.knowledge_base_id,
                DataSource.tenant_id == UUID(tenant_id),
                DataSource.status == DataSourceStatus.ACTIVE,
            )
        )
    else:
        # Fallback: legacy brain_domain_id tagging
        result = await db.execute(
            select(DataSource.type).where(
                DataSource.brain_domain_id == UUID(domain_id),
                DataSource.tenant_id == UUID(tenant_id),
                DataSource.status == DataSourceStatus.ACTIVE,
            )
        )

    return list({str(row[0]).lower() for row in result.all()})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _ensure_domain_permissions(slug: str, db: AsyncSession) -> None:
    """Insert brain.{slug}.query and brain.{slug}.admin into permissions if missing."""
    for action in ("query", "admin"):
        perm_name = f"brain.{slug}.{action}"
        existing = await db.execute(select(Permission).where(Permission.name == perm_name))
        if existing.scalar_one_or_none() is None:
            perm = Permission(
                name=perm_name,
                resource="brain",
                action=f"{slug}.{action}",
                description=f"Company Brain — {action} access to '{slug}' domain",
                is_system=False,
            )
            db.add(perm)
            logger.info("Auto-created permission: %s", perm_name)


async def _invalidate_domain_cache(tenant_id: str) -> None:
    """Remove the domain config cache entry so the next query reloads from DB."""
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        key = _DOMAIN_CACHE_KEY.format(tenant_id=tenant_id)
        await redis.delete(key)
    except Exception as exc:
        logger.debug("Domain cache invalidation failed (%s)", exc)
