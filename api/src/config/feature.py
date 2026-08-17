"""Feature configuration."""

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings


class HttpConfig(BaseSettings):
    """HTTP configuration settings."""

    inner_cors_origins: str = Field(
        default="",
        description=(
            "Comma-separated list of allowed CORS origins. "
            "Example: 'https://app.example.com,https://admin.example.com'. "
            "Leave empty to deny all cross-origin requests (recommended for production). "
            "Set to 'http://localhost:3005' for local development."
        ),
    )

    @computed_field  # type: ignore[misc]
    @property
    def cors_origins(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.inner_cors_origins.split(",") if origin.strip()]


class FileUploadConfig(BaseSettings):
    """File upload configuration."""

    max_upload_size: int = Field(
        default=15728640,
        description="Max upload size in bytes (15MB)",
    )

    inner_allowed_extensions: str = Field(
        default="txt,pdf,docx,md,html",
        description="Comma-separated list of allowed file extensions",
    )

    @computed_field  # type: ignore[misc]
    @property
    def allowed_extensions(self) -> list[str]:
        """Get allowed extensions as a list."""
        return [ext.strip() for ext in self.inner_allowed_extensions.split(",") if ext.strip()]


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key",
    )

    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key",
    )


class VectorDBConfig(BaseSettings):
    """
    Vector database configuration.

    Following Synkora's architecture, supports multiple vector database providers.
    ChromaDB is the default and recommended option for simplicity.
    """

    # Vector store type selection
    vector_store: str = Field(
        default="CHROMA",
        description="Vector store type (CHROMA, QDRANT, WEAVIATE, MILVUS, etc.)",
    )

    # ChromaDB configuration (default)
    chroma_host: str = Field(
        default="localhost",
        description="ChromaDB host",
    )

    chroma_port: int = Field(
        default=8000,
        description="ChromaDB port",
    )

    chroma_tenant: str = Field(
        default="default_tenant",
        description="ChromaDB tenant",
    )

    chroma_database: str = Field(
        default="default_database",
        description="ChromaDB database",
    )

    chroma_auth_provider: str | None = Field(
        default=None,
        description="ChromaDB auth provider",
    )

    chroma_auth_credentials: str | None = Field(
        default=None,
        description="ChromaDB auth credentials",
    )

    # Qdrant configuration
    qdrant_url: str | None = Field(
        default=None,
        description="Qdrant URL",
    )

    qdrant_api_key: str | None = Field(
        default=None,
        description="Qdrant API key",
    )

    # Weaviate configuration
    weaviate_url: str | None = Field(
        default=None,
        description="Weaviate URL",
    )

    weaviate_api_key: str | None = Field(
        default=None,
        description="Weaviate API key",
    )

    # Milvus configuration
    milvus_host: str | None = Field(
        default=None,
        description="Milvus host",
    )

    milvus_port: int | None = Field(
        default=None,
        description="Milvus port",
    )

    milvus_user: str | None = Field(
        default=None,
        description="Milvus user",
    )

    milvus_password: str | None = Field(
        default=None,
        description="Milvus password",
    )


class MonitoringConfig(BaseSettings):
    """Monitoring configuration."""

    sentry_dsn: str | None = Field(
        default=None,
        description="Sentry DSN",
    )

    sentry_environment: str | None = Field(
        default=None,
        description="Sentry environment",
    )

    metrics_auth_token: str | None = Field(
        default=None,
        description=(
            "Bearer token required to access /metrics and /api/v1/stats/performance. "
            "If unset the endpoints are open (acceptable inside a private network). "
            "Set this in production to prevent topology leakage."
        ),
    )


