"""Live, read-only validate-on-save checks for the 4 cloud provider integrations.

Called from controllers/oauth/apps.py at create/update time so an invalid credential is
rejected immediately with HTTPException(400, ...) instead of being stored silently broken.
Each function raises ValueError with a user-actionable message on failure.
"""

import asyncio
import json
import time
from typing import Any

import httpx
import jwt as pyjwt

_GCP_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GCP_SCOPE = "https://www.googleapis.com/auth/cloud-platform.read-only"


async def validate_aws_credentials(access_key_id: str, secret_access_key: str, region: str = "us-east-1") -> None:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

    def _check() -> None:
        session = boto3.Session(
            aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key, region_name=region
        )
        client = session.client("sts")
        client.get_caller_identity()

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _check)
    except (ClientError, NoCredentialsError, BotoCoreError) as e:
        raise ValueError(
            "AWS credentials are invalid or expired — please check the access key ID and secret access key."
        ) from e


async def _get_gcp_access_token(service_account: dict[str, Any], scope: str) -> str:
    now = int(time.time())
    claims = {
        "iss": service_account["client_email"],
        "scope": scope,
        "aud": _GCP_TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }
    signed = pyjwt.encode(claims, service_account["private_key"], algorithm="RS256")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _GCP_TOKEN_URL,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": signed},
        )
    if not resp.is_success:
        raise ValueError("GCP credentials are invalid or expired — please check the service account key.")
    return resp.json()["access_token"]


async def validate_gcp_credentials(service_account_json: str, project_id: str) -> None:
    try:
        service_account = json.loads(service_account_json)
    except (json.JSONDecodeError, TypeError) as e:
        raise ValueError("GCP service account key must be valid JSON.") from e

    token = await _get_gcp_access_token(service_account, _GCP_SCOPE)
    url = f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    if not resp.is_success:
        raise ValueError(
            f"GCP credentials could not access project '{project_id}' "
            f"(status {resp.status_code}) — check the service account's permissions and project_id."
        )


async def validate_azure_credentials(tenant_id: str, client_id: str, client_secret: str, subscription_id: str) -> None:
    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://management.azure.com/.default",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, data=data)
    if not resp.is_success:
        raise ValueError(
            "Azure credentials are invalid or expired — please check the tenant ID, client ID, and client secret."
        )


async def validate_digitalocean_credentials(token: str) -> None:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://api.digitalocean.com/v2/account", headers={"Authorization": f"Bearer {token}"})
    if not resp.is_success:
        raise ValueError("DigitalOcean token is invalid or expired — please check the personal access token.")
