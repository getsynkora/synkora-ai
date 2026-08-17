"""Tests for the Slack Event Mode webhook's interactive-component (button click) handling."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from src.controllers.slack_webhooks import public_router
from src.core.database import get_async_db


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def mock_slack_bot():
    bot = MagicMock()
    bot.id = uuid4()
    bot.deleted_at = None
    bot.is_active = True
    bot.is_event_mode = True
    return bot


@pytest.fixture
def client(mock_db_session, mock_slack_bot):
    app = FastAPI()
    app.include_router(public_router)

    async def mock_db():
        yield mock_db_session

    app.dependency_overrides[get_async_db] = mock_db
    mock_db_session.get = AsyncMock(return_value=mock_slack_bot)

    return TestClient(app), mock_slack_bot


class TestInteractionWebhook:
    def test_block_actions_payload_acks_immediately_and_schedules_background(self, client):
        test_client, mock_slack_bot = client
        interaction_payload = {
            "type": "block_actions",
            "actions": [{"action_id": "hitl_approve", "value": str(uuid4())}],
            "user": {"id": "U123"},
        }
        form_body = f"payload={json.dumps(interaction_payload)}"

        with (
            patch("src.controllers.slack_webhooks.SlackEventService") as MockEventService,
            patch(
                "src.controllers.slack_webhooks._process_interaction_background", new_callable=AsyncMock
            ) as mock_process_interaction,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.verify_request.return_value = True
            MockEventService.return_value = mock_service_instance

            response = test_client.post(
                f"/api/webhooks/slack/{mock_slack_bot.id}/events",
                content=form_body,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Slack-Request-Timestamp": "1234567890",
                    "X-Slack-Signature": "v0=abc",
                },
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}
        mock_process_interaction.assert_called_once()

    def test_invalid_signature_rejected(self, client):
        test_client, mock_slack_bot = client
        interaction_payload = {"type": "block_actions", "actions": []}
        form_body = f"payload={json.dumps(interaction_payload)}"

        with patch("src.controllers.slack_webhooks.SlackEventService") as MockEventService:
            mock_service_instance = MagicMock()
            mock_service_instance.verify_request.return_value = False
            MockEventService.return_value = mock_service_instance

            response = test_client.post(
                f"/api/webhooks/slack/{mock_slack_bot.id}/events",
                content=form_body,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Slack-Request-Timestamp": "1234567890",
                    "X-Slack-Signature": "v0=bad",
                },
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_payload_field_rejected(self, client):
        test_client, mock_slack_bot = client
        response = test_client.post(
            f"/api/webhooks/slack/{mock_slack_bot.id}/events",
            content="foo=bar",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_json_event_still_handled_unchanged(self, client):
        """Regression: existing JSON event_callback flow must still work."""
        test_client, mock_slack_bot = client
        event_payload = {"type": "event_callback", "event": {"type": "app_mention"}}

        with (
            patch("src.controllers.slack_webhooks.SlackEventService") as MockEventService,
            patch(
                "src.controllers.slack_webhooks._process_event_background", new_callable=AsyncMock
            ) as mock_process_event,
        ):
            mock_service_instance = MagicMock()
            mock_service_instance.verify_request.return_value = True
            MockEventService.return_value = mock_service_instance

            response = test_client.post(
                f"/api/webhooks/slack/{mock_slack_bot.id}/events",
                json=event_payload,
                headers={
                    "X-Slack-Request-Timestamp": "1234567890",
                    "X-Slack-Signature": "v0=abc",
                },
            )

        assert response.status_code == status.HTTP_200_OK
        mock_process_event.assert_called_once()
