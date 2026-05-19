"""
Agent Loader Service.

Handles loading agents from cache/database and managing LLM configurations.
"""

import logging
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.services.agents.agent_manager import AgentManager
from src.services.agents.config import AgentConfig, ModelConfig, ToolConfig
from src.services.agents.implementations import ClaudeCodeAgent, CodeAgent, LLMAgent, ResearchAgent
from src.services.agents.llm_provider_presets import get_model_preset
from src.services.agents.routing.intent_classifier import classify_query
from src.services.agents.routing.model_router import RoutingDecision, get_router
from src.services.agents.security import decrypt_value
from src.services.cache import get_agent_cache

logger = logging.getLogger(__name__)


class AgentLoadResult:
    """Result of agent loading operation."""

    def __init__(
        self,
        db_agent: Agent | None = None,
        agent: Any | None = None,
        cache_hit: bool = False,
        loading_time: float = 0.0,
        error: str | None = None,
        is_workflow: bool = False,
        fallback_config_ids: list[str] | None = None,
        routing_decision: Any | None = None,
    ):
        self.db_agent = db_agent
        self.agent = agent
        self.cache_hit = cache_hit
        self.loading_time = loading_time
        self.error = error
        self.is_workflow = is_workflow
        self.fallback_config_ids: list[str] = fallback_config_ids or []
        self.routing_decision = routing_decision


