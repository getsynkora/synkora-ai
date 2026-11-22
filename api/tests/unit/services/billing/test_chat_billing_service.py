"""
Unit tests for Chat Billing Service.

Tests billing validation for chat and conversation operations.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.billing.chat_billing_service import (
    BillingErrorCode,
    BillingValidationError,
    BillingValidationResult,
    ChatBillingService,
)


class TestBillingErrorCode:
    """Test BillingErrorCode enum."""

    def test_error_codes_exist(self):
        """Test that all expected error codes exist."""
        assert BillingErrorCode.SUBSCRIPTION_EXPIRED == "SUBSCRIPTION_EXPIRED"
        assert BillingErrorCode.SUBSCRIPTION_CANCELLED == "SUBSCRIPTION_CANCELLED"
        assert BillingErrorCode.SUBSCRIPTION_SUSPENDED == "SUBSCRIPTION_SUSPENDED"
        assert BillingErrorCode.INSUFFICIENT_CREDITS == "INSUFFICIENT_CREDITS"
        assert BillingErrorCode.NO_LLM_CONFIG == "NO_LLM_CONFIG"
        assert BillingErrorCode.CONVERSATION_LIMIT_EXCEEDED == "CONVERSATION_LIMIT_EXCEEDED"
        assert BillingErrorCode.MESSAGE_LIMIT_EXCEEDED == "MESSAGE_LIMIT_EXCEEDED"


class TestBillingValidationError:
    """Test BillingValidationError dataclass."""

    def test_create_error(self):
        """Test creating a validation error."""
        error = BillingValidationError(
            error_code=BillingErrorCode.INSUFFICIENT_CREDITS,
            message="Not enough credits",
            details={"available": 5, "required": 10},
        )

        assert error.error_code == BillingErrorCode.INSUFFICIENT_CREDITS
        assert error.message == "Not enough credits"
        assert error.details["available"] == 5
        assert error.details["required"] == 10

    def test_create_error_without_details(self):
        """Test creating error without details."""
        error = BillingValidationError(
            error_code=BillingErrorCode.SUBSCRIPTION_EXPIRED,
            message="Subscription expired",
        )

        assert error.details is None


class TestBillingValidationResult:
    """Test BillingValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = BillingValidationResult(is_valid=True)

        assert result.is_valid is True
        assert result.error is None

    def test_invalid_result_with_error(self):
        """Test creating an invalid result with error."""
        error = BillingValidationError(
            error_code=BillingErrorCode.INSUFFICIENT_CREDITS,
            message="Not enough credits",
        )
        result = BillingValidationResult(is_valid=False, error=error)

        assert result.is_valid is False
        assert result.error == error


class TestChatBillingServiceInit:
    """Test ChatBillingService initialization."""

    @patch("src.services.billing.chat_billing_service.PlanRestrictionService")
    @patch("src.services.billing.chat_billing_service.CreditService")
    def test_init(self, mock_credit_service, mock_restriction_service):
        """Test service initialization."""
        mock_db = AsyncMock(spec=AsyncSession)

        service = ChatBillingService(mock_db)

        assert service.db == mock_db
        mock_restriction_service.assert_called_once_with(mock_db)
        mock_credit_service.assert_called_once_with(mock_db)


class TestValidateSubscription:
    """Test subscription validation."""

    @pytest.fixture
    def billing_service(self):
        """Create a billing service with mocked dependencies."""
        with patch("src.services.billing.chat_billing_service.PlanRestrictionService") as mock_restriction:
            with patch("src.services.billing.chat_billing_service.CreditService"):
                mock_db = AsyncMock(spec=AsyncSession)
                service = ChatBillingService(mock_db)
                service.restriction_service = mock_restriction.return_value
                return service

    async def test_valid_subscription(self, billing_service):
        """Test validation with valid subscription."""
        tenant_id = uuid.uuid4()
        billing_service.restriction_service.check_subscription_validity = AsyncMock(return_value=None)

        result = await billing_service.validate_subscription(tenant_id)

        assert result.is_valid is True
        assert result.error is None

    async def test_expired_subscription(self, billing_service):
        """Test validation with expired subscription."""
        from src.services.billing.plan_restriction_service import SubscriptionExpiredError

        tenant_id = uuid.uuid4()
        billing_service.restriction_service.check_subscription_validity = AsyncMock(
            side_effect=SubscriptionExpiredError()
        )

        result = await billing_service.validate_subscription(tenant_id)

        assert result.is_valid is False
        assert result.error.error_code == BillingErrorCode.SUBSCRIPTION_EXPIRED

    async def test_cancelled_subscription(self, billing_service):
        """Test validation with cancelled subscription."""
        from src.services.billing.plan_restriction_service import SubscriptionCancelledError

        tenant_id = uuid.uuid4()
        billing_service.restriction_service.check_subscription_validity = AsyncMock(
            side_effect=SubscriptionCancelledError()
        )

        result = await billing_service.validate_subscription(tenant_id)

        assert result.is_valid is False
        assert result.error.error_code == BillingErrorCode.SUBSCRIPTION_CANCELLED

    async def test_suspended_subscription(self, billing_service):
        """Test validation with suspended subscription."""
        from src.services.billing.plan_restriction_service import SubscriptionSuspendedError

        tenant_id = uuid.uuid4()
        billing_service.restriction_service.check_subscription_validity = AsyncMock(
            side_effect=SubscriptionSuspendedError()
        )

        result = await billing_service.validate_subscription(tenant_id)

        assert result.is_valid is False
        assert result.error.error_code == BillingErrorCode.SUBSCRIPTION_SUSPENDED


