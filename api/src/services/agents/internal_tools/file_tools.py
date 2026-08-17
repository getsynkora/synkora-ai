"""
File System Tools for Synkora Agents.

Provides comprehensive file system operations including reading, writing, editing,
directory management, and file manipulation with enterprise security controls.
"""

import base64
import fnmatch
import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Maximum token length for file content (configurable)
MAX_TOKEN_LENGTH = 100000

# Security configuration
ALLOWED_EXTENSIONS = {
    "text": {
        ".txt",
        ".md",
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".mjs",
        ".cjs",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".csv",
        ".html",
        ".css",
        ".scss",
        ".less",
        ".sass",
        ".sql",
        ".sh",
        ".bat",
        ".ini",
        ".conf",
        ".log",
        ".env",
        ".gitignore",
        ".dockerfile",
        ".vue",
        ".svelte",
        ".astro",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".rb",
        ".php",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".swift",
        ".m",
        ".dart",
        ".toml",
        ".lock",
        ".prisma",
        ".graphql",
    },
    "media": {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
        ".svg",
        ".mp4",
        ".avi",
        ".mov",
        ".pdf",
        ".doc",
        ".docx",
    },
}

# Combined allowed extensions for internal_read_file
ALL_ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS["text"] | ALLOWED_EXTENSIONS["media"]

# Maximum file size limits (in bytes)
MAX_TEXT_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_MEDIA_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Blocked patterns for security
BLOCKED_PATH_PATTERNS = [
    r"\.\./",  # Path traversal
    r"/etc/",  # System directories
    r"/sys/",
    r"/proc/",
    r"/root/",
    r"~",  # Home directory shortcuts
]


def _get_workspace_path(config: dict[str, Any] | None) -> str | None:
    """Get the workspace path from config or RuntimeContext (including Celery task fallback)."""
    from src.services.agents.workspace_manager import get_workspace_path_from_config

    return get_workspace_path_from_config(config)


def _is_path_within_workspace(path: str, workspace_path: str | None) -> tuple[bool, str | None]:
    """
    Check if a path is within the workspace directory.

    Args:
        path: Path to check
        workspace_path: Base workspace path

    Returns:
        Tuple of (is_within, error_message)
    """
    if not workspace_path:
        return False, "No workspace path configured. File operations require a valid workspace."

    try:
        # Resolve both paths to handle symlinks and relative paths
        real_path = os.path.realpath(path)
        real_workspace = os.path.realpath(workspace_path)

        # Check if path starts with workspace path
        if not real_path.startswith(real_workspace + os.sep) and real_path != real_workspace:
            return (
                False,
                f"Access denied: Path '{path}' is outside the workspace directory. Use workspace path: {workspace_path}",
            )

        return True, None

    except Exception as e:
        return False, f"Error validating path: {str(e)}"


def _is_path_allowed(path: str, workspace_path: str | None = None) -> tuple[bool, str | None]:
    """
    Check if the path is within allowed directories and safe to access.

    Args:
        path: Path to validate
        workspace_path: Base workspace path (required for security)

    Returns:
        Tuple of (is_allowed, error_message)
    """
    try:
        # Normalize path
        real_path = os.path.realpath(path)

        # Check for blocked patterns
        for pattern in BLOCKED_PATH_PATTERNS:
            if re.search(pattern, real_path):
                logger.warning(f"Blocked path pattern detected: {pattern} in {real_path}")
                return False, "Access denied: Path contains blocked pattern"

        # Must be within workspace
        is_within, error = _is_path_within_workspace(path, workspace_path)
        if not is_within:
            return False, error

        return True, None

    except Exception as e:
        logger.error(f"Error validating path {path}: {e}")
        return False, f"Error validating path: {str(e)}"


def _validate_file_path(
    file_path: str, must_exist: bool = True, config: dict[str, Any] | None = None
) -> tuple[bool, str | None]:
    """
    Validate file path with comprehensive security checks.

    Args:
        file_path: Path to validate
        must_exist: Whether file must exist
        config: Optional configuration dictionary containing workspace_path

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Get workspace path
        workspace_path = _get_workspace_path(config)

        # Basic path security check
        is_allowed, error = _is_path_allowed(file_path, workspace_path)
        if not is_allowed:
            return False, error

        # Convert to Path object for safer handling
        path = Path(file_path)

        if must_exist:
            if not path.exists():
                return False, f"File not found: {file_path}"

            if not path.is_file():
                return False, f"Path is not a file: {file_path}"

            if not os.access(path, os.R_OK):
                return False, f"File is not readable: {file_path}"

        return True, None

    except Exception as e:
        return False, f"Invalid file path: {str(e)}"


def _validate_directory_path(
    dir_path: str, must_exist: bool = True, config: dict[str, Any] | None = None
) -> tuple[bool, str | None]:
    """
    Validate directory path with security checks.

    Args:
        dir_path: Directory path to validate
        must_exist: Whether directory must exist
        config: Optional configuration dictionary containing workspace_path

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Get workspace path
        workspace_path = _get_workspace_path(config)

        # Basic path security check
        is_allowed, error = _is_path_allowed(dir_path, workspace_path)
        if not is_allowed:
            return False, error

        path = Path(dir_path)

        if must_exist:
            if not path.exists():
                return False, f"Directory not found: {dir_path}"

            if not path.is_dir():
                return False, f"Path is not a directory: {dir_path}"

        return True, None

    except Exception as e:
        return False, f"Invalid directory path: {str(e)}"


