"""
BaseConnector — interface every Company Brain source connector must implement.

Adding a new source type (e.g. Salesforce, MT5, EHR) requires only:
  1. Create a class that extends BaseConnector
  2. Set source_type = "salesforce"
  3. Register it: CONNECTOR_REGISTRY["salesforce"] = SalesforceConnector

No changes to the router, retriever, assembler, or any other pipeline code.

Document shape (returned by fetch_documents):
  {
    "id":           str,     # stable external ID (message TS, issue key, etc.)
    "content":      str,     # plain text for embedding
    "title":        str | None,
    "url":          str | None,
    "metadata":     dict,    # source-specific (channel, author, labels, etc.)
    "occurred_at":  str | None,  # ISO-8601 timestamp from the source system
  }
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator


@dataclass
class ConnectorDocument:
    """Normalised document returned by every connector."""

    id: str
    content: str
    title: str | None = None
    url: str | None = None
    metadata: dict = field(default_factory=dict)
    occurred_at: str | None = None  # ISO-8601


@dataclass
class ConnectorHealth:
    status: str  # "ok" | "degraded" | "down"
    message: str = ""
    details: dict = field(default_factory=dict)


class BaseConnector(ABC):
    """
    Abstract source connector for Company Brain ingestion.

    Each connector is instantiated once per DataSource record and receives
    the decrypted config dict from DataSource.config + credentials.
    """

    #: Must match a DataSourceType value (e.g. "SLACK", "SALESFORCE", "CUSTOM")
    source_type: str = ""

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Args:
            config: Merged dict of DataSource.config + decrypted credentials.
                    Connector reads whatever keys it needs from here.
        """
        self.config = config

    @abstractmethod
    async def fetch_documents(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> AsyncIterator[list[ConnectorDocument]]:
        """
        Yield batches of documents from the source.

        Args:
            since:  Fetch documents newer than this (None = full sync).
            until:  Fetch documents older than this (None = now).

        Yields:
            Batches of ConnectorDocument (list). Batch size is connector-defined.
        """
        # Make the method a proper async generator
        return
        yield  # noqa: unreachable

    @abstractmethod
    async def health_check(self) -> ConnectorHealth:
        """Verify the connector can reach its source system."""

    async def get_schema(self) -> dict[str, Any]:
        """
        Return a JSON-serialisable schema describing the connector's config fields.
        Used by the UI to render a dynamic config form.
        Default: empty schema (connector has no required config).
        """
        return {}