class TestValidateCredits:
    """Test credit validation."""

    @pytest.fixture
    def billing_service(self):
        """Create a billing service with mocked dependencies."""
        with patch("src.services.billing.chat_billing_service.PlanRestrictionService"):
            with patch("src.services.billing.chat_billing_service.CreditService") as mock_credit:
                mock_db = AsyncMock(spec=AsyncSession)
                service = ChatBillingService(mock_db)
                service.credit_service = mock_credit.return_value
                return service

    @patch("src.services.billing.chat_billing_service.get_chat_action_type")
    async def test_sufficient_credits(self, mock_get_action_type, billing_service):
        """Test validation with sufficient credits."""
        tenant_id = uuid.uuid4()
        mock_get_action_type.return_value = "chat_gpt4"
        billing_service.credit_service.get_available_credits = AsyncMock(return_value=100)

        with patch("src.models.credit_transaction.ActionType.get_credit_cost", return_value=10):
            result = await billing_service.validate_credits(tenant_id, "gpt-4")

        assert result.is_valid is True

    @patch("src.services.billing.chat_billing_service.get_chat_action_type")
    async def test_insufficient_credits(self, mock_get_action_type, billing_service):
        """Test validation with insufficient credits."""
        tenant_id = uuid.uuid4()
        mock_get_action_type.return_value = "chat_gpt4"
        billing_service.credit_service.get_available_credits = AsyncMock(return_value=5)

        with patch("src.models.credit_transaction.ActionType.get_credit_cost", return_value=10):
            result = await billing_service.validate_credits(tenant_id, "gpt-4")

        assert result.is_valid is False
        assert result.error.error_code == BillingErrorCode.INSUFFICIENT_CREDITS
        assert result.error.details["available_credits"] == 5
        assert result.error.details["required_credits"] == 10


class TestValidateConversationLimit:
    """Test conversation limit validation."""

    @pytest.fixture
    def billing_service(self):
        """Create a billing service with mocked dependencies."""
        with patch("src.services.billing.chat_billing_service.PlanRestrictionService") as mock_restriction:
            with patch("src.services.billing.chat_billing_service.CreditService"):
                mock_db = AsyncMock(spec=AsyncSession)
                service = ChatBillingService(mock_db)
                service.restriction_service = mock_restriction.return_value
                return service

    async def test_within_limit(self, billing_service):
        """Test validation when within conversation limit."""
        tenant_id = uuid.uuid4()
        account_id = uuid.uuid4()
        billing_service.restriction_service.enforce_conversation_limit = AsyncMock(return_value=None)

        result = await billing_service.validate_conversation_limit(tenant_id, account_id)

        assert result.is_valid is True

    async def test_limit_exceeded(self, billing_service):
        """Test validation when conversation limit exceeded."""
        from src.services.billing.plan_restriction_service import ConversationLimitExceededError

        tenant_id = uuid.uuid4()
        account_id = uuid.uuid4()
        billing_service.restriction_service.enforce_conversation_limit = AsyncMock(
            side_effect=ConversationLimitExceededError("Limit exceeded")
        )
        billing_service.restriction_service.get_conversation_limit = AsyncMock(return_value=10)

        result = await billing_service.validate_conversation_limit(tenant_id, account_id)

        assert result.is_valid is False
        assert result.error.error_code == BillingErrorCode.CONVERSATION_LIMIT_EXCEEDED
        assert result.error.details["limit"] == 10


