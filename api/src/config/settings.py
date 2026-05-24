"""
Application configuration settings.

This module provides a centralized configuration management system using Pydantic Settings.
All configuration values are loaded from environment variables with validation and defaults.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .celery import CeleryConfig
from .database import DatabaseConfig
from .feature import (
    AWSConfig,
    BotWorkerConfig,
    CompanyBrainConfig,
    ComputeConfig,
    DOConfig,
    DomainConfig,
    FileUploadConfig,
    GCPConfig,
    HttpConfig,
    LangfuseConfig,
    LLMConfig,
    MonitoringConfig,
    StripeConfig,
    TracingConfig,
    VectorDBConfig,
    WorkspaceConfig,
)
from .redis import RedisConfig
from .security import LoggingConfig, RateLimitConfig, SecurityConfig


class AppConfig(BaseSettings):
    """Application configuration."""

    app_env: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        description="Application environment",
    )

    app_version: str = Field(
        default="0.1.0",
        description="Application version",
    )

    app_debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )

    api_host: str = Field(
        default="0.0.0.0",
        description="API host",
    )

    api_port: int = Field(
        default=5001,
        description="API port",
    )

    api_base_url: str = Field(
        default="http://localhost:5001",
        validation_alias="WEBHOOK_BASE_URL",
        description="Public-facing base URL of the API server (used to construct webhook URLs).",
    )

    app_base_url: str | None = Field(
        default=None,
        validation_alias="APP_BASE_URL",
        description="Public-facing base URL for A2A same-instance routing and SSRF bypass.",
    )

    agent_lens_enabled: bool = Field(
        default=True,
        validation_alias="AGENT_LENS_ENABLED",
        description="Enable Agent Lens observability (tool call logging). Set to false to disable without code changes.",
    )

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "production"


class Settings(
    # Application configs
    AppConfig,
    # Infrastructure configs
    DatabaseConfig,
    RedisConfig,
    CeleryConfig,
    # Security configs
    SecurityConfig,
    RateLimitConfig,
    LoggingConfig,
    # Feature configs
    HttpConfig,
    FileUploadConfig,
    LLMConfig,
    VectorDBConfig,
    MonitoringConfig,
    LangfuseConfig,
    StripeConfig,
    DomainConfig,
    BotWorkerConfig,
    WorkspaceConfig,
    ComputeConfig,
    CompanyBrainConfig,
    TracingConfig,
    # Cloud/serverless execution backends
    AWSConfig,
    GCPConfig,
    DOConfig,
):
    """Main application settings combining all config modules."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Settings: Application settings instance

    Note:
        This function is cached to avoid re-reading environment variables
        on every call. The cache is cleared when the process restarts.
    """
    return Settings()


# Export settings instance
settings = get_settings()
