import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests
from celery.exceptions import MaxRetriesExceededError, Retry

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


@pytest.fixture(autouse=True)
def safe_destination():
    with (
        patch.object(tasks, "destination_error", return_value=None),
        patch.object(tasks, "decrypt_value", return_value=SECRET),
    ):
        yield


def _run(payload=None):
    return tasks.deliver_webhook_event.run(str(uuid4()), "delivery-1", "usage.threshold", payload or {"a": 1})


class TestDelivery:
    def test_signed_json_post_and_failures_reset(self, db, endpoint):
        endpoint.consecutive_failures = 3
        with patch.object(tasks.requests, "post", return_value=MagicMock(status_code=204)) as post:
            _run({"a": 1})

        kwargs = post.call_args.kwargs
        body = kwargs["data"]
        assert json.loads(body) == {"a": 1}
        header = kwargs["headers"]["X-Synkora-Signature"]
        timestamp = header.split(",")[0].removeprefix("t=")
        expected = hmac.new(SECRET.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
        assert header == f"t={timestamp},v1={expected}"
        assert kwargs["headers"]["X-Synkora-Event"] == "usage.threshold"
        assert kwargs["headers"]["X-Synkora-Delivery"] == "delivery-1"
        assert kwargs["allow_redirects"] is False  # a redirect could point at an internal address
        assert endpoint.consecutive_failures == 0

    def test_inactive_or_missing_endpoint_sends_nothing(self, db, endpoint):
        endpoint.is_active = False
        with patch.object(tasks.requests, "post") as post:
            _run()
        post.assert_not_called()

    def test_destination_is_checked_again_at_send_time(self, db, endpoint):
        with (
            patch.object(tasks, "destination_error", return_value="private address"),
            patch.object(tasks.requests, "post") as post,
        ):
            _run()
        post.assert_not_called()
        assert endpoint.consecutive_failures == 1

    def test_a_failed_attempt_is_retried_without_counting_a_failure_yet(self, db, endpoint):
        with (
            patch.object(tasks.requests, "post", return_value=MagicMock(status_code=500)),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=Retry()) as retry,
        ):
            with pytest.raises(Retry):
                _run()
        retry.assert_called_once()
        assert endpoint.consecutive_failures == 0

    def test_a_network_error_is_retried_too(self, db):
        with (
            patch.object(tasks.requests, "post", side_effect=requests.ConnectionError("refused")),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=Retry()),
        ):
            with pytest.raises(Retry):
                _run()

    def test_giving_up_counts_one_failure(self, db, endpoint):
        with (
            patch.object(tasks.requests, "post", return_value=MagicMock(status_code=500)),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=MaxRetriesExceededError()),
        ):
            _run()
        assert endpoint.consecutive_failures == 1
        assert endpoint.is_active is True

    def test_repeated_failures_switch_the_endpoint_off(self, db, endpoint):
        endpoint.consecutive_failures = tasks.MAX_CONSECUTIVE_FAILURES - 1
        with (
            patch.object(tasks.requests, "post", return_value=MagicMock(status_code=500)),
            patch.object(tasks.deliver_webhook_event, "retry", side_effect=MaxRetriesExceededError()),
        ):
            _run()
        assert endpoint.is_active is False

    def test_the_session_is_always_closed(self, db):
        with patch.object(tasks.requests, "post", return_value=MagicMock(status_code=200)):
            _run()
        db.close.assert_called_once()
