"""
Provisioning API - set up and run customer tenants from another system's backend.

Authentication: ``Authorization: Bearer <agent api key>`` with the ``tenants:manage`` permission, on a
tenant that a platform operator has enabled for tenant management. Every call is limited to the tenants
that caller created; other tenants are reported as not found.

Typical flow for a new customer:
    1. POST /tenants                      create the customer's tenant on a plan
    2. POST /tenants/{id}/agents          create its agents from your template agents
    3. PUT  /tenants/{id}/agents/{agent}/llm-key   give an agent its LLM key (if not sent in step 2)
    4. POST /tenants/{id}/api-keys        keys your frontend or backend uses to chat and show usage
    5. PUT  /tenants/{id}/subscription    report plan changes and renewals from your billing system
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.controllers.agent_api_account import (
    CurrentPlanResponse,
    UsageResponse,
    build_plan_response,
    build_usage_response,
)
from src.core.database import get_async_db
from src.middleware.agent_api_auth import AgentApiAuthMiddleware
from src.models.agent_api_key import AgentApiKey
from src.models.tenant import Tenant
from src.services.tenant_provisioning_service import (
    DEFAULT_KEY_PERMISSIONS,
    ProvisioningError,
    TenantProvisioningService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public/tenants", tags=["Provisioning API"])


async def get_provisioning_service(
    request: Request, db: AsyncSession = Depends(get_async_db)
) -> TenantProvisioningService:
    """Authenticate the caller and return a service limited to the tenants it manages."""
    api_key = await AgentApiAuthMiddleware.authenticate_request(request, "tenants:manage")
    manager = await db.get(Tenant, api_key.tenant_id)
    if manager is None or not manager.can_manage_tenants:
        raise HTTPException(status_code=403, detail="This tenant is not enabled to manage other tenants")
    return TenantProvisioningService(db, manager)


def _http(err: ProvisioningError) -> HTTPException:
    return HTTPException(status_code=err.status_code, detail=str(err))


# ---- schemas -----------------------------------------------------------------------------------


class TenantInfo(BaseModel):
    id: str
    name: str
    external_ref: str | None
    status: str
    created_at: datetime


class TenantDetail(TenantInfo):
    plan: CurrentPlanResponse


class TenantListResponse(BaseModel):
    tenants: list[TenantInfo]
    total: int


class CreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    external_ref: str | None = Field(None, max_length=255, description="Your own id for this customer; unique per you")
    plan: str | None = Field(None, description="Plan name or id. Omit to create the tenant with no subscription")
    billing_cycle: str | None = Field(None, description="MONTHLY or YEARLY")
    period_start: datetime | None = None
    period_end: datetime | None = None


class UpdateTenantRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    external_ref: str | None = Field(None, max_length=255)


class SubscriptionRequest(BaseModel):
    plan: str | None = Field(None, description="Plan name or id to move the customer to")
    status: str | None = Field(None, description="ACTIVE, TRIAL, SUSPENDED, CANCELLED or EXPIRED")
    billing_cycle: str | None = Field(None, description="MONTHLY or YEARLY")
    period_start: datetime | None = None
    period_end: datetime | None = Field(None, description="A new period starts every message pool at zero")
    cancel_at_period_end: bool | None = None
    renew: bool = Field(False, description="Start a new 30-day period now and reset allowances")


class AgentSummary(BaseModel):
    id: str
    name: str
    slug: str | None
    quota_pool: str | None
    status: str


class CreateAgentRequest(BaseModel):
    template_agent_id: UUID = Field(..., description="One of your own agents to copy settings from")
    name: str = Field(..., min_length=1, max_length=255)
    quota_pool: str | None = Field(
        None, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$", description="Defaults to the template's pool"
    )
    llm_api_key: str | None = Field(None, description="The customer's LLM key. Stored encrypted, never returned")


class LLMKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=1)


class CreateKeyRequest(BaseModel):
    agent_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    permissions: list[str] = Field(default_factory=lambda: list(DEFAULT_KEY_PERMISSIONS))
    rate_limit_per_minute: int = Field(60, ge=1, le=1000)
    rate_limit_per_hour: int = Field(1000, ge=1, le=100000)
    rate_limit_per_day: int = Field(10000, ge=1, le=1000000)
    allowed_origins: list[str] | None = None


class KeyInfo(BaseModel):
    id: str
    agent_id: str
    name: str
    key_prefix: str
    permissions: list[str]
    is_active: bool
    created_at: datetime


class CreatedKey(KeyInfo):
    key: str = Field(..., description="The API key. Shown once; store it now")


def _tenant_info(tenant: Tenant) -> TenantInfo:
    return TenantInfo(
        id=str(tenant.id),
        name=tenant.name,
        external_ref=tenant.external_ref,
        status=str(tenant.status),
        created_at=tenant.created_at,
    )


def _key_info(key: AgentApiKey) -> KeyInfo:
    return KeyInfo(
        id=str(key.id),
        agent_id=str(key.agent_id),
        name=key.key_name,
        key_prefix=key.key_prefix,
        permissions=list(key.permissions or []),
        is_active=bool(key.is_active),
        created_at=key.created_at,
    )


# ---- tenants -----------------------------------------------------------------------------------


@router.post("", response_model=TenantDetail, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: CreateTenantRequest,
    service: TenantProvisioningService = Depends(get_provisioning_service),
):
    """Create a customer tenant, optionally already on a plan. Requires permission: tenants:manage"""
    try:
        tenant = await service.create_tenant(
            name=body.name,
            external_ref=body.external_ref,
            plan=body.plan,
            billing_cycle=body.billing_cycle,
            period_start=body.period_start,
            period_end=body.period_end,
        )
        plan = await build_plan_response(service.db, tenant.id)
    except ProvisioningError as err:
        raise _http(err) from err
    return TenantDetail(**_tenant_info(tenant).model_dump(), plan=plan)


@router.get("", response_model=TenantListResponse)
async def list_tenants(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    external_ref: str | None = None,
    service: TenantProvisioningService = Depends(get_provisioning_service),
):
    """Tenants you created, newest first. Requires permission: tenants:manage"""
    tenants, total = await service.list_tenants(limit=limit, offset=offset, external_ref=external_ref)
    return TenantListResponse(tenants=[_tenant_info(t) for t in tenants], total=total)


@router.get("/{tenant_id}", response_model=TenantDetail)
async def get_tenant(tenant_id: UUID, service: TenantProvisioningService = Depends(get_provisioning_service)):
    """One tenant with its plan. Requires permission: tenants:manage"""
    try:
        tenant = await service.get_managed(tenant_id)
    except ProvisioningError as err:
        raise _http(err) from err
    plan = await build_plan_response(service.db, tenant.id)
    return TenantDetail(**_tenant_info(tenant).model_dump(), plan=plan)


@router.patch("/{tenant_id}", response_model=TenantInfo)
async def update_tenant(
    tenant_id: UUID,
    body: UpdateTenantRequest,
    service: TenantProvisioningService = Depends(get_provisioning_service),
):
    """Rename a tenant or change its external_ref. Requires permission: tenants:manage"""
    try:
        tenant = await service.get_managed(tenant_id)
        tenant = await service.update_tenant(tenant, name=body.name, external_ref=body.external_ref)
    except ProvisioningError as err:
        raise _http(err) from err
    return _tenant_info(tenant)


# ---- plan and usage ----------------------------------------------------------------------------


@router.put("/{tenant_id}/subscription", response_model=CurrentPlanResponse)
async def set_subscription(
    tenant_id: UUID,
    body: SubscriptionRequest,
    service: TenantProvisioningService = Depends(get_provisioning_service),
):
    """
    Report a plan change, status change or renewal for a customer.

    Billing runs in your system; this tells Synkora which plan the customer is on and for which
    period. Requires permission: tenants:manage
    """
    try:
        tenant = await service.get_managed(tenant_id)
        await service.set_subscription(tenant, **body.model_dump())
    except ProvisioningError as err:
        raise _http(err) from err
    return await build_plan_response(service.db, tenant.id)


@router.get("/{tenant_id}/plan", response_model=CurrentPlanResponse)
async def get_tenant_plan(tenant_id: UUID, service: TenantProvisioningService = Depends(get_provisioning_service)):
    """A customer's current plan. Requires permission: tenants:manage"""
    try:
        tenant = await service.get_managed(tenant_id)
    except ProvisioningError as err:
        raise _http(err) from err
    return await build_plan_response(service.db, tenant.id)