class LangfuseConfig(BaseSettings):
    """Langfuse observability configuration."""

    langfuse_enabled: bool = Field(
        default=False,
        description="Enable Langfuse tracing",
    )

    langfuse_public_key: str | None = Field(
        default=None,
        description="Langfuse public key",
    )

    langfuse_secret_key: str | None = Field(
        default=None,
        description="Langfuse secret key",
    )

    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse host URL",
    )

    langfuse_sample_rate: float = Field(
        default=1.0,
        description="Sampling rate for traces (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )

    @property
    def is_configured(self) -> bool:
        """Check if Langfuse is properly configured."""
        return bool(self.langfuse_enabled and self.langfuse_public_key and self.langfuse_secret_key)


class StripeConfig(BaseSettings):
    """Stripe payment configuration."""

    stripe_secret_key: str | None = Field(
        default=None,
        description="Stripe secret API key",
    )

    stripe_publishable_key: str | None = Field(
        default=None,
        description="Stripe publishable API key",
    )

    stripe_webhook_secret: str | None = Field(
        default=None,
        description="Stripe webhook signing secret",
    )

    stripe_enabled: bool = Field(
        default=False,
        description="Enable Stripe payment processing",
    )

    @property
    def is_configured(self) -> bool:
        """Check if Stripe is properly configured."""
        return bool(self.stripe_enabled and self.stripe_secret_key and self.stripe_publishable_key)


class DomainConfig(BaseSettings):
    """Domain configuration."""

    platform_domain: str = Field(
        default="localhost",
        description=(
            "Platform domain used for subdomain routing. "
            "Set to your public domain in production, e.g. 'app.example.com'."
        ),
    )

    webhook_base_url: str | None = Field(
        default=None,
        description=(
            "Publicly reachable base URL for webhook endpoints. "
            "Required for Telegram webhook mode, e.g. 'https://api.example.com'."
        ),
    )

    widget_js_url: str = Field(
        default="http://localhost:3005/widget.js",
        description=(
            "Public URL where widget.js is served. "
            "Set to your frontend URL in production, e.g. 'https://app.example.com/widget.js'."
        ),
    )

    public_api_url: str = Field(
        default="http://localhost:5001/api/v1",
        description=(
            "Public base URL for the API, used in widget embed code. "
            "Set to your API URL in production, e.g. 'https://api.example.com/api/v1'."
        ),
    )


class BotWorkerConfig(BaseSettings):
    """Bot Worker configuration for scalable bot management."""

    # Worker capacity
    bot_worker_capacity: int = Field(
        default=1000,
        description="Maximum number of bots per worker",
    )

    # Heartbeat settings
    bot_worker_heartbeat_interval: int = Field(
        default=10,
        description="Heartbeat interval in seconds",
    )

    bot_worker_heartbeat_timeout: int = Field(
        default=30,
        description="Consider worker dead after this many seconds without heartbeat",
    )

    # Health server
    bot_worker_health_port: int = Field(
        default=8080,
        description="Port for worker health check server",
    )

    # Scaling
    bot_worker_bots_per_worker_target: int = Field(
        default=800,
        description="Target bots per worker for auto-scaling decisions",
    )


class WorkspaceConfig(BaseSettings):
    """
    Workspace configuration for agent sandbox environments.

    Provides isolated workspace directories per agent session for
    git clones, file operations, and command execution.
    """

    workspace_base_path: str = Field(
        default="/tmp/synkora/workspaces",
        description="Base directory for agent workspaces",
    )

    workspace_ttl_hours: int = Field(
        default=24,
        description="Time-to-live for workspaces in hours",
    )

    workspace_max_size_mb: int = Field(
        default=2000,
        description="Maximum size per workspace in MB (2GB default)",
    )

    workspace_max_per_tenant: int = Field(
        default=100,
        description="Maximum concurrent workspaces per tenant",
    )


class ComputeConfig(BaseSettings):
    """synkora-sandbox service configuration."""

    sandbox_service_url: str | None = Field(
        default=None,
        description="URL of the synkora-sandbox service (e.g. http://synkora-sandbox:5004)",
    )

    sandbox_api_key: str | None = Field(
        default=None,
        description="Shared secret for sandbox service authentication",
    )

    scraper_api_key: str | None = Field(
        default=None,
        description="Shared secret for scraper service authentication",
    )


class CompanyBrainConfig(BaseSettings):
    """
    Company Brain (data hub) configuration.

    All settings are read from environment variables — nothing is hardcoded.
    Swap any component (search backend, queue, dedup) without changing code.
    """

    # Search backend
    company_brain_search_backend: str = Field(
        default="qdrant_hybrid",
        description="Search backend: qdrant_hybrid | postgres_fts | elasticsearch | typesense",
    )

    # Ingestion queue
    company_brain_queue_backend: str = Field(
        default="redis_streams",
        description="Ingestion queue backend: redis_streams | celery_only",
    )
    company_brain_stream_maxlen: int = Field(
        default=500_000,
        description="Max entries per Redis Stream per tenant per source (MAXLEN ~)",
    )
    company_brain_batch_size: int = Field(
        default=100,
        description="Number of document chunks per embedding API call",
    )
    company_brain_min_content_tokens: int = Field(
        default=10,
        description="Skip indexing documents shorter than this many tokens",
    )

    # Embedding model per source type — serialised JSON map
    # e.g. '{"default":"text-embedding-3-small","confluence":"text-embedding-3-large"}'
    company_brain_embedding_models: str = Field(
        default='{"default":"text-embedding-3-small","confluence":"text-embedding-3-large","notion":"text-embedding-3-large"}',
        description="JSON map: source_type -> embedding model name",
    )

    # Chunking strategy per source type — serialised JSON map
    # e.g. '{"slack":"thread","github_pr":"diff","confluence":"document","default":"fixed"}'
    company_brain_chunking_strategies: str = Field(
        default='{"slack":"thread","github_pr":"diff","confluence":"document","notion":"document","default":"fixed"}',
        description="JSON map: source_type -> chunking strategy (thread|diff|document|fixed)",
    )

    # Tiered storage (days)
    company_brain_hot_days: int = Field(
        default=90,
        description="Documents indexed within this many days go to the hot tier (always searched)",
    )
    company_brain_warm_days: int = Field(
        default=730,
        description="Documents older than hot_days but within this threshold go to warm tier",
    )

    # Deduplication
    company_brain_dedup_backend: str = Field(
        default="redis_set",
        description="Dedup backend: redis_set | postgres",
    )
    company_brain_dedup_ttl_days: int = Field(
        default=7,
        description="TTL in days for dedup keys (redis_set backend only)",
    )

    # Query layer
    company_brain_query_router_model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="LLM model ID used for query intent classification (cheap, fast)",
    )
    company_brain_context_tokens: int = Field(
        default=32_000,
        description="Max tokens of retrieved context passed to the answer LLM",
    )
    company_brain_rerank_cache_ttl: int = Field(
        default=60,
        description="TTL in seconds for the rerank result cache (0 = disabled). "
        "At 60s, 100 concurrent agents share one retrieval per unique query.",
    )
    company_brain_enable_pageindex: bool = Field(
        default=False,
        description="Route long-form document queries through PageIndex (higher quality, higher cost)",
    )

    # Sync schedule
    company_brain_full_sync_hours: int = Field(
        default=24,
        description="How often a full re-sync runs (hours)",
    )


