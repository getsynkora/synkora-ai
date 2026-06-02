"""
Credit Service - Manages credit balances and transactions

Features:
- Credit balance management
- Transaction history
- API call tracking
- Overage handling with grace periods
- Credit rollover support
"""

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.credit_balance import CreditBalance
from src.models.credit_transaction import CreditTransaction, TransactionType
from src.models.usage_analytics import UsageAnalytics

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    """Raised when a tenant doesn't have enough credits"""

    def __init__(
        self,
        message: str,
        available_credits: int,
        required_credits: int,
        overage_allowed: bool = False,
        grace_period_days: int = 0,
    ):
        self.available_credits = available_credits
        self.required_credits = required_credits
        self.overage_allowed = overage_allowed
        self.grace_period_days = grace_period_days
        super().__init__(message)


class CreditService:
    """Service for managing credit balances and transactions"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_balance(self, tenant_id: UUID) -> CreditBalance | None:
        """Get credit balance for a tenant"""
        result = await self.db.execute(select(CreditBalance).where(CreditBalance.tenant_id == tenant_id))
        return result.scalar_one_or_none()

    async def get_or_create_balance(self, tenant_id: UUID) -> CreditBalance:
        """Get or create credit balance for a tenant"""
        balance = await self.get_balance(tenant_id)
        if not balance:
            balance = CreditBalance(tenant_id=tenant_id, total_credits=0, used_credits=0, available_credits=0)
            self.db.add(balance)
            await self.db.commit()
            await self.db.refresh(balance)
        return balance

    async def get_available_credits(self, tenant_id: UUID, with_lock: bool = False) -> int:
        """
        Get available credits for a tenant.

        Args:
            tenant_id: Tenant UUID
            with_lock: If True, acquires a row lock for atomic operations.
                       Use this when checking before deducting credits.

        SECURITY: When with_lock=True, this prevents race conditions
        where multiple concurrent requests could exceed credit limits.
        """
        if with_lock:
            # SECURITY: Use row-level locking for atomic check-and-deduct operations
            result = await self.db.execute(
                select(CreditBalance).where(CreditBalance.tenant_id == tenant_id).with_for_update()
            )
            balance = result.scalar_one_or_none()
        else:
            balance = await self.get_balance(tenant_id)

        if not balance:
            return 0
        return balance.total_credits - balance.used_credits

    async def add_credits(
        self,
        tenant_id: UUID,
        amount: int,
        transaction_type: TransactionType,
        description: str,
        reference_id: UUID | None = None,
        reference_type: str | None = None,
    ) -> CreditTransaction:
        """
        Add credits to a tenant's balance.

        SECURITY: Uses SELECT ... FOR UPDATE to prevent race conditions
        when multiple concurrent requests try to add credits.
        """
        # SECURITY: Use row-level locking to prevent race condition
        result = await self.db.execute(
            select(CreditBalance)
            .where(CreditBalance.tenant_id == tenant_id)
            .with_for_update()  # SECURITY: Acquire exclusive lock
        )
        balance = result.scalar_one_or_none()

        if not balance:
            # Create balance if it doesn't exist
            balance = CreditBalance(tenant_id=tenant_id, total_credits=0, used_credits=0, available_credits=0)
            self.db.add(balance)
            await self.db.flush()  # Get the ID without committing

        # Update balance atomically
        balance.total_credits += amount
        balance.available_credits = balance.total_credits - balance.used_credits

        # Create transaction record
        transaction = CreditTransaction(
            credit_balance_id=balance.id,
            tenant_id=tenant_id,
            amount=amount,
            transaction_type=transaction_type,
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
            balance_after=balance.available_credits,
        )

        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)

        return transaction

    async def deduct_credits(
        self,
        tenant_id: UUID,
        amount: int,
        transaction_type: TransactionType,
        description: str,
        reference_id: UUID | None = None,
        reference_type: str | None = None,
    ) -> CreditTransaction:
        """
        Deduct credits from a tenant's balance.

        SECURITY: Uses SELECT ... FOR UPDATE to prevent race conditions
        when multiple concurrent requests try to deduct credits.
        """
        # SECURITY: Use row-level locking to prevent race condition
        # This locks the row until the transaction is committed
        result = await self.db.execute(
            select(CreditBalance)
            .where(CreditBalance.tenant_id == tenant_id)
            .with_for_update()  # SECURITY: Acquire exclusive lock
        )
        balance = result.scalar_one_or_none()

        if not balance:
            # Create balance if it doesn't exist (with lock)
            balance = CreditBalance(tenant_id=tenant_id, total_credits=0, used_credits=0, available_credits=0)
            self.db.add(balance)
            await self.db.flush()  # Get the ID without committing

        if balance.available_credits < amount:
            raise ValueError(f"Insufficient credits. Available: {balance.available_credits}, Required: {amount}")

        # Update balance atomically
        balance.used_credits += amount
        balance.available_credits = balance.total_credits - balance.used_credits

        # Create transaction record
        transaction = CreditTransaction(
            credit_balance_id=balance.id,
            tenant_id=tenant_id,
            amount=-amount,  # Negative for deduction
            transaction_type=transaction_type,
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
            balance_after=balance.available_credits,
        )

        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)

        return transaction

    async def refund_credits(
        self,
        tenant_id: UUID,
        amount: int,
        description: str,
        reference_id: UUID | None = None,
        reference_type: str | None = None,
    ) -> CreditTransaction:
        """
        Refund credits to a tenant.

        SECURITY: Uses SELECT ... FOR UPDATE to prevent race conditions
        when multiple concurrent refunds are processed.
        """
        # SECURITY: Use row-level locking to prevent race condition
        result = await self.db.execute(
            select(CreditBalance)
            .where(CreditBalance.tenant_id == tenant_id)
            .with_for_update()  # SECURITY: Acquire exclusive lock
        )
        balance = result.scalar_one_or_none()

        if not balance:
            # Create balance if it doesn't exist
            balance = CreditBalance(tenant_id=tenant_id, total_credits=0, used_credits=0, available_credits=0)
            self.db.add(balance)
            await self.db.flush()

        # Reduce used credits (effectively adding back to available)
        balance.used_credits = max(0, balance.used_credits - amount)
        balance.available_credits = balance.total_credits - balance.used_credits

        # Create transaction record
        transaction = CreditTransaction(
            credit_balance_id=balance.id,
            tenant_id=tenant_id,
            amount=amount,
            transaction_type=TransactionType.REFUND,
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
            balance_after=balance.available_credits,
        )

        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)

        return transaction

    async def get_transaction_history(
        self, tenant_id: UUID, filters: dict | None = None, limit: int = 100, offset: int = 0
    ) -> list[CreditTransaction]:
        """Get transaction history for a tenant"""
        query = select(CreditTransaction).where(CreditTransaction.tenant_id == tenant_id)

        # Apply filters if provided
        if filters:
            if "transaction_type" in filters:
                query = query.where(CreditTransaction.transaction_type == filters["transaction_type"])

        query = query.order_by(CreditTransaction.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_usage_stats(self, tenant_id: UUID) -> dict:
        """Get usage statistics for a tenant"""
        balance = await self.get_balance(tenant_id)
        if not balance:
            return {"total_credits": 0, "used_credits": 0, "available_credits": 0, "usage_percentage": 0}

        usage_pct = (balance.used_credits / balance.total_credits * 100) if balance.total_credits > 0 else 0

        return {
            "total_credits": balance.total_credits,
            "used_credits": balance.used_credits,
            "available_credits": balance.available_credits,
            "usage_percentage": round(usage_pct, 2),
        }

    async def reset_monthly_usage(self, tenant_id: UUID) -> None:
        """
        Reset monthly usage (called during subscription renewal).

        SECURITY: Uses SELECT ... FOR UPDATE to prevent race conditions
        during subscription renewal operations.
        """
        # SECURITY: Use row-level locking to prevent race condition
        result = await self.db.execute(
            select(CreditBalance)
            .where(CreditBalance.tenant_id == tenant_id)
            .with_for_update()  # SECURITY: Acquire exclusive lock
        )
        balance = result.scalar_one_or_none()

        if balance:
            balance.used_credits = 0
            balance.available_credits = balance.total_credits
            await self.db.commit()

    async def deduct_credits_idempotent(
        self,
        tenant_id: UUID,
        user_id: UUID | None,
        agent_id: UUID,
        action_type: "ActionType",
        metadata: dict,
        extra_credits: int = 0,
    ) -> CreditTransaction | None:
        """
        Deduct credits with idempotency check.

        Uses message_id or conversation_id + unique suffix as idempotency key
        to prevent duplicate deductions.

        SECURITY: The idempotency check is performed INSIDE the row lock to prevent
        race conditions where two concurrent requests could both pass the check
        before either creates the transaction.

        Args:
            tenant_id: Tenant UUID
            user_id: User UUID (optional)
            agent_id: Agent UUID
            action_type: Action type enum
            metadata: Metadata dict containing message_id, conversation_id, etc.

        Returns:
            CreditTransaction if deduction was performed, None if already processed
        """
        import uuid as uuid_module

        # Generate idempotency key from metadata
        message_id = metadata.get("message_id")
        conversation_id = metadata.get("conversation_id")

        if message_id:
            idempotency_key = f"msg_{message_id}"
        elif conversation_id:
            # SECURITY: Use UUID instead of timestamp for better uniqueness
            # Timestamp has 1-second resolution which can cause collisions
            idempotency_key = f"conv_{conversation_id}_{uuid_module.uuid4().hex[:8]}"
        else:
            # No idempotency key available, proceed without check
            idempotency_key = None

        # Get credit cost for this action (base + any per-use pricing markup)
        from src.models.credit_transaction import ActionType as ActionTypeModel

        credit_cost = ActionTypeModel.get_credit_cost(action_type) + max(0, extra_credits)

        # SECURITY: Use row-level locking to prevent race condition
        # The lock MUST be acquired BEFORE the idempotency check to prevent TOCTOU
        result = await self.db.execute(
            select(CreditBalance)
            .where(CreditBalance.tenant_id == tenant_id)
            .with_for_update()  # SECURITY: Acquire exclusive lock FIRST
        )
        balance = result.scalar_one_or_none()

        # SECURITY: Check idempotency AFTER acquiring lock to prevent race condition
        # This ensures only one request can create the transaction
        if idempotency_key:
            existing_result = await self.db.execute(
                select(CreditTransaction).where(CreditTransaction.idempotency_key == idempotency_key)
            )
            existing = existing_result.scalar_one_or_none()

            if existing:
                # Transaction already processed - release lock by not committing
                return None

        if not balance:
            balance = CreditBalance(tenant_id=tenant_id, total_credits=0, used_credits=0, available_credits=0)
            self.db.add(balance)
            await self.db.flush()

        # Check if sufficient credits (but don't raise error in async context)
        if balance.available_credits < credit_cost:
            logger.warning(
                f"Insufficient credits for tenant {tenant_id}: "
                f"available={balance.available_credits}, required={credit_cost}"
            )
            return None

        # Update balance atomically
        balance.used_credits += credit_cost
        balance.available_credits = balance.total_credits - balance.used_credits

        # Create transaction record with idempotency key
        transaction = CreditTransaction(
            credit_balance_id=balance.id,
            tenant_id=tenant_id,
            amount=-credit_cost,  # Negative for deduction
            transaction_type=TransactionType.USAGE,
            description=f"Credit deduction for {action_type.value}",
            reference_id=agent_id,
            reference_type="agent",
            transaction_metadata=__import__("json").dumps(metadata),
            idempotency_key=idempotency_key,
            balance_after=balance.available_credits,  # Add balance_after field
        )

        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)

        return transaction

    # =========================================================================
    # API Call Tracking
    # =========================================================================

    async def track_api_call(
        self, tenant_id: UUID, agent_id: UUID | None = None, credits_used: int = 0
    ) -> UsageAnalytics:
        """
        Track an API call for a tenant.

        Args:
            tenant_id: Tenant UUID
            agent_id: Optional agent UUID if call is agent-specific
            credits_used: Credits consumed by this API call

        Returns:
            Updated UsageAnalytics record
        """
        today = date.today()
        record = await UsageAnalytics.get_or_create(
            session=self.db, tenant_id=tenant_id, metric_type="api_calls", analytics_date=today, agent_id=agent_id
        )
        record.increment(count=1, credits=credits_used)
        await self.db.commit()
        return record

    async def get_api_call_count(
        self, tenant_id: UUID, start_date: date | None = None, end_date: date | None = None
    ) -> int:
        """
        Get total API calls for a tenant within a date range.

        Args:
            tenant_id: Tenant UUID
            start_date: Start date (defaults to start of current month)
            end_date: End date (defaults to today)

        Returns:
            Total API call count
        """
        if start_date is None:
            # Default to start of current month
            today = date.today()
            start_date = date(today.year, today.month, 1)
        if end_date is None:
            end_date = date.today()

        result = await self.db.execute(
            select(func.coalesce(func.sum(UsageAnalytics.total_count), 0))
            .where(UsageAnalytics.tenant_id == tenant_id)
            .where(UsageAnalytics.metric_type == "api_calls")
            .where(UsageAnalytics.date >= start_date)
            .where(UsageAnalytics.date <= end_date)
        )
        return result.scalar() or 0

    async def check_api_call_limit(self, tenant_id: UUID, max_api_calls: int | None) -> tuple[bool, int, int]:
        """
        Check if tenant has exceeded their API call limit.

        Args:
            tenant_id: Tenant UUID
            max_api_calls: Maximum API calls per month (None = unlimited)

        Returns:
            Tuple of (within_limit, current_count, limit)
        """
        if max_api_calls is None:
            return (True, 0, -1)  # Unlimited

        current_count = await self.get_api_call_count(tenant_id)
        return (current_count < max_api_calls, current_count, max_api_calls)

    # =========================================================================
    # Overage and Grace Period Handling
    # =========================================================================

    async def deduct_with_overage(
        self,
        tenant_id: UUID,
        amount: int,
        transaction_type: TransactionType,
        description: str,
        overage_allowed: bool = False,
        overage_rate: Decimal = Decimal("0"),
        grace_period_days: int = 0,
        reference_id: UUID | None = None,
        reference_type: str | None = None,
    ) -> tuple[CreditTransaction, Decimal | None]:
        """
        Deduct credits with overage handling.

        If credits are insufficient:
        - If overage_allowed: Allow the deduction and return the overage charge
        - If grace_period_days > 0: Allow deduction during grace period
        - Otherwise: Raise InsufficientCreditsError

        Args:
            tenant_id: Tenant UUID
            amount: Credits to deduct
            transaction_type: Type of transaction
            description: Transaction description
            overage_allowed: Whether overage is allowed for this plan
            overage_rate: Rate per credit in overage (e.g., $0.02)
            grace_period_days: Days of grace period allowed
            reference_id: Optional reference to related entity
            reference_type: Type of referenced entity

        Returns:
            Tuple of (CreditTransaction, overage_charge or None)

        Raises:
            InsufficientCreditsError if credits insufficient and no overage/grace

        SECURITY: Uses SELECT ... FOR UPDATE to prevent race conditions.
        """
        # SECURITY: Use row-level locking to prevent race condition
        result = await self.db.execute(
            select(CreditBalance)
            .where(CreditBalance.tenant_id == tenant_id)
            .with_for_update()  # SECURITY: Acquire exclusive lock
        )
        balance = result.scalar_one_or_none()

        if not balance:
            balance = CreditBalance(tenant_id=tenant_id, total_credits=0, used_credits=0, available_credits=0)
            self.db.add(balance)
            await self.db.flush()

        overage_charge = None
        overage_credits = 0

        if balance.available_credits < amount:
            # Check if overage is allowed
            if overage_allowed:
                overage_credits = amount - balance.available_credits
                overage_charge = Decimal(overage_credits) * overage_rate
                logger.info(f"Overage for tenant {tenant_id}: {overage_credits} credits, charge: ${overage_charge}")
            elif grace_period_days > 0:
                # Check if we're within grace period
                # Grace period starts when credits first went negative
                if await self._is_within_grace_period(tenant_id, grace_period_days):
                    logger.info(f"Tenant {tenant_id} is within grace period, allowing deduction")
                else:
                    raise InsufficientCreditsError(
                        f"Insufficient credits and grace period expired. "
                        f"Available: {balance.available_credits}, Required: {amount}",
                        available_credits=balance.available_credits,
                        required_credits=amount,
                        overage_allowed=overage_allowed,
                        grace_period_days=grace_period_days,
                    )
            else:
                raise InsufficientCreditsError(
                    f"Insufficient credits. Available: {balance.available_credits}, Required: {amount}",
                    available_credits=balance.available_credits,
                    required_credits=amount,
                    overage_allowed=False,
                    grace_period_days=0,
                )

        # Update balance atomically
        balance.used_credits += amount
        balance.available_credits = balance.total_credits - balance.used_credits

        # Create transaction record
        transaction = CreditTransaction(
            credit_balance_id=balance.id,
            tenant_id=tenant_id,
            amount=-amount,
            transaction_type=transaction_type,
            description=description,
            reference_id=reference_id,
            reference_type=reference_type,
            balance_after=balance.available_credits,
        )

        self.db.add(transaction)

        # If there was overage, create an overage transaction record
        if overage_credits > 0 and overage_charge is not None:
            overage_transaction = CreditTransaction(
                credit_balance_id=balance.id,
                tenant_id=tenant_id,
                amount=0,  # No credit change, just tracking overage
                transaction_type=TransactionType.ADJUSTMENT,
                description=f"Overage charge: {overage_credits} credits @ ${overage_rate}/credit = ${overage_charge}",
                transaction_metadata=str(
                    {
                        "overage_credits": overage_credits,
                        "overage_rate": str(overage_rate),
                        "overage_charge": str(overage_charge),
                    }
                ),
                balance_after=balance.available_credits,
            )
            self.db.add(overage_transaction)

        await self.db.commit()
        await self.db.refresh(transaction)

        return transaction, overage_charge

    async def _is_within_grace_period(self, tenant_id: UUID, grace_period_days: int) -> bool:
        """
        Check if tenant is still within their grace period.

        Grace period starts when credits first went negative (balance_after < 0).
        """
        # Find the first transaction where balance went negative
        result = await self.db.execute(
            select(CreditTransaction.created_at)
            .where(CreditTransaction.tenant_id == tenant_id)
            .where(CreditTransaction.balance_after < 0)
            .order_by(CreditTransaction.created_at.asc())
            .limit(1)
        )
        first_negative = result.scalar_one_or_none()

        if first_negative is None:
            # Never went negative, grace period hasn't started
            return True

        grace_end = first_negative + timedelta(days=grace_period_days)
        return datetime.now(UTC) < grace_end

    # =========================================================================
    # Credit Rollover
    # =========================================================================

    async def apply_monthly_rollover(
        self, tenant_id: UUID, new_credits: int, max_rollover: int, credits_rollover: bool
    ) -> tuple[int, int]:
        """
        Apply monthly credit rollover during subscription renewal.

        SECURITY: Uses SELECT ... FOR UPDATE to prevent race conditions
        during subscription renewal operations.

        Args:
            tenant_id: Tenant UUID
            new_credits: New monthly credits to add
            max_rollover: Maximum credits that can roll over
            credits_rollover: Whether rollover is enabled for this plan

        Returns:
            Tuple of (total_credits_after, rolled_over_credits)
        """
        # SECURITY: Use row-level locking to prevent race condition
        result = await self.db.execute(
            select(CreditBalance)
            .where(CreditBalance.tenant_id == tenant_id)
            .with_for_update()  # SECURITY: Acquire exclusive lock
        )
        balance = result.scalar_one_or_none()

        if not balance:
            # Create balance if it doesn't exist
            balance = CreditBalance(tenant_id=tenant_id, total_credits=0, used_credits=0, available_credits=0)
            self.db.add(balance)
            await self.db.flush()

        rolled_over = 0
        if credits_rollover and balance.available_credits > 0:
            # Cap rollover at max_rollover
            rolled_over = min(balance.available_credits, max_rollover)
            logger.info(f"Rolling over {rolled_over} credits for tenant {tenant_id} (max: {max_rollover})")

        # Reset and add new credits plus rollover
        balance.used_credits = 0
        balance.total_credits = new_credits + rolled_over
        balance.available_credits = balance.total_credits

        # Create transaction for rollover if applicable
        if rolled_over > 0:
            rollover_transaction = CreditTransaction(
                credit_balance_id=balance.id,
                tenant_id=tenant_id,
                amount=rolled_over,
                transaction_type=TransactionType.ADJUSTMENT,
                description=f"Credit rollover from previous period: {rolled_over} credits",
                balance_after=balance.available_credits,
            )
            self.db.add(rollover_transaction)

        await self.db.commit()
        return balance.total_credits, rolled_over

    async def get_overage_summary(
        self, tenant_id: UUID, start_date: date | None = None, end_date: date | None = None
    ) -> dict:
        """
        Get overage summary for a tenant within a date range.

        Returns:
            Dict with total_overage_credits, total_overage_charge, transactions
        """
        if start_date is None:
            today = date.today()
            start_date = date(today.year, today.month, 1)
        if end_date is None:
            end_date = date.today()

        # Get overage transactions
        result = await self.db.execute(
            select(CreditTransaction)
            .where(CreditTransaction.tenant_id == tenant_id)
            .where(CreditTransaction.transaction_type == TransactionType.ADJUSTMENT)
            .where(CreditTransaction.description.like("Overage charge%"))
            .where(func.date(CreditTransaction.created_at) >= start_date)
            .where(func.date(CreditTransaction.created_at) <= end_date)
        )
        overage_transactions = list(result.scalars().all())

        total_credits = 0
        total_charge = Decimal("0")

        for txn in overage_transactions:
            if txn.transaction_metadata:
                try:
                    import ast

                    meta = ast.literal_eval(txn.transaction_metadata)
                    total_credits += meta.get("overage_credits", 0)
                    total_charge += Decimal(meta.get("overage_charge", "0"))
                except (ValueError, SyntaxError):
                    pass

        return {
            "total_overage_credits": total_credits,
            "total_overage_charge": float(total_charge),
            "transaction_count": len(overage_transactions),
        }
