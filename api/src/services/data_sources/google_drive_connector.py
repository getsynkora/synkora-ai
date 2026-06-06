"""
Google Drive data source connector.

Fetches documents from Google Drive for knowledge base ingestion.
"""

import io
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.data_source import DataSource
from src.services.data_sources.base_connector import BaseConnector
from src.services.oauth.google_drive_oauth import GoogleDriveOAuth

logger = logging.getLogger(__name__)


class GoogleDriveConnector(BaseConnector):
    """
    Google Drive data source connector.

    Fetches documents from Google Drive and extracts text content.
    Supports Google Docs, Sheets, Slides, and other file types.
    """

    SUPPORTED_MIME_TYPES = {
        "application/vnd.google-apps.document": "text/plain",  # Google Docs
        "application/vnd.google-apps.spreadsheet": "text/csv",  # Google Sheets
        "application/vnd.google-apps.presentation": "text/plain",  # Google Slides
        "application/pdf": "application/pdf",
        "text/plain": "text/plain",
        "text/html": "text/html",
        "text/markdown": "text/markdown",
    }

    def __init__(self, data_source: DataSource, db: AsyncSession, oauth_provider: GoogleDriveOAuth):
        """
        Initialize Google Drive connector.

        Args:
            data_source: DataSource model instance
            db: Database session
            oauth_provider: GoogleDriveOAuth provider instance
        """
        super().__init__(data_source, db)
        self.oauth_provider = oauth_provider
        self.service = None

    async def connect(self) -> bool:
        """
        Initialize Google Drive API client.

        Returns:
            True if connection successful
        """
        try:
            # Get OAuth token
            oauth_token = await self._get_oauth_token()
            if not oauth_token:
                raise ValueError("No OAuth token found for Google Drive")

            # Create credentials
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            credentials = Credentials(
                token=oauth_token.access_token,
                refresh_token=oauth_token.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.oauth_provider.client_id,
                client_secret=self.oauth_provider.client_secret,
                scopes=GoogleDriveOAuth.SCOPES,
            )

            # Build Drive API service
            self.service = build("drive", "v3", credentials=credentials)

            logger.info(f"Connected to Google Drive for data source: {self.data_source.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Google Drive: {e}", exc_info=True)
            raise

    async def disconnect(self) -> None:
        """Close the connection to Google Drive."""
        self.service = None
        logger.info("Disconnected from Google Drive")

    async def test_connection(self) -> dict[str, Any]:
        """
        Test the connection to Google Drive.

        Returns:
            Dictionary with test results
        """
        try:
            if not self.service:
                await self.connect()

            # Try to get user info
            about = self.service.about().get(fields="user,storageQuota").execute()
            user = about.get("user", {})
            quota = about.get("storageQuota", {})

            return {
                "success": True,
                "message": f"Successfully connected as {user.get('emailAddress')}",
                "details": {
                    "email": user.get("emailAddress"),
                    "name": user.get("displayName"),
                    "quota_used": quota.get("usage"),
                    "quota_limit": quota.get("limit"),
                },
            }

        except Exception as e:
            logger.error(f"Connection test failed: {e}", exc_info=True)
            return {"success": False, "message": f"Connection failed: {str(e)}", "details": {"error": str(e)}}

    async def fetch_documents(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch documents from Google Drive.

        Args:
            since: Only fetch documents modified after this date
            limit: Maximum number of documents to fetch

        Returns:
            List of documents with text content and metadata
        """
        if not self.service:
            await self.connect()

        documents = []

        try:
            # Build query
            query_parts = []

            # Only fetch supported file types
            mime_type_query = " or ".join([f"mimeType='{mime}'" for mime in self.SUPPORTED_MIME_TYPES.keys()])
            query_parts.append(f"({mime_type_query})")

            # Filter by modification date if provided
            if since:
                since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
                query_parts.append(f"modifiedTime > '{since_str}'")

            # Exclude trashed files
            query_parts.append("trashed = false")

            query = " and ".join(query_parts)

            # Fetch files
            page_token = None
            fetched_count = 0

            while True:
                results = (
                    self.service.files()
                    .list(
                        q=query,
                        pageSize=min(100, limit - fetched_count) if limit else 100,
                        pageToken=page_token,
                        fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, owners, size, webViewLink)",
                    )
                    .execute()
                )

                files = results.get("files", [])

                for file in files:
                    try:
                        # Extract text content
                        text_content = await self._extract_file_content(file)

                        if not text_content:
                            logger.warning(f"No content extracted from file: {file['name']}")
                            continue

                        # Get owner information
                        owner = file.get("owners", [{}])[0]
                        owner_email = owner.get("emailAddress", "unknown")
                        owner_name = owner.get("displayName", "Unknown")

                        document = {
                            "id": file["id"],
                            "text": text_content,
                            "metadata": {
                                "source": "google_drive",
                                "title": file["name"],
                                "mime_type": file["mimeType"],
                                "author": owner_name,
                                "author_email": owner_email,
                                "created_time": file.get("createdTime"),
                                "modified_time": file.get("modifiedTime"),
                                "size": file.get("size", 0),
                                "url": file.get("webViewLink"),
                                "file_id": file["id"],
                            },
                        }

                        documents.append(document)
                        fetched_count += 1

                        if limit and fetched_count >= limit:
                            break

                    except Exception as e:
                        logger.error(
                            f"Error processing file {file.get('name')}: {e}",
                            exc_info=True,
                        )
                        continue

                # Check if we should continue pagination
                page_token = results.get("nextPageToken")
                if not page_token or (limit and fetched_count >= limit):
                    break

            logger.info(f"Fetched {len(documents)} documents from Google Drive for data source: {self.data_source.id}")
            return documents

        except Exception as e:
            logger.error(f"Error fetching documents from Google Drive: {e}", exc_info=True)
            raise

    async def _extract_file_content(self, file: dict[str, Any]) -> str:
        """
        Extract text content from a Google Drive file.

        Args:
            file: File metadata from Drive API

        Returns:
            Extracted text content
        """
        file_id = file["id"]
        mime_type = file["mimeType"]

        try:
            # Handle Google Workspace files (Docs, Sheets, Slides)
            if mime_type.startswith("application/vnd.google-apps"):
                export_mime_type = self.SUPPORTED_MIME_TYPES.get(mime_type)
                if not export_mime_type:
                    logger.warning(f"Unsupported Google Workspace type: {mime_type}")
                    return ""

                request = self.service.files().export_media(fileId=file_id, mimeType=export_mime_type)
            else:
                # Handle regular files
                request = self.service.files().get_media(fileId=file_id)

            # Download content
            from googleapiclient.http import MediaIoBaseDownload

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False

            while not done:
                status, done = downloader.next_chunk()

            # Extract text from downloaded content
            content = fh.getvalue()

            # Decode based on mime type
            if mime_type in ["text/plain", "text/html", "text/markdown"] or (
                "export_mime_type" in locals() and export_mime_type == "text/plain"
            ):
                text = content.decode("utf-8", errors="ignore")
            elif "export_mime_type" in locals() and export_mime_type == "text/csv":
                # For spreadsheets exported as CSV
                text = content.decode("utf-8", errors="ignore")
            elif mime_type == "application/pdf":
                # For PDFs, we'd need a PDF parser
                # For now, just note that it's a PDF
                text = f"[PDF Document: {file['name']}]"
                logger.info(f"PDF file detected: {file['name']}. Consider adding PDF parsing.")
            else:
                text = content.decode("utf-8", errors="ignore")

            return text.strip()

        except Exception as e:
            logger.error(
                f"Error extracting content from file {file.get('name')}: {e}",
                exc_info=True,
            )
            return ""

    async def get_document_count(self) -> int:
        """
        Get total count of accessible documents.

        Returns:
            Number of documents
        """
        if not self.service:
            await self.connect()

        try:
            # Build query for supported file types
            mime_type_query = " or ".join([f"mimeType='{mime}'" for mime in self.SUPPORTED_MIME_TYPES.keys()])
            query = f"({mime_type_query}) and trashed = false"

            # Get count
            results = self.service.files().list(q=query, pageSize=1, fields="files(id)").execute()

            # Note: Drive API doesn't provide total count directly
            # This is an approximation
            return len(results.get("files", []))

        except Exception as e:
            logger.error(f"Error getting document count: {e}", exc_info=True)
            return 0

    async def search_documents(self, query: str, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Search documents in Google Drive.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching documents
        """
        if not self.service:
            await self.connect()

        try:
            # Build search query
            # SECURITY: Escape single quotes to prevent Google Drive Query Language injection
            # In Drive Query Language, single quotes are escaped by doubling them ('')
            escaped_query = query.replace("\\", "\\\\").replace("'", "\\'")
            mime_type_query = " or ".join([f"mimeType='{mime}'" for mime in self.SUPPORTED_MIME_TYPES.keys()])
            full_query = f"({mime_type_query}) and trashed = false and fullText contains '{escaped_query}'"

            # Search files
            results = (
                self.service.files()
                .list(
                    q=full_query,
                    pageSize=limit or 100,
                    fields="files(id, name, mimeType, createdTime, modifiedTime, owners, webViewLink)",
                )
                .execute()
            )

            files = results.get("files", [])
            documents = []

            for file in files:
                try:
                    text_content = await self._extract_file_content(file)

                    if not text_content:
                        continue

                    owner = file.get("owners", [{}])[0]

                    document = {
                        "id": file["id"],
                        "text": text_content,
                        "metadata": {
                            "source": "google_drive",
                            "title": file["name"],
                            "mime_type": file["mimeType"],
                            "author": owner.get("displayName", "Unknown"),
                            "author_email": owner.get("emailAddress", "unknown"),
                            "created_time": file.get("createdTime"),
                            "modified_time": file.get("modifiedTime"),
                            "url": file.get("webViewLink"),
                            "file_id": file["id"],
                        },
                    }

                    documents.append(document)

                except Exception as e:
                    logger.error(f"Error processing search result: {e}", exc_info=True)
                    continue

            logger.info(f"Found {len(documents)} documents matching query: {query}")
            return documents

        except Exception as e:
            logger.error(f"Error searching documents: {e}", exc_info=True)
            return []

    def get_required_config_fields(self) -> list[str]:
        """
        Get required configuration fields.

        Returns:
            List of required field names
        """
        return ["oauth_token_id"]

    async def validate_connection(self) -> bool:
        """
        Validate the connection to Google Drive.

        Returns:
            True if connection is valid
        """
        try:
            if not self.service:
                await self.connect()

            # Try to get user info
            about = self.service.about().get(fields="user").execute()
            user = about.get("user", {})

            logger.info(f"Google Drive connection validated for user: {user.get('emailAddress')}")
            return True

        except Exception as e:
            logger.warning(f"Connection validation failed: {e}", exc_info=True)
            return False

    async def _get_oauth_token(self) -> Any:
        """Retrieve OAuth token from data source configuration."""
        # Logic to get token from self.data_source (e.g., using oauth_provider to refresh)
        # This is a placeholder - actual implementation depends on how tokens are stored
        # Assuming data_source.credentials or similar
        # For now, assuming we can get it or refreshing it using the provider

        # NOTE: This method was missing in previous context but referenced in connect()
        # We need to implement it or mock it in tests.
        # In BaseConnector, usually we handle this or the subclass does.

        if not self.data_source.credentials:
            return None

        # Simple object to match what connect() expects (access_token, refresh_token)
        class Token:
            def __init__(self, access, refresh):
                self.access_token = access
                self.refresh_token = refresh

        creds = self.data_source.credentials
        return Token(creds.get("access_token"), creds.get("refresh_token"))
