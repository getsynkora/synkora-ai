"""
Agent API Keys Controller - Internal API for managing API keys.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models import Account
from src.models.agent import Agent
from src.models.agent_api_key import AgentApiKey
from src.models.agent_api_usage import AgentApiUsage
from src.schemas.agent_api import (
    ApiKeyListResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    UpdateApiKeyRequest,
    UsageByEndpoint,
    UsageStats,
    UsageStatsResponse,
)
from src.services.agent_api.api_key_service import AgentApiKeyService

router = APIRouter(prefix="/api/v1/agent-api-keys", tags=["Agent API Keys"])


@router.post("", response_model=CreateApiKeyResponse)
async def create_api_key(
    request: CreateApiKeyRequest,
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create a new API key for agent integration.

    The full API key is only shown once at creation time.
    """
    # agent_id is required — the DB model has agent_id NOT NULL with FK to agents
    if not request.agent_id:
        raise HTTPException(status_code=422, detail="agent_id is required")

    # Verify the agent exists and belongs to this tenant
    result = await db.execute(
        select(Agent).filter(
            Agent.id == request.agent_id,
            Agent.tenant_id == tenant_id,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Create API key
    api_key, plain_key = await AgentApiKeyService.create_api_key(
        db=db,
        agent_id=request.agent_id,
        tenant_id=tenant_id,
        name=request.key_name,
        permissions=request.permissions,
        rate_limit_per_minute=request.rate_limit_per_minute,
        rate_limit_per_hour=request.rate_limit_per_hour,
        rate_limit_per_day=request.rate_limit_per_day,
        allowed_ips=request.allowed_ips,
        allowed_origins=request.allowed_origins,
        expires_at=request.expires_at,
    )

    return CreateApiKeyResponse(
        id=api_key.id,
        key_name=api_key.key_name,
        api_key=plain_key,
        key_prefix=api_key.key_prefix,
        agent_id=api_key.agent_id,
        permissions=api_key.permissions,
        rate_limit_per_minute=api_key.rate_limit_per_minute,
        rate_limit_per_hour=api_key.rate_limit_per_hour,
        rate_limit_per_day=api_key.rate_limit_per_day,
        allowed_ips=api_key.allowed_ips,
        allowed_origins=api_key.allowed_origins,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    agent_id: str | None = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all API keys for the tenant.

    Optionally filter by agent_id (UUID) or agent name.
    """
    query = select(AgentApiKey).filter(AgentApiKey.tenant_id == tenant_id)

    if agent_id:
        # Try to parse as UUID first
        try:
            agent_uuid = UUID(agent_id)
            query = query.filter(AgentApiKey.agent_id == agent_uuid)
        except ValueError:
            # If not a UUID, treat as agent slug and look up the agent
            result = await db.execute(
                select(Agent).filter(
                    Agent.slug == agent_id,
                    Agent.tenant_id == tenant_id,
                )
            )
            agent = result.scalar_one_or_none()
            if agent:
                query = query.filter(AgentApiKey.agent_id == agent.id)
            else:
                # Agent not found, return empty list
                return ApiKeyListResponse(keys=[], total=0)

    result = await db.execute(query.order_by(AgentApiKey.created_at.desc()))
    api_keys = result.scalars().all()

    return ApiKeyListResponse(
        keys=[ApiKeyResponse.model_validate(key) for key in api_keys],
        total=len(api_keys),
    )


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    key_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get details of a specific API key.
    """
    result = await db.execute(
        select(AgentApiKey).filter(
            AgentApiKey.id == key_id,
            AgentApiKey.tenant_id == tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    return ApiKeyResponse.model_validate(api_key)


@router.put("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: UUID,
    request: UpdateApiKeyRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update an API key's settings.

    Note: The actual key value cannot be changed, only its settings.
    """
    result = await db.execute(
        select(AgentApiKey).filter(
            AgentApiKey.id == key_id,
            AgentApiKey.tenant_id == tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Update fields
    if request.key_name is not None:
        api_key.key_name = request.key_name
    if request.is_active is not None:
        api_key.is_active = request.is_active
    if request.permissions is not None:
        api_key.permissions = request.permissions
    if request.rate_limit_per_minute is not None:
        api_key.rate_limit_per_minute = request.rate_limit_per_minute
    if request.rate_limit_per_hour is not None:
        api_key.rate_limit_per_hour = request.rate_limit_per_hour
    if request.rate_limit_per_day is not None:
        api_key.rate_limit_per_day = request.rate_limit_per_day
    if request.allowed_ips is not None:
        api_key.allowed_ips = request.allowed_ips
    if request.allowed_origins is not None:
        api_key.allowed_origins = request.allowed_origins
    if request.expires_at is not None:
        api_key.expires_at = request.expires_at

    api_key.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(api_key)

    return ApiKeyResponse.model_validate(api_key)


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete an API key.

    This action cannot be undone.
    """
    result = await db.execute(
        select(AgentApiKey).filter(
            AgentApiKey.id == key_id,
            AgentApiKey.tenant_id == tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    await db.delete(api_key)
    await db.commit()

    return {"message": "API key deleted successfully"}


@router.post("/{key_id}/regenerate", response_model=CreateApiKeyResponse)
async def regenerate_api_key(
    key_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Regenerate an API key.

    This creates a new key value while preserving all settings.
    The old key is immediately invalidated.
    """
    result = await db.execute(
        select(AgentApiKey).filter(
            AgentApiKey.id == key_id,
            AgentApiKey.tenant_id == tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Regenerate key by generating new key and updating
    plain_key, hashed_key = AgentApiKeyService.generate_api_key()
    api_key.api_key = hashed_key
    api_key.key_prefix = plain_key[:20]  # Must match the 20-char prefix used in validation
    api_key.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(api_key)

    new_key = api_key

    return CreateApiKeyResponse(
        id=new_key.id,
        key_name=new_key.key_name,
        api_key=plain_key,
        key_prefix=new_key.key_prefix,
        agent_id=new_key.agent_id,
        permissions=new_key.permissions,
        rate_limit_per_minute=new_key.rate_limit_per_minute,
        rate_limit_per_hour=new_key.rate_limit_per_hour,
        rate_limit_per_day=new_key.rate_limit_per_day,
        allowed_ips=new_key.allowed_ips,
        allowed_origins=new_key.allowed_origins,
        expires_at=new_key.expires_at,
        created_at=new_key.created_at,
    )


@router.get("/{key_id}/usage", response_model=UsageStatsResponse)
async def get_api_key_usage(
    key_id: UUID,
    days: int = 30,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get usage statistics for an API key.

    Returns overall stats and breakdown by endpoint.
    """
    # Verify API key exists and belongs to tenant
    result = await db.execute(
        select(AgentApiKey).filter(
            AgentApiKey.id == key_id,
            AgentApiKey.tenant_id == tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Calculate date range
    from datetime import timedelta

    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=days)

    # Get overall stats
    stats_result = await db.execute(
        select(
            func.count(AgentApiUsage.id).label("total_requests"),
            func.sum(AgentApiUsage.tokens_used).label("total_tokens"),
        ).filter(
            AgentApiUsage.api_key_id == key_id,
            AgentApiUsage.created_at >= start_date,
            AgentApiUsage.created_at <= end_date,
        )
    )
    stats = stats_result.first()

    overall = UsageStats(
        total_requests=stats.total_requests or 0,
        total_tokens=stats.total_tokens or 0,
        total_cost=0.0,  # Cost tracking not implemented in AgentApiUsage model
        period_start=start_date,
        period_end=end_date,
    )

    # Get stats by endpoint
    endpoint_result = await db.execute(
        select(
            AgentApiUsage.endpoint,
            func.count(AgentApiUsage.id).label("requests"),
            func.avg(AgentApiUsage.response_time_ms).label("avg_response_time"),
            func.sum(case((AgentApiUsage.status_code >= 400, 1), else_=0)).label("errors"),
        )
        .filter(
            AgentApiUsage.api_key_id == key_id,
            AgentApiUsage.created_at >= start_date,
            AgentApiUsage.created_at <= end_date,
        )
        .group_by(AgentApiUsage.endpoint)
    )
    endpoint_stats = endpoint_result.all()

    by_endpoint = []
    for row in endpoint_stats:
        error_rate = float(row.errors) / float(row.requests) if row.requests > 0 else 0.0
        by_endpoint.append(
            UsageByEndpoint(
                endpoint=row.endpoint,
                requests=row.requests,
                avg_response_time_ms=float(row.avg_response_time or 0),
                error_rate=error_rate,
            )
        )

    return UsageStatsResponse(overall=overall, by_endpoint=by_endpoint)
