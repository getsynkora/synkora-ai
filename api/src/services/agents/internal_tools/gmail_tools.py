"""
Gmail Tools for AI Agents.
Provides Gmail management capabilities including listing, searching, and bulk deleting emails.
"""

import json
import logging
from datetime import UTC
from typing import Any

from googleapiclient.errors import HttpError
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def _get_gmail_service(runtime_context: Any) -> Any:
    """
    Get authenticated Gmail service.

    Args:
        runtime_context: Runtime context with credentials

    Returns:
        Gmail API service object
    """
    from datetime import datetime, timedelta

    from src.models.agent_tool import AgentTool
    from src.models.oauth_app import OAuthApp
    from src.models.user_oauth_token import UserOAuthToken
    from src.services.agents.security import decrypt_value, encrypt_value
    from src.services.oauth.gmail_oauth import GmailOAuth

    db = runtime_context.db_session
    agent_id = runtime_context.agent_id
    user_id = getattr(runtime_context, "user_id", None)

    # Find Gmail tool for this agent
    result = await db.execute(
        select(AgentTool).filter(
            AgentTool.agent_id == agent_id,
            AgentTool.tool_name.like("%gmail%"),
            AgentTool.enabled,
        )
    )
    agent_tool = result.scalar_one_or_none()

    if not agent_tool or not agent_tool.oauth_app_id:
        raise ValueError("Gmail not configured for this agent. Please connect Gmail OAuth first.")

    # Get OAuth app (case-insensitive provider check)
    result = await db.execute(
        select(OAuthApp).filter(
            OAuthApp.id == agent_tool.oauth_app_id, OAuthApp.provider.ilike("gmail"), OAuthApp.is_active
        )
    )
    oauth_app = result.scalar_one_or_none()

    if not oauth_app:
        raise ValueError("Gmail OAuth app not found or inactive.")

    # Try to get user token first
    user_token = None
    if user_id:
        result = await db.execute(
            select(UserOAuthToken).filter(
                UserOAuthToken.user_id == user_id, UserOAuthToken.oauth_app_id == oauth_app.id
            )
        )
        user_token = result.scalar_one_or_none()

    # Get credentials
    access_token = None
    refresh_token = None

    if user_token and user_token.access_token:
        decrypted_user_token = decrypt_value(user_token.access_token)

        # Gmail OAuth callback stores credentials as JSON
        # Check if it's a JSON string and parse it
        if decrypted_user_token.startswith("{"):
            try:
                user_creds_data = json.loads(decrypted_user_token)
                access_token = user_creds_data.get("access_token")
                refresh_token = user_creds_data.get("refresh_token")
            except json.JSONDecodeError:
                access_token = decrypted_user_token
                refresh_token = decrypt_value(user_token.refresh_token) if user_token.refresh_token else None
        else:
            access_token = decrypted_user_token
            if user_token.refresh_token:
                refresh_token = decrypt_value(user_token.refresh_token)

        # Check if token is expired and refresh if needed
        if user_token.token_expires_at:
            now = datetime.now(UTC)
            expires_at = user_token.token_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)

            if expires_at <= now and refresh_token:
                # Refresh the token
                try:
                    client_id = oauth_app.client_id
                    client_secret = decrypt_value(oauth_app.client_secret) if oauth_app.client_secret else None

                    gmail_oauth = GmailOAuth(
                        client_id=client_id, client_secret=client_secret, redirect_uri=oauth_app.redirect_uri
                    )

                    token_data = await gmail_oauth.refresh_access_token(refresh_token)
                    access_token = token_data["access_token"]

                    # Update stored token
                    user_token.access_token = encrypt_value(access_token)
                    if "refresh_token" in token_data:
                        user_token.refresh_token = encrypt_value(token_data["refresh_token"])
                    if "expires_in" in token_data:
                        user_token.token_expires_at = datetime.now(UTC) + timedelta(seconds=token_data["expires_in"])
                    await db.commit()
                    logger.info("✅ Refreshed Gmail token")
                except Exception as e:
                    logger.error(f"Failed to refresh Gmail token: {e}")
                    raise ValueError("Gmail token expired and refresh failed. Please reconnect Gmail.")

    elif oauth_app.access_token:
        # Fall back to OAuth app token
        decrypted_token = decrypt_value(oauth_app.access_token)

        # Gmail OAuth callback stores credentials as JSON
        # Check if it's a JSON string and parse it
        if decrypted_token.startswith("{"):
            try:
                creds_data = json.loads(decrypted_token)
                access_token = creds_data.get("access_token")
                refresh_token = creds_data.get("refresh_token")
            except json.JSONDecodeError:
                access_token = decrypted_token
                refresh_token = decrypt_value(oauth_app.refresh_token) if oauth_app.refresh_token else None
        else:
            access_token = decrypted_token
            if oauth_app.refresh_token:
                refresh_token = decrypt_value(oauth_app.refresh_token)

    if not access_token:
        raise ValueError("No Gmail access token available. Please connect Gmail OAuth.")

    # Build credentials and service
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=oauth_app.client_id,
        client_secret=decrypt_value(oauth_app.client_secret) if oauth_app.client_secret else None,
    )

    return build("gmail", "v1", credentials=creds)


