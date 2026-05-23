"""
Usage statistics controller
"""

import logging
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.services.billing import CreditService, PlanRestrictionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/usage-stats", tags=["usage-stats"])


class UsageStatsResponse(BaseModel):
    """Response model for usage statistics"""

    plan_name: str
    plan_tier: str
    limits: dict[str, Any]
    current_usage: dict[str, int]
    usage_percentage: dict[str, float]
    credit_balance: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=UsageStatsResponse)
async def get_usage_stats(
    db: AsyncSession = Depends(get_async_db),
    current_account=Depends(get_current_account),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
):
    """
    Get current usage statistics for the tenant's subscription plan.

    Returns:
    - Plan name and tier
    - Plan limits for agents, team members, and API calls
    - Current usage counts
    - Usage percentage for each resource
    """
    try:
        restriction_service = PlanRestrictionService(db)
        credit_service = CreditService(db)

        # Get full usage stats + plan in one call
        stats = await restriction_service.get_usage_stats(tenant_id)
        plan = await restriction_service.get_tenant_plan(tenant_id)

        # Get credit balance
        credit_balance = await credit_service.get_balance(tenant_id)

        usage = stats.get("usage", {})

        def _pct(current: int, limit: int | None) -> float:
            return round(current / limit * 100, 2) if limit else 0.0

        agents = usage.get("agents", {})
        team_members = usage.get("team_members", {})

        return UsageStatsResponse(
            plan_name=stats.get("plan_name", "Free"),
            plan_tier=stats.get("plan_tier", "FREE"),
            limits={
                "max_agents": plan.max_agents if plan else None,
                "max_team_members": plan.max_team_members if plan else None,
                "max_api_calls_per_month": plan.max_api_calls_per_month if plan else None,
                "max_knowledge_bases": plan.max_knowledge_bases if plan else None,
                "max_data_sources": plan.max_data_sources if plan else None,
                "max_custom_tools": plan.max_custom_tools if plan else None,
                "max_database_connections": plan.max_database_connections if plan else None,
                "max_mcp_servers": plan.max_mcp_servers if plan else None,
                "max_scheduled_tasks": plan.max_scheduled_tasks if plan else None,
                "max_widgets": plan.max_widgets if plan else None,
                "max_slack_bots": plan.max_slack_bots if plan else None,
                "features": plan.features or {} if plan else {},
            },
            current_usage={
                "agents": agents.get("current", 0),
                "team_members": team_members.get("current", 0),
                "api_calls_this_month": 0,
            },
            usage_percentage={
                "agents": _pct(agents.get("current", 0), agents.get("limit")),
                "team_members": _pct(team_members.get("current", 0), team_members.get("limit")),
                "api_calls": 0.0,
            },
            credit_balance=credit_balance.available_credits if credit_balance else None,
        )

    except Exception as e:
        logger.error(f"Error getting usage stats: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get usage statistics")
