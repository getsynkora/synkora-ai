"""
Google Drive Tools for AI Agents.

Provides comprehensive Google Drive integration including:
- File operations (list, get, upload, download, update, delete, search)
- Folder operations (create, move)
- Sharing and permissions
- Google Docs operations
- Google Sheets operations
"""

import base64
import json
import logging
from typing import Any

import aiohttp
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Google Drive API base URLs
DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
DOCS_API_BASE = "https://www.googleapis.com/docs/v1"
SHEETS_API_BASE = "https://www.googleapis.com/sheets/v4"


async def _get_google_drive_access_token(runtime_context, tool_name: str) -> str:
    """
    Get Google Drive access token from runtime context.

    This resolves the token by checking:
    1. User's personal token (user-first resolution)
    2. OAuth app token (fallback)

    Args:
        runtime_context: RuntimeContext with db_session
        tool_name: Name of the tool requesting access

    Returns:
        Access token string

    Raises:
        ValueError: If no token is available
    """
    from src.models.agent_tool import AgentTool
    from src.models.oauth_app import OAuthApp
    from src.models.user_oauth_token import UserOAuthToken
    from src.services.agents.security import decrypt_value

    db = runtime_context.db_session

    # Get agent tool configuration
    result = await db.execute(
        select(AgentTool).filter(
            AgentTool.agent_id == runtime_context.agent_id, AgentTool.tool_name == tool_name, AgentTool.enabled
        )
    )
    agent_tool = result.scalar_one_or_none()

    if not agent_tool or not agent_tool.oauth_app_id:
        raise ValueError(f"No OAuth app configured for tool {tool_name}")

    # Get OAuth app (case-insensitive provider check)
    result = await db.execute(
        select(OAuthApp).filter(
            OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("google_drive"), OAuthApp.is_active
        )
    )
    oauth_app = result.scalar_one_or_none()

    if not oauth_app:
        raise ValueError("No active Google Drive OAuth app found")

    access_token = None

    # Try user token first (user-first resolution)
    result = await db.execute(select(UserOAuthToken).filter(UserOAuthToken.oauth_app_id == oauth_app.id))
    user_token = result.scalar_one_or_none()

    if user_token and user_token.access_token:
        decrypted_token = decrypt_value(user_token.access_token)
        access_token = decrypted_token
        logger.info(f"✅ Using user's Google Drive token (OAuth app: '{oauth_app.app_name}')")
    elif oauth_app.access_token:
        # Fall back to OAuth app token
        access_token = decrypt_value(oauth_app.access_token)
        logger.info(f"✅ Using Google Drive OAuth app token '{oauth_app.app_name}'")

    if not access_token:
        raise ValueError("No Google Drive access token available. Please connect Google Drive.")

    return access_token


# ============================================================================
# FILE OPERATIONS (7 tools)
# ============================================================================


async def internal_google_drive_list_files(
    page_size: int = 100,
    page_token: str | None = None,
    query: str | None = None,
    order_by: str = "modifiedTime desc",
    spaces: str = "drive",
    **kwargs,
) -> dict[str, Any]:
    """
    List files and folders in Google Drive.

    Args:
        page_size: Maximum number of files to return (1-1000)
        page_token: Token for next page of results
        query: Search query (e.g., "name contains 'report'", "mimeType = 'application/pdf'")
        order_by: Sort order (e.g., "modifiedTime desc", "name", "createdTime")
        spaces: Spaces to search (drive, appDataFolder, photos)

    Returns:
        Dictionary with files list and pagination info

    Example queries:
        - "name contains 'report'" - Files containing 'report' in name
        - "mimeType = 'application/pdf'" - PDF files only
        - "trashed = false" - Non-trashed files
        - "'parent_folder_id' in parents" - Files in specific folder
    """
    # Get runtime context and tool name from kwargs
    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_drive_list_files")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        params = {
            "pageSize": min(page_size, 1000),
            "fields": "nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, webViewLink, owners, shared, parents)",
            "orderBy": order_by,
            "spaces": spaces,
        }

        if page_token:
            params["pageToken"] = page_token
        if query:
            params["q"] = query

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{DRIVE_API_BASE}/files", headers=headers, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to list files: {error_text}")

                data = await response.json()

                return {
                    "files": data.get("files", []),
                    "next_page_token": data.get("nextPageToken"),
                    "total_returned": len(data.get("files", [])),
                }

    except Exception as e:
        logger.error(f"Error listing Drive files: {e}", exc_info=True)
        raise