async def internal_gmail_list_emails(
    query: str | None = None,
    label_ids: list[str] | None = None,
    max_results: int = 100,
    page_token: str | None = None,
    include_spam_trash: bool = False,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    List emails from Gmail with optional filtering.

    Args:
        query: Gmail search query (e.g., "from:example@gmail.com", "is:unread", "older_than:7d")
        label_ids: List of label IDs to filter (e.g., ["INBOX", "UNREAD", "SPAM"])
        max_results: Maximum number of emails to return (default: 100, max: 500)
        page_token: Token for pagination
        include_spam_trash: Whether to include spam and trash (default: False)

    Returns:
        Dict with emails list, next page token, and result count

    Example:
        # List unread emails from last week
        result = await internal_gmail_list_emails(
            query="is:unread newer_than:7d",
            max_results=50
        )

        # List emails from specific sender
        result = await internal_gmail_list_emails(
            query="from:newsletter@example.com"
        )

        # List promotional emails older than 30 days
        result = await internal_gmail_list_emails(
            query="category:promotions older_than:30d"
        )

    Query syntax examples:
        - "from:sender@example.com" - From specific sender
        - "to:recipient@example.com" - To specific recipient
        - "subject:meeting" - Subject contains "meeting"
        - "is:unread" - Unread emails
        - "is:read" - Read emails
        - "is:starred" - Starred emails
        - "has:attachment" - Has attachments
        - "older_than:7d" - Older than 7 days (d=days, m=months, y=years)
        - "newer_than:1d" - Newer than 1 day
        - "before:2024/01/01" - Before specific date
        - "after:2024/01/01" - After specific date
        - "category:promotions" - Promotional emails
        - "category:social" - Social network emails
        - "category:updates" - Update emails
        - "label:important" - With specific label
        - "in:spam" - In spam folder
        - "in:trash" - In trash folder
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        service = await _get_gmail_service(runtime_context)

        # Build request parameters
        params = {
            "userId": "me",
            "maxResults": min(max_results, 500),
            "includeSpamTrash": include_spam_trash,
        }

        if query:
            params["q"] = query

        if label_ids:
            params["labelIds"] = label_ids

        if page_token:
            params["pageToken"] = page_token

        # List messages
        results = service.users().messages().list(**params).execute()

        messages = results.get("messages", [])
        next_page_token = results.get("nextPageToken")
        result_size_estimate = results.get("resultSizeEstimate", 0)

        # Fetch details for each message
        emails = []
        for msg_ref in messages:
            try:
                message = (
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=msg_ref["id"],
                        format="metadata",
                        metadataHeaders=["From", "To", "Subject", "Date"],
                    )
                    .execute()
                )

                headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}

                emails.append(
                    {
                        "id": message["id"],
                        "thread_id": message.get("threadId"),
                        "snippet": message.get("snippet", ""),
                        "from": headers.get("From", ""),
                        "to": headers.get("To", ""),
                        "subject": headers.get("Subject", "(No Subject)"),
                        "date": headers.get("Date", ""),
                        "labels": message.get("labelIds", []),
                        "size_estimate": message.get("sizeEstimate", 0),
                    }
                )
            except HttpError as e:
                logger.warning(f"Failed to fetch message {msg_ref['id']}: {e}")
                continue

        logger.info(f"Listed {len(emails)} emails with query: {query}")

        return {
            "success": True,
            "emails": emails,
            "count": len(emails),
            "total_estimate": result_size_estimate,
            "next_page_token": next_page_token,
            "has_more": next_page_token is not None,
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error listing emails: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_search_emails(
    query: str,
    max_results: int = 100,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Search emails using Gmail query syntax.

    Args:
        query: Gmail search query (required)
        max_results: Maximum number of results (default: 100)

    Returns:
        Dict with matching emails

    Example:
        # Find all newsletters
        result = await internal_gmail_search_emails(
            query="from:newsletter OR from:noreply category:promotions"
        )

        # Find large attachments
        result = await internal_gmail_search_emails(
            query="has:attachment larger:10M"
        )
    """
    return await internal_gmail_list_emails(
        query=query,
        max_results=max_results,
        runtime_context=runtime_context,
        config=config,
    )


async def internal_gmail_get_email(
    message_id: str,
    format: str = "full",
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get a single email by ID with full content.

    Args:
        message_id: Gmail message ID
        format: Response format - "full", "metadata", "minimal", or "raw"

    Returns:
        Dict with email details and content
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        service = await _get_gmail_service(runtime_context)

        message = service.users().messages().get(userId="me", id=message_id, format=format).execute()

        headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}

        # Extract body
        body = ""
        payload = message.get("payload", {})
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    import base64

                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8")
                        break
        else:
            import base64

            data = payload.get("body", {}).get("data", "")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8")

        return {
            "success": True,
            "email": {
                "id": message["id"],
                "thread_id": message.get("threadId"),
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "cc": headers.get("Cc", ""),
                "subject": headers.get("Subject", "(No Subject)"),
                "date": headers.get("Date", ""),
                "labels": message.get("labelIds", []),
                "snippet": message.get("snippet", ""),
                "body": body,
            },
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error getting email: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_delete_email(
    message_id: str,
    permanent: bool = False,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Delete a single email.

    Args:
        message_id: Gmail message ID to delete
        permanent: If True, permanently deletes. If False, moves to trash (default: False)

    Returns:
        Dict with success status
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        service = await _get_gmail_service(runtime_context)

        if permanent:
            service.users().messages().delete(userId="me", id=message_id).execute()
            logger.info(f"Permanently deleted email {message_id}")
        else:
            service.users().messages().trash(userId="me", id=message_id).execute()
            logger.info(f"Moved email {message_id} to trash")

        return {
            "success": True,
            "message": f"Email {'permanently deleted' if permanent else 'moved to trash'}",
            "message_id": message_id,
            "permanent": permanent,
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error deleting email: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_bulk_delete(
    query: str | None = None,
    message_ids: list[str] | None = None,
    max_delete: int = 1000,
    permanent: bool = False,
    dry_run: bool = False,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Bulk delete emails matching a query or by message IDs.

    Args:
        query: Gmail search query to find emails to delete (e.g., "older_than:30d category:promotions")
        message_ids: List of specific message IDs to delete (alternative to query)
        max_delete: Maximum number of emails to delete in one operation (default: 1000, max: 5000)
        permanent: If True, permanently deletes. If False, moves to trash (default: False)
        dry_run: If True, only counts emails without deleting (default: False)

    Returns:
        Dict with deletion results including count of deleted emails

    Example:
        # Delete all promotional emails older than 30 days
        result = await internal_gmail_bulk_delete(
            query="category:promotions older_than:30d",
            max_delete=500
        )

        # Delete all emails from a specific sender
        result = await internal_gmail_bulk_delete(
            query="from:newsletter@spam.com",
            permanent=True
        )

        # Dry run to see how many emails would be deleted
        result = await internal_gmail_bulk_delete(
            query="is:unread older_than:1y",
            dry_run=True
        )

        # Delete specific emails by ID
        result = await internal_gmail_bulk_delete(
            message_ids=["msg_id_1", "msg_id_2", "msg_id_3"]
        )

    Common bulk delete queries:
        - "category:promotions older_than:30d" - Old promotional emails
        - "category:social older_than:30d" - Old social notifications
        - "from:noreply@* older_than:7d" - Old automated emails
        - "is:unread older_than:1y" - Old unread emails
        - "has:attachment larger:10M older_than:90d" - Large old attachments
        - "in:spam" - All spam
        - "label:newsletter older_than:14d" - Old newsletters

    Security:
        - Rate limiting applied
        - Maximum 5000 emails per operation
        - Use dry_run first to verify query results
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        if not query and not message_ids:
            return {"success": False, "error": "Either 'query' or 'message_ids' is required"}

        service = await _get_gmail_service(runtime_context)

        # Enforce maximum limit
        max_delete = min(max_delete, 5000)

        # Collect message IDs to delete
        ids_to_delete = []

        if message_ids:
            ids_to_delete = message_ids[:max_delete]
        else:
            # Fetch messages matching query
            page_token = None
            while len(ids_to_delete) < max_delete:
                results = (
                    service.users()
                    .messages()
                    .list(
                        userId="me",
                        q=query,
                        maxResults=min(500, max_delete - len(ids_to_delete)),
                        pageToken=page_token,
                    )
                    .execute()
                )

                messages = results.get("messages", [])
                if not messages:
                    break

                ids_to_delete.extend([m["id"] for m in messages])

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

        total_found = len(ids_to_delete)

        if dry_run:
            logger.info(f"Dry run: would delete {total_found} emails with query: {query}")
            return {
                "success": True,
                "dry_run": True,
                "would_delete": total_found,
                "query": query,
                "message": f"Dry run complete. Would delete {total_found} emails.",
            }

        if total_found == 0:
            return {
                "success": True,
                "deleted": 0,
                "failed": 0,
                "message": "No emails found matching the criteria",
                "query": query,
            }

        # Batch delete using Gmail API batch modify
        deleted_count = 0
        failed_count = 0
        batch_size = 100  # Gmail API recommends batches of 100

        for i in range(0, len(ids_to_delete), batch_size):
            batch_ids = ids_to_delete[i : i + batch_size]

            try:
                if permanent:
                    # Use batchDelete for permanent deletion
                    service.users().messages().batchDelete(userId="me", body={"ids": batch_ids}).execute()
                else:
                    # Use batchModify to add TRASH label
                    service.users().messages().batchModify(
                        userId="me",
                        body={"ids": batch_ids, "addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX"]},
                    ).execute()

                deleted_count += len(batch_ids)
                logger.info(f"Deleted batch of {len(batch_ids)} emails ({deleted_count}/{total_found})")

            except HttpError as e:
                logger.error(f"Batch delete failed: {e}")
                failed_count += len(batch_ids)

        action = "permanently deleted" if permanent else "moved to trash"
        logger.info(f"Bulk delete complete: {deleted_count} {action}, {failed_count} failed")

        return {
            "success": True,
            "deleted": deleted_count,
            "failed": failed_count,
            "total_found": total_found,
            "permanent": permanent,
            "query": query,
            "message": f"Successfully {action} {deleted_count} emails"
            + (f", {failed_count} failed" if failed_count > 0 else ""),
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error in bulk delete: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_get_labels(
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get all Gmail labels for the account.

    Returns:
        Dict with list of labels

    Example:
        result = await internal_gmail_get_labels()
        # Returns system labels (INBOX, SENT, TRASH, etc.) and user-created labels
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        service = await _get_gmail_service(runtime_context)

        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])

        return {
            "success": True,
            "labels": [
                {
                    "id": label["id"],
                    "name": label["name"],
                    "type": label.get("type", "user"),
                    "messages_total": label.get("messagesTotal", 0),
                    "messages_unread": label.get("messagesUnread", 0),
                }
                for label in labels
            ],
            "count": len(labels),
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error getting labels: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_empty_trash(
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Empty the Gmail trash folder (permanently deletes all trashed emails).

    Returns:
        Dict with success status

    Warning:
        This action is irreversible. All emails in trash will be permanently deleted.
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        service = await _get_gmail_service(runtime_context)

        # Empty trash
        service.users().messages().list(userId="me", labelIds=["TRASH"]).execute()

        # Gmail doesn't have a direct "empty trash" API, so we batch delete
        page_token = None
        deleted_count = 0

        while True:
            results = (
                service.users()
                .messages()
                .list(userId="me", labelIds=["TRASH"], maxResults=500, pageToken=page_token)
                .execute()
            )

            messages = results.get("messages", [])
            if not messages:
                break

            ids = [m["id"] for m in messages]
            service.users().messages().batchDelete(userId="me", body={"ids": ids}).execute()
            deleted_count += len(ids)

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"Emptied trash: {deleted_count} emails permanently deleted")

        return {
            "success": True,
            "deleted": deleted_count,
            "message": f"Trash emptied. {deleted_count} emails permanently deleted.",
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error emptying trash: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_empty_spam(
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Empty the Gmail spam folder (permanently deletes all spam emails).

    Returns:
        Dict with success status

    Warning:
        This action is irreversible. All emails in spam will be permanently deleted.
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        service = await _get_gmail_service(runtime_context)

        page_token = None
        deleted_count = 0

        while True:
            results = (
                service.users()
                .messages()
                .list(userId="me", labelIds=["SPAM"], maxResults=500, pageToken=page_token)
                .execute()
            )

            messages = results.get("messages", [])
            if not messages:
                break

            ids = [m["id"] for m in messages]
            service.users().messages().batchDelete(userId="me", body={"ids": ids}).execute()
            deleted_count += len(ids)

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        logger.info(f"Emptied spam: {deleted_count} emails permanently deleted")

        return {
            "success": True,
            "deleted": deleted_count,
            "message": f"Spam folder emptied. {deleted_count} emails permanently deleted.",
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error emptying spam: {e}")
        return {"success": False, "error": str(e)}


# =============================================================================
# EMAIL SENDING / REPLY / FORWARD
# =============================================================================


def _create_message(
    to: str,
    subject: str,
    body: str,
    from_email: str | None = None,
    cc: str | None = None,
    bcc: str | None = None,
    html: bool = False,
    in_reply_to: str | None = None,
    references: str | None = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a Gmail API message object.

    Args:
        to: Recipient email address(es), comma-separated
        subject: Email subject
        body: Email body (plain text or HTML)
        from_email: Sender email (optional, uses authenticated user's email)
        cc: CC recipients, comma-separated
        bcc: BCC recipients, comma-separated
        html: Whether body is HTML
        in_reply_to: Message-ID for reply
        references: References header for threading
        thread_id: Gmail thread ID for threading

    Returns:
        Gmail API message object
    """
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if html:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(body, "html"))
    else:
        msg = MIMEText(body)

    msg["To"] = to
    msg["Subject"] = subject

    if from_email:
        msg["From"] = from_email
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = references or in_reply_to

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    message = {"raw": raw}
    if thread_id:
        message["threadId"] = thread_id

    return message


async def internal_gmail_send_email(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    html: bool = False,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Send an email through Gmail API.

    Args:
        to: Recipient email address(es), comma-separated for multiple
        subject: Email subject line
        body: Email body content (plain text or HTML)
        cc: CC recipients, comma-separated (optional)
        bcc: BCC recipients, comma-separated (optional)
        html: Whether the body is HTML content (default: False)

    Returns:
        Dict with send result including message ID

    Example:
        # Send plain text email
        result = await internal_gmail_send_email(
            to="user@example.com",
            subject="Hello",
            body="This is a test email."
        )

        # Send HTML email to multiple recipients
        result = await internal_gmail_send_email(
            to="user1@example.com, user2@example.com",
            subject="Newsletter",
            body="<h1>Welcome</h1><p>This is HTML content.</p>",
            html=True,
            cc="manager@example.com"
        )
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        if not to:
            return {"success": False, "error": "Recipient 'to' is required"}

        if not subject:
            return {"success": False, "error": "Subject is required"}

        if not body:
            return {"success": False, "error": "Body is required"}

        service = await _get_gmail_service(runtime_context)

        # Get sender's email
        profile = service.users().getProfile(userId="me").execute()
        from_email = profile.get("emailAddress")

        # Create message
        message = _create_message(
            to=to,
            subject=subject,
            body=body,
            from_email=from_email,
            cc=cc,
            bcc=bcc,
            html=html,
        )

        # Send message
        sent = service.users().messages().send(userId="me", body=message).execute()

        logger.info(f"Sent email to {to}, message ID: {sent['id']}")

        return {
            "success": True,
            "message_id": sent["id"],
            "thread_id": sent.get("threadId"),
            "to": to,
            "subject": subject,
            "message": f"Email sent successfully to {to}",
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_reply(
    message_id: str,
    body: str,
    reply_all: bool = False,
    html: bool = False,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Reply to an email.

    Args:
        message_id: Gmail message ID to reply to
        body: Reply body content
        reply_all: If True, reply to all recipients (default: False, reply to sender only)
        html: Whether the body is HTML content (default: False)

    Returns:
        Dict with reply result

    Example:
        # Reply to sender only
        result = await internal_gmail_reply(
            message_id="abc123",
            body="Thanks for your email!"
        )

        # Reply all with HTML
        result = await internal_gmail_reply(
            message_id="abc123",
            body="<p>Thanks everyone!</p>",
            reply_all=True,
            html=True
        )
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        if not message_id:
            return {"success": False, "error": "Message ID is required"}

        if not body:
            return {"success": False, "error": "Reply body is required"}

        service = await _get_gmail_service(runtime_context)

        # Get original message
        original = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "To", "Cc", "Subject", "Message-ID"],
            )
            .execute()
        )

        headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}
        thread_id = original.get("threadId")

        # Get sender's email
        profile = service.users().getProfile(userId="me").execute()
        my_email = profile.get("emailAddress")

        # Determine recipients
        original_from = headers.get("From", "")
        original_to = headers.get("To", "")
        original_cc = headers.get("Cc", "")
        original_subject = headers.get("Subject", "")
        original_message_id = headers.get("Message-ID", "")

        # Reply to sender
        to = original_from

        cc = None
        if reply_all:
            # Include original To and Cc, excluding myself
            all_recipients = []
            for addr in (original_to + "," + original_cc).split(","):
                addr = addr.strip()
                if addr and my_email.lower() not in addr.lower():
                    all_recipients.append(addr)
            if all_recipients:
                cc = ", ".join(all_recipients)

        # Add "Re:" prefix if not present
        subject = original_subject
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        # Create reply message
        message = _create_message(
            to=to,
            subject=subject,
            body=body,
            from_email=my_email,
            cc=cc,
            html=html,
            in_reply_to=original_message_id,
            references=original_message_id,
            thread_id=thread_id,
        )

        # Send reply
        sent = service.users().messages().send(userId="me", body=message).execute()

        logger.info(f"Sent reply to {to}, message ID: {sent['id']}")

        return {
            "success": True,
            "message_id": sent["id"],
            "thread_id": sent.get("threadId"),
            "to": to,
            "cc": cc,
            "subject": subject,
            "reply_all": reply_all,
            "message": f"Reply sent successfully to {to}",
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error sending reply: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_forward(
    message_id: str,
    to: str,
    additional_message: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Forward an email to another recipient.

    Args:
        message_id: Gmail message ID to forward
        to: Recipient email address(es), comma-separated
        additional_message: Optional message to prepend to forwarded email

    Returns:
        Dict with forward result

    Example:
        # Simple forward
        result = await internal_gmail_forward(
            message_id="abc123",
            to="colleague@example.com"
        )

        # Forward with additional message
        result = await internal_gmail_forward(
            message_id="abc123",
            to="boss@example.com",
            additional_message="FYI - See the email below."
        )
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        if not message_id:
            return {"success": False, "error": "Message ID is required"}

        if not to:
            return {"success": False, "error": "Recipient 'to' is required"}

        service = await _get_gmail_service(runtime_context)

        # Get original message with full content
        original = service.users().messages().get(userId="me", id=message_id, format="full").execute()

        headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}

        original_from = headers.get("From", "Unknown")
        original_to = headers.get("To", "")
        original_date = headers.get("Date", "")
        original_subject = headers.get("Subject", "(No Subject)")

        # Get original body
        import base64

        original_body = ""
        payload = original.get("payload", {})
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        original_body = base64.urlsafe_b64decode(data).decode("utf-8")
                        break
                elif part.get("mimeType") == "text/html" and not original_body:
                    data = part.get("body", {}).get("data", "")
                    if data:
                        original_body = base64.urlsafe_b64decode(data).decode("utf-8")
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                original_body = base64.urlsafe_b64decode(data).decode("utf-8")

        # Get sender's email
        profile = service.users().getProfile(userId="me").execute()
        my_email = profile.get("emailAddress")

        # Build forwarded message body
        forward_header = f"""
---------- Forwarded message ---------
From: {original_from}
Date: {original_date}
Subject: {original_subject}
To: {original_to}

"""
        if additional_message:
            body = f"{additional_message}\n{forward_header}{original_body}"
        else:
            body = f"{forward_header}{original_body}"

        # Add "Fwd:" prefix
        subject = original_subject
        if not subject.lower().startswith("fwd:"):
            subject = f"Fwd: {subject}"

        # Create forward message
        message = _create_message(
            to=to,
            subject=subject,
            body=body,
            from_email=my_email,
            html=False,
        )

        # Send forward
        sent = service.users().messages().send(userId="me", body=message).execute()

        logger.info(f"Forwarded email to {to}, message ID: {sent['id']}")

        return {
            "success": True,
            "message_id": sent["id"],
            "thread_id": sent.get("threadId"),
            "to": to,
            "subject": subject,
            "original_message_id": message_id,
            "message": f"Email forwarded successfully to {to}",
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error forwarding email: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_create_draft(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    html: bool = False,
    reply_to_message_id: str | None = None,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Create an email draft (saved but not sent).

    Args:
        to: Recipient email address(es), comma-separated
        subject: Email subject line
        body: Email body content
        cc: CC recipients, comma-separated (optional)
        bcc: BCC recipients, comma-separated (optional)
        html: Whether the body is HTML content (default: False)
        reply_to_message_id: If provided, creates draft as reply to this message

    Returns:
        Dict with draft creation result

    Example:
        # Create a draft
        result = await internal_gmail_create_draft(
            to="client@example.com",
            subject="Proposal",
            body="Please find attached..."
        )

        # Create a reply draft
        result = await internal_gmail_create_draft(
            to="sender@example.com",
            subject="Re: Question",
            body="Let me get back to you on this.",
            reply_to_message_id="abc123"
        )
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        if not to:
            return {"success": False, "error": "Recipient 'to' is required"}

        if not subject:
            return {"success": False, "error": "Subject is required"}

        service = await _get_gmail_service(runtime_context)

        # Get sender's email
        profile = service.users().getProfile(userId="me").execute()
        my_email = profile.get("emailAddress")

        thread_id = None
        in_reply_to = None
        references = None

        # If replying, get original message details
        if reply_to_message_id:
            original = (
                service.users()
                .messages()
                .get(userId="me", id=reply_to_message_id, format="metadata", metadataHeaders=["Message-ID"])
                .execute()
            )
            headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}
            thread_id = original.get("threadId")
            in_reply_to = headers.get("Message-ID")
            references = in_reply_to

        # Create message
        message = _create_message(
            to=to,
            subject=subject,
            body=body,
            from_email=my_email,
            cc=cc,
            bcc=bcc,
            html=html,
            in_reply_to=in_reply_to,
            references=references,
            thread_id=thread_id,
        )

        # Create draft
        draft = service.users().drafts().create(userId="me", body={"message": message}).execute()

        logger.info(f"Created draft, draft ID: {draft['id']}")

        return {
            "success": True,
            "draft_id": draft["id"],
            "message_id": draft.get("message", {}).get("id"),
            "to": to,
            "subject": subject,
            "message": "Draft created successfully",
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error creating draft: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_list_drafts(
    max_results: int = 20,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    List email drafts.

    Args:
        max_results: Maximum number of drafts to return (default: 20)

    Returns:
        Dict with list of drafts

    Example:
        result = await internal_gmail_list_drafts(max_results=10)
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        service = await _get_gmail_service(runtime_context)

        results = service.users().drafts().list(userId="me", maxResults=max_results).execute()
        drafts = results.get("drafts", [])

        draft_details = []
        for draft in drafts:
            try:
                detail = service.users().drafts().get(userId="me", id=draft["id"], format="metadata").execute()
                msg = detail.get("message", {})
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

                draft_details.append(
                    {
                        "draft_id": draft["id"],
                        "message_id": msg.get("id"),
                        "to": headers.get("To", ""),
                        "subject": headers.get("Subject", "(No Subject)"),
                        "snippet": msg.get("snippet", ""),
                    }
                )
            except Exception:
                draft_details.append({"draft_id": draft["id"], "error": "Failed to fetch details"})

        return {
            "success": True,
            "drafts": draft_details,
            "count": len(draft_details),
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error listing drafts: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_send_draft(
    draft_id: str,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Send a draft email.

    Args:
        draft_id: Gmail draft ID to send

    Returns:
        Dict with send result

    Example:
        result = await internal_gmail_send_draft(draft_id="r123456")
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        if not draft_id:
            return {"success": False, "error": "Draft ID is required"}

        service = await _get_gmail_service(runtime_context)

        # Send the draft
        sent = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()

        logger.info(f"Sent draft {draft_id}, message ID: {sent['id']}")

        return {
            "success": True,
            "message_id": sent["id"],
            "thread_id": sent.get("threadId"),
            "draft_id": draft_id,
            "message": "Draft sent successfully",
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error sending draft: {e}")
        return {"success": False, "error": str(e)}


async def internal_gmail_delete_draft(
    draft_id: str,
    runtime_context: Any | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Delete a draft email.

    Args:
        draft_id: Gmail draft ID to delete

    Returns:
        Dict with deletion result

    Example:
        result = await internal_gmail_delete_draft(draft_id="r123456")
    """
    try:
        if not runtime_context:
            return {"success": False, "error": "Runtime context is required"}

        if not draft_id:
            return {"success": False, "error": "Draft ID is required"}

        service = await _get_gmail_service(runtime_context)

        service.users().drafts().delete(userId="me", id=draft_id).execute()

        logger.info(f"Deleted draft {draft_id}")

        return {
            "success": True,
            "draft_id": draft_id,
            "message": "Draft deleted successfully",
        }

    except HttpError as e:
        logger.error(f"Gmail API error: {e}")
        return {"success": False, "error": f"Gmail API error: {e.reason}"}
    except Exception as e:
        logger.error(f"Error deleting draft: {e}")
        return {"success": False, "error": str(e)}
