"""Tests for cloud provider validate-on-save credential checks."""

import json

import pytest

from src.services.cloud_providers.credential_validators import (
    validate_aws_credentials,
    validate_azure_credentials,
    validate_digitalocean_credentials,
    validate_gcp_credentials,
)


class TestValidateAWSCredentials:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        class _FakeSTS:
            def get_caller_identity(self):
                return {"Account": "123456789012", "Arn": "arn:aws:iam::123456789012:user/test"}

        class _FakeSession:
            def __init__(self, **kwargs):
                pass

            def client(self, service_name):
                assert service_name == "sts"
                return _FakeSTS()

        import boto3

        monkeypatch.setattr(boto3, "Session", _FakeSession)

        await validate_aws_credentials(access_key_id="AKIA...", secret_access_key="secret", region="us-east-1")

    @pytest.mark.asyncio
    async def test_failure_raises_value_error(self, monkeypatch):
        from botocore.exceptions import ClientError

        class _FakeSTS:
            def get_caller_identity(self):
                raise ClientError(
                    {"Error": {"Code": "InvalidClientTokenId", "Message": "invalid"}}, "GetCallerIdentity"
                )

        class _FakeSession:
            def __init__(self, **kwargs):
                pass

            def client(self, service_name):
                return _FakeSTS()

        import boto3

        monkeypatch.setattr(boto3, "Session", _FakeSession)

        with pytest.raises(ValueError, match="AWS credentials"):
            await validate_aws_credentials(access_key_id="bad", secret_access_key="bad", region="us-east-1")


class TestValidateGCPCredentials:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        import httpx

        from src.services.cloud_providers import credential_validators

        async def _fake_get_token(service_account, scope):
            return "fake-token"

        class _FakeResponse:
            status_code = 200
            is_success = True
            text = "{}"

            def json(self):
                return {"projectId": "my-project"}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(credential_validators, "_get_gcp_access_token", _fake_get_token)
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        sa_json = json.dumps({"client_email": "sa@my-project.iam.gserviceaccount.com", "private_key": "key"})
        await validate_gcp_credentials(service_account_json=sa_json, project_id="my-project")

    @pytest.mark.asyncio
    async def test_invalid_json_raises_value_error(self):
        with pytest.raises(ValueError, match="valid JSON"):
            await validate_gcp_credentials(service_account_json="not json", project_id="my-project")

    @pytest.mark.asyncio
    async def test_project_lookup_failure_raises_value_error(self, monkeypatch):
        import httpx

        from src.services.cloud_providers import credential_validators

        async def _fake_get_token(service_account, scope):
            return "fake-token"

        class _FakeResponse:
            status_code = 403
            is_success = False
            text = "permission denied"

            def json(self):
                return {}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(credential_validators, "_get_gcp_access_token", _fake_get_token)
        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        sa_json = json.dumps({"client_email": "sa@my-project.iam.gserviceaccount.com", "private_key": "key"})
        with pytest.raises(ValueError, match="GCP credentials"):
            await validate_gcp_credentials(service_account_json=sa_json, project_id="my-project")


class TestValidateAzureCredentials:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        import httpx

        class _FakeResponse:
            is_success = True
            status_code = 200
            text = "{}"

            def json(self):
                return {"access_token": "tok"}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        await validate_azure_credentials(
            tenant_id="tenant-1", client_id="app-1", client_secret="secret-1", subscription_id="sub-1"
        )

    @pytest.mark.asyncio
    async def test_failure_raises_value_error(self, monkeypatch):
        import httpx

        class _FakeResponse:
            is_success = False
            status_code = 401
            text = "invalid_client"

            def json(self):
                return {}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        with pytest.raises(ValueError, match="Azure credentials"):
            await validate_azure_credentials(
                tenant_id="tenant-1", client_id="bad", client_secret="bad", subscription_id="sub-1"
            )


class TestValidateDigitalOceanCredentials:
    @pytest.mark.asyncio
    async def test_success(self, monkeypatch):
        import httpx

        class _FakeResponse:
            is_success = True
            status_code = 200
            text = "{}"

            def json(self):
                return {"account": {"status": "active"}}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        await validate_digitalocean_credentials(token="do-pat")

    @pytest.mark.asyncio
    async def test_failure_raises_value_error(self, monkeypatch):
        import httpx

        class _FakeResponse:
            is_success = False
            status_code = 401
            text = "Unable to authenticate"

            def json(self):
                return {}

        class _FakeAsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url, **kwargs):
                return _FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        with pytest.raises(ValueError, match="DigitalOcean"):
            await validate_digitalocean_credentials(token="bad-token")
