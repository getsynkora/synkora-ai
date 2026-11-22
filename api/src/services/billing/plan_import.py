"""
Plan import - create or update subscription plans (including quota pools) from a config file.

The plan list lives in data, not code, so any product or industry can define its own pools::

    [{"name": "Growth", "price_monthly": 549, "quota_pools": [{"key": "support", "label": "...", "limit": 5000}]}]

See ``api/examples/quota_plans.example.json``.
"""

import re
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.subscription_plan import PlanTier, SubscriptionPlan

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
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise PlanConfigError(f"pool {key!r}: limit must be a whole number of 0 or more")
        label = pool.get("label") or key
        if not isinstance(label, str):
            raise PlanConfigError(f"pool {key!r}: label must be text")
        seen.add(key)
        clean.append({"key": key, "label": label, "limit": limit})
    return clean


def _parse_plan(raw: dict) -> dict:
    if not isinstance(raw, dict) or not raw.get("name"):
        raise PlanConfigError("each plan needs a name")
    name = raw["name"]
    try:
        tier = PlanTier[str(raw.get("tier", "STARTER")).upper()]
    except KeyError:
        raise PlanConfigError(f"plan {name!r}: tier must be one of {[t.name for t in PlanTier]}") from None
    if "price_monthly" not in raw:
        raise PlanConfigError(f"plan {name!r}: price_monthly is required")

    values: dict[str, Any] = {
        "tier": tier,
        "price_monthly": Decimal(str(raw["price_monthly"])),
        "price_yearly": Decimal(str(raw["price_yearly"])) if raw.get("price_yearly") is not None else None,
        "credits_monthly": int(raw.get("credits_monthly", 0)),
        "credits_rollover": bool(raw.get("credits_rollover", False)),
        "is_active": bool(raw.get("is_active", True)),
        "quota_pools": validate_quota_pools(raw.get("quota_pools")) or None,
    }
    for column in _OPTIONAL_COLUMNS:
        if column in raw:
            values[column] = raw[column]
    return {"name": name, "values": values}


async def import_plans(db: AsyncSession, plans: list[dict]) -> dict[str, str]:
    """
    Create or update plans by name. Returns ``{plan name: "created" | "updated"}``.

    All plans are validated before any are written, so a bad entry changes nothing.
    """
    if not isinstance(plans, list) or not plans:
        raise PlanConfigError("the config must be a non-empty list of plans")
    parsed = [_parse_plan(p) for p in plans]
    names = [p["name"] for p in parsed]
    if len(set(names)) != len(names):
        raise PlanConfigError("plan names must be unique")

    outcome: dict[str, str] = {}
    for item in parsed:
        existing = (
            await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.name == item["name"]))
        ).scalar_one_or_none()
        if existing:
            for column, value in item["values"].items():
                setattr(existing, column, value)
            outcome[item["name"]] = "updated"
        else:
            db.add(SubscriptionPlan(name=item["name"], **item["values"]))
            outcome[item["name"]] = "created"
    await db.commit()
    return outcome
