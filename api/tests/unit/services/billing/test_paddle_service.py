"""
Unit tests for Paddle Payment Service.

Tests customer management, subscription handling, webhooks, and one-time charges.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tenant_subscription import SubscriptionStatus


class TestPaddleServiceInit:
    """Test PaddleService initialization."""

    @pytest.mark.asyncio
    @patch("src.services.billing.paddle_service.IntegrationConfigService")
    @patch("src.services.billing.paddle_service.SubscriptionService")
    @patch("src.services.billing.paddle_service.CreditService")
    async def test_init_with_config(self, mock_credit, mock_sub, mock_integration):
        """Test initialization with valid config."""
        from src.services.billing.paddle_service import PaddleService

        mock_db = AsyncMock(spec=AsyncSession)
        mock_config = MagicMock()
        mock_config.id = uuid.uuid4()
        mock_config.provider = "paddle"
        mock_config.is_active = True
        mock_config.config_data = {}

        mock_integration_instance = MagicMock()
        mock_integration_instance.get_active_config = AsyncMock(return_value=mock_config)
        mock_integration_instance._decrypt_config.return_value = {
            "credentials": {
                "api_key": "test_api_key",
                "client_side_token": "test_client_token",
                "webhook_secret": "test_webhook_secret",
            },
            "settings": {"environment": "sandbox"},
        }
        mock_integration.return_value = mock_integration_instance

        service = await PaddleService.create(mock_db)

        assert service.api_key == "test_api_key"
        assert service.client_side_token == "test_client_token"
        assert service.webhook_secret == "test_webhook_secret"
        assert service.environment == "sandbox"
        assert service.base_url == "https://sandbox-api.paddle.com"

    @patch("src.services.billing.paddle_service.IntegrationConfigService")
    @patch("src.services.billing.paddle_service.SubscriptionService")
    @patch("src.services.billing.paddle_service.CreditService")
    def test_init_without_config(self, mock_credit, mock_sub, mock_integration):
        """Test initialization without config."""
        from src.services.billing.paddle_service import PaddleService

        mock_db = AsyncMock(spec=AsyncSession)
        mock_integration_instance = MagicMock()
        mock_integration_instance.get_active_config.return_value = None
        mock_integration.return_value = mock_integration_instance

        service = PaddleService(mock_db)

        assert service.api_key is None
        assert service.environment == "sandbox"

    @pytest.mark.asyncio
    @patch("src.services.billing.paddle_service.IntegrationConfigService")
    @patch("src.services.billing.paddle_service.SubscriptionService")
    @patch("src.services.billing.paddle_service.CreditService")
    async def test_init_production_environment(self, mock_credit, mock_sub, mock_integration):
        """Test initialization with production environment."""
        from src.services.billing.paddle_service import PaddleService

        mock_db = AsyncMock(spec=AsyncSession)
        mock_config = MagicMock()
        mock_config.config_data = {}

        mock_integration_instance = MagicMock()
        mock_integration_instance.get_active_config = AsyncMock(return_value=mock_config)
        mock_integration_instance._decrypt_config.return_value = {
            "credentials": {"api_key": "live_key"},
            "settings": {"environment": "production"},
        }
        mock_integration.return_value = mock_integration_instance

        service = await PaddleService.create(mock_db)

        assert service.environment == "production"
        assert service.base_url == "https://api.paddle.com"


class TestEnsurePaddleConfigured:
    """Test _ensure_paddle_configured method."""

    @patch("src.services.billing.paddle_service.IntegrationConfigService")
    @patch("src.services.billing.paddle_service.SubscriptionService")
    @patch("src.services.billing.paddle_service.CreditService")
    def test_raises_when_not_configured(self, mock_credit, mock_sub, mock_integration):
        """Test that error is raised when Paddle is not configured."""
        from src.services.billing.paddle_service import PaddleService

        mock_db = AsyncMock(spec=AsyncSession)
        mock_integration_instance = MagicMock()
        mock_integration_instance.get_active_config.return_value = None
        mock_integration.return_value = mock_integration_instance

        service = PaddleService(mock_db)

        with pytest.raises(ValueError) as exc_info:
            service._ensure_paddle_configured()

        assert "not enabled" in str(exc_info.value) or "not properly configured" in str(exc_info.value)


class TestMakeRequest:
    """Test _make_request method."""

    @pytest.mark.asyncio
    @patch("src.services.billing.paddle_service.IntegrationConfigService")
    @patch("src.services.billing.paddle_service.SubscriptionService")
    @patch("src.services.billing.paddle_service.CreditService")
    async def test_make_request_success(self, mock_credit, mock_sub, mock_integration):
        """Test successful API request."""
        from src.services.billing.paddle_service import PaddleService

        mock_db = AsyncMock(spec=AsyncSession)
        mock_integration_instance = MagicMock()
        mock_integration.return_value = mock_integration_instance

        service = PaddleService(mock_db)
        service.api_key = "test_key"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b'{"data": {"id": "cus_123"}}'
            mock_response.json.return_value = {"data": {"id": "cus_123"}}

            mock_client_instance = AsyncMock()
            mock_client_instance.request = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await service._make_request("GET", "/customers/cus_123")

            assert result["data"]["id"] == "cus_123"

    @pytest.mark.asyncio
    @patch("src.services.billing.paddle_service.IntegrationConfigService")
    @patch("src.services.billing.paddle_service.SubscriptionService")
    @patch("src.services.billing.paddle_service.CreditService")
    async def test_make_request_error(self, mock_credit, mock_sub, mock_integration):
        """Test API request error handling."""
        from src.services.billing.paddle_service import PaddleService

        mock_db = AsyncMock(spec=AsyncSession)
        mock_integration_instance = MagicMock()
        mock_integration.return_value = mock_integration_instance

        service = PaddleService(mock_db)
        service.api_key = "test_key"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.content = b'{"error": {"detail": "Not found"}}'
            mock_response.json.return_value = {"error": {"detail": "Not found"}}
            mock_response.text = "Not found"

            mock_client_instance = AsyncMock()
            mock_client_instance.request = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            with pytest.raises(Exception) as exc_info:
                await service._make_request("GET", "/customers/invalid")

            assert "Paddle API error" in str(exc_info.value)


class TestCustomerManagement:
    """Test customer management methods."""

    @pytest.fixture
    def paddle_service(self):
        """Create a mocked Paddle service."""
        with patch("src.services.billing.paddle_service.IntegrationConfigService") as mock_integration:
            with patch("src.services.billing.paddle_service.SubscriptionService"):
                with patch("src.services.billing.paddle_service.CreditService"):
                    mock_db = AsyncMock(spec=AsyncSession)
                    mock_config = MagicMock()
                    mock_integration_instance = MagicMock()
                    mock_integration_instance.get_active_config.return_value = mock_config
                    mock_integration_instance._decrypt_config.return_value = {
                        "credentials": {"api_key": "test_key"},
                        "settings": {"environment": "sandbox"},
                    }
                    mock_integration.return_value = mock_integration_instance

                    from src.services.billing.paddle_service import PaddleService

                    return PaddleService(mock_db)

    async def test_create_customer(self, paddle_service):
        """Test customer creation."""
        tenant_id = uuid.uuid4()

        with patch.object(paddle_service, "_make_request") as mock_request:
            mock_request.return_value = {"data": {"id": "ctm_123"}}

            # Mock db.execute for async pattern
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = MagicMock()
            paddle_service.db.execute = AsyncMock(return_value=mock_result)
            paddle_service.db.commit = AsyncMock()

            customer_id = await paddle_service.create_customer(
                tenant_id=tenant_id,
                email="test@example.com",
                name="Test User",
            )

            assert customer_id == "ctm_123"
            mock_request.assert_called_once()

    async def test_get_or_create_customer_existing(self, paddle_service):
        """Test get_or_create_customer with existing customer."""
        tenant_id = uuid.uuid4()

        mock_subscription = MagicMock()
        mock_subscription.paddle_customer_id = "ctm_existing"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        paddle_service.db.execute = AsyncMock(return_value=mock_result)

        customer_id = await paddle_service.get_or_create_customer(
            tenant_id=tenant_id,
            email="test@example.com",
        )

        assert customer_id == "ctm_existing"


class TestSubscriptionManagement:
    """Test subscription management methods."""

    @pytest.fixture
    def paddle_service(self):
        """Create a mocked Paddle service."""
        with patch("src.services.billing.paddle_service.IntegrationConfigService") as mock_integration:
            with patch("src.services.billing.paddle_service.SubscriptionService"):
                with patch("src.services.billing.paddle_service.CreditService"):
                    mock_db = AsyncMock(spec=AsyncSession)
                    mock_config = MagicMock()
                    mock_integration_instance = MagicMock()
                    mock_integration_instance.get_active_config.return_value = mock_config
                    mock_integration_instance._decrypt_config.return_value = {
                        "credentials": {"api_key": "test_key"},
                        "settings": {"environment": "sandbox"},
                    }
                    mock_integration.return_value = mock_integration_instance

                    from src.services.billing.paddle_service import PaddleService

                    return PaddleService(mock_db)

    @pytest.mark.asyncio
    async def test_get_subscription(self, paddle_service):
        """Test getting a subscription."""
        with patch.object(paddle_service, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {
                "data": {
                    "id": "sub_123",
                    "status": "active",
                    "customer_id": "ctm_123",
                }
            }

            result = await paddle_service.get_subscription("sub_123")

            assert result["id"] == "sub_123"
            assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_cancel_subscription(self, paddle_service):
        """Test subscription cancellation."""
        with patch.object(paddle_service, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            result = await paddle_service.cancel_subscription("sub_123")

            assert result is True
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_subscription(self, paddle_service):
        """Test subscription pausing."""
        with patch.object(paddle_service, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            result = await paddle_service.pause_subscription("sub_123")

            assert result is True

    @pytest.mark.asyncio
    async def test_resume_subscription(self, paddle_service):
        """Test subscription resuming."""
        with patch.object(paddle_service, "_make_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            result = await paddle_service.resume_subscription("sub_123")

            assert result is True


class TestWebhookVerification:
    """Test webhook signature verification."""

    @pytest.fixture
    def paddle_service(self):
        """Create a mocked Paddle service."""
        with patch("src.services.billing.paddle_service.IntegrationConfigService") as mock_integration:
            with patch("src.services.billing.paddle_service.SubscriptionService"):
                with patch("src.services.billing.paddle_service.CreditService"):
                    mock_db = AsyncMock(spec=AsyncSession)
                    mock_config = MagicMock()
                    mock_integration_instance = MagicMock()
                    mock_integration_instance.get_active_config.return_value = mock_config
                    mock_integration_instance._decrypt_config.return_value = {
                        "credentials": {
                            "api_key": "test_key",
                            "webhook_secret": "test_webhook_secret",
                        },
                        "settings": {"environment": "sandbox"},
                    }
                    mock_integration.return_value = mock_integration_instance

                    from src.services.billing.paddle_service import PaddleService

                    return PaddleService(mock_db)

    def test_verify_webhook_without_secret(self, paddle_service):
        """Test webhook verification rejects when no secret configured (security: fail closed)."""
        paddle_service.webhook_secret = None

        result = paddle_service.verify_webhook_signature(b'{"data": "test"}', "ts=123;h1=abc")

        assert result is False

    def test_verify_webhook_invalid_signature(self, paddle_service):
        """Test webhook verification fails with invalid signature."""
        paddle_service.webhook_secret = "test_webhook_secret"
        result = paddle_service.verify_webhook_signature(
            b'{"data": "test"}',
            "ts=123456;h1=invalid_signature",
        )

        assert result is False

    def test_verify_webhook_malformed_signature(self, paddle_service):
        """Test webhook verification with malformed signature."""
        paddle_service.webhook_secret = "test_webhook_secret"
        result = paddle_service.verify_webhook_signature(
            b'{"data": "test"}',
            "malformed_signature",
        )

        assert result is False


class TestWebhookHandlers:
    """Test webhook event handlers."""

    @pytest.fixture
    def paddle_service(self):
        """Create a mocked Paddle service."""
        with patch("src.services.billing.paddle_service.IntegrationConfigService") as mock_integration:
            with patch("src.services.billing.paddle_service.SubscriptionService"):
                with patch("src.services.billing.paddle_service.CreditService"):
                    mock_db = AsyncMock(spec=AsyncSession)
                    mock_config = MagicMock()
                    mock_integration_instance = MagicMock()
                    mock_integration_instance.get_active_config.return_value = mock_config
                    mock_integration_instance._decrypt_config.return_value = {
                        "credentials": {"api_key": "test_key"},
                        "settings": {"environment": "sandbox"},
                    }
                    mock_integration.return_value = mock_integration_instance

                    from src.services.billing.paddle_service import PaddleService

                    return PaddleService(mock_db)

    async def test_handle_subscription_created(self, paddle_service):
        """Test handling subscription.created event."""
        tenant_id = uuid.uuid4()
        mock_subscription = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        paddle_service.db.execute = AsyncMock(return_value=mock_result)
        paddle_service.db.commit = AsyncMock()

        data = {
            "id": "sub_123",
            "customer_id": "ctm_123",
            "custom_data": {"tenant_id": str(tenant_id)},
        }

        result = await paddle_service._handle_subscription_created(data)

        assert result is True
        assert mock_subscription.paddle_subscription_id == "sub_123"
        assert mock_subscription.status == SubscriptionStatus.ACTIVE

    async def test_handle_subscription_created_no_tenant(self, paddle_service):
        """Test handling subscription.created when tenant not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        paddle_service.db.execute = AsyncMock(return_value=mock_result)

        data = {
            "id": "sub_123",
            "customer_id": "ctm_unknown",
            "custom_data": {},
        }

        result = await paddle_service._handle_subscription_created(data)

        assert result is False

    async def test_handle_subscription_canceled(self, paddle_service):
        """Test handling subscription.canceled event."""
        mock_subscription = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        paddle_service.db.execute = AsyncMock(return_value=mock_result)
        paddle_service.db.commit = AsyncMock()

        data = {"id": "sub_123"}

        result = await paddle_service._handle_subscription_canceled(data)

        assert result is True
        assert mock_subscription.status == SubscriptionStatus.CANCELLED

    async def test_handle_subscription_paused(self, paddle_service):
        """Test handling subscription.paused event."""
        mock_subscription = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        paddle_service.db.execute = AsyncMock(return_value=mock_result)
        paddle_service.db.commit = AsyncMock()

        data = {"id": "sub_123"}

        result = await paddle_service._handle_subscription_paused(data)

        assert result is True
        assert mock_subscription.status == SubscriptionStatus.SUSPENDED

    async def test_handle_subscription_resumed(self, paddle_service):
        """Test handling subscription.resumed event."""
        mock_subscription = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_subscription
        paddle_service.db.execute = AsyncMock(return_value=mock_result)
        paddle_service.db.commit = AsyncMock()

        data = {"id": "sub_123"}

        result = await paddle_service._handle_subscription_resumed(data)

        assert result is True
        assert mock_subscription.status == SubscriptionStatus.ACTIVE

    async def test_handle_webhook_event_routing(self, paddle_service):
        """Test webhook event routing."""
        with patch.object(paddle_service, "_handle_subscription_created", new_callable=AsyncMock) as mock_handler:
            mock_handler.return_value = True

            result = await paddle_service.handle_webhook_event("subscription.created", {"id": "sub_123"})

            assert result is True
            mock_handler.assert_called_once_with({"id": "sub_123"})

    async def test_handle_unhandled_event(self, paddle_service):
        """Test handling unhandled webhook event."""
        result = await paddle_service.handle_webhook_event("unknown.event", {"data": "test"})

        assert result is True  # Unhandled events return True


