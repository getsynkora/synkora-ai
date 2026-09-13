"""
Celery tasks for load testing operations.
"""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from celery.exceptions import MaxRetriesExceededError

from src.celery_app import celery_app
from src.core.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="execute_load_test", bind=True, max_retries=1, default_retry_delay=30)
def execute_load_test(self, test_run_id: str) -> dict[str, Any]:
    """
    Execute a load test run.

    This task:
    1. Generates the K6 script
    2. Executes K6 via Docker
    3. Streams results to Redis
    4. Updates the test run with summary metrics

    Args:
        test_run_id: UUID of the test run

    Returns:
        dict: Execution results
    """
    db = SessionLocal()

    try:
        from src.models.load_test import LoadTest, LoadTestStatus
        from src.models.test_run import TestRun, TestRunStatus
        from src.models.test_scenario import TestScenario
        from src.services.load_testing.k6_executor import K6Executor
        from src.services.load_testing.k6_generator import K6ScriptGenerator

        logger.info(f"Starting load test execution: {test_run_id}")

        # Get test run
        test_run = db.query(TestRun).filter(TestRun.id == uuid.UUID(test_run_id)).first()
        if not test_run:
            raise ValueError(f"Test run {test_run_id} not found")

        # Get load test
        load_test = db.query(LoadTest).filter(LoadTest.id == test_run.load_test_id).first()
        if not load_test:
            raise ValueError(f"Load test {test_run.load_test_id} not found")

        # Get scenarios
        scenarios = (
            db.query(TestScenario)
            .filter(TestScenario.load_test_id == load_test.id)
            .order_by(TestScenario.display_order)
            .all()
        )

        # Update status to initializing
        test_run.status = TestRunStatus.INITIALIZING
        db.commit()

        # Generate K6 script
        generator = K6ScriptGenerator(load_test, scenarios)
        k6_script = generator.generate()

        # Store script in test run
        test_run.k6_script = k6_script
        db.commit()

        # Create executor
        executor = K6Executor(
            test_run_id=uuid.UUID(test_run_id),
            k6_script=k6_script,
        )

        # Update status to running
        test_run.status = TestRunStatus.RUNNING
        test_run.started_at = datetime.now(UTC)
        db.commit()

        # Publish start event
        _publish_event(test_run_id, {"event": "started", "timestamp": datetime.now(UTC).isoformat()})

        # Define metrics callback
        def on_metrics(data: dict):
            _publish_event(test_run_id, data)

            # Store metric data point
            _store_metric(db, test_run_id, data)

        # Execute K6
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            results = loop.run_until_complete(executor.execute_docker(on_metrics))
        finally:
            loop.close()

        # Parse summary
        summary_metrics = {}
        if results.get("summary"):
            summary_metrics = executor.parse_summary(results["summary"])

        # Update test run
        test_run.status = TestRunStatus.COMPLETED if not results.get("error") else TestRunStatus.FAILED
        test_run.completed_at = datetime.now(UTC)
        test_run.summary_metrics = summary_metrics
        test_run.error_message = results.get("error")
        test_run.peak_vus = int(summary_metrics.get("vus_max") or 0)
        test_run.total_requests = int(summary_metrics.get("http_reqs") or 0)

        # Update load test status
        load_test.status = LoadTestStatus.READY
        db.commit()

        # Publish completion event
        _publish_event(
            test_run_id,
            {
                "event": "completed",
                "status": test_run.status.value,
                "summary": summary_metrics,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        # Trigger metrics export if monitoring integrations exist
        export_metrics_to_monitoring.delay(test_run_id)

        logger.info(f"Load test execution completed: {test_run_id}")

        return {
            "success": True,
            "test_run_id": test_run_id,
            "status": test_run.status.value,
            "summary_metrics": summary_metrics,
        }

    except Exception as exc:
        logger.error(f"Error executing load test: {exc}", exc_info=True)

        # Update test run status
        try:
            from src.models.load_test import LoadTestStatus
            from src.models.test_run import TestRun, TestRunStatus

            test_run = db.query(TestRun).filter(TestRun.id == uuid.UUID(test_run_id)).first()
            if test_run:
                test_run.status = TestRunStatus.FAILED
                test_run.completed_at = datetime.now(UTC)
                test_run.error_message = str(exc)

                if test_run.load_test_id:
                    load_test = db.query(LoadTest).filter(LoadTest.id == test_run.load_test_id).first()
                    if load_test:
                        load_test.status = LoadTestStatus.READY

                db.commit()
        except Exception:
            pass

        # Publish error event
        _publish_event(
            test_run_id,
            {
                "event": "error",
                "error": str(exc),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        return {"success": False, "error": str(exc)}

    finally:
        db.close()


@celery_app.task(name="cancel_load_test", bind=True)
def cancel_load_test(self, test_run_id: str) -> dict[str, Any]:
    """
    Cancel a running load test.

    Args:
        test_run_id: UUID of the test run

    Returns:
        dict: Cancellation result
    """
    db = SessionLocal()

    try:
        from src.models.load_test import LoadTest, LoadTestStatus
        from src.models.test_run import TestRun, TestRunStatus

        logger.info(f"Cancelling load test: {test_run_id}")

        test_run = db.query(TestRun).filter(TestRun.id == uuid.UUID(test_run_id)).first()
        if not test_run:
            raise ValueError(f"Test run {test_run_id} not found")

        # Stop Docker container
        import subprocess

        container_name = f"k6-{test_run_id}"
        try:
            subprocess.run(["docker", "stop", container_name], capture_output=True, timeout=30)
        except Exception:
            pass

        # Update status
        test_run.status = TestRunStatus.CANCELLED
        test_run.completed_at = datetime.now(UTC)

        # Update load test status
        if test_run.load_test_id:
            load_test = db.query(LoadTest).filter(LoadTest.id == test_run.load_test_id).first()
            if load_test:
                load_test.status = LoadTestStatus.READY

        db.commit()

        # Publish cancellation event
        _publish_event(
            test_run_id,
            {
                "event": "cancelled",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        logger.info(f"Load test cancelled: {test_run_id}")

        return {"success": True, "test_run_id": test_run_id}

    except Exception as exc:
        logger.error(f"Error cancelling load test: {exc}", exc_info=True)
        return {"success": False, "error": str(exc)}

    finally:
        db.close()


@celery_app.task(name="export_metrics_to_monitoring", bind=True, max_retries=3, default_retry_delay=60)
def export_metrics_to_monitoring(self, test_run_id: str) -> dict[str, Any]:
    """
    Export test metrics to configured monitoring integrations.

    Args:
        test_run_id: UUID of the test run

    Returns:
        dict: Export results
    """
    db = SessionLocal()

    try:
        from src.models.monitoring_integration import MonitoringIntegration, MonitoringProvider
        from src.models.test_run import TestRun

        logger.info(f"Exporting metrics for test run: {test_run_id}")

        test_run = db.query(TestRun).filter(TestRun.id == uuid.UUID(test_run_id)).first()
        if not test_run:
            raise ValueError(f"Test run {test_run_id} not found")

        # Get active integrations for tenant
        integrations = (
            db.query(MonitoringIntegration)
            .filter(
                MonitoringIntegration.tenant_id == test_run.tenant_id,
                MonitoringIntegration.is_active == True,  # noqa: E712
            )
            .all()
        )

        if not integrations:
            logger.info("No active monitoring integrations found")
            return {"success": True, "exports": []}

        results = []

        for integration in integrations:
            try:
                config = integration.get_config()
                export_settings = integration.export_settings or {}

                # Skip if auto_export is disabled
                if not export_settings.get("auto_export", True):
                    continue

                # Export based on provider
                if integration.provider == MonitoringProvider.DATADOG:
                    result = _export_to_datadog(test_run, config, export_settings)
                elif integration.provider == MonitoringProvider.OPENTELEMETRY:
                    result = _export_to_otlp(test_run, config, export_settings)
                elif integration.provider == MonitoringProvider.GRAFANA_CLOUD:
                    result = _export_to_grafana(test_run, config, export_settings)
                elif integration.provider == MonitoringProvider.WEBHOOK:
                    result = _export_to_webhook(test_run, config, export_settings)
                else:
                    result = {"success": False, "error": f"Unsupported provider: {integration.provider}"}

                # Update sync status
                integration.last_sync_at = datetime.now(UTC)
                integration.sync_status = "success" if result.get("success") else "failed"
                integration.sync_error = result.get("error")

                results.append(
                    {
                        "integration_id": str(integration.id),
                        "provider": integration.provider.value,
                        **result,
                    }
                )

            except Exception as e:
                logger.error(f"Error exporting to {integration.provider}: {e}")
                results.append(
                    {
                        "integration_id": str(integration.id),
                        "provider": integration.provider.value,
                        "success": False,
                        "error": str(e),
                    }
                )

        db.commit()

        return {"success": True, "exports": results}

    except Exception as exc:
        logger.error(f"Error exporting metrics: {exc}", exc_info=True)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {"success": False, "error": str(exc)}

    finally:
        db.close()


@celery_app.task(name="generate_test_report")
def generate_test_report(
    test_run_id: str,
    format: str = "json",
    include_time_series: bool = True,
    include_k6_script: bool = False,
) -> dict[str, Any]:
    """
    Generate an export report for a test run.

    Args:
        test_run_id: UUID of the test run
        format: Export format (json, csv, pdf)
        include_time_series: Include time series data
        include_k6_script: Include generated K6 script

    Returns:
        dict: Export result with download URL
    """
    db = SessionLocal()

    try:
        from src.models.test_result import TestResult
        from src.models.test_run import TestRun

        logger.info(f"Generating report for test run: {test_run_id}")

        test_run = db.query(TestRun).filter(TestRun.id == uuid.UUID(test_run_id)).first()
        if not test_run:
            raise ValueError(f"Test run {test_run_id} not found")

        # Build report data
        report = {
            "test_run_id": str(test_run.id),
            "load_test_id": str(test_run.load_test_id),
            "status": test_run.status.value,
            "started_at": test_run.started_at.isoformat() if test_run.started_at else None,
            "completed_at": test_run.completed_at.isoformat() if test_run.completed_at else None,
            "duration_seconds": test_run.duration_seconds,
            "summary_metrics": test_run.summary_metrics,
            "peak_vus": test_run.peak_vus,
            "total_requests": test_run.total_requests,
            "error_message": test_run.error_message,
        }

        if include_k6_script:
            report["k6_script"] = test_run.k6_script

        if include_time_series:
            results = (
                db.query(TestResult)
                .filter(TestResult.test_run_id == uuid.UUID(test_run_id))
                .order_by(TestResult.timestamp)
                .all()
            )
            report["time_series"] = [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "metric_type": r.metric_type.value,
                    "value": r.metric_value,
                    "percentile": r.percentile.value if r.percentile else None,
                    "tags": r.tags,
                }
                for r in results
            ]

        # Generate file based on format
        if format == "json":
            content = json.dumps(report, indent=2)
            content_type = "application/json"
            extension = "json"
        elif format == "csv":
            content = _generate_csv(report)
            content_type = "text/csv"
            extension = "csv"
        else:
            # Default to JSON
            content = json.dumps(report, indent=2)
            content_type = "application/json"
            extension = "json"

        # Upload to storage and get URL
        from src.services.storage.file_service import get_file_service

        file_service = get_file_service()
        filename = f"load-test-report-{test_run_id}.{extension}"

        # Upload file
        download_url = file_service.upload_text_content(
            content=content,
            filename=filename,
            content_type=content_type,
            tenant_id=str(test_run.tenant_id),
        )

        return {
            "download_url": download_url,
            "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            "format": format,
            "file_size": len(content),
        }

    except Exception as exc:
        logger.error(f"Error generating report: {exc}", exc_info=True)
        raise

    finally:
        db.close()


@celery_app.task(name="cleanup_old_test_results")
def cleanup_old_test_results(days: int = 30) -> dict[str, Any]:
    """
    Clean up old test results to manage storage.

    Args:
        days: Number of days to retain results

    Returns:
        dict: Cleanup results
    """
    db = SessionLocal()

    try:
        from src.models.test_result import TestResult
        from src.models.test_run import TestRun

        cutoff_date = datetime.now(UTC) - timedelta(days=days)

        logger.info(f"Cleaning up test results older than {cutoff_date}")

        # Delete old test results
        deleted_results = (
            db.query(TestResult).filter(TestResult.created_at < cutoff_date).delete(synchronize_session=False)
        )

        # Optionally delete old completed test runs
        deleted_runs = (
            db.query(TestRun)
            .filter(
                TestRun.completed_at < cutoff_date,
                TestRun.status.in_(["completed", "failed", "cancelled"]),
            )
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(f"Cleaned up {deleted_results} results and {deleted_runs} runs")

        return {
            "success": True,
            "deleted_results": deleted_results,
            "deleted_runs": deleted_runs,
        }

    except Exception as exc:
        logger.error(f"Error cleaning up test results: {exc}", exc_info=True)
        db.rollback()
        return {"success": False, "error": str(exc)}

    finally:
        db.close()


# ============================================================================
# Helper Functions
# ============================================================================


def _publish_event(test_run_id: str, data: dict) -> None:
    """Publish event to Redis for SSE streaming."""
    try:
        from src.config.redis import get_redis

        redis = get_redis()
        channel = f"test_run:{test_run_id}:results"
        redis.publish(channel, json.dumps(data))
    except Exception as e:
        logger.warning(f"Failed to publish event: {e}")


def _store_metric(db, test_run_id: str, data: dict) -> None:
    """Store a metric data point in the database."""
    try:
        from src.models.test_result import MetricType, TestResult

        metric_name = data.get("metric")
        if not metric_name:
            return

        # Map K6 metric names to our enum
        metric_mapping = {
            "http_req_duration": MetricType.HTTP_REQ_DURATION,
            "http_req_failed": MetricType.HTTP_REQ_FAILED,
            "http_reqs": MetricType.HTTP_REQS,
            "vus": MetricType.VUS,
            "vus_max": MetricType.VUS_MAX,
            "data_received": MetricType.DATA_RECEIVED,
            "data_sent": MetricType.DATA_SENT,
            "iterations": MetricType.ITERATIONS,
            "ttft": MetricType.TTFT,
            "tokens_per_sec": MetricType.TOKENS_PER_SEC,
        }

        metric_type = metric_mapping.get(metric_name)
        if not metric_type:
            return

        value = data.get("value")
        if value is None:
            return

        timestamp = data.get("timestamp")
        if timestamp:
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            timestamp = datetime.now(UTC)

        result = TestResult(
            test_run_id=uuid.UUID(test_run_id),
            timestamp=timestamp,
            metric_type=metric_type,
            metric_value=float(value),
            tags=data.get("tags"),
        )

        db.add(result)
        # Commit in batches to avoid too many small transactions
        if hasattr(db, "_metric_count"):
            db._metric_count += 1
        else:
            db._metric_count = 1

        if db._metric_count % 100 == 0:
            db.commit()

    except Exception as e:
        logger.warning(f"Failed to store metric: {e}")


def _monitoring_export_request(method: str, url: str, **kwargs):
    import asyncio

    from src.services.security.monitoring_http import monitoring_request

    try:
        return asyncio.run(monitoring_request(method, url, **kwargs))
    except Exception:
        raise ValueError("Monitoring connection failed or destination is not permitted") from None


def _export_to_datadog(test_run, config: dict, settings: dict) -> dict:
    """Export metrics to DataDog."""

    api_key = config.get("api_key")
    site = config.get("site", "datadoghq.com")
    metric_prefix = settings.get("metric_prefix", "synkora.loadtest")
    tags = settings.get("tags", [])

    metrics = test_run.summary_metrics or {}
    timestamp = int(test_run.completed_at.timestamp()) if test_run.completed_at else int(datetime.now(UTC).timestamp())

    # Build DataDog series
    series = []
    for metric_name, value in metrics.items():
        if value is not None:
            series.append(
                {
                    "metric": f"{metric_prefix}.{metric_name}",
                    "points": [[timestamp, float(value)]],
                    "type": "gauge",
                    "tags": tags + [f"test_run_id:{test_run.id}"],
                }
            )

    if not series:
        return {"success": True, "metrics_sent": 0}

    response = _monitoring_export_request(
        "POST",
        f"https://api.{site}/api/v1/series",
        headers={
            "DD-API-KEY": api_key,
            "Content-Type": "application/json",
        },
        json={"series": series},
        timeout=30,
        tenant_id=test_run.tenant_id,
    )

    if response.status_code == 202:
        return {"success": True, "metrics_sent": len(series)}
    else:
        return {"success": False, "error": f"Monitoring endpoint returned HTTP {response.status_code}"}


def _export_to_otlp(test_run, config: dict, settings: dict) -> dict:
    """Export metrics to OTLP endpoint."""
    # Simplified OTLP export - in production use opentelemetry-sdk

    endpoint = config.get("endpoint")
    headers = config.get("headers", {})

    metrics = test_run.summary_metrics or {}

    # Build OTLP metrics payload (simplified)
    payload = {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "synkora-loadtest"}},
                        {"key": "test_run_id", "value": {"stringValue": str(test_run.id)}},
                    ]
                },
                "scopeMetrics": [
                    {
                        "metrics": [
                            {
                                "name": f"loadtest.{name}",
                                "gauge": {"dataPoints": [{"asDouble": value}]},
                            }
                            for name, value in metrics.items()
                            if value is not None
                        ]
                    }
                ],
            }
        ]
    }

    response = _monitoring_export_request(
        "POST",
        f"{endpoint}/v1/metrics",
        headers={"Content-Type": "application/json", **headers},
        json=payload,
        timeout=30,
        tenant_id=test_run.tenant_id,
    )

    if 200 <= response.status_code < 300:
        return {"success": True}
    else:
        return {"success": False, "error": f"Monitoring endpoint returned HTTP {response.status_code}"}