class TracingConfig(BaseSettings):
    """Agent session trace configuration (Elasticsearch-backed observability)."""

    elasticsearch_url: str = Field(
        default="http://elasticsearch:9200",
        validation_alias="ELASTICSEARCH_URL",
        description="Elasticsearch URL for agent session tracing",
    )
    elasticsearch_username: str = Field(
        default="elastic",
        validation_alias="ELASTICSEARCH_USERNAME",
        description="Elasticsearch username",
    )
    elasticsearch_password: str = Field(
        default="changeme",
        validation_alias="ELASTICSEARCH_PASSWORD",
        description="Elasticsearch password",
    )
    agent_trace_enabled: bool = Field(
        default=True,
        validation_alias="AGENT_TRACE_ENABLED",
        description="Enable agent session tracing to Elasticsearch",
    )
    agent_trace_index: str = Field(
        default="agent-session-events",
        validation_alias="AGENT_TRACE_INDEX",
        description="Elasticsearch index name for agent session events",
    )
    agent_trace_retention_days: int = Field(
        default=7,
        validation_alias="AGENT_TRACE_RETENTION_DAYS",
        description="Days to retain agent session events in Elasticsearch",
    )
    agent_feedback_index: str = Field(
        default="agent-feedback",
        validation_alias="AGENT_FEEDBACK_INDEX",
        description="Elasticsearch index name for per-message user feedback",
    )
    agent_outcomes_index: str = Field(
        default="agent-outcomes",
        validation_alias="AGENT_OUTCOMES_INDEX",
        description="Elasticsearch index name for session outcome documents",
    )
    agent_eval_datasets_index: str = Field(
        default="agent-eval-datasets",
        validation_alias="AGENT_EVAL_DATASETS_INDEX",
        description="Elasticsearch index name for eval datasets and cases",
    )
    agent_eval_runs_index: str = Field(
        default="agent-eval-runs",
        validation_alias="AGENT_EVAL_RUNS_INDEX",
        description="Elasticsearch index name for eval run results",
    )
    eval_judge_model: str = Field(
        default="gpt-4o-mini",
        validation_alias="EVAL_JUDGE_MODEL",
        description="LLM model used for the on-demand eval judge",
    )
    eval_judge_max_tokens: int = Field(
        default=512,
        validation_alias="EVAL_JUDGE_MAX_TOKENS",
        description="Max tokens for eval judge LLM responses",
    )
    eval_judge_llm_config_id: str | None = Field(
        default=None,
        validation_alias="EVAL_JUDGE_LLM_CONFIG_ID",
        description="UUID of an AgentLLMConfig row to use as the judge's LLM for standalone eval/regression tests",
    )


