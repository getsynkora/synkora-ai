"""Delivery of outbound webhook events (see src/services/outbound_webhooks.py)."""

import json
import logging
import time
from uuid import UUID

import requests
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from src.core.database import get_db
from src.models.webhook_endpoint import WebhookEndpoint
from src.services.agents.security import decrypt_value
from src.services.outbound_webhooks import MAX_CONSECUTIVE_FAILURES, post_pinned, resolve_destination, sign_payload

logger = logging.getLogger(__name__)

DELIVERY_TIMEOUT_SECONDS = 10


def _record_result(db, endpoint: WebhookEndpoint, ok: bool) -> None:
    if ok:
        endpoint.consecutive_failures = 0
    else:
        endpoint.consecutive_failures = (endpoint.consecutive_failures or 0) + 1
        if endpoint.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            endpoint.is_active = False
            logger.warning("Webhook endpoint %s switched off after repeated failures", endpoint.id)
    db.commit()


@shared_task(
    name="webhooks.deliver_event",
    bind=True,
    max_retries=5,
    acks_late=True,
    time_limit=30,
    soft_time_limit=20,
)
def deliver_webhook_event(self, endpoint_id: str, delivery_id: str, event_type: str, payload: dict):
    """POST one signed event to one endpoint, retrying with backoff when it does not answer 2xx."""
    db = next(get_db())
    try:
        endpoint = db.get(WebhookEndpoint, UUID(endpoint_id))
        if endpoint is None or not endpoint.is_active:
            return

        # Check and resolve the destination now, then connect to exactly that address: DNS may have changed since
        # the endpoint was registered, and a second lookup at connect time could return an internal address.
        destination, error = resolve_destination(endpoint.url)
        if error:
            logger.warning("Webhook %s not sent to %s: %s", delivery_id, endpoint.id, error)
            _record_result(db, endpoint, ok=False)
            return

        body = json.dumps(payload, separators=(",", ":"), default=str)
        timestamp = int(time.time())
        signature = sign_payload(decrypt_value(endpoint.secret), timestamp, body)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Synkora-Webhooks/1.0",
            "X-Synkora-Event": event_type,
            "X-Synkora-Delivery": delivery_id,
            "X-Synkora-Signature": f"t={timestamp},v1={signature}",
        }
        try:
            status_code = post_pinned(destination, body, headers, timeout=DELIVERY_TIMEOUT_SECONDS)
            ok = 200 <= status_code < 300
        except requests.RequestException as err:
            logger.info("Webhook %s to %s failed: %s", delivery_id, endpoint.id, err)
            ok = False

        if ok:
            _record_result(db, endpoint, ok=True)
            return
        try:
            raise self.retry(countdown=min(30 * 2**self.request.retries, 3600))
        except MaxRetriesExceededError:
            # Counted once per event that never got through, not once per attempt
            logger.warning(
                "Webhook %s to %s given up after %s attempts", delivery_id, endpoint.id, self.max_retries + 1
            )
            _record_result(db, endpoint, ok=False)
    finally:
        db.close()
