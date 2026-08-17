from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.data_source import DataSource
from src.services.data_sources.slack_connector import SlackConnector


class TestSlackConnectorAccessToken:
    @pytest.fixture
    def mock_db_session(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_data_source(self):
        ds = MagicMock(spec=DataSource)
        ds.oauth_app_id = None
        ds.slack_bot_id = None
        ds.access_token_encrypted = None
        ds.oauth_app = None
        ds.config = {}
        ds.tenant_id = "tenant-123"
        ds.id = "ds-123"
        ds.name = "Test Slack Source"
        return ds

    @pytest.fixture
    def connector(self, mock_data_source, mock_db_session):
        return SlackConnector(mock_data_source, mock_db_session)

    @pytest.mark.asyncio
    async def test_get_access_token_uses_slack_bot_when_linked(self, connector, mock_db_session):
        connector.data_source.slack_bot_id = "slack-bot-123"

        mock_slack_bot = MagicMock()
        mock_slack_bot.slack_bot_token = "encrypted-bot-token"

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_slack_bot
        mock_db_session.execute.return_value = result_mock

        with patch("src.services.agents.security.decrypt_value", return_value="xoxb-decrypted-token") as mock_decrypt:
            token = await connector._get_access_token()

        assert token == "xoxb-decrypted-token"
        mock_decrypt.assert_called_once_with("encrypted-bot-token")

    @pytest.mark.asyncio
    async def test_get_access_token_falls_back_when_no_slack_bot(self, connector):
        connector.data_source.slack_bot_id = None
        connector.data_source.access_token_encrypted = "encrypted-direct-token"

        with patch("src.services.agents.security.decrypt_value", return_value="xoxb-direct-token") as mock_decrypt:
            token = await connector._get_access_token()

        assert token == "xoxb-direct-token"
        mock_decrypt.assert_called_once_with("encrypted-direct-token")
