import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests
from celery.exceptions import MaxRetriesExceededError, Retry, SoftTimeLimitExceeded

from src.services.outbound_webhooks import Destination
from src.tasks import webhook_tasks as tasks

SECRET = "whsec_test"


@pytest.fixture
def endpoint():
    return MagicMock(url="https://hooks.example.com/in", secret="enc", is_active=True, consecutive_failures=0)


@pytest.fixture
def db(endpoint):
    session = MagicMock()
    session.get.return_value = endpoint
    with patch.object(tasks, "get_db", lambda: iter([session])):
        yield session


DESTINATION = Destination("hooks.example.com", 443, "93.184.216.34", "/in")


@pytest.fixture(autouse=True)
def safe_destination():
    with (
        patch.object(tasks, "resolve_destination", return_value=(DESTINATION, None)),
        patch.object(tasks, "decrypt_value", return_value=SECRET),
    ):
        yield


def _run(payload=None):
    return tasks.deliver_webhook_event.run(str(uuid4()), "delivery-1", "usage.threshold", payload or {"a": 1})


class TestDelivery:
    def test_signed_json_post_and_failures_reset(self, db, endpoint):
        endpoint.consecutive_failures = 3
        with patch.object(tasks, "post_pinned", return_value=204) as post:
            _run({"a": 1})

        destination, body, headers = post.call_args.args[:3]
        assert destination == DESTINATION  # the address that was checked is the address that is contacted
        assert json.loads(body) == {"a": 1}
        header = headers["X-Synkora-Signature"]
        timestamp = header.split(",")[0].removeprefix("t=")
        expected = hmac.new(SECRET.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
        assert header == f"t={timestamp},v1={expected}"
        assert headers["X-Synkora-Event"] == "usage.threshold"
        assert headers["X-Synkora-Delivery"] == "delivery-1"
        assert endpoint.consecutive_failures == 0

    def test_inactive_or_missing_endpoint_sends_nothing(self, db, endpoint):
        endpoint.is_active = False
        with patch.object(tasks, "post_pinned") as post:
            _run()
        post.assert_not_called()

    def test_destination_is_checked_again_at_send_time(self, db, endpoint):
        with (
            patch.object(
                tasks, "resolve_destination", return_value=(None, "URL points to a private or internal address")
            ),
            patch.object(tasks, "post_pinned") as post,
        ):
            _run()
        post.assert_not_called()
        assert endpoint.consecutive_failures == 1

    def test_the_url_is_resolved_once_per_delivery_and_the_result_is_what_gets_contacted(self, db, endpoint):
        """Reproduces DNS rebinding: a second lookup at connect time could return an internal address."""
        with (
            patch.object(tasks, "resolve_destination", return_value=(DESTINATION, None)) as resolve,
            patch.object(tasks, "post_pinned", return_value=200) as post,
        ):
            _run()
        resolve.assert_called_once_with(endpoint.url)
        assert post.call_args.args[0] is DESTINATION

    def test_every_failed_attempt_counts_and_is_retried_while_the_endpoint_is_on(self, db, endpoint):
        with (
            patch.object(tasks, "post_pinned", return_value=500),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=Retry()) as retry,
        ):
            with pytest.raises(Retry):
                _run()
        retry.assert_called_once()
        assert endpoint.consecutive_failures == 1

    def test_a_tarpit_endpoint_is_switched_off_after_a_few_attempts_not_after_many_events(self, db, endpoint):
        """Reproduces a trickling receiver holding workers through every retry of every event and staying on."""
        with (
            patch.object(tasks, "post_pinned", side_effect=SoftTimeLimitExceeded()),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=Retry()),
        ):
            for _ in range(tasks.MAX_CONSECUTIVE_FAILURES - 1):
                with pytest.raises(Retry):
                    _run()
            assert endpoint.is_active is True
            _run()  # the last failure switches it off, and no further retry is scheduled
        assert endpoint.is_active is False

    def test_a_slow_dns_answer_hitting_the_time_limit_counts_as_a_failure(self, db, endpoint):
        with (
            patch.object(tasks, "resolve_destination", side_effect=SoftTimeLimitExceeded()),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=Retry()),
        ):
            with pytest.raises(Retry):
                _run()
        assert endpoint.consecutive_failures == 1

    def test_a_network_error_is_retried_too(self, db):
        with (
            patch.object(tasks, "post_pinned", side_effect=requests.ConnectionError("refused")),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=Retry()),
        ):
            with pytest.raises(Retry):
                _run()

    def test_giving_up_does_not_count_the_last_attempt_twice(self, db, endpoint):
        with (
            patch.object(tasks, "post_pinned", return_value=500),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=MaxRetriesExceededError()),
        ):
            _run()
        assert endpoint.consecutive_failures == 1
        assert endpoint.is_active is True

    def test_repeated_failures_switch_the_endpoint_off(self, db, endpoint):
        endpoint.consecutive_failures = tasks.MAX_CONSECUTIVE_FAILURES - 1
        with (
            patch.object(tasks, "post_pinned", return_value=500),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=MaxRetriesExceededError()),
        ):
            _run()
        assert endpoint.is_active is False

    def test_the_session_is_always_closed(self, db):
        with patch.object(tasks, "post_pinned", return_value=200):
            _run()
        db.close.assert_called_once()


class TestSlowReceivers:
    """A receiver that trickles its answer must not keep a worker busy or stay switched on."""

    def test_short_socket_timeouts_are_used(self, db):
        with patch.object(tasks, "post_pinned", return_value=200) as post:
            _run()
        assert post.call_args.kwargs["timeout"] == (tasks.CONNECT_TIMEOUT_SECONDS, tasks.READ_TIMEOUT_SECONDS)

    def test_the_attempt_has_a_hard_wall_clock_limit(self):
        assert tasks.deliver_webhook_event.soft_time_limit <= 15
        assert tasks.deliver_webhook_event.time_limit <= 20

    def test_hitting_the_time_limit_counts_as_a_failed_attempt(self, db, endpoint):
        """Reproduces the soft time limit escaping as an unhandled error that never counted against the endpoint."""
        with (
            patch.object(tasks, "post_pinned", side_effect=SoftTimeLimitExceeded()),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=MaxRetriesExceededError()),
        ):
            _run()
        assert endpoint.consecutive_failures == 1

    def test_a_slow_success_counts_as_a_failure(self, db, endpoint):
        clock = iter([100.0, 100.0 + tasks.SLOW_DELIVERY_SECONDS + 1])
        with (
            patch.object(tasks.time, "monotonic", side_effect=lambda: next(clock)),
            patch.object(tasks, "post_pinned", return_value=200),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=MaxRetriesExceededError()),
        ):
            _run()
        assert endpoint.consecutive_failures == 1

    def test_failure_logs_never_include_the_url(self, db, caplog):
        error = requests.ConnectionError(
            "HTTPSConnectionPool(host=x): Max retries exceeded with url: /hook?token=SECRET"
        )
        with (
            patch.object(tasks, "post_pinned", side_effect=error),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=MaxRetriesExceededError()),
            caplog.at_level("INFO"),
        ):
            _run()
        assert "SECRET" not in caplog.text and "ConnectionError" in caplog.text

    def test_delivery_runs_on_the_notifications_queue(self):
        # the existing notifications worker consumes this queue, so no extra worker has to be deployed
        from src.celery_app import celery_app

        assert celery_app.conf.task_routes["webhooks.deliver_event"] == {"queue": "notifications"}
