#!/usr/bin/env python3
"""
Let a tenant create and manage customer tenants through the API (platform operator tool).

Usage:
    python enable_tenant_provisioning.py <tenant_id>                       # enable
    python enable_tenant_provisioning.py <tenant_id> --agent <agent_id>    # enable and print a manager API key
    python enable_tenant_provisioning.py <tenant_id> --disable

The manager key has the tenants:manage, billing:read and webhooks:manage permissions. It is printed once; store it.
See api/src/controllers/agent_api_provisioning.py for the endpoints it unlocks.
"""

import argparse
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from sqlalchemy import select

from src.core.database import get_async_session_factory
from src.models.agent import Agent
from src.models.agent_api_key import AgentApiKey
from src.models.tenant import Tenant
from src.services.agent_api.api_key_service import AgentApiKeyService


async def main(tenant_id: uuid.UUID, agent_id: uuid.UUID | None, disable: bool) -> int:
    async with get_async_session_factory()() as db:
        tenant = await db.get(Tenant, tenant_id)
        if tenant is None:
            print(f"Tenant {tenant_id} not found")
            return 1

        tenant.can_manage_tenants = not disable
        if disable:
            # Switch off the tenant's management keys too, so re-enabling later does not silently revive them
            keys = (
                (
                    await db.execute(
                        select(AgentApiKey).where(
                            AgentApiKey.tenant_id == tenant_id,
                            AgentApiKey.is_active.is_(True),
                            AgentApiKey.permissions.any("tenants:manage"),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for key in keys:
                key.is_active = False
            print(f"Deactivated {len(keys)} tenant-management key(s)")
        await db.commit()
        print(f"{'Disabled' if disable else 'Enabled'} tenant management for {tenant.name} ({tenant.id})")

        if agent_id and not disable:
            agent = await db.scalar(select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id))
            if agent is None:
                print(f"Agent {agent_id} not found in this tenant")
                return 1
            _, plain = await AgentApiKeyService.create_api_key(
                db=db,
                agent_id=agent.id,
                tenant_id=tenant.id,
                name="Tenant management",
                permissions=["tenants:manage", "billing:read", "webhooks:manage"],
            )
            print(f"Manager API key (shown once): {plain}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tenant_id", type=uuid.UUID)
    parser.add_argument("--agent", type=uuid.UUID, help="create a manager key attached to this agent of the tenant")
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.tenant_id, args.agent, args.disable)))
