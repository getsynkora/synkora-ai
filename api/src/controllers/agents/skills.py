"""
Agent Skills API endpoints.

Provides REST API endpoints for managing agent skills.
"""

import io
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.controllers.agents.models import AgentResponse
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent

logger = logging.getLogger(__name__)

# Create router
agents_skills_router = APIRouter()


class AddSkillRequest(BaseModel):
    """Request model for adding a pre-defined skill."""

    skill_id: str
    skill_name: str
    skill_category: str


@agents_skills_router.post("/{agent_slug}/skills/add", response_model=AgentResponse)
async def add_predefined_skill(
    agent_slug: str,
    request: AddSkillRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Add a pre-defined skill to an agent.

    Fetches skill content from S3 and adds to agent's context files.

    Args:
        agent_name: Name of the agent
        request: Skill details (skill_id, skill_name, skill_category)
        db: Database session

    Returns:
        Upload confirmation with file details
    """
    try:
        from botocore.exceptions import ClientError

        from src.services.agents.context_file_processor import AgentContextFileProcessor
        from src.services.storage.s3_storage import S3StorageService

        # Get agent from database
        result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")

        skill_id = request.skill_id
        skill_category = request.skill_category

        # Fetch skill content from S3 — reuse the same bucket/credentials/region
        # config as the rest of the app (AWS_S3_BUCKET) instead of a separate,
        # never-provisioned SKILLS_S3_BUCKET bucket.
        s3_service = S3StorageService()
        skills_bucket = s3_service.bucket_name
        s3_key = f"claude-skills/{skill_category}/{skill_id}/SKILL.md"

        logger.info(f"Fetching skill from S3: s3://{skills_bucket}/{s3_key}")

        try:
            response = s3_service.s3_client.get_object(Bucket=skills_bucket, Key=s3_key)
            skill_content = response["Body"].read().decode("utf-8")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Skill '{skill_id}' not found in S3")
            logger.warning(f"S3 error fetching skill: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch skill from S3: {error_code}"
            )

        if not skill_content or len(skill_content.strip()) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Skill content is empty")

        # Create a file-like object for the processor
        file_content = skill_content.encode("utf-8")
        file_obj = io.BytesIO(file_content)

        # Generate filename
        filename = f"skill-{skill_id}.md"

        # Initialize processor and process file
        processor = AgentContextFileProcessor(db)
        context_file = await processor.process_file(
            agent=agent, file=file_obj, filename=filename, content_type="text/markdown"
        )

        return AgentResponse(
            success=True,
            message=f"Skill '{request.skill_name}' added successfully",
            data={
                "file_id": str(context_file.id),
                "filename": context_file.filename,
                "file_size": context_file.file_size,
                "extraction_status": context_file.extraction_status,
                "skill_id": skill_id,
                "skill_name": request.skill_name,
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add skill: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add skill")
