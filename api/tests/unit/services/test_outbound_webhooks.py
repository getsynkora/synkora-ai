import hashlib
import hmac
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services import outbound_webhooks as hooks
from src.services.billing.quota_service import QuotaService


class TestSigning:
    def test_signature_is_the_hmac_of_timestamp_dot_body(self):
        expected = hmac.new(b"whsec_x", b'123.{"a":1}', hashlib.sha256).hexdigest()
        assert hooks.sign_payload("whsec_x", 123, '{"a":1}') == expected

    def test_a_different_secret_or_body_gives_a_different_signature(self):
        base = hooks.sign_payload("s1", 1, "body")
        assert hooks.sign_payload("s2", 1, "body") != base
        assert hooks.sign_payload("s1", 1, "other") != base
        assert hooks.sign_payload("s1", 2, "body") != base

    def test_secrets_are_unique_and_prefixed(self):
        assert hooks.new_secret().startswith("whsec_")
        assert hooks.new_secret() != hooks.new_secret()


class TestDestination:
    def test_only_https_and_public_addresses_are_allowed(self):
        with patch.object(hooks, "validate_url", return_value=(True, None)) as check:
            assert hooks.destination_error("https://example.com/hook") is None
        kwargs = check.call_args.kwargs
        assert kwargs["allowed_schemes"] == ["https"]
        assert kwargs["block_private_ips"] is True and kwargs["resolve_dns"] is True

    def test_a_refused_url_returns_the_reason(self):
        with patch.object(hooks, "validate_url", return_value=(False, "private address")):
            assert hooks.destination_error("https://10.0.0.1/x") == "private address"


class TestEmitEvent:
    def _db(self, tenant, endpoints):
        db = AsyncMock()
        db.get = AsyncMock(return_value=tenant)
        result = MagicMock()
        result.scalars.return_value.all.return_value = endpoints
        db.execute = AsyncMock(return_value=result)
        return db

    async def test_event_goes_to_own_and_managers_endpoints_with_customer_identity(self):
        manager_id, customer_id = uuid4(), uuid4()
        customer = MagicMock(id=customer_id, external_ref="cust-7", managed_by_tenant_id=manager_id)
        endpoints = [MagicMock(id=uuid4()), MagicMock(id=uuid4())]
        db = self._db(customer, endpoints)
        with patch.object(hooks, "deliver_to") as deliver:
            queued = await hooks.emit_event(db, customer_id, hooks.EVENT_USAGE_THRESHOLD, {"pool": "p"})

        assert queued == 2 and deliver.call_count == 2
        event = deliver.call_args.args[1]
        assert event["type"] == "usage.threshold"
        assert event["tenant_id"] == str(customer_id) and event["tenant_external_ref"] == "cust-7"
        assert event["data"] == {"pool": "p"}
        owners = next(v for v in db.execute.call_args[0][0].compile().params.values() if isinstance(v, list))
        assert set(owners) == {customer_id, manager_id}

    async def test_no_endpoints_queues_nothing(self):
        db = self._db(MagicMock(id=uuid4(), external_ref=None, managed_by_tenant_id=None), [])
        with patch.object(hooks, "deliver_to") as deliver:
            assert await hooks.emit_event(db, uuid4(), hooks.EVENT_USAGE_THRESHOLD, {}) == 0
        deliver.assert_not_called()

    async def test_a_failure_never_breaks_the_caller(self):
        db = AsyncMock()
        db.get = AsyncMock(side_effect=RuntimeError("db down"))
        assert await hooks.emit_event(db, uuid4(), hooks.EVENT_USAGE_THRESHOLD, {}) == 0


class TestSubscriptionEventData:
    def test_describes_the_subscription(self):
        sub = MagicMock(
            status=MagicMock(value="ACTIVE"),
            current_period_start=datetime(2026, 11, 1, tzinfo=UTC),
            current_period_end=None,
            cancel_at_period_end=True,
        )
        data = hooks.subscription_event_data(sub, "Growth")
        assert data == {
            "plan": "Growth",
            "status": "ACTIVE",
            "current_period_start": "2026-11-01T00:00:00+00:00",
            "current_period_end": None,
            "cancel_at_period_end": True,
        }


class TestThresholds:
    async def _crossed(self, before, after, limit):
        service = QuotaService(AsyncMock())
        with patch("src.services.billing.quota_service.emit_event", new=AsyncMock()) as emit:
            await service._notify_thresholds(uuid4(), {"key": "p", "label": "P", "limit": limit}, before, after)
        return [call.args[3]["threshold_percent"] for call in emit.await_args_list]

    @pytest.mark.parametrize(
        ("before", "after", "limit", "expected"),
        [
            (3, 4, 5, [80]),  # 80% of 5 is 4
            (4, 5, 5, [100]),  # already past 80%
            (7, 8, 10, [80]),
            (8, 9, 10, []),
            (0, 1, 10, []),
            (0, 1, 1, [80, 100]),  # a single message crosses both
            (9, 10, 10, [100]),
            (10, 11, 10, []),  # overshoot does not repeat the alert
        ],
    )
    async def test_alerts_once_when_each_level_is_crossed(self, before, after, limit, expected):
        assert await self._crossed(before, after, limit) == expected

    async def test_a_pool_with_no_allowance_never_alerts(self):
        assert await self._crossed(0, 1, 0) == []