@router.get("/{tenant_id}/usage", response_model=UsageResponse)
async def get_tenant_usage(tenant_id: UUID, service: TenantProvisioningService = Depends(get_provisioning_service)):
    """A customer's usage this period. Requires permission: tenants:manage"""
    try:
        tenant = await service.get_managed(tenant_id)
    except ProvisioningError as err:
        raise _http(err) from err
    return await build_usage_response(service.db, tenant.id)


# ---- agents ------------------------------------------------------------------------------------


@router.get("/{tenant_id}/agents", response_model=list[AgentSummary])
async def list_tenant_agents(tenant_id: UUID, service: TenantProvisioningService = Depends(get_provisioning_service)):
    """A customer's agents. Requires permission: tenants:manage"""
    try:
        tenant = await service.get_managed(tenant_id)
    except ProvisioningError as err:
        raise _http(err) from err
    agents = await service.list_agents(tenant)
    return [
        AgentSummary(id=str(a.id), name=a.agent_name, slug=a.slug, quota_pool=a.quota_pool, status=str(a.status))
        for a in agents
    ]


@router.post("/{tenant_id}/agents", response_model=AgentSummary, status_code=status.HTTP_201_CREATED)
async def create_tenant_agent(
    tenant_id: UUID,
    body: CreateAgentRequest,
    service: TenantProvisioningService = Depends(get_provisioning_service),
):
    """
    Create an agent for a customer from one of your template agents.

    Copies prompt, description, suggestions, category, tags and LLM provider and model settings.
    Never copies LLM keys, tool credentials or links to your knowledge bases.
    Requires permission: tenants:manage
    """
    try:
        tenant = await service.get_managed(tenant_id)
        agent = await service.create_agent_from_template(
            tenant,
            template_agent_id=body.template_agent_id,
            name=body.name,
            quota_pool=body.quota_pool,
            llm_api_key=body.llm_api_key,
        )
    except ProvisioningError as err:
        raise _http(err) from err
    return AgentSummary(
        id=str(agent.id), name=agent.agent_name, slug=agent.slug, quota_pool=agent.quota_pool, status=str(agent.status)
    )


