"""
Tool Configuration Controller.

Handles API endpoints for managing tool configurations (API keys, settings, etc.)

SECURITY: All endpoints require authentication and admin role.
"""

import logging
import os
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_async_db
from ..middleware.auth_middleware import get_current_account, get_current_tenant_id, require_role
from ..models import Account, AccountRole
from ..services.agents.adk_tools import tool_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])


class ToolConfigRequest(BaseModel):
    """Request model for saving tool configuration."""

    tool: str
    config: dict[str, str]


class ToolTestRequest(BaseModel):
    """Request model for testing tool configuration."""

    pass


@router.get("/config")
async def get_tool_configurations(
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    _: None = Depends(require_role(AccountRole.ADMIN)),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, dict[str, str]]:
    """
    Get all tool configurations.

    Returns configurations with masked sensitive values.

    SECURITY: Requires ADMIN role.
    """
    logger.info(f"Tool config read by account={current_account.id} tenant={tenant_id}")
    try:
        configs = {}

        # Web Search
        configs["web_search"] = {"SERPAPI_KEY": _mask_value(os.getenv("SERPAPI_KEY", ""))}

        # GitHub
        configs["github"] = {"GITHUB_TOKEN": _mask_value(os.getenv("GITHUB_TOKEN", ""))}

        # Gmail
        configs["GMAIL"] = {"GMAIL_CREDENTIALS_PATH": os.getenv("GMAIL_CREDENTIALS_PATH", "")}

        # YouTube
        configs["youtube"] = {"YOUTUBE_API_KEY": _mask_value(os.getenv("YOUTUBE_API_KEY", ""))}

        return configs
    except Exception as e:
        logger.error(f"Failed to get tool configurations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/config")
async def save_tool_configuration(
    request: ToolConfigRequest,
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    _: None = Depends(require_role(AccountRole.ADMIN)),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """
    Save tool configuration.

    Updates environment variables and .env file.

    SECURITY: Requires ADMIN role. Only allows specific whitelisted config keys.
    """
    tool_name = request.tool
    config = request.config

    # SECURITY: Whitelist of allowed configuration keys
    allowed_keys = {
        "SERPAPI_KEY",
        "GITHUB_TOKEN",
        "GMAIL_CREDENTIALS_PATH",
        "YOUTUBE_API_KEY",
    }

    # Validate all keys are in whitelist
    for key in config.keys():
        if key not in allowed_keys:
            logger.warning(
                f"SECURITY: Rejected config key '{key}' from account={current_account.id} tenant={tenant_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Configuration key '{key}' is not allowed",
            )

    logger.info(f"Tool config update by account={current_account.id} tenant={tenant_id} tool={tool_name}")

    try:
        # Update environment variables
        for key, value in config.items():
            if value:  # Only set non-empty values
                os.environ[key] = value

        # Update .env file
        env_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")

        _update_env_file(env_file_path, config)

        logger.info(f"Tool configuration saved: {tool_name} by account={current_account.id}")

        return {"success": True, "message": f"Configuration for {tool_name} saved successfully"}
    except Exception as e:
        logger.error(f"Failed to save tool configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/test/{tool_name}")
async def test_tool_configuration(
    tool_name: str,
    config: dict[str, str],
    current_account: Account = Depends(get_current_account),
    tenant_id: UUID = Depends(get_current_tenant_id),
    _: None = Depends(require_role(AccountRole.ADMIN)),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """
    Test tool configuration by making a test API call.

    SECURITY: Requires ADMIN role.
    """
    logger.info(f"Tool test by account={current_account.id} tenant={tenant_id} tool={tool_name}")
    try:
        # Temporarily set environment variables for testing
        original_values = {}
        for key, value in config.items():
            original_values[key] = os.getenv(key)
            if value:
                os.environ[key] = value

        try:
            # Test based on tool type
            if tool_name == "web_search":
                result = await _test_web_search()
            elif tool_name == "github":
                result = await _test_github()
            elif tool_name == "youtube":
                result = await _test_youtube()
            elif tool_name == "GMAIL":
                result = await _test_gmail()
            else:
                result = {"success": False, "error": f"Unknown tool: {tool_name}"}
        finally:
            # Restore original environment variables
            for key, value in original_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        return result
    except Exception as e:
        logger.error(f"Failed to test tool configuration: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _mask_value(value: str) -> str:
    """Mask sensitive values for display."""
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def _update_env_file(file_path: str, config: dict[str, str]):
    """Update .env file with new configuration values."""
    try:
        # Read existing .env file
        if os.path.exists(file_path):
            with open(file_path) as f:
                lines = f.readlines()
        else:
            lines = []

        # Update or add configuration values
        updated_keys = set()
        new_lines = []

        for line in lines:
            line = line.rstrip()
            if "=" in line and not line.startswith("#"):
                key = line.split("=")[0].strip()
                if key in config:
                    # Update existing key
                    new_lines.append(f"{key}={config[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line + "\n")
            else:
                new_lines.append(line + "\n")

        # Add new keys that weren't in the file
        for key, value in config.items():
            if key not in updated_keys and value:
                new_lines.append(f"{key}={value}\n")

        # Write back to file
        with open(file_path, "w") as f:
            f.writelines(new_lines)

        logger.info(f"Updated .env file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to update .env file: {e}", exc_info=True)
        raise


async def _test_web_search() -> dict[str, Any]:
    """Test web search configuration."""
    try:
        result = await tool_registry.execute_tool("web_search", {"query": "test", "num_results": 1})

        if "error" in result:
            return {"success": False, "error": result["error"]}

        return {"success": True, "message": "Web search is working correctly"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _test_github() -> dict[str, Any]:
    """Test GitHub configuration."""
    try:
        result = await tool_registry.execute_tool("github_search_repos", {"query": "python", "limit": 1})

        if "error" in result:
            return {"success": False, "error": result["error"]}

        return {"success": True, "message": "GitHub integration is working correctly"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _test_youtube() -> dict[str, Any]:
    """Test YouTube configuration."""
    try:
        result = await tool_registry.execute_tool("youtube_search", {"query": "test", "max_results": 1})

        if "error" in result:
            return {"success": False, "error": result["error"]}

        return {"success": True, "message": "YouTube integration is working correctly"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _test_gmail() -> dict[str, Any]:
    """Test Gmail configuration."""
    try:
        # Just check if credentials file exists
        creds_path = os.getenv("GMAIL_CREDENTIALS_PATH")
        if not creds_path:
            return {"success": False, "error": "GMAIL_CREDENTIALS_PATH not set"}

        if not os.path.exists(creds_path):
            return {"success": False, "error": f"Credentials file not found: {creds_path}"}

        return {"success": True, "message": "Gmail credentials file found"}
    except Exception as e:
        return {"success": False, "error": str(e)}
