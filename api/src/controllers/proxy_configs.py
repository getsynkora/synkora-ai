"""Proxy Config API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.proxy_config import ProxyConfig, ProxyProvider
from src.schemas.load_testing import (
    CreateProxyConfigRequest,
    CreateProxyConfigResponse,
    ProxyConfigListResponse,
    ProxyConfigResponse,
    ProxyUsageResponse,
    UpdateProxyConfigRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proxy/configs", tags=["proxy"])


@router.post("", response_model=CreateProxyConfigResponse, status_code=201)
async def create_proxy_config(
    request: CreateProxyConfigRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create a new proxy configuration with API key."""
    try:
        # Validate provider
        try:
            provider = ProxyProvider(request.provider)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {request.provider}")

        # Generate API key
        api_key, api_key_prefix, api_key_hash = ProxyConfig.generate_api_key()

        # Create proxy config
        proxy_config = ProxyConfig(
            tenant_id=tenant_id,
            name=request.name,
            provider=provider,
            api_key_hash=api_key_hash,
            api_key_prefix=api_key_prefix,
            mock_config=request.mock_config.model_dump() if request.mock_config else {},
            rate_limit=request.rate_limit,
            is_active=True,
        )

        db.add(proxy_config)
        await db.commit()
        await db.refresh(proxy_config)

        logger.info(f"Created proxy config: {proxy_config.name} (ID: {proxy_config.id})")

        return CreateProxyConfigResponse(
            id=proxy_config.id,
            tenant_id=proxy_config.tenant_id,
            name=proxy_config.name,
            provider=proxy_config.provider.value,
            api_key=api_key,  # Only returned at creation
            api_key_prefix=proxy_config.api_key_prefix,
            mock_config=proxy_config.mock_config or {},
            rate_limit=proxy_config.rate_limit,
            is_active=proxy_config.is_active,
            usage_count=proxy_config.usage_count,
            total_tokens_generated=proxy_config.total_tokens_generated,
            created_at=proxy_config.created_at,
            updated_at=proxy_config.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating proxy config: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=ProxyConfigListResponse)