def _export_to_grafana(test_run, config: dict, settings: dict) -> dict:
    """Export metrics to Grafana Cloud."""

    prometheus_url = config.get("prometheus_url")
    username = config.get("username")
    api_key = config.get("api_key")
    metric_prefix = settings.get("metric_prefix", "synkora_loadtest")

    metrics = test_run.summary_metrics or {}

    # Build Prometheus remote write format
    lines = []
    for name, value in metrics.items():
        if value is not None:
            metric_name = f"{metric_prefix}_{name}".replace(".", "_")
            lines.append(f'{metric_name}{{test_run_id="{test_run.id}"}} {value}')

    if not lines:
        return {"success": True, "metrics_sent": 0}

    response = _monitoring_export_request(
        "POST",
        f"{prometheus_url}/api/v1/push",
        auth=(username, api_key),
        content="\n".join(lines).encode(),
        headers={"Content-Type": "text/plain"},
        timeout=30,
        tenant_id=test_run.tenant_id,
    )

    if 200 <= response.status_code < 300:
        return {"success": True, "metrics_sent": len(lines)}
    else:
        return {"success": False, "error": f"Monitoring endpoint returned HTTP {response.status_code}"}


def _export_to_webhook(test_run, config: dict, settings: dict) -> dict:
    """Export metrics to webhook endpoint."""

    url = config.get("url")
    method = str(config.get("method", "POST")).upper()
    if method not in {"POST", "PUT", "PATCH"}:
        return {"success": False, "error": "Unsupported webhook export method"}
    headers = config.get("headers", {})

    payload = {
        "test_run_id": str(test_run.id),
        "load_test_id": str(test_run.load_test_id),
        "tenant_id": str(test_run.tenant_id),
        "status": test_run.status.value,
        "started_at": test_run.started_at.isoformat() if test_run.started_at else None,
        "completed_at": test_run.completed_at.isoformat() if test_run.completed_at else None,
        "summary_metrics": test_run.summary_metrics,
        "peak_vus": test_run.peak_vus,
        "total_requests": test_run.total_requests,
    }

    response = _monitoring_export_request(
        method=method,
        url=url,
        headers={"Content-Type": "application/json", **headers},
        json=payload,
        timeout=30,
        tenant_id=test_run.tenant_id,
    )

    if 200 <= response.status_code < 300:
        return {"success": True}
    else:
        return {"success": False, "error": f"Monitoring endpoint returned HTTP {response.status_code}"}


