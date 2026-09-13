from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.agent_api_key import AgentApiKey
from src.models.agent_api_usage import AgentApiUsage
from src.services.agent_api.api_key_service import AgentApiKeyService


class TestAgentApiKeyService:
    @pytest.fixture
    def mock_db_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def mock_agent(self):
        agent = MagicMock(spec=Agent)
        agent.id = uuid4()
        return agent

    @pytest.fixture
    def mock_api_key(self):
        key = MagicMock(spec=AgentApiKey)
        key.id = uuid4()
        key.api_key = "hashed_key"
        key.rate_limit_per_minute = 60
        key.rate_limit_per_hour = 1000
        key.rate_limit_per_day = 10000
        key.permissions = ["*"]
        key.allowed_ips = []
        key.allowed_origins = []
        key.is_active = True
        key.expires_at = None
        return key

    def test_generate_api_key(self):
        with patch("src.services.agent_api.api_key_service.encrypt_value") as mock_encrypt:
            mock_encrypt.return_value = "hashed_key"
            full_key, hashed_key = AgentApiKeyService.generate_api_key(prefix="test_")

            assert full_key.startswith("test_")
            assert len(full_key) > 20
            assert hashed_key == "hashed_key"
            mock_encrypt.assert_called_once_with(full_key)

    @pytest.mark.asyncio
    async def test_create_api_key_success(self, mock_db_session, mock_agent):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_agent
        mock_db_session.execute.return_value = mock_result

        with patch("src.services.agent_api.api_key_service.encrypt_value") as mock_encrypt:
            mock_encrypt.return_value = "hashed_key"

            api_key, plain_key = await AgentApiKeyService.create_api_key(
                mock_db_session, agent_id=mock_agent.id, tenant_id=uuid4(), name="Test Key", permissions=["chat"]
            )

            assert api_key.key_name == "Test Key"
            assert api_key.permissions == ["chat"]
            assert api_key.api_key == "hashed_key"
            assert plain_key.startswith("sk_live_")

            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_api_key_no_agent_validation(self, mock_db_session):
        """Service no longer validates agent existence — that check lives in the controller."""
        with patch("src.services.agent_api.api_key_service.encrypt_value", return_value="hashed"):
            api_key, plain_key = await AgentApiKeyService.create_api_key(
                mock_db_session, agent_id=uuid4(), tenant_id=uuid4(), name="Test Key", permissions=[]
            )
        assert api_key.key_name == "Test Key"
        assert plain_key.startswith("sk_live_")

    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, mock_db_session, mock_api_key):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_api_key]
        mock_db_session.execute.return_value = mock_result

        with patch("src.services.agent_api.api_key_service.decrypt_value") as mock_decrypt:
            mock_decrypt.return_value = "sk_test_abcdefghijklmn_key"

            result = await AgentApiKeyService.validate_api_key(mock_db_session, "sk_test_abcdefghijklmn_key")

            assert result == mock_api_key
            assert mock_api_key.last_used_at is not None
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid_format(self, mock_db_session):
        assert await AgentApiKeyService.validate_api_key(mock_db_session, "invalid") is None

    @pytest.mark.asyncio
    async def test_validate_api_key_not_found(self, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        assert await AgentApiKeyService.validate_api_key(mock_db_session, "sk_test_abcdefghijklmn_key") is None

    @pytest.mark.asyncio
    async def test_validate_api_key_expired(self, mock_db_session, mock_api_key):
        mock_api_key.expires_at = datetime.now(UTC) - timedelta(days=1)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_api_key]
        mock_db_session.execute.return_value = mock_result

        with patch("src.services.agent_api.api_key_service.decrypt_value") as mock_decrypt:
            mock_decrypt.return_value = "sk_test_abcdefghijklmn_key"
            assert await AgentApiKeyService.validate_api_key(mock_db_session, "sk_test_abcdefghijklmn_key") is None

    def test_validate_ip_address(self, mock_api_key):
        mock_api_key.allowed_ips = []
        assert AgentApiKeyService.validate_ip_address(mock_api_key, "1.2.3.4") is True

        mock_api_key.allowed_ips = ["1.2.3.4"]
        assert AgentApiKeyService.validate_ip_address(mock_api_key, "1.2.3.4") is True
        assert AgentApiKeyService.validate_ip_address(mock_api_key, "5.6.7.8") is False

        mock_api_key.allowed_ips = ["*"]
        assert AgentApiKeyService.validate_ip_address(mock_api_key, "5.6.7.8") is True

    def test_validate_origin(self, mock_api_key):
        mock_api_key.allowed_origins = []
        assert AgentApiKeyService.validate_origin(mock_api_key, "https://example.com") is True

        mock_api_key.allowed_origins = ["example.com"]
        assert AgentApiKeyService.validate_origin(mock_api_key, "https://example.com") is True
        assert AgentApiKeyService.validate_origin(mock_api_key, "https://other.com") is False

        mock_api_key.allowed_origins = ["*.example.com"]
        assert AgentApiKeyService.validate_origin(mock_api_key, "https://sub.example.com") is True

        # Missing origin
        assert AgentApiKeyService.validate_origin(mock_api_key, None) is False

    def test_check_permission(self, mock_api_key):
        mock_api_key.permissions = ["*"]
        assert AgentApiKeyService.check_permission(mock_api_key, "any") is True

        mock_api_key.permissions = ["chat"]
        assert AgentApiKeyService.check_permission(mock_api_key, "chat") is True
        assert AgentApiKeyService.check_permission(mock_api_key, "files") is False

    def test_check_rate_limit(self, mock_api_key):
        """Test rate limiting via Redis-backed service."""
        mock_redis = MagicMock()

        with patch("src.services.agent_api.api_key_service._get_redis_client", return_value=mock_redis):
            # No rate limit exceeded - all counts return 0
            mock_redis.eval.return_value = 0

            allowed, error = AgentApiKeyService.check_rate_limit(mock_api_key)
            assert allowed is True
            assert error is None

            # Test minute limit exceeded
            mock_api_key.rate_limit_per_minute = 1
            mock_redis.eval.return_value = 1  # minute exceeded, hour ok, day ok

            allowed, error = AgentApiKeyService.check_rate_limit(mock_api_key)
            assert allowed is False
            assert "Rate limit exceeded" in error

    @pytest.mark.asyncio
    async def test_track_usage(self, mock_db_session):
        api_key_id = uuid4()
        result = await AgentApiKeyService.track_usage(mock_db_session, api_key_id, "endpoint", "GET", 200, 100)

        assert isinstance(result, AgentApiUsage)
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, mock_db_session, mock_api_key):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_db_session.execute.return_value = mock_result

        assert await AgentApiKeyService.revoke_api_key(mock_db_session, mock_api_key.id) is True
        assert mock_api_key.is_active is False
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_api_key_not_found(self, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        assert await AgentApiKeyService.revoke_api_key(mock_db_session, uuid4()) is False

    @pytest.mark.asyncio
    async def test_update_api_key(self, mock_db_session, mock_api_key):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_db_session.execute.return_value = mock_result

        updated = await AgentApiKeyService.update_api_key(mock_db_session, mock_api_key.id, name="New Name")

        assert updated.key_name == "New Name"
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_api_key_not_found(self, mock_db_session):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        assert await AgentApiKeyService.update_api_key(mock_db_session, uuid4(), name="New") is None

    @pytest.mark.asyncio
    async def test_list_api_keys(self, mock_db_session, mock_api_key):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_api_key]
        mock_db_session.execute.return_value = mock_result

        keys = await AgentApiKeyService.list_api_keys(mock_db_session, uuid4())
        assert keys == [mock_api_key]

    @pytest.mark.asyncio
    async def test_get_usage_stats(self, mock_db_session):
        # Mock the sequence of db.execute calls
        # 1. Total requests count
        mock_total = MagicMock()
        mock_total.scalar.return_value = 100

        # 2. Successful requests count
        mock_successful = MagicMock()
        mock_successful.scalar.return_value = 90

        # 3. Average response time
        mock_avg = MagicMock()
        mock_avg.scalar.return_value = 150.5

        # 4. Total tokens
        mock_tokens = MagicMock()
        mock_tokens.scalar.return_value = 5000

        # 5. Endpoint stats
        mock_endpoints = MagicMock()
        mock_endpoints.all.return_value = [("chat", 100)]

        mock_db_session.execute.side_effect = [mock_total, mock_successful, mock_avg, mock_tokens, mock_endpoints]

        stats = await AgentApiKeyService.get_usage_stats(mock_db_session, uuid4())

        assert stats["total_requests"] == 100
        assert stats["successful_requests"] == 90
        assert stats["failed_requests"] == 10
        assert stats["avg_response_time_ms"] == 150.5
        assert stats["total_tokens_used"] == 5000

    @pytest.mark.asyncio
    async def test_validate_api_key_exception(self, mock_db_session, mock_api_key):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_api_key]
        mock_db_session.execute.return_value = mock_result

        with patch("src.services.agent_api.api_key_service.decrypt_value", side_effect=Exception("Decrypt error")):
            assert await AgentApiKeyService.validate_api_key(mock_db_session, "sk_test_abcdefghijklmn_key") is None

    def test_validate_origin_wildcard(self, mock_api_key):
        mock_api_key.allowed_origins = ["*"]
        assert AgentApiKeyService.validate_origin(mock_api_key, "https://any.com") is True

    def test_check_rate_limit_hour_day(self, mock_api_key):
        """Test hourly and daily rate limiting via Redis."""
        mock_redis = MagicMock()

        with patch("src.services.agent_api.api_key_service._get_redis_client", return_value=mock_redis):
            # Hour limit exceeded
            mock_api_key.rate_limit_per_hour = 1
            mock_redis.eval.return_value = 2  # minute ok, hour exceeded, day ok

            allowed, error = AgentApiKeyService.check_rate_limit(mock_api_key)
            assert allowed is False
            assert "requests per hour" in error

            # Day limit exceeded
            mock_api_key.rate_limit_per_hour = 1000  # reset
            mock_api_key.rate_limit_per_day = 1
            mock_redis.eval.return_value = 3  # minute ok, hour ok, day exceeded

            allowed, error = AgentApiKeyService.check_rate_limit(mock_api_key)
            assert allowed is False
            assert "requests per day" in error

    @pytest.mark.asyncio
    async def test_update_api_key_all_fields(self, mock_db_session, mock_api_key):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_api_key
        mock_db_session.execute.return_value = mock_result

        expires = datetime.now(UTC)
        await AgentApiKeyService.update_api_key(
            mock_db_session,
            mock_api_key.id,
            permissions=["new"],
            rate_limit_per_minute=10,
            rate_limit_per_hour=100,
            rate_limit_per_day=1000,
            allowed_ips=["1.1.1.1"],
            allowed_origins=["test.com"],
            expires_at=expires,
        )

        assert mock_api_key.permissions == ["new"]
        assert mock_api_key.rate_limit_per_minute == 10
        assert mock_api_key.allowed_ips == ["1.1.1.1"]
        assert mock_api_key.expires_at == expires
