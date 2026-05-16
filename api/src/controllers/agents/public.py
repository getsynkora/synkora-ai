"""
Agent API endpoints.

Provides REST API endpoints for managing and executing Google Agent SDK agents.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.controllers.agents.models import AgentResponse
from src.core.database import get_async_db
from src.models.agent import Agent
from src.models.agent_pricing import AgentPricing
from src.models.agent_public_profile import AgentPublicProfile
from src.services.agents.agent_manager import AgentManager
from src.services.storage.s3_storage import S3StorageService

logger = logging.getLogger(__name__)

# Create router
agents_public_router = APIRouter()

# Global agent manager instance
agent_manager = AgentManager()


def get_avatar_url(avatar: str | None) -> str | None:
    """
    Convert S3 avatar path to presigned URL.

    Args:
        avatar: S3 key or URL

    Returns:
        Presigned URL or None if no avatar
    """
    if not avatar:
        return None

    # If it's already an HTTP URL, return as-is
    if avatar.startswith(("http://", "https://")):
        return avatar

    # If it's an S3 key or s3:// URI, generate presigned URL
    if avatar.startswith("s3://") or "/" in avatar:
        try:
            s3_service = S3StorageService()
            # Generate presigned URL valid for 7 days
            return s3_service.generate_presigned_url(avatar, expiration=86400 * 7)
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for avatar: {e}")
            return None

    return avatar


# Public Agents Endpoints


@agents_public_router.get("/public", response_model=AgentResponse)
async def list_public_agents(
    category: str | None = None,
    search: str | None = None,
    sort_by: str = "popular",
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all public agents available in the marketplace.

    Args:
        category: Filter by category
        search: Search query for name/description
        sort_by: Sort order (popular, recent, name, rating)
        limit: Maximum number of agents to return
        offset: Offset for pagination
        db: Database session

    Returns:
        List of public agents with stats
    """
    try:
        from sqlalchemy import asc, desc, or_

        # Base query for public agents
        query = select(Agent).where(Agent.is_public)

        # Apply filters
        if category:
            query = query.filter(Agent.category == category)

        if search:
            search_term = f"%{search}%"
            query = query.filter(or_(Agent.agent_name.ilike(search_term), Agent.description.ilike(search_term)))

        # Apply sorting
        if sort_by == "popular":
            query = query.order_by(desc(Agent.usage_count))
        elif sort_by == "recent":
            query = query.order_by(desc(Agent.created_at))
        elif sort_by == "name":
            query = query.order_by(asc(Agent.agent_name))
        elif sort_by == "rating":
            # Sort by likes_count - dislikes_count
            query = query.order_by(desc(Agent.likes_count - Agent.dislikes_count))

        # Get total count before pagination
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total_count = count_result.scalar()

        # Apply pagination
        result = await db.execute(query.limit(limit).offset(offset))
        agents = result.scalars().all()

        # Fetch published slugs for all agents in one query
        agent_ids = [a.id for a in agents]
        slug_result = await db.execute(
            select(AgentPublicProfile.agent_id, AgentPublicProfile.slug).where(
                AgentPublicProfile.agent_id.in_(agent_ids),
                AgentPublicProfile.is_published.is_(True),
            )
        )
        slug_map = {row.agent_id: row.slug for row in slug_result}

        # Fetch pricing for all agents in one query
        pricing_result = await db.execute(
            select(AgentPricing).where(AgentPricing.agent_id.in_(agent_ids), AgentPricing.is_active.is_(True))
        )
        pricing_map = {p.agent_id: p for p in pricing_result.scalars().all()}

        # Build response
        agents_list = []
        for agent in agents:
            pricing = pricing_map.get(agent.id)
            pricing_data = None
            if pricing:
                pricing_data = {
                    "model": pricing.pricing_model,
                    "is_free": pricing.pricing_model == "FREE",
                    "credits_per_use": pricing.credits_per_use,
                    "session_credits": pricing.session_credits,
                    "daily_credits": pricing.daily_credits,
                    "weekly_credits": pricing.weekly_credits,
                    "monthly_credits": pricing.monthly_subscription_credits,
                    "trial_messages": pricing.trial_messages or 0,
                }
            agents_list.append(
                {
                    "id": str(agent.id),
                    "agent_name": agent.agent_name,
                    "slug": slug_map.get(agent.id),
                    "description": agent.description,
                    "avatar": get_avatar_url(agent.avatar),
                    "category": agent.category,
                    "tags": agent.tags or [],
                    "likes_count": agent.likes_count,
                    "dislikes_count": agent.dislikes_count,
                    "usage_count": agent.usage_count,
                    "model_name": agent.llm_config.get("model", "Unknown Model"),
                    "provider": agent.llm_config.get("provider", "Unknown"),
                    "created_at": agent.created_at.isoformat(),
                    "pricing": pricing_data,
                }
            )

        return AgentResponse(
            success=True,
            message=f"Found {len(agents_list)} public agents",
            data={"agents": agents_list, "total": total_count, "limit": limit, "offset": offset},
        )

    except Exception as e:
        logger.error(f"Failed to list public agents: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list public agents")