def _generate_csv(report: dict) -> str:
    """Generate CSV content from report data."""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)

    # Write summary
    writer.writerow(["Test Run Report"])
    writer.writerow([""])
    writer.writerow(["Test Run ID", report["test_run_id"]])
    writer.writerow(["Status", report["status"]])
    writer.writerow(["Started At", report["started_at"]])
    writer.writerow(["Completed At", report["completed_at"]])
    writer.writerow(["Duration (s)", report["duration_seconds"]])
    writer.writerow(["Peak VUs", report["peak_vus"]])
    writer.writerow(["Total Requests", report["total_requests"]])
    writer.writerow([""])

    # Write summary metrics
    writer.writerow(["Summary Metrics"])
    if report.get("summary_metrics"):
        for name, value in report["summary_metrics"].items():
            writer.writerow([name, value])
    writer.writerow([""])

    # Write time series if included
    if report.get("time_series"):
        writer.writerow(["Time Series Data"])
        writer.writerow(["timestamp", "metric_type", "value", "percentile", "tags"])
        for point in report["time_series"]:
            writer.writerow(
                [
                    point["timestamp"],
                    point["metric_type"],
                    point["value"],
                    point.get("percentile", ""),
                    json.dumps(point.get("tags", {})),
                ]
            )

    return output.getvalue()
