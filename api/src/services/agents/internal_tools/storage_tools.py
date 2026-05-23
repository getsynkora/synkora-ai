"""
Storage Tools for Synkora Agents.

Wrapper tools that expose the existing S3StorageService to agents.
Allows agents to upload, download, and manage files in S3 storage.
"""

import logging
import os
from datetime import UTC, datetime
from typing import Any

from src.services.storage.s3_storage import get_s3_storage

from .git_helpers import async_makedirs, async_path_exists, async_read_file_bytes, async_write_file_bytes

logger = logging.getLogger(__name__)


def _get_workspace_path(config: dict[str, Any] | None, runtime_context: Any = None) -> str | None:
    """Get the workspace path from config or RuntimeContext (including Celery task fallback)."""
    import uuid as _uuid

    from src.services.agents.workspace_manager import get_workspace_path_from_config

    path = get_workspace_path_from_config(config)
    if path:
        return path

    # Fallback: create workspace directly from runtime_context when ContextVar isn't propagated
    rc = runtime_context or (config.get("_runtime_context") if config else None)
    if rc and getattr(rc, "tenant_id", None):
        from src.services.agents.workspace_manager import get_workspace_manager

        tenant_id = rc.tenant_id
        conversation_id = getattr(rc, "conversation_id", None) or _uuid.uuid5(tenant_id, "background_tasks")
        return get_workspace_manager().get_or_create_workspace(tenant_id, conversation_id)

    return None


def _validate_path_in_workspace(path: str, workspace_path: str | None) -> tuple[bool, str | None]:
    """Validate that a path is within the workspace directory."""
    if not workspace_path:
        return False, "No workspace path configured. File operations require a valid workspace."

    try:
        real_workspace = os.path.realpath(workspace_path).removeprefix("/private")

        # Resolve relative paths against the workspace root so the LLM can pass
        # bare filenames like "output.csv" or subdirectory paths like "exports/output.csv".
        if not os.path.isabs(path):
            resolved = os.path.join(workspace_path, path)
        else:
            resolved = path

        real_path = os.path.realpath(resolved).removeprefix("/private")

        if not (real_path.startswith(real_workspace + os.sep) or real_path == real_workspace):
            return False, (
                f"Path '{path}' is outside the workspace directory. "
                f"Use a relative filename (e.g. 'output.csv') or a path under '{workspace_path}'."
            )

        return True, None
    except Exception as e:
        return False, f"Error validating path: {str(e)}"