def _validate_file_extension(file_path: str, file_type: str = "text") -> tuple[bool, str | None]:
    """
    Validate file extension against allowed types.

    Args:
        file_path: Path to the file
        file_type: Type of file ('text' or 'media')

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        path = Path(file_path)
        extension = path.suffix.lower()

        if file_type not in ALLOWED_EXTENSIONS:
            return False, f"Unknown file type: {file_type}"

        allowed_exts = ALLOWED_EXTENSIONS[file_type]

        if extension not in allowed_exts:
            return False, f"File extension '{extension}' not allowed for {file_type} files"

        return True, None

    except Exception as e:
        return False, f"Error validating file extension: {str(e)}"


def _check_file_size(file_path: str, file_type: str = "text") -> tuple[bool, str | None]:
    """
    Check if file size is within allowed limits.

    Args:
        file_path: Path to the file
        file_type: Type of file ('text' or 'media')

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        file_size = os.path.getsize(file_path)

        if file_type == "text":
            max_size = MAX_TEXT_FILE_SIZE
        elif file_type == "media":
            max_size = MAX_MEDIA_FILE_SIZE
        else:
            return False, f"Unknown file type: {file_type}"

        if file_size > max_size:
            return False, f"File size ({file_size} bytes) exceeds maximum allowed ({max_size} bytes)"

        return True, None

    except Exception as e:
        return False, f"Error checking file size: {str(e)}"


def _count_tokens(text: str) -> int:
    """
    Count tokens in text using tiktoken.

    Args:
        text: Text to count tokens for

    Returns:
        Number of tokens
    """
    try:
        import tiktoken

        # Use cl100k_base encoding (GPT-4 tokenizer)
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        return len(tokens)

    except ImportError:
        logger.warning("tiktoken not installed, using approximate token count")
        return len(text) // 4
    except Exception as e:
        logger.error(f"Error counting tokens: {e}")
        return len(text) // 4


