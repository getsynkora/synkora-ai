"""
Controller for managing agent LLM configurations.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.schemas.agent_llm_config import (
    AgentLLMConfigCreate,
    AgentLLMConfigReorder,
    AgentLLMConfigResponse,
    AgentLLMConfigUpdate,
)
from src.services.agents.llm_config_service import LLMConfigService
from src.services.agents.llm_provider_presets import (
    get_all_models_for_comparison,
    get_all_providers,
    get_provider_models,
    get_provider_preset,
)
from src.services.cache import get_agent_cache

logger = logging.getLogger(__name__)
router = APIRouter()

# Separate router for LLM provider endpoints (no agent context needed)
providers_router = APIRouter(prefix="/api/v1", tags=["llm-providers"])


def invalidate_agent_llm_cache(agent_name: str, tenant_id: str = ""):
    """Invalidate agent cache and remove from memory when LLM configs change.

    Args:
        agent_name: Name of the agent whose cache should be invalidated.
        tenant_id: Tenant whose cache entry should be deleted.  Must be supplied
                   so the correct tenant-scoped key is removed; without it the
                   deletion targets a key that does not exist and becomes a no-op.
    """
    logger.info(f"Starting cache invalidation for agent '{agent_name}' (tenant={tenant_id or 'unscoped'})...")

    # Step 1: Invalidate Redis cache using sync client
    try:
        from src.config.redis import get_redis

        cache = get_agent_cache()
        sync_redis = get_redis()
        if sync_redis:
            # Tenant-scoped config key — matches what _cache_agent stores
            config_key = cache._agent_config_key(agent_name, tenant_id)
            # Routing LLM-configs cache is not tenant-scoped (no API keys, just metadata)
            llm_configs_key = cache._build_key("llm_configs", agent_name)
            deleted = sync_redis.delete(config_key, llm_configs_key)
            logger.info(f"Deleted Redis cache keys '{config_key}', '{llm_configs_key}' (deleted: {deleted})")
        else:
            logger.warning("Redis not available, skipping cache invalidation")
    except Exception as e:
        logger.error(f"Error invalidating Redis cache: {e}")

    # Step 2: Remove agent from in-memory registry (best-effort; agent reloads on next request)
    try:
        from src.services.agents.agent_manager import AgentManager

        agent_manager = AgentManager()

        if agent_name in agent_manager.registry:
            # Try tenant-scoped unregister first; fall back to zero-UUID (platform agents)
            for reg_tenant in [tenant_id, "00000000-0000-0000-0000-000000000000"]:
                try:
                    agent_manager.registry.unregister(agent_name, reg_tenant)
                    logger.info(f"Removed agent '{agent_name}' from memory registry (tenant={reg_tenant})")
                    break
                except KeyError:
                    continue
        else:
            logger.info(f"Agent '{agent_name}' not in memory registry, no need to remove")
    except Exception as e:
        logger.warning(f"Failed to remove agent from memory (non-critical): {e}")

    logger.info(f"Cache invalidation complete for agent '{agent_name}'")


async def get_agent_by_name_or_id(
    agent_identifier: str, tenant_id: UUID, db: AsyncSession, allow_public: bool = True
) -> Agent:
    """Get agent by name or ID and verify user has access.

    Args:
        agent_identifier: Agent name or UUID
        tenant_id: Current user's tenant ID
        db: Database session
        allow_public: If True, also allow access to public agents (default: True)

    Returns:
        Agent instance

    Raises:
        HTTPException: If agent not found or access denied
    """
    agent = None

    # Try to parse as UUID first
    try:
        agent_id = UUID(agent_identifier)
        result = await db.execute(select(Agent).filter(Agent.id == agent_id, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        # If not found and allow_public, check for public agent
        if not agent and allow_public:
            result = await db.execute(select(Agent).filter(Agent.id == agent_id, Agent.is_public.is_(True)))
            agent = result.scalar_one_or_none()
    except ValueError:
        # If not a valid UUID, treat as agent name
        result = await db.execute(select(Agent).filter(Agent.slug == agent_identifier, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()
        # If not found and allow_public, check for public agent
        if not agent and allow_public:
            result = await db.execute(select(Agent).filter(Agent.slug == agent_identifier, Agent.is_public.is_(True)))
            agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    return agent


@router.post("/{agent_slug}/llm-configs", response_model=AgentLLMConfigResponse)
async def create_llm_config(
    agent_slug: str,
    config_data: AgentLLMConfigCreate,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Create a new LLM configuration for an agent."""
    # Get agent by name or ID and verify access (don't allow modifying public agents you don't own)
    agent = await get_agent_by_name_or_id(agent_slug, tenant_id, db, allow_public=False)

    try:
        # Default enabled to True if not provided
        enabled = config_data.enabled if config_data.enabled is not None else True

        config = await LLMConfigService.create_config(
            session=db,
            agent_id=agent.id,
            tenant_id=tenant_id,
            name=config_data.name,
            provider=config_data.provider,
            model_name=config_data.model_name,
            api_key=config_data.api_key,
            api_base=config_data.api_base,
            temperature=config_data.temperature,
            max_tokens=config_data.max_tokens,
            top_p=config_data.top_p,
            additional_params=config_data.additional_params,
            is_default=config_data.is_default,
            display_order=config_data.display_order,
            enabled=enabled,
            routing_rules=config_data.routing_rules,
            routing_weight=config_data.routing_weight,
        )

        await db.commit()
        await db.refresh(config)

        # Invalidate cache after creating LLM config
        invalidate_agent_llm_cache(agent.slug, str(tenant_id))

        return AgentLLMConfigResponse(
            id=config.id,
            agent_id=config.agent_id,
            tenant_id=config.tenant_id,
            name=config.name,
            provider=config.provider,
            model_name=config.model_name,
            api_base=config.api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            additional_params=config.additional_params,
            is_default=config.is_default,
            display_order=config.display_order,
            enabled=config.enabled,
            routing_rules=config.routing_rules,
            routing_weight=config.routing_weight,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
        )
    except Exception as e:
        await db.rollback()
        logger.warning(f"Failed to create LLM config: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create LLM configuration")