async def internal_google_drive_get_file(file_id: str, **kwargs) -> dict[str, Any]:
    """
    Get metadata for a specific file or folder.

    Args:
        file_id: Google Drive file ID

    Returns:
        File metadata including name, type, size, dates, sharing info
    """
    # Sanitize file_id to remove trailing punctuation
    file_id = _sanitize_file_id(file_id)

    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_drive_get_file")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        params = {
            "fields": "id, name, mimeType, size, createdTime, modifiedTime, webViewLink, webContentLink, owners, shared, parents, description, permissions"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{DRIVE_API_BASE}/files/{file_id}", headers=headers, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to get file: {error_text}")

                return await response.json()

    except Exception as e:
        logger.error(f"Error getting Drive file: {e}", exc_info=True)
        raise


def _sanitize_file_id(file_id: str) -> str:
    """Sanitize file ID by removing trailing punctuation and whitespace."""
    if not file_id:
        return file_id
    # Strip whitespace and common trailing punctuation that LLMs might add
    cleaned = file_id.strip().rstrip(".,;:!?")
    # Validate: real Drive IDs are 25-44 alphanumeric/dash/underscore chars.
    # If the value looks like a file name (short, contains spaces, etc.) reject it early.
    import re as _re

    if not _re.match(r"^[A-Za-z0-9_\-]{25,}$", cleaned):
        raise ValueError(
            f"'{cleaned}' does not look like a valid Google Drive file ID. "
            "Use the file ID from the listing (the long alphanumeric string), not the file name."
        )
    return cleaned


