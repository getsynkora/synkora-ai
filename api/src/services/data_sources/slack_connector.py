"""Slack data source connector."""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.data_source import DataSource
from src.models.document import Document
from src.services.storage.s3_storage import S3StorageService

from .base_connector import BaseConnector

logger = logging.getLogger(__name__)


class SlackConnector(BaseConnector):
    """Connector for Slack workspace data."""

    def __init__(self, data_source: DataSource, db: AsyncSession):
        """
        Initialize Slack connector.

        Args:
            data_source: DataSource model instance
            db: Database session
        """
        super().__init__(data_source, db)
        self.client: WebClient | None = None

    async def connect(self) -> bool:
        """Establish connection to Slack."""
        try:
            access_token = await self._get_access_token()
            if not access_token:
                logger.error("No access token found for data source")
                return False

            self.client = WebClient(token=access_token)

            # Test the connection
            response = self.client.auth_test()
            logger.info(f"Connected to Slack workspace: {response['team']}")
            return True

        except SlackApiError as e:
            logger.error(f"Failed to connect to Slack: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to Slack: {e}")
            return False

    def _try_decrypt(self, encrypted: str, source_label: str) -> str | None:
        """Decrypt a candidate token, or None (never raise) so the caller can fall
        through to the next candidate in the priority chain instead of aborting
        the whole lookup on one corrupted/stale credential."""
        from src.services.agents.security import decrypt_value

        try:
            return decrypt_value(encrypted)
        except Exception as e:
            logger.warning(
                f"Could not decrypt {source_label} for data source {self.data_source.name} "
                f"— skipping to next credential source: {e}"
            )
            return None

    async def _get_access_token(self) -> str | None:
        """
        Get decrypted access token using user-first resolution.

        Priority:
        1. Linked SlackBot's bot token (reuses an existing agent's Slack connection)
        2. User's personal OAuth token (from UserOAuthToken table)
        3. Data source's direct access_token_encrypted
        4. OAuth app's admin token (fallback)

        A candidate that fails to decrypt is skipped (not fatal) so one corrupted
        or revoked credential doesn't block falling through to the next source.
        """
        from uuid import UUID as UUIDType

        from src.models.slack_bot import SlackBot
        from src.models.user_oauth_token import UserOAuthToken

        # First, try to reuse an existing agent's Slack bot connection
        if self.data_source.slack_bot_id:
            result = await self.db.execute(select(SlackBot).filter(SlackBot.id == self.data_source.slack_bot_id))
            slack_bot = result.scalar_one_or_none()

            if slack_bot and slack_bot.slack_bot_token:
                logger.info(f"Using linked SlackBot token for data source {self.data_source.name}")
                token = self._try_decrypt(slack_bot.slack_bot_token, "linked SlackBot token")
                if token:
                    return token

        # Next, try to get user's personal token if OAuth app is linked
        if self.data_source.oauth_app_id:
            # Get account_id from config (set when user connected the data source)
            account_id_str = self.data_source.config.get("connected_by_account_id")

            if account_id_str:
                try:
                    # Convert string to UUID for DB query
                    account_id = UUIDType(account_id_str) if isinstance(account_id_str, str) else account_id_str
                except ValueError:
                    logger.warning(f"Invalid account_id in config: {account_id_str}")
                    account_id = None

                if account_id:
                    # Look up user's personal token
                    result = await self.db.execute(
                        select(UserOAuthToken).filter(
                            UserOAuthToken.account_id == account_id,
                            UserOAuthToken.oauth_app_id == self.data_source.oauth_app_id,
                        )
                    )
                    user_token = result.scalar_one_or_none()

                    if user_token and user_token.access_token:
                        logger.info(f"Using user's personal Slack token for data source {self.data_source.name}")
                        token = self._try_decrypt(user_token.access_token, "user's personal token")
                        if token:
                            return token
            else:
                # No specific user - try to find any user token for this tenant/oauth_app
                # This handles cases where the data source was created before we tracked account_id
                result = await self.db.execute(
                    select(UserOAuthToken).filter(UserOAuthToken.oauth_app_id == self.data_source.oauth_app_id)
                )
                user_token = result.scalar_one_or_none()

                if user_token and user_token.access_token:
                    logger.info(f"Using first available user token for Slack data source {self.data_source.name}")
                    token = self._try_decrypt(user_token.access_token, "first available user token")
                    if token:
                        return token

        # Fall back to data source's direct token
        if self.data_source.access_token_encrypted:
            logger.info(f"Using data source's direct token for {self.data_source.name}")
            token = self._try_decrypt(self.data_source.access_token_encrypted, "data source's direct token")
            if token:
                return token

        # Fall back to OAuth app's admin token
        if self.data_source.oauth_app_id and self.data_source.oauth_app:
            oauth_app = self.data_source.oauth_app
            if oauth_app.access_token:
                logger.info(f"Using OAuth app admin token for Slack data source {self.data_source.name}")
                token = self._try_decrypt(oauth_app.access_token, "OAuth app admin token")
                if token:
                    return token

        return None

    async def disconnect(self) -> None:
        """Close connection to Slack."""
        self.client = None
        logger.info("Disconnected from Slack")

    async def test_connection(self) -> dict[str, Any]:
        """Test the Slack connection."""
        try:
            if not self.client:
                connected = await self.connect()
                if not connected:
                    return {"success": False, "message": "Failed to connect to Slack", "details": {}}

            response = self.client.auth_test()

            return {
                "success": True,
                "message": "Successfully connected to Slack",
                "details": {
                    "team": response.get("team"),
                    "user": response.get("user"),
                    "team_id": response.get("team_id"),
                    "user_id": response.get("user_id"),
                },
            }

        except SlackApiError as e:
            return {
                "success": False,
                "message": f"Slack API error: {e.response['error']}",
                "details": {"error": str(e)},
            }
        except Exception as e:
            return {"success": False, "message": f"Unexpected error: {str(e)}", "details": {"error": str(e)}}

    async def fetch_documents(self, since: datetime | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """Fetch messages from Slack channels."""
        if not self.client:
            raise ConnectionError("Not connected to Slack")

        documents = []
        config = self.data_source.config

        # Get channels to sync — support both "channel_ids" (IDs) and "channels" (names or IDs)
        channel_ids = config.get("channel_ids", [])
        include_threads = config.get("include_threads", True)
        include_private = config.get("include_private", False)

        channels_raw: list[str] = []
        if not channel_ids:
            # Fall back to "channels" key which may contain names or IDs
            channels_raw = config.get("channels", [])
            if isinstance(channels_raw, str):
                channels_raw = [c.strip() for c in channels_raw.split(",") if c.strip()]
            if channels_raw:
                channel_ids = await self._resolve_channel_names(channels_raw)
                if not channel_ids:
                    raise ConnectionError(
                        f"Could not find Slack channel(s): {', '.join(channels_raw)}. "
                        "If this is a private channel, invite the bot to the channel first "
                        "(type /invite @<app-name> in the channel)."
                    )

        # Only fall back to all channels if nothing is configured at all
        if not channel_ids and not channels_raw:
            channel_ids = await self._get_all_channels(include_private)

        # Default lookback for first sync — avoid fetching entire channel history
        if since is None:
            lookback_days = config.get("initial_sync_days", 30)
            since = datetime.now(UTC) - timedelta(days=lookback_days)

        oldest = str(int(since.timestamp()))

        for channel_id in channel_ids:
            try:
                # Get channel info
                channel_info = self.client.conversations_info(channel=channel_id)
                channel_name = channel_info["channel"]["name"]
                is_member = channel_info["channel"].get("is_member", False)

                # Join channel if not a member
                if not is_member:
                    try:
                        self.client.conversations_join(channel=channel_id)
                        logger.info(f"Joined channel: {channel_name}")
                    except SlackApiError as join_error:
                        logger.warning(f"Could not join channel {channel_name}: {join_error.response['error']}")
                        # Skip this channel if we can't join
                        continue

                # Fetch messages
                messages = await self._fetch_channel_messages(channel_id, channel_name, oldest, limit)
                documents.extend(messages)

                # Fetch thread replies if enabled
                if include_threads:
                    for message in messages:
                        if message.get("metadata", {}).get("thread_ts"):
                            thread_messages = await self._fetch_thread_replies(
                                channel_id, channel_name, message["metadata"]["thread_ts"]
                            )
                            documents.extend(thread_messages)

            except SlackApiError as e:
                logger.error(f"Error fetching from channel {channel_id}: {e}")
                continue

        return documents[:limit] if limit else documents

    async def _resolve_channel_names(self, names_or_ids: list[str]) -> list[str]:
        """Resolve a mix of channel names and IDs to channel IDs."""
        resolved = []
        unresolved_names = []

        for entry in names_or_ids:
            # Already an ID (starts with C, G, D followed by alphanumeric)
            if entry.startswith(("C", "G", "D")) and len(entry) >= 9:
                resolved.append(entry)
            else:
                unresolved_names.append(entry.lstrip("#").lower())

        if unresolved_names:
            try:
                response = self.client.conversations_list(
                    types="public_channel,private_channel",
                    exclude_archived=True,
                    limit=1000,
                )
                for channel in response.get("channels", []):
                    if channel["name"].lower() in unresolved_names:
                        resolved.append(channel["id"])
                        logger.info(f"Resolved channel name '{channel['name']}' to ID {channel['id']}")
            except SlackApiError as e:
                logger.error(f"Error resolving channel names: {e}")

        return resolved

    async def _get_all_channels(self, include_private: bool = False) -> list[str]:
        """Get all accessible channel IDs."""
        channel_ids = []

        try:
            # Get public channels
            response = self.client.conversations_list(
                types="public_channel" if not include_private else "public_channel,private_channel",
                exclude_archived=True,
            )

            for channel in response["channels"]:
                channel_ids.append(channel["id"])

        except SlackApiError as e:
            logger.error(f"Error fetching channels: {e}")

        return channel_ids

    async def _fetch_channel_messages(
        self, channel_id: str, channel_name: str, oldest: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Fetch messages from a specific channel."""
        messages = []
        cursor = None

        try:
            while True:
                response = self.client.conversations_history(
                    channel=channel_id, oldest=oldest, limit=min(limit or 1000, 1000), cursor=cursor
                )

                for msg in response["messages"]:
                    # Skip bot messages if configured
                    if msg.get("subtype") == "bot_message" and not self.data_source.config.get("include_bots", False):
                        continue

                    # Get user info
                    user_name = await self._get_user_name(msg.get("user"))

                    document = {
                        "id": f"{channel_id}_{msg['ts']}",
                        "text": msg.get("text", ""),
                        "metadata": {
                            "source": "SLACK",
                            "channel": channel_name,
                            "channel_id": channel_id,
                            "user": user_name,
                            "user_id": msg.get("user"),
                            "timestamp": datetime.fromtimestamp(float(msg["ts"])).isoformat(),
                            "thread_ts": msg.get("thread_ts"),
                            "message_type": msg.get("subtype", "message"),
                        },
                    }
                    messages.append(document)

                # Check if there are more messages
                if not response.get("has_more") or (limit and len(messages) >= limit):
                    break

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

        except SlackApiError as e:
            logger.error(f"Error fetching messages from {channel_id}: {e}")

        return messages

    async def _fetch_thread_replies(self, channel_id: str, channel_name: str, thread_ts: str) -> list[dict[str, Any]]:
        """Fetch replies in a thread."""
        messages = []

        try:
            response = self.client.conversations_replies(channel=channel_id, ts=thread_ts)

            for msg in response["messages"][1:]:  # Skip the parent message
                user_name = await self._get_user_name(msg.get("user"))

                document = {
                    "id": f"{channel_id}_{msg['ts']}",
                    "text": msg.get("text", ""),
                    "metadata": {
                        "source": "SLACK",
                        "channel": channel_name,
                        "channel_id": channel_id,
                        "user": user_name,
                        "user_id": msg.get("user"),
                        "timestamp": datetime.fromtimestamp(float(msg["ts"])).isoformat(),
                        "thread_ts": thread_ts,
                        "is_reply": True,
                        "message_type": msg.get("subtype", "message"),
                    },
                }
                messages.append(document)

        except SlackApiError as e:
            logger.error(f"Error fetching thread replies: {e}")

        return messages

    async def _get_user_name(self, user_id: str | None) -> str:
        """Get user name from user ID."""
        if not user_id:
            return "Unknown"

        try:
            response = self.client.users_info(user=user_id)
            user = response["user"]
            return user.get("real_name") or user.get("display_name") or user.get("name") or user_id
        except (SlackApiError, KeyError):
            return user_id

    async def _store_message_to_s3_and_db(
        self, message_data: dict[str, Any], raw_message: dict[str, Any]
    ) -> Document | None:
        """
        Store message to S3 and create Document record.

        Args:
            message_data: Processed message data with text and metadata
            raw_message: Raw Slack API message response

        Returns:
            Document instance or None if failed
        """
        try:
            # Initialize S3 service
            s3 = S3StorageService()

            # Generate S3 key
            timestamp = datetime.fromisoformat(message_data["metadata"]["timestamp"])
            filename = f"message-{message_data['id']}.json"
            s3_key = s3.generate_key(
                tenant_id=self.data_source.tenant_id, source_type="SLACK", filename=filename, timestamp=timestamp
            )

            # Upload raw message to S3
            raw_json = json.dumps(raw_message, indent=2)
            s3_result = s3.upload_file(
                file_content=raw_json.encode("utf-8"),
                key=s3_key,
                content_type="application/json",
                metadata={
                    "channel": message_data["metadata"]["channel"],
                    "user": message_data["metadata"]["user"],
                    "timestamp": message_data["metadata"]["timestamp"],
                    "message_type": message_data["metadata"]["message_type"],
                },
            )

            # Generate Slack permalink
            channel_id = message_data["metadata"]["channel_id"]
            msg_ts = raw_message["ts"].replace(".", "")
            self.data_source.config.get("team_id", "")
            slack_url = f"https://slack.com/archives/{channel_id}/p{msg_ts}"

            # Create Document record
            document = Document(
                tenant_id=self.data_source.tenant_id,
                knowledge_base_id=None,  # Will be set when added to KB
                data_source_id=self.data_source.id,
                title=f"Slack message in #{message_data['metadata']['channel']}",
                content=message_data["text"],
                source_type="SLACK",
                external_id=message_data["id"],
                external_url=slack_url,
                s3_bucket=s3_result["bucket"],
                s3_key=s3_result["key"],
                s3_url=s3_result["url"],
                file_size=len(raw_json),
                mime_type="application/json",
                metadata={
                    "channel": message_data["metadata"]["channel"],
                    "channel_id": message_data["metadata"]["channel_id"],
                    "user": message_data["metadata"]["user"],
                    "user_id": message_data["metadata"]["user_id"],
                    "timestamp": message_data["metadata"]["timestamp"],
                    "thread_ts": message_data["metadata"].get("thread_ts"),
                    "is_reply": message_data["metadata"].get("is_reply", False),
                    "message_type": message_data["metadata"]["message_type"],
                },
            )

            self.db.add(document)
            await self.db.commit()
            await self.db.refresh(document)

            logger.info(f"Stored Slack message {message_data['id']} to S3 and DB")
            return document

        except Exception as e:
            logger.error(f"Failed to store message to S3/DB: {e}")
            await self.db.rollback()
            return None

    async def sync_to_knowledge_base(
        self, knowledge_base_id: str, since: datetime | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """
        Sync Slack messages to knowledge base with S3 storage.

        Args:
            knowledge_base_id: Target knowledge base ID
            since: Only sync messages after this time
            limit: Maximum number of messages to sync

        Returns:
            Sync result with statistics
        """
        try:
            if not self.client:
                await self.connect()

            # Fetch messages
            messages = await self.fetch_documents(since=since, limit=limit)

            stored_count = 0
            failed_count = 0

            for msg_data in messages:
                # Get raw message for S3 storage
                # Note: In production, you'd want to fetch the full message
                # For now, we'll reconstruct from metadata
                raw_message = {
                    "ts": msg_data["id"].split("_")[1],
                    "text": msg_data["text"],
                    "user": msg_data["metadata"]["user_id"],
                    "type": "message",
                    "subtype": msg_data["metadata"]["message_type"],
                    "channel": msg_data["metadata"]["channel_id"],
                    "thread_ts": msg_data["metadata"].get("thread_ts"),
                }

                # Store to S3 and create Document
                document = await self._store_message_to_s3_and_db(msg_data, raw_message)

                if document:
                    # Associate with knowledge base
                    document.knowledge_base_id = knowledge_base_id
                    await self.db.commit()
                    stored_count += 1
                else:
                    failed_count += 1

            return {
                "success": True,
                "total_fetched": len(messages),
                "stored": stored_count,
                "failed": failed_count,
                "message": f"Synced {stored_count} messages to knowledge base",
            }

        except Exception as e:
            logger.error(f"Sync to knowledge base failed: {e}")
            return {"success": False, "error": str(e), "message": "Failed to sync messages"}

    async def get_document_count(self) -> int:
        """Get total number of messages."""
        # This is an approximation as Slack doesn't provide a direct count
        # We'll return the count from the last sync
        return len(await self.fetch_documents())

    def get_required_config_fields(self) -> list[str]:
        """Get required configuration fields."""
        return []  # All config is optional, channels can be auto-discovered

    def get_oauth_url(self) -> str | None:
        """Get Slack OAuth URL."""
        from src.services.oauth.slack_oauth import SlackOAuth

        oauth = SlackOAuth()
        return oauth.get_authorization_url(state=f"data_source_{self.data_source.id}")

    async def handle_oauth_callback(self, code: str) -> dict[str, Any]:
        """Handle Slack OAuth callback."""
        from src.services.agents.security import encrypt_value
        from src.services.oauth.slack_oauth import SlackOAuth

        try:
            oauth = SlackOAuth()
            token_data = await oauth.exchange_code(code)

            # Store encrypted access token
            access_token = token_data.get("access_token")
            if access_token:
                self.data_source.access_token_encrypted = encrypt_value(access_token)

            # Store metadata in config
            team_info = token_data.get("team", {})
            self.data_source.config = {
                **(self.data_source.config or {}),
                "team_id": team_info.get("id"),
                "team_name": team_info.get("name"),
                "bot_user_id": token_data.get("bot_user_id"),
            }
            self.data_source.is_connected = True
            await self.db.commit()

            return {
                "success": True,
                "message": "Successfully connected to Slack",
                "team": team_info.get("name"),
            }

        except Exception as e:
            logger.error(f"OAuth callback error: {e}")
            return {"success": False, "message": f"Failed to complete OAuth: {str(e)}"}
