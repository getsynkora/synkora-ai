"""
Agent API endpoints.

Provides REST API endpoints for managing and executing Google Agent SDK agents.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.controllers.agents.models import AgentResponse
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.services.agents.agent_manager import AgentManager
from src.services.security.file_security import FileSecurityService

logger = logging.getLogger(__name__)

# Create router
agents_context_files_router = APIRouter()

# Global agent manager instance
agent_manager = AgentManager()

# SECURITY: Global file security service instance for magic byte validation
file_security = FileSecurityService()


# Agent Context Files Management Endpoints


# Maximum file upload size (50MB)
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024
# Allowed file extensions for context files
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".csv", ".json", ".xml", ".html", ".htm"}


@agents_context_files_router.post("/{agent_slug}/context-files/upload", response_model=AgentResponse)
async def upload_context_file(
    agent_slug: str,
    file: UploadFile = File(...),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Upload a context file for an agent.

    Args:
        agent_name: Name of the agent
        file: File to upload (max 50MB, allowed types: txt, md, pdf, docx, csv, json, xml, html)
        db: Database session

    Returns:
        Upload confirmation with file details
    """
    try:
        import os

        from src.services.agents.context_file_processor import AgentContextFileProcessor

        # SECURITY: Validate file extension
        if file.filename:
            _, ext = os.path.splitext(file.filename.lower())
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File type '{ext}' not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
                )

        # SECURITY: Validate file size by reading content
        # Read file content to check size (this also allows re-reading later)
        file_content = await file.read()
        file_size = len(file_content)

        if file_size > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds maximum allowed size ({MAX_UPLOAD_SIZE_BYTES / 1024 / 1024:.0f}MB)",
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty files are not allowed",
            )

        # SECURITY: Comprehensive file validation using FileSecurityService
        # This includes magic byte validation and malicious content scanning
        validation_result = file_security.validate_file(
            file_content=file_content,
            filename=file.filename or "unnamed",
            category="document",  # Use document category for context files
        )

        if not validation_result["is_valid"]:
            error_details = "; ".join(validation_result["errors"])
            logger.warning(f"Context file validation failed for upload from tenant {tenant_id}: {error_details}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {error_details}",
            )

        # Log any warnings
        if validation_result["warnings"]:
            logger.info(f"Context file upload warnings: {validation_result['warnings']}")

        # Reset file position for downstream processing
        await file.seek(0)

        # Get agent from database
        result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")

        # Initialize processor
        processor = AgentContextFileProcessor(db)

        # Process file
        context_file = await processor.process_file(
            agent=agent, file=file.file, filename=file.filename, content_type=file.content_type
        )

        return AgentResponse(
            success=True,
            message=f"File '{file.filename}' uploaded successfully",
            data={
                "file_id": str(context_file.id),
                "filename": context_file.filename,
                "file_size": context_file.file_size,
                "extraction_status": context_file.extraction_status,
            },
        )

    except ValueError as e:
        logger.warning(f"Invalid context file upload: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file or file format")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to upload context file: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload file")


@agents_context_files_router.get("/{agent_slug}/context-files", response_model=AgentResponse)
async def list_context_files(
    agent_slug: str, tenant_id: uuid.UUID = Depends(get_current_tenant_id), db: AsyncSession = Depends(get_async_db)
):
    """
    List all context files for an agent.

    Args:
        agent_name: Name of the agent
        db: Database session

    Returns:
        List of context files
    """
    try:
        from sqlalchemy import or_

        from src.models.agent_context_file import AgentContextFile

        # SECURITY: Single OR query to prevent timing attacks
        # Checks: (agent belongs to tenant) OR (agent is public)
        result = await db.execute(
            select(Agent).filter(Agent.slug == agent_slug, or_(Agent.tenant_id == tenant_id, Agent.is_public.is_(True)))
        )
        agent = result.scalar_one_or_none()

        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")

        # Get context files
        result = await db.execute(
            select(AgentContextFile)
            .filter(AgentContextFile.agent_id == agent.id)
            .order_by(AgentContextFile.display_order)
        )
        files = result.scalars().all()

        files_list = []
        for f in files:
            files_list.append(
                {
                    "id": str(f.id),
                    "filename": f.filename,
                    "file_type": f.file_type,
                    "file_size": f.file_size,
                    "extraction_status": f.extraction_status,
                    "extraction_error": f.extraction_error,
                    "display_order": f.display_order,
                    "created_at": f.created_at.isoformat(),
                    "updated_at": f.updated_at.isoformat(),
                }
            )

        return AgentResponse(success=True, message=f"Found {len(files_list)} context files", data={"files": files_list})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list context files: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list context files")


