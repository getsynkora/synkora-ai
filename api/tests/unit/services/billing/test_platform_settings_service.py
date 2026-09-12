from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.platform_settings import PlatformSettings
from src.services.billing.platform_settings_service import (
    PlatformSettingsService,
    invalidate_platform_settings_cache,
)


class TestPlatformSettingsService:
    @pytest.fixture(autouse=True)
    def _reset_settings_cache(self):
        # The service keeps a process-local cache of the settings singleton;
        # clear it before and after each test so tests don't leak state into
        # one another via that module-level cache.
        invalidate_platform_settings_cache()
        yield
        invalidate_platform_settings_cache()

    @pytest.fixture
    def mock_db(self):
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def service(self, mock_db):
        return PlatformSettingsService(mock_db)

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock(spec=PlatformSettings)
        settings.stripe_enabled = "false"
        settings.stripe_secret_key = None
        settings.stripe_publishable_key = None
        settings.stripe_webhook_secret = None
        return settings

    @pytest.mark.asyncio
    async def test_get_settings_existing(self, service, mock_db, mock_settings):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_settings
        mock_db.execute.return_value = mock_result

        result = await service.get_settings()

        assert result == mock_settings
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_settings_create_default(self, service, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.get_settings()

        assert isinstance(result, PlatformSettings)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_stripe_keys(self, service, mock_db, mock_settings):
        with (
            patch.object(service, "get_settings", new_callable=AsyncMock, return_value=mock_settings),
            patch("src.services.billing.platform_settings_service.encrypt_value", side_effect=lambda x: f"enc_{x}"),
        ):
            await service.update_stripe_keys(
                secret_key="sk_test", publishable_key="pk_test", webhook_secret="whsec_test"
            )

            assert mock_settings.stripe_secret_key == "enc_sk_test"
            assert mock_settings.stripe_publishable_key == "pk_test"
            assert mock_settings.stripe_webhook_secret == "enc_whsec_test"
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_enable_stripe_success(self, service, mock_db, mock_settings):
        mock_settings.stripe_secret_key = "enc_sk"
        mock_settings.stripe_publishable_key = "pk"

        with patch.object(service, "get_settings", new_callable=AsyncMock, return_value=mock_settings):
            await service.enable_stripe()

            assert mock_settings.stripe_enabled == "true"
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_enable_stripe_missing_keys(self, service, mock_db, mock_settings):
        mock_settings.stripe_secret_key = None

        with patch.object(service, "get_settings", new_callable=AsyncMock, return_value=mock_settings):
            with pytest.raises(ValueError, match="Stripe keys must be configured"):
                await service.enable_stripe()

    @pytest.mark.asyncio
    async def test_disable_stripe(self, service, mock_db, mock_settings):
        mock_settings.stripe_enabled = "true"

        with patch.object(service, "get_settings", new_callable=AsyncMock, return_value=mock_settings):
            await service.disable_stripe()

            assert mock_settings.stripe_enabled == "false"
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_stripe_secret_key(self, service, mock_settings):
        mock_settings.stripe_secret_key = "enc_sk"

        with (
            patch.object(service, "get_settings", new_callable=AsyncMock, return_value=mock_settings),
            patch("src.services.billing.platform_settings_service.decrypt_value", return_value="sk_test"),
        ):
            key = await service.get_stripe_secret_key()
            assert key == "sk_test"

    @pytest.mark.asyncio
    async def test_get_stripe_secret_key_none(self, service, mock_settings):
        mock_settings.stripe_secret_key = None

        with patch.object(service, "get_settings", new_callable=AsyncMock, return_value=mock_settings):
            assert await service.get_stripe_secret_key() is None

    @pytest.mark.asyncio
    async def test_is_stripe_configured(self, service, mock_settings):
        with patch.object(service, "get_settings", new_callable=AsyncMock, return_value=mock_settings):
            assert await service.is_stripe_configured() is False

            mock_settings.stripe_secret_key = "sk"
            mock_settings.stripe_publishable_key = "pk"
            mock_settings.stripe_webhook_secret = "wh"

            assert await service.is_stripe_configured() is True

    @pytest.mark.asyncio
    async def test_is_stripe_enabled(self, service, mock_settings):
        with patch.object(service, "get_settings", new_callable=AsyncMock, return_value=mock_settings):
            mock_settings.stripe_enabled = "false"
            assert await service.is_stripe_enabled() is False

            mock_settings.stripe_enabled = "true"
            # Assuming keys are set via is_stripe_configured check inside is_stripe_enabled
            # Let's mock is_stripe_configured instead
            with patch.object(service, "is_stripe_configured", new_callable=AsyncMock, return_value=True):
                assert await service.is_stripe_enabled() is True

    @pytest.mark.asyncio
    async def test_test_stripe_connection_success(self, service):
        with (
            patch.object(service, "is_stripe_configured", new_callable=AsyncMock, return_value=True),
            patch.object(service, "get_stripe_secret_key", new_callable=AsyncMock, return_value="sk_test"),
        ):
            # Mock stripe library
            mock_stripe = MagicMock()
            mock_account = MagicMock()
            mock_account.id = "acct_123"
            mock_account.business_profile.name = "Test Biz"
            mock_account.country = "US"
            mock_account.default_currency = "usd"
            mock_stripe.Account.retrieve.return_value = mock_account

            # Patch sys.modules to inject our mock stripe
            with patch.dict("sys.modules", {"stripe": mock_stripe}):
                result = await service.test_stripe_connection()

                assert result["success"] is True
                assert result["account_id"] == "acct_123"
                assert mock_stripe.api_key == "sk_test"

    @pytest.mark.asyncio
    async def test_test_stripe_connection_not_configured(self, service):
        with patch.object(service, "is_stripe_configured", new_callable=AsyncMock, return_value=False):
            with pytest.raises(ValueError, match="Stripe is not configured"):
                await service.test_stripe_connection()

    @pytest.mark.asyncio
    async def test_clear_stripe_keys(self, service, mock_db, mock_settings):
        with patch.object(service, "get_settings", new_callable=AsyncMock, return_value=mock_settings):
            await service.clear_stripe_keys()

            assert mock_settings.stripe_secret_key is None
            assert mock_settings.stripe_publishable_key is None
            assert mock_settings.stripe_webhook_secret is None
            assert mock_settings.stripe_enabled == "false"
            mock_db.commit.assert_called_once()