async def list_proxy_configs(
    is_active: bool | None = Query(None),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """List all proxy configurations."""
    try:
        query = select(ProxyConfig).filter(ProxyConfig.tenant_id == tenant_id)

        if is_active is not None:
            query = query.filter(ProxyConfig.is_active == is_active)

        query = query.order_by(ProxyConfig.created_at.desc())

        result = await db.execute(query)
        configs = result.scalars().all()

        return ProxyConfigListResponse(
            items=[_proxy_config_to_response(c) for c in configs],
            total=len(configs),
        )

    except Exception as e:
        logger.error(f"Error listing proxy configs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{config_id}", response_model=ProxyConfigResponse)
async def get_proxy_config(
    config_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific proxy configuration."""
    try:
        proxy_config = await _get_proxy_config(db, config_id, tenant_id)
        return _proxy_config_to_response(proxy_config)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting proxy config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{config_id}", response_model=ProxyConfigResponse)
async def update_proxy_config(
    config_id: UUID,
    request: UpdateProxyConfigRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a proxy configuration."""
    try:
        proxy_config = await _get_proxy_config(db, config_id, tenant_id)

        if request.name is not None:
            proxy_config.name = request.name
        if request.provider is not None:
            try:
                proxy_config.provider = ProxyProvider(request.provider)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid provider: {request.provider}")
        if request.mock_config is not None:
            proxy_config.mock_config = request.mock_config.model_dump()
        if request.rate_limit is not None:
            proxy_config.rate_limit = request.rate_limit
        if request.is_active is not None:
            proxy_config.is_active = request.is_active

        await db.commit()
        await db.refresh(proxy_config)

        logger.info(f"Updated proxy config: {proxy_config.name} (ID: {proxy_config.id})")

        return _proxy_config_to_response(proxy_config)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating proxy config: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{config_id}", status_code=204)
async def delete_proxy_config(
    config_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Delete a proxy configuration."""
    try:
        proxy_config = await _get_proxy_config(db, config_id, tenant_id)

        await db.delete(proxy_config)
        await db.commit()

        logger.info(f"Deleted proxy config: {proxy_config.name} (ID: {proxy_config.id})")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting proxy config: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{config_id}/regenerate-key", response_model=CreateProxyConfigResponse)
async def regenerate_api_key(
    config_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Regenerate API key for a proxy configuration."""
    try:
        proxy_config = await _get_proxy_config(db, config_id, tenant_id)

        # Generate new API key
        api_key, api_key_prefix, api_key_hash = ProxyConfig.generate_api_key()

        proxy_config.api_key_hash = api_key_hash
        proxy_config.api_key_prefix = api_key_prefix

        await db.commit()
        await db.refresh(proxy_config)

        logger.info(f"Regenerated API key for proxy config: {proxy_config.id}")

        return CreateProxyConfigResponse(
            id=proxy_config.id,
            tenant_id=proxy_config.tenant_id,
            name=proxy_config.name,
            provider=proxy_config.provider.value,
            api_key=api_key,  # Return new key
            api_key_prefix=proxy_config.api_key_prefix,
            mock_config=proxy_config.mock_config or {},
            rate_limit=proxy_config.rate_limit,
            is_active=proxy_config.is_active,
            usage_count=proxy_config.usage_count,
            total_tokens_generated=proxy_config.total_tokens_generated,
            created_at=proxy_config.created_at,
            updated_at=proxy_config.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating API key: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{config_id}/usage", response_model=ProxyUsageResponse)
async def get_proxy_usage(
    config_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Get usage statistics for a proxy configuration."""
    try:
        proxy_config = await _get_proxy_config(db, config_id, tenant_id)

        # Get usage stats from Redis

        from src.config.redis import get_redis_async

        redis = get_redis_async()

        # Get hourly and daily counts from Redis
        hour_key = f"proxy:{config_id}:requests:hour"
        day_key = f"proxy:{config_id}:requests:day"

        requests_last_hour = int(await redis.get(hour_key) or 0)
        requests_last_day = int(await redis.get(day_key) or 0)

        # Calculate error rate from Redis
        error_key = f"proxy:{config_id}:errors:day"
        errors_last_day = int(await redis.get(error_key) or 0)
        error_rate = errors_last_day / max(requests_last_day, 1)

        return ProxyUsageResponse(
            proxy_config_id=config_id,
            total_requests=proxy_config.usage_count,
            total_tokens=proxy_config.total_tokens_generated,
            requests_last_hour=requests_last_hour,
            requests_last_day=requests_last_day,
            error_rate=error_rate,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting proxy usage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Helper Functions
# ============================================================================


async def _get_proxy_config(db: AsyncSession, config_id: UUID, tenant_id: UUID) -> ProxyConfig:
    """Get a proxy config by ID with tenant verification."""
    result = await db.execute(
        select(ProxyConfig).filter(ProxyConfig.id == config_id, ProxyConfig.tenant_id == tenant_id)
    )
    proxy_config = result.scalar_one_or_none()

    if not proxy_config:
        raise HTTPException(status_code=404, detail="Proxy configuration not found")

    return proxy_config


def _proxy_config_to_response(proxy_config: ProxyConfig) -> ProxyConfigResponse:
    """Convert ProxyConfig model to response schema."""
    return ProxyConfigResponse(
        id=proxy_config.id,
        tenant_id=proxy_config.tenant_id,
        name=proxy_config.name,
        provider=proxy_config.provider.value,
        api_key_prefix=proxy_config.api_key_prefix,
        mock_config=proxy_config.mock_config or {},
        rate_limit=proxy_config.rate_limit,
        is_active=proxy_config.is_active,
        usage_count=proxy_config.usage_count,
        total_tokens_generated=proxy_config.total_tokens_generated,
        created_at=proxy_config.created_at,
        updated_at=proxy_config.updated_at,
    )
