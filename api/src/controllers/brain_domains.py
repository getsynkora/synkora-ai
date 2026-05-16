"""Company Brain domain management API."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.schemas.brain_domain import (
    AssignDataSourceBody,
    BrainDomainCreate,
    BrainDomainResponse,
    BrainDomainUpdate,
)
from src.services.company_brain.domain_service import (
    assign_data_source,
    create_domain,
    delete_domain,
    get_domain,
    list_domains,
    update_domain,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/brain/domains", response_model=list[BrainDomainResponse], tags=["company-brain"])
async def list_brain_domains(
    tenant_id: UUID = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """List all Company Brain domains for the current tenant."""
    return await list_domains(tenant_id, db)


@router.post(
    "/brain/domains", response_model=BrainDomainResponse, status_code=status.HTTP_201_CREATED, tags=["company-brain"]
)
async def create_brain_domain(
    body: BrainDomainCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new Company Brain domain.

    Auto-creates two permissions in the platform:
      brain.{slug}.query — assign to roles that should be able to search this domain
      brain.{slug}.admin — assign to roles that should manage this domain
    """
    from src.services.company_brain.domain_service import get_domain_by_slug

    existing = await get_domain_by_slug(body.slug, tenant_id, db)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Domain slug '{body.slug}' already exists")

    return await create_domain(
        tenant_id=tenant_id,
        name=body.name,
        slug=body.slug,
        description=body.description,
        rerank_weight=body.rerank_weight,
        is_active=body.is_active,
        knowledge_base_id=body.knowledge_base_id,
        db=db,
    )


@router.get("/brain/domains/{domain_id}", response_model=BrainDomainResponse, tags=["company-brain"])
async def get_brain_domain(
    domain_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    domain = await get_domain(domain_id, tenant_id, db)
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    return domain


@router.patch("/brain/domains/{domain_id}", response_model=BrainDomainResponse, tags=["company-brain"])
async def update_brain_domain(
    domain_id: UUID,
    body: BrainDomainUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    domain = await get_domain(domain_id, tenant_id, db)
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    updates = body.model_dump(exclude_none=True)
    return await update_domain(domain, updates, db)


@router.delete("/brain/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["company-brain"])
async def delete_brain_domain(
    domain_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    domain = await get_domain(domain_id, tenant_id, db)
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    await delete_domain(domain, db)


@router.post("/brain/domains/assign-source", status_code=status.HTTP_200_OK, tags=["company-brain"])
async def assign_source_to_domain(
    body: AssignDataSourceBody,
    tenant_id: UUID = Depends(get_current_tenant_id),
    _account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Assign a DataSource to a domain (or unassign by passing domain_id=null).
    This is how tenants build their domain → source mapping.
    """
    found = await assign_data_source(
        data_source_id=body.data_source_id,
        domain_id=body.domain_id,
        tenant_id=tenant_id,
        db=db,
    )
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")
    return {"ok": True}