@providers_router.get("/llm-providers")
def list_llm_providers():
    """List all available LLM provider presets."""
    providers = get_all_providers()
    return [
        {
            "provider_id": p.provider_id,
            "provider_name": p.provider_name,
            "description": p.description,
            "requires_api_key": p.requires_api_key,
            "requires_api_base": p.requires_api_base,
            "default_api_base": p.default_api_base,
            "setup_instructions": p.setup_instructions,
            "documentation_url": p.documentation_url,
            "model_count": len(p.models) if p.models else 0,
        }
        for p in providers
    ]


@providers_router.get("/llm-providers/compare")
def compare_llm_models(
    filter: str | None = None,
    sort_by: str | None = None,
):
    """Return a flat list of all models across all providers with comparison metadata.

    Query params:
      filter  – "open_source" | "cheap" | "fast" | "quality"
      sort_by – "quality" (default) | "cost" | "speed"
    """
    models = get_all_models_for_comparison()

    # Apply filters
    if filter == "open_source":
        models = [m for m in models if m.get("is_open_source")]
    elif filter == "cheap":
        models = [m for m in models if m.get("cost_input_per_1m") is not None and m["cost_input_per_1m"] <= 1.0]
    elif filter == "fast":
        models = [m for m in models if m.get("speed_tier") == "fast"]
    elif filter == "quality":
        models = [m for m in models if m.get("quality_score") is not None and m["quality_score"] >= 9.0]

    # Apply sorting
    if sort_by == "cost":
        models.sort(key=lambda m: (m.get("cost_input_per_1m") is None, m.get("cost_input_per_1m") or 0))
    elif sort_by == "speed":
        _speed_order = {"fast": 0, "medium": 1, "slow": 2}
        models.sort(key=lambda m: _speed_order.get(m.get("speed_tier") or "", 3))
    else:
        # Default: quality descending, unknowns last
        models.sort(key=lambda m: -(m.get("quality_score") or 0))

    return models


