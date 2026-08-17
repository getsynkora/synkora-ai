"""Azure cloud provider adapter: Monitor Logs/Metrics/Alerts, Resource Health, Defender for Cloud."""

from typing import Any

import httpx

from src.services.cloud_providers.base_adapter import CloudProviderAdapter

_MANAGEMENT_SCOPE = "https://management.azure.com/.default"
_LOG_ANALYTICS_SCOPE = "https://api.loganalytics.io/.default"
_API_VERSION = "2023-11-01"


class AzureAdapter(CloudProviderAdapter):
    def __init__(self, credentials: dict[str, Any]):
        super().__init__(credentials)
        config = credentials.get("config") or {}
        self.tenant_id = config.get("azure_tenant_id", "")
        self.subscription_id = config.get("subscription_id", "")
        self.client_id = credentials.get("client_id", "")
        self.client_secret = credentials.get("api_token", "")

    async def _get_access_token(self, scope: str) -> str:
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": scope,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, data=data)
        if not resp.is_success:
            raise ValueError("Azure credentials are invalid or expired — please reconnect in Integrations.")
        return resp.json()["access_token"]

    async def _request(self, method: str, url: str, scope: str = _MANAGEMENT_SCOPE, **kwargs) -> httpx.Response:
        token = await self._get_access_token(scope)
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            return await client.request(method, url, headers=headers, **kwargs)

    async def get_logs(
        self,
        log_source: str,
        start_time: str,
        end_time: str,
        filter_query: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            query = filter_query or "union * | order by TimeGenerated desc"
            url = f"https://api.loganalytics.io/v1/workspaces/{log_source}/query"
            body = {"query": f"{query} | take {limit}", "timespan": f"{start_time}/{end_time}"}
            resp = await self._request("POST", url, scope=_LOG_ANALYTICS_SCOPE, json=body)
            if not resp.is_success:
                return self._fail(f"Azure Monitor Logs error ({resp.status_code}): {resp.text}")
            table = (resp.json().get("tables") or [{}])[0]
            columns = [c["name"] for c in table.get("columns", [])]
            rows = table.get("rows", [])
            entries = [dict(zip(columns, row, strict=False)) for row in rows]
            return self._ok(data=entries)
        except ValueError as e:
            return self._fail(str(e))
        except httpx.HTTPError as e:
            return self._fail(f"Azure Monitor Logs request failed: {e}")

    async def get_metrics(
        self,
        metric_name: str,
        start_time: str,
        end_time: str,
        resource_id: str = "",
        period_seconds: int = 300,
    ) -> dict[str, Any]:
        if not resource_id:
            return self._fail("resource_id is required for Azure Monitor Metrics (full ARM resource ID).")
        try:
            interval = f"PT{max(period_seconds // 60, 1)}M"
            url = (
                f"https://management.azure.com{resource_id}/providers/microsoft.insights/metrics"
                f"?api-version=2018-01-01&metricnames={metric_name}"
                f"&timespan={start_time}/{end_time}&interval={interval}"
            )
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"Azure Monitor Metrics error ({resp.status_code}): {resp.text}")
            return self._ok(data=resp.json().get("value", []))
        except ValueError as e:
            return self._fail(str(e))
        except httpx.HTTPError as e:
            return self._fail(f"Azure Monitor Metrics request failed: {e}")

    async def list_alerts(self, active_only: bool = True) -> dict[str, Any]:
        try:
            url = (
                f"https://management.azure.com/subscriptions/{self.subscription_id}"
                f"/providers/Microsoft.AlertsManagement/alerts?api-version={_API_VERSION}"
            )
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"Azure Monitor alerts error ({resp.status_code}): {resp.text}")
            alerts = resp.json().get("value", [])
            if active_only:
                alerts = [a for a in alerts if a.get("properties", {}).get("essentials", {}).get("alertState") == "New"]
            return self._ok(data=alerts)
        except ValueError as e:
            return self._fail(str(e))
        except httpx.HTTPError as e:
            return self._fail(f"Azure Monitor alerts request failed: {e}")

    async def get_resource_health(self, resource_id: str = "") -> dict[str, Any]:
        if not resource_id:
            return self._fail("resource_id is required for Azure Resource Health (full ARM resource ID).")
        try:
            url = (
                f"https://management.azure.com{resource_id}"
                f"/providers/Microsoft.ResourceHealth/availabilityStatuses/current?api-version=2022-10-01"
            )
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"Azure Resource Health error ({resp.status_code}): {resp.text}")
            return self._ok(data=resp.json())
        except ValueError as e:
            return self._fail(str(e))
        except httpx.HTTPError as e:
            return self._fail(f"Azure Resource Health request failed: {e}")

    async def list_security_findings(self, severity: str = "") -> dict[str, Any]:
        try:
            url = (
                f"https://management.azure.com/subscriptions/{self.subscription_id}"
                f"/providers/Microsoft.Security/assessments?api-version=2020-01-01"
            )
            resp = await self._request("GET", url)
            if not resp.is_success:
                return self._fail(f"Defender for Cloud error ({resp.status_code}): {resp.text}")
            findings = resp.json().get("value", [])
            if severity:
                findings = [
                    f
                    for f in findings
                    if f.get("properties", {}).get("status", {}).get("severity", "").lower() == severity.lower()
                ]
            return self._ok(data=findings)
        except ValueError as e:
            return self._fail(str(e))
        except httpx.HTTPError as e:
            return self._fail(f"Defender for Cloud request failed: {e}")