async def internal_google_drive_download_file(file_id: str, **kwargs) -> dict[str, Any]:
    """
    Download file content from Google Drive.

    Args:
        file_id: Google Drive file ID

    Returns:
        Dictionary with file content (base64 encoded) and metadata

    Note: For large files, consider using export for Google Workspace files
    """
    # Sanitize file_id to remove trailing punctuation
    file_id = _sanitize_file_id(file_id)

    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_drive_download_file")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}"}

        async with aiohttp.ClientSession() as session:
            # Get file metadata first
            async with session.get(
                f"{DRIVE_API_BASE}/files/{file_id}", headers=headers, params={"fields": "name, mimeType, size"}
            ) as meta_response:
                if meta_response.status != 200:
                    error_text = await meta_response.text()
                    raise Exception(f"Failed to get file metadata: {error_text}")
                metadata = await meta_response.json()

            # Download content
            async with session.get(
                f"{DRIVE_API_BASE}/files/{file_id}", headers=headers, params={"alt": "media"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to download file: {error_text}")

                content = await response.read()

                return {
                    "file_id": file_id,
                    "name": metadata.get("name"),
                    "mime_type": metadata.get("mimeType"),
                    "size": metadata.get("size"),
                    "content": base64.b64encode(content).decode("utf-8"),
                    "encoding": "base64",
                }

    except Exception as e:
        logger.error(f"Error downloading Drive file: {e}", exc_info=True)
        raise


async def internal_google_drive_upload_file(
    name: str,
    content: str,
    mime_type: str = "text/plain",
    parent_folder_id: str | None = None,
    description: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """
    Upload a new file to Google Drive.

    Args:
        name: File name
        content: File content (base64 encoded for binary files, plain text for text files)
        mime_type: MIME type of the file
        parent_folder_id: Optional parent folder ID
        description: Optional file description

    Returns:
        Created file metadata including file_id
    """
    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_drive_upload_file")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        # Build metadata
        metadata = {"name": name, "mimeType": mime_type}

        if parent_folder_id:
            metadata["parents"] = [parent_folder_id]
        if description:
            metadata["description"] = description

        # For multipart upload
        boundary = "===============7330845974216740156=="

        # Decode content if base64
        try:
            file_content = base64.b64decode(content)
        except Exception:
            file_content = content.encode("utf-8")

        # Build multipart body
        body_parts = [
            f"--{boundary}",
            "Content-Type: application/json; charset=UTF-8",
            "",
            json.dumps(metadata),
            f"--{boundary}",
            f"Content-Type: {mime_type}",
            "",
            file_content.decode("utf-8", errors="ignore"),
            f"--{boundary}--",
        ]

        body = "\r\n".join(body_parts)

        headers["Content-Type"] = f"multipart/related; boundary={boundary}"

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{DRIVE_API_BASE}/files?uploadType=multipart&fields=id,name,mimeType,webViewLink",
                headers=headers,
                data=body,
            ) as response,
        ):
            if response.status not in [200, 201]:
                error_text = await response.text()
                raise Exception(f"Failed to upload file: {error_text}")

            return await response.json()

    except Exception as e:
        logger.error(f"Error uploading Drive file: {e}", exc_info=True)
        raise


async def internal_google_drive_update_file(
    file_id: str, name: str | None = None, content: str | None = None, description: str | None = None, **kwargs
) -> dict[str, Any]:
    """
    Update an existing file's metadata or content.

    Args:
        file_id: Google Drive file ID
        name: New file name (optional)
        content: New file content (optional, base64 encoded)
        description: New description (optional)

    Returns:
        Updated file metadata
    """
    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_drive_update_file")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        # Build metadata update
        metadata = {}
        if name:
            metadata["name"] = name
        if description is not None:
            metadata["description"] = description

        async with aiohttp.ClientSession() as session:
            # Update metadata if provided
            if metadata:
                async with session.patch(
                    f"{DRIVE_API_BASE}/files/{file_id}", headers=headers, json=metadata
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to update file metadata: {error_text}")

            # Update content if provided
            if content:
                try:
                    file_content = base64.b64decode(content)
                except Exception:
                    file_content = content.encode("utf-8")

                async with session.patch(
                    f"{DRIVE_API_BASE}/files/{file_id}?uploadType=media",
                    headers={**headers, "Content-Type": "application/octet-stream"},
                    data=file_content,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Failed to update file content: {error_text}")

            # Get updated file info
            async with session.get(
                f"{DRIVE_API_BASE}/files/{file_id}",
                headers=headers,
                params={"fields": "id,name,mimeType,modifiedTime,webViewLink"},
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to get updated file: {error_text}")

                return await response.json()

    except Exception as e:
        logger.error(f"Error updating Drive file: {e}", exc_info=True)
        raise


async def internal_google_drive_delete_file(file_id: str, **kwargs) -> dict[str, Any]:
    """
    Delete a file or folder from Google Drive.

    Args:
        file_id: Google Drive file ID

    Returns:
        Success confirmation
    """
    # Sanitize file_id to remove trailing punctuation
    file_id = _sanitize_file_id(file_id)

    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_drive_delete_file")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.delete(f"{DRIVE_API_BASE}/files/{file_id}", headers=headers) as response:
                if response.status != 204:
                    error_text = await response.text()
                    raise Exception(f"Failed to delete file: {error_text}")

                return {"success": True, "file_id": file_id, "message": "File deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting Drive file: {e}", exc_info=True)
        raise


async def internal_google_drive_search_files(query: str, page_size: int = 50, **kwargs) -> dict[str, Any]:
    """
    Search for files in Google Drive using advanced query syntax.

    Args:
        query: Search query string
        page_size: Maximum results to return

    Returns:
        List of matching files

    Example queries:
        - "name contains 'budget' and mimeType = 'application/pdf'"
        - "fullText contains 'quarterly report'"
        - "modifiedTime > '2025-01-01T00:00:00'"
        - "sharedWithMe and not trashed"
    """
    return await internal_google_drive_list_files(page_size=page_size, query=query, **kwargs)


# ============================================================================
# FOLDER OPERATIONS (2 tools)
# ============================================================================


async def internal_google_drive_create_folder(
    name: str, parent_folder_id: str | None = None, **kwargs
) -> dict[str, Any]:
    """
    Create a new folder in Google Drive.

    Args:
        name: Folder name
        parent_folder_id: Optional parent folder ID (creates in root if not specified)

    Returns:
        Created folder metadata including folder_id
    """
    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_drive_create_folder")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}

        if parent_folder_id:
            metadata["parents"] = [parent_folder_id]

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{DRIVE_API_BASE}/files", headers=headers, json=metadata, params={"fields": "id,name,webViewLink"}
            ) as response,
        ):
            if response.status not in [200, 201]:
                error_text = await response.text()
                raise Exception(f"Failed to create folder: {error_text}")

            return await response.json()

    except Exception as e:
        logger.error(f"Error creating Drive folder: {e}", exc_info=True)
        raise


async def internal_google_drive_move_file(file_id: str, new_parent_folder_id: str, **kwargs) -> dict[str, Any]:
    """
    Move a file to a different folder.

    Args:
        file_id: Google Drive file ID to move
        new_parent_folder_id: Target folder ID

    Returns:
        Updated file metadata
    """
    # Sanitize IDs to remove trailing punctuation
    file_id = _sanitize_file_id(file_id)
    new_parent_folder_id = _sanitize_file_id(new_parent_folder_id)

    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_drive_move_file")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        async with aiohttp.ClientSession() as session:
            # Get current parents
            async with session.get(
                f"{DRIVE_API_BASE}/files/{file_id}", headers=headers, params={"fields": "parents"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to get file parents: {error_text}")
                data = await response.json()
                previous_parents = ",".join(data.get("parents", []))

            # Move file
            async with session.patch(
                f"{DRIVE_API_BASE}/files/{file_id}",
                headers=headers,
                params={
                    "addParents": new_parent_folder_id,
                    "removeParents": previous_parents,
                    "fields": "id,name,parents,webViewLink",
                },
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to move file: {error_text}")

                return await response.json()

    except Exception as e:
        logger.error(f"Error moving Drive file: {e}", exc_info=True)
        raise


# ============================================================================
# SHARING & PERMISSIONS (3 tools)
# ============================================================================


async def internal_google_drive_share_file(
    file_id: str, email: str, role: str = "reader", send_notification: bool = True, **kwargs
) -> dict[str, Any]:
    """
    Share a file with a user.

    Args:
        file_id: Google Drive file ID
        email: Email address to share with
        role: Permission role (reader, commenter, writer, owner)
        send_notification: Whether to send email notification

    Returns:
        Permission details
    """
    # Sanitize file_id to remove trailing punctuation
    file_id = _sanitize_file_id(file_id)

    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_drive_share_file")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        permission = {"type": "user", "role": role, "emailAddress": email}

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{DRIVE_API_BASE}/files/{file_id}/permissions",
                headers=headers,
                json=permission,
                params={"sendNotificationEmail": str(send_notification).lower()},
            ) as response,
        ):
            if response.status not in [200, 201]:
                error_text = await response.text()
                raise Exception(f"Failed to share file: {error_text}")

            return await response.json()

    except Exception as e:
        logger.error(f"Error sharing Drive file: {e}", exc_info=True)
        raise


async def internal_google_drive_get_permissions(file_id: str, **kwargs) -> dict[str, Any]:
    """
    Get all permissions for a file.

    Args:
        file_id: Google Drive file ID

    Returns:
        List of permissions
    """
    # Sanitize file_id to remove trailing punctuation
    file_id = _sanitize_file_id(file_id)

    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_drive_get_permissions")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{DRIVE_API_BASE}/files/{file_id}/permissions",
                headers=headers,
                params={"fields": "permissions(id,type,role,emailAddress,displayName)"},
            ) as response,
        ):
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to get permissions: {error_text}")

            return await response.json()

    except Exception as e:
        logger.error(f"Error getting Drive permissions: {e}", exc_info=True)
        raise


async def internal_google_drive_remove_permission(file_id: str, permission_id: str, **kwargs) -> dict[str, Any]:
    """
    Remove a permission from a file.

    Args:
        file_id: Google Drive file ID
        permission_id: Permission ID to remove

    Returns:
        Success confirmation
    """
    # Sanitize IDs to remove trailing punctuation
    file_id = _sanitize_file_id(file_id)
    permission_id = _sanitize_file_id(permission_id)

    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_drive_remove_permission")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}"}

        async with (
            aiohttp.ClientSession() as session,
            session.delete(
                f"{DRIVE_API_BASE}/files/{file_id}/permissions/{permission_id}", headers=headers
            ) as response,
        ):
            if response.status != 204:
                error_text = await response.text()
                raise Exception(f"Failed to remove permission: {error_text}")

            return {"success": True, "message": "Permission removed successfully"}

    except Exception as e:
        logger.error(f"Error removing Drive permission: {e}", exc_info=True)
        raise


