"""Knowledge base models for configurable vector storage."""

import enum
import logging

from sqlalchemy import JSON, Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel, TimestampMixin

logger = logging.getLogger(__name__)


class VectorDBProvider(enum.StrEnum):
    """Supported vector database providers."""

    QDRANT = "QDRANT"
    PINECONE = "PINECONE"
    WEAVIATE = "WEAVIATE"
    CHROMA = "CHROMA"
    MILVUS = "MILVUS"


class EmbeddingProvider(enum.StrEnum):
    """Supported embedding providers."""

    SENTENCE_TRANSFORMERS = "SENTENCE_TRANSFORMERS"
    OPENAI = "OPENAI"
    COHERE = "COHERE"
    HUGGINGFACE = "HUGGINGFACE"
    LITELLM = "LITELLM"


class KnowledgeBaseStatus(enum.StrEnum):
    """Knowledge base status."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"
    INITIALIZING = "INITIALIZING"


class ChunkingStrategy(enum.StrEnum):
    """Chunking strategies for different content types."""

    FIXED = "FIXED"  # Fixed size chunking (default)
    SEMANTIC = "SEMANTIC"  # Semantic-aware chunking
    EMAIL = "EMAIL"  # Email-specific chunking
    SLACK = "SLACK"  # Slack thread-aware chunking
    DOCUMENT = "DOCUMENT"  # Document structure-aware chunking
    CODE = "CODE"  # Code structure-aware chunking


class IngestionMode(enum.StrEnum):
    """Knowledge base ingestion mode."""

    STANDARD = "standard"  # Synchronous DocumentProcessor path (legacy/default)
    ADVANCED = "advanced"  # Company Brain streaming ingestion pipeline


class KnowledgeBase(BaseModel, TimestampMixin):
    """
    Knowledge base configuration.

    A knowledge base is a configurable vector storage that can be shared
    across multiple agents and data sources.
    """

    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[KnowledgeBaseStatus] = mapped_column(
        Enum(KnowledgeBaseStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=KnowledgeBaseStatus.INACTIVE,
    )
    ingestion_mode: Mapped[IngestionMode] = mapped_column(
        Enum(IngestionMode, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=IngestionMode.STANDARD,
    )

    # Vector DB configuration
    vector_db_provider: Mapped[VectorDBProvider] = mapped_column(
        Enum(VectorDBProvider, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    vector_db_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Example for Qdrant: {"host": "localhost", "port": 6333, "collection_name": "kb_1"}
    # Example for Pinecone: {"api_key": "...", "environment": "us-west1-gcp", "index_name": "kb-1"}

    # Embedding configuration
    embedding_provider: Mapped[EmbeddingProvider] = mapped_column(
        Enum(EmbeddingProvider, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    # Example: "all-MiniLM-L6-v2" for sentence-transformers, "text-embedding-ada-002" for OpenAI

    embedding_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Example: {"dimension": 384, "batch_size": 32, "api_key": "encrypted_key"}

    def get_embedding_config_decrypted(self) -> dict:
        """Get embedding config with decrypted API key."""
        if not self.embedding_config:
            return {}
        config = self.embedding_config.copy()
        if "api_key" in config and config["api_key"]:
            # Import here to avoid circular dependency
            from src.services.agents.security import decrypt_value

            try:
                config["api_key"] = decrypt_value(config["api_key"])
                logger.debug(f"Decrypted API key for knowledge base: {self.name}")
            except Exception as e:
                logger.error(f"Failed to decrypt API key for knowledge base {self.name}: {e}")
        return config

    def set_embedding_config_encrypted(self, config: dict) -> None:
        """Set embedding config with encrypted API key."""
        if not config:
            self.embedding_config = {}
            return
        config_copy = config.copy()
        if "api_key" in config_copy and config_copy["api_key"]:
            # Only encrypt if it's not already encrypted
            # (encrypted values start with 'gAAAAA')
            if not config_copy["api_key"].startswith("gAAAAA"):
                # Import here to avoid circular dependency
                from src.services.agents.security import encrypt_value

                try:
                    config_copy["api_key"] = encrypt_value(config_copy["api_key"])
                    logger.info(
                        f"Encrypted API key for knowledge base: {self.name if hasattr(self, 'name') else 'new'}"
                    )
                except Exception as e:
                    logger.error(f"Failed to encrypt API key: {e}")
                    raise
        self.embedding_config = config_copy

    def get_vector_db_config_decrypted(self) -> dict:
        """Get vector DB config with decrypted API key."""
        if not self.vector_db_config:
            return {}
        config = self.vector_db_config.copy()
        if "api_key" in config and config["api_key"]:
            # Import here to avoid circular dependency
            from src.services.agents.security import decrypt_value

            try:
                config["api_key"] = decrypt_value(config["api_key"])
                logger.debug(f"Decrypted vector DB API key for knowledge base: {self.name}")
            except Exception as e:
                logger.error(f"Failed to decrypt vector DB API key for knowledge base {self.name}: {e}")
        return config

    def set_vector_db_config_encrypted(self, config: dict) -> None:
        """Set vector DB config with encrypted API key."""
        if not config:
            self.vector_db_config = {}
            return
        config_copy = config.copy()
        if "api_key" in config_copy and config_copy["api_key"]:
            # Only encrypt if it's not already encrypted
            # (encrypted values start with 'gAAAAA')
            if not config_copy["api_key"].startswith("gAAAAA"):
                # Import here to avoid circular dependency
                from src.services.agents.security import encrypt_value

                try:
                    config_copy["api_key"] = encrypt_value(config_copy["api_key"])
                    logger.info(
                        f"Encrypted vector DB API key for knowledge base: {self.name if hasattr(self, 'name') else 'new'}"
                    )
                except Exception as e:
                    logger.error(f"Failed to encrypt vector DB API key: {e}")
                    raise
        self.vector_db_config = config_copy

    # Settings
    is_global: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # If true, available to all agents in tenant

    # Chunking configuration
    chunking_strategy: Mapped[ChunkingStrategy] = mapped_column(
        Enum(ChunkingStrategy, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ChunkingStrategy.FIXED,
    )
    chunk_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1500
    )  # Text chunk size for splitting (increased from 1000)
    chunk_overlap: Mapped[int] = mapped_column(
        Integer, nullable=False, default=150
    )  # Overlap between chunks (decreased from 200)
    min_chunk_size: Mapped[int] = mapped_column(
        Integer, nullable=False, default=500
    )  # Minimum chunk size to avoid tiny chunks
    max_chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=3000)  # Maximum chunk size cap
    chunking_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Example: {"preserve_structure": true, "email_threshold": 2000, "slack_thread_size": 1500}

    # Statistics
    total_documents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("ingestion_mode", IngestionMode.STANDARD)
        super().__init__(**kwargs)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="knowledge_bases")
    data_sources: Mapped[list["DataSource"]] = relationship("DataSource", back_populates="knowledge_base")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="knowledge_base")
    agents: Mapped[list["AgentKnowledgeBase"]] = relationship(
        "AgentKnowledgeBase", back_populates="knowledge_base", cascade="all, delete-orphan"
    )
    app_store_sources: Mapped[list["AppStoreSource"]] = relationship("AppStoreSource", back_populates="knowledge_base")

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id}, name={self.name}, provider={self.vector_db_provider})>"
