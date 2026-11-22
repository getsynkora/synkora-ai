"""
Paddle Payment Integration Service

Handles all Paddle payment operations including:
- Customer management
- Subscription creation and management
- Transaction handling (one-time payments)
- Webhook processing

Paddle acts as a Merchant of Record (MoR), handling VAT/tax compliance worldwide.
"""

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.credit_topup import CreditTopup, TopupStatus
from src.models.credit_transaction import TransactionType
from src.models.subscription_plan import SubscriptionPlan
from src.models.tenant_subscription import SubscriptionStatus, TenantSubscription
from src.services.billing.credit_service import CreditService
from src.services.billing.subscription_service import SubscriptionService
from src.services.integrations.integration_config_service import IntegrationConfigService

logger = logging.getLogger(__name__)


class PaddleService:
    """Service for handling Paddle payment operations"""

    def __init__(self, db: AsyncSession, _skip_init: bool = False):
        self.db = db
        self.credit_service = CreditService(db)
        self.subscription_service = SubscriptionService(db)
        self.integration_config_service = IntegrationConfigService(db)

        # Set defaults — overwritten by _initialize_paddle()
        self.api_key = None
        self.client_side_token = None
        self.webhook_secret = None
        self.environment = "sandbox"
        self.base_url = "https://sandbox-api.paddle.com"

    @classmethod
    async def create(cls, db: AsyncSession) -> "PaddleService":
        """Factory method to create an initialized PaddleService instance."""
        service = cls(db, _skip_init=True)
        await service._initialize_paddle()
        return service

    async def _initialize_paddle(self):
        """Initialize Paddle with API key from integration config"""
        logger.info("Initializing Paddle service...")
        config = await self._get_paddle_config()
        if config:
            self.api_key = config.get("api_key")
            self.client_side_token = config.get("client_side_token")
            self.webhook_secret = config.get("webhook_secret")
            self.environment = config.get("environment", "sandbox")
            self.base_url = (
                "https://sandbox-api.paddle.com" if self.environment == "sandbox" else "https://api.paddle.com"
            )
            logger.info(f"Paddle initialized in {self.environment} mode")
        else:
            logger.warning("Paddle integration not configured")

    async def _get_paddle_config(self) -> dict | None:
        """Get Paddle configuration from integration config"""
        logger.info("Fetching Paddle config from integration configs...")
        config = await self.integration_config_service.get_active_config(None, "payment", "paddle")

        if config:
            logger.info(
                f"Found Paddle integration config: id={config.id}, provider={config.provider}, is_active={config.is_active}"
            )
            config_data = self.integration_config_service._decrypt_config(config.config_data)

            credentials = config_data.get("credentials", {})
            settings = config_data.get("settings", {})

            return {
                "api_key": credentials.get("api_key"),
                "client_side_token": credentials.get("client_side_token"),
                "webhook_secret": credentials.get("webhook_secret"),
                "environment": settings.get("environment", "sandbox"),
            }
        else:
            logger.warning("No active Paddle integration config found")
            return None

    def _get_paddle_client_side_token(self) -> str | None:
        """Get Paddle client-side token (cached after initialization)"""
        return self.client_side_token

    def _get_paddle_webhook_secret(self) -> str | None:
        """Get Paddle webhook secret (cached after initialization)"""
        return self.webhook_secret

    def _ensure_paddle_configured(self):
        """Ensure Paddle is properly configured before operations"""
        if not self.api_key:
            raise ValueError("Paddle integration is not enabled or not properly configured")

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Make an authenticated request to Paddle API"""
        self._ensure_paddle_configured()

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=30.0,
            )

            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("detail", response.text)
                raise Exception(f"Paddle API error ({response.status_code}): {error_msg}")

            return response.json() if response.content else {}

    # =========================================================================
    # Customer Management
    # =========================================================================

    async def create_customer(
        self, tenant_id: UUID, email: str, name: str | None = None, metadata: dict | None = None
    ) -> str:
        """
        Create a Paddle customer for a tenant

        Args:
            tenant_id: Tenant UUID
            email: Customer email
            name: Customer name (optional)
            metadata: Additional metadata (optional)

        Returns:
            Paddle customer ID
        """
        try:
            custom_data = metadata or {}
            custom_data["tenant_id"] = str(tenant_id)

            request_data = {
                "email": email,
                "custom_data": custom_data,
            }

            if name:
                request_data["name"] = name

            response = await self._make_request("POST", "/customers", data=request_data)
            customer_id = response.get("data", {}).get("id")

            # Store customer ID in tenant's subscription record
            result = await self.db.execute(select(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_id))
            subscription = result.scalar_one_or_none()

            if subscription:
                subscription.paddle_customer_id = customer_id
                await self.db.commit()

            logger.info(f"Created Paddle customer {customer_id} for tenant {tenant_id}")
            return customer_id

        except Exception as e:
            logger.error(f"Failed to create Paddle customer: {e}")
            raise Exception(f"Failed to create Paddle customer: {str(e)}")

    async def get_or_create_customer(self, tenant_id: UUID, email: str, name: str | None = None) -> str:
        """
        Get existing Paddle customer or create new one

        Args:
            tenant_id: Tenant UUID
            email: Customer email
            name: Customer name (optional)

        Returns:
            Paddle customer ID
        """
        # Check if customer already exists in subscription record
        result = await self.db.execute(select(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_id))
        subscription = result.scalar_one_or_none()

        if subscription and subscription.paddle_customer_id:
            return subscription.paddle_customer_id

        # Try to find existing customer by email
        try:
            response = await self._make_request("GET", "/customers", params={"email": email})
            customers = response.get("data", [])
            if customers:
                customer_id = customers[0].get("id")
                # Update subscription record if exists
                if subscription:
                    subscription.paddle_customer_id = customer_id
                    await self.db.commit()
                return customer_id
        except Exception:
            pass  # Customer not found, create new one

        # Create new customer
        return await self.create_customer(tenant_id, email, name)

    # =========================================================================
    # Subscription Management
    # =========================================================================

    async def get_subscription(self, subscription_id: str) -> dict:
        """
        Get a Paddle subscription by ID

        Args:
            subscription_id: Paddle subscription ID

        Returns:
            Subscription data
        """
        response = await self._make_request("GET", f"/subscriptions/{subscription_id}")
        return response.get("data", {})

    async def create_subscription_transaction(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        metadata: dict | None = None,
    ) -> dict:
        """
        Create a transaction for subscription checkout

        Paddle uses transactions for both one-time and subscription purchases.

        Args:
            customer_id: Paddle customer ID
            price_id: Paddle price ID
            success_url: URL to redirect after success
            metadata: Additional metadata

        Returns:
            Transaction data with checkout URL
        """
        try:
            custom_data = metadata or {}

            request_data = {
                "customer_id": customer_id,
                "items": [{"price_id": price_id, "quantity": 1}],
                "checkout": {
                    "url": success_url,
                },
                "custom_data": custom_data,
            }

            response = await self._make_request("POST", "/transactions", data=request_data)
            transaction = response.get("data", {})
            transaction_id = transaction.get("id")

            # Construct the Paddle checkout URL from the transaction ID
            checkout_base = (
                "https://sandbox-buy.paddle.com" if self.environment == "sandbox" else "https://buy.paddle.com"
            )
            checkout_url = f"{checkout_base}?_ptxn={transaction_id}"

            return {
                "transaction_id": transaction_id,
                "checkout_url": checkout_url,
                "status": transaction.get("status"),
            }

        except Exception as e:
            logger.error(f"Failed to create subscription transaction: {e}")
            raise Exception(f"Failed to create subscription transaction: {str(e)}")

    async def update_subscription(
        self, subscription_id: str, price_id: str | None = None, proration_billing_mode: str = "prorated_immediately"
    ) -> dict:
        """
        Update an existing subscription

        Args:
            subscription_id: Paddle subscription ID
            price_id: New price ID (optional)
            proration_billing_mode: How to handle prorations

        Returns:
            Updated subscription data
        """
        try:
            request_data = {"proration_billing_mode": proration_billing_mode}

            if price_id:
                # Get current subscription to find item ID
                subscription = await self.get_subscription(subscription_id)
                items = subscription.get("items", [])
                if items:
                    item_id = items[0].get("id")
                    request_data["items"] = [{"id": item_id, "price_id": price_id}]

            response = await self._make_request("PATCH", f"/subscriptions/{subscription_id}", data=request_data)
            subscription = response.get("data", {})

            return {
                "subscription_id": subscription.get("id"),
                "status": subscription.get("status"),
                "current_billing_period": subscription.get("current_billing_period"),
            }

        except Exception as e:
            logger.warning(f"Failed to update subscription: {e}")
            raise Exception(f"Failed to update subscription: {str(e)}")

    async def cancel_subscription(self, subscription_id: str, effective_from: str = "next_billing_period") -> bool:
        """
        Cancel a Paddle subscription

        Args:
            subscription_id: Paddle subscription ID
            effective_from: When to cancel ("immediately" or "next_billing_period")

        Returns:
            Success status
        """
        try:
            request_data = {"effective_from": effective_from}
            await self._make_request("POST", f"/subscriptions/{subscription_id}/cancel", data=request_data)
            logger.info(f"Cancelled Paddle subscription {subscription_id} effective {effective_from}")
            return True

        except Exception as e:
            logger.warning(f"Failed to cancel subscription: {e}")
            raise Exception(f"Failed to cancel subscription: {str(e)}")

    async def pause_subscription(self, subscription_id: str, effective_from: str = "next_billing_period") -> bool:
        """
        Pause a Paddle subscription

        Args:
            subscription_id: Paddle subscription ID
            effective_from: When to pause

        Returns:
            Success status
        """
        try:
            request_data = {
                "scheduled_change": {
                    "action": "pause",
                    "effective_at": effective_from,
                }
            }
            await self._make_request("PATCH", f"/subscriptions/{subscription_id}", data=request_data)
            logger.info(f"Paused Paddle subscription {subscription_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to pause subscription: {e}")
            raise Exception(f"Failed to pause subscription: {str(e)}")

    async def resume_subscription(self, subscription_id: str, effective_from: str = "immediately") -> bool:
        """
        Resume a paused Paddle subscription

        Args:
            subscription_id: Paddle subscription ID
            effective_from: When to resume

        Returns:
            Success status
        """
        try:
            request_data = {
                "scheduled_change": None,  # Clear any scheduled pause
            }
            await self._make_request("PATCH", f"/subscriptions/{subscription_id}", data=request_data)
            logger.info(f"Resumed Paddle subscription {subscription_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to resume subscription: {e}")
            raise Exception(f"Failed to resume subscription: {str(e)}")

    # =========================================================================
    # One-Time Payments (Credit Top-ups)
    # =========================================================================

    async def create_one_time_charge(
        self,
        tenant_id: UUID,
        topup_id: UUID,
        credits_amount: int,
        price_cents: int,
        customer_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        """
        Create a one-time transaction for credit top-up

        Args:
            tenant_id: Tenant UUID
            topup_id: Credit topup ID
            credits_amount: Number of credits
            price_cents: Price in cents
            customer_id: Paddle customer ID
            success_url: Success redirect URL
            cancel_url: Cancel redirect URL (not directly supported by Paddle, included in custom_data)

        Returns:
            Transaction data with checkout URL
        """
        try:
            custom_data = {
                "tenant_id": str(tenant_id),
                "topup_id": str(topup_id),
                "credits_amount": credits_amount,
                "type": "credit_topup",
                "cancel_url": cancel_url,
            }

            # Note: Paddle prices are created in the dashboard, not dynamically
            # For dynamic pricing, we need to use price_override
            request_data = {
                "customer_id": customer_id,
                "items": [
                    {
                        "price": {
                            "description": f"{credits_amount} Credits",
                            "name": f"Credit Top-up: {credits_amount} Credits",
                            "billing_cycle": None,  # One-time purchase
                            "unit_price": {
                                "amount": str(price_cents),
                                "currency_code": "USD",
                            },
                            "product_id": await self._get_or_create_credits_product_id(),
                        },
                        "quantity": 1,
                    }
                ],
                "checkout": {
                    "url": success_url,
                },
                "custom_data": custom_data,
            }

            response = await self._make_request("POST", "/transactions", data=request_data)
            transaction = response.get("data", {})
            transaction_id = transaction.get("id")

            # Construct the Paddle checkout URL from the transaction ID
            checkout_base = (
                "https://sandbox-buy.paddle.com" if self.environment == "sandbox" else "https://buy.paddle.com"
            )
            checkout_url = f"{checkout_base}?_ptxn={transaction_id}"

            return {
                "transaction_id": transaction_id,
                "checkout_url": checkout_url,
                "status": transaction.get("status"),
            }

        except Exception as e:
            logger.error(f"Failed to create one-time charge: {e}")
            raise Exception(f"Failed to create one-time charge: {str(e)}")

    async def _get_or_create_credits_product_id(self) -> str:
        """Get or create a product ID for credits. This should be configured in Paddle dashboard."""
        # In a real implementation, this would be stored in config or environment
        # For now, return a placeholder that should be configured
        config = await self._get_paddle_config()
        if config:
            settings = await self.integration_config_service.get_active_config(None, "payment", "paddle")
            if settings:
                config_data = self.integration_config_service._decrypt_config(settings.config_data)
                return config_data.get("settings", {}).get("credits_product_id", "")
        return ""

    async def create_topup_checkout(
        self,
        tenant_id: UUID,
        topup_id: UUID,
        credits_amount: int,
        price_cents: int,
        customer_id: str,
        success_url: str,
        cancel_url: str,
    ) -> dict:
        """
        Create a checkout session for credit top-up (alias for create_one_time_charge)
        """
        return await self.create_one_time_charge(
            tenant_id=tenant_id,
            topup_id=topup_id,
            credits_amount=credits_amount,
            price_cents=price_cents,
            customer_id=customer_id,
            success_url=success_url,
            cancel_url=cancel_url,
        )

    async def create_subscription_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: dict | None = None,
    ) -> dict:
        """
        Create a checkout session for subscription

        Args:
            customer_id: Paddle customer ID
            price_id: Paddle price ID for the subscription
            success_url: Success redirect URL
            cancel_url: Cancel redirect URL

        Returns:
            Checkout session data
        """
        try:
            custom_data = metadata or {}
            custom_data["cancel_url"] = cancel_url

            request_data = {
                "customer_id": customer_id,
                "items": [{"price_id": price_id, "quantity": 1}],
                "checkout": {
                    "url": success_url,
                },
                "custom_data": custom_data,
            }

            response = await self._make_request("POST", "/transactions", data=request_data)
            transaction = response.get("data", {})
            transaction_id = transaction.get("id")

            # Construct the Paddle checkout URL from the transaction ID
            # For Paddle Billing, use the _ptxn query parameter format
            checkout_base = (
                "https://sandbox-buy.paddle.com" if self.environment == "sandbox" else "https://buy.paddle.com"
            )
            checkout_url = f"{checkout_base}?_ptxn={transaction_id}"

            return {
                "session_id": transaction_id,
                "checkout_url": checkout_url,
                "status": transaction.get("status"),
            }

        except Exception as e:
            logger.error(f"Failed to create subscription checkout session: {e}")
            raise Exception(f"Failed to create subscription checkout session: {str(e)}")

    # =========================================================================
    # Webhook Handling
    # =========================================================================

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Paddle webhook signature

        Args:
            payload: Request payload bytes
            signature: Paddle-Signature header value

        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            logger.error(
                "SECURITY: Paddle webhook secret not configured — rejecting webhook. Set PADDLE_WEBHOOK_SECRET."
            )
            return False

        try:
            # Paddle signature format: ts=timestamp;h1=hash
            parts = dict(part.split("=") for part in signature.split(";"))
            timestamp = parts.get("ts", "")
            received_hash = parts.get("h1", "")

            # Compute expected signature
            signed_payload = f"{timestamp}:{payload.decode('utf-8')}"
            expected_hash = hmac.new(
                self.webhook_secret.encode("utf-8"),
                signed_payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            return hmac.compare_digest(expected_hash, received_hash)

        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False

    async def handle_webhook_event(self, event_type: str, data: dict) -> bool:
        """
        Handle Paddle webhook events

        Args:
            event_type: Event type string
            data: Event data

        Returns:
            Success status
        """
        handlers = {
            "subscription.created": self._handle_subscription_created,
            "subscription.updated": self._handle_subscription_updated,
            "subscription.canceled": self._handle_subscription_canceled,
            "subscription.paused": self._handle_subscription_paused,
            "subscription.resumed": self._handle_subscription_resumed,
            "transaction.completed": self._handle_transaction_completed,
            "transaction.payment_failed": self._handle_transaction_payment_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            return await handler(data)

        logger.info(f"Unhandled Paddle webhook event: {event_type}")
        return True  # Unhandled events are considered successful

    async def _handle_subscription_created(self, data: dict) -> bool:
        """Handle subscription.created event"""
        subscription_id = data.get("id")
        customer_id = data.get("customer_id")
        custom_data = data.get("custom_data", {})
        tenant_id_str = custom_data.get("tenant_id")

        if not tenant_id_str:
            # Try to find tenant by customer ID
            result = await self.db.execute(
                select(TenantSubscription).filter(TenantSubscription.paddle_customer_id == customer_id)
            )
            tenant_subscription = result.scalar_one_or_none()
        else:
            result = await self.db.execute(
                select(TenantSubscription).filter(TenantSubscription.tenant_id == UUID(tenant_id_str))
            )
            tenant_subscription = result.scalar_one_or_none()

        if not tenant_subscription:
            logger.warning(f"No tenant subscription found for Paddle subscription {subscription_id}")
            return False

        # Update subscription record
        tenant_subscription.paddle_subscription_id = subscription_id
        tenant_subscription.paddle_customer_id = customer_id
        tenant_subscription.payment_provider = "paddle"
        tenant_subscription.status = SubscriptionStatus.ACTIVE
        await self.db.commit()

        logger.info(f"Handled subscription.created for {subscription_id}")
        return True

    async def _handle_subscription_updated(self, data: dict) -> bool:
        """Handle subscription.updated event"""
        subscription_id = data.get("id")
        status = data.get("status")

        result = await self.db.execute(
            select(TenantSubscription).filter(TenantSubscription.paddle_subscription_id == subscription_id)
        )
        tenant_subscription = result.scalar_one_or_none()

        if tenant_subscription:
            # Map Paddle status to our status
            status_map = {
                "active": SubscriptionStatus.ACTIVE,
                "canceled": SubscriptionStatus.CANCELLED,
                "past_due": SubscriptionStatus.ACTIVE,  # Keep active but flag
                "paused": SubscriptionStatus.SUSPENDED,
                "trialing": SubscriptionStatus.TRIAL,
            }

            tenant_subscription.status = status_map.get(status, SubscriptionStatus.ACTIVE)

            # Update billing period
            billing_period = data.get("current_billing_period", {})
            if billing_period:
                if billing_period.get("starts_at"):
                    tenant_subscription.current_period_start = datetime.fromisoformat(
                        billing_period["starts_at"].replace("Z", "+00:00")
                    )
                if billing_period.get("ends_at"):
                    tenant_subscription.current_period_end = datetime.fromisoformat(
                        billing_period["ends_at"].replace("Z", "+00:00")
                    )

            await self.db.commit()

        logger.info(f"Handled subscription.updated for {subscription_id}")
        return True

    async def _handle_subscription_canceled(self, data: dict) -> bool:
        """Handle subscription.canceled event"""
        subscription_id = data.get("id")

        result = await self.db.execute(
            select(TenantSubscription).filter(TenantSubscription.paddle_subscription_id == subscription_id)
        )
        tenant_subscription = result.scalar_one_or_none()

        if tenant_subscription:
            tenant_subscription.status = SubscriptionStatus.CANCELLED
            tenant_subscription.cancelled_at = datetime.now(UTC)
            await self.db.commit()

        logger.info(f"Handled subscription.canceled for {subscription_id}")
        return True

    async def _handle_subscription_paused(self, data: dict) -> bool:
        """Handle subscription.paused event"""
        subscription_id = data.get("id")

        result = await self.db.execute(
            select(TenantSubscription).filter(TenantSubscription.paddle_subscription_id == subscription_id)
        )
        tenant_subscription = result.scalar_one_or_none()

        if tenant_subscription:
            tenant_subscription.status = SubscriptionStatus.SUSPENDED
            await self.db.commit()

        logger.info(f"Handled subscription.paused for {subscription_id}")
        return True

    async def _handle_subscription_resumed(self, data: dict) -> bool:
        """Handle subscription.resumed event"""
        subscription_id = data.get("id")

        result = await self.db.execute(
            select(TenantSubscription).filter(TenantSubscription.paddle_subscription_id == subscription_id)
        )
        tenant_subscription = result.scalar_one_or_none()

        if tenant_subscription:
            tenant_subscription.status = SubscriptionStatus.ACTIVE
            await self.db.commit()

        logger.info(f"Handled subscription.resumed for {subscription_id}")
        return True

    async def _handle_transaction_completed(self, data: dict) -> bool:
        """Handle transaction.completed event for one-time payments"""
        transaction_id = data.get("id")
        custom_data = data.get("custom_data", {})
        event_type = custom_data.get("type")

        if event_type == "credit_topup":
            topup_id = custom_data.get("topup_id")
            credits_amount = int(custom_data.get("credits_amount", 0))
            tenant_id = UUID(custom_data.get("tenant_id"))

            # Update topup status
            result = await self.db.execute(select(CreditTopup).filter(CreditTopup.id == UUID(topup_id)))
            topup = result.scalar_one_or_none()

            if topup:
                topup.status = TopupStatus.COMPLETED
                topup.paddle_transaction_id = transaction_id
                topup.completed_at = datetime.now(UTC)
                await self.db.commit()

                # Add credits to tenant
                await self.credit_service.add_credits(
                    tenant_id=tenant_id,
                    amount=credits_amount,
                    transaction_type=TransactionType.PURCHASE,
                    description=f"Credit top-up purchase: {credits_amount} credits (Paddle)",
                )

            logger.info(f"Handled transaction.completed for credit topup {topup_id}")

        elif event_type in ["subscription", "subscription_upgrade"]:
            # Handle subscription creation/upgrade from transaction
            tenant_id = UUID(custom_data.get("tenant_id"))
            plan_id = UUID(custom_data.get("plan_id"))
            # subscription_id is directly in data, not nested
            subscription_id = data.get("subscription_id")
            customer_id = data.get("customer_id")

            # Get the plan
            result = await self.db.execute(select(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id))
            plan = result.scalar_one_or_none()

            if not plan:
                logger.warning(f"Plan {plan_id} not found for transaction {transaction_id}")
                return False

            # Check if tenant already has a subscription
            result = await self.db.execute(select(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_id))
            tenant_subscription = result.scalar_one_or_none()

            # Only a checkout or a recurring renewal starts a new period. A proration charge for a plan change
            # ("subscription_update") or a one-off charge must not reset allowances or grant another month.
            starts_new_period = data.get("origin") in (None, "web", "api", "subscription_recurring")

            if tenant_subscription:
                # Update existing subscription
                tenant_subscription.plan_id = plan_id
                tenant_subscription.paddle_subscription_id = subscription_id
                tenant_subscription.paddle_customer_id = customer_id
                tenant_subscription.payment_provider = "paddle"
                tenant_subscription.status = SubscriptionStatus.ACTIVE
                # A paid (re-)subscription replaces any earlier request to cancel at period end
                tenant_subscription.cancel_at_period_end = False
                tenant_subscription.cancelled_at = None
                if starts_new_period:
                    tenant_subscription.current_period_start = datetime.now(UTC)
                # Period end will be updated by subscription.updated webhook
            else:
                from datetime import timedelta

                # Create new subscription
                tenant_subscription = TenantSubscription(
                    tenant_id=tenant_id,
                    plan_id=plan_id,
                    paddle_subscription_id=subscription_id,
                    paddle_customer_id=customer_id,
                    payment_provider="paddle",
                    status=SubscriptionStatus.ACTIVE,
                    current_period_start=datetime.now(UTC),
                    current_period_end=datetime.now(UTC) + timedelta(days=30),
                )
                self.db.add(tenant_subscription)

            await self.db.commit()
            await self.db.refresh(tenant_subscription)

            # Allocate monthly credits
            if starts_new_period:
                await self.subscription_service.renew_subscription(tenant_subscription.id)

            logger.info(f"Handled transaction.completed for subscription {subscription_id}")

        return True

    async def _handle_transaction_payment_failed(self, data: dict) -> bool:
        """Handle transaction.payment_failed event"""
        custom_data = data.get("custom_data", {})

        if custom_data.get("type") == "credit_topup":
            topup_id = custom_data.get("topup_id")

            # Update topup status
            result = await self.db.execute(select(CreditTopup).filter(CreditTopup.id == UUID(topup_id)))
            topup = result.scalar_one_or_none()

            if topup:
                topup.status = TopupStatus.FAILED
                await self.db.commit()

            logger.info(f"Handled transaction.payment_failed for topup {topup_id}")

        return True

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_client_token(self) -> str | None:
        """Get client-side token for Paddle.js initialization"""
        return self._get_paddle_client_side_token()

    def get_environment(self) -> str:
        """Get current Paddle environment (sandbox or production)"""
        return self.environment
