"""
Chat Billing Service - Validates billing requirements for chat and conversation operations.

This service provides a clean interface for controllers to validate billing requirements
before processing chat messages or creating conversations.
"""

import logging
import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.billing.credit_service import CreditService
from src.services.billing.credit_utils import get_chat_action_type
from src.services.billing.plan_restriction_service import (
    ConversationLimitExceededError,
    MessageLimitExceededError,
    PlanRestrictionService,
    SubscriptionCancelledError,
    SubscriptionExpiredError,
    SubscriptionSuspendedError,
)
from src.services.billing.quota_service import QuotaService

logger = logging.getLogger(__name__)


class BillingErrorCode(StrEnum):
    """Billing error codes for API responses."""

    SUBSCRIPTION_EXPIRED = "SUBSCRIPTION_EXPIRED"
    SUBSCRIPTION_CANCELLED = "SUBSCRIPTION_CANCELLED"
    SUBSCRIPTION_SUSPENDED = "SUBSCRIPTION_SUSPENDED"
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    NO_LLM_CONFIG = "NO_LLM_CONFIG"
    CONVERSATION_LIMIT_EXCEEDED = "CONVERSATION_LIMIT_EXCEEDED"
    MESSAGE_LIMIT_EXCEEDED = "MESSAGE_LIMIT_EXCEEDED"


@dataclass
class BillingValidationError:
    """Represents a billing validation error."""

    error_code: BillingErrorCode
    message: str
    details: dict | None = None


@dataclass
class BillingValidationResult:
    """Result of billing validation."""

    is_valid: bool
    error: BillingValidationError | None = None


