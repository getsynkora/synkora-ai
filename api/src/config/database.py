"""Database configuration."""

from typing import Any
from urllib.parse import parse_qsl, quote_plus, urlencode

from pydantic import Field, NonNegativeInt, computed_field
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    """Database configuration settings."""

    db_host: str = Field(
        default="localhost",
        description="Hostname or IP address of the database server",
    )

    db_port: int = Field(
        default=5432,
        description="Port number for database connection",
    )

    db_username: str = Field(
        default="postgres",
        description="Username for database authentication",
    )

    db_password: str = Field(
        default="",
        description="Password for database authentication",
    )

    db_database: str = Field(
        default="synkora",
        description="Name of the database to connect to",
    )

    db_charset: str = Field(
        default="",
        description="Character set for database connection",
    )

    db_extras: str = Field(
        default="",
        description="Additional database connection parameters",
    )

    sqlalchemy_database_uri_scheme: str = Field(
        default="postgresql",
        description="Database URI scheme for SQLAlchemy sync connection",
    )

    sqlalchemy_async_database_uri_scheme: str = Field(
        default="postgresql+asyncpg",
        description="Database URI scheme for SQLAlchemy async connection (requires asyncpg driver)",
    )

    sqlalchemy_pool_size: NonNegativeInt = Field(
        default=5,
        description=(
            "Connections held open per process. "
            "With PgBouncer (PGBOUNCER_ENABLED=true) in front of PostgreSQL, "
            "keep this small — PgBouncer multiplexes app connections to a fixed "
            "pool of real PostgreSQL connections, so a large per-process pool "
            "wastes memory without adding PostgreSQL capacity."
        ),
    )

    sqlalchemy_max_overflow: NonNegativeInt = Field(
        default=5,
        description=(
            "Burst connections beyond pool_size. "
            "PgBouncer handles multiplexing; keep overflow small (5) to avoid "
            "a thundering-herd of client connections to PgBouncer under load."
        ),
    )

    sqlalchemy_pool_recycle: NonNegativeInt = Field(
        default=3600,
        description="Number of seconds after which a connection is automatically recycled",
    )

    sqlalchemy_pool_use_lifo: bool = Field(
        default=True,
        description="Use LIFO for connection pool - reuses recently-returned (warm) connections first, keeping fewer connections open",
    )

    sqlalchemy_pool_pre_ping: bool = Field(
        default=True,
        description="Pre-ping connections before reuse. Catches stale connections (e.g. after DB restart or load-balancer timeout) before they cause a 500 error",
    )

    sqlalchemy_echo: bool = Field(
        default=False,
        description="If True, SQLAlchemy will log all SQL statements",
    )

    sqlalchemy_pool_timeout: NonNegativeInt = Field(
        default=30,
        description="Number of seconds to wait for a connection from the pool before raising a timeout error",
    )

    def _apply_ssl(self, db_extras: str) -> str:
        """Append sslmode=verify-full for non-development/test environments unless already set."""
        import os

        app_env = os.getenv("APP_ENV", "development")
        if app_env not in ("development", "test", "testing") and "sslmode=" not in db_extras:
            db_extras = (db_extras + "&sslmode=verify-full").lstrip("&") if db_extras else "sslmode=verify-full"
        return db_extras

    @computed_field  # type: ignore[misc]
    @property
    def sqlalchemy_database_uri(self) -> str:
        """Construct SQLAlchemy sync database URI."""
        db_extras = (
            f"{self.db_extras}&client_encoding={self.db_charset}" if self.db_charset else self.db_extras
        ).strip("&")
        db_extras = self._apply_ssl(db_extras)
        db_extras = f"?{db_extras}" if db_extras else ""
        return (
            f"{self.sqlalchemy_database_uri_scheme}://"
            f"{quote_plus(self.db_username)}:{quote_plus(self.db_password)}@"
            f"{self.db_host}:{self.db_port}/{self.db_database}"
            f"{db_extras}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def sqlalchemy_async_database_uri(self) -> str:
        """Construct SQLAlchemy async database URI.

        asyncpg does not accept 'sslmode' as a URL parameter (that is a libpq/psycopg2
        concept). SSL for asyncpg is passed via connect_args['ssl'] instead, so we
        strip any 'sslmode=*' segment from db_extras here.
        """
        db_extras = (
            f"{self.db_extras}&client_encoding={self.db_charset}" if self.db_charset else self.db_extras
        ).strip("&")
        # Remove sslmode=* — asyncpg doesn't recognise it; ssl is set via connect_args.
        db_extras = urlencode(
            [
                (key, value)
                for key, value in parse_qsl(db_extras)
                if key not in {"sslmode", "sslrootcert", "sslcert", "sslkey"}
            ]
        )
        db_extras = f"?{db_extras}" if db_extras else ""
        return (
            f"{self.sqlalchemy_async_database_uri_scheme}://"
            f"{quote_plus(self.db_username)}:{quote_plus(self.db_password)}@"
            f"{self.db_host}:{self.db_port}/{self.db_database}"
            f"{db_extras}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def sqlalchemy_engine_options(self) -> dict[str, Any]:
        """Get SQLAlchemy sync engine options (for psycopg2)."""
        connect_args = {"options": "-c timezone=UTC"}

        return {
            "pool_size": self.sqlalchemy_pool_size,
            "max_overflow": self.sqlalchemy_max_overflow,
            "pool_recycle": self.sqlalchemy_pool_recycle,
            "pool_pre_ping": self.sqlalchemy_pool_pre_ping,
            "connect_args": connect_args,
            "pool_use_lifo": self.sqlalchemy_pool_use_lifo,
            "pool_reset_on_return": "rollback",
            "pool_timeout": self.sqlalchemy_pool_timeout,
        }

    pgbouncer_enabled: bool = Field(
        default=False,
        description=(
            "Set to True when PgBouncer sits between the app and PostgreSQL. "
            "Disables asyncpg prepared-statement caching (statement_cache_size=0), "
            "which is incompatible with PgBouncer transaction-mode pooling."
        ),
    )

    @computed_field  # type: ignore[misc]
    @property
    def sqlalchemy_async_engine_options(self) -> dict[str, Any]:
        """Get SQLAlchemy async engine options (for asyncpg)."""
        # asyncpg uses different connection args format than psycopg2.
        # server_settings is the asyncpg equivalent of psycopg2's options.
        connect_args: dict[str, Any] = {
            "server_settings": {"timezone": "UTC"},
            "command_timeout": 30,  # Statement timeout in seconds
        }

        extras = dict(parse_qsl(self._apply_ssl(self.db_extras or "")))
        mode = extras.get("sslmode")
        if mode == "disable":
            connect_args["ssl"] = False
        elif mode:
            import ssl

            if mode not in {"require", "verify-ca", "verify-full"}:
                raise ValueError("Use sslmode=verify-full, verify-ca, require, or disable")
            # Never silently downgrade a requested verified connection. 'require'
            # also verifies the server; production defaults to verify-full.
            ca = extras.get("sslrootcert")
            context = ssl.create_default_context(cafile=None if ca in {None, "system"} else ca)
            context.check_hostname = mode != "verify-ca"
            context.verify_mode = ssl.CERT_REQUIRED
            if extras.get("sslcert"):
                context.load_cert_chain(extras["sslcert"], extras.get("sslkey"))
            connect_args["ssl"] = context

        if self.pgbouncer_enabled:
            # PgBouncer transaction mode does not support named prepared statements.
            # asyncpg caches prepared statements by default — disable to prevent
            # "prepared statement ... already exists" errors under transaction pooling.
            connect_args["statement_cache_size"] = 0

        # pool_use_lifo is omitted: AsyncAdaptedQueuePool (used by async engines)
        # does not support the use_lifo parameter — only the sync QueuePool does.
        #
        # pool_pre_ping: disabled when PgBouncer is in front. PgBouncer keeps persistent
        # connections to PostgreSQL and handles dead connection detection itself.
        # pre_ping sends SELECT 1 on every checkout — with cross-cloud latency (DO→AWS)
        # this adds ~15ms per session per request for zero benefit.
        pre_ping = False if self.pgbouncer_enabled else self.sqlalchemy_pool_pre_ping

        return {
            "pool_size": self.sqlalchemy_pool_size,
            "max_overflow": self.sqlalchemy_max_overflow,
            "pool_recycle": self.sqlalchemy_pool_recycle,
            "pool_pre_ping": pre_ping,
            "connect_args": connect_args,
            "pool_reset_on_return": "rollback",
            "pool_timeout": self.sqlalchemy_pool_timeout,
        }
