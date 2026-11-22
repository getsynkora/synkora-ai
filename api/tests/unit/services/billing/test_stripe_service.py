from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.credit_topup import CreditTopup, TopupStatus
from src.models.integration_config import IntegrationConfig
from src.models.tenant_subscription import TenantSubscription
from src.services.billing.stripe_service import StripeService


class TestStripeService:
    @pytest.fixture
    def mock_db(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.add = MagicMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def mock_integration_service(self):
        with patch("src.services.billing.stripe_service.IntegrationConfigService") as mock:
            yield mock

    @pytest.fixture
    def mock_stripe(self):
        with patch("src.services.billing.stripe_service.stripe") as mock:
            yield mock

    @pytest.fixture
    async def service(self, mock_db, mock_integration_service, mock_stripe):
        # Setup active config for initialization
        mock_config = MagicMock(spec=IntegrationConfig)
        mock_config.id = uuid4()
        mock_config.provider = "stripe"
        mock_config.is_active = True
        mock_config.config_data = b"encrypted"

        mock_service_instance = mock_integration_service.return_value
        # get_active_config is now async
        mock_service_instance.get_active_config = AsyncMock(return_value=mock_config)
        mock_service_instance._decrypt_config.return_value = {
            "credentials": {"secret_key": "sk_test", "webhook_secret": "whsec_test"},
            "settings": {"publishable_key": "pk_test"},
        }

        return await StripeService.create(mock_db)

    @pytest.mark.asyncio
    async def test_init_success(self, service, mock_stripe):
        assert mock_stripe.api_key == "sk_test"

    @pytest.mark.asyncio
    async def test_init_no_config(self, mock_db, mock_integration_service, mock_stripe):
        mock_integration_service.return_value.get_active_config = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="Stripe secret key not configured"):
            await StripeService.create(mock_db)

    @pytest.mark.asyncio
    async def test_get_stripe_keys(self, service):
        assert await service._get_stripe_secret_key() == "sk_test"
        assert await service._get_stripe_publishable_key() == "pk_test"
        assert await service._get_stripe_webhook_secret() == "whsec_test"

    async def test_create_customer(self, service, mock_stripe):
        tenant_id = uuid4()
        mock_stripe.Customer.create.return_value = MagicMock(id="cus_123")

        # Mock existing subscription query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        service.db.execute.return_value = mock_result

        cus_id = await service.create_customer(tenant_id, "test@example.com", "Test User")

        assert cus_id == "cus_123"
        mock_stripe.Customer.create.assert_called_with(
            email="test@example.com", name="Test User", metadata={"tenant_id": str(tenant_id)}
        )

    async def test_create_customer_updates_subscription(self, service, mock_stripe):
        tenant_id = uuid4()
        mock_stripe.Customer.create.return_value = MagicMock(id="cus_123")

        mock_sub = MagicMock(spec=TenantSubscription)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sub
        service.db.execute.return_value = mock_result

        await service.create_customer(tenant_id, "test@example.com")

        assert mock_sub.stripe_customer_id == "cus_123"
        service.db.commit.assert_called()

    async def test_get_or_create_customer_existing(self, service):
        tenant_id = uuid4()
        mock_sub = MagicMock(spec=TenantSubscription)
        mock_sub.stripe_customer_id = "cus_existing"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sub
        service.db.execute.return_value = mock_result

        cus_id = await service.get_or_create_customer(tenant_id, "email@test.com")
        assert cus_id == "cus_existing"

    async def test_get_or_create_customer_new(self, service, mock_stripe):
        tenant_id = uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        service.db.execute.return_value = mock_result
        mock_stripe.Customer.create.return_value = MagicMock(id="cus_new")

        cus_id = await service.get_or_create_customer(tenant_id, "email@test.com")
        assert cus_id == "cus_new"

    async def test_create_subscription(self, service, mock_stripe):
        mock_sub = MagicMock()
        mock_sub.id = "sub_123"
        mock_sub.status = "active"
        mock_sub.latest_invoice.payment_intent.client_secret = "pi_secret"
        mock_stripe.Subscription.create.return_value = mock_sub

        result = await service.create_subscription("cus_1", "price_1", trial_days=14)

        assert result["subscription_id"] == "sub_123"
        assert result["client_secret"] == "pi_secret"
        mock_stripe.Subscription.create.assert_called_with(
            customer="cus_1",
            items=[{"price": "price_1"}],
            metadata={},
            payment_behavior="default_incomplete",
            payment_settings={"save_default_payment_method": "on_subscription"},
            expand=["latest_invoice.payment_intent"],
            invoice_settings={"custom_fields": [{"name": "Platform", "value": "Synkora"}]},
            trial_period_days=14,
        )

    async def test_update_subscription(self, service, mock_stripe):
        mock_sub = MagicMock()
        mock_sub.__getitem__.return_value = [{"id": "si_1"}]  # items data
        mock_stripe.Subscription.retrieve.return_value = mock_sub

        mock_updated = MagicMock()
        mock_updated.id = "sub_123"
        mock_updated.status = "active"
        mock_updated.current_period_end = 1234567890
        mock_stripe.Subscription.modify.return_value = mock_updated

        result = await service.update_subscription("sub_123", "new_price")

        assert result["subscription_id"] == "sub_123"
        mock_stripe.Subscription.modify.assert_called()

    async def test_cancel_subscription(self, service, mock_stripe):
        await service.cancel_subscription("sub_1", immediate=True)
        mock_stripe.Subscription.delete.assert_called_with("sub_1")

        await service.cancel_subscription("sub_1", immediate=False)
        mock_stripe.Subscription.modify.assert_called_with("sub_1", cancel_at_period_end=True)

    async def test_create_payment_intent(self, service, mock_stripe):
        mock_pi = MagicMock()
        mock_pi.id = "pi_1"
        mock_pi.client_secret = "secret"
        mock_pi.status = "requires_payment_method"
        mock_stripe.PaymentIntent.create.return_value = mock_pi

        result = await service.create_payment_intent(1000, "cus_1")

        assert result["payment_intent_id"] == "pi_1"
        mock_stripe.PaymentIntent.create.assert_called()

    async def test_create_checkout_session(self, service, mock_stripe):
        mock_session = MagicMock()
        mock_session.id = "sess_1"
        mock_session.url = "url"
        mock_session.status = "open"
        mock_stripe.checkout.Session.create.return_value = mock_session

        result = await service.create_checkout_session("cus_1", [], "success", "cancel")

        assert result["session_id"] == "sess_1"
        mock_stripe.checkout.Session.create.assert_called()

    async def test_create_topup_checkout_session(self, service, mock_stripe):
        # Mock internal call
        service.create_checkout_session = AsyncMock(return_value={"session_id": "sess_1"})

        result = await service.create_topup_checkout_session(uuid4(), uuid4(), 100, 1000, "cus_1", "success", "cancel")

        assert result["session_id"] == "sess_1"
        service.create_checkout_session.assert_called()

    async def test_create_subscription_checkout_session(self, service, mock_stripe):
        # Mock internal call
        service.create_checkout_session = AsyncMock(return_value={"session_id": "sess_1"})

        result = await service.create_subscription_checkout_session("cus_1", "price_1", "success", "cancel")

        assert result["session_id"] == "sess_1"
        service.create_checkout_session.assert_called()

    async def test_create_topup_payment(self, service, mock_stripe):
        mock_pi = MagicMock()
        mock_pi.id = "pi_1"
        mock_stripe.PaymentIntent.create.return_value = mock_pi

        # Just mock create_payment_intent to simplify
        service.create_payment_intent = AsyncMock(return_value={"payment_intent_id": "pi_1"})

        tenant_id = uuid4()

        with patch("src.services.billing.stripe_service.CreditTopup") as MockTopup:
            mock_instance = MockTopup.return_value
            mock_instance.id = uuid4()

            result = await service.create_topup_payment(tenant_id, 100, 1000, "cus_1")

            assert result["payment_intent_id"] == "pi_1"
            assert "topup_id" in result

            # Verify DB adds
            service.db.add.assert_called()
            service.db.commit.assert_called()

    def test_construct_webhook_event(self, service, mock_stripe):
        mock_stripe.Webhook.construct_event.return_value = {"type": "test"}

        event = service.construct_webhook_event(b"payload", "sig", "secret")
        assert event["type"] == "test"

    async def test_handle_webhook_event_handlers(self, service):
        service._handle_checkout_session_completed = AsyncMock(return_value=True)

        event = {"type": "checkout.session.completed", "data": {"object": {}}}
        result = await service.handle_webhook_event(event)
        assert result is True
        service._handle_checkout_session_completed.assert_called()

    async def test_handle_subscription_created(self, service):
        mock_sub = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sub
        service.db.execute.return_value = mock_result

        sub_data = {"customer": "cus_1", "id": "sub_1"}
        result = await service._handle_subscription_created(sub_data)
        assert result is True
        service.db.commit.assert_called()

    async def test_handle_subscription_updated(self, service):
        mock_sub = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sub
        service.db.execute.return_value = mock_result

        sub_data = {"id": "sub_1", "status": "active", "cancel_at_period_end": False}
        result = await service._handle_subscription_updated(sub_data)
        assert result is True
        service.db.commit.assert_called()

    async def test_handle_invoice_payment_succeeded(self, service):
        mock_sub = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_sub
        service.db.execute.return_value = mock_result

        # Mock subscription service
        service.subscription_service.renew_subscription = AsyncMock()

        inv_data = {"subscription": "sub_1"}
        result = await service._handle_invoice_payment_succeeded(inv_data)
        assert result is True
        # Must be the subscription's own id, not the tenant id
        service.subscription_service.renew_subscription.assert_called_once_with(mock_sub.id)

    async def test_handle_checkout_session_completed_topup(self, service):
        mock_topup = MagicMock(spec=CreditTopup)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_topup
        service.db.execute.return_value = mock_result

        # Mock credit_service method correctly
        service.credit_service.add_credits = AsyncMock()

        session = {
            "metadata": {
                "type": "credit_topup",
                "topup_id": str(uuid4()),
                "credits_amount": "100",
                "tenant_id": str(uuid4()),
            }
        }

        result = await service._handle_checkout_session_completed(session)
        assert result is True
        assert mock_topup.status == TopupStatus.COMPLETED
        service.credit_service.add_credits.assert_called()

    async def test_handle_checkout_session_completed_subscription(self, service):
        # Case: New subscription
        mock_plan = MagicMock()
        mock_result_plan = MagicMock()
        mock_result_plan.scalar_one_or_none.return_value = mock_plan

        mock_result_no_sub = MagicMock()
        mock_result_no_sub.scalar_one_or_none.return_value = None

        service.db.execute.side_effect = [mock_result_plan, mock_result_no_sub]

        session = {
            "subscription": "sub_1",
            "customer": "cus_1",
            "metadata": {"type": "subscription", "tenant_id": str(uuid4()), "plan_id": str(uuid4())},
        }

        # Mock db.add to avoid actual execution if mocked
        service.db.add = MagicMock()
        service.subscription_service.renew_subscription = AsyncMock()

        result = await service._handle_checkout_session_completed(session)
        assert result is True
        service.db.add.assert_called()  # New sub added
        service.subscription_service.renew_subscription.assert_called()

    async def test_handle_payment_intent_succeeded(self, service):
        mock_topup = MagicMock(spec=CreditTopup)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_topup
        service.db.execute.return_value = mock_result

        # Mock credit_service method correctly
        service.credit_service.add_credits = AsyncMock()

        pi = {
            "metadata": {
                "type": "credit_topup",
                "topup_id": str(uuid4()),
                "credits_amount": "100",
                "tenant_id": str(uuid4()),
            }
        }

        result = await service._handle_payment_intent_succeeded(pi)
        assert result is True
        assert mock_topup.status == TopupStatus.COMPLETED
        service.credit_service.add_credits.assert_called()

    async def test_handle_payment_intent_failed(self, service):
        mock_topup = MagicMock(spec=CreditTopup)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_topup
        service.db.execute.return_value = mock_result

        pi = {"metadata": {"type": "credit_topup", "topup_id": str(uuid4())}}

        result = await service._handle_payment_intent_failed(pi)
        assert result is True
        assert mock_topup.status == TopupStatus.FAILED

    async def test_payout_methods(self, service, mock_stripe):
        mock_stripe.Payout.create.return_value = MagicMock(id="po_1")
        res = await service.create_payout("acct_1", 1000)
        assert res["payout_id"] == "po_1"

        mock_stripe.Account.create.return_value = MagicMock(id="acct_1")
        res = await service.create_connected_account("email@test.com")
        assert res == "acct_1"

        mock_stripe.AccountLink.create.return_value = MagicMock(url="http://link")
        res = await service.create_account_link("acct_1", "ref", "ret")
        assert res == "http://link"

    async def test_payment_methods(self, service, mock_stripe):
        mock_stripe.SetupIntent.create.return_value = MagicMock(id="si_1", client_secret="sec")
        res = await service.create_setup_intent("cus_1")
        assert res["setup_intent_id"] == "si_1"

        mock_stripe.PaymentMethod.list.return_value = MagicMock(data=[MagicMock(id="pm_1", type="card")])
        res = await service.list_payment_methods("cus_1")
        assert len(res) == 1
        assert res[0]["id"] == "pm_1"

        await service.detach_payment_method("pm_1")
        mock_stripe.PaymentMethod.detach.assert_called()

        await service.set_default_payment_method("cus_1", "pm_1")
        mock_stripe.Customer.modify.assert_called()