class TestValidateMessageLimit:
    """Test message limit validation."""

    @pytest.fixture
    def billing_service(self):
        """Create a billing service with mocked dependencies."""
        with patch("src.services.billing.chat_billing_service.PlanRestrictionService") as mock_restriction:
            with patch("src.services.billing.chat_billing_service.CreditService"):
                mock_db = AsyncMock(spec=AsyncSession)
                service = ChatBillingService(mock_db)
                service.restriction_service = mock_restriction.return_value
                return service

    async def test_within_limit(self, billing_service):
        """Test validation when within message limit."""
        tenant_id = uuid.uuid4()
        conversation_id = uuid.uuid4()
        billing_service.restriction_service.enforce_message_limit = AsyncMock(return_value=None)

        result = await billing_service.validate_message_limit(tenant_id, conversation_id)

        assert result.is_valid is True

    async def test_limit_exceeded(self, billing_service):
        """Test validation when message limit exceeded."""
        from src.services.billing.plan_restriction_service import MessageLimitExceededError

        tenant_id = uuid.uuid4()
        conversation_id = uuid.uuid4()
        billing_service.restriction_service.enforce_message_limit = AsyncMock(
            side_effect=MessageLimitExceededError("Message limit exceeded")
        )
        billing_service.restriction_service.get_message_limit = AsyncMock(return_value=100)

        result = await billing_service.validate_message_limit(tenant_id, conversation_id)

        assert result.is_valid is False
        assert result.error.error_code == BillingErrorCode.MESSAGE_LIMIT_EXCEEDED
        assert result.error.details["limit"] == 100


class TestValidateChatRequest:
    """Test full chat request validation."""

    @pytest.fixture
    def billing_service(self):
        """Create a billing service with mocked dependencies."""
        with patch("src.services.billing.chat_billing_service.PlanRestrictionService"):
            with patch("src.services.billing.chat_billing_service.CreditService"):
                mock_db = AsyncMock(spec=AsyncSession)
                service = ChatBillingService(mock_db)
                # Legacy case: the plan has no quota pools, so shared credits apply
                service.validate_quota = AsyncMock(return_value=None)
                return service

    async def test_quota_pool_replaces_credit_check(self, billing_service):
        """A metered pool with room left is enough; credits are not consulted."""
        billing_service.validate_quota = AsyncMock(return_value=BillingValidationResult(is_valid=True))
        credits = AsyncMock(return_value=BillingValidationResult(is_valid=True))
        with (
            patch.object(
                billing_service,
                "validate_subscription",
                AsyncMock(return_value=BillingValidationResult(is_valid=True)),
            ),
            patch.object(billing_service, "validate_credits", credits),
        ):
            result = await billing_service.validate_chat_request(uuid.uuid4(), "gpt-4", quota_pool="support")

        assert result.is_valid is True
        credits.assert_not_called()

    async def test_exhausted_quota_pool_blocks_chat(self, billing_service):
        """An exhausted pool stops the chat even if the tenant has credits."""
        error = BillingValidationError(error_code=BillingErrorCode.QUOTA_EXCEEDED, message="Used up")
        billing_service.validate_quota = AsyncMock(return_value=BillingValidationResult(is_valid=False, error=error))
        credits = AsyncMock(return_value=BillingValidationResult(is_valid=True))
        with (
            patch.object(
                billing_service,
                "validate_subscription",
                AsyncMock(return_value=BillingValidationResult(is_valid=True)),
            ),
            patch.object(billing_service, "validate_credits", credits),
        ):
            result = await billing_service.validate_chat_request(uuid.uuid4(), "gpt-4", quota_pool="support")

        assert result.is_valid is False
        assert result.error.error_code == BillingErrorCode.QUOTA_EXCEEDED
        credits.assert_not_called()

    async def test_all_validations_pass(self, billing_service):
        """Test when all validations pass."""
        tenant_id = uuid.uuid4()

        with (
            patch.object(
                billing_service,
                "validate_subscription",
                AsyncMock(return_value=BillingValidationResult(is_valid=True)),
            ),
            patch.object(
                billing_service,
                "validate_credits",
                AsyncMock(return_value=BillingValidationResult(is_valid=True)),
            ),
        ):
            result = await billing_service.validate_chat_request(tenant_id, "gpt-4")

        assert result.is_valid is True

    async def test_subscription_fails(self, billing_service):
        """Test when subscription validation fails."""
        tenant_id = uuid.uuid4()
        error = BillingValidationError(
            error_code=BillingErrorCode.SUBSCRIPTION_EXPIRED,
            message="Expired",
        )

        with patch.object(
            billing_service,
            "validate_subscription",
            AsyncMock(return_value=BillingValidationResult(is_valid=False, error=error)),
        ):
            result = await billing_service.validate_chat_request(tenant_id, "gpt-4")

        assert result.is_valid is False
        assert result.error.error_code == BillingErrorCode.SUBSCRIPTION_EXPIRED

    async def test_credits_fail(self, billing_service):
        """Test when credit validation fails."""
        tenant_id = uuid.uuid4()
        error = BillingValidationError(
            error_code=BillingErrorCode.INSUFFICIENT_CREDITS,
            message="Not enough",
        )

        with (
            patch.object(
                billing_service,
                "validate_subscription",
                AsyncMock(return_value=BillingValidationResult(is_valid=True)),
            ),
            patch.object(
                billing_service,
                "validate_credits",
                AsyncMock(return_value=BillingValidationResult(is_valid=False, error=error)),
            ),
        ):
            result = await billing_service.validate_chat_request(tenant_id, "gpt-4")

        assert result.is_valid is False
        assert result.error.error_code == BillingErrorCode.INSUFFICIENT_CREDITS

    async def test_message_limit_checked_when_conversation_provided(self, billing_service):
        """Test that message limit is checked when conversation_id provided."""
        tenant_id = uuid.uuid4()
        conversation_id = uuid.uuid4()

        with (
            patch.object(
                billing_service,
                "validate_subscription",
                AsyncMock(return_value=BillingValidationResult(is_valid=True)),
            ),
            patch.object(
                billing_service,
                "validate_credits",
                AsyncMock(return_value=BillingValidationResult(is_valid=True)),
            ),
            patch.object(
                billing_service,
                "validate_message_limit",
                AsyncMock(return_value=BillingValidationResult(is_valid=True)),
            ) as mock_validate,
        ):
            await billing_service.validate_chat_request(tenant_id, "gpt-4", conversation_id=conversation_id)

        mock_validate.assert_called_once_with(tenant_id, conversation_id)


