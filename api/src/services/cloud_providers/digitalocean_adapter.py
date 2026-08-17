"""DigitalOcean cloud provider adapter: Droplet metrics, monitoring alerts, resource health.

Logs and security findings have no DigitalOcean API equivalent (see capability matrix in
docs/superpowers/specs/2026-08-16-cloud-provider-integrations-design.md) — those two methods
return a clear "not supported" result instead of being omitted.
"""

from typing import Any

import httpx

from src.services.cloud_providers.base_adapter import CloudProviderAdapter

_BASE_URL = "https://api.digitalocean.com/v2"


class DigitalOceanAdapter(CloudProviderAdapter):
    def __init__(self, credentials: dict[str, Any]):
        super().__init__(credentials)
        self.token = credentials.get("api_token", "")

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            return await client.request(method, f"{_BASE_URL}{path}", headers=headers, **kwargs)

    def _friendly_error(self, resp: httpx.Response) -> str:
        if resp.status_code in (401, 403):
            return "DigitalOcean token is invalid or expired — please reconnect in Integrations."
        return f"DigitalOcean error ({resp.status_code}): {resp.text}"

    async def get_logs(
        self,
        log_source: str,
        start_time: str,
        end_time: str,
        filter_query: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        return self._fail("Not supported by DigitalOcean")

    async def get_metrics(
        self,
        metric_name: str,
        start_time: str,
        end_time: str,
        resource_id: str = "",
        period_seconds: int = 300,
    ) -> dict[str, Any]:
        if not resource_id:
            return self._fail("resource_id (droplet ID) is required for DigitalOcean metrics.")
        try:
            path = f"/monitoring/metrics/droplet/{metric_name}"
            params = {"host_id": resource_id, "start": start_time, "end": end_time}
            resp = await self._request("GET", path, params=params)
            if not resp.is_success:
                return self._fail(self._friendly_error(resp))
            return self._ok(data=resp.json().get("data", {}).get("result", []))
        except httpx.HTTPError as e:
            return self._fail(f"DigitalOcean metrics request failed: {e}")

    async def list_alerts(self, active_only: bool = True) -> dict[str, Any]:
        try:
            resp = await self._request("GET", "/monitoring/alerts")
            if not resp.is_success:
                return self._fail(self._friendly_error(resp))
            policies = resp.json().get("policies", [])
            if active_only:
                policies = [p for p in policies if p.get("enabled")]
            return self._ok(data=policies)
        except httpx.HTTPError as e:
            return self._fail(f"DigitalOcean alerts request failed: {e}")

    async def get_resource_health(self, resource_id: str = "") -> dict[str, Any]:
        if not resource_id:
            return self._fail("resource_id (droplet ID) is required for DigitalOcean resource health.")
        try:
            resp = await self._request("GET", f"/droplets/{resource_id}")
            if not resp.is_success:
                return self._fail(self._friendly_error(resp))
            return self._ok(data=resp.json().get("droplet", {}))
        except httpx.HTTPError as e:
            return self._fail(f"DigitalOcean droplet status request failed: {e}")

    async def list_security_findings(self, severity: str = "") -> dict[str, Any]:
        return self._fail("Not supported by DigitalOcean")
