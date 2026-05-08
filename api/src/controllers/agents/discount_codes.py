"""Discount code endpoints for agent pricing."""

import logging
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id
from src.models.agent import Agent
from src.models.agent_discount_code import AgentDiscountCode, DiscountType
from src.models.agent_pricing import AgentPricing
from src.services.billing.discount_code_service import DiscountCodeService

logger = logging.getLogger(__name__)

router = APIRouter()  # Auth: prefix /api/v1/agents
public_router = APIRouter()  # Public: no prefix


class CreateDiscountCodeRequest(BaseModel):
    code: str
    discount_type: DiscountType
    discount_value: Decimal
    max_uses: int | None = None
    valid_from: str | None = None  # ISO datetime string
    valid_until: str | None = None


class ValidateDiscountRequest(BaseModel):
    code: str
    agent_pricing_id: UUID


@router.get("/{agent_name}/discount-codes")
async def list_discount_codes(
    agent_name: str,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List discount codes for an agent."""
    agent_result = await db.execute(select(Agent).where(Agent.agent_name == agent_name, Agent.tenant_id == tenant_id))
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    pricing_result = await db.execute(select(AgentPricing).where(AgentPricing.agent_id == agent.id))
    pricing = pricing_result.scalar_one_or_none()
    if pricing is None:
        return {"codes": []}

    codes_result = await db.execute(select(AgentDiscountCode).where(AgentDiscountCode.agent_pricing_id == pricing.id))
    codes = codes_result.scalars().all()
    return {"codes": [c.__dict__ for c in codes]}


@router.post("/{agent_name}/discount-codes")
async def create_discount_code(
    agent_name: str,
    body: CreateDiscountCodeRequest,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Create a discount code for an agent."""
    from datetime import UTC, datetime

    agent_result = await db.execute(select(Agent).where(Agent.agent_name == agent_name, Agent.tenant_id == tenant_id))
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    pricing_result = await db.execute(select(AgentPricing).where(AgentPricing.agent_id == agent.id))
    pricing = pricing_result.scalar_one_or_none()
    if pricing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent has no pricing configuration")

    def _parse_dt(s: str) -> datetime:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)

    valid_from = _parse_dt(body.valid_from) if body.valid_from else None
    valid_until = _parse_dt(body.valid_until) if body.valid_until else None

    try:
        code = await DiscountCodeService.create_code(
            agent_pricing_id=pricing.id,
            tenant_id=tenant_id,
            code=body.code,
            discount_type=body.discount_type,
            discount_value=body.discount_value,
            db=db,
            max_uses=body.max_uses,
            valid_from=valid_from,
            valid_until=valid_until,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"code": code.__dict__}


@router.delete("/{agent_name}/discount-codes/{code_id}")
async def delete_discount_code(
    agent_name: str,
    code_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    account=Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Deactivate a discount code."""
    result = await db.execute(
        select(AgentDiscountCode).where(
            AgentDiscountCode.id == code_id,
            AgentDiscountCode.tenant_id == tenant_id,
        )
    )
    code = result.scalar_one_or_none()
    if code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discount code not found")

    code.is_active = False
    await db.commit()
    return {"deleted": True}


@public_router.post("/api/public/discount-codes/validate")
async def validate_discount_code(body: ValidateDiscountRequest, db: AsyncSession = Depends(get_async_db)):
    """Validate a discount code publicly."""
    discount = await DiscountCodeService.validate_code(body.code, body.agent_pricing_id, db)
    if discount is None:
        return {"valid": False}
    return {
        "valid": True,
        "discount_type": discount.discount_type,
        "discount_value": float(discount.discount_value),
    }
