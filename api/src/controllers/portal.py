"""
Portal Controller

Public and authenticated endpoints for the white-label tenant portal.

Public endpoints (no auth):
  GET  /api/v1/portal/{tenant_slug}/config
  GET  /api/v1/portal/{tenant_slug}/agents
  GET  /api/v1/portal/{tenant_slug}/agents/{agent_slug}

Authenticated endpoints (tenant admin):
  GET  /api/v1/portal/settings
  PUT  /api/v1/portal/settings
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.tenant import Account, Tenant, TenantAccountJoin
from src.models.tenant_portal import TenantPortal
from src.schemas.portal import (
    PortalAgentResponse,
    PortalConfigResponse,
    TenantPortalResponse,
    UpdatePortalSettingsBody,
)

logger = logging.getLogger(__name__)

# Public router — no authentication required
public_router = APIRouter()

# Authenticated router — requires valid Bearer token
router = APIRouter()

_SLUG_RE = re.compile(r"^[a-z0-9-]{2,100}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_portal_by_slug(slug: str, db: AsyncSession) -> TenantPortal:
    """Return an enabled TenantPortal by subdomain slug, or raise 404."""
    result = await db.execute(
        select(TenantPortal).where(
            TenantPortal.subdomain == slug,
            TenantPortal.portal_enabled.is_(True),
        )
    )
    portal = result.scalar_one_or_none()
    if not portal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portal not found or not enabled")
    return portal


async def _get_portal_agents(
    portal: TenantPortal,
    db: AsyncSession,
    include_members_only: bool = False,
    page: int = 1,
    limit: int = 20,
    search: str | None = None,
) -> list[Agent]:
    """Return agents for a portal filtered by visibility."""
    visibility_values = ["public"]
    if include_members_only:
        visibility_values.append("members_only")

    stmt = (
        select(Agent)
        .where(
            Agent.tenant_id == portal.tenant_id,
            Agent.portal_visibility.in_(visibility_values),
            Agent.status == "ACTIVE",
        )
        .limit(min(limit, 100))
        .offset((page - 1) * limit)
    )

    if search:
        stmt = stmt.where(Agent.agent_name.ilike(f"%{search}%"))

    result = await db.execute(stmt)
    return list(result.scalars().all())


def _agent_to_portal_response(agent: Agent) -> PortalAgentResponse:
    return PortalAgentResponse(
        slug=agent.slug or agent.agent_name,
        agent_name=agent.agent_name,
        description=agent.description,
        avatar=agent.avatar,
        category=agent.category,
        tags=list(agent.tags) if agent.tags else None,
        suggestion_prompts=agent.suggestion_prompts,
        portal_visibility=agent.portal_visibility or "hidden",
    )


def _portal_to_response(portal: TenantPortal) -> TenantPortalResponse:
    return TenantPortalResponse(
        id=str(portal.id),
        tenant_id=str(portal.tenant_id),
        portal_enabled=portal.portal_enabled,
        subdomain=portal.subdomain,
        portal_domain=portal.portal_domain,
        branding_config=portal.branding_config,
        featured_agent_slugs=list(portal.featured_agent_slugs) if portal.featured_agent_slugs else None,
        seo_config=portal.seo_config,
        created_at=portal.created_at.isoformat(),
        updated_at=portal.updated_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@public_router.get("/api/v1/portal/{tenant_slug}/config", response_model=PortalConfigResponse, tags=["portal"])
async def get_portal_config(
    tenant_slug: str,
    db: AsyncSession = Depends(get_async_db),
) -> PortalConfigResponse:
    """
    Return public portal configuration including branding and featured agents.
    Returns 404 if the portal is disabled or the slug is unknown.
    """
    portal = await _get_portal_by_slug(tenant_slug, db)

    # Resolve featured agents
    featured: list[Agent] = []
    if portal.featured_agent_slugs:
        slugs = list(portal.featured_agent_slugs)[:12]
        result = await db.execute(
            select(Agent).where(
                Agent.slug.in_(slugs),
                Agent.tenant_id == portal.tenant_id,
                Agent.portal_visibility.in_(["public", "members_only"]),
                Agent.status == "ACTIVE",
            )
        )
        agents_by_slug = {(a.slug or a.agent_name): a for a in result.scalars().all()}
        featured = [agents_by_slug[s] for s in slugs if s in agents_by_slug]

    return PortalConfigResponse(
        portal_enabled=portal.portal_enabled,
        subdomain=portal.subdomain,
        branding_config=portal.branding_config,
        seo_config=portal.seo_config,
        featured_agents=[_agent_to_portal_response(a) for a in featured],
    )


@public_router.get("/api/v1/portal/{tenant_slug}/agents", tags=["portal"])
async def list_portal_agents(
    tenant_slug: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """
    List portal agents.
    - No auth: returns portal_visibility=public agents only.
    - With valid Bearer token for this tenant: also returns members_only agents.
    """
    portal = await _get_portal_by_slug(tenant_slug, db)

    # Check if caller has a valid Bearer token for this tenant
    include_members = False
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from src.services import AuthService

            token = auth_header.split(" ", 1)[1]
            payload = AuthService.decode_token(token)
            if payload and str(payload.get("tenant_id", "")) == str(portal.tenant_id):
                include_members = True
        except Exception:
            pass

    agents = await _get_portal_agents(
        portal, db, include_members_only=include_members, page=page, limit=limit, search=search
    )

    return {
        "data": [_agent_to_portal_response(a) for a in agents],
        "page": page,
        "limit": limit,
    }


@public_router.get("/api/v1/portal/{tenant_slug}/agents/{agent_slug}", tags=["portal"])
async def get_portal_agent(
    tenant_slug: str,
    agent_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """
    Return a single portal agent's public info.
    - Returns 404 if portal_visibility=hidden.
    - Returns 401 if portal_visibility=members_only and no valid token.
    """
    portal = await _get_portal_by_slug(tenant_slug, db)

    result = await db.execute(
        select(Agent).where(
            Agent.slug == agent_slug,
            Agent.tenant_id == portal.tenant_id,
            Agent.status == "ACTIVE",
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    visibility = agent.portal_visibility or "hidden"

    if visibility == "hidden":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if visibility == "members_only":
        # Require a valid tenant Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to view this agent",
            )
        try:
            from src.services import AuthService

            token = auth_header.split(" ", 1)[1]
            payload = AuthService.decode_token(token)
            if not payload or str(payload.get("tenant_id", "")) != str(portal.tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required to view this agent",
                )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to view this agent",
            )

    return {"data": _agent_to_portal_response(agent)}


# ---------------------------------------------------------------------------
# Authenticated endpoints (tenant admin)
# ---------------------------------------------------------------------------


@router.get("/api/v1/portal/settings", tags=["portal"])
async def get_portal_settings(
    current_account: Account = Depends(get_current_account),
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Return the portal settings for the current tenant."""
    result = await db.execute(select(TenantPortal).where(TenantPortal.tenant_id == tenant_id))
    portal = result.scalar_one_or_none()

    if not portal:
        # Return empty defaults — portal hasn't been configured yet
        return {
            "data": {
                "portal_enabled": False,
                "subdomain": None,
                "portal_domain": None,
                "branding_config": None,
                "featured_agent_slugs": None,
                "seo_config": None,
            }
        }

    return {"data": _portal_to_response(portal)}


