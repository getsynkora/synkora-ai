"""
CloudProviderAdapter — abstract base class for cloud infrastructure adapters.

Each concrete adapter (AWS/GCP/Azure/DigitalOcean) wraps that provider's
read-only operational APIs (logs, metrics, alerts, resource health, security
findings) behind a single common interface so the `internal_*` tool layer
never needs to know which provider it's talking to.

All methods return a dict shaped `{"success": bool, "error": str | None, ...}`
so tool functions can pass the result straight back to the LLM without
re-shaping it. Providers that don't support a capability (e.g. DigitalOcean
has no log-query API) still implement the method — they just return
`_fail("Not supported by <provider>")` instead of raising or being omitted,
so the LLM gets an explicit answer instead of guessing.
"""

from abc import ABC, abstractmethod
from typing import Any


class CloudProviderAdapter(ABC):
    """Common interface for read-only cloud provider operational APIs."""

    def __init__(self, credentials: dict[str, Any]):
        """
        Args:
            credentials: Resolved credential dict from `cloud_shared.get_cloud_provider_config()`
                (contains decrypted secrets — never log this dict).
        """
        self.credentials = credentials

    @staticmethod
    def _ok(**data: Any) -> dict[str, Any]:
        return {"success": True, "error": None, **data}

    @staticmethod
    def _fail(error: str) -> dict[str, Any]:
        return {"success": False, "error": error}

    @abstractmethod
    async def get_logs(
        self,
        log_source: str,
        start_time: str,
        end_time: str,
        filter_query: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        """Fetch log entries from `log_source` between `start_time`/`end_time` (ISO 8601)."""
        ...

    @abstractmethod
    async def get_metrics(
        self,
        metric_name: str,
        start_time: str,
        end_time: str,
        resource_id: str = "",
        period_seconds: int = 300,
    ) -> dict[str, Any]:
        """Fetch a time series for `metric_name`, optionally scoped to `resource_id`."""
        ...

    @abstractmethod
    async def list_alerts(self, active_only: bool = True) -> dict[str, Any]:
        """List alerts/alarms, optionally filtered to only currently-active ones."""
        ...

    @abstractmethod
    async def get_resource_health(self, resource_id: str = "") -> dict[str, Any]:
        """Get health/status for a specific resource, or all resources if `resource_id` is empty."""
        ...

    @abstractmethod
    async def list_security_findings(self, severity: str = "") -> dict[str, Any]:
        """List security findings, optionally filtered by `severity` (e.g. 'HIGH', 'CRITICAL')."""
        ...
