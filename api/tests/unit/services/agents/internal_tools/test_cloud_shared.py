"""Tests for get_cloud_provider_config() shared cloud-credential resolution helper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.internal_tools.cloud_shared import get_cloud_provider_config


class _FakeRuntimeContext:
    agent_id = "agent-1"


def _make_db_mock(agent_tool=None, oauth_app=None):
    """Build a fake async db session whose execute() returns agent_tool then oauth_app."""
    db = AsyncMock()

    agent_tool_result = MagicMock()
    agent_tool_result.scalar_one_or_none.return_value = agent_tool

    oauth_app_result = MagicMock()
    oauth_app_result.scalar_one_or_none.return_value = oauth_app

    db.execute = AsyncMock(side_effect=[agent_tool_result, oauth_app_result])
    return db


def _fake_session_factory(db):
    class _CtxMgr:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *args):
            return False

    return lambda: _CtxMgr()


@pytest.mark.asyncio
async def test_success_returns_decrypted_config():
    agent_tool = MagicMock(oauth_app_id="oauth-app-1")
    oauth_app = MagicMock(client_id="client-abc", api_token="encrypted-secret", config={"region": "us-east-1"})
    db = _make_db_mock(agent_tool=agent_tool, oauth_app=oauth_app)

    with (
        patch(
            "src.services.agents.internal_tools.cloud_shared.get_async_session_factory",
            return_value=_fake_session_factory(db),
        ),
        patch(
            "src.services.agents.internal_tools.cloud_shared.decrypt_value",
            return_value="decrypted-secret",
        ),
    ):
        result = await get_cloud_provider_config(_FakeRuntimeContext(), "internal_aws_get_logs", "aws")

    assert result == {
        "client_id": "client-abc",
        "api_token": "decrypted-secret",
        "config": {"region": "us-east-1"},
    }


@pytest.mark.asyncio
async def test_no_agent_tool_raises_value_error():
    db = _make_db_mock(agent_tool=None, oauth_app=None)

    with patch(
        "src.services.agents.internal_tools.cloud_shared.get_async_session_factory",
        return_value=_fake_session_factory(db),
    ):
        with pytest.raises(ValueError, match="No OAuth app configured"):
            await get_cloud_provider_config(_FakeRuntimeContext(), "internal_aws_get_logs", "aws")


@pytest.mark.asyncio
async def test_agent_tool_without_oauth_app_id_raises_value_error():
    agent_tool = MagicMock(oauth_app_id=None)
    db = _make_db_mock(agent_tool=agent_tool, oauth_app=None)

    with patch(
        "src.services.agents.internal_tools.cloud_shared.get_async_session_factory",
        return_value=_fake_session_factory(db),
    ):
        with pytest.raises(ValueError, match="No OAuth app configured"):
            await get_cloud_provider_config(_FakeRuntimeContext(), "internal_gcp_get_logs", "gcp")


@pytest.mark.asyncio
async def test_no_matching_oauth_app_raises_value_error():
    agent_tool = MagicMock(oauth_app_id="oauth-app-1")
    db = _make_db_mock(agent_tool=agent_tool, oauth_app=None)

    with patch(
        "src.services.agents.internal_tools.cloud_shared.get_async_session_factory",
        return_value=_fake_session_factory(db),
    ):
        with pytest.raises(ValueError, match="No active azure OAuth app found"):
            await get_cloud_provider_config(_FakeRuntimeContext(), "internal_azure_get_logs", "azure")


@pytest.mark.asyncio
async def test_oauth_app_missing_api_token_raises_value_error():
    agent_tool = MagicMock(oauth_app_id="oauth-app-1")
    oauth_app = MagicMock(client_id="", api_token=None, config={})
    db = _make_db_mock(agent_tool=agent_tool, oauth_app=oauth_app)

    with patch(
        "src.services.agents.internal_tools.cloud_shared.get_async_session_factory",
        return_value=_fake_session_factory(db),
    ):
        with pytest.raises(ValueError, match="credential is missing"):
            await get_cloud_provider_config(_FakeRuntimeContext(), "internal_digitalocean_list_alerts", "digitalocean")
