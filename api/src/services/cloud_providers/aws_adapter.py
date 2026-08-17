"""
AWS adapter — CloudWatch Logs/Metrics/Alarms, EC2 instance status, Security Hub findings.

Uses boto3 directly (already a project dependency, needed for SigV4 request
signing — there's no lightweight REST alternative for AWS's signing scheme).
Blocking boto3 calls are wrapped in `run_in_executor`, the same idiom used by
`s3_storage.py` elsewhere in this codebase.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from src.services.cloud_providers.base_adapter import CloudProviderAdapter

logger = logging.getLogger(__name__)

# Synkora's own deployment sets AWS_ENDPOINT_URL (and similar env vars) to point the
# MinIO S3-compatible storage integration at its internal endpoint. Botocore treats that
# env var as a global override for every AWS service, so without this, every boto3 client
# built here for a customer's real AWS account would get silently redirected to MinIO.
_IGNORE_ENV_ENDPOINT_CONFIG = Config(ignore_configured_endpoint_urls=True)


def _friendly_error(e: Exception) -> str:
    if isinstance(e, NoCredentialsError):
        return "AWS credentials are invalid or expired — please reconnect in Integrations."
    if isinstance(e, ClientError):
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("UnrecognizedClientException", "InvalidClientTokenId", "AccessDenied", "AccessDeniedException"):
            return "AWS credentials are invalid or expired — please reconnect in Integrations."
        return f"AWS error ({code}): {e.response.get('Error', {}).get('Message', str(e))}"
    return f"AWS error: {e}"


class AWSAdapter(CloudProviderAdapter):
    def __init__(self, credentials: dict[str, Any]):
        super().__init__(credentials)
        config = credentials.get("config") or {}
        self.session = boto3.Session(
            aws_access_key_id=credentials.get("client_id"),
            aws_secret_access_key=credentials.get("api_token"),
            region_name=config.get("region", "us-east-1"),
        )

    async def _run(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def get_logs(
        self,
        log_source: str,
        start_time: str,
        end_time: str,
        filter_query: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            client = self.session.client("logs", config=_IGNORE_ENV_ENDPOINT_CONFIG)
            start_ms = int(datetime.fromisoformat(start_time.replace("Z", "+00:00")).timestamp() * 1000)
            end_ms = int(datetime.fromisoformat(end_time.replace("Z", "+00:00")).timestamp() * 1000)
            kwargs: dict[str, Any] = {
                "logGroupName": log_source,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": min(limit, 10000),
            }
            if filter_query:
                kwargs["filterPattern"] = filter_query
            resp = await self._run(client.filter_log_events, **kwargs)
            events = [
                {
                    "timestamp": e["timestamp"],
                    "message": e["message"],
                    "log_stream": e.get("logStreamName"),
                }
                for e in resp.get("events", [])
            ]
            return self._ok(entries=events)
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            return self._fail(_friendly_error(e))

    async def get_metrics(
        self,
        metric_name: str,
        start_time: str,
        end_time: str,
        resource_id: str = "",
        period_seconds: int = 300,
    ) -> dict[str, Any]:
        try:
            client = self.session.client("cloudwatch", config=_IGNORE_ENV_ENDPOINT_CONFIG)
            namespace, _, name = metric_name.rpartition(":")
            namespace = namespace or "AWS/EC2"
            name = name or metric_name
            dimensions = [{"Name": "InstanceId", "Value": resource_id}] if resource_id else []
            resp = await self._run(
                client.get_metric_statistics,
                Namespace=namespace,
                MetricName=name,
                Dimensions=dimensions,
                StartTime=datetime.fromisoformat(start_time.replace("Z", "+00:00")),
                EndTime=datetime.fromisoformat(end_time.replace("Z", "+00:00")),
                Period=period_seconds,
                Statistics=["Average", "Maximum", "Minimum"],
            )
            datapoints = [
                {
                    "timestamp": dp["Timestamp"].isoformat(),
                    "average": dp.get("Average"),
                    "maximum": dp.get("Maximum"),
                    "minimum": dp.get("Minimum"),
                    "unit": dp.get("Unit"),
                }
                for dp in resp.get("Datapoints", [])
            ]
            return self._ok(datapoints=sorted(datapoints, key=lambda d: d["timestamp"]))
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            return self._fail(_friendly_error(e))

    async def list_alerts(self, active_only: bool = True) -> dict[str, Any]:
        try:
            client = self.session.client("cloudwatch", config=_IGNORE_ENV_ENDPOINT_CONFIG)
            kwargs: dict[str, Any] = {}
            if active_only:
                kwargs["StateValue"] = "ALARM"
            resp = await self._run(client.describe_alarms, **kwargs)
            alarms = [
                {
                    "AlarmName": a["AlarmName"],
                    "StateValue": a["StateValue"],
                    "MetricName": a.get("MetricName"),
                    "Namespace": a.get("Namespace"),
                    "Threshold": a.get("Threshold"),
                }
                for a in resp.get("MetricAlarms", [])
            ]
            return self._ok(alerts=alarms)
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            return self._fail(_friendly_error(e))

    async def get_resource_health(self, resource_id: str = "") -> dict[str, Any]:
        try:
            client = self.session.client("ec2", config=_IGNORE_ENV_ENDPOINT_CONFIG)
            kwargs: dict[str, Any] = {"IncludeAllInstances": True}
            if resource_id:
                kwargs["InstanceIds"] = [resource_id]
            resp = await self._run(client.describe_instance_status, **kwargs)
            instances = [
                {
                    "InstanceId": i["InstanceId"],
                    "InstanceState": i.get("InstanceState", {}).get("Name"),
                    "SystemStatus": i.get("SystemStatus", {}).get("Status"),
                    "InstanceStatus": i.get("InstanceStatus", {}).get("Status"),
                }
                for i in resp.get("InstanceStatuses", [])
            ]
            return self._ok(instances=instances)
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            return self._fail(_friendly_error(e))

    async def list_security_findings(self, severity: str = "") -> dict[str, Any]:
        try:
            client = self.session.client("securityhub", config=_IGNORE_ENV_ENDPOINT_CONFIG)
            kwargs: dict[str, Any] = {"MaxResults": 100}
            if severity:
                kwargs["Filters"] = {"SeverityLabel": [{"Value": severity.upper(), "Comparison": "EQUALS"}]}
            resp = await self._run(client.get_findings, **kwargs)
            findings = [
                {
                    "Id": f.get("Id"),
                    "Title": f.get("Title"),
                    "Severity": f.get("Severity", {}).get("Label"),
                    "ResourceId": (f.get("Resources") or [{}])[0].get("Id"),
                    "Description": f.get("Description"),
                }
                for f in resp.get("Findings", [])
            ]
            return self._ok(findings=findings)
        except (ClientError, BotoCoreError, NoCredentialsError) as e:
            return self._fail(_friendly_error(e))