class ChatBillingService:
    """Service for validating billing requirements for chat operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.restriction_service = PlanRestrictionService(db)
        self.credit_service = CreditService(db)

    async def validate_subscription(self, tenant_id: uuid.UUID) -> BillingValidationResult:
        """
        Validate that tenant has a valid subscription.

        Args:
            tenant_id: Tenant UUID

        Returns:
            BillingValidationResult with is_valid=True if valid, or error details if not
        """
        try:
            await self.restriction_service.check_subscription_validity(tenant_id)
            return BillingValidationResult(is_valid=True)
        except SubscriptionExpiredError:
            return BillingValidationResult(
                is_valid=False,
                error=BillingValidationError(
                    error_code=BillingErrorCode.SUBSCRIPTION_EXPIRED,
                    message="Your subscription has expired. Please renew to continue.",
                ),
            )
        except SubscriptionCancelledError:
            return BillingValidationResult(
                is_valid=False,
                error=BillingValidationError(
                    error_code=BillingErrorCode.SUBSCRIPTION_CANCELLED,
                    message="Your subscription has been cancelled. Please resubscribe to continue.",
                ),
            )
        except SubscriptionSuspendedError:
            return BillingValidationResult(
                is_valid=False,
                error=BillingValidationError(
                    error_code=BillingErrorCode.SUBSCRIPTION_SUSPENDED,
                    message="Your subscription has been suspended. Please contact support or update your payment method.",
                ),
            )

    async def validate_credits(self, tenant_id: uuid.UUID, model_name: str) -> BillingValidationResult:
        """
        Validate that tenant has sufficient credits for the model.

        Args:
            tenant_id: Tenant UUID
            model_name: LLM model name

        Returns:
            BillingValidationResult with is_valid=True if sufficient credits, or error details if not
        """
        from src.models.credit_transaction import ActionType

        action_type = get_chat_action_type(model_name)
        available = await self.credit_service.get_available_credits(tenant_id)
        required = ActionType.get_credit_cost(action_type)

        if available >= required:
            return BillingValidationResult(is_valid=True)

        return BillingValidationResult(
            is_valid=False,
            error=BillingValidationError(
                error_code=BillingErrorCode.INSUFFICIENT_CREDITS,
                message=f"You need {required} credits for this chat but only have {available} available. Please add more credits to continue.",
                details={
                    "available_credits": available,
                    "required_credits": required,
                },
            ),
        )

    async def validate_quota(self, tenant_id: uuid.UUID, quota_pool: str | None) -> BillingValidationResult | None:
        """
        Check the agent's plan quota pool.

        Returns None when the plan does not meter this pool (caller falls back to credits),
        otherwise a result that is invalid once the pool is used up for this billing period.
        """
        status = await QuotaService(self.db).get_pool_status(tenant_id, quota_pool)
        if status is None:
            return None
        if not status.exhausted:
            return BillingValidationResult(is_valid=True)
        return BillingValidationResult(
            is_valid=False,
            error=BillingValidationError(
                error_code=BillingErrorCode.QUOTA_EXCEEDED,
                message=(
                    f"You've used all {status.limit} {status.label} included in your plan this month. "
                    f"Upgrade your plan or wait until {status.period_end:%b %d} when your allowance resets."
                ),
                details={
                    "pool": status.key,
                    "limit": status.limit,
                    "used": status.used,
                    "resets_at": status.period_end.isoformat(),
                },
            ),
        )

    async def validate_conversation_limit(self, tenant_id: uuid.UUID, account_id: uuid.UUID) -> BillingValidationResult:
        """
        Validate that user hasn't exceeded conversation limit.

        Args:
            tenant_id: Tenant UUID
            account_id: User account UUID

        Returns:
            BillingValidationResult with is_valid=True if within limit, or error details if not
        """
        try:
            await self.restriction_service.enforce_conversation_limit(tenant_id, account_id)
            return BillingValidationResult(is_valid=True)
        except ConversationLimitExceededError as e:
            limit = await self.restriction_service.get_conversation_limit(tenant_id)
            return BillingValidationResult(
                is_valid=False,
                error=BillingValidationError(
                    error_code=BillingErrorCode.CONVERSATION_LIMIT_EXCEEDED,
                    message=str(e),
                    details={"limit": limit},
                ),
            )

    async def validate_message_limit(self, tenant_id: uuid.UUID, conversation_id: uuid.UUID) -> BillingValidationResult:
        """
        Validate that conversation hasn't exceeded message limit.

        Args:
            tenant_id: Tenant UUID
            conversation_id: Conversation UUID

        Returns:
            BillingValidationResult with is_valid=True if within limit, or error details if not
        """
        try:
            await self.restriction_service.enforce_message_limit(tenant_id, conversation_id)
            return BillingValidationResult(is_valid=True)
        except MessageLimitExceededError as e:
            limit = await self.restriction_service.get_message_limit(tenant_id)
            return BillingValidationResult(
                is_valid=False,
                error=BillingValidationError(
                    error_code=BillingErrorCode.MESSAGE_LIMIT_EXCEEDED,
                    message=str(e),
                    details={"limit": limit},
                ),
            )

    async def validate_chat_request(
        self,
        tenant_id: uuid.UUID,
        model_name: str,
        conversation_id: uuid.UUID | None = None,
        quota_pool: str | None = None,
    ) -> BillingValidationResult:
        """
        Validate all billing requirements for a chat request.

        Performs validations in order:
        1. Subscription validity
        2. Credit availability
        3. Message limit (if conversation_id provided)

        Args:
            tenant_id: Tenant UUID
            model_name: LLM model name for credit calculation
            conversation_id: Optional conversation UUID for message limit check

        Returns:
            BillingValidationResult with first error encountered, or is_valid=True if all pass
        """
        # 1. Check subscription validity
        result = await self.validate_subscription(tenant_id)
        if not result.is_valid:
            return result

        # 2. Check the plan's quota pool for this agent; plans without pools use shared credits
        result = await self.validate_quota(tenant_id, quota_pool)
        if result is None:
            result = await self.validate_credits(tenant_id, model_name)
        if not result.is_valid:
            return result

        # 3. Check message limit if conversation_id provided
        if conversation_id:
            result = await self.validate_message_limit(tenant_id, conversation_id)
            if not result.is_valid:
                return result

        return BillingValidationResult(is_valid=True)

    async def validate_conversation_creation(
        self, tenant_id: uuid.UUID, account_id: uuid.UUID
    ) -> BillingValidationResult:
        """
        Validate all billing requirements for creating a conversation.

        Performs validations in order:
        1. Subscription validity
        2. Conversation limit

        Args:
            tenant_id: Tenant UUID
            account_id: User account UUID

        Returns:
            BillingValidationResult with first error encountered, or is_valid=True if all pass
        """
        # 1. Check subscription validity
        result = await self.validate_subscription(tenant_id)
        if not result.is_valid:
            return result

        # 2. Check conversation limit
        result = await self.validate_conversation_limit(tenant_id, account_id)
        if not result.is_valid:
            return result

        return BillingValidationResult(is_valid=True)