# ============================================================================
# GOOGLE DOCS OPERATIONS (3 tools)
# ============================================================================


async def internal_google_docs_create_document(
    title: str, content: str | None = None, parent_folder_id: str | None = None, **kwargs
) -> dict[str, Any]:
    """
    Create a new Google Docs document.

    Args:
        title: Document title
        content: Initial content (plain text)
        parent_folder_id: Optional parent folder ID

    Returns:
        Created document metadata including document_id
    """
    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_docs_create_document")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:
            # Create empty document in Drive
            metadata = {"name": title, "mimeType": "application/vnd.google-apps.document"}
            if parent_folder_id:
                metadata["parents"] = [parent_folder_id]

            async with session.post(f"{DRIVE_API_BASE}/files", headers=headers, json=metadata) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    raise Exception(f"Failed to create document: {error_text}")
                doc_data = await response.json()
                doc_id = doc_data["id"]

            # Add content if provided
            if content:
                requests = [{"insertText": {"location": {"index": 1}, "text": content}}]

                async with session.post(
                    f"{DOCS_API_BASE}/documents/{doc_id}:batchUpdate", headers=headers, json={"requests": requests}
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to add content to document: {await response.text()}")

            return {"document_id": doc_id, "title": title, "url": f"https://docs.google.com/document/d/{doc_id}/edit"}

    except Exception as e:
        logger.error(f"Error creating Google Doc: {e}", exc_info=True)
        raise


async def internal_google_docs_get_content(document_id: str, **kwargs) -> dict[str, Any]:
    """
    Get content from a Google Docs document.

    Args:
        document_id: Google Docs document ID

    Returns:
        Document content and metadata
    """
    # Sanitize document_id to remove trailing punctuation
    document_id = _sanitize_file_id(document_id)

    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_docs_get_content")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{DOCS_API_BASE}/documents/{document_id}", headers=headers) as response:
                if response.status != 200:
                    if response.status == 404:
                        raise Exception(
                            f"Document '{document_id}' not found. Ensure the ID is correct and the account has access to it."
                        )
                    error_text = await response.text()
                    if error_text.strip().startswith("<"):
                        error_text = f"HTTP {response.status}"
                    raise Exception(f"Failed to get document: {error_text}")

                data = await response.json()

                # Extract text content
                content = []
                if "body" in data and "content" in data["body"]:
                    for element in data["body"]["content"]:
                        if "paragraph" in element:
                            for text_element in element["paragraph"].get("elements", []):
                                if "textRun" in text_element:
                                    content.append(text_element["textRun"].get("content", ""))

                return {
                    "document_id": document_id,
                    "title": data.get("title"),
                    "content": "".join(content),
                    "revision_id": data.get("revisionId"),
                }

    except Exception as e:
        logger.error(f"Error getting Google Doc content: {e}", exc_info=True)
        raise


