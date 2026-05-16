"""
File management endpoints.

Provides REST API endpoints for general file operations.

SECURITY: All file uploads are validated using FileSecurityService
which performs magic byte validation and malicious content scanning.
"""

import logging
import os
import re
import uuid
from urllib.parse import unquote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.controllers.agents.models import AgentResponse
from src.core.database import get_async_db
from src.core.errors import safe_error_message
from src.middleware.auth_middleware import get_current_tenant_id
from src.models.agent import Agent
from src.services.security.file_security import FileSecurityService, ScannerUnavailableError
from src.services.storage.s3_storage import S3StorageService

# SECURITY: Global file security service instance
file_security = FileSecurityService()

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize a filename to prevent path traversal and other security issues.

    Args:
        filename: Original filename from user input
        max_length: Maximum allowed filename length

    Returns:
        Sanitized filename safe for storage

    Security measures:
    - Removes path separators to prevent directory traversal
    - Removes null bytes
    - Removes control characters
    - Limits filename length
    - Preserves only safe characters
    """
    if not filename:
        return f"unnamed_{uuid.uuid4().hex[:8]}"

    # Get just the filename part, removing any path components
    filename = os.path.basename(filename)

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove control characters (ASCII 0-31 except common whitespace)
    filename = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", filename)

    # Remove/replace dangerous characters
    # Keep alphanumeric, dots, hyphens, underscores, and spaces
    filename = re.sub(r"[^\w\s.\-]", "_", filename)

    # Remove leading/trailing dots and spaces
    filename = filename.strip(". ")

    # Replace multiple consecutive dots with single dot (prevent ../ tricks)
    filename = re.sub(r"\.{2,}", ".", filename)

    # Replace multiple consecutive underscores/spaces with single underscore
    filename = re.sub(r"[\s_]+", "_", filename)

    # Limit filename length
    if len(filename) > max_length:
        # Preserve extension if present
        name, ext = os.path.splitext(filename)
        if ext:
            max_name_length = max_length - len(ext)
            filename = name[:max_name_length] + ext
        else:
            filename = filename[:max_length]

    # If filename is now empty or just extension, generate a safe name
    if not filename or filename.startswith("."):
        filename = f"file_{uuid.uuid4().hex[:8]}{filename}"

    return filename


# Create router
files_router = APIRouter()


@files_router.post("/upload", response_model=AgentResponse)
async def upload_file(
    file: UploadFile = File(...),
    agent_slug: str | None = Form(None),
    entity_type: str | None = Form(None),
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Upload a file to S3 and optionally update entity (like agent avatar).

    Args:
        file: File to upload
        agent_slug: Optional agent slug to update avatar for
        entity_type: Optional entity type (e.g., "agent_avatar")
        tenant_id: Tenant ID
        db: Database session

    Returns:
        File upload result
    """
    try:
        # Initialize S3 storage
        storage_service = S3StorageService()

        # Read file content
        content = await file.read()

        # SECURITY: Comprehensive file validation using FileSecurityService
        # This includes magic byte validation, malicious content scanning, and size limits
        category = "avatar" if entity_type == "agent_avatar" else "default"
        try:
            validation_result = file_security.validate_file(
                file_content=content,
                filename=file.filename or "unnamed",
                category=category,
            )
        except ScannerUnavailableError as scan_err:
            logger.error(f"File scanning service unavailable: {scan_err}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File scanning service unavailable. Please try again later.",
            )

        if not validation_result["is_valid"]:
            error_details = "; ".join(validation_result["errors"])
            logger.warning(f"File validation failed for upload from tenant {tenant_id}: {error_details}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {error_details}",
            )

        # Log any warnings
        if validation_result["warnings"]:
            logger.info(f"File upload warnings: {validation_result['warnings']}")

        # Validate file for avatar uploads (additional content-type check)
        if entity_type == "agent_avatar":
            if not file.content_type or not file.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Only image files are allowed for avatar upload"
                )

            # Validate file size (5MB limit) - redundant with FileSecurityService but explicit
            if len(content) > 5 * 1024 * 1024:  # 5MB
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Avatar file size must be less than 5MB"
                )

        # Determine source type based on entity type
        source_type = "uploads"
        if entity_type == "agent_avatar":
            source_type = "agent-avatars"
            if agent_slug:
                # Include agent slug in filename for avatars
                original_filename = file.filename or "avatar.jpg"
                # SECURITY: Sanitize the original filename
                safe_original = sanitize_filename(original_filename)
                file_extension = safe_original.split(".")[-1] if "." in safe_original else "jpg"
                # SECURITY: Also sanitize agent_slug as it comes from user input
                safe_agent_slug = sanitize_filename(agent_slug).replace(".", "_")
                filename = f"{safe_agent_slug}_avatar.{file_extension}"
            else:
                # SECURITY: Sanitize user-provided filename
                filename = sanitize_filename(file.filename)
        else:
            # SECURITY: Sanitize user-provided filename
            filename = sanitize_filename(file.filename)

        # Generate key
        key = storage_service.generate_key(tenant_id=tenant_id, source_type=source_type, filename=filename)

        # Upload file
        result = storage_service.upload_file(file_content=content, key=key, content_type=file.content_type)

        # Generate a presigned URL for browser access (24 hours expiration)
        presigned_url = storage_service.generate_presigned_url(
            key=result["url"],  # Pass the S3 URI
            expiration=86400,  # 24 hours
        )

        # Update result with the HTTP URL
        result["http_url"] = presigned_url

        # Update entity if specified
        updated_entity = None
        if entity_type == "agent_avatar" and agent_slug:
            # Decode URL-encoded agent slug
            decoded_agent_slug = unquote(agent_slug)

            # Update agent avatar
            agent_result = await db.execute(
                select(Agent).filter(Agent.slug == decoded_agent_slug, Agent.tenant_id == tenant_id)
            )
            db_agent = agent_result.scalar_one_or_none()

            if not db_agent:
                # Still return success for file upload but note agent not found
                return AgentResponse(
                    success=True,
                    message="File uploaded successfully, but agent not found for avatar update",
                    data={
                        "url": result["url"],
                        "key": result["key"],
                        "filename": file.filename,
                        "content_type": file.content_type,
                        "warning": f"Agent '{agent_slug}' not found - avatar not updated",
                    },
                )

            # Store old avatar for reference
            old_avatar = db_agent.avatar

            # Update avatar with S3 URI (not presigned URL) for permanent storage
            # The presigned URL will be generated on-demand when retrieving the agent
            db_agent.avatar = result["url"]  # S3 URI format: s3://bucket/key
            await db.commit()
            await db.refresh(db_agent)

            updated_entity = {
                "type": "agent",
                "name": decoded_agent_slug,
                "field_updated": "avatar",
                "previous_value": old_avatar,
                "new_value": result["url"],  # S3 URI
            }

        response_data = {
            "url": presigned_url,  # Temporary presigned URL for immediate display
            "s3_uri": result["url"],  # S3 URI to store in database - THIS is what should be saved!
            "key": result["key"],
            "filename": file.filename,
            "content_type": file.content_type,
        }

        if updated_entity:
            response_data["updated_entity"] = updated_entity

        message = "File uploaded successfully"
        if entity_type == "agent_avatar" and agent_slug and updated_entity:
            message = f"Avatar uploaded and updated successfully for agent '{agent_slug}'"

        return AgentResponse(success=True, message=message, data=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=safe_error_message(e, "Failed to upload file", include_type=True),
        )
