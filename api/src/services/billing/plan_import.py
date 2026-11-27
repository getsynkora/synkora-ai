"""
Plan import - create or update subscription plans (including quota pools) from a config file.

The plan list lives in data, not code, so any product or industry can define its own pools::

    [{"name": "Growth", "price_monthly": 549, "quota_pools": [{"key": "support", "label": "...", "limit": 5000}]}]

See ``api/examples/quota_plans.example.json``.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.subscription_plan import PlanTier, SubscriptionPlan

MAX_INT32 = 2**31 - 1  # counters and limits are stored in 32-bit integer columns
_POOL_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

_OPTIONAL_COLUMNS = (
    "description",
    "max_agents",
    "max_team_members",
    "max_api_calls_per_month",
    "max_knowledge_bases",
    "max_data_sources",
    "max_custom_tools",
    "max_database_connections",
    "max_mcp_servers",
    "max_scheduled_tasks",
    "max_widgets",
    "max_slack_bots",
    "max_api_keys",
    "features",
    "stripe_product_id",
    "stripe_price_id",
    "paddle_product_id",
    "paddle_price_id",
)


class PlanConfigError(ValueError):
    """The plan config is invalid."""


def validate_quota_pools(pools: Any) -> list[dict]:
    """Return a clean copy of ``pools`` or raise PlanConfigError."""
    if pools is None:
        return []
    if not isinstance(pools, list):
        raise PlanConfigError("quota_pools must be a list")
    clean: list[dict] = []
    seen: set[str] = set()
    for pool in pools:
        if not isinstance(pool, dict):
            raise PlanConfigError("each quota pool must be an object with key, label and limit")
        key = pool.get("key")
        if not isinstance(key, str) or not _POOL_KEY.match(key):
            raise PlanConfigError(f"invalid pool key {key!r}: use lowercase letters, digits, '-' or '_'")
        if key in seen:
            raise PlanConfigError(f"duplicate pool key {key!r}")
        limit = pool.get("limit")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0 or limit > MAX_INT32:
            raise PlanConfigError(f"pool {key!r}: limit must be a whole number from 0 to {MAX_INT32}")
        label = pool.get("label") or key
        if not isinstance(label, str):
            raise PlanConfigError(f"pool {key!r}: label must be text")
        seen.add(key)
        clean.append({"key": key, "label": label, "limit": limit})
    return clean


# What a brand-new plan gets for anything the file does not say. An existing plan keeps its own values.
_CREATE_DEFAULTS = {"tier": PlanTier.STARTER, "credits_monthly": 0, "credits_rollover": False, "is_active": True}


def _number(plan_name: str, field: str, value: Any, kind: type) -> Any:
    try:
        return kind(str(value)) if kind is Decimal else kind(value)
    except (InvalidOperation, ValueError, TypeError):
        raise PlanConfigError(f"plan {plan_name!r}: {field} must be a number") from None


def _parse_plan(raw: dict) -> dict:
    """Only the fields the file mentions are returned, so updating a plan never resets the others."""
    if not isinstance(raw, dict) or not raw.get("name"):
        raise PlanConfigError("each plan needs a name")
    name = raw["name"]

    values: dict[str, Any] = {}
    if "tier" in raw:
        try:
            values["tier"] = PlanTier[str(raw["tier"]).upper()]
        except KeyError:
            raise PlanConfigError(f"plan {name!r}: tier must be one of {[t.name for t in PlanTier]}") from None
    if "price_monthly" in raw:
        values["price_monthly"] = _number(name, "price_monthly", raw["price_monthly"], Decimal)
        if values["price_monthly"] < 0:
            raise PlanConfigError(f"plan {name!r}: price_monthly cannot be negative")
    if "price_yearly" in raw:
        values["price_yearly"] = (
            None if raw["price_yearly"] is None else _number(name, "price_yearly", raw["price_yearly"], Decimal)
        )
    if "credits_monthly" in raw:
        values["credits_monthly"] = _number(name, "credits_monthly", raw["credits_monthly"], int)
        if not 0 <= values["credits_monthly"] <= MAX_INT32:
            raise PlanConfigError(f"plan {name!r}: credits_monthly must be from 0 to {MAX_INT32}")
    if "credits_rollover" in raw:
        values["credits_rollover"] = bool(raw["credits_rollover"])
    if "is_active" in raw:
        values["is_active"] = bool(raw["is_active"])
    if "is_public" in raw:
        values["is_public"] = bool(raw["is_public"])
    if "quota_pools" in raw:
        values["quota_pools"] = validate_quota_pools(raw["quota_pools"]) or None
    for column in _OPTIONAL_COLUMNS:
        if column in raw:
            values[column] = raw[column]
    features = values.get("features")
    if features is not None and not isinstance(features, dict):
        raise PlanConfigError(f"plan {name!r}: features must be an object")
    if features and "max_rollover_credits" in features:
        cap = features["max_rollover_credits"]
        if isinstance(cap, bool) or not isinstance(cap, int) or not 0 <= cap <= MAX_INT32:
            raise PlanConfigError(f"plan {name!r}: features.max_rollover_credits must be a whole number of 0 or more")
    return {"name": name, "values": values}


async def import_plans(db: AsyncSession, plans: list[dict]) -> dict[str, str]:
    """
    Create or update plans by name. Returns ``{plan name: "created" | "updated"}``.

    A new plan needs ``price_monthly``; anything else it does not mention gets a default. An existing plan
    changes only the fields in the file. All plans are checked before any are written.
    """
    if not isinstance(plans, list) or not plans:
        raise PlanConfigError("the config must be a non-empty list of plans")
    parsed = [_parse_plan(p) for p in plans]
    names = [p["name"] for p in parsed]
    if len(set(names)) != len(names):
        raise PlanConfigError("plan names must be unique")

    existing: dict[str, SubscriptionPlan | None] = {}
    for item in parsed:
        plan = (
            await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == item["name"]))
        ).scalar_one_or_none()
        existing[item["name"]] = plan
        if plan is None and "price_monthly" not in item["values"]:
            raise PlanConfigError(f"plan {item['name']!r} is new, so price_monthly is required")

    # The Free plan is looked up as the single plan with tier FREE, so there can only be one
    free_in_file = [item["name"] for item in parsed if item["values"].get("tier") == PlanTier.FREE]
    if free_in_file:
        other_free = await db.scalar(
            select(SubscriptionPlan.name).where(
                SubscriptionPlan.tier == PlanTier.FREE, SubscriptionPlan.name.not_in(free_in_file)
            )
        )
        if len(free_in_file) > 1 or other_free:
            raise PlanConfigError("only one plan can have tier FREE")

    outcome: dict[str, str] = {}
    for item in parsed:
        plan = existing[item["name"]]
        if plan:
            for column, value in item["values"].items():
                setattr(plan, column, value)
            outcome[item["name"]] = "updated"
        else:
            db.add(SubscriptionPlan(name=item["name"], **{**_CREATE_DEFAULTS, **item["values"]}))
            outcome[item["name"]] = "created"
    await db.commit()
    return outcome