async def internal_google_docs_append_content(document_id: str, content: str, **kwargs) -> dict[str, Any]:
    """
    Append content to the end of a Google Docs document.

    Args:
        document_id: Google Docs document ID
        content: Text content to append

    Returns:
        Success confirmation
    """
    # Sanitize document_id to remove trailing punctuation
    document_id = _sanitize_file_id(document_id)

    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_docs_append_content")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        # Get document to find end index
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{DOCS_API_BASE}/documents/{document_id}", headers=headers) as response:
                if response.status != 200:
                    if response.status == 404:
                        raise Exception(
                            f"Document '{document_id}' not found. Ensure the ID is correct and the account has access to it."
                        )
                    error_text = await response.text()
                    if error_text.strip().startswith("<"):
                        error_text = f"HTTP {response.status}"
                    raise Exception(f"Failed to get document: {error_text}")
                doc_data = await response.json()
                end_index = doc_data["body"]["content"][-1]["endIndex"] - 1

            # Append text
            requests = [{"insertText": {"location": {"index": end_index}, "text": content}}]

            async with session.post(
                f"{DOCS_API_BASE}/documents/{document_id}:batchUpdate", headers=headers, json={"requests": requests}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to append content: {error_text}")

                return {"success": True, "document_id": document_id, "message": "Content appended successfully"}

    except Exception as e:
        logger.error(f"Error appending to Google Doc: {e}", exc_info=True)
        raise


# ============================================================================
# GOOGLE SHEETS OPERATIONS (3 tools)
# ============================================================================


async def internal_google_sheets_create_spreadsheet(
    title: str, parent_folder_id: str | None = None, **kwargs
) -> dict[str, Any]:
    """
    Create a new Google Sheets spreadsheet.

    Args:
        title: Spreadsheet title
        parent_folder_id: Optional parent folder ID

    Returns:
        Created spreadsheet metadata including spreadsheet_id
    """
    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_sheets_create_spreadsheet")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:
            # Create spreadsheet
            async with session.post(
                f"{SHEETS_API_BASE}/spreadsheets", headers=headers, json={"properties": {"title": title}}
            ) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    raise Exception(f"Failed to create spreadsheet: {error_text}")
                sheet_data = await response.json()
                sheet_id = sheet_data["spreadsheetId"]

            # Move to folder if specified
            if parent_folder_id:
                async with session.patch(
                    f"{DRIVE_API_BASE}/files/{sheet_id}", headers=headers, params={"addParents": parent_folder_id}
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to move spreadsheet to folder: {await response.text()}")

            return {
                "spreadsheet_id": sheet_id,
                "title": title,
                "url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit",
            }

    except Exception as e:
        logger.error(f"Error creating Google Sheet: {e}", exc_info=True)
        raise


async def internal_google_sheets_read_range(
    spreadsheet_id: str, range_name: str = "Sheet1!A1:Z100", **kwargs
) -> dict[str, Any]:
    """
    Read data from a Google Sheets range.

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID
        range_name: Range in A1 notation (e.g., "Sheet1!A1:D10")

    Returns:
        Range data as 2D array
    """
    # Sanitize spreadsheet_id to remove trailing punctuation
    spreadsheet_id = _sanitize_file_id(spreadsheet_id)

    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_sheets_read_range")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{SHEETS_API_BASE}/spreadsheets/{spreadsheet_id}/values/{range_name}", headers=headers
            ) as response,
        ):
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to read range: {error_text}")

            data = await response.json()
            return {
                "spreadsheet_id": spreadsheet_id,
                "range": data.get("range"),
                "values": data.get("values", []),
                "row_count": len(data.get("values", [])),
            }

    except Exception as e:
        logger.error(f"Error reading Google Sheet range: {e}", exc_info=True)
        raise


