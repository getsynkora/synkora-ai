"""
MCP Server Model

Database model for storing Model Context Protocol (MCP) server configurations.
MCP servers extend agent capabilities by providing additional tools and resources.
"""

import json as _json

from sqlalchemy import JSON, Column, String, Text
from sqlalchemy.orm import relationship

from src.models.base import BaseModel, StatusMixin, TenantMixin


class MCPServer(BaseModel, StatusMixin, TenantMixin):
    """
    MCP Server model for storing server configurations.

    Sensitive fields (auth_config, env_vars, headers) are encrypted at rest using
    Fernet symmetric encryption via encrypt_value/decrypt_value. The backing columns
    store "enc:<fernet_token>" strings; property getters/setters handle transparent
    encryption and decryption. Unencrypted legacy rows (plain JSON text) are read
    correctly for backwards compatibility and re-encrypted on next write.

    Attributes:
        name: Human-readable name for the MCP server
        url: Server URL/endpoint
        description: Detailed description of server capabilities
        server_type: Type of MCP server (http, websocket, etc.)
        auth_type: Authentication method (none, api_key, oauth, etc.)
        auth_config: Authentication configuration (Fernet-encrypted at rest)
        env_vars: stdio environment variables (Fernet-encrypted at rest)
        headers: Custom HTTP headers (Fernet-encrypted at rest)
        capabilities: JSON object describing server capabilities
        metadata: Additional metadata about the server
        status: Server status (active, inactive, error)
        tenant_id: Tenant identifier for multi-tenancy
    """

    __tablename__ = "mcp_servers"

    name = Column(String(255), nullable=False, index=True, comment="MCP server name")

    url = Column(String(500), nullable=True, comment="MCP server URL/endpoint (required for http transport)")

    description = Column(Text, nullable=True, comment="Server description and capabilities")

    transport_type = Column(String(20), nullable=False, default="http", comment="Transport type: http, stdio")

    command = Column(String(500), nullable=True, comment="Command to run for stdio transport (e.g., 'npx', 'python')")

    args = Column(
        JSON, nullable=True, comment="Command arguments as array (e.g., ['-y', '@modelcontextprotocol/server-github'])"
    )

    # Backing column: stores Fernet-encrypted JSON string ("enc:<token>") or NULL.
    # Access only via the .env_vars property — never read _env_vars_enc directly.
    _env_vars_enc = Column("env_vars", Text, nullable=True, comment="Environment variables for stdio process (Fernet-encrypted)")

    server_type = Column(String(50), nullable=False, default="http", comment="Server type (http, websocket, grpc)")

    auth_type = Column(
        String(50), nullable=False, default="none", comment="Authentication type (none, api_key, oauth, bearer)"
    )

    # Backing column: stores Fernet-encrypted JSON string ("enc:<token>") or NULL.
    # Access only via the .auth_config property — never read _auth_config_enc directly.
    _auth_config_enc = Column("auth_config", Text, nullable=True, comment="Authentication configuration (Fernet-encrypted)")

    # Backing column: stores Fernet-encrypted JSON string ("enc:<token>") or NULL.
    # Access only via the .headers property — never read _headers_enc directly.
    _headers_enc = Column("headers", Text, nullable=True, comment="Custom HTTP headers (Fernet-encrypted)")

    capabilities = Column(JSON, nullable=True, comment="Server capabilities and available tools")

    server_metadata = Column(JSON, nullable=True, comment="Additional server metadata")

    # Relationships
    agents = relationship("AgentMCPServer", back_populates="mcp_server", cascade="all, delete-orphan", lazy="selectin")

    # ------------------------------------------------------------------
    # Encrypted field properties
    # ------------------------------------------------------------------

    @property
    def auth_config(self) -> dict | None:
        """Return decrypted auth config. Backwards-compatible with unencrypted rows."""
        raw = self._auth_config_enc
        if not raw:
            return None
        if raw.startswith("enc:"):
            from src.services.agents.security import decrypt_value  # noqa: PLC0415
            return _json.loads(decrypt_value(raw[4:]))
        return _json.loads(raw)

    @auth_config.setter
    def auth_config(self, value: dict | None) -> None:
        if value is None:
            self._auth_config_enc = None
            return
        from src.services.agents.security import encrypt_value  # noqa: PLC0415
        self._auth_config_enc = f"enc:{encrypt_value(_json.dumps(value))}"

    @property
    def env_vars(self) -> dict | None:
        """Return decrypted env vars. Backwards-compatible with unencrypted rows."""
        raw = self._env_vars_enc
        if not raw:
            return None
        if raw.startswith("enc:"):
            from src.services.agents.security import decrypt_value  # noqa: PLC0415
            return _json.loads(decrypt_value(raw[4:]))
        return _json.loads(raw)

    @env_vars.setter
    def env_vars(self, value: dict | None) -> None:
        if value is None:
            self._env_vars_enc = None
            return
        from src.services.agents.security import encrypt_value  # noqa: PLC0415
        self._env_vars_enc = f"enc:{encrypt_value(_json.dumps(value))}"

    @property
    def headers(self) -> dict | None:
        """Return decrypted headers. Backwards-compatible with unencrypted rows."""
        raw = self._headers_enc
        if not raw:
            return None
        if raw.startswith("enc:"):
            from src.services.agents.security import decrypt_value  # noqa: PLC0415
            return _json.loads(decrypt_value(raw[4:]))
        return _json.loads(raw)

    @headers.setter
    def headers(self, value: dict | None) -> None:
        if value is None:
            self._headers_enc = None
            return
        from src.services.agents.security import encrypt_value  # noqa: PLC0415
        self._headers_enc = f"enc:{encrypt_value(_json.dumps(value))}"

    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        """String representation of MCP server."""
        return f"<MCPServer(id={self.id}, name='{self.name}', url='{self.url}')>"

    def to_dict(self, exclude: set[str] | None = None) -> dict:
        """
        Convert to dictionary, excluding sensitive auth data by default.

        Args:
            exclude: Additional fields to exclude

        Returns:
            Dictionary representation of the server
        """
        exclude = exclude or set()
        # Always exclude sensitive encrypted fields unless explicitly requested
        for field in ("auth_config", "env_vars", "headers"):
            if field not in exclude:
                exclude.add(field)

        return super().to_dict(exclude=exclude)

    def to_dict_with_auth(self) -> dict:
        """
        Convert to dictionary including decrypted authentication config.
        Use with caution — only for authorized internal operations.

        Returns:
            Full dictionary including decrypted auth_config, env_vars, and headers
        """
        data = super().to_dict(exclude=set())
        # super().to_dict() reads column names from __table__.columns and calls
        # getattr(self, column.name). For our three encrypted fields the column
        # names ("auth_config", "env_vars", "headers") resolve to the @property
        # getters, so the values returned here are already decrypted dicts.
        return data