class AgentLoaderService:
    """Service for loading and caching agents."""

    def __init__(self, agent_manager: AgentManager):
        self.agent_manager = agent_manager
        self.cache = get_agent_cache()

    @staticmethod
    def _get_max_tokens_with_preset_default(
        provider: str, model_name: str, configured_max_tokens: int | None
    ) -> int | None:
        """
        Get max_tokens, using preset defaults if not configured.

        This ensures that agents have appropriate max_tokens for tool calls
        that may generate large content (e.g., PDF generation, document creation).

        Args:
            provider: LLM provider (e.g., 'anthropic', 'litellm')
            model_name: Model name (e.g., 'claude-4-5-sonnet')
            configured_max_tokens: Value from agent config (may be None)

        Returns:
            max_tokens value (from config, preset, or default 16384)
        """
        if configured_max_tokens is not None:
            return configured_max_tokens

        # Try to get preset default
        # For litellm provider, try both 'litellm' and original provider presets
        model_preset = get_model_preset(provider, model_name)
        if not model_preset and provider == "litellm":
            # Try common providers for litellm models
            for fallback_provider in ["anthropic", "openai", "gemini"]:
                model_preset = get_model_preset(fallback_provider, model_name)
                if model_preset:
                    break

        if model_preset and model_preset.default_max_tokens:
            logger.info(
                f"Using preset default max_tokens: {model_preset.default_max_tokens} for {provider}/{model_name}"
            )
            return model_preset.default_max_tokens

        default_max_tokens = 16384
        logger.info(f"Using fallback max_tokens: {default_max_tokens} for {provider}/{model_name}")
        return default_max_tokens

    def _reconstruct_agent(self, cached_data: dict[str, Any]) -> Agent:
        """
        Reconstruct an Agent instance from cached data without touching the database.

        Used by the fast path when the agent is already warm in the in-process registry.
        The returned object is detached (not attached to any session), which is fine
        because all attribute access in the hot path uses scalar columns only.
        """
        from datetime import datetime

        agent_data = {k: v for k, v in cached_data.items() if k not in ["default_llm_config"]}

        # Parse datetime strings back to datetime objects
        for dt_field in ["created_at", "updated_at"]:
            if agent_data.get(dt_field) and isinstance(agent_data[dt_field], str):
                agent_data[dt_field] = datetime.fromisoformat(agent_data[dt_field])

        # Convert UUID string fields back to UUID objects
        for uuid_field in ["id", "tenant_id", "email_template_id"]:
            if agent_data.get(uuid_field) and isinstance(agent_data[uuid_field], str):
                try:
                    agent_data[uuid_field] = uuid.UUID(agent_data[uuid_field])
                except ValueError:
                    pass

        return Agent(**agent_data)

    async def load_agent(
        self,
        agent_name: str,
        db: AsyncSession,
        llm_config_id: str | None = None,
        query: str | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        tenant_id: str = "",
    ) -> AgentLoadResult:
        """
        Load agent from cache or database, with optional intelligent model routing.

        When the agent has routing_mode != "fixed" and a query is provided, the
        router classifies the query and selects the most cost-effective LLM config.

        Args:
            agent_name: Slug of the agent (globally unique)
            db: Database session
            llm_config_id: Explicit LLM config ID override (bypasses routing)
            query: User message (used by router for intent/complexity classification)
            conversation_history: Prior turns (used by router for complexity scoring)
            tenant_id: Tenant identifier for tenant-scoped registry lookup

        Returns:
            AgentLoadResult with loaded agent, routing decision, and fallback IDs
        """
        agent_slug = agent_name  # parameter kept as agent_name for call-site compat
        start_time = time.time()

        # Fast path: agent is already warm in the in-process registry AND in Redis.
        # Skip db.merge() entirely — reconstruct db_agent from Redis data as a
        # detached object (all hot-path attribute accesses are scalar columns).
        # Bypass when:
        #   - llm_config_id is set (needs fresh DB config)
        #   - query is set (routing may select a different config)
        if not llm_config_id and not query:
            in_memory_agent = self.agent_manager.registry.get(agent_slug, tenant_id)
            if in_memory_agent and in_memory_agent.llm_client:
                cached_data = await self.cache.get_agent_config(agent_slug, tenant_id=tenant_id)
                if cached_data:
                    db_agent = self._reconstruct_agent(cached_data)
                    is_workflow = bool(db_agent.workflow_type)
                    logger.info(
                        f"⚡ Fast path HIT for agent '{agent_slug}' "
                        f"(registry+redis, no DB) ({time.time() - start_time:.4f}s)"
                    )
                    return AgentLoadResult(
                        db_agent=db_agent,
                        agent=in_memory_agent,
                        cache_hit=True,
                        loading_time=time.time() - start_time,
                        is_workflow=is_workflow,
                    )

        # Slow path: Redis → DB lookup
        cached_data = await self.cache.get_agent_config(agent_slug, tenant_id=tenant_id)

        if cached_data:
            db_agent = await self._load_from_cache(cached_data, db)
            cache_hit = True
            logger.info(f"Cache HIT for agent '{agent_slug}' ({time.time() - start_time:.3f}s)")
        else:
            db_agent = await self._load_from_database(agent_slug, db, tenant_id=tenant_id)
            cache_hit = False

            if db_agent:
                await self._cache_agent(db_agent, db, requesting_tenant_id=tenant_id)
                logger.info(
                    f"Cache MISS for agent '{agent_slug}', cached for next time ({time.time() - start_time:.3f}s)"
                )

        if not db_agent:
            return AgentLoadResult(
                error=f"Agent {agent_slug} not found in database", loading_time=time.time() - start_time
            )

        # Check if workflow agent
        is_workflow = bool(db_agent.workflow_type)

        if is_workflow:
            logger.info(f"Detected workflow agent: {agent_slug}, type: {db_agent.workflow_type}")
            return AgentLoadResult(
                db_agent=db_agent, cache_hit=cache_hit, loading_time=time.time() - start_time, is_workflow=True
            )

        # Run model routing if a query was provided and routing is non-fixed
        routing_decision = None
        effective_config_id = llm_config_id  # explicit override wins
        fallback_config_ids: list[str] = []

        agent_routing_mode = getattr(db_agent, "routing_mode", "fixed") or "fixed"

        if query and not llm_config_id and agent_routing_mode != "fixed":
            routing_decision, effective_config_id, fallback_config_ids = await self._run_routing(
                db_agent=db_agent,
                query=query,
                conversation_history=conversation_history,
                db=db,
            )

        # Load regular agent into memory
        agent = await self._load_agent_to_memory(
            agent_name=agent_slug,
            db_agent=db_agent,
            cached_data=cached_data,
            llm_config_id=effective_config_id,
            db=db,
            requesting_tenant_id=tenant_id,
        )

        return AgentLoadResult(
            db_agent=db_agent,
            agent=agent,
            cache_hit=cache_hit,
            loading_time=time.time() - start_time,
            is_workflow=False,
            error=agent.get("error") if isinstance(agent, dict) else None,
            fallback_config_ids=fallback_config_ids,
            routing_decision=routing_decision,
        )

    async def _load_from_cache(self, cached_data: dict[str, Any], db: AsyncSession) -> Agent:
        """Load agent from cached data.

        Returns a detached (transient) Agent instance — same as the fast-path
        _reconstruct_agent() — so the object is never tracked by the SQLAlchemy
        session.  This avoids autoflush errors when tools or credential resolvers
        run SELECT queries on the same session during streaming.
        """
        return self._reconstruct_agent(cached_data)

    async def _load_from_database(self, agent_slug: str, db: AsyncSession, tenant_id: str = "") -> Agent | None:
        """Load agent from database by slug, scoped to tenant to prevent cross-tenant leakage.

        Platform-shared agents (tenant_id = zero UUID) are accessible to all tenants.
        The platform fallback uses agent_name lookup (platform_engineer_agent is the only
        platform agent and does not use slug-based routing).
        """
        from uuid import UUID

        _PLATFORM_TENANT_ID = UUID("00000000-0000-0000-0000-000000000000")

        filters = [Agent.slug == agent_slug]
        tid = None
        if tenant_id:
            try:
                tid = UUID(tenant_id)
            except ValueError:
                logger.error("Invalid tenant_id format '%s' — refusing cross-tenant load", tenant_id)
                return None
            filters.append(Agent.tenant_id == tid)

        result = await db.execute(select(Agent).filter(*filters))
        agent = result.scalar_one_or_none()

        # Fall back to the platform-shared agent (zero UUID tenant) when not found under current tenant.
        # Platform agents are looked up by agent_name since they are seeded without slugs.
        if agent is None and tenant_id and tid != _PLATFORM_TENANT_ID:
            result = await db.execute(
                select(Agent).filter(Agent.agent_name == agent_slug, Agent.tenant_id == _PLATFORM_TENANT_ID)
            )
            agent = result.scalar_one_or_none()

        return agent

    async def _cache_agent(self, db_agent: Agent, db: AsyncSession, requesting_tenant_id: str = "") -> None:
        """Cache agent configuration."""
        from src.models.agent_llm_config import AgentLLMConfig

        _PLATFORM_TENANT_ID = "00000000-0000-0000-0000-000000000000"
        is_platform_agent = str(db_agent.tenant_id) == _PLATFORM_TENANT_ID

        # For platform-shared agents scope the LLM config lookup to the requesting tenant
        # so the cached entry contains that tenant's API key, not a random tenant's.
        llm_tenant_filter = []
        if is_platform_agent and requesting_tenant_id:
            try:
                llm_tenant_filter = [AgentLLMConfig.tenant_id == uuid.UUID(requesting_tenant_id)]
            except ValueError:
                pass

        # Load default LLM config
        llm_config_stmt = select(AgentLLMConfig).where(
            AgentLLMConfig.agent_id == db_agent.id,
            AgentLLMConfig.enabled,
            AgentLLMConfig.is_default,
            *llm_tenant_filter,
        )
        llm_config_result = await db.execute(llm_config_stmt)
        default_llm_config = llm_config_result.scalar_one_or_none()

        # Prepare LLM config dict
        llm_config_dict = None
        if default_llm_config:
            llm_config_dict = {
                "provider": default_llm_config.provider,
                "model_name": default_llm_config.model_name,
                "temperature": default_llm_config.temperature,
                "max_tokens": default_llm_config.max_tokens,
                "top_p": default_llm_config.top_p,
                "api_key": default_llm_config.api_key,  # Encrypted
                "api_base": default_llm_config.api_base,
                "additional_params": default_llm_config.additional_params or {},
            }

        # Cache agent data
        agent_dict = {
            "id": str(db_agent.id),
            "agent_name": db_agent.agent_name,
            "slug": db_agent.slug,
            "agent_type": db_agent.agent_type,
            "description": db_agent.description,
            "avatar": db_agent.avatar,
            "system_prompt": db_agent.system_prompt,
            "llm_config": db_agent.llm_config,
            "default_llm_config": llm_config_dict,
            "tools_config": db_agent.tools_config,
            "agent_metadata": db_agent.agent_metadata,
            "observability_config": db_agent.observability_config,
            "workflow_type": db_agent.workflow_type,
            "workflow_config": db_agent.workflow_config,
            "routing_mode": getattr(db_agent, "routing_mode", "fixed") or "fixed",
            "routing_config": getattr(db_agent, "routing_config", None),
            "status": db_agent.status,
            "tenant_id": str(db_agent.tenant_id),
            "email_template_id": str(db_agent.email_template_id) if getattr(db_agent, "email_template_id", None) else None,
            "created_at": db_agent.created_at.isoformat() if db_agent.created_at else None,
            "updated_at": db_agent.updated_at.isoformat() if db_agent.updated_at else None,
        }

        # Use slug as cache key when available; fall back to agent_name for platform agents
        cache_slug = db_agent.slug or db_agent.agent_name
        cache_tenant_id = str(db_agent.tenant_id)
        await self.cache.set_agent_config(
            slug=cache_slug,
            tenant_id=cache_tenant_id,
            config=agent_dict,
        )

        # For platform-shared agents (zero UUID tenant), also cache under the requesting tenant's
        # key so subsequent requests from that tenant hit the cache directly.
        _PLATFORM_TENANT_ID = "00000000-0000-0000-0000-000000000000"
        if (
            cache_tenant_id == _PLATFORM_TENANT_ID
            and requesting_tenant_id
            and requesting_tenant_id != _PLATFORM_TENANT_ID
        ):
            await self.cache.set_agent_config(
                slug=cache_slug,
                tenant_id=requesting_tenant_id,
                config=agent_dict,
            )

    async def _load_agent_to_memory(
        self,
        agent_name: str,
        db_agent: Agent,
        cached_data: dict[str, Any] | None,
        llm_config_id: str | None,
        db: AsyncSession,
        requesting_tenant_id: str = "",
    ) -> Any:
        """Load agent into memory with LLM client."""
        _tenant_id = str(db_agent.tenant_id) if db_agent.tenant_id else ""

        # Check if already in memory (tenant-scoped).
        agent = self.agent_manager.registry.get(agent_name, _tenant_id)

        if agent and agent.llm_client and not llm_config_id:
            logger.info(f"Agent '{agent_name}' already in memory with LLM client")
            return agent

        # Remove broken agent from memory if exists (no llm_client means init failed)
        if agent and not agent.llm_client:
            logger.warning(f"Agent '{agent_name}' in memory but LLM client not initialized, reloading...")
            try:
                await self.agent_manager.delete_agent(agent_name, _tenant_id)
            except Exception as e:
                logger.warning(f"Failed to remove broken agent: {e}")
            agent = None

        # Load LLM configuration
        llm_config, api_key, error = await self._resolve_llm_config(
            db_agent=db_agent,
            cached_data=cached_data,
            llm_config_id=llm_config_id,
            db=db,
            requesting_tenant_id=requesting_tenant_id,
        )

        if error:
            return {"error": error}

        # Create agent config
        tools = []
        if db_agent.tools_config and "tools" in db_agent.tools_config:
            tools = [ToolConfig(**tool) for tool in db_agent.tools_config["tools"]]

        config = AgentConfig(
            name=agent_name,  # slug — consistent with registry lookup key
            description=db_agent.description or "",
            system_prompt=db_agent.system_prompt or "",
            llm_config=llm_config,
            tools=tools,
        )

        # Determine agent class
        agent_class_map = {
            "llm": LLMAgent,
            "research": ResearchAgent,
            "code": CodeAgent,
            "claude_code": ClaudeCodeAgent,
        }
        agent_class = agent_class_map.get(db_agent.agent_type.lower() if db_agent.agent_type else "llm", LLMAgent)

        # When routing selected a specific config (llm_config_id is set) and the agent is
        # already registered with the default model, build a temporary agent instance for
        # this request only — do NOT register it, so the default agent stays cached.
        if llm_config_id and agent:
            try:
                from src.services.agents.security import get_api_key_manager

                key_manager = get_api_key_manager()
                encrypted_key = key_manager.encrypt_api_key(api_key) if api_key else None
                if encrypted_key:
                    config.llm_config.api_key = encrypted_key
                routed_agent = agent_class(config, observability_config=db_agent.observability_config or {})
                if api_key:
                    routed_agent.initialize_client(api_key)
                logger.info(
                    f"[routing] Built temporary agent for '{agent_name}' with model "
                    f"'{llm_config.model_name}' (config_id={llm_config_id})"
                )
                return routed_agent
            except Exception as e:
                logger.warning(f"[routing] Failed to build routed agent, falling back to registered: {e}")
                return agent

        # Create and register agent (tenant-scoped registry entry)
        try:
            new_agent = await self.agent_manager.create_agent(
                config=config,
                agent_class=agent_class,
                api_key=api_key,
                observability_config=db_agent.observability_config or {},
                tenant_id=_tenant_id,
            )

            logger.info(f"Agent '{agent_name}' loaded into memory")
            return new_agent

        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            return {"error": f"Failed to create agent: {str(e)}"}

    async def _run_routing(
        self,
        db_agent: Agent,
        query: str,
        conversation_history: list[dict[str, Any]] | None,
        db: AsyncSession,
    ) -> tuple[RoutingDecision | None, str | None, list[str]]:
        """
        Classify the query and pick the best LLM config using the model router.

        LLM configs are cached in Redis (TTL=300s) to avoid a DB query on every
        routed request.  The cache is keyed by agent_id so it's invalidated
        automatically when configs change (via agent update → cache eviction).

        Returns:
            (RoutingDecision, selected_config_id, fallback_config_ids)
        """
        from src.models.agent_llm_config import AgentLLMConfig

        try:
            all_configs = await self._load_llm_configs_cached(db_agent, db)

            if not all_configs:
                return None, None, []

            # Classify the query (< 1ms, zero API cost)
            classification = classify_query(query, conversation_history)

            # Run the router
            router = get_router()
            decision = router.select(
                routing_mode=getattr(db_agent, "routing_mode", "fixed") or "fixed",
                routing_config=getattr(db_agent, "routing_config", None),
                llm_configs=all_configs,
                classification=classification,
                explicit_config_id=None,
            )

            logger.info(
                f"[routing] agent={db_agent.agent_name} {decision} "
                f"intent={classification.intent} complexity={classification.complexity:.2f} "
                f"tokens~={classification.estimated_input_tokens}"
            )

            return decision, decision.primary_config_id, decision.fallback_config_ids

        except Exception as e:
            logger.warning(f"[routing] Failed for agent '{db_agent.agent_name}', using default: {e}")
            return None, None, []

    async def _load_llm_configs_cached(self, db_agent: Agent, db: AsyncSession) -> list:
        """
        Return all enabled AgentLLMConfig rows for the agent.

        Tries Redis first (TTL=300s).  On miss, loads from DB and populates the cache.
        Returns lightweight proxy objects that expose the same attributes the router
        reads (id, model_name, provider, is_default, enabled, routing_rules,
        routing_weight, display_order).
        """
        import json
        import types

        from src.models.agent_llm_config import AgentLLMConfig

        # Key consistent with AgentCacheService._build_key so invalidation works
        # Use slug when available; fall back to agent_name for platform agents without slugs
        cache_key = self.cache._build_key("llm_configs", db_agent.slug or db_agent.agent_name)

        # ── Redis fast path ──────────────────────────────────────────────────
        redis = self.cache._get_redis()
        if redis:
            try:
                raw = await redis.get(cache_key)
                if raw:
                    rows = json.loads(raw)
                    logger.debug(
                        f"[routing] LLM config cache HIT for agent '{db_agent.agent_name}' ({len(rows)} configs)"
                    )
                    return [types.SimpleNamespace(**r) for r in rows]
            except Exception as cache_err:
                logger.debug(f"[routing] LLM config cache read error (continuing to DB): {cache_err}")

        # ── DB slow path ─────────────────────────────────────────────────────
        stmt = (
            select(AgentLLMConfig)
            .where(AgentLLMConfig.agent_id == db_agent.id, AgentLLMConfig.enabled)
            .order_by(AgentLLMConfig.display_order, AgentLLMConfig.created_at)
        )
        result = await db.execute(stmt)
        db_configs = list(result.scalars().all())

        # Serialize only the fields the router reads (no api_key — not needed for routing)
        serializable = [
            {
                "id": str(c.id),
                "model_name": c.model_name,
                "provider": c.provider,
                "is_default": bool(c.is_default),
                "enabled": bool(c.enabled),
                "routing_rules": c.routing_rules or {},
                "routing_weight": float(c.routing_weight) if c.routing_weight is not None else None,
                "display_order": int(c.display_order or 0),
            }
            for c in db_configs
        ]

        if redis and serializable:
            try:
                await redis.setex(cache_key, 300, json.dumps(serializable))
                logger.debug(
                    f"[routing] LLM config cache SET for agent '{db_agent.agent_name}' "
                    f"({len(serializable)} configs, TTL=300s)"
                )
            except Exception as cache_err:
                logger.debug(f"[routing] LLM config cache write error: {cache_err}")

        return [types.SimpleNamespace(**r) for r in serializable]

    async def _resolve_llm_config(
        self,
        db_agent: Agent,
        cached_data: dict[str, Any] | None,
        llm_config_id: str | None,
        db: AsyncSession,
        requesting_tenant_id: str = "",
    ) -> tuple[ModelConfig | None, str | None, str | None]:
        """
        Resolve LLM configuration from cache or database.

        For platform-shared agents (zero UUID tenant_id), LLM configs are stored per-tenant
        so we must filter by the requesting tenant's ID to prevent cross-tenant key leakage.

        Returns:
            Tuple of (ModelConfig, api_key, error_message)
        """
        from src.models.agent_llm_config import AgentLLMConfig

        _PLATFORM_TENANT_ID = "00000000-0000-0000-0000-000000000000"
        is_platform_agent = str(db_agent.tenant_id) == _PLATFORM_TENANT_ID

        cached_llm = cached_data.get("default_llm_config") if cached_data else None

        if cached_llm and not llm_config_id:
            logger.info(f"Using CACHED LLM config: {cached_llm.get('provider')}/{cached_llm.get('model_name')}")

            api_key = decrypt_value(cached_llm["api_key"]) if cached_llm.get("api_key") else ""

            # Apply preset defaults for max_tokens if not configured
            max_tokens = self._get_max_tokens_with_preset_default(
                cached_llm["provider"], cached_llm["model_name"], cached_llm["max_tokens"]
            )

            llm_config = ModelConfig(
                provider=cached_llm["provider"],
                model_name=cached_llm["model_name"],
                temperature=cached_llm["temperature"],
                max_tokens=max_tokens,
                top_p=cached_llm["top_p"],
                api_key=api_key,
                api_base=cached_llm.get("api_base"),
                additional_params=cached_llm.get("additional_params") or {},
            )

            return llm_config, api_key, None

        # Build base tenant filter for platform-shared agents.
        # Regular agents: their configs are owned by the same tenant, so filtering by
        # agent_id is sufficient. Platform agents: configs from all tenants share the
        # same agent_id, so we MUST scope by requesting_tenant_id.
        tenant_filter = []
        if is_platform_agent and requesting_tenant_id:
            try:
                tenant_filter = [AgentLLMConfig.tenant_id == uuid.UUID(requesting_tenant_id)]
            except ValueError:
                pass

        # Load from database
        default_llm_config = None

        if llm_config_id:
            try:
                llm_config_uuid = uuid.UUID(llm_config_id)
                stmt = select(AgentLLMConfig).where(
                    AgentLLMConfig.id == llm_config_uuid,
                    AgentLLMConfig.agent_id == db_agent.id,
                    AgentLLMConfig.enabled,
                    *tenant_filter,
                )
                result = await db.execute(stmt)
                default_llm_config = result.scalar_one_or_none()
            except (ValueError, Exception) as e:
                logger.warning(f"Invalid llm_config_id '{llm_config_id}': {e}")

        # Try default config
        if not default_llm_config:
            stmt = select(AgentLLMConfig).where(
                AgentLLMConfig.agent_id == db_agent.id,
                AgentLLMConfig.enabled,
                AgentLLMConfig.is_default,
                *tenant_filter,
            )
            result = await db.execute(stmt)
            default_llm_config = result.scalar_one_or_none()

        # Try any enabled config (still scoped to tenant for platform agents)
        if not default_llm_config:
            stmt = (
                select(AgentLLMConfig)
                .where(AgentLLMConfig.agent_id == db_agent.id, AgentLLMConfig.enabled, *tenant_filter)
                .order_by(AgentLLMConfig.display_order, AgentLLMConfig.created_at)
                .limit(1)
            )
            result = await db.execute(stmt)
            default_llm_config = result.scalar_one_or_none()

        if not default_llm_config:
            error_msg = f'No LLM model configured for agent "{db_agent.agent_name}". Please configure at least one LLM model in the "LLM Configuration" tab.'
            return None, None, error_msg

        # Decrypt API key
        api_key = decrypt_value(default_llm_config.api_key) if default_llm_config.api_key else ""

        if not api_key or api_key.strip() == "":
            error_msg = f'Agent "{db_agent.agent_name}" is missing LLM API key. Please configure the LLM settings.'
            return None, None, error_msg

        # Apply preset defaults for max_tokens if not configured
        max_tokens = self._get_max_tokens_with_preset_default(
            default_llm_config.provider, default_llm_config.model_name, default_llm_config.max_tokens
        )

        llm_config = ModelConfig(
            provider=default_llm_config.provider,
            model_name=default_llm_config.model_name,
            temperature=default_llm_config.temperature,
            max_tokens=max_tokens,
            top_p=default_llm_config.top_p,
            api_key=api_key,
            api_base=default_llm_config.api_base,
            additional_params=default_llm_config.additional_params or {},
        )

        logger.info(f"Loaded LLM config: {llm_config.provider}/{llm_config.model_name} (max_tokens={max_tokens})")

        return llm_config, api_key, None