@agents_context_files_router.get("/context-files/{file_id}/download", response_model=AgentResponse)
async def download_context_file(
    file_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get download URL for a context file.

    Args:
        file_id: UUID of the context file
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Presigned download URL
    """
    try:
        from src.models.agent_context_file import AgentContextFile
        from src.services.agents.context_file_processor import AgentContextFileProcessor

        # Convert string to UUID
        try:
            file_uuid = uuid.UUID(file_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file ID format")

        # SECURITY: Single query with join to verify file exists AND belongs to tenant's agent
        # This prevents IDOR and timing attacks by doing ownership verification in one query
        result = await db.execute(
            select(AgentContextFile)
            .join(Agent, AgentContextFile.agent_id == Agent.id)
            .filter(AgentContextFile.id == file_uuid, Agent.tenant_id == tenant_id)
        )
        context_file = result.scalar_one_or_none()

        if not context_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Context file with ID '{file_id}' not found"
            )

        # Generate download URL
        processor = AgentContextFileProcessor(db)
        download_url = await processor.get_download_url(context_file)

        return AgentResponse(
            success=True,
            message="Download URL generated",
            data={
                "download_url": download_url,
                "filename": context_file.filename,
                "expires_in": 3600,  # 1 hour
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate download URL: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate download URL")


@agents_context_files_router.get("/context-files/{file_id}/content", response_model=AgentResponse)
async def get_context_file_content(
    file_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get the content of a context file.

    Args:
        file_id: UUID of the context file
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        File content
    """
    try:
        from src.models.agent_context_file import AgentContextFile
        from src.services.storage.s3_storage import S3StorageService

        # Convert string to UUID
        try:
            file_uuid = uuid.UUID(file_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file ID format")

        # SECURITY: Single query with join to verify file exists AND belongs to tenant's agent
        # This prevents IDOR and timing attacks by doing ownership verification in one query
        result = await db.execute(
            select(AgentContextFile)
            .join(Agent, AgentContextFile.agent_id == Agent.id)
            .filter(AgentContextFile.id == file_uuid, Agent.tenant_id == tenant_id)
        )
        context_file = result.scalar_one_or_none()

        if not context_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Context file with ID '{file_id}' not found"
            )

        # Fetch content from S3
        s3_storage = S3StorageService()
        content = s3_storage.download_file(context_file.s3_key)

        return AgentResponse(
            success=True,
            message="File content retrieved",
            data={
                "file_id": str(context_file.id),
                "filename": context_file.filename,
                "content": content.decode("utf-8") if isinstance(content, bytes) else content,
                "file_type": context_file.file_type,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get context file content: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get file content")


from pydantic import BaseModel


class UpdateContextFileRequest(BaseModel):
    """Request model for updating context file content."""

    content: str


# Allowed formats for editing (text-based formats)
EDITABLE_EXTENSIONS = {".md", ".txt", ".csv", ".docx"}


def is_file_editable(filename: str) -> bool:
    """Check if a file is editable (text formats: .md, .txt, .csv, .docx)."""
    lower_filename = filename.lower()
    return any(lower_filename.endswith(ext) for ext in EDITABLE_EXTENSIONS)


@agents_context_files_router.put("/context-files/{file_id}/content", response_model=AgentResponse)
async def update_context_file_content(
    file_id: str,
    request: UpdateContextFileRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Update the content of a context file.

    Only text formats (.md, .txt) can be edited.

    Args:
        file_id: UUID of the context file
        request: New content
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Update confirmation
    """
    try:
        from src.models.agent_context_file import AgentContextFile
        from src.services.storage.s3_storage import S3StorageService

        # Convert string to UUID
        try:
            file_uuid = uuid.UUID(file_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file ID format")

        # SECURITY: Single query with join to verify file exists AND belongs to tenant's agent
        # This prevents IDOR and timing attacks by doing ownership verification in one query
        result = await db.execute(
            select(AgentContextFile)
            .join(Agent, AgentContextFile.agent_id == Agent.id)
            .filter(AgentContextFile.id == file_uuid, Agent.tenant_id == tenant_id)
        )
        context_file = result.scalar_one_or_none()

        if not context_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Context file with ID '{file_id}' not found"
            )

        # Check if file is editable (only allowed formats)
        if not is_file_editable(context_file.filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only text formats (.md, .txt, .csv, .docx) can be edited",
            )

        # Update content in S3
        s3_storage = S3StorageService()
        new_content = request.content.encode("utf-8")

        s3_storage.upload_file(
            file_content=new_content, key=context_file.s3_key, content_type=context_file.file_type or "text/markdown"
        )

        # Update file size and extracted text in database
        context_file.file_size = len(new_content)
        context_file.extracted_text = request.content
        context_file.extraction_status = "COMPLETED"
        context_file.extraction_error = None

        await db.commit()

        return AgentResponse(
            success=True,
            message=f"File '{context_file.filename}' updated successfully",
            data={
                "file_id": str(context_file.id),
                "filename": context_file.filename,
                "file_size": context_file.file_size,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update context file content: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update file content")


@agents_context_files_router.delete("/context-files/{file_id}", response_model=AgentResponse)
async def delete_context_file(
    file_id: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Delete a context file.

    Args:
        file_id: UUID of the context file
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Deletion confirmation
    """
    try:
        from src.models.agent_context_file import AgentContextFile
        from src.services.agents.context_file_processor import AgentContextFileProcessor

        # Convert string to UUID
        try:
            file_uuid = uuid.UUID(file_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file ID format")

        # SECURITY: Single query with join to verify file exists AND belongs to tenant's agent
        # This prevents IDOR and timing attacks by doing ownership verification in one query
        result = await db.execute(
            select(AgentContextFile)
            .join(Agent, AgentContextFile.agent_id == Agent.id)
            .filter(AgentContextFile.id == file_uuid, Agent.tenant_id == tenant_id)
        )
        context_file = result.scalar_one_or_none()

        if not context_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Context file with ID '{file_id}' not found"
            )

        filename = context_file.filename

        # Delete file
        processor = AgentContextFileProcessor(db)
        await processor.delete_file(context_file)

        return AgentResponse(success=True, message=f"File '{filename}' deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete context file: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete file")
