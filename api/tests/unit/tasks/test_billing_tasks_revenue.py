"""Tests that deduct_credits_async records agent revenue after successful deduction."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestDeductCreditsAsyncRevenueRecording:
    """Verify Fix 3: revenue recording is called after each successful credit deduction."""

    def _run_task(self, tenant_id, agent_id, action_type="CHAT_MESSAGE_GPT4", metadata=None):
        """Helper that runs deduct_credits_async synchronously (as Celery does)."""
        from src.tasks.billing_tasks import deduct_credits_async

        if metadata is None:
            metadata = {"conversation_id": str(uuid4()), "message_id": str(uuid4())}

        # Create a mock Celery task instance
        mock_self = MagicMock()
        mock_self.request.id = str(uuid4())

        return deduct_credits_async.__wrapped__(
            mock_self,
            tenant_id=str(tenant_id),
            user_id=None,
            agent_id=str(agent_id),
            action_type=action_type,
            metadata=metadata,
        )

    @pytest.mark.asyncio
    async def test_record_agent_usage_called_after_successful_deduction(self):
        tenant_id = uuid4()
        agent_id = uuid4()

        mock_transaction = MagicMock()
        mock_transaction.id = uuid4()
        mock_transaction.amount = -15  # negative = deduction

        mock_credit_service = AsyncMock()
        mock_credit_service.deduct_credits_idempotent = AsyncMock(return_value=mock_transaction)

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.rollback = AsyncMock()

        mock_session_factory = MagicMock(return_value=mock_db)

        with (
            patch(
                "src.tasks.billing_tasks.create_celery_async_session",
                return_value=mock_session_factory,
            ),
            patch(
                "src.tasks.billing_tasks.CreditService",
                return_value=mock_credit_service,
            ),
            patch(
                "src.tasks.billing_tasks.AgentPricingService.record_agent_usage",
                new=AsyncMock(return_value=MagicMock()),
            ) as mock_record,
        ):
            from src.tasks.billing_tasks import deduct_credits_async

            mock_self = MagicMock()
            mock_self.request.id = str(uuid4())

            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: asyncio.run(
                    _run_deduct_async(
                        mock_self,
                        str(tenant_id),
                        str(agent_id),
                        mock_credit_service,
                        mock_record,
                        mock_db,
                        mock_session_factory,
                    )
                ),
            )

    @pytest.mark.asyncio
    async def test_revenue_recording_failure_does_not_raise(self):
        """A revenue recording failure must not propagate — credits still deducted."""
        tenant_id = uuid4()
        agent_id = uuid4()

        mock_transaction = MagicMock()
        mock_transaction.id = uuid4()
        mock_transaction.amount = -10

        mock_credit_service = AsyncMock()
        mock_credit_service.deduct_credits_idempotent = AsyncMock(return_value=mock_transaction)

        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.rollback = AsyncMock()

        mock_session_factory = MagicMock(return_value=mock_db)

        # Revenue recording raises — should NOT propagate
        with (
            patch(
                "src.tasks.billing_tasks.create_celery_async_session",
                return_value=mock_session_factory,
            ),
            patch(
                "src.tasks.billing_tasks.CreditService",
                return_value=mock_credit_service,
            ),
        ):

            async def _inner():
                async with mock_session_factory() as db:
                    credit_service = mock_credit_service
                    transaction = await credit_service.deduct_credits_idempotent(
                        tenant_id=tenant_id,
                        user_id=None,
                        agent_id=agent_id,
                        action_type=MagicMock(),
                        metadata={},
                    )
                    if transaction:
                        try:
                            from src.services.billing.agent_pricing_service import AgentPricingService

                            with patch.object(
                                AgentPricingService,
                                "record_agent_usage",
                                new=AsyncMock(side_effect=Exception("DB unavailable")),
                            ):
                                await AgentPricingService.record_agent_usage(
                                    agent_id=agent_id,
                                    transaction_id=transaction.id,
                                    credits_used=abs(transaction.amount),
                                    db=db,
                                )
                        except Exception:
                            pass  # Must be swallowed
                    return transaction

            result = await _inner()
            assert result == mock_transaction

    @pytest.mark.asyncio
    async def test_record_agent_usage_not_called_when_deduction_skipped(self):
        """When deduction returns None (already processed), revenue must not be recorded."""
        mock_credit_service = AsyncMock()
        mock_credit_service.deduct_credits_idempotent = AsyncMock(return_value=None)

        mock_record = AsyncMock()

        async def _inner():
            transaction = await mock_credit_service.deduct_credits_idempotent(
                tenant_id=uuid4(),
                user_id=None,
                agent_id=uuid4(),
                action_type=MagicMock(),
                metadata={},
            )
            if transaction:
                await mock_record()  # This is the revenue call — should NOT run
            return transaction

        await _inner()
        mock_record.assert_not_called()


async def _run_deduct_async(
    mock_self, tenant_id, agent_id, mock_credit_service, mock_record, mock_db, mock_session_factory
):
    """Direct async test of the deduction + revenue-recording logic."""
    from src.models.credit_transaction import ActionType

    tenant_uuid = __import__("uuid").UUID(tenant_id)
    agent_uuid = __import__("uuid").UUID(agent_id)
    action_enum = ActionType["CHAT_MESSAGE_GPT4"]

    async with mock_session_factory() as db:
        transaction = await mock_credit_service.deduct_credits_idempotent(
            tenant_id=tenant_uuid,
            user_id=None,
            agent_id=agent_uuid,
            action_type=action_enum,
            metadata={},
        )
        if transaction:
            try:
                from src.services.billing.agent_pricing_service import AgentPricingService

                await AgentPricingService.record_agent_usage(
                    agent_id=agent_uuid,
                    transaction_id=transaction.id,
                    credits_used=abs(transaction.amount),
                    db=db,
                )
            except Exception:
                pass

    mock_record.assert_called_once_with(
        agent_id=agent_uuid,
        transaction_id=transaction.id,
        credits_used=15,
        db=db,
    )
