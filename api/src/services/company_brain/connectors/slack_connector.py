"""
Slack connector for Company Brain ingestion.

Config keys (from DataSource.config + decrypted credentials):
  bot_token:    str   — Slack Bot Token (xoxb-...)
  channels:     list  — channel names or IDs to sync (empty = all joined channels)
  oldest_days:  int   — how many days back to fetch on full sync (default 90)

Documents produced:
  One per Slack message (or thread reply). Thread context is included in metadata.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, AsyncIterator

from .base import BaseConnector, ConnectorDocument, ConnectorHealth

logger = logging.getLogger(__name__)

_DEFAULT_OLDEST_DAYS = 90
_BATCH_SIZE = 200


class SlackConnector(BaseConnector):
    source_type = "slack"

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._token: str = config.get("bot_token", "")
        self._channels: list[str] = config.get("channels") or []
        self._oldest_days: int = int(config.get("oldest_days", _DEFAULT_OLDEST_DAYS))

    async def fetch_documents(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> AsyncIterator[list[ConnectorDocument]]:
        """Yield batches of Slack messages as ConnectorDocuments."""
        if not self._token:
            logger.error("SlackConnector: bot_token not configured")
            return

        try:
            from slack_sdk.web.async_client import AsyncWebClient
        except ImportError:
            logger.error("slack_sdk not installed — pip install slack-sdk")
            return

        client = AsyncWebClient(token=self._token)
        oldest_ts = _to_slack_ts(since or datetime.now(UTC) - timedelta(days=self._oldest_days))
        latest_ts = _to_slack_ts(until) if until else None

        channel_ids = await self._resolve_channel_ids(client)

        for channel_id in channel_ids:
            async for batch in self._fetch_channel(client, channel_id, oldest_ts, latest_ts):
                yield batch

    async def health_check(self) -> ConnectorHealth:
        if not self._token:
            return ConnectorHealth(status="down", message="bot_token not configured")
        try:
            from slack_sdk.web.async_client import AsyncWebClient

            client = AsyncWebClient(token=self._token)
            resp = await client.auth_test()
            if resp["ok"]:
                return ConnectorHealth(
                    status="ok",
                    message=f"Connected as {resp.get('user')} to {resp.get('team')}",
                )
            return ConnectorHealth(status="degraded", message=str(resp.get("error")))
        except Exception as exc:
            return ConnectorHealth(status="down", message=str(exc))

    async def get_schema(self) -> dict[str, Any]:
        return {
            "bot_token": {"type": "string", "secret": True, "label": "Bot Token (xoxb-...)"},
            "channels": {"type": "array", "items": "string", "label": "Channel names/IDs (empty = all)"},
            "oldest_days": {"type": "integer", "default": _DEFAULT_OLDEST_DAYS, "label": "Full sync lookback (days)"},
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _resolve_channel_ids(self, client: Any) -> list[str]:
        if self._channels:
            # Caller passed names or IDs — resolve names to IDs if needed
            ids = []
            resp = await client.conversations_list(types="public_channel,private_channel", limit=1000)
            name_to_id = {c["name"]: c["id"] for c in resp.get("channels", [])}
            for ch in self._channels:
                ids.append(name_to_id.get(ch, ch))  # fall back to treating it as an ID
            return ids

        # No filter — return all joined channels
        resp = await client.conversations_list(types="public_channel,private_channel", limit=1000)
        return [c["id"] for c in resp.get("channels", []) if c.get("is_member")]

    async def _fetch_channel(
        self,
        client: Any,
        channel_id: str,
        oldest_ts: str,
        latest_ts: str | None,
    ) -> AsyncIterator[list[ConnectorDocument]]:
        cursor = None
        while True:
            kwargs: dict[str, Any] = {
                "channel": channel_id,
                "oldest": oldest_ts,
                "limit": _BATCH_SIZE,
            }
            if latest_ts:
                kwargs["latest"] = latest_ts
            if cursor:
                kwargs["cursor"] = cursor

            resp = await client.conversations_history(**kwargs)
            messages = resp.get("messages", [])

            docs = [_message_to_doc(msg, channel_id) for msg in messages if msg.get("type") == "message"]
            if docs:
                yield docs

            next_cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not next_cursor:
                break
            cursor = next_cursor


def _to_slack_ts(dt: datetime) -> str:
    return str(dt.timestamp())


def _message_to_doc(msg: dict[str, Any], channel_id: str) -> ConnectorDocument:
    ts = msg.get("ts", "")
    text = msg.get("text", "")
    user = msg.get("user", msg.get("bot_id", "unknown"))
    occurred_at = None
    try:
        occurred_at = datetime.fromtimestamp(float(ts), tz=UTC).isoformat()
    except Exception:
        pass

    return ConnectorDocument(
        id=f"{channel_id}:{ts}",
        content=text,
        title=None,
        url=None,
        metadata={
            "channel_id": channel_id,
            "user": user,
            "ts": ts,
            "thread_ts": msg.get("thread_ts"),
            "reply_count": msg.get("reply_count", 0),
        },
        occurred_at=occurred_at,
    )
