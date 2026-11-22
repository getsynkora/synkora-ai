from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.billing.chat_billing_service import BillingErrorCode, ChatBillingService
from src.services.billing.quota_service import (
    DEFAULT_POOL_KEY,
    ConsumeResult,
    PoolStatus,
    QuotaService,
    ReserveResult,
)

POOLS = [
    {"key": "support", "label": "Support messages", "limit": 5},
    {"key": DEFAULT_POOL_KEY, "label": "Messages", "limit": 100},
]


def _status(used: int, limit: int = 5) -> PoolStatus:
    start = datetime(2026, 11, 1, tzinfo=UTC)
    return PoolStatus("support", "Support messages", limit, used, start, start + timedelta(days=30))


@pytest.fixture
def db():
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


class TestFindPool:
    def test_matches_key(self):
        assert QuotaService._find_pool(POOLS, "support")["limit"] == 5

    def test_no_key_uses_default_pool(self):
        assert QuotaService._find_pool(POOLS, None)["key"] == DEFAULT_POOL_KEY

    def test_unknown_key_is_not_metered(self):
        assert QuotaService._find_pool(POOLS, "other") is None

    def test_plan_without_pools_is_not_metered(self):
        assert QuotaService._find_pool(None, "support") is None
        assert QuotaService._find_pool([], "support") is None


class TestPoolStatus:
    def test_remaining_never_negative(self):
        assert _status(used=7).remaining == 0
        assert _status(used=2).remaining == 3

    def test_exhausted_at_limit(self):
        assert not _status(used=4).exhausted
        assert _status(used=5).exhausted


class TestPeriod:
    def test_uses_subscription_period(self):
        start = datetime(2026, 11, 3, tzinfo=UTC)
        end = datetime(2026, 12, 3, tzinfo=UTC)
        sub = MagicMock(current_period_start=start, current_period_end=end)
        assert QuotaService._period(sub) == (start, end)

    def test_falls_back_to_calendar_month(self):
        sub = MagicMock(current_period_start=None, current_period_end=None)
        start, end = QuotaService._period(sub)
        assert start.day == 1 and start.hour == 0
        assert end > start


class TestConsume:
    async def test_no_subscription_is_not_metered(self, db):
        service = QuotaService(db)
        with patch.object(service, "_active_plan", AsyncMock(return_value=None)):
            assert await service.consume(uuid4(), "support", "msg_1") == ConsumeResult.NOT_METERED

    async def test_plan_without_pools_is_not_metered(self, db):
        service = QuotaService(db)
        sub = MagicMock(current_period_start=None, current_period_end=None)
        plan = MagicMock(quota_pools=None)
        with patch.object(service, "_active_plan", AsyncMock(return_value=(sub, plan))):
            assert await service.consume(uuid4(), "support", "msg_1") == ConsumeResult.NOT_METERED
        db.execute.assert_not_called()

    async def test_repeated_key_is_duplicate_and_not_counted(self, db):
        service = QuotaService(db)
        sub = MagicMock(current_period_start=None, current_period_end=None)
        plan = MagicMock(quota_pools=POOLS)
        already_counted = MagicMock()
        already_counted.scalar_one_or_none.return_value = None
        db.execute.return_value = already_counted
        with patch.object(service, "_active_plan", AsyncMock(return_value=(sub, plan))):
            result = await service.consume(uuid4(), "support", "msg_1")
        assert result == ConsumeResult.DUPLICATE
        assert db.execute.call_count == 1  # only the event insert, no counter update
        db.commit.assert_not_called()


class TestValidateQuota:
    async def test_not_metered_returns_none_so_credits_apply(self, db):
        service = ChatBillingService(db)
        with patch("src.services.billing.chat_billing_service.QuotaService") as quota:
            quota.return_value.get_pool_status = AsyncMock(return_value=None)
            assert await service.validate_quota(uuid4(), "support") is None

    async def test_available_pool_is_valid(self, db):
        service = ChatBillingService(db)
        with patch("src.services.billing.chat_billing_service.QuotaService") as quota:
            quota.return_value.get_pool_status = AsyncMock(return_value=_status(used=1))
            result = await service.validate_quota(uuid4(), "support")
        assert result.is_valid

    async def test_exhausted_pool_blocks_with_reset_date(self, db):
        service = ChatBillingService(db)
        with patch("src.services.billing.chat_billing_service.QuotaService") as quota:
            quota.return_value.get_pool_status = AsyncMock(return_value=_status(used=5))
            result = await service.validate_quota(uuid4(), "support")
        assert not result.is_valid
        assert result.error.error_code == BillingErrorCode.QUOTA_EXCEEDED
        assert "Support messages" in result.error.message
        assert result.error.details["limit"] == 5


def _result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    r.first.return_value = value
    return r


class TestReserve:
    @pytest.fixture
    def metered(self):
        sub = MagicMock(current_period_start=None, current_period_end=None)
        return sub, MagicMock(quota_pools=POOLS)

    async def test_not_metered_without_pools(self, db):
        service = QuotaService(db)
        sub = MagicMock(current_period_start=None, current_period_end=None)
        with patch.object(service, "_active_plan", AsyncMock(return_value=(sub, MagicMock(quota_pools=None)))):
            assert await service.reserve(uuid4(), "support", "msg_1") == ReserveResult.NOT_METERED
        db.execute.assert_not_called()

    async def test_reserved_commits(self, db, metered):
        service = QuotaService(db)
        # event insert -> new id, counter upsert, conditional update -> new used value
        db.execute.side_effect = [_result(uuid4()), _result(None), _result(1)]
        with patch.object(service, "_active_plan", AsyncMock(return_value=metered)):
            assert await service.reserve(uuid4(), "support", "msg_1") == ReserveResult.RESERVED
        db.commit.assert_awaited_once()
        db.rollback.assert_not_called()

    async def test_full_pool_is_exhausted_and_rolls_back_the_event(self, db, metered):
        service = QuotaService(db)
        db.execute.side_effect = [_result(uuid4()), _result(None), _result(None)]  # update matched no row
        with patch.object(service, "_active_plan", AsyncMock(return_value=metered)):
            assert await service.reserve(uuid4(), "support", "msg_1") == ReserveResult.EXHAUSTED
        db.rollback.assert_awaited_once()
        db.commit.assert_not_called()

    async def test_same_key_twice_is_duplicate(self, db, metered):
        service = QuotaService(db)
        db.execute.side_effect = [_result(None)]
        with patch.object(service, "_active_plan", AsyncMock(return_value=metered)):
            assert await service.reserve(uuid4(), "support", "msg_1") == ReserveResult.DUPLICATE
        assert db.execute.call_count == 1


class TestRelease:
    async def test_unknown_key_returns_false(self, db):
        db.execute.return_value = _result(None)
        assert await QuotaService(db).release(uuid4(), "msg_missing") is False
        db.commit.assert_not_called()

    async def test_known_key_gives_the_unit_back(self, db):
        db.execute.side_effect = [_result(("support", datetime(2026, 11, 1, tzinfo=UTC), 1)), _result(None)]
        assert await QuotaService(db).release(uuid4(), "msg_1") is True
        assert db.execute.call_count == 2
        db.commit.assert_awaited_once()
