"""DiscountCode service — create, validate, and apply discount codes."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_discount_code import AgentDiscountCode, DiscountType

logger = logging.getLogger(__name__)


class DiscountCodeService:
    """Service for managing agent discount codes."""

    @staticmethod
    async def create_code(
        agent_pricing_id: UUID,
        tenant_id: UUID,
        code: str,
        discount_type: DiscountType,
        discount_value: Decimal,
        db: AsyncSession,
        max_uses: int | None = None,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> AgentDiscountCode:
        """Create a new discount code."""
        code = code.upper().strip()

        # Check uniqueness within pricing
        result = await db.execute(
            select(AgentDiscountCode).where(
                AgentDiscountCode.agent_pricing_id == agent_pricing_id,
                AgentDiscountCode.code == code,
            )
        )
        if result.scalar_one_or_none():
            raise ValueError(f"Code '{code}' already exists for this agent pricing")

        discount = AgentDiscountCode(
            agent_pricing_id=agent_pricing_id,
            tenant_id=tenant_id,
            code=code,
            discount_type=discount_type,
            discount_value=discount_value,
            max_uses=max_uses,
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=True,
        )
        db.add(discount)
        await db.commit()
        await db.refresh(discount)
        return discount

    @staticmethod
    async def validate_code(
        code: str,
        agent_pricing_id: UUID,
        db: AsyncSession,
    ) -> AgentDiscountCode | None:
        """Validate a discount code. Returns the code if valid, None otherwise."""
        code = code.upper().strip()
        now = datetime.now(UTC)

        result = await db.execute(
            select(AgentDiscountCode).where(
                AgentDiscountCode.agent_pricing_id == agent_pricing_id,
                AgentDiscountCode.code == code,
                AgentDiscountCode.is_active.is_(True),
            )
        )
        discount = result.scalar_one_or_none()
        if discount is None:
            return None

        # Check validity window
        if discount.valid_from and now < discount.valid_from:
            return None
        if discount.valid_until and now > discount.valid_until:
            return None

        # Check usage limit
        if discount.max_uses is not None and discount.used_count >= discount.max_uses:
            return None

        return discount

    @staticmethod
    async def apply_and_consume(
        discount_id: UUID,
        base_credits: int,
        db: AsyncSession,
    ) -> int:
        """Apply discount and increment used_count atomically. Returns discounted credit amount."""
        result = await db.execute(
            select(AgentDiscountCode).where(AgentDiscountCode.id == discount_id).with_for_update()
        )
        discount = result.scalar_one_or_none()
        if discount is None:
            raise ValueError("Discount code not found")

        # Re-validate usage limit under lock
        if discount.max_uses is not None and discount.used_count >= discount.max_uses:
            raise ValueError("Discount code usage limit reached")

        # Calculate discounted amount
        if discount.discount_type == DiscountType.PERCENTAGE:
            reduction = int(base_credits * float(discount.discount_value) / 100)
        else:  # FLAT_CREDITS
            reduction = int(discount.discount_value)

        discounted = max(0, base_credits - reduction)

        # Consume usage
        discount.used_count += 1
        await db.commit()

        return discounted