async def internal_s3_upload_file(
    file_path: str,
    s3_key: str | None = None,
    content_type: str | None = None,
    metadata: dict[str, str] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Upload a file to S3 storage.
    IMPORTANT: file_path must be within the workspace directory.

    Args:
        file_path: Path to the local file to upload (must be within workspace)
        s3_key: S3 object key (defaults to filename if not provided)
        content_type: MIME type of the file
        metadata: Additional metadata to attach to the object
        config: Configuration dictionary
        runtime_context: Runtime context

    Returns:
        Dictionary with upload result including S3 URL and presigned URL
    """
    try:
        # Validate file_path is within workspace
        workspace_path = _get_workspace_path(config, runtime_context)
        is_valid, error = _validate_path_in_workspace(file_path, workspace_path)
        if not is_valid:
            return {"error": error}

        # Resolve relative paths against workspace root
        if workspace_path and not os.path.isabs(file_path):
            file_path = os.path.join(workspace_path, file_path)

        if not await async_path_exists(file_path, config):
            return {"error": f"File not found: {file_path}"}

        # Read file content (routes through sandbox when remote)
        file_content = await async_read_file_bytes(file_path, config)
        if file_content is None:
            return {"error": f"Failed to read file: {file_path}"}

        # Default s3_key to filename
        if not s3_key:
            s3_key = os.path.basename(file_path)

        # Initialize S3 service
        s3_service = get_s3_storage()

        # Upload file
        result = s3_service.upload_file(
            file_content=file_content, key=s3_key, content_type=content_type, metadata=metadata
        )

        # Generate presigned URL for 7 days
        presigned_url = s3_service.generate_presigned_url(
            key=s3_key,
            expiration=86400 * 7,  # 7 days
        )

        logger.info(f"Uploaded {file_path} to S3: {s3_key}")

        return {
            "success": True,
            "s3_key": result["key"],
            "s3_uri": result["url"],
            "presigned_url": presigned_url,
            "bucket": result["bucket"],
            "size": len(file_content),
        }

    except Exception as e:
        logger.error(f"Error uploading file to S3: {e}", exc_info=True)
        return {"error": f"Failed to upload to S3: {str(e)}"}


async def internal_s3_upload_directory(
    directory_path: str,
    base_prefix: str,
    tenant_id: str | None = None,
    metadata: dict[str, str] | None = None,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Upload an entire directory to S3 storage.

    Useful for uploading tutorial directories with multiple chapters.
    IMPORTANT: directory_path must be within the workspace directory.

    Args:
        directory_path: Path to the local directory to upload (must be within workspace)
        base_prefix: Base S3 prefix/path for uploaded files
        tenant_id: Optional tenant ID for organizing files
        metadata: Common metadata to attach to all files
        config: Configuration dictionary
        runtime_context: Runtime context

    Returns:
        Dictionary with upload results for all files
    """
    try:
        # Validate directory_path is within workspace
        workspace_path = _get_workspace_path(config, runtime_context)
        is_valid, error = _validate_path_in_workspace(directory_path, workspace_path)
        if not is_valid:
            return {"error": error}

        if not await async_path_exists(directory_path, config):
            return {"error": f"Directory not found: {directory_path}"}

        # Initialize S3 service
        s3_service = get_s3_storage()

        # Prepare base prefix
        if tenant_id:
            base_prefix = f"tenants/{tenant_id}/{base_prefix.strip('/')}"

        uploaded_files = []
        failed_files = []

        from src.services.compute.resolver import get_compute_session_from_config

        _cs = await get_compute_session_from_config(config)

        if _cs is not None and _cs.is_remote:
            # Remote: enumerate files via find, read each via compute session
            find_r = await _cs.exec_command(["find", directory_path, "-type", "f"])
            all_files = [f for f in find_r.get("output", "").splitlines() if f.strip()] if find_r.get("success") else []
        else:
            if not os.path.isdir(directory_path):
                return {"error": f"Path is not a directory: {directory_path}"}
            all_files = []
            for root, _dirs, files in os.walk(directory_path):
                for file in files:
                    all_files.append(os.path.join(root, file))

        for file_path in all_files:
            relative_path = os.path.relpath(file_path, directory_path)
            s3_key = f"{base_prefix}/{relative_path}"
            try:
                file_content = await async_read_file_bytes(file_path, config)
                if file_content is None:
                    raise ValueError(f"Could not read file: {file_path}")

                result = s3_service.upload_file(file_content=file_content, key=s3_key, metadata=metadata)
                presigned_url = s3_service.generate_presigned_url(key=s3_key, expiration=86400 * 7)
                uploaded_files.append(
                    {
                        "filename": relative_path,
                        "s3_key": s3_key,
                        "s3_uri": result["url"],
                        "presigned_url": presigned_url,
                        "size": len(file_content),
                    }
                )
                logger.info(f"Uploaded {relative_path} to S3")
            except Exception as e:
                logger.error(f"Failed to upload {relative_path}: {e}")
                failed_files.append({"filename": relative_path, "error": str(e)})

        if not uploaded_files:
            return {"error": "No files were uploaded successfully"}

        # Find index file URL
        index_url = None
        for file_info in uploaded_files:
            if file_info["filename"] == "index.md":
                index_url = file_info["presigned_url"]
                break

        logger.info(f"Directory upload complete: {len(uploaded_files)} files uploaded, {len(failed_files)} failed")

        return {
            "success": True,
            "base_prefix": base_prefix,
            "index_url": index_url,
            "uploaded_files": uploaded_files,
            "failed_files": failed_files,
            "total_uploaded": len(uploaded_files),
            "total_failed": len(failed_files),
        }

    except Exception as e:
        logger.error(f"Error uploading directory to S3: {e}", exc_info=True)
        return {"error": f"Failed to upload directory: {str(e)}"}


async def internal_s3_download_file(
    s3_key: str, output_path: str | None = None, config: dict[str, Any] | None = None, runtime_context: Any = None
) -> dict[str, Any]:
    """
    Download a file from S3 storage.
    IMPORTANT: output_path must be within the workspace directory.

    Args:
        s3_key: S3 object key or S3 URI (s3://bucket/key)
        output_path: Optional local path to save the file (must be within workspace)
        config: Configuration dictionary
        runtime_context: Runtime context

    Returns:
        Dictionary with download result and file content
    """
    try:
        # Validate output_path is within workspace if provided
        resolved_output_path = output_path
        if output_path:
            workspace_path = _get_workspace_path(config, runtime_context)
            is_valid, error = _validate_path_in_workspace(output_path, workspace_path)
            if not is_valid:
                return {"error": error}
            # Use the workspace-resolved absolute path for writing
            if workspace_path and not os.path.isabs(output_path):
                resolved_output_path = os.path.join(workspace_path, output_path)

        # Initialize S3 service
        s3_service = get_s3_storage()

        # Download file
        file_content = s3_service.download_file(s3_key)

        # Save to file if output path provided
        if resolved_output_path:
            parent_dir = os.path.dirname(resolved_output_path)
            if parent_dir:
                await async_makedirs(parent_dir, config)
            await async_write_file_bytes(resolved_output_path, file_content, config)
            logger.info(f"Downloaded S3 file to: {resolved_output_path}")

        return {
            "success": True,
            "s3_key": s3_key,
            "output_path": resolved_output_path,
            "size": len(file_content),
            "content": file_content.decode("utf-8") if resolved_output_path is None else None,
        }

    except Exception as e:
        logger.error(f"Error downloading from S3: {e}", exc_info=True)
        return {"error": f"Failed to download from S3: {str(e)}"}


async def internal_s3_generate_presigned_url(
    s3_key: str, expiration: int = 3600, config: dict[str, Any] | None = None, runtime_context: Any = None
) -> dict[str, Any]:
    """
    Generate a presigned URL for temporary access to an S3 object.

    Args:
        s3_key: S3 object key or S3 URI
        expiration: URL expiration time in seconds (default: 1 hour)
        config: Configuration dictionary
        runtime_context: Runtime context

    Returns:
        Dictionary with presigned URL and expiration info
    """
    try:
        # Initialize S3 service
        s3_service = get_s3_storage()

        # Generate presigned URL
        url = s3_service.generate_presigned_url(key=s3_key, expiration=expiration)

        from datetime import timedelta

        expires_at = datetime.now(UTC) + timedelta(seconds=expiration)

        return {
            "success": True,
            "presigned_url": url,
            "s3_key": s3_key,
            "expires_in": expiration,
            "expires_at": expires_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Error generating presigned URL: {e}", exc_info=True)
        return {"error": f"Failed to generate presigned URL: {str(e)}"}


async def internal_s3_list_files(
    prefix: str = "", max_keys: int = 1000, config: dict[str, Any] | None = None, runtime_context: Any = None
) -> dict[str, Any]:
    """
    List files in S3 with a given prefix.

    Args:
        prefix: Key prefix to filter by (e.g., "tutorials/project-name/")
        max_keys: Maximum number of keys to return
        config: Configuration dictionary
        runtime_context: Runtime context

    Returns:
        Dictionary with list of files and their metadata
    """
    try:
        # Initialize S3 service
        s3_service = get_s3_storage()

        # List files
        files = s3_service.list_files(prefix=prefix, max_keys=max_keys)

        return {"success": True, "prefix": prefix, "files": files, "total_files": len(files)}

    except Exception as e:
        logger.error(f"Error listing S3 files: {e}", exc_info=True)
        return {"error": f"Failed to list S3 files: {str(e)}"}


async def internal_s3_delete_file(
    s3_key: str, config: dict[str, Any] | None = None, runtime_context: Any = None
) -> dict[str, Any]:
    """
    Delete a file from S3 storage.

    Args:
        s3_key: S3 object key
        config: Configuration dictionary
        runtime_context: Runtime context

    Returns:
        Dictionary with deletion result
    """
    try:
        # Initialize S3 service
        s3_service = get_s3_storage()

        # Delete file
        s3_service.delete_file(s3_key)

        logger.info(f"Deleted S3 file: {s3_key}")

        return {"success": True, "s3_key": s3_key, "message": "File deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting S3 file: {e}", exc_info=True)
        return {"error": f"Failed to delete S3 file: {str(e)}"}


async def internal_s3_file_exists(
    s3_key: str, config: dict[str, Any] | None = None, runtime_context: Any = None
) -> dict[str, Any]:
    """
    Check if a file exists in S3 storage.

    Args:
        s3_key: S3 object key
        config: Configuration dictionary
        runtime_context: Runtime context

    Returns:
        Dictionary with existence result
    """
    try:
        # Initialize S3 service
        s3_service = get_s3_storage()

        # Check if file exists
        exists = s3_service.file_exists(s3_key)

        return {"success": True, "s3_key": s3_key, "exists": exists}

    except Exception as e:
        logger.error(f"Error checking S3 file existence: {e}", exc_info=True)
        return {"error": f"Failed to check S3 file: {str(e)}"}


async def internal_s3_get_file_metadata(
    s3_key: str, config: dict[str, Any] | None = None, runtime_context: Any = None
) -> dict[str, Any]:
    """
    Get metadata for a file in S3 storage.

    Args:
        s3_key: S3 object key
        config: Configuration dictionary
        runtime_context: Runtime context

    Returns:
        Dictionary with file metadata
    """
    try:
        # Initialize S3 service
        s3_service = get_s3_storage()

        # Get metadata
        metadata = s3_service.get_file_metadata(s3_key)

        return {"success": True, "s3_key": s3_key, **metadata}

    except Exception as e:
        logger.error(f"Error getting S3 file metadata: {e}", exc_info=True)
        return {"error": f"Failed to get S3 file metadata: {str(e)}"}
