"""Tests for _validate_cloud_provider_config() live validate-on-save dispatch."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.controllers.oauth.apps import _validate_cloud_provider_config


class TestValidateCloudProviderConfig:
    @pytest.mark.asyncio
    async def test_non_cloud_provider_skips_validation(self):
        # Should return immediately without attempting any network call.
        await _validate_cloud_provider_config("github", "oauth", None, None, {})

    @pytest.mark.asyncio
    async def test_aws_success_calls_validator(self):
        with patch(
            "src.controllers.oauth.apps.validate_aws_credentials", new=AsyncMock(return_value=None)
        ) as mock_validate:
            await _validate_cloud_provider_config("aws", "api_token", "AKIA...", "secret", {"region": "us-west-2"})

            mock_validate.assert_called_once_with(
                access_key_id="AKIA...", secret_access_key="secret", region="us-west-2"
            )

    @pytest.mark.asyncio
    async def test_aws_failure_raises_http_exception(self):
        with patch(
            "src.controllers.oauth.apps.validate_aws_credentials",
            new=AsyncMock(side_effect=ValueError("AWS credentials are invalid or expired.")),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await _validate_cloud_provider_config("aws", "api_token", "bad", "bad", {})

            assert exc_info.value.status_code == 400
            assert "AWS credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_gcp_success_calls_validator(self):
        with patch(
            "src.controllers.oauth.apps.validate_gcp_credentials", new=AsyncMock(return_value=None)
        ) as mock_validate:
            await _validate_cloud_provider_config("gcp", "api_token", None, "{}", {"project_id": "proj-1"})

            mock_validate.assert_called_once_with(service_account_json="{}", project_id="proj-1")

    @pytest.mark.asyncio
    async def test_azure_success_calls_validator(self):
        with patch(
            "src.controllers.oauth.apps.validate_azure_credentials", new=AsyncMock(return_value=None)
        ) as mock_validate:
            await _validate_cloud_provider_config(
                "azure",
                "api_token",
                "app-1",
                "secret-1",
                {"azure_tenant_id": "tenant-1", "subscription_id": "sub-1"},
            )

            mock_validate.assert_called_once_with(
                tenant_id="tenant-1", client_id="app-1", client_secret="secret-1", subscription_id="sub-1"
            )

    @pytest.mark.asyncio
    async def test_digitalocean_success_calls_validator(self):
        with patch(
            "src.controllers.oauth.apps.validate_digitalocean_credentials", new=AsyncMock(return_value=None)
        ) as mock_validate:
            await _validate_cloud_provider_config("digitalocean", "api_token", None, "do-pat", {})

            mock_validate.assert_called_once_with(token="do-pat")

    @pytest.mark.asyncio
    async def test_wrong_auth_method_skips_validation(self):
        # A cloud provider row saved with a non-api_token auth_method (shouldn't normally
        # happen, but must not crash) skips the live check rather than erroring.
        await _validate_cloud_provider_config("aws", "oauth", "id", "secret", {})