class TestUtilityMethods:
    """Test utility methods."""

    @pytest.fixture
    def paddle_service(self):
        """Create a mocked Paddle service."""
        with patch("src.services.billing.paddle_service.IntegrationConfigService") as mock_integration:
            with patch("src.services.billing.paddle_service.SubscriptionService"):
                with patch("src.services.billing.paddle_service.CreditService"):
                    mock_db = AsyncMock(spec=AsyncSession)
                    mock_config = MagicMock()
                    mock_integration_instance = MagicMock()
                    mock_integration_instance.get_active_config.return_value = mock_config
                    mock_integration_instance._decrypt_config.return_value = {
                        "credentials": {
                            "api_key": "test_key",
                            "client_side_token": "test_client_token",
                        },
                        "settings": {"environment": "sandbox"},
                    }
                    mock_integration.return_value = mock_integration_instance

                    from src.services.billing.paddle_service import PaddleService

                    return PaddleService(mock_db)

    def test_get_client_token(self, paddle_service):
        """Test getting client-side token."""
        paddle_service.client_side_token = "test_client_token"
        token = paddle_service.get_client_token()

        assert token == "test_client_token"

    def test_get_environment(self, paddle_service):
        """Test getting environment."""
        env = paddle_service.get_environment()

        assert env == "sandbox"