@router.put("/api/v1/portal/settings", tags=["portal"])
async def update_portal_settings(
    body: UpdatePortalSettingsBody,
    current_account: Account = Depends(get_current_account),
    tenant_id: str = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
) -> dict:
    """Create or update the portal settings for the current tenant."""
    result = await db.execute(select(TenantPortal).where(TenantPortal.tenant_id == tenant_id))
    portal = result.scalar_one_or_none()

    if not portal:
        # Auto-generate subdomain from tenant name
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        slug = _make_slug(tenant.name if tenant else str(tenant_id))
        slug = await _ensure_unique_slug(slug, db)

        portal = TenantPortal(
            tenant_id=tenant_id,
            subdomain=slug,
            portal_enabled=False,
        )
        db.add(portal)

    if body.portal_enabled is not None:
        portal.portal_enabled = body.portal_enabled

    if body.portal_domain is not None:
        portal.portal_domain = body.portal_domain or None

    if body.branding_config is not None:
        portal.branding_config = body.branding_config.model_dump(exclude_none=True)

    if body.featured_agent_slugs is not None:
        portal.featured_agent_slugs = body.featured_agent_slugs

    if body.seo_config is not None:
        portal.seo_config = body.seo_config.model_dump(exclude_none=True)

    await db.commit()
    await db.refresh(portal)

    return {"data": _portal_to_response(portal)}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _make_slug(name: str) -> str:
    """Convert a tenant name to a URL-safe slug."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:80] or "portal"


async def _ensure_unique_slug(slug: str, db: AsyncSession, suffix: int = 0) -> str:
    """Append a numeric suffix until the slug is unique."""
    candidate = f"{slug}-{suffix}" if suffix else slug
    result = await db.execute(select(TenantPortal).where(TenantPortal.subdomain == candidate))
    if result.scalar_one_or_none() is None:
        return candidate
    return await _ensure_unique_slug(slug, db, suffix + 1)
