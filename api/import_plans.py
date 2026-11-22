#!/usr/bin/env python3
"""
Create or update subscription plans (with quota pools) from a JSON file.

Usage:
    python import_plans.py examples/quota_plans.example.json
    python import_plans.py my_plans.json --dry-run     # validate only

Plans are matched by name. Existing plans are updated; subscribers keep their plan.
"""

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.core.database import get_async_session_factory
from src.services.billing.plan_import import PlanConfigError, _parse_plan, import_plans


async def main(path: str, dry_run: bool) -> int:
    with open(path) as fh:
        plans = json.load(fh)

    if dry_run:
        try:
            for plan in plans:
                _parse_plan(plan)
        except PlanConfigError as err:
            print(f"Invalid: {err}")
            return 1
        print(f"OK: {len(plans)} plan(s) are valid. Nothing was written.")
        return 0

    async with get_async_session_factory()() as db:
        try:
            outcome = await import_plans(db, plans)
        except PlanConfigError as err:
            print(f"Invalid: {err}")
            return 1
    for name, state in outcome.items():
        print(f"{state}: {name}")

    # The public plan list is cached; drop it so changes show at once
    try:
        from src.config.redis import get_redis_async

        redis = get_redis_async()
        if redis:
            await redis.delete("billing:plans")
    except Exception as err:
        print(f"Note: could not clear the cached plan list ({type(err).__name__}); it refreshes within an hour")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="JSON file containing a list of plans")
    parser.add_argument("--dry-run", action="store_true", help="validate the file without writing")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.path, args.dry_run)))