class TestValidateConversationCreation:
    """Test conversation creation validation."""

    @pytest.fixture
    def billing_service(self):
        """Create a billing service with mocked dependencies."""
        with patch("src.services.billing.chat_billing_service.PlanRestrictionService"):
            with patch("src.services.billing.chat_billing_service.CreditService"):
                mock_db = AsyncMock(spec=AsyncSession)
                return ChatBillingService(mock_db)

    async def test_all_validations_pass(self, billing_service):
        """Test when all validations pass."""
        tenant_id = uuid.uuid4()
        account_id = uuid.uuid4()

        with (
            patch.object(
                billing_service,
                "validate_subscription",
                AsyncMock(return_value=BillingValidationResult(is_valid=True)),
            ),
            patch.object(
                billing_service,
                "validate_conversation_limit",
                AsyncMock(return_value=BillingValidationResult(is_valid=True)),
            ),
        ):
            result = await billing_service.validate_conversation_creation(tenant_id, account_id)

        assert result.is_valid is True

    async def test_subscription_fails(self, billing_service):
        """Test when subscription validation fails."""
        tenant_id = uuid.uuid4()
        account_id = uuid.uuid4()
        error = BillingValidationError(
            error_code=BillingErrorCode.SUBSCRIPTION_CANCELLED,
            message="Cancelled",
        )

        with patch.object(
            billing_service,
            "validate_subscription",
            AsyncMock(return_value=BillingValidationResult(is_valid=False, error=error)),
        ):
            result = await billing_service.validate_conversation_creation(tenant_id, account_id)

        assert result.is_valid is False
        assert result.error.error_code == BillingErrorCode.SUBSCRIPTION_CANCELLED

    async def test_conversation_limit_fails(self, billing_service):
        """Test when conversation limit validation fails."""
        tenant_id = uuid.uuid4()
        account_id = uuid.uuid4()
        error = BillingValidationError(
            error_code=BillingErrorCode.CONVERSATION_LIMIT_EXCEEDED,
            message="Limit exceeded",
        )

        with (
            patch.object(
                billing_service,
                "validate_subscription",
                AsyncMock(return_value=BillingValidationResult(is_valid=True)),
            ),
            patch.object(
                billing_service,
                "validate_conversation_limit",
                AsyncMock(return_value=BillingValidationResult(is_valid=False, error=error)),
            ),
        ):
            result = await billing_service.validate_conversation_creation(tenant_id, account_id)

        assert result.is_valid is False
        assert result.error.error_code == BillingErrorCode.CONVERSATION_LIMIT_EXCEEDED