class TestPaddleTransactionRenewals:
    @pytest.fixture
    def paddle_service(self):
        with patch("src.services.billing.paddle_service.IntegrationConfigService") as mock_integration:
            with patch("src.services.billing.paddle_service.SubscriptionService"):
                with patch("src.services.billing.paddle_service.CreditService"):
                    mock_integration.return_value._decrypt_config.return_value = {
                        "credentials": {"api_key": "k"},
                        "settings": {"environment": "sandbox"},
                    }
                    from src.services.billing.paddle_service import PaddleService

                    service = PaddleService(AsyncMock(spec=AsyncSession))
                    service.subscription_service.renew_subscription = AsyncMock()
                    return service

    def _data(self, origin):
        return {
            "id": "txn_1",
            "origin": origin,
            "subscription_id": "sub_1",
            "customer_id": "ctm_1",
            "custom_data": {"type": "subscription", "tenant_id": str(uuid.uuid4()), "plan_id": str(uuid.uuid4())},
        }

    def _existing(self, paddle_service):
        existing = MagicMock(cancel_at_period_end=True, current_period_start="old-start")
        plan_result, sub_result = MagicMock(), MagicMock()
        plan_result.scalar_one_or_none.return_value = MagicMock()
        sub_result.scalar_one_or_none.return_value = existing
        paddle_service.db.execute = AsyncMock(side_effect=[plan_result, sub_result])
        paddle_service.db.commit = AsyncMock()
        paddle_service.db.refresh = AsyncMock()
        return existing

    @pytest.mark.parametrize(
        "origin", ["subscription_update", "subscription_charge", "subscription_payment_method_change"]
    )
    async def test_a_proration_or_one_off_charge_does_not_start_a_new_period(self, paddle_service, origin):
        """Reproduces a plan change resetting allowances and granting another month of credits."""
        existing = self._existing(paddle_service)
        assert await paddle_service._handle_transaction_completed(self._data(origin))
        paddle_service.subscription_service.renew_subscription.assert_not_called()
        assert existing.current_period_start == "old-start"

    @pytest.mark.parametrize("origin", ["web", "api", "subscription_recurring", None])
    async def test_checkout_and_recurring_renewals_start_a_new_period(self, paddle_service, origin):
        existing = self._existing(paddle_service)
        assert await paddle_service._handle_transaction_completed(self._data(origin))
        paddle_service.subscription_service.renew_subscription.assert_awaited_once()
        assert existing.cancel_at_period_end is False  # a paid subscription clears a pending cancellation
