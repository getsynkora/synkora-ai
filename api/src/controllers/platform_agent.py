"""
Platform Engineer Agent Controller

GET  /api/v1/platform-agent/status     — plan access + configured flag
GET  /api/v1/platform-agent/llm-config — return current tenant's LLM config
POST /api/v1/platform-agent/llm-config — upsert current tenant's LLM config
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.agent_llm_config import AgentLLMConfig
from src.schemas.agent_llm_config import AgentLLMConfigResponse
from src.services.agents.llm_config_service import LLMConfigService

logger = logging.getLogger(__name__)

router = APIRouter()

PLATFORM_TENANT_ID = UUID("00000000-0000-0000-0000-000000000000")
PLATFORM_ENGINEER_AGENT_NAME = "platform_engineer_agent"


class PlatformAgentLLMConfigUpsert(BaseModel):
    """Request body for upsert — api_key is optional so updates don't require re-entering the key."""

    name: str
    provider: str
    model_name: str
    api_key: str | None = None
    api_base: str | None = None
    temperature: float | None = 0.7
    max_tokens: int | None = None
    top_p: float | None = None
    enabled: bool = True


class PlatformAgentStatusResponse(BaseModel):
    has_access: bool
    is_configured: bool
    agent_name: str
    provider: str | None = None
    model_name: str | None = None
    plan_tier: str


async def _get_platform_engineer_agent(db: AsyncSession) -> Agent | None:
    result = await db.execute(
        select(Agent).where(
            Agent.tenant_id == PLATFORM_TENANT_ID,
            Agent.agent_name == PLATFORM_ENGINEER_AGENT_NAME,
        )
    )
    return result.scalar_one_or_none()


@router.get("/status", response_model=PlatformAgentStatusResponse)
async def get_platform_agent_status(
    current_account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Return whether the current tenant has plan access to the platform engineer
    agent and whether they have configured an LLM API key for it.

    LLM config is managed via the standard agent LLM config page:
    /agents/platform_engineer_agent/llm-configs
    """
    from src.services.billing.plan_restriction_service import PlanRestrictionService

    restriction_service = PlanRestrictionService(db)

    has_access = await restriction_service.check_feature_access(tenant_id, "platform_engineer_agent")

    plan = await restriction_service.get_tenant_plan(tenant_id)
    plan_tier = plan.tier.value if plan else "FREE"

    agent = await _get_platform_engineer_agent(db)
    if not agent:
        return PlatformAgentStatusResponse(
            has_access=has_access,
            is_configured=False,
            agent_name=PLATFORM_ENGINEER_AGENT_NAME,
            plan_tier=plan_tier,
        )

    # Check if tenant has an LLM config row for this agent
    result = await db.execute(
        select(AgentLLMConfig).where(
            AgentLLMConfig.agent_id == agent.id,
            AgentLLMConfig.tenant_id == tenant_id,
            AgentLLMConfig.enabled.is_(True),
        )
    )
    llm_cfg = result.scalar_one_or_none()

    is_configured = bool(llm_cfg and llm_cfg.api_key)
    provider = llm_cfg.provider if llm_cfg else None
    model_name = llm_cfg.model_name if llm_cfg else None

    return PlatformAgentStatusResponse(
        has_access=has_access,
        is_configured=is_configured,
        agent_name=PLATFORM_ENGINEER_AGENT_NAME,
        provider=provider,
        model_name=model_name,
        plan_tier=plan_tier,
    )


@router.get("/llm-config", response_model=AgentLLMConfigResponse | None)
async def get_platform_agent_llm_config(
    current_account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Return the current tenant's LLM config for the platform engineer agent, or null."""
    agent = await _get_platform_engineer_agent(db)
    if not agent:
        return None

    configs = await LLMConfigService.get_agent_configs(session=db, agent_id=agent.id, tenant_id=tenant_id)
    return configs[0] if configs else None


@router.post("/llm-config", response_model=AgentLLMConfigResponse)
async def upsert_platform_agent_llm_config(
    config_data: PlatformAgentLLMConfigUpsert,
    current_account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """Create or update the current tenant's LLM config for the platform engineer agent."""
    from src.services.billing.plan_restriction_service import PlanRestrictionService

    restriction_service = PlanRestrictionService(db)
    has_access = await restriction_service.check_feature_access(tenant_id, "platform_engineer_agent")
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform Engineer Agent is not available on your current plan.",
        )

    agent = await _get_platform_engineer_agent(db)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform engineer agent not found. Run the seed script first.",
        )

    # Check for existing config — update if present, create if not
    configs = await LLMConfigService.get_agent_configs(session=db, agent_id=agent.id, tenant_id=tenant_id)

    if configs:
        existing = configs[0]
        updates: dict = {
            "name": config_data.name,
            "provider": config_data.provider,
            "model_name": config_data.model_name,
            "api_base": config_data.api_base,
            "temperature": config_data.temperature,
            "max_tokens": config_data.max_tokens,
            "top_p": config_data.top_p,
            "enabled": config_data.enabled if config_data.enabled is not None else True,
        }
        if config_data.api_key:
            updates["api_key"] = config_data.api_key
        config = await LLMConfigService.update_config(session=db, config_id=existing.id, tenant_id=tenant_id, **updates)
    else:
        config = await LLMConfigService.create_config(
            session=db,
            agent_id=agent.id,
            tenant_id=tenant_id,
            name=config_data.name,
            provider=config_data.provider,
            model_name=config_data.model_name,
            api_key=config_data.api_key or "",
            api_base=config_data.api_base,
            temperature=config_data.temperature,
            max_tokens=config_data.max_tokens,
            top_p=config_data.top_p,
            enabled=config_data.enabled if config_data.enabled is not None else True,
            is_default=True,
        )

    await db.commit()
    await db.refresh(config)

    # Invalidate agent cache so the new LLM config is picked up immediately
    try:
        from src.controllers.agents.llm_configs import invalidate_agent_llm_cache

        invalidate_agent_llm_cache(PLATFORM_ENGINEER_AGENT_NAME, str(tenant_id))
        logger.info("Invalidated PE agent cache after LLM config update")
    except Exception as e:
        logger.warning(f"Failed to invalidate PE agent cache: {e}")

    return config