async def internal_google_sheets_write_range(
    spreadsheet_id: str, range_name: str, values: list[list[Any]], **kwargs
) -> dict[str, Any]:
    """
    Write data to a Google Sheets range.

    Args:
        spreadsheet_id: Google Sheets spreadsheet ID
        range_name: Range in A1 notation (e.g., "Sheet1!A1")
        values: 2D array of values to write

    Returns:
        Update confirmation with affected range
    """
    # Sanitize spreadsheet_id to remove trailing punctuation
    spreadsheet_id = _sanitize_file_id(spreadsheet_id)

    runtime_context = kwargs.get("runtime_context")
    config = kwargs.get("config", {})
    tool_name = config.get("_tool_name", "internal_google_sheets_write_range")

    if not runtime_context:
        return {"success": False, "error": "Runtime context not available for Google Drive authentication"}

    access_token = await _get_google_drive_access_token(runtime_context, tool_name)

    try:
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        body = {"values": values}

        async with (
            aiohttp.ClientSession() as session,
            session.put(
                f"{SHEETS_API_BASE}/spreadsheets/{spreadsheet_id}/values/{range_name}",
                headers=headers,
                json=body,
                params={"valueInputOption": "USER_ENTERED"},
            ) as response,
        ):
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to write range: {error_text}")

            data = await response.json()
            return {
                "spreadsheet_id": spreadsheet_id,
                "updated_range": data.get("updatedRange"),
                "updated_rows": data.get("updatedRows"),
                "updated_columns": data.get("updatedColumns"),
                "updated_cells": data.get("updatedCells"),
            }

    except Exception as e:
        logger.error(f"Error writing to Google Sheet: {e}", exc_info=True)
        raise
