"""
GCP adapter — Cloud Logging, Cloud Monitoring, Compute Engine, Security Command Center.

Auth: the full service-account JSON key is stored as OAuthApp.api_token. We sign
a JWT with the service account's private key (RS256, via the already-present
`pyjwt` + `cryptography` — the same libraries used for GitHub App JWT auth in
credential_resolver.py) and exchange it for a bearer token at Google's OAuth2
token endpoint. Plain REST calls via httpx — no google-cloud-* SDKs.
"""

import json
import time
from typing import Any

import httpx
import jwt as pyjwt

from src.services.cloud_providers.base_adapter import CloudProviderAdapter

_SCOPE = "https://www.googleapis.com/auth/cloud-platform.read-only"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GCPAdapter(CloudProviderAdapter):
    def __init__(self, credentials: dict[str, Any]):
        super().__init__(credentials)
        self.service_account = json.loads(credentials["api_token"])
        config = credentials.get("config") or {}
        self.project_id = config.get("project_id") or self.service_account.get("project_id")

    async def _get_access_token(self) -> str:
        now = int(time.time())
        claims = {
            "iss": self.service_account["client_email"],
            "scope": _SCOPE,
            "aud": _TOKEN_URL,
            "iat": now,
            "exp": now + 3600,
        }
        signed = pyjwt.encode(claims, self.service_account["private_key"], algorithm="RS256")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": signed},
            )
        if not resp.is_success:
            raise ValueError("GCP credentials are invalid or expired — please reconnect in Integrations.")
        return resp.json()["access_token"]

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            return await client.request(method, url, headers=headers, **kwargs)

    async def get_logs(
        self, log_source: str, start_time: str, end_time: str, filter_query: str = "", limit: int = 100
    ) -> dict[str, Any]:
        try:
            filter_parts = [f'timestamp>="{start_time}"', f'timestamp<="{end_time}"']
            if log_source:
                filter_parts.append(f'logName="projects/{self.project_id}/logs/{log_source}"')
            if filter_query:
                filter_parts.append(filter_query)
            body = {
                "resourceNames": [f"projects/{self.project_id}"],
                "filter": " AND ".join(filter_parts),
                "pageSize": min(limit, 1000),
                "orderBy": "timestamp desc",
            }
            resp = await self._request("POST", "https://logging.googleapis.com/v2/entries:list", json=body)
            if not resp.is_success:
                return self._fail(f"GCP Logging error {resp.status_code}: {resp.text[:300]}")
            return self._ok(entries=resp.json().get("entries", []))
        except ValueError as e:
            return self._fail(str(e))
        except Exception as e:
            return self._fail(f"GCP error: {e}")

    async def get_metrics(
        self, metric_name: str, start_time: str, end_time: str, resource_id: str = "", period_seconds: int = 300
    ) -> dict[str, Any]:
        try:
            metric_filter = f'metric.type="{metric_name}"'
            if resource_id:
                metric_filter += f' AND resource.labels.instance_id="{resource_id}"'
            params = {
                "filter": metric_filter,
                "interval.startTime": start_time,
                "interval.endTime": end_time,
                "aggregation.alignmentPeriod": f"{period_seconds}s",
            }
            url = f"https://monitoring.googleapis.com/v3/projects/{self.project_id}/timeSeries"
            resp = await self._request("GET", url, params=params)
            if not resp.is_success:
                return self._fail(f"GCP Monitoring error {resp.status_code}: {resp.text[:300]}")
            return self._ok(datapoints=resp.json().get("timeSeries", []))
        except ValueError as e:
            return self._fail(str(e))
        except Exception as e:
            return self._fail(f"GCP error: {e}")

    async def list_alerts(self, active_only: bool = True) -> dict[str, Any]:
        try:
            url = f"https://monitoring.googleapis.com/v3/projects/{self.project_id}/alertPolicies"
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"GCP Monitoring error {resp.status_code}: {resp.text[:300]}")
            policies = resp.json().get("alertPolicies", [])
            if active_only:
                policies = [p for p in policies if p.get("enabled", True)]
            return self._ok(alerts=policies)
        except ValueError as e:
            return self._fail(str(e))
        except Exception as e:
            return self._fail(f"GCP error: {e}")

    async def get_resource_health(self, resource_id: str = "") -> dict[str, Any]:
        try:
            url = f"https://compute.googleapis.com/compute/v1/projects/{self.project_id}/aggregated/instances"
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"GCP Compute error {resp.status_code}: {resp.text[:300]}")
            instances = []
            for scoped in resp.json().get("items", {}).values():
                for inst in scoped.get("instances", []):
                    if resource_id and inst.get("name") != resource_id:
                        continue
                    instances.append({"name": inst.get("name"), "status": inst.get("status"), "zone": inst.get("zone")})
            return self._ok(instances=instances)
        except ValueError as e:
            return self._fail(str(e))
        except Exception as e:
            return self._fail(f"GCP error: {e}")

    async def list_security_findings(self, severity: str = "") -> dict[str, Any]:
        try:
            url = f"https://securitycenter.googleapis.com/v1/projects/{self.project_id}/sources/-/findings"
            params = {}
            if severity:
                params["filter"] = f'severity="{severity.upper()}"'
            resp = await self._request("GET", url, params=params)
            if not resp.is_success:
                return self._fail(f"GCP Security Command Center error {resp.status_code}: {resp.text[:300]}")
            findings = [r.get("finding", {}) for r in resp.json().get("listFindingsResults", [])]
            return self._ok(findings=findings)
        except ValueError as e:
            return self._fail(str(e))
        except Exception as e:
            return self._fail(f"GCP error: {e}")
