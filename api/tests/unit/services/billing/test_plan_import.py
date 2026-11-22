import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.subscription_plan import SubscriptionPlan
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

    async def test_existing_plan_is_updated_in_place(self, db):
        existing = SubscriptionPlan(name="Growth", price_monthly=1, credits_monthly=5)
        self._existing(db, existing)
        outcome = await import_plans(
            db, [{"name": "Growth", "price_monthly": 299, "quota_pools": [{"key": "a", "limit": 7}]}]
        )
        assert outcome == {"Growth": "updated"}
        assert existing.quota_pools == [{"key": "a", "label": "a", "limit": 7}]
        assert existing.credits_monthly == 0
        db.add.assert_not_called()

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
        with pytest.raises(PlanConfigError):
            await import_plans(db, plans)

    async def test_duplicate_names_rejected(self, db):
        with pytest.raises(PlanConfigError, match="unique"):
            await import_plans(db, [{"name": "A", "price_monthly": 1}, {"name": "A", "price_monthly": 2}])