async def internal_read_text_file(
    file_path: str, start_line: int = 1, max_lines: int | None = None, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Read and analyze text files with token counting and pagination support.

    This is an internal tool that provides file reading capabilities without
    requiring an external MCP server. It includes security checks, token counting,
    and pagination support for large files.

    Args:
        file_path: Path to the text file to read
        start_line: 1-based line number to start reading from (default: 1)
        max_lines: Maximum number of lines to read (0 or None = no limit)
        config: Optional configuration dictionary

    Returns:
        Dictionary containing:
        - path: File path
        - name: File name
        - content: File content (possibly truncated)
        - token_count: Number of tokens in content
        - size: File size in bytes
        - total_lines: Total number of lines in file
        - read_start_line: Line number where reading started
        - lines_read: Number of lines actually read
        - is_truncated: Whether content was truncated
        - truncation_reason: Reason for truncation (if applicable)
        - error: Error message (if any)
    """
    try:
        # Validate file path
        is_valid, error_msg = _validate_file_path(file_path, config=config)
        if not is_valid:
            return {"error": error_msg}

        # Get file info
        path = Path(file_path).resolve()
        file_size = path.stat().st_size
        file_name = path.name

        # Read file content
        try:
            with open(path, encoding="utf-8") as f:
                all_lines = f.readlines()
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(path, encoding="latin-1") as f:
                    all_lines = f.readlines()
            except Exception as e:
                return {"error": f"Failed to read file with encoding: {str(e)}"}

        total_lines = len(all_lines)

        # Validate start_line
        if start_line < 1:
            start_line = 1
        if start_line > total_lines:
            return {"error": f"start_line ({start_line}) exceeds total lines ({total_lines})"}

        # Calculate line range to read (convert to 0-based indexing)
        start_idx = start_line - 1

        if max_lines is None or max_lines <= 0:
            # Read all lines from start_line to end
            lines_to_read = all_lines[start_idx:]
            end_idx = total_lines
        else:
            # Read specified number of lines
            end_idx = min(start_idx + max_lines, total_lines)
            lines_to_read = all_lines[start_idx:end_idx]

        # Join lines and count tokens
        content = "".join(lines_to_read)
        token_count = _count_tokens(content)

        # Check if we need to truncate due to token limit
        is_truncated = False
        truncation_reason = None
        lines_read = len(lines_to_read)

        if token_count > MAX_TOKEN_LENGTH:
            # Truncate content to fit within token limit
            is_truncated = True
            truncation_reason = f"Content truncated (exceeded MAX_TOKEN_LENGTH: {MAX_TOKEN_LENGTH} tokens)."

            # Binary search to find how many lines fit within token limit
            left, right = 0, len(lines_to_read)
            while left < right:
                mid = (left + right + 1) // 2
                test_content = "".join(lines_to_read[:mid])
                test_tokens = _count_tokens(test_content)

                if test_tokens <= MAX_TOKEN_LENGTH:
                    left = mid
                else:
                    right = mid - 1

            # Use the maximum number of lines that fit
            lines_to_read = lines_to_read[:left]
            content = "".join(lines_to_read)
            token_count = _count_tokens(content)
            lines_read = len(lines_to_read)

        elif max_lines and lines_read < (end_idx - start_idx):
            # Content was truncated due to max_lines limit
            is_truncated = True
            truncation_reason = f"Content truncated (hit max_lines: {max_lines})."

        # Build result
        result = {
            "path": str(path),
            "name": file_name,
            "content": content,
            "token_count": token_count,
            "size": file_size,
            "total_lines": total_lines,
            "read_start_line": start_line,
            "lines_read": lines_read,
            "is_truncated": is_truncated,
        }

        if truncation_reason:
            result["truncation_reason"] = truncation_reason

        return result

    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}", exc_info=True)
        return {"error": f"Failed to read file: {str(e)}"}


async def internal_search_files(
    directory: str, regex_pattern: str, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Search for files in a directory matching a regex pattern.

    Args:
        directory: The directory to search in
        regex_pattern: The regex pattern to search for
        config: Optional configuration dictionary

    Returns:
        Dictionary containing matches or error
    """
    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        try:
            compiled_pattern = re.compile(regex_pattern)
        except re.error as e:
            return {"error": f"Invalid regex pattern: {str(e)}"}

        result = await _cs.exec_command(["find", directory, "-type", "f"])
        if not result.get("success"):
            return {"error": result.get("error") or f"Path not found: {directory}"}

        matches = []
        for file_path in result["output"].splitlines():
            file_path = file_path.strip()
            if not file_path:
                continue
            file_name = os.path.basename(file_path)
            if compiled_pattern.match(file_name):
                matches.append({"path": file_path, "name": file_name, "directory": os.path.dirname(file_path)})

        return {"directory": directory, "pattern": regex_pattern, "matches": matches, "total_matches": len(matches)}

    try:
        # Validate directory path
        is_valid, error_msg = _validate_directory_path(directory, config=config)
        if not is_valid:
            return {"error": error_msg}

        logger.info(f"Searching for files in '{directory}' matching '{regex_pattern}' regex pattern")
        matches = []

        try:
            compiled_pattern = re.compile(regex_pattern)
        except re.error as e:
            return {"error": f"Invalid regex pattern: {str(e)}"}

        for root, _, files in os.walk(directory):
            for file in files:
                if compiled_pattern.match(file):
                    file_path = os.path.join(root, file)
                    matches.append({"path": file_path, "name": file, "directory": root})

        return {"directory": directory, "pattern": regex_pattern, "matches": matches, "total_matches": len(matches)}

    except Exception as e:
        logger.error(f"Error searching files in {directory}: {e}", exc_info=True)
        return {"error": f"Failed to search files: {str(e)}"}


async def internal_read_media_file(file_path: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Read a media file and return its content as base64 encoded string.

    Args:
        file_path: Path to the media file
        config: Optional configuration dictionary

    Returns:
        Dictionary containing file info and base64 content
    """
    try:
        # Validate file path
        is_valid, error_msg = _validate_file_path(file_path, config=config)
        if not is_valid:
            return {"error": error_msg}

        # Validate file extension
        is_valid_ext, ext_error = _validate_file_extension(file_path, "media")
        if not is_valid_ext:
            return {"error": ext_error}

        # Check file size
        size_valid, size_error = _check_file_size(file_path, "media")
        if not size_valid:
            return {"error": size_error}

        # Read file content
        with open(file_path, "rb") as f:
            content = f.read()

        encoded_content = base64.b64encode(content).decode("utf-8")
        mime_type, _ = mimetypes.guess_type(file_path)

        return {
            "path": file_path,
            "name": os.path.basename(file_path),
            "content": encoded_content,
            "size": len(content),
            "mime_type": mime_type,
            "encoding": "base64",
        }

    except Exception as e:
        logger.error(f"Error reading media file {file_path}: {e}", exc_info=True)
        return {"error": f"Failed to read media file: {str(e)}"}


async def internal_read_file(
    file_path: str, start_line: int = 1, max_lines: int | None = None, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Read a file and return its content. Automatically detects file type based on extension.

    For text files: Returns content as string with token counting and pagination support.
    For media files: Returns content as base64 encoded string with metadata.

    This tool combines the functionality of internal_read_text_file and internal_read_media_file.

    Args:
        file_path: Path to the file to read
        start_line: 1-based line number to start reading from (default: 1, only for text files)
        max_lines: Maximum number of lines to read (0 or None = no limit, only for text files)
        config: Optional configuration dictionary

    Returns:
        Dictionary containing:
        For text files:
        - path: File path
        - name: File name
        - content: File content (possibly truncated)
        - file_type: "text"
        - token_count: Number of tokens in content
        - size: File size in bytes
        - total_lines: Total number of lines in file
        - read_start_line: Line number where reading started
        - lines_read: Number of lines actually read
        - is_truncated: Whether content was truncated
        - truncation_reason: Reason for truncation (if applicable)
        - error: Error message (if any)

        For media files:
        - path: File path
        - name: File name
        - content: Base64 encoded content
        - file_type: "media"
        - size: File size in bytes
        - mime_type: MIME type of the file
        - encoding: "base64"
        - error: Error message (if any)
    """
    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        _max = max_lines if max_lines else 200
        return await _cs.read_file(file_path, start_line=start_line, max_lines=_max)

    try:
        # Validate file path
        is_valid, error_msg = _validate_file_path(file_path, config=config)
        if not is_valid:
            return {"error": error_msg}

        # Get file extension and determine file type
        path = Path(file_path).resolve()
        extension = path.suffix.lower()

        # Validate extension is allowed
        if extension not in ALL_ALLOWED_EXTENSIONS:
            allowed_list = ", ".join(sorted(ALL_ALLOWED_EXTENSIONS))
            return {"error": f"File extension '{extension}' not allowed. Allowed extensions: {allowed_list}"}

        # Determine if it's a text or media file
        is_text_file = extension in ALLOWED_EXTENSIONS["text"]

        if is_text_file:
            # Handle as text file
            file_size = path.stat().st_size
            file_name = path.name

            # Check file size
            if file_size > MAX_TEXT_FILE_SIZE:
                return {"error": f"File size ({file_size} bytes) exceeds maximum allowed ({MAX_TEXT_FILE_SIZE} bytes)"}

            # Read file content
            try:
                with open(path, encoding="utf-8") as f:
                    all_lines = f.readlines()
            except UnicodeDecodeError:
                # Try with different encoding
                try:
                    with open(path, encoding="latin-1") as f:
                        all_lines = f.readlines()
                except Exception as e:
                    return {"error": f"Failed to read file with encoding: {str(e)}"}

            total_lines = len(all_lines)

            # Validate start_line
            if start_line < 1:
                start_line = 1
            if start_line > total_lines:
                return {"error": f"start_line ({start_line}) exceeds total lines ({total_lines})"}

            # Calculate line range to read (convert to 0-based indexing)
            start_idx = start_line - 1

            if max_lines is None or max_lines <= 0:
                # Read all lines from start_line to end
                lines_to_read = all_lines[start_idx:]
                end_idx = total_lines
            else:
                # Read specified number of lines
                end_idx = min(start_idx + max_lines, total_lines)
                lines_to_read = all_lines[start_idx:end_idx]

            # Join lines and count tokens
            content = "".join(lines_to_read)
            token_count = _count_tokens(content)

            # Check if we need to truncate due to token limit
            is_truncated = False
            truncation_reason = None
            lines_read = len(lines_to_read)

            if token_count > MAX_TOKEN_LENGTH:
                # Truncate content to fit within token limit
                is_truncated = True
                truncation_reason = f"Content truncated (exceeded MAX_TOKEN_LENGTH: {MAX_TOKEN_LENGTH} tokens)."

                # Binary search to find how many lines fit within token limit
                left, right = 0, len(lines_to_read)
                while left < right:
                    mid = (left + right + 1) // 2
                    test_content = "".join(lines_to_read[:mid])
                    test_tokens = _count_tokens(test_content)

                    if test_tokens <= MAX_TOKEN_LENGTH:
                        left = mid
                    else:
                        right = mid - 1

                # Use the maximum number of lines that fit
                lines_to_read = lines_to_read[:left]
                content = "".join(lines_to_read)
                token_count = _count_tokens(content)
                lines_read = len(lines_to_read)

            elif max_lines and lines_read < (end_idx - start_idx):
                # Content was truncated due to max_lines limit
                is_truncated = True
                truncation_reason = f"Content truncated (hit max_lines: {max_lines})."

            # Build result for text file
            result = {
                "path": str(path),
                "name": file_name,
                "content": content,
                "file_type": "text",
                "token_count": token_count,
                "size": file_size,
                "total_lines": total_lines,
                "read_start_line": start_line,
                "lines_read": lines_read,
                "is_truncated": is_truncated,
            }

            if truncation_reason:
                result["truncation_reason"] = truncation_reason

            return result

        else:
            # Handle as media file
            # Check file size
            file_size = path.stat().st_size
            if file_size > MAX_MEDIA_FILE_SIZE:
                return {"error": f"File size ({file_size} bytes) exceeds maximum allowed ({MAX_MEDIA_FILE_SIZE} bytes)"}

            # Read file content
            with open(file_path, "rb") as f:
                content = f.read()

            encoded_content = base64.b64encode(content).decode("utf-8")
            mime_type, _ = mimetypes.guess_type(file_path)

            return {
                "path": str(path),
                "name": path.name,
                "content": encoded_content,
                "file_type": "media",
                "size": len(content),
                "mime_type": mime_type,
                "encoding": "base64",
            }

    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}", exc_info=True)
        return {"error": f"Failed to read file: {str(e)}"}


async def internal_write_file(
    file_path: str, content: str, encoding: str = "utf-8", config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Write content to a file with security validation.

    Args:
        file_path: Path where to write the file
        content: Content to write
        encoding: File encoding (default: utf-8)
        config: Optional configuration dictionary

    Returns:
        Dictionary indicating success or error
    """
    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        return await _cs.write_file(file_path, content)

    try:
        # Validate file path (don't require existence since we're creating)
        is_valid, error_msg = _validate_file_path(file_path, must_exist=False, config=config)
        if not is_valid:
            return {"error": error_msg}

        # Validate file extension for text files
        is_valid_ext, ext_error = _validate_file_extension(file_path, "text")
        if not is_valid_ext:
            return {"error": ext_error}

        # Create directory if it doesn't exist
        dir_path = os.path.dirname(file_path)
        if dir_path:  # Only create directory if there is a parent directory
            os.makedirs(dir_path, exist_ok=True)

        # Write file
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)

        file_size = os.path.getsize(file_path)

        return {"success": True, "path": file_path, "size": file_size, "encoding": encoding}

    except Exception as e:
        logger.error(f"Error writing file {file_path}: {e}", exc_info=True)
        return {"error": f"Failed to write file: {str(e)}"}


async def internal_edit_file(
    file_path: str, search_pattern: str, replace_with: str, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Edit a file by searching for a pattern and replacing it.

    Args:
        file_path: Path to the file to edit
        search_pattern: Pattern to search for
        replace_with: Text to replace with
        config: Optional configuration dictionary

    Returns:
        Dictionary indicating success or error
    """
    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        read_result = await _cs.read_file(file_path, start_line=1, max_lines=10_000_000)
        if not read_result.get("success"):
            return {"error": read_result.get("error") or f"File not found: {file_path}"}

        content = read_result["content"]
        new_content = content.replace(search_pattern, replace_with)
        replacement_count = content.count(search_pattern)

        write_result = await _cs.write_file(file_path, new_content)
        if not write_result.get("success"):
            return {"error": write_result.get("error") or f"Failed to write {file_path}"}

        return {
            "success": True,
            "path": file_path,
            "replacements_made": replacement_count,
            "search_pattern": search_pattern,
            "replace_with": replace_with,
        }

    try:
        # Validate file path
        is_valid, error_msg = _validate_file_path(file_path, config=config)
        if not is_valid:
            return {"error": error_msg}

        # Validate file extension
        is_valid_ext, ext_error = _validate_file_extension(file_path, "text")
        if not is_valid_ext:
            return {"error": ext_error}

        # Read current content
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Perform replacement
        new_content = content.replace(search_pattern, replace_with)
        replacement_count = content.count(search_pattern)

        # Write back to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return {
            "success": True,
            "path": file_path,
            "replacements_made": replacement_count,
            "search_pattern": search_pattern,
            "replace_with": replace_with,
        }

    except Exception as e:
        logger.error(f"Error editing file {file_path}: {e}", exc_info=True)
        return {"error": f"Failed to edit file: {str(e)}"}


async def internal_get_file_info(file_path: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Get comprehensive information about a file or directory.

    Args:
        file_path: Path to the file or directory
        config: Optional configuration dictionary

    Returns:
        Dictionary containing file information
    """
    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        if not await _cs.file_exists(file_path):
            return {"error": f"Path not found: {file_path}"}

        stat_result = await _cs.exec_command(["stat", "-c", "%s|%Y|%Z|%F", file_path])
        if not stat_result.get("success"):
            return {"error": stat_result.get("error") or f"Failed to stat {file_path}"}

        try:
            size_str, mtime_str, ctime_str, ftype = stat_result["output"].strip().split("|", 3)
            is_dir = "directory" in ftype
            info = {
                "path": file_path,
                "name": os.path.basename(file_path.rstrip("/")),
                "size": int(size_str),
                "last_modified": float(mtime_str),
                "created": float(ctime_str),
                "is_dir": is_dir,
                "is_file": not is_dir,
            }
        except (ValueError, IndexError) as e:
            return {"error": f"Failed to parse stat output for {file_path}: {e}"}

        if info["is_file"]:
            info["extension"] = os.path.splitext(file_path)[1].lower()
            info["mime_type"] = mimetypes.guess_type(file_path)[0]

        return info

    try:
        # Get workspace path and validate
        workspace_path = _get_workspace_path(config)
        is_allowed, error = _is_path_allowed(file_path, workspace_path)
        if not is_allowed:
            return {"error": error}

        if not os.path.exists(file_path):
            return {"error": f"Path not found: {file_path}"}

        path = Path(file_path)
        stats = path.stat()

        info = {
            "path": str(path.resolve()),
            "name": path.name,
            "size": stats.st_size,
            "last_modified": stats.st_mtime,
            "created": stats.st_ctime,
            "is_dir": path.is_dir(),
            "is_file": path.is_file(),
            "permissions": oct(stats.st_mode)[-3:],
            "owner_readable": os.access(path, os.R_OK),
            "owner_writable": os.access(path, os.W_OK),
            "owner_executable": os.access(path, os.X_OK),
        }

        if path.is_file():
            info["extension"] = path.suffix.lower()
            info["mime_type"] = mimetypes.guess_type(str(path))[0]

        return info

    except Exception as e:
        logger.error(f"Error getting file info for {file_path}: {e}", exc_info=True)
        return {"error": f"Failed to get file info: {str(e)}"}


async def internal_move_file(
    source_path: str, destination_path: str, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Move a file or directory from source to destination.

    Args:
        source_path: Source file/directory path
        destination_path: Destination path
        config: Optional configuration dictionary

    Returns:
        Dictionary indicating success or error
    """
    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        if not await _cs.file_exists(source_path):
            return {"error": f"Source path not found: {source_path}"}

        dest_dir = os.path.dirname(destination_path)
        if dest_dir:
            await _cs.create_dir(dest_dir)

        mv_result = await _cs.exec_command(["mv", source_path, destination_path])
        if not mv_result.get("success"):
            return {"error": mv_result.get("error") or f"Failed to move {source_path} to {destination_path}"}

        return {"success": True, "source": source_path, "destination": destination_path, "operation": "move"}

    try:
        # Get workspace path and validate both paths
        workspace_path = _get_workspace_path(config)

        is_allowed, error = _is_path_allowed(source_path, workspace_path)
        if not is_allowed:
            return {"error": f"Source path error: {error}"}

        is_allowed, error = _is_path_allowed(destination_path, workspace_path)
        if not is_allowed:
            return {"error": f"Destination path error: {error}"}

        if not os.path.exists(source_path):
            return {"error": f"Source path not found: {source_path}"}

        # Create destination directory if needed
        dest_dir = os.path.dirname(destination_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)

        # Perform move operation
        shutil.move(source_path, destination_path)

        return {"success": True, "source": source_path, "destination": destination_path, "operation": "move"}

    except Exception as e:
        logger.error(f"Error moving {source_path} to {destination_path}: {e}", exc_info=True)
        return {"error": f"Failed to move file: {str(e)}"}


async def internal_create_directory(directory_path: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Create a directory with parent directories as needed.

    Args:
        directory_path: Path of directory to create
        config: Optional configuration dictionary

    Returns:
        Dictionary indicating success or error
    """
    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        return await _cs.create_dir(directory_path)

    try:
        # Validate directory path
        is_valid, error_msg = _validate_directory_path(directory_path, must_exist=False, config=config)
        if not is_valid:
            return {"error": error_msg}

        # Create directory
        os.makedirs(directory_path, exist_ok=True)

        return {"success": True, "path": directory_path, "created": not os.path.exists(directory_path)}

    except Exception as e:
        logger.error(f"Error creating directory {directory_path}: {e}", exc_info=True)
        return {"error": f"Failed to create directory: {str(e)}"}


async def internal_list_directory(
    directory_path: str, include_hidden: bool = False, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    List directory contents with detailed information.

    Args:
        directory_path: Path to directory to list
        include_hidden: Whether to include hidden files
        config: Optional configuration dictionary

    Returns:
        Dictionary containing directory listing
    """
    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        result = await _cs.list_dir(directory_path)
        if not result["success"]:
            return {"error": result["error"]}
        # Adapt to the format callers expect
        entries = result.get("entries", [])
        if not include_hidden:
            entries = [e for e in entries if not e["name"].startswith(".")]
        items = [
            {
                "name": e["name"],
                "type": "directory" if e["is_dir"] else "file",
                "size": e["size"],
            }
            for e in entries
        ]
        return {
            "path": directory_path,
            "items": items,
            "total_items": len(items),
        }

    try:
        # Validate directory path
        is_valid, error_msg = _validate_directory_path(directory_path, config=config)
        if not is_valid:
            return {"error": error_msg}

        items = []
        total_size = 0

        for item_name in os.listdir(directory_path):
            # Skip hidden files unless requested
            if not include_hidden and item_name.startswith("."):
                continue

            item_path = os.path.join(directory_path, item_name)

            try:
                stats = os.stat(item_path)
                is_dir = os.path.isdir(item_path)
                size = stats.st_size if not is_dir else 0
                total_size += size

                items.append(
                    {
                        "name": item_name,
                        "path": item_path,
                        "size": size,
                        "is_dir": is_dir,
                        "is_file": os.path.isfile(item_path),
                        "last_modified": stats.st_mtime,
                        "permissions": oct(stats.st_mode)[-3:],
                    }
                )
            except OSError as e:
                logger.warning(f"Could not stat {item_path}: {e}")
                continue

        # Sort items: directories first, then files, both alphabetically
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        return {
            "directory": directory_path,
            "items": items,
            "total_items": len(items),
            "total_size": total_size,
            "include_hidden": include_hidden,
        }

    except Exception as e:
        logger.error(f"Error listing directory {directory_path}: {e}", exc_info=True)
        return {"error": f"Failed to list directory: {str(e)}"}


async def internal_directory_tree(
    directory_path: str, max_depth: int | None = None, show_hidden: bool = False, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Generate a directory tree structure using the tree command.

    Args:
        directory_path: Path to directory to generate tree for
        max_depth: Maximum depth of directory tree (None = no limit)
        show_hidden: Whether to include hidden files
        config: Optional configuration dictionary

    Returns:
        Dictionary containing tree output and metadata
    """
    # Build tree command (shared between local and remote execution)
    command = ["tree"]
    if max_depth is not None and max_depth > 0:
        command.extend(["-L", str(max_depth)])
    if show_hidden:
        command.append("-a")
    command.append(directory_path)

    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        result = await _cs.exec_command(command, timeout=30)
        if not result.get("success"):
            return {"path": directory_path, "tree": "", "error": result.get("error") or "tree command failed"}
        return {"path": directory_path, "tree": result["output"], "max_depth": max_depth, "show_hidden": show_hidden}

    try:
        # Validate directory path
        is_valid, error_msg = _validate_directory_path(directory_path, config=config)
        if not is_valid:
            return {"error": error_msg}

        logger.info(f"Generating directory tree for: {directory_path}")

        try:
            from src.services.agents.internal_tools.command_tools import _is_command_safe

            workspace_path = _get_workspace_path(config)
            if not _is_command_safe(command, workspace_path):
                return {"error": f"Command blocked by security validator: {' '.join(command)}"}

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,  # Prevent hanging
            )

            tree_output = result.stdout

            return {"path": directory_path, "tree": tree_output, "max_depth": max_depth, "show_hidden": show_hidden}

        except FileNotFoundError:
            logger.error("tree command not found. Please install tree utility.")
            return {
                "path": directory_path,
                "tree": "",
                "error": "tree command not found. Please install it using: brew install tree (macOS) or apt-get install tree (Linux)",
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"tree command failed for '{directory_path}': {e.stderr}")
            return {"path": directory_path, "tree": "", "error": f"tree command failed: {e.stderr}"}
        except subprocess.TimeoutExpired:
            logger.error(f"tree command timed out for '{directory_path}'")
            return {"path": directory_path, "tree": "", "error": "tree command timed out after 30 seconds"}

    except Exception as e:
        logger.error(f"Error generating directory tree for {directory_path}: {e}", exc_info=True)
        return {"error": f"Failed to generate directory tree: {str(e)}"}


def _glob_pattern_to_regex(pattern: str) -> re.Pattern:
    """
    Convert a glob pattern (supporting '**') to a compiled regex matching POSIX-style
    relative paths. Used to filter remote 'find' output against a glob pattern, since
    the compute session interface has no native glob primitive.
    """
    regex_parts = []
    i = 0
    while i < len(pattern):
        if pattern[i : i + 3] == "**/":
            regex_parts.append("(?:.*/)?")
            i += 3
        elif pattern[i : i + 2] == "**":
            regex_parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            regex_parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            regex_parts.append("[^/]")
            i += 1
        else:
            regex_parts.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(regex_parts) + "$")


# Default directories/files to skip during glob and grep
_SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
}


async def internal_glob(
    pattern: str,
    path: str | None = None,
    max_results: int = 1000,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Find files matching a glob pattern within the workspace.

    Supports recursive patterns like **/*.py, src/**/*.ts, etc.

    Args:
        pattern: Glob pattern to match (e.g. "**/*.py", "src/**/*.ts")
        path: Directory to search in (defaults to workspace root)
        max_results: Maximum number of files to return (default 1000)
        config: Optional configuration dictionary

    Returns:
        Dictionary containing matching file paths sorted by modification time
    """
    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        search_dir = path if path else (_cs.base_path or ".")
        result = await _cs.exec_command(["find", search_dir, "-type", "f"])
        if not result.get("success"):
            return {"error": result.get("error") or f"Path not found: {search_dir}"}

        matcher = _glob_pattern_to_regex(pattern)
        all_files = [f.strip() for f in result["output"].splitlines() if f.strip()]

        matches: list[dict[str, Any]] = []
        total_found = 0
        for file_path in all_files:
            rel_path = os.path.relpath(file_path, search_dir)
            parts = rel_path.split(os.sep)
            if any(part in _SKIP_DIRS for part in parts):
                continue
            if not matcher.match(rel_path):
                continue
            total_found += 1
            if len(matches) < max_results:
                matches.append({"path": file_path, "name": os.path.basename(file_path)})

        return {
            "pattern": pattern,
            "directory": str(search_dir),
            "matches": matches,
            "total_matches": len(matches),
            "total_found": total_found,
            "truncated": total_found > max_results,
        }

    try:
        workspace_path = _get_workspace_path(config)
        if not workspace_path:
            return {"error": "No workspace path configured."}

        search_dir = path if path else workspace_path

        # Validate directory
        is_valid, error_msg = _validate_directory_path(search_dir, config=config)
        if not is_valid:
            return {"error": error_msg}

        search_path = Path(search_dir)
        matches: list[dict[str, Any]] = []
        total_found = 0

        for file_path in search_path.glob(pattern):
            # Skip hidden/unwanted directories
            parts = file_path.relative_to(search_path).parts
            if any(part in _SKIP_DIRS for part in parts):
                continue

            if file_path.is_file():
                total_found += 1
                if len(matches) < max_results:
                    try:
                        stat = file_path.stat()
                        matches.append(
                            {
                                "path": str(file_path),
                                "name": file_path.name,
                                "size": stat.st_size,
                                "modified": stat.st_mtime,
                            }
                        )
                    except OSError:
                        continue

        # Sort by modification time (most recent first)
        matches.sort(key=lambda x: x["modified"], reverse=True)

        return {
            "pattern": pattern,
            "directory": str(search_dir),
            "matches": matches,
            "total_matches": len(matches),
            "total_found": total_found,
            "truncated": total_found > max_results,
        }

    except Exception as e:
        logger.error(f"Error in internal_glob with pattern '{pattern}': {e}", exc_info=True)
        return {"error": f"Failed to glob files: {str(e)}"}


async def internal_grep(
    pattern: str,
    path: str | None = None,
    include: str | None = None,
    case_insensitive: bool = False,
    max_results: int = 50,
    context_lines: int = 2,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Search file contents for a regex pattern within the workspace.

    Walks the directory tree and searches file contents using regex, similar to
    ripgrep. Returns matching files with line numbers and content snippets.

    Args:
        pattern: Regex pattern to search for in file contents
        path: File or directory to search in (defaults to workspace root)
        include: Glob pattern to filter files (e.g. "*.py", "*.ts")
        case_insensitive: Whether to perform case-insensitive search
        max_results: Maximum number of matches to return (default 50)
        context_lines: Number of context lines around each match (default 2)
        config: Optional configuration dictionary

    Returns:
        Dictionary containing matches with file paths, line numbers, and snippets
    """
    # Compile regex up front (shared between local and remote execution)
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error as e:
        return {"error": f"Invalid regex pattern: {str(e)}"}

    def _scan_lines(lines: list[str]) -> list[dict[str, Any]]:
        """Scan a list of file lines for the pattern, building context snippets."""
        file_matches = []
        for line_num, line in enumerate(lines, start=1):
            if compiled.search(line):
                start = max(0, line_num - 1 - context_lines)
                end = min(len(lines), line_num + context_lines)
                context = []
                for ctx_idx in range(start, end):
                    prefix = ">" if ctx_idx == line_num - 1 else " "
                    context.append(f"{prefix} {ctx_idx + 1}: {lines[ctx_idx].rstrip()}")

                file_matches.append(
                    {
                        "line": line_num,
                        "content": line.rstrip(),
                        "context": "\n".join(context),
                    }
                )
        return file_matches

    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    if _cs is not None and _cs.is_remote:
        search_path_str = path if path else (_cs.base_path or ".")

        find_result = await _cs.exec_command(["find", search_path_str, "-type", "f"])
        if not find_result.get("success"):
            return {"error": find_result.get("error") or f"Path not found: {search_path_str}"}

        candidate_files = [f.strip() for f in find_result["output"].splitlines() if f.strip()]

        matches: list[dict[str, Any]] = []
        files_searched = 0
        files_with_matches = 0

        for file_path in candidate_files:
            if len(matches) >= max_results:
                break

            rel_parts = os.path.relpath(file_path, search_path_str).split(os.sep)
            if any(part in _SKIP_DIRS for part in rel_parts):
                continue

            file_name = os.path.basename(file_path)
            if include and not fnmatch.fnmatch(file_name, include):
                continue

            ext = os.path.splitext(file_name)[1].lower()
            if ext in ALLOWED_EXTENSIONS["media"]:
                continue

            read_result = await _cs.read_file(file_path, start_line=1, max_lines=10_000_000)
            if not read_result.get("success"):
                continue

            files_searched += 1
            lines = read_result["content"].splitlines(keepends=True)
            file_matches = _scan_lines(lines)
            if file_matches:
                files_with_matches += 1
                for m in file_matches:
                    if len(matches) >= max_results:
                        break
                    matches.append({"file": file_path, **m})

        return {
            "pattern": pattern,
            "path": search_path_str,
            "include": include,
            "case_insensitive": case_insensitive,
            "matches": matches,
            "total_matches": len(matches),
            "files_searched": files_searched,
            "files_with_matches": files_with_matches,
            "truncated": len(matches) >= max_results,
        }

    try:
        workspace_path = _get_workspace_path(config)
        if not workspace_path:
            return {"error": "No workspace path configured."}

        search_path_str = path if path else workspace_path

        # Validate path
        search_path = Path(search_path_str)
        if search_path.is_file():
            is_valid, error_msg = _validate_file_path(search_path_str, config=config)
            if not is_valid:
                return {"error": error_msg}
            files_to_search = [search_path]
        elif search_path.is_dir():
            is_valid, error_msg = _validate_directory_path(search_path_str, config=config)
            if not is_valid:
                return {"error": error_msg}
            files_to_search = None  # Will walk directory
        else:
            return {"error": f"Path not found: {search_path_str}"}

        matches: list[dict[str, Any]] = []
        files_searched = 0
        files_with_matches = 0

        def _search_file(file_path: Path) -> list[dict[str, Any]]:
            """Search a single file for the pattern."""
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except (OSError, UnicodeDecodeError):
                return []
            return _scan_lines(lines)

        if files_to_search is not None:
            # Search specific file
            for fp in files_to_search:
                files_searched += 1
                file_matches = _search_file(fp)
                if file_matches:
                    files_with_matches += 1
                    for m in file_matches:
                        if len(matches) >= max_results:
                            break
                        matches.append({"file": str(fp), **m})
        else:
            # Walk directory
            for root, dirs, files in os.walk(search_path_str):
                # Skip unwanted directories in-place
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]

                for file_name in files:
                    if len(matches) >= max_results:
                        break

                    # Apply include filter
                    if include and not fnmatch.fnmatch(file_name, include):
                        continue

                    file_path = Path(root) / file_name

                    # Skip binary files by checking extension
                    ext = file_path.suffix.lower()
                    if ext in ALLOWED_EXTENSIONS["media"]:
                        continue

                    files_searched += 1
                    file_matches = _search_file(file_path)
                    if file_matches:
                        files_with_matches += 1
                        for m in file_matches:
                            if len(matches) >= max_results:
                                break
                            matches.append({"file": str(file_path), **m})

                if len(matches) >= max_results:
                    break

        return {
            "pattern": pattern,
            "path": search_path_str,
            "include": include,
            "case_insensitive": case_insensitive,
            "matches": matches,
            "total_matches": len(matches),
            "files_searched": files_searched,
            "files_with_matches": files_with_matches,
            "truncated": len(matches) >= max_results,
        }

    except Exception as e:
        logger.error(f"Error in internal_grep with pattern '{pattern}': {e}", exc_info=True)
        return {"error": f"Failed to grep files: {str(e)}"}


async def internal_notebook_edit(
    notebook_path: str,
    cell_number: int,
    new_source: str = "",
    cell_type: str | None = None,
    edit_mode: str = "replace",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Edit a Jupyter notebook cell.

    Supports replacing, inserting, or deleting cells in .ipynb files.

    Args:
        notebook_path: Path to the .ipynb file
        cell_number: 0-indexed cell number to edit
        new_source: New source content for the cell (ignored for delete mode)
        cell_type: Cell type ("code" or "markdown"). Defaults to existing cell type.
        edit_mode: Edit mode - "replace", "insert", or "delete" (default: "replace")
        config: Optional configuration dictionary

    Returns:
        Dictionary indicating success or error
    """
    # Route to remote compute session when configured
    from src.services.compute.resolver import get_compute_session_from_config

    _cs = await get_compute_session_from_config(config)
    is_remote = _cs is not None and _cs.is_remote

    try:
        # Validate .ipynb extension
        if not notebook_path.lower().endswith(".ipynb"):
            return {"error": "File must have .ipynb extension"}

        # Validate edit_mode first
        if edit_mode not in ("replace", "insert", "delete"):
            return {"error": f"Invalid edit_mode: {edit_mode}. Must be 'replace', 'insert', or 'delete'."}

        # Validate file path based on edit mode
        if is_remote:
            file_exists = await _cs.file_exists(notebook_path)
            if edit_mode in ("replace", "delete") and not file_exists:
                return {"error": f"File not found: {notebook_path}"}
        else:
            file_exists = os.path.exists(notebook_path)
            if edit_mode in ("replace", "delete"):
                # File must exist for replace/delete
                is_valid, error_msg = _validate_file_path(notebook_path, must_exist=True, config=config)
                if not is_valid:
                    return {"error": error_msg}
            else:
                # For insert, file may or may not exist, but path must be valid within workspace
                is_valid, error_msg = _validate_file_path(notebook_path, must_exist=False, config=config)
                if not is_valid:
                    return {"error": error_msg}

        if cell_type and cell_type not in ("code", "markdown"):
            return {"error": f"Invalid cell_type: {cell_type}. Must be 'code' or 'markdown'."}

        # Read existing notebook or create minimal structure
        if file_exists and is_remote:
            read_result = await _cs.read_file(notebook_path, start_line=1, max_lines=10_000_000)
            if not read_result.get("success"):
                return {"error": read_result.get("error") or f"Failed to read {notebook_path}"}
            try:
                notebook = json.loads(read_result["content"])
            except json.JSONDecodeError as e:
                return {"error": f"Failed to parse notebook JSON: {str(e)}"}
        elif file_exists:
            try:
                with open(notebook_path, encoding="utf-8") as f:
                    notebook = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                return {"error": f"Failed to parse notebook JSON: {str(e)}"}
        else:
            # Create new notebook for insert mode
            notebook = {
                "nbformat": 4,
                "nbformat_minor": 2,
                "metadata": {
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python",
                        "name": "python3",
                    },
                    "language_info": {"name": "python", "version": "3.11.0"},
                },
                "cells": [],
            }

        # Validate notebook structure
        if "cells" not in notebook:
            return {"error": "Invalid notebook format: missing 'cells' key."}

        cells = notebook["cells"]
        num_cells = len(cells)

        # Build new cell object with proper source line handling
        def _make_cell(source: str, ctype: str) -> dict:
            # Use splitlines with keepends to preserve line structure
            # Jupyter expects each line as a separate string, with newlines preserved
            lines = source.splitlines(keepends=True)
            # If source doesn't end with newline, last line won't have one (which is correct)
            if not lines:
                lines = [""]
            cell = {
                "cell_type": ctype,
                "metadata": {},
                "source": lines,
            }
            if ctype == "code":
                cell["execution_count"] = None
                cell["outputs"] = []
            return cell

        if edit_mode == "replace":
            if num_cells == 0:
                return {"error": "Cannot replace cell in empty notebook. Use 'insert' mode instead."}
            if cell_number < 0 or cell_number >= num_cells:
                return {"error": f"Cell number {cell_number} out of range. Valid range: 0 to {num_cells - 1}."}

            target_type = cell_type or cells[cell_number].get("cell_type", "code")
            cells[cell_number] = _make_cell(new_source, target_type)
            action = "replaced"

        elif edit_mode == "insert":
            if cell_number < 0 or cell_number > num_cells:
                return {"error": f"Cell number {cell_number} out of range for insert. Valid range: 0 to {num_cells}."}

            insert_type = cell_type or "code"
            cells.insert(cell_number, _make_cell(new_source, insert_type))
            action = "inserted"

        elif edit_mode == "delete":
            if num_cells == 0:
                return {"error": "Cannot delete cell from empty notebook."}
            if cell_number < 0 or cell_number >= num_cells:
                return {"error": f"Cell number {cell_number} out of range. Valid range: 0 to {num_cells - 1}."}

            cells.pop(cell_number)
            action = "deleted"

        if is_remote:
            write_result = await _cs.write_file(notebook_path, json.dumps(notebook, indent=1, ensure_ascii=False))
            if not write_result.get("success"):
                return {"error": write_result.get("error") or f"Failed to write {notebook_path}"}
        else:
            # Create parent directories if needed
            parent_dir = os.path.dirname(notebook_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            # Write back
            with open(notebook_path, "w", encoding="utf-8") as f:
                json.dump(notebook, f, indent=1, ensure_ascii=False)

        return {
            "success": True,
            "path": notebook_path,
            "action": action,
            "cell_number": cell_number,
            "total_cells": len(cells),
        }

    except Exception as e:
        logger.error(f"Error editing notebook {notebook_path}: {e}", exc_info=True)
        return {"error": f"Failed to edit notebook: {str(e)}"}
