"""
Backfill script: generate slugs for all existing agents.

Usage:
    python generate_agent_slugs.py

Logic:
- Load all agents ordered by created_at ASC
- For each agent: base = slugify(agent_name)
- If base is already taken globally, append first 4 chars of agent.id
- Update agent.slug
- Commit in batches of 100
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))


def slugify(name: str) -> str:
    """Convert agent_name to a URL-safe slug."""
    slug = re.sub(r"[^a-z0-9-]", "-", name.lower())
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def main():
    import asyncio

    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from src.config.settings import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.sqlalchemy_async_database_uri, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def run():
        from src.models.agent import Agent

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Agent).order_by(Agent.created_at.asc()))
            agents = list(result.scalars().all())

        print(f"Found {len(agents)} agents to process.")

        taken: set[str] = set()
        updates: list[tuple[str, str]] = []  # (agent_id, slug)

        for agent in agents:
            base = slugify(agent.agent_name)
            if not base:
                base = "agent"

            slug = base
            if slug in taken:
                suffix = str(agent.id).replace("-", "")[:4]
                slug = f"{base}-{suffix}"
                # If still taken, keep appending more chars
                extra = 4
                while slug in taken and extra < 32:
                    extra += 4
                    slug = f"{base}-{str(agent.id).replace('-', '')[:extra]}"

            taken.add(slug)
            updates.append((str(agent.id), slug))

        # Commit in batches of 100
        BATCH_SIZE = 100
        total_updated = 0

        async with AsyncSessionLocal() as session:
            for i in range(0, len(updates), BATCH_SIZE):
                batch = updates[i : i + BATCH_SIZE]
                for agent_id, slug in batch:
                    await session.execute(
                        text("UPDATE agents SET slug = :slug WHERE id = :id"),
                        {"slug": slug, "id": agent_id},
                    )
                await session.commit()
                total_updated += len(batch)
                print(f"  Committed batch {i // BATCH_SIZE + 1}: {total_updated}/{len(updates)} agents")

        print(f"\nDone. Updated {total_updated} agents with slugs.")

    asyncio.run(run())


if __name__ == "__main__":
    main()