@router.put("/{tenant_id}/agents/{agent_id}/llm-key", status_code=status.HTTP_204_NO_CONTENT)
async def set_agent_llm_key(
    tenant_id: UUID,
    agent_id: UUID,
    body: LLMKeyRequest,
    service: TenantProvisioningService = Depends(get_provisioning_service),
):
    """Set a customer agent's LLM key. Stored encrypted and never returned. Requires permission: tenants:manage"""
    try:
        tenant = await service.get_managed(tenant_id)
        await service.set_llm_key(tenant, agent_id, body.api_key)
    except ProvisioningError as err:
        raise _http(err) from err
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- api keys ----------------------------------------------------------------------------------


@router.get("/{tenant_id}/api-keys", response_model=list[KeyInfo])
async def list_tenant_keys(tenant_id: UUID, service: TenantProvisioningService = Depends(get_provisioning_service)):
    """A customer's API keys (prefix only, never the key). Requires permission: tenants:manage"""
    try:
        tenant = await service.get_managed(tenant_id)
    except ProvisioningError as err:
        raise _http(err) from err
    result = await service.db.execute(
        select(AgentApiKey).where(AgentApiKey.tenant_id == tenant.id).order_by(AgentApiKey.created_at.desc())
    )
    return [_key_info(k) for k in result.scalars().all()]


@router.post("/{tenant_id}/api-keys", response_model=CreatedKey, status_code=status.HTTP_201_CREATED)
async def create_tenant_key(
    tenant_id: UUID,
    body: CreateKeyRequest,
    service: TenantProvisioningService = Depends(get_provisioning_service),
):
    """
    Create an API key for one of a customer's agents. The key is returned once.

    Allowed permissions: chat, read, write, billing:read, handoff:read, handoff:write,
    knowledge:read, knowledge:write. Requires permission: tenants:manage
    """
    try:
        tenant = await service.get_managed(tenant_id)
        key, plain = await service.create_api_key(tenant, **body.model_dump())
    except ProvisioningError as err:
        raise _http(err) from err
    return CreatedKey(**_key_info(key).model_dump(), key=plain)


@router.delete("/{tenant_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_tenant_key(
    tenant_id: UUID,
    key_id: UUID,
    service: TenantProvisioningService = Depends(get_provisioning_service),
):
    """Revoke a customer's API key. Requires permission: tenants:manage"""
    try:
        tenant = await service.get_managed(tenant_id)
    except ProvisioningError as err:
        raise _http(err) from err
    key = await service.db.scalar(
        select(AgentApiKey).where(AgentApiKey.id == key_id, AgentApiKey.tenant_id == tenant.id)
    )
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    key.is_active = False
    await service.db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
