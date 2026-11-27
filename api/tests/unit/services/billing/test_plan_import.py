import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.subscription_plan import PlanTier, SubscriptionPlan
from src.services.billing.plan_import import PlanConfigError, import_plans, validate_quota_pools

EXAMPLE = Path(__file__).resolve().parents[4] / "examples" / "quota_plans.example.json"


class TestValidateQuotaPools:
    def test_accepts_a_valid_list_and_fills_label(self):
        pools = validate_quota_pools([{"key": "chat", "limit": 10}, {"key": "docs", "label": "Docs", "limit": 0}])
        assert pools == [{"key": "chat", "label": "chat", "limit": 10}, {"key": "docs", "label": "Docs", "limit": 0}]

    def test_none_means_no_pools(self):
        assert validate_quota_pools(None) == []

    @pytest.mark.parametrize(
        "bad",
        [
            "nope",
            [{"key": "Has Space", "limit": 1}],
            [{"key": "", "limit": 1}],
            [{"key": "a", "limit": -1}],
            [{"key": "a", "limit": "10"}],
            [{"key": "a", "limit": True}],
            [{"key": "a", "limit": 1}, {"key": "a", "limit": 2}],
            [{"limit": 1}],
        ],
    )
    def test_rejects_bad_pools(self, bad):
        with pytest.raises(PlanConfigError):
            validate_quota_pools(bad)


class TestImportPlans:
    @pytest.fixture
    def db(self):
        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        return session

    def _existing(self, db, plan):
        result = MagicMock()
        result.scalar_one_or_none.return_value = plan
        db.execute.return_value = result

    async def test_example_file_is_valid_and_creates_plans(self, db):
        self._existing(db, None)
        plans = json.loads(EXAMPLE.read_text())
        outcome = await import_plans(db, plans)
        assert outcome == {"Growth": "created", "Scale": "created"}
        created = [c.args[0] for c in db.add.call_args_list]
        assert created[0].quota_pools[0] == {"key": "assistant", "label": "Assistant agent messages", "limit": 2500}
        db.commit.assert_awaited_once()

    async def test_updating_a_plan_changes_only_the_fields_in_the_file(self, db):
        """Reproduces a price-only update wiping pools and credits and re-activating a retired plan."""
        pools = [{"key": "a", "label": "A", "limit": 7}]
        existing = SubscriptionPlan(
            name="Growth",
            tier=PlanTier.PROFESSIONAL,
            price_monthly=1,
            credits_monthly=500,
            credits_rollover=True,
            is_active=False,
            quota_pools=pools,
        )
        self._existing(db, existing)

        outcome = await import_plans(db, [{"name": "Growth", "price_monthly": 349}])

        assert outcome == {"Growth": "updated"}
        assert existing.price_monthly == 349
        assert existing.tier == PlanTier.PROFESSIONAL
        assert existing.credits_monthly == 500 and existing.credits_rollover is True
        assert existing.is_active is False
        assert existing.quota_pools == pools
        db.add.assert_not_called()

    async def test_pools_can_be_changed_or_removed_when_the_file_says_so(self, db):
        existing = SubscriptionPlan(
            name="Growth", price_monthly=1, quota_pools=[{"key": "a", "label": "A", "limit": 1}]
        )
        self._existing(db, existing)
        await import_plans(db, [{"name": "Growth", "quota_pools": [{"key": "b", "limit": 9}]}])
        assert existing.quota_pools == [{"key": "b", "label": "b", "limit": 9}]
        await import_plans(db, [{"name": "Growth", "quota_pools": []}])
        assert existing.quota_pools is None

    async def test_a_new_plan_gets_defaults_for_what_is_not_mentioned(self, db):
        self._existing(db, None)
        await import_plans(db, [{"name": "Basic", "price_monthly": 10}])
        created = db.add.call_args.args[0]
        assert created.tier == PlanTier.STARTER and created.credits_monthly == 0
        assert created.credits_rollover is False and created.is_active is True

    async def test_a_new_plan_without_a_price_is_refused_and_nothing_is_written(self, db):
        self._existing(db, None)
        with pytest.raises(PlanConfigError, match="price_monthly is required"):
            await import_plans(db, [{"name": "Basic"}])
        db.add.assert_not_called()
        db.commit.assert_not_called()

    @pytest.mark.parametrize(
        "bad",
        [
            {"price_monthly": "ten"},
            {"price_monthly": 1, "credits_monthly": "lots"},
            {"price_monthly": 1, "price_yearly": "x"},
        ],
    )
    async def test_bad_numbers_are_a_clear_config_error_not_a_traceback(self, db, bad):
        self._existing(db, None)
        with pytest.raises(PlanConfigError, match="must be a number"):
            await import_plans(db, [{"name": "Basic", **bad}])

    async def test_one_bad_plan_writes_nothing(self, db):
        self._existing(db, None)
        with pytest.raises(PlanConfigError):
            await import_plans(
                db,
                [
                    {"name": "Good", "price_monthly": 1},
                    {"name": "Bad", "price_monthly": 1, "quota_pools": [{"key": "X", "limit": 1}]},
                ],
            )
        db.add.assert_not_called()
        db.commit.assert_not_called()

    @pytest.mark.parametrize(
        "plans",
        [[], [{"price_monthly": 1}], [{"name": "A"}], [{"name": "A", "price_monthly": 1, "tier": "GOLD"}]],
    )
    async def test_rejects_invalid_configs(self, db, plans):
        self._existing(db, None)  # a new plan
        with pytest.raises(PlanConfigError):
            await import_plans(db, plans)

    async def test_duplicate_names_rejected(self, db):
        with pytest.raises(PlanConfigError, match="unique"):
            await import_plans(db, [{"name": "A", "price_monthly": 1}, {"name": "A", "price_monthly": 2}])


class TestPlanValueLimits:
    @pytest.fixture
    def db(self):
        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result
        session.scalar.return_value = None
        return session

    @pytest.mark.parametrize(
        "extra",
        [
            {"credits_monthly": -5},
            {"credits_monthly": 2**31},
            {"price_monthly": -1},
            {"features": {"max_rollover_credits": -1}},
            {"features": {"max_rollover_credits": "lots"}},
            {"features": {"max_rollover_credits": True}},
            {"features": "nope"},
            {"quota_pools": [{"key": "a", "limit": 2**31}]},
        ],
    )
    async def test_values_that_would_break_billing_are_refused(self, db, extra):
        with pytest.raises(PlanConfigError):
            await import_plans(db, [{"name": "P", "price_monthly": 1, **extra}])
        db.commit.assert_not_called()

    async def test_only_one_free_plan(self, db):
        db.scalar.return_value = "Existing Free"
        with pytest.raises(PlanConfigError, match="tier FREE"):
            await import_plans(db, [{"name": "Another Free", "price_monthly": 0, "tier": "FREE"}])
        db.scalar.return_value = None
        with pytest.raises(PlanConfigError, match="tier FREE"):
            await import_plans(
                db,
                [{"name": "A", "price_monthly": 0, "tier": "FREE"}, {"name": "B", "price_monthly": 0, "tier": "FREE"}],
            )


def test_a_plan_can_be_hidden_from_the_pricing_page():
    from src.services.billing.plan_import import _parse_plan

    assert _parse_plan({"name": "Partner", "is_public": False})["values"]["is_public"] is False
    assert "is_public" not in _parse_plan({"name": "Partner"})["values"]  # updating a plan leaves it as it was