@providers_router.get("/llm-providers/{provider_id}")
def get_llm_provider(provider_id: str):
    """Get details for a specific LLM provider including available models."""
    from src.services.agents.llm_provider_presets import enrich_model_with_comparison

    provider = get_provider_preset(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Provider '{provider_id}' not found")

    return {
        "provider_id": provider.provider_id,
        "provider_name": provider.provider_name,
        "description": provider.description,
        "requires_api_key": provider.requires_api_key,
        "requires_api_base": provider.requires_api_base,
        "default_api_base": provider.default_api_base,
        "setup_instructions": provider.setup_instructions,
        "documentation_url": provider.documentation_url,
        "models": [
            {
                "name": m.name,
                "model_name": m.model_name,
                "description": m.description,
                "default_temperature": m.default_temperature,
                "default_max_tokens": m.default_max_tokens,
                "default_top_p": m.default_top_p,
                "additional_params": m.additional_params,
                "max_input_tokens": m.max_input_tokens,
                "max_output_tokens": m.max_output_tokens,
                "cost_input_per_1m": em.cost_input_per_1m,
                "cost_output_per_1m": em.cost_output_per_1m,
                "is_open_source": em.is_open_source,
                "quality_score": em.quality_score,
                "speed_tier": em.speed_tier,
                "tags": em.tags,
            }
            for m in (provider.models or [])
            for em in [enrich_model_with_comparison(m)]
        ],
    }


@providers_router.get("/llm-providers/{provider_id}/models")
def list_provider_models(provider_id: str):
    """List all models for a specific provider."""
    from src.services.agents.llm_provider_presets import enrich_model_with_comparison

    models = get_provider_models(provider_id)
    if not models:
        provider = get_provider_preset(provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Provider '{provider_id}' not found")
        return []

    return [
        {
            "name": em.name,
            "model_name": em.model_name,
            "description": em.description,
            "default_temperature": em.default_temperature,
            "default_max_tokens": em.default_max_tokens,
            "default_top_p": em.default_top_p,
            "additional_params": em.additional_params,
            "max_input_tokens": em.max_input_tokens,
            "max_output_tokens": em.max_output_tokens,
            "cost_input_per_1m": em.cost_input_per_1m,
            "cost_output_per_1m": em.cost_output_per_1m,
            "is_open_source": em.is_open_source,
            "quality_score": em.quality_score,
            "speed_tier": em.speed_tier,
            "tags": em.tags,
        }
        for m in models
        for em in [enrich_model_with_comparison(m)]
    ]


@router.get("/{agent_slug}/llm-configs", response_model=list[AgentLLMConfigResponse])
async def list_llm_configs(
    agent_slug: str,
    enabled_only: bool = False,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List all LLM configurations for an agent.

    For public agents, returns configs using the agent owner's tenant_id.
    """
    # Get agent by name or ID and verify access (allow public agents)
    agent = await get_agent_by_name_or_id(agent_slug, tenant_id, db, allow_public=True)

    # Use the agent's tenant_id to fetch configs (important for public agents)
    configs = await LLMConfigService.get_agent_configs(
        session=db, agent_id=agent.id, tenant_id=agent.tenant_id, enabled_only=enabled_only
    )

    return [
        AgentLLMConfigResponse(
            id=config.id,
            agent_id=config.agent_id,
            tenant_id=config.tenant_id,
            name=config.name,
            provider=config.provider,
            model_name=config.model_name,
            api_base=config.api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            additional_params=config.additional_params,
            is_default=config.is_default,
            display_order=config.display_order,
            enabled=config.enabled,
            routing_rules=config.routing_rules,
            routing_weight=config.routing_weight,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
        )
        for config in configs
    ]


@router.get("/{agent_slug}/llm-configs/{config_id}", response_model=AgentLLMConfigResponse)
async def get_llm_config(
    agent_slug: str,
    config_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get a specific LLM configuration.

    For public agents, returns config using the agent owner's tenant_id.
    """
    # Get agent by name or ID and verify access (allow public agents)
    agent = await get_agent_by_name_or_id(agent_slug, tenant_id, db, allow_public=True)

    # Use the agent's tenant_id to fetch config (important for public agents)
    config = await LLMConfigService.get_config(session=db, config_id=config_id, tenant_id=agent.tenant_id)

    if not config or config.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM configuration not found")

    return AgentLLMConfigResponse(
        id=config.id,
        agent_id=config.agent_id,
        tenant_id=config.tenant_id,
        name=config.name,
        provider=config.provider,
        model_name=config.model_name,
        api_base=config.api_base,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        top_p=config.top_p,
        additional_params=config.additional_params,
        is_default=config.is_default,
        display_order=config.display_order,
        enabled=config.enabled,
        routing_rules=config.routing_rules,
        routing_weight=config.routing_weight,
        created_at=config.created_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
    )


@router.patch("/{agent_slug}/llm-configs/{config_id}", response_model=AgentLLMConfigResponse)
async def update_llm_config(
    agent_slug: str,
    config_id: UUID,
    config_data: AgentLLMConfigUpdate,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Update an LLM configuration."""
    # Get agent by name or ID and verify access (don't allow modifying public agents you don't own)
    agent = await get_agent_by_name_or_id(agent_slug, tenant_id, db, allow_public=False)

    # Verify config belongs to this agent
    existing_config = await LLMConfigService.get_config(session=db, config_id=config_id, tenant_id=tenant_id)

    if not existing_config or existing_config.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM configuration not found")

    try:
        # Only include non-None values in the update
        update_data = {k: v for k, v in config_data.model_dump().items() if v is not None}

        config = await LLMConfigService.update_config(
            session=db, config_id=config_id, tenant_id=tenant_id, **update_data
        )

        await db.commit()
        await db.refresh(config)

        # Invalidate cache after updating LLM config
        invalidate_agent_llm_cache(agent.slug, str(tenant_id))

        return AgentLLMConfigResponse(
            id=config.id,
            agent_id=config.agent_id,
            tenant_id=config.tenant_id,
            name=config.name,
            provider=config.provider,
            model_name=config.model_name,
            api_base=config.api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            additional_params=config.additional_params,
            is_default=config.is_default,
            display_order=config.display_order,
            enabled=config.enabled,
            routing_rules=config.routing_rules,
            routing_weight=config.routing_weight,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
        )
    except Exception as e:
        await db.rollback()
        logger.warning(f"Failed to update LLM config: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update LLM configuration")


@router.delete("/{agent_slug}/llm-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    agent_slug: str,
    config_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Delete an LLM configuration."""
    # Get agent by name or ID and verify access (don't allow modifying public agents you don't own)
    agent = await get_agent_by_name_or_id(agent_slug, tenant_id, db, allow_public=False)

    # Verify config belongs to this agent
    existing_config = await LLMConfigService.get_config(session=db, config_id=config_id, tenant_id=tenant_id)

    if not existing_config or existing_config.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM configuration not found")

    try:
        await LLMConfigService.delete_config(session=db, config_id=config_id, tenant_id=tenant_id)

        await db.commit()

        # Invalidate cache after deleting LLM config
        invalidate_agent_llm_cache(agent.slug, str(tenant_id))
    except ValueError as e:
        await db.rollback()
        logger.warning(f"Failed to delete LLM config (ValueError): {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to delete LLM configuration")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete LLM config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete LLM configuration"
        )


@router.post("/{agent_slug}/llm-configs/{config_id}/set-default", response_model=AgentLLMConfigResponse)
async def set_default_config(
    agent_slug: str,
    config_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Set an LLM configuration as the default."""
    # Get agent by name or ID and verify access (don't allow modifying public agents you don't own)
    agent = await get_agent_by_name_or_id(agent_slug, tenant_id, db, allow_public=False)

    # Verify config belongs to this agent
    existing_config = await LLMConfigService.get_config(session=db, config_id=config_id, tenant_id=tenant_id)

    if not existing_config or existing_config.agent_id != agent.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM configuration not found")

    try:
        config = await LLMConfigService.set_default_config(session=db, config_id=config_id, tenant_id=tenant_id)

        await db.commit()
        await db.refresh(config)

        # Invalidate cache after setting default LLM config
        invalidate_agent_llm_cache(agent.slug, str(tenant_id))

        return AgentLLMConfigResponse(
            id=config.id,
            agent_id=config.agent_id,
            tenant_id=config.tenant_id,
            name=config.name,
            provider=config.provider,
            model_name=config.model_name,
            api_base=config.api_base,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            additional_params=config.additional_params,
            is_default=config.is_default,
            display_order=config.display_order,
            enabled=config.enabled,
            routing_rules=config.routing_rules,
            routing_weight=config.routing_weight,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
        )
    except Exception as e:
        await db.rollback()
        logger.warning(f"Failed to set default LLM config: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to set default LLM configuration")


@router.post("/{agent_slug}/llm-configs/reorder", response_model=list[AgentLLMConfigResponse])
async def reorder_configs(
    agent_slug: str,
    reorder_data: AgentLLMConfigReorder,
    db: AsyncSession = Depends(get_async_db),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Reorder LLM configurations."""
    # Get agent by name or ID and verify access (don't allow modifying public agents you don't own)
    agent = await get_agent_by_name_or_id(agent_slug, tenant_id, db, allow_public=False)

    try:
        configs = await LLMConfigService.reorder_configs(
            session=db, agent_id=agent.id, tenant_id=tenant_id, config_orders=reorder_data.config_orders
        )

        await db.commit()
        for config in configs:
            await db.refresh(config)

        return [
            AgentLLMConfigResponse(
                id=config.id,
                agent_id=config.agent_id,
                tenant_id=config.tenant_id,
                name=config.name,
                provider=config.provider,
                model_name=config.model_name,
                api_base=config.api_base,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                additional_params=config.additional_params,
                is_default=config.is_default,
                display_order=config.display_order,
                enabled=config.enabled,
                routing_rules=config.routing_rules,
                routing_weight=config.routing_weight,
                created_at=config.created_at.isoformat(),
                updated_at=config.updated_at.isoformat(),
            )
            for config in configs
        ]
    except Exception as e:
        await db.rollback()
        logger.warning(f"Failed to reorder LLM configs: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to reorder LLM configurations")
