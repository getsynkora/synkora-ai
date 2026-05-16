"""
Stripe Payment Integration Service

Handles all Stripe payment operations including:
- Customer management
- Subscription creation and management
- Payment intents
- Webhook processing
- Payouts for agent creators
"""

import asyncio
import logging
import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from src.config.redis import get_redis_async
from src.models.credit_topup import CreditTopup, TopupStatus
from src.models.credit_transaction import TransactionType
from src.models.subscription_plan import SubscriptionPlan
from src.models.tenant_subscription import SubscriptionStatus, TenantSubscription
from src.services.billing.agent_user_subscription_service import AgentUserSubscriptionService
from src.services.billing.credit_service import CreditService
from src.services.billing.subscription_service import SubscriptionService
from src.services.integrations.integration_config_service import IntegrationConfigService


class StripeService:
    """Service for handling Stripe payment operations"""

    def __init__(self, db: AsyncSession, _skip_init: bool = False):
        self.db = db
        self.credit_service = CreditService(db)
        self.subscription_service = SubscriptionService(db)
        self.integration_config_service = IntegrationConfigService(db)
        self._initialized = _skip_init  # True if created via factory method

    @classmethod
    async def create(cls, db: AsyncSession) -> "StripeService":
        """Factory method to create an initialized StripeService instance."""
        service = cls(db, _skip_init=True)
        await service._initialize_stripe()
        return service

    async def _initialize_stripe(self):
        """Initialize Stripe with API key from integration config"""
        logger.info("Initializing Stripe service...")
        stripe_key = await self._get_stripe_secret_key()
        if stripe_key:
            logger.info("Stripe secret key found, setting API key")
            stripe.api_key = stripe_key
            self._initialized = True
        else:
            logger.error("Stripe secret key not found in integration configs")
            raise ValueError("Stripe secret key not configured in integration configs")

    async def _get_stripe_secret_key(self) -> str | None:
        """Get Stripe secret key from integration config"""
        logger.info("Fetching Stripe secret key from integration configs...")
        logger.debug("Calling get_active_config with tenant_id=None, category='payment', provider='stripe'")

        config = await self.integration_config_service.get_active_config(None, "payment", "stripe")

        if config:
            logger.info(
                f"Found integration config: id={config.id}, provider={config.provider}, is_active={config.is_active}"
            )
            config_data = self.integration_config_service._decrypt_config(config.config_data)
            logger.debug(f"Decrypted config data keys: {list(config_data.keys())}")

            # Access nested credentials.secret_key
            credentials = config_data.get("credentials", {})
            secret_key = credentials.get("secret_key")

            if secret_key:
                logger.info("Stripe secret key found in config")
                return secret_key
            else:
                logger.warning("Stripe secret key not found in config data")
                return None
        else:
            logger.warning("No active Stripe integration config found")
            return None

    async def _get_stripe_publishable_key(self) -> str | None:
        """Get Stripe publishable key from integration config"""
        config = await self.integration_config_service.get_active_config(None, "payment", "stripe")
        if config:
            config_data = self.integration_config_service._decrypt_config(config.config_data)
            # Access nested settings.publishable_key
            settings = config_data.get("settings", {})
            return settings.get("publishable_key")
        return None

    async def _get_stripe_webhook_secret(self) -> str | None:
        """Get Stripe webhook secret from integration config"""
        config = await self.integration_config_service.get_active_config(None, "payment", "stripe")
        if config:
            config_data = self.integration_config_service._decrypt_config(config.config_data)
            # Access nested credentials.webhook_secret
            credentials = config_data.get("credentials", {})
            return credentials.get("webhook_secret")
        return None

    async def _ensure_stripe_configured(self):
        """Ensure Stripe is properly configured before operations"""
        stripe_key = await self._get_stripe_secret_key()
        if not stripe_key:
            raise ValueError("Stripe integration is not enabled or not properly configured")

    # Customer Management

    async def create_customer(
        self, tenant_id: UUID, email: str, name: str | None = None, metadata: dict | None = None
    ) -> str:
        """
        Create a Stripe customer for a tenant

        Args:
            tenant_id: Tenant UUID
            email: Customer email
            name: Customer name (optional)
            metadata: Additional metadata (optional)

        Returns:
            Stripe customer ID
        """
        try:
            customer_metadata = metadata or {}
            customer_metadata["tenant_id"] = str(tenant_id)

            customer = await asyncio.to_thread(
                stripe.Customer.create, email=email, name=name, metadata=customer_metadata
            )

            # Store customer ID in tenant's subscription record
            # Check if tenant has a subscription record, if not create one
            result = await self.db.execute(select(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_id))
            subscription = result.scalar_one_or_none()

            if subscription:
                subscription.stripe_customer_id = customer.id
                await self.db.commit()

            return customer.id

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create Stripe customer: {str(e)}")

    async def get_or_create_customer(self, tenant_id: UUID, email: str, name: str | None = None) -> str:
        """
        Get existing Stripe customer or create new one

        Args:
            tenant_id: Tenant UUID
            email: Customer email
            name: Customer name (optional)

        Returns:
            Stripe customer ID
        """
        # Check if customer already exists in subscription record
        result = await self.db.execute(select(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_id))
        subscription = result.scalar_one_or_none()

        if subscription and subscription.stripe_customer_id:
            return subscription.stripe_customer_id

        # Create new customer
        return await self.create_customer(tenant_id, email, name)

    # Subscription Management

    async def create_subscription(
        self, customer_id: str, price_id: str, trial_days: int | None = None, metadata: dict | None = None
    ) -> dict:
        """
        Create a Stripe subscription

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            trial_days: Trial period in days (optional)
            metadata: Additional metadata (optional)

        Returns:
            Subscription data
        """
        try:
            subscription_params = {
                "customer": customer_id,
                "items": [{"price": price_id}],
                "metadata": metadata or {},
                "payment_behavior": "default_incomplete",
                "payment_settings": {"save_default_payment_method": "on_subscription"},
                "expand": ["latest_invoice.payment_intent"],
                "invoice_settings": {
                    "custom_fields": [
                        {"name": "Platform", "value": "Synkora"},
                    ]
                },
            }

            if trial_days:
                subscription_params["trial_period_days"] = trial_days

            subscription = await asyncio.to_thread(stripe.Subscription.create, **subscription_params)

            return {
                "subscription_id": subscription.id,
                "client_secret": subscription.latest_invoice.payment_intent.client_secret,
                "status": subscription.status,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create subscription: {str(e)}")

    async def update_subscription(
        self, subscription_id: str, price_id: str | None = None, proration_behavior: str = "create_prorations"
    ) -> dict:
        """
        Update an existing subscription

        Args:
            subscription_id: Stripe subscription ID
            price_id: New price ID (optional)
            proration_behavior: How to handle prorations

        Returns:
            Updated subscription data
        """
        try:
            subscription = await asyncio.to_thread(stripe.Subscription.retrieve, subscription_id)

            update_params = {"proration_behavior": proration_behavior}

            if price_id:
                update_params["items"] = [
                    {"id": subscription.get("items", {}).get("data", [{}])[0].get("id"), "price": price_id}
                ]

            updated_subscription = await asyncio.to_thread(stripe.Subscription.modify, subscription_id, **update_params)

            return {
                "subscription_id": updated_subscription.id,
                "status": updated_subscription.status,
                "current_period_end": updated_subscription.current_period_end,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to update subscription: {str(e)}")

    async def cancel_subscription(self, subscription_id: str, immediate: bool = False) -> bool:
        """
        Cancel a Stripe subscription

        Args:
            subscription_id: Stripe subscription ID
            immediate: Cancel immediately or at period end

        Returns:
            Success status
        """
        try:
            if immediate:
                await asyncio.to_thread(stripe.Subscription.delete, subscription_id)
            else:
                await asyncio.to_thread(stripe.Subscription.modify, subscription_id, cancel_at_period_end=True)
            return True

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to cancel subscription: {str(e)}")

    # Payment Intents

    async def create_payment_intent(
        self,
        amount: int,  # Amount in cents
        customer_id: str,
        currency: str = "usd",
        metadata: dict | None = None,
    ) -> dict:
        """
        Create a payment intent for one-time payments

        Args:
            amount: Amount in cents
            customer_id: Stripe customer ID
            currency: Currency code
            metadata: Additional metadata

        Returns:
            Payment intent data
        """
        try:
            payment_intent = await asyncio.to_thread(
                stripe.PaymentIntent.create,
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True},
            )

            return {
                "payment_intent_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "status": payment_intent.status,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create payment intent: {str(e)}")

    # Checkout Sessions (Hosted Payment Page)

    async def create_checkout_session(
        self,
        customer_id: str,
        line_items: list[dict],
        success_url: str,
        cancel_url: str,
        metadata: dict | None = None,
        mode: str = "payment",
    ) -> dict:
        """
        Create a Stripe Checkout session for hosted payment page

        Args:
            customer_id: Stripe customer ID
            line_items: List of line items to purchase
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled
            metadata: Additional metadata
            mode: 'payment' for one-time, 'subscription' for recurring

        Returns:
            Checkout session data with URL
        """
        try:
            support_email = os.environ.get("SUPPORT_EMAIL", "support@your-domain.com")
            session_params: dict = {
                "customer": customer_id,
                "line_items": line_items,
                "mode": mode,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata or {},
                "payment_method_types": ["card"],
                "billing_address_collection": "auto",
                # Safe per-session branding — does not affect account-wide Stripe Dashboard settings
                "custom_text": {"submit": {"message": "You'll be charged by Synkora"}},
                "allow_promotion_codes": True,
            }
            if mode == "payment":
                session_params["invoice_creation"] = {
                    "enabled": True,
                    "invoice_data": {
                        "footer": f"Synkora Platform | {support_email}",
                    },
                }

            session = await asyncio.to_thread(stripe.checkout.Session.create, **session_params)

            return {"session_id": session.id, "checkout_url": session.url, "status": session.status}

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create checkout session: {str(e)}")

    async def create_topup_checkout_session(
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
        Create a checkout session for credit top-up

        Args:
            tenant_id: Tenant UUID
            topup_id: Credit topup ID
            credits_amount: Number of credits to purchase
            price_cents: Price in cents
            customer_id: Stripe customer ID
            success_url: Success redirect URL
            cancel_url: Cancel redirect URL

        Returns:
            Checkout session data
        """
        line_items = [
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"{credits_amount} Credits",
                        "description": f"Purchase {credits_amount} credits for your account",
                    },
                    "unit_amount": price_cents,
                },
                "quantity": 1,
            }
        ]

        metadata = {
            "tenant_id": str(tenant_id),
            "topup_id": str(topup_id),
            "credits_amount": credits_amount,
            "type": "credit_topup",
        }

        return await self.create_checkout_session(
            customer_id=customer_id,
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
            mode="payment",
        )

    async def create_subscription_checkout_session(
        self, customer_id: str, price_id: str, success_url: str, cancel_url: str, metadata: dict | None = None
    ) -> dict:
        """
        Create a checkout session for subscription

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID for the subscription
            success_url: Success redirect URL
            cancel_url: Cancel redirect URL
            metadata: Additional metadata

        Returns:
            Checkout session data
        """
        line_items = [{"price": price_id, "quantity": 1}]

        return await self.create_checkout_session(
            customer_id=customer_id,
            line_items=line_items,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
            mode="subscription",
        )

    # Credit Top-ups

    async def create_topup_payment(
        self, tenant_id: UUID, credits_amount: int, price_cents: int, customer_id: str
    ) -> dict:
        """
        Create a payment for credit top-up

        Args:
            tenant_id: Tenant UUID
            credits_amount: Number of credits to purchase
            price_cents: Price in cents
            customer_id: Stripe customer ID

        Returns:
            Payment intent data with topup record
        """
        # Create topup record
        topup = CreditTopup(
            tenant_id=tenant_id,
            credits=credits_amount,
            amount=Decimal(price_cents) / 100,
            payment_method="stripe",
            status=TopupStatus.PENDING,
        )
        self.db.add(topup)
        await self.db.commit()
        await self.db.refresh(topup)

        # Create payment intent
        payment_intent = await self.create_payment_intent(
            amount=price_cents,
            customer_id=customer_id,
            metadata={
                "tenant_id": str(tenant_id),
                "topup_id": str(topup.id),
                "credits_amount": credits_amount,
                "type": "credit_topup",
            },
        )

        # Update topup with payment intent ID
        topup.stripe_payment_intent_id = payment_intent["payment_intent_id"]
        await self.db.commit()

        return {**payment_intent, "topup_id": str(topup.id)}

    # Webhook Handling

    def construct_webhook_event(self, payload: bytes, signature: str, webhook_secret: str) -> stripe.Event:
        """
        Verify and construct webhook event

        Args:
            payload: Request payload
            signature: Stripe signature header
            webhook_secret: Webhook secret

        Returns:
            Verified Stripe event
        """
        try:
            event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
            return event
        except ValueError:
            raise Exception("Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise Exception("Invalid signature")

    # SECURITY: Redis key prefix for webhook deduplication
    WEBHOOK_DEDUP_PREFIX = "stripe_webhook_event:"
    # SECURITY: TTL for deduplication keys (24 hours - matches Stripe's retry window)
    WEBHOOK_DEDUP_TTL = 86400

    def _check_webhook_idempotency(self, event_id: str) -> bool:
        """
        SECURITY: Check if webhook event has already been processed.

        Prevents replay attacks and duplicate processing of billing events.

        Args:
            event_id: Stripe event ID

        Returns:
            True if this is a new event, False if already processed
        """
        try:
            from src.config.redis import get_redis

            redis = get_redis()
            if not redis:
                # SECURITY: Log warning but allow processing if Redis unavailable
                # Better to risk double-processing than miss payments
                logger.warning("Redis unavailable for webhook deduplication")
                return True

            dedup_key = f"{self.WEBHOOK_DEDUP_PREFIX}{event_id}"

            # SECURITY: Use SETNX for atomic check-and-set
            # Returns True if key was set (new event), False if already exists
            is_new = redis.setnx(dedup_key, "1")

            if is_new:
                # Set TTL on the key
                redis.expire(dedup_key, self.WEBHOOK_DEDUP_TTL)
                return True
            else:
                logger.warning(f"Duplicate webhook event detected: {event_id}")
                return False

        except Exception as e:
            logger.warning(f"Error checking webhook idempotency: {e}")
            # Allow processing on error - better than missing payments
            return True

    async def handle_webhook_event(self, event: stripe.Event) -> bool:
        """
        Handle Stripe webhook events

        SECURITY: Includes idempotency check to prevent replay attacks.

        Args:
            event: Stripe event object

        Returns:
            Success status
        """
        event_id = event.get("id")
        event_type = event["type"]

        # SECURITY: Check for duplicate events (replay attack prevention)
        if event_id and not self._check_webhook_idempotency(event_id):
            logger.info(f"Skipping duplicate webhook event: {event_id}")
            return True  # Return True to acknowledge to Stripe

        handlers = {
            "checkout.session.completed": self._handle_checkout_session_completed,
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_succeeded": self._handle_invoice_payment_succeeded,
            "invoice.payment_failed": self._handle_invoice_payment_failed,
            "payment_intent.succeeded": self._handle_payment_intent_succeeded,
            "payment_intent.payment_failed": self._handle_payment_intent_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            return await handler(event["data"]["object"])

        return True  # Unhandled events are considered successful

    # Webhook Event Handlers

    async def _handle_subscription_created(self, subscription: dict) -> bool:
        """Handle subscription.created event"""
        customer_id = subscription["customer"]
        subscription_id = subscription["id"]

        # Find tenant subscription by customer ID
        result = await self.db.execute(
            select(TenantSubscription).filter(TenantSubscription.stripe_customer_id == customer_id)
        )
        tenant_subscription = result.scalar_one_or_none()

        if not tenant_subscription:
            return False

        # Update subscription record
        tenant_subscription.stripe_subscription_id = subscription_id
        tenant_subscription.status = SubscriptionStatus.ACTIVE
        await self.db.commit()

        return True

    async def _handle_subscription_updated(self, subscription: dict) -> bool:
        """Handle subscription.updated event"""
        subscription_id = subscription["id"]
        status = subscription["status"]

        # Find and update subscription
        result = await self.db.execute(
            select(TenantSubscription).filter(TenantSubscription.stripe_subscription_id == subscription_id)
        )
        tenant_subscription = result.scalar_one_or_none()

        if tenant_subscription:
            # Map Stripe status to our status
            status_map = {
                "active": SubscriptionStatus.ACTIVE,
                "canceled": SubscriptionStatus.CANCELLED,
                "past_due": SubscriptionStatus.ACTIVE,  # Keep active but flag
                "unpaid": SubscriptionStatus.EXPIRED,
                "trialing": SubscriptionStatus.TRIAL,
            }

            tenant_subscription.status = status_map.get(status, SubscriptionStatus.ACTIVE)
            tenant_subscription.cancel_at_period_end = subscription.get("cancel_at_period_end", False)
            await self.db.commit()

        return True

    async def _handle_subscription_deleted(self, subscription: dict) -> bool:
        """Handle subscription.deleted event"""
        subscription_id = subscription["id"]

        result = await self.db.execute(
            select(TenantSubscription).filter(TenantSubscription.stripe_subscription_id == subscription_id)
        )
        tenant_subscription = result.scalar_one_or_none()

        if tenant_subscription:
            tenant_subscription.status = SubscriptionStatus.CANCELLED
            await self.db.commit()

        return True

    async def _handle_invoice_payment_succeeded(self, invoice: dict) -> bool:
        """Handle invoice.payment_succeeded event"""
        subscription_id = invoice.get("subscription")

        if not subscription_id:
            return True

        result = await self.db.execute(
            select(TenantSubscription).filter(TenantSubscription.stripe_subscription_id == subscription_id)
        )
        tenant_subscription = result.scalar_one_or_none()

        if tenant_subscription:
            # Renew subscription and allocate credits
            await self.subscription_service.renew_subscription(tenant_subscription.tenant_id)

        return True

    async def _handle_invoice_payment_failed(self, invoice: dict) -> bool:
        """Handle invoice.payment_failed event"""
        subscription_id = invoice.get("subscription")

        if not subscription_id:
            return True

        result = await self.db.execute(
            select(TenantSubscription).filter(TenantSubscription.stripe_subscription_id == subscription_id)
        )
        tenant_subscription = result.scalar_one_or_none()

        if tenant_subscription:
            # Mark subscription as having payment issues
            # Could send notification to user
            pass

        return True

    async def _handle_checkout_session_completed(self, session: dict) -> bool:
        """Handle checkout.session.completed event"""
        metadata = session.get("metadata", {})
        event_type = metadata.get("type")

        if event_type == "credit_topup":
            topup_id = metadata.get("topup_id")
            credits_amount = int(metadata.get("credits_amount", 0))
            tenant_id = UUID(metadata.get("tenant_id"))

            # Update topup status
            result = await self.db.execute(select(CreditTopup).filter(CreditTopup.id == UUID(topup_id)))
            topup = result.scalar_one_or_none()

            if topup:
                topup.status = TopupStatus.COMPLETED
                topup.completed_at = datetime.now(UTC)
                await self.db.commit()

                # Add credits to tenant
                await self.credit_service.add_credits(
                    tenant_id=tenant_id,
                    amount=credits_amount,
                    transaction_type=TransactionType.PURCHASE,
                    description=f"Credit top-up purchase: {credits_amount} credits",
                )

        elif event_type == "agent_access":
            session_id = session.get("id")
            try:
                raw_token, guest_email = await AgentUserSubscriptionService.fulfill_guest_subscription(
                    session_id, self.db
                )
                # Store token in Redis for frontend retrieval (one-time read, 10 min TTL)
                try:
                    redis = get_redis_async()
                    await redis.setex(f"agent_token:{session_id}", 600, raw_token)
                except Exception as redis_err:
                    logger.warning(f"Failed to cache agent token in Redis: {redis_err}")
                logger.info(f"Agent access granted for guest {guest_email}, session={session_id}")
            except Exception as e:
                logger.error(f"Failed to fulfill agent access for session {session_id}: {e}")
                return False

        elif event_type in ["subscription", "subscription_upgrade"]:
            # Handle subscription creation/upgrade
            tenant_id = UUID(metadata.get("tenant_id"))
            plan_id = UUID(metadata.get("plan_id"))
            subscription_id = session.get("subscription")
            customer_id = session.get("customer")

            # Get the plan
            result = await self.db.execute(select(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id))
            plan = result.scalar_one_or_none()

            if not plan:
                return False

            # Check if tenant already has a subscription
            result = await self.db.execute(select(TenantSubscription).filter(TenantSubscription.tenant_id == tenant_id))
            tenant_subscription = result.scalar_one_or_none()

            if tenant_subscription:
                # Update existing subscription
                tenant_subscription.plan_id = plan_id
                tenant_subscription.stripe_subscription_id = subscription_id
                tenant_subscription.stripe_customer_id = customer_id
                tenant_subscription.status = SubscriptionStatus.ACTIVE
                tenant_subscription.current_period_start = datetime.now(UTC)
                # Set period end to 30 days from now (will be updated by Stripe webhook)
                from datetime import timedelta

                tenant_subscription.current_period_end = datetime.now(UTC) + timedelta(days=30)
            else:
                from datetime import timedelta

                # Create new subscription
                tenant_subscription = TenantSubscription(
                    tenant_id=tenant_id,
                    plan_id=plan_id,
                    stripe_subscription_id=subscription_id,
                    stripe_customer_id=customer_id,
                    status=SubscriptionStatus.ACTIVE,
                    current_period_start=datetime.now(UTC),
                    current_period_end=datetime.now(UTC) + timedelta(days=30),
                )
                self.db.add(tenant_subscription)

            await self.db.commit()
            await self.db.refresh(tenant_subscription)

            # Allocate monthly credits using the subscription ID
            await self.subscription_service.renew_subscription(tenant_subscription.id)

        return True

    async def verify_checkout_session(self, session_id: str) -> bool:
        """
        Verify and process a Stripe checkout session.
        This can be called when the user returns from Stripe checkout
        to create the subscription if webhooks aren't configured.

        Args:
            session_id: Stripe checkout session ID

        Returns:
            True if session was processed successfully
        """
        try:
            # Retrieve the checkout session from Stripe
            session = await asyncio.to_thread(
                stripe.checkout.Session.retrieve, session_id, expand=["subscription", "customer"]
            )

            # Only process if the session is completed
            if session.payment_status == "paid" and session.status == "complete":
                # Extract subscription ID (could be expanded object or string ID)
                subscription_id = None
                if session.subscription:
                    if isinstance(session.subscription, stripe.Subscription):
                        subscription_id = session.subscription.id
                    else:
                        subscription_id = session.subscription

                # Extract customer ID (could be expanded object or string ID)
                customer_id = None
                if session.customer:
                    if isinstance(session.customer, stripe.Customer):
                        customer_id = session.customer.id
                    else:
                        customer_id = session.customer

                # Convert session to dict format expected by handler
                session_dict = {
                    "id": session.id,
                    "subscription": subscription_id,
                    "customer": customer_id,
                    "metadata": session.metadata or {},
                    "payment_status": session.payment_status,
                    "status": session.status,
                }

                # Process using the existing handler
                return await self._handle_checkout_session_completed(session_dict)

            return False

        except stripe.error.StripeError as e:
            logger.warning(f"Error verifying checkout session: {str(e)}")
            raise Exception(f"Failed to verify checkout session: {str(e)}")

    async def _handle_payment_intent_succeeded(self, payment_intent: dict) -> bool:
        """Handle payment_intent.succeeded event"""
        metadata = payment_intent.get("metadata", {})

        if metadata.get("type") == "credit_topup":
            topup_id = metadata.get("topup_id")
            credits_amount = int(metadata.get("credits_amount", 0))
            tenant_id = UUID(metadata.get("tenant_id"))

            # Update topup status
            result = await self.db.execute(select(CreditTopup).filter(CreditTopup.id == UUID(topup_id)))
            topup = result.scalar_one_or_none()

            if topup:
                topup.status = TopupStatus.COMPLETED
                topup.completed_at = datetime.now(UTC)
                await self.db.commit()

                # Add credits to tenant
                await self.credit_service.add_credits(
                    tenant_id=tenant_id,
                    amount=credits_amount,
                    transaction_type=TransactionType.PURCHASE,
                    description=f"Credit top-up purchase: {credits_amount} credits",
                )

        return True

    async def _handle_payment_intent_failed(self, payment_intent: dict) -> bool:
        """Handle payment_intent.payment_failed event"""
        metadata = payment_intent.get("metadata", {})

        if metadata.get("type") == "credit_topup":
            topup_id = metadata.get("topup_id")

            # Update topup status
            result = await self.db.execute(select(CreditTopup).filter(CreditTopup.id == UUID(topup_id)))
            topup = result.scalar_one_or_none()

            if topup:
                topup.status = TopupStatus.FAILED
                await self.db.commit()

        return True

    # Payout Management (for agent creators)

    async def create_payout(
        self, account_id: str, amount_cents: int, currency: str = "usd", metadata: dict | None = None
    ) -> dict:
        """
        Create a payout to an agent creator's connected account

        Args:
            account_id: Stripe connected account ID
            amount_cents: Amount in cents
            currency: Currency code
            metadata: Additional metadata

        Returns:
            Payout data
        """
        try:
            payout = await asyncio.to_thread(
                stripe.Payout.create,
                amount=amount_cents,
                currency=currency,
                metadata=metadata or {},
                stripe_account=account_id,
            )

            return {"payout_id": payout.id, "status": payout.status, "arrival_date": payout.arrival_date}

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create payout: {str(e)}")

    async def create_connected_account(self, email: str, country: str = "US", metadata: dict | None = None) -> str:
        """
        Create a Stripe connected account for an agent creator

        Args:
            email: Creator email
            country: Country code
            metadata: Additional metadata

        Returns:
            Connected account ID
        """
        try:
            account = await asyncio.to_thread(
                stripe.Account.create,
                type="express",
                country=country,
                email=email,
                capabilities={"card_payments": {"requested": True}, "transfers": {"requested": True}},
                metadata=metadata or {},
            )

            return account.id

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create connected account: {str(e)}")

    async def create_account_link(self, account_id: str, refresh_url: str, return_url: str) -> str:
        """
        Create an account link for onboarding

        Args:
            account_id: Connected account ID
            refresh_url: URL to redirect if link expires
            return_url: URL to redirect after completion

        Returns:
            Account link URL
        """
        try:
            account_link = await asyncio.to_thread(
                stripe.AccountLink.create,
                account=account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type="account_onboarding",
            )

            return account_link.url

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create account link: {str(e)}")

    # Payment Method Management

    async def create_setup_intent(self, customer_id: str, metadata: dict | None = None) -> dict:
        """
        Create a setup intent for collecting payment method without charging

        Args:
            customer_id: Stripe customer ID
            metadata: Additional metadata

        Returns:
            Setup intent data with client secret
        """
        try:
            setup_intent = await asyncio.to_thread(
                stripe.SetupIntent.create,
                customer=customer_id,
                payment_method_types=["card"],
                metadata=metadata or {},
                usage="off_session",
            )

            return {
                "setup_intent_id": setup_intent.id,
                "client_secret": setup_intent.client_secret,
                "status": setup_intent.status,
            }

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create setup intent: {str(e)}")

    async def list_payment_methods(self, customer_id: str, type: str = "card") -> list[dict]:
        """
        List payment methods for a customer

        Args:
            customer_id: Stripe customer ID
            type: Payment method type (default: 'card')

        Returns:
            List of payment methods
        """
        try:
            payment_methods = await asyncio.to_thread(stripe.PaymentMethod.list, customer=customer_id, type=type)

            return [
                {
                    "id": pm.id,
                    "type": pm.type,
                    "card": {
                        "brand": pm.card.brand,
                        "last4": pm.card.last4,
                        "exp_month": pm.card.exp_month,
                        "exp_year": pm.card.exp_year,
                    }
                    if pm.type == "card"
                    else None,
                    "created": pm.created,
                }
                for pm in payment_methods.data
            ]

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to list payment methods: {str(e)}")

    async def detach_payment_method(self, payment_method_id: str) -> bool:
        """
        Detach (remove) a payment method from customer

        Args:
            payment_method_id: Payment method ID to detach

        Returns:
            Success status
        """
        try:
            await asyncio.to_thread(stripe.PaymentMethod.detach, payment_method_id)
            return True

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to detach payment method: {str(e)}")

    async def set_default_payment_method(self, customer_id: str, payment_method_id: str) -> bool:
        """
        Set default payment method for a customer

        Args:
            customer_id: Stripe customer ID
            payment_method_id: Payment method ID to set as default

        Returns:
            Success status
        """
        try:
            await asyncio.to_thread(
                stripe.Customer.modify, customer_id, invoice_settings={"default_payment_method": payment_method_id}
            )
            return True

        except stripe.error.StripeError as e:
            raise Exception(f"Failed to set default payment method: {str(e)}")