class AWSConfig(BaseSettings):
    """AWS configuration for Lambda execution backend."""

    aws_access_key_id: str | None = Field(
        default=None,
        description="AWS access key ID",
    )

    aws_secret_access_key: str | None = Field(
        default=None,
        description="AWS secret access key",
    )

    aws_region: str = Field(
        default="us-east-1",
        description="AWS region",
    )

    aws_lambda_function_arn: str | None = Field(
        default=None,
        description="ARN of the Lambda function to invoke for agent tasks",
    )

    aws_lambda_role_arn: str | None = Field(
        default=None,
        description="IAM role ARN for Lambda execution (used when creating the function)",
    )

    lambda_invocation_secret: str | None = Field(
        default=None,
        description="HMAC signing key for Lambda invocation payloads",
    )

    @property
    def is_configured(self) -> bool:
        """Check if AWS is properly configured."""
        return bool(self.aws_access_key_id and self.aws_secret_access_key and self.aws_lambda_function_arn)


class GCPConfig(BaseSettings):
    """GCP configuration for Cloud Run execution backend."""

    gcp_project_id: str | None = Field(
        default=None,
        description="GCP project ID",
    )

    gcp_service_account_json: str | None = Field(
        default=None,
        description="Base64-encoded service account JSON",
    )

    gcp_region: str = Field(
        default="us-central1",
        description="GCP region",
    )

    cloud_run_job_name: str | None = Field(
        default=None,
        description="Cloud Run Job name to execute agent tasks",
    )

    cloud_run_invocation_secret: str | None = Field(
        default=None,
        description="HMAC signing key for Cloud Run invocation payloads",
    )

    @property
    def is_configured(self) -> bool:
        """Check if GCP is properly configured."""
        return bool(self.gcp_project_id and self.gcp_service_account_json and self.cloud_run_job_name)


class DOConfig(BaseSettings):
    """DigitalOcean configuration for Functions execution backend."""

    do_api_token: str | None = Field(
        default=None,
        description="DigitalOcean API token (personal access token with write scope)",
    )

    do_functions_endpoint: str | None = Field(
        default=None,
        description=(
            "Full HTTPS endpoint URL for the deployed DO Function. "
            "Format: https://faas-{region}.doserverless.co/api/v1/web/{namespace_id}/{package}/{function}"
        ),
    )

    do_functions_invocation_secret: str | None = Field(
        default=None,
        description="HMAC signing key for DO Functions invocation payloads",
    )

    @property
    def is_configured(self) -> bool:
        """Check if DO Functions is properly configured."""
        return bool(self.do_api_token and self.do_functions_endpoint)


class FeatureConfig(BaseSettings):
    """Feature configuration combining all feature settings."""

    http: HttpConfig = HttpConfig()
    file_upload: FileUploadConfig = FileUploadConfig()
    llm: LLMConfig = LLMConfig()
    vector_db: VectorDBConfig = VectorDBConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    langfuse: LangfuseConfig = LangfuseConfig()
    stripe: StripeConfig = StripeConfig()