@agents_public_router.get("/public/{agent_id}", response_model=AgentResponse)
async def get_public_agent_details(agent_id: str, user_id: str | None = None, db: AsyncSession = Depends(get_async_db)):
    """
    Get detailed information about a public agent.

    Args:
        agent_id: UUID of the agent
        user_id: Optional user ID to check if user has rated
        db: Database session

    Returns:
        Agent details with tools, capabilities, and user rating
    """
    try:
        from src.models.agent_rating import AgentRating
        from src.models.agent_tool import AgentTool

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # Get agent
        result = await db.execute(select(Agent).where(Agent.id == agent_uuid, Agent.is_public))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Public agent with ID '{agent_id}' not found"
            )

        # Get agent tools
        result = await db.execute(select(AgentTool).filter(AgentTool.agent_id == agent_uuid, AgentTool.enabled))
        agent_tools = result.scalars().all()

        tools_list = [
            {"name": tool.tool_name, "description": tool.config.get("description", "")} for tool in agent_tools
        ]

        # Get user's rating if user_id provided
        user_rating = None
        if user_id:
            result = await db.execute(
                select(AgentRating).filter(AgentRating.agent_id == agent_uuid, AgentRating.user_id == user_id)
            )
            rating = result.scalar_one_or_none()
            if rating:
                user_rating = rating.rating

        # Increment usage count
        agent.usage_count += 1
        await db.commit()

        return AgentResponse(
            success=True,
            message="Agent details retrieved",
            data={
                "id": str(agent.id),
                "agent_name": agent.agent_name,
                "description": agent.description,
                "avatar": get_avatar_url(agent.avatar),
                "system_prompt": agent.system_prompt,
                "category": agent.category,
                "tags": agent.tags or [],
                "likes_count": agent.likes_count,
                "dislikes_count": agent.dislikes_count,
                "usage_count": agent.usage_count,
                "model_name": agent.llm_config.get("model", "Unknown Model"),
                "provider": agent.llm_config.get("provider", "Unknown"),
                "tools": tools_list,
                "user_rating": user_rating,
                "allow_subscriptions": agent.allow_subscriptions,
                "created_at": agent.created_at.isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get public agent details: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get agent details")


class RateAgentRequest(BaseModel):
    """Request model for rating an agent."""

    rating: str = Field(..., description="Rating: 'like' or 'dislike'")
    user_id: str = Field(..., description="User identifier (email, session ID, or UUID)")


@agents_public_router.post("/public/{agent_id}/rate", response_model=AgentResponse)
async def rate_agent(agent_id: str, request: RateAgentRequest, db: AsyncSession = Depends(get_async_db)):
    """
    Rate a public agent (like or dislike).

    Args:
        agent_id: UUID of the agent
        request: Rating request
        db: Database session

    Returns:
        Updated rating counts
    """
    try:
        from src.models.agent_rating import AgentRating

        # Validate rating value
        if request.rating not in ["like", "dislike"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rating must be 'like' or 'dislike'")

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # Get agent
        result = await db.execute(select(Agent).where(Agent.id == agent_uuid, Agent.is_public))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Public agent with ID '{agent_id}' not found"
            )

        # Check if user has already rated
        result = await db.execute(
            select(AgentRating).filter(AgentRating.agent_id == agent_uuid, AgentRating.user_id == request.user_id)
        )
        existing_rating = result.scalar_one_or_none()

        if existing_rating:
            # Update existing rating
            old_rating = existing_rating.rating

            # Decrement old rating count
            if old_rating == "like":
                agent.likes_count = max(0, agent.likes_count - 1)
            else:
                agent.dislikes_count = max(0, agent.dislikes_count - 1)

            # Update rating
            existing_rating.rating = request.rating

            # Increment new rating count
            if request.rating == "like":
                agent.likes_count += 1
            else:
                agent.dislikes_count += 1

            message = "Rating updated successfully"
        else:
            # Create new rating
            new_rating = AgentRating(agent_id=agent_uuid, user_id=request.user_id, rating=request.rating)
            db.add(new_rating)

            # Increment rating count
            if request.rating == "like":
                agent.likes_count += 1
            else:
                agent.dislikes_count += 1

            message = "Rating added successfully"

        await db.commit()
        await db.refresh(agent)

        return AgentResponse(
            success=True,
            message=message,
            data={
                "agent_id": str(agent.id),
                "likes_count": agent.likes_count,
                "dislikes_count": agent.dislikes_count,
                "user_rating": request.rating,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to rate agent: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to rate agent")


@agents_public_router.delete("/public/{agent_id}/rate", response_model=AgentResponse)
async def remove_agent_rating(agent_id: str, user_id: str, db: AsyncSession = Depends(get_async_db)):
    """
    Remove a user's rating from an agent.

    Args:
        agent_id: UUID of the agent
        user_id: User identifier
        db: Database session

    Returns:
        Updated rating counts
    """
    try:
        from src.models.agent_rating import AgentRating

        # Convert string to UUID
        try:
            agent_uuid = uuid.UUID(agent_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid agent ID format")

        # Get agent
        result = await db.execute(select(Agent).where(Agent.id == agent_uuid, Agent.is_public))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Public agent with ID '{agent_id}' not found"
            )

        # Find and delete rating
        result = await db.execute(
            select(AgentRating).filter(AgentRating.agent_id == agent_uuid, AgentRating.user_id == user_id)
        )
        rating = result.scalar_one_or_none()

        if not rating:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")

        # Decrement rating count
        if rating.rating == "like":
            agent.likes_count = max(0, agent.likes_count - 1)
        else:
            agent.dislikes_count = max(0, agent.dislikes_count - 1)

        await db.delete(rating)
        await db.commit()
        await db.refresh(agent)

        return AgentResponse(
            success=True,
            message="Rating removed successfully",
            data={"agent_id": str(agent.id), "likes_count": agent.likes_count, "dislikes_count": agent.dislikes_count},
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to remove rating: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to remove rating")
