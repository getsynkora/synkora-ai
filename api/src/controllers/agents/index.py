"""
Agent CRUD operations.

Handles basic agent creation, listing, retrieval, update, delete, and reset operations.
"""

import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from src.controllers.agents.models import (
    AgentResponse,
    CloneAgentRequest,
    CreateAgentRequest,
    ExecuteAgentRequest,
    ExecuteWorkflowRequest,
    UpdateAgentRequest,
)
from src.core.database import get_async_db
from src.middleware.auth_middleware import get_current_account, get_current_tenant_id, require_role
from src.models import AccountRole
from src.models.agent import Agent
from src.services.agents.agent_manager import AgentManager
from src.services.agents.implementations import ClaudeCodeAgent, CodeAgent, LLMAgent, ResearchAgent
from src.services.cache import get_agent_cache
from src.services.storage.s3_storage import S3StorageService

logger = logging.getLogger(__name__)

# Create router
agents_index_router = APIRouter()

# Global agent manager instance
agent_manager = AgentManager()

# Singleton S3 storage service — reused across requests to avoid boto3 client overhead
_storage_service: S3StorageService | None = None


def _get_storage_service() -> S3StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = S3StorageService()
    return _storage_service


def convert_s3_uri_to_presigned_url(s3_uri: str) -> str:
    """
    Convert S3 URI to presigned URL for frontend display.

    Args:
        s3_uri: S3 URI (s3://bucket/key) or HTTP URL

    Returns:
        Presigned HTTP URL or original URL if not S3 URI
    """
    if not s3_uri:
        return s3_uri

    # If it's already an HTTP URL, return as-is
    if s3_uri.startswith(("http://", "https://")):
        return s3_uri

    # If it's an S3 URI or key path, generate presigned URL
    if s3_uri.startswith("s3://") or "/" in s3_uri:
        try:
            storage_service = _get_storage_service()
            # Generate presigned URL valid for 7 days
            return storage_service.generate_presigned_url(s3_uri, expiration=86400 * 7)
        except Exception as e:
            logger.warning(f"Failed to generate presigned URL for {s3_uri}: {e}")
            return s3_uri

    return s3_uri


# Endpoints
@agents_index_router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: CreateAgentRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_role(AccountRole.ADMIN)),
):
    """
    Create and register a new agent.

    Args:
        request: Agent creation request
        db: Database session

    Returns:
        Agent creation response
    """
    try:
        # Check agent creation limit
        from src.services.billing import PlanRestrictionError, PlanRestrictionService

        restriction_service = PlanRestrictionService(db)
        try:
            await restriction_service.enforce_agent_limit(tenant_id)
        except PlanRestrictionError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        # Determine agent class
        agent_class_map = {
            "llm": LLMAgent,
            "research": ResearchAgent,
            "code": CodeAgent,
            "claude_code": ClaudeCodeAgent,
        }

        agent_class = agent_class_map.get(request.agent_type.lower())
        if not agent_class:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown agent type: {request.agent_type}. Valid types: llm, research, code, claude_code",
            )

        # SECURITY: Scan system prompt for potential injection patterns
        if request.config.system_prompt:
            from src.services.security.advanced_prompt_scanner import advanced_prompt_scanner

            scan_result = advanced_prompt_scanner.scan_comprehensive(
                text=request.config.system_prompt,
                user_id=f"tenant_{tenant_id}",
                context={"source": "agent_creation", "agent_name": request.config.name},
            )

            if not scan_result["is_safe"]:
                detections = scan_result.get("detections", [])
                threat_names = [d.get("pattern_id", "unknown") for d in detections]
                logger.warning(
                    f"System prompt injection detected during agent creation '{request.config.name}' by tenant {tenant_id}: {threat_names}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"System prompt contains potentially dangerous patterns: {', '.join(threat_names)}",
                )

        # SECURITY: Sanitize suggestion_prompts to prevent stored XSS
        from src.services.security.input_sanitizer import sanitize_suggestion_prompts

        sanitized_suggestion_prompts = sanitize_suggestion_prompts(getattr(request.config, "suggestion_prompts", []))

        # Create agent in memory (tenant-scoped)
        if request.api_key:
            await agent_manager.create_agent(
                config=request.config, agent_class=agent_class, api_key=request.api_key, tenant_id=str(tenant_id)
            )

        # Prepare llm_config with encrypted API key
        from src.services.agents.internal_tools.platform_tools import normalize_tool_categories
        from src.services.agents.security import encrypt_value

        llm_config_data = request.config.llm_config.model_dump()
        if llm_config_data.get("api_key"):
            llm_config_data["api_key"] = encrypt_value(llm_config_data["api_key"])

        normalized_tool_names = (
            normalize_tool_categories([tool.name for tool in request.config.tools]) if request.config.tools else []
        )
        normalized_tool_payloads: list[dict[str, object]] = []
        if request.config.tools:
            seen_tool_names: set[str] = set()
            for tool in request.config.tools:
                normalized_values = normalize_tool_categories([tool.name])
                normalized_name = normalized_values[0] if normalized_values else tool.name
                if normalized_name in seen_tool_names:
                    continue
                seen_tool_names.add(normalized_name)
                tool_payload = tool.model_dump()
                tool_payload["name"] = normalized_name
                if tool_payload.get("description") == tool.name.replace("_", " "):
                    tool_payload["description"] = normalized_name.replace("_", " ")
                normalized_tool_payloads.append(tool_payload)

        # Save to database
        db_agent = Agent(
            tenant_id=tenant_id,
            agent_name=request.config.name,
            agent_type=request.agent_type.lower(),
            description=request.config.description,
            avatar=request.config.avatar,
            system_prompt=request.config.system_prompt,
            llm_config=llm_config_data,
            tools_config={"tools": normalized_tool_payloads} if normalized_tool_payloads else None,
            agent_metadata=request.config.metadata or {},
            status="ACTIVE",
            suggestion_prompts=sanitized_suggestion_prompts,  # SECURITY: Use sanitized prompts
            is_public=getattr(request, "is_public", False),
            category=getattr(request, "category", None),
            tags=getattr(request, "tags", []) or [],
            role_id=uuid.UUID(request.role_id) if request.role_id else None,
            human_contact_id=uuid.UUID(request.human_contact_id) if request.human_contact_id else None,
        )

        import re as _re

        db.add(db_agent)
        # Set slug: use provided slug if valid, otherwise auto-generate from agent name
        if request.slug:
            db_agent.slug = request.slug
        else:
            _base_slug = _re.sub(r"[^a-z0-9-]", "-", request.config.name.lower())
            _base_slug = _re.sub(r"-+", "-", _base_slug).strip("-") or "agent"
            db_agent.slug = _base_slug
        await db.commit()
        await db.refresh(db_agent)

        # Enable AgentTool records for any tool categories in the request
        # (direct per-category patterns — avoids enabling unrelated tools in the same capability group)
        if request.config.tools:
            try:
                import fnmatch

                from src.models.agent_tool import AgentTool
                from src.services.agents.adk_tools import tool_registry
                from src.services.agents.internal_tools.platform_tools import TOOL_CATEGORY_TO_PATTERNS

                available_tool_names = [t["name"] for t in tool_registry.list_tools()]
                requested_categories = normalized_tool_names

                matched_tools: set[str] = set()
                for cat in requested_categories:
                    patterns = TOOL_CATEGORY_TO_PATTERNS.get(cat, [])
                    for tool_name in available_tool_names:
                        if any(fnmatch.fnmatch(tool_name, p) for p in patterns):
                            matched_tools.add(tool_name)

                for tool_name in matched_tools:
                    db.add(AgentTool(agent_id=db_agent.id, tool_name=tool_name, config={}, enabled=True))

                await db.commit()
            except Exception as tool_err:
                await db.rollback()
                logger.warning(f"Failed to enable AgentTool records: {tool_err}")

        # Also create an entry in the agent_llm_configs table for the LLM config
        # This is required because the edit page and chat use that table
        try:
            from sqlalchemy import select as sa_select

            from src.models.agent_llm_config import AgentLLMConfig
            from src.services.agents.security import encrypt_value

            llm_data = request.config.llm_config

            # --- Inherit full LLM config from Platform Engineer when no API key provided ---
            pe_cfg_inherited: AgentLLMConfig | None = None
            if not llm_data.api_key:
                platform_tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
                pe_agent_row = (
                    await db.execute(
                        sa_select(Agent).where(
                            Agent.agent_name == "platform_engineer_agent",
                            Agent.tenant_id == platform_tenant_id,
                        )
                    )
                ).scalar_one_or_none()
                if pe_agent_row:
                    _pe_cfg = (
                        await db.execute(
                            sa_select(AgentLLMConfig)
                            .where(
                                AgentLLMConfig.agent_id == pe_agent_row.id,
                                AgentLLMConfig.tenant_id == tenant_id,
                            )
                            .limit(1)
                        )
                    ).scalar_one_or_none()
                    if _pe_cfg and _pe_cfg.api_key:
                        pe_cfg_inherited = _pe_cfg
                        logger.info(
                            f"Agent '{request.config.name}': inherited LLM config from platform_engineer_agent"
                            f" ({_pe_cfg.provider}/{_pe_cfg.model_name})"
                        )

            if llm_data.api_key:
                # User supplied a key — encrypt it and use request values as-is
                encrypted_api_key = encrypt_value(llm_data.api_key)
                effective_provider = llm_data.provider
                effective_model = llm_data.model_name
                effective_api_base = llm_data.api_base
                effective_temperature = llm_data.temperature
                effective_max_tokens = llm_data.max_tokens
                effective_top_p = llm_data.top_p
                effective_additional_params = llm_data.additional_params or {}
            elif pe_cfg_inherited:
                # No key supplied — copy everything from PE config
                encrypted_api_key = pe_cfg_inherited.api_key
                effective_provider = pe_cfg_inherited.provider
                effective_model = pe_cfg_inherited.model_name
                effective_api_base = pe_cfg_inherited.api_base
                effective_temperature = pe_cfg_inherited.temperature
                effective_max_tokens = pe_cfg_inherited.max_tokens
                effective_top_p = pe_cfg_inherited.top_p
                effective_additional_params = pe_cfg_inherited.additional_params or {}
            else:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "No API key provided and no Platform Engineer LLM configuration found. "
                        "Supply an api_key or configure the Platform Engineer agent's LLM settings first."
                    ),
                )

            llm_config_entry = AgentLLMConfig(
                tenant_id=tenant_id,
                agent_id=db_agent.id,
                name=f"Primary {effective_model}",
                provider=effective_provider,
                model_name=effective_model,
                api_key=encrypted_api_key,
                api_base=effective_api_base,
                temperature=effective_temperature,
                max_tokens=effective_max_tokens,
                top_p=effective_top_p,
                additional_params=effective_additional_params,
                is_default=True,
                display_order=0,
                enabled=True,
            )
            db.add(llm_config_entry)
            await db.flush()

            from src.services.agents.internal_tools.platform_tools import (
                resolve_image_generation_config,
                upsert_image_generation_llm_config,
            )

            requested_categories = normalized_tool_names
            image_metadata = request.config.metadata or {}
            image_config = resolve_image_generation_config(
                tools_list=requested_categories,
                image_llm_provider=image_metadata.get("image_generation_provider"),
                image_llm_model=image_metadata.get("image_generation_model"),
                fallback_provider=effective_provider,
            )
            if image_config:
                await upsert_image_generation_llm_config(
                    db_session=db,
                    agent=db_agent,
                    tenant_id=tenant_id,
                    encrypted_api_key=encrypted_api_key,
                    api_base=effective_api_base,
                    additional_params=effective_additional_params,
                    provider=image_config["provider"],
                    model_name=image_config["model"],
                )

            await db.commit()
            logger.info(f"Created LLM config entry for agent '{request.config.name}'")
        except Exception as llm_err:
            logger.warning(f"Failed to create LLM config entry: {llm_err}")
            # Don't fail agent creation if LLM config entry fails

        # PERFORMANCE: Invalidate agents list cache for this tenant
        cache = get_agent_cache()
        await cache.invalidate_agents_list(str(tenant_id))

        # Audit: log agent creation (best-effort)
        try:
            from src.services.activity.activity_log_service import ActivityLogService

            _log_svc = ActivityLogService(db)
            await _log_svc.log_activity(
                tenant_id=tenant_id,
                account_id=current_account.id,
                action="agent.created",
                resource_type="agent",
                resource_id=db_agent.id,
                details={"agent_name": db_agent.agent_name, "agent_type": db_agent.agent_type},
            )
        except Exception:
            pass

        return AgentResponse(
            success=True,
            message=f"Agent '{request.config.name}' created successfully",
            data={"agent_id": str(db_agent.id), "agent_name": request.config.name, "slug": db_agent.slug},
        )

    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        from sqlalchemy.exc import IntegrityError

        await db.rollback()

        # Handle duplicate agent name error (constraint is uq_agent_name_tenant)
        if isinstance(e, IntegrityError) and ("uq_agent_name_tenant" in str(e) or "agents_agent_name_idx" in str(e)):
            logger.warning(f"Duplicate agent name attempted: {request.config.name}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Agent with name '{request.config.name}' already exists. Please choose a different name.",
            )

        # Handle duplicate slug error
        elif isinstance(e, IntegrityError) and "uq_agent_slug" in str(e):
            logger.warning(f"Duplicate agent slug attempted: {getattr(request, 'slug', None) or request.config.name}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Agent slug is already in use. Please choose a different slug.",
            )

        # Handle other integrity errors
        elif isinstance(e, IntegrityError):
            logger.warning(f"Database integrity error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid data provided. Please check your input and try again.",
            )

        # Handle other exceptions
        logger.error(f"Failed to create agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create agent. Please try again later.",
        )


@agents_index_router.post("/execute", response_model=AgentResponse)
async def execute_agent(
    request: ExecuteAgentRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Execute a registered agent.

    Args:
        request: Agent execution request
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Execution result
    """
    try:
        from sqlalchemy import or_

        # SECURITY: Verify agent belongs to tenant OR is public before execution
        result = await db.execute(
            select(Agent).filter(
                Agent.slug == request.agent_slug, or_(Agent.tenant_id == tenant_id, Agent.is_public.is_(True))
            )
        )
        db_agent = result.scalar_one_or_none()

        if not db_agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{request.agent_slug}' not found")

        result = await agent_manager.execute_agent(request.agent_slug, request.input_data, str(tenant_id))

        return AgentResponse(
            success=result.get("status") == "success",
            message=f"Agent '{request.agent_slug}' executed",
            data=result,
        )

    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    except Exception as e:
        logger.error(f"Failed to execute agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute agent",
        )


@agents_index_router.post("/workflows/execute", response_model=AgentResponse)
async def execute_workflow(
    request: ExecuteWorkflowRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Execute a multi-agent workflow.

    Args:
        request: Workflow execution request
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Workflow execution result
    """
    try:
        from sqlalchemy import or_

        # SECURITY: Verify all agents in workflow belong to tenant OR are public
        agent_names = [step.agent_name for step in request.workflow_config.steps]
        result = await db.execute(
            select(Agent).filter(
                Agent.slug.in_(agent_names), or_(Agent.tenant_id == tenant_id, Agent.is_public.is_(True))
            )
        )
        found_slugs = {a.slug for a in result.scalars().all()}
        for agent_name in agent_names:
            if agent_name not in found_slugs:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_name}' not found in workflow"
                )

        result = await agent_manager.execute_workflow(request.workflow_config, request.input_data)

        return AgentResponse(
            success=result.get("status") in ["success", "partial_success"],
            message=f"Workflow '{request.workflow_config.name}' executed",
            data=result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute workflow",
        )


@agents_index_router.get("/", response_model=AgentResponse)
async def list_agents(
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List all registered agents from database with pagination.

    Args:
        page: Page number (starts from 1)
        page_size: Number of items per page
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        Paginated list of agent names with metadata including workflow info and sub-agents
    """
    from src.models.agent_sub_agent import AgentSubAgent

    try:
        # Validate pagination parameters
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 10
        if page_size > 100:
            page_size = 100

        # PERFORMANCE: Only use the list cache when there is no search query
        cache = get_agent_cache()
        tenant_id_str = str(tenant_id)
        if not search:
            cached_data = await cache.get_agents_list(tenant_id_str, page, page_size)
            if cached_data:
                return AgentResponse(
                    success=True,
                    message=cached_data.get("message", "Found agents (cached)"),
                    data=cached_data.get("data", {}),
                )

        # Build base filters (tenant + optional search)
        base_filters = [Agent.tenant_id == tenant_id]
        if search:
            search_term = f"%{search}%"
            from sqlalchemy import or_ as _or

            base_filters.append(
                _or(
                    Agent.agent_name.ilike(search_term),
                    Agent.description.ilike(search_term),
                )
            )

        # Calculate offset
        offset = (page - 1) * page_size

        # Get total count
        count_result = await db.execute(select(func.count()).select_from(Agent).filter(*base_filters))
        total_count = count_result.scalar()

        # PERFORMANCE: Get paginated agents from database without restoring to memory
        # Agents are loaded on-demand when needed, not on list
        agents_result = await db.execute(
            select(Agent).filter(*base_filters).order_by(Agent.created_at.desc()).offset(offset).limit(page_size)
        )
        db_agents = agents_result.scalars().all()

        # Get sub-agent counts for all agents in one query
        agent_ids = [db_agent.id for db_agent in db_agents]
        sub_agent_counts_result = await db.execute(
            select(AgentSubAgent.parent_agent_id, func.count(AgentSubAgent.id).label("count"))
            .filter(AgentSubAgent.parent_agent_id.in_(agent_ids))
            .group_by(AgentSubAgent.parent_agent_id)
        )
        sub_agent_counts = sub_agent_counts_result.all()
        sub_agent_count_map = {str(parent_id): count for parent_id, count in sub_agent_counts}

        # Get sub-agents data for agents that have sub-agents
        sub_agents_result = await db.execute(
            select(AgentSubAgent)
            .options(selectinload(AgentSubAgent.sub_agent))
            .filter(AgentSubAgent.parent_agent_id.in_(agent_ids))
            .order_by(AgentSubAgent.execution_order)
        )
        sub_agents_data = sub_agents_result.scalars().all()

        # Get set of agent IDs that are used as sub-agents (to filter them out from main list)
        # PERFORMANCE: Scope to current tenant to avoid unbounded cross-tenant query
        sub_agent_ids_query = await db.execute(
            select(AgentSubAgent.sub_agent_id)
            .join(Agent, Agent.id == AgentSubAgent.parent_agent_id)
            .filter(Agent.tenant_id == tenant_id)
            .distinct()
        )
        sub_agent_ids_result = sub_agent_ids_query.all()
        sub_agent_ids_set = {str(row[0]) for row in sub_agent_ids_result}

        # Build sub-agents map by parent_agent_id
        sub_agents_map: dict = {}
        for sub_agent_rel in sub_agents_data:
            parent_id = str(sub_agent_rel.parent_agent_id)
            if parent_id not in sub_agents_map:
                sub_agents_map[parent_id] = []
            sub_agents_map[parent_id].append(
                {
                    "id": str(sub_agent_rel.id),
                    "sub_agent_id": str(sub_agent_rel.sub_agent_id),
                    "sub_agent_name": sub_agent_rel.sub_agent.agent_name if sub_agent_rel.sub_agent else None,
                    "sub_agent_type": sub_agent_rel.sub_agent.agent_type if sub_agent_rel.sub_agent else None,
                    "execution_order": sub_agent_rel.execution_order,
                    "is_active": sub_agent_rel.is_active,
                }
            )

        # NOTE: Removed agent restoration loop to prevent N+1 queries and memory bloat
        # Agents are now loaded lazily when actually needed (e.g., during chat)

        # Calculate pagination metadata
        total_pages = (total_count + page_size - 1) // page_size
        has_next = page < total_pages
        has_prev = page > 1

        # Fetch published slugs for all agents in one query
        from src.models.agent_public_profile import AgentPublicProfile

        slug_rows = await db.execute(
            select(AgentPublicProfile.agent_id, AgentPublicProfile.slug).where(
                AgentPublicProfile.agent_id.in_(agent_ids),
                AgentPublicProfile.is_published.is_(True),
            )
        )
        slug_map = {row.agent_id: row.slug for row in slug_rows}

        # Convert S3 URIs to presigned URLs for avatars
        agents_list = []
        for db_agent in db_agents:
            agent_id_str = str(db_agent.id)
            avatar_url = convert_s3_uri_to_presigned_url(db_agent.avatar) if db_agent.avatar else None

            # Check if this agent is a sub-agent of another agent
            # Either via parent_agent_id or via AgentSubAgent junction table
            is_sub_agent = db_agent.parent_agent_id is not None or agent_id_str in sub_agent_ids_set

            agents_list.append(
                {
                    "id": agent_id_str,
                    "agent_name": db_agent.agent_name,
                    "slug": db_agent.slug,
                    "public_slug": slug_map.get(db_agent.id),
                    "description": db_agent.description,
                    "agent_type": db_agent.agent_type,
                    "avatar": avatar_url,
                    "status": db_agent.status,
                    "workflow_type": db_agent.workflow_type,
                    "execution_count": db_agent.execution_count,
                    "success_rate": db_agent.success_rate,
                    "created_at": db_agent.created_at.isoformat() if db_agent.created_at else None,
                    "sub_agents_count": sub_agent_count_map.get(agent_id_str, 0),
                    "sub_agents": sub_agents_map.get(agent_id_str, []),
                    "is_public": db_agent.is_public,
                    "category": db_agent.category,
                    "tags": db_agent.tags or [],
                    "is_sub_agent": is_sub_agent,
                }
            )

        # Build response data
        response_message = f"Found {total_count} agents"
        response_data = {
            "agents": [db_agent.agent_name for db_agent in db_agents],
            "agents_list": agents_list,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_count,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev,
            },
        }

        # PERFORMANCE: Cache the response for 60 seconds (skip when search is active)
        if not search:
            await cache.set_agents_list(
                tenant_id_str,
                {"message": response_message, "data": response_data},
                page,
                page_size,
            )

        return AgentResponse(
            success=True,
            message=response_message,
            data=response_data,
        )

    except Exception as e:
        logger.error(f"Failed to list agents: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list agents")


# NOTE: Static routes like /categories and /stats MUST be defined BEFORE dynamic routes like /{agent_name}
# Otherwise FastAPI will match "categories" as an agent_name parameter
@agents_index_router.get("/categories", response_model=AgentResponse)
async def list_agent_categories(db: AsyncSession = Depends(get_async_db)):
    """
    List all available agent categories.

    Args:
        db: Database session

    Returns:
        List of categories with agent counts
    """
    try:
        # Get categories with counts
        categories_result = await db.execute(
            select(Agent.category, func.count(Agent.id).label("count"))
            .filter(Agent.is_public, Agent.category.isnot(None))
            .group_by(Agent.category)
        )
        categories = categories_result.all()

        categories_list = [{"name": cat, "count": count} for cat, count in categories]

        return AgentResponse(
            success=True, message=f"Found {len(categories_list)} categories", data={"categories": categories_list}
        )

    except Exception as e:
        logger.error(f"Failed to list categories: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list categories")


@agents_index_router.get("/stats", response_model=AgentResponse)
async def get_all_stats(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get statistics for all agents belonging to the current tenant.

    Args:
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Statistics for tenant's agents only
    """
    try:
        # SECURITY: Only return stats for agents belonging to current tenant
        result = await db.execute(select(Agent.agent_name).filter(Agent.tenant_id == tenant_id))
        tenant_agents = result.all()
        tenant_agent_names = {a[0] for a in tenant_agents}

        all_stats = agent_manager.get_all_stats()
        # Filter stats to only include tenant's agents
        filtered_stats = {name: stats for name, stats in all_stats.items() if name in tenant_agent_names}

        return AgentResponse(success=True, message="Retrieved stats for tenant agents", data={"agents": filtered_stats})

    except Exception as e:
        logger.error(f"Failed to get all stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent stats",
        )


@agents_index_router.get("/{agent_slug}", response_model=AgentResponse)
async def get_agent(
    agent_slug: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get details of a specific agent.

    Args:
        agent_name: Name of the agent
        db: Database session

    Returns:
        Agent details
    """
    try:
        from sqlalchemy import or_

        # SECURITY: Single query with OR to prevent timing attacks
        # Checks: (agent belongs to tenant) OR (agent is public)
        result = await db.execute(
            select(Agent)
            .options(selectinload(Agent.role), selectinload(Agent.human_contact))
            .filter(Agent.slug == agent_slug, or_(Agent.tenant_id == tenant_id, Agent.is_public.is_(True)))
        )
        db_agent = result.scalar_one_or_none()

        if not db_agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")

        # SECURITY: determine ownership before exposing sensitive fields
        is_own_agent = str(db_agent.tenant_id) == str(tenant_id)

        # Return 404 (not 403) for agents belonging to a different tenant that are not public,
        # to avoid leaking the existence of private agents across tenants.
        if not is_own_agent and not db_agent.is_public:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")

        # Get runtime stats if agent is in memory (tenant-scoped lookup)
        stats = {}
        if is_own_agent and agent_manager.registry.contains(agent_slug, str(tenant_id)):
            stats = agent_manager.get_agent_stats(agent_slug, str(tenant_id))

        # Convert S3 URI to presigned URL for avatar display
        avatar_url = convert_s3_uri_to_presigned_url(db_agent.avatar) if db_agent.avatar else None

        # Build role and human contact data
        role_data = None
        if db_agent.role:
            role_data = {
                "id": str(db_agent.role.id),
                "role_type": db_agent.role.role_type,
                "role_name": db_agent.role.role_name,
            }

        human_contact_data = None
        if db_agent.human_contact:
            human_contact_data = {
                "id": str(db_agent.human_contact.id),
                "name": db_agent.human_contact.name,
                "preferred_channel": db_agent.human_contact.preferred_channel,
            }

        # SECURITY: strip sensitive config fields when serving a cross-tenant public agent
        if is_own_agent:
            llm_config_out = db_agent.llm_config
            system_prompt_out = db_agent.system_prompt
            tools_config_out = db_agent.tools_config
            observability_config_out = db_agent.observability_config or {}
        else:
            raw_llm = db_agent.llm_config or {}
            # SECURITY: hide model/provider info for cross-tenant public agents when
            # HIDE_MODEL_INFO_IN_PUBLIC=true is set. Prevents competitors or users from
            # fingerprinting which LLM is backing a public agent.
            _hide_model_info = os.getenv("HIDE_MODEL_INFO_IN_PUBLIC", "false").lower() == "true"
            if _hide_model_info:
                llm_config_out = {"model": "custom", "provider": "custom"}
            else:
                llm_config_out = {"model": raw_llm.get("model"), "provider": raw_llm.get("provider")}
            system_prompt_out = None  # never expose system prompt cross-tenant
            tools_config_out = None
            observability_config_out = {}

        return AgentResponse(
            success=True,
            message=f"Agent '{agent_slug}' details",
            data={
                "id": str(db_agent.id),
                "agent_name": db_agent.agent_name,
                "slug": db_agent.slug,
                "agent_type": db_agent.agent_type,
                "description": db_agent.description,
                "avatar": avatar_url,
                "system_prompt": system_prompt_out,
                "llm_config": llm_config_out,
                "tools_config": tools_config_out,
                "observability_config": observability_config_out,
                "agent_metadata": db_agent.agent_metadata or {} if is_own_agent else {},
                "suggestion_prompts": db_agent.suggestion_prompts or [],
                "status": db_agent.status,
                "is_public": db_agent.is_public or False,
                "allow_subscriptions": db_agent.allow_subscriptions or False,
                "category": db_agent.category,
                "tags": db_agent.tags or [],
                "voice_enabled": db_agent.voice_enabled or False,
                "voice_config": db_agent.voice_config or {} if is_own_agent else {},
                "is_adk_workflow_enabled": db_agent.workflow_type is not None,
                "workflow_type": db_agent.workflow_type if is_own_agent else None,
                "workflow_config": db_agent.workflow_config if is_own_agent else None,
                "routing_mode": getattr(db_agent, "routing_mode", "fixed") or "fixed" if is_own_agent else "fixed",
                "routing_config": getattr(db_agent, "routing_config", None) if is_own_agent else None,
                "execution_backend": getattr(db_agent, "execution_backend", "celery") or "celery"
                if is_own_agent
                else None,
                "created_at": db_agent.created_at.isoformat(),
                "updated_at": db_agent.updated_at.isoformat(),
                "stats": stats,
                "role_id": str(db_agent.role_id) if (db_agent.role_id and is_own_agent) else None,
                "human_contact_id": str(db_agent.human_contact_id)
                if (db_agent.human_contact_id and is_own_agent)
                else None,
                "role": role_data if is_own_agent else None,
                "human_contact": human_contact_data if is_own_agent else None,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent details",
        )


@agents_index_router.get("/{agent_slug}/stats", response_model=AgentResponse)
async def get_agent_stats(
    agent_slug: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get statistics for a specific agent.
    Allows access to public agents even if they don't belong to the current tenant.

    Args:
        agent_name: Name of the agent
        db: Database session

    Returns:
        Agent statistics including database info
    """
    try:
        from sqlalchemy import or_

        from src.models.tenant import Tenant

        # SECURITY: Single query with OR to prevent timing attacks
        # Checks: (agent belongs to tenant) OR (agent is public)
        result = await db.execute(
            select(Agent).filter(Agent.slug == agent_slug, or_(Agent.tenant_id == tenant_id, Agent.is_public.is_(True)))
        )
        db_agent = result.scalar_one_or_none()

        if not db_agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")

        # Convert S3 URI to presigned URL for avatar display
        avatar_url = convert_s3_uri_to_presigned_url(db_agent.avatar) if db_agent.avatar else None

        # Use database values for execution stats
        # Calculate failed executions from total and success count
        failed_count = db_agent.execution_count - db_agent.success_count

        # Get creator information from tenant (separate query - Agent doesn't have tenant relationship)
        creator_name = None
        if db_agent.tenant_id:
            tenant_result = await db.execute(select(Tenant).filter(Tenant.id == db_agent.tenant_id))
            tenant = tenant_result.scalar_one_or_none()
            if tenant:
                creator_name = tenant.name

        # Determine whether the requesting tenant owns this agent
        is_own_agent = str(db_agent.tenant_id) == str(tenant_id)

        # For cross-tenant public agents, strip sensitive configuration fields
        if is_own_agent:
            llm_config_response = db_agent.llm_config
        else:
            # Only expose the model name; remove api_key, api_base, and other secrets
            raw_llm = db_agent.llm_config or {}
            llm_config_response = {"model": raw_llm.get("model")}

        # Combine database info with computed stats
        stats = {
            "agent_id": str(db_agent.id),
            "agent_name": db_agent.agent_name,
            "agent_type": db_agent.agent_type,
            "description": db_agent.description,
            "avatar": avatar_url,
            "status": db_agent.status,
            "llm_config": llm_config_response,
            "observability_config": db_agent.observability_config or {},
            "suggestion_prompts": db_agent.suggestion_prompts or [],
            "created_at": db_agent.created_at.isoformat(),
            "updated_at": db_agent.updated_at.isoformat(),
            "execution_count": db_agent.execution_count,
            "success_rate": db_agent.success_rate,  # Uses property from model
            "total_executions": db_agent.execution_count,
            "successful_executions": db_agent.success_count,
            "failed_executions": failed_count,
            "average_execution_time": 0.0,  # This would need separate tracking
            "likes_count": db_agent.likes_count,
            "dislikes_count": db_agent.dislikes_count,
            "usage_count": db_agent.usage_count,
            "creator_name": creator_name,
        }
        # Only include tenant_id for the agent's own tenant — never leak it cross-tenant
        if is_own_agent:
            stats["tenant_id"] = str(db_agent.tenant_id)

        return AgentResponse(success=True, message=f"Stats for agent '{agent_slug}'", data=stats)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get agent stats",
        )


@agents_index_router.put("/{agent_slug}", response_model=AgentResponse)
async def update_agent(
    agent_slug: str,
    request: UpdateAgentRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_role(AccountRole.ADMIN)),
):
    """
    Update an agent's configuration.

    Args:
        agent_name: Name of the agent to update
        request: Update request with fields to change
        db: Database session

    Returns:
        Update confirmation
    """
    try:
        # Get agent from database
        result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
        db_agent = result.scalar_one_or_none()

        if not db_agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")

        # Update fields if provided
        old_agent_name = db_agent.agent_name  # remember original for cache invalidation
        if request.name is not None and request.name != db_agent.agent_name:
            new_name = request.name.strip()
            if not new_name:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Agent name cannot be empty")
            # Check name is not already taken
            existing = await db.scalar(select(Agent).filter(Agent.agent_name == new_name, Agent.tenant_id == tenant_id))
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"An agent named '{new_name}' already exists",
                )
            db_agent.agent_name = new_name
        if request.description is not None:
            db_agent.description = request.description
        if request.avatar is not None:
            db_agent.avatar = request.avatar
        if request.system_prompt is not None:
            # SECURITY: Scan system prompt for potential injection patterns
            from src.services.security.advanced_prompt_scanner import advanced_prompt_scanner

            scan_result = advanced_prompt_scanner.scan_comprehensive(
                text=request.system_prompt,
                user_id=f"tenant_{tenant_id}",
                context={"source": "system_prompt_update", "agent_name": agent_slug},
            )

            if not scan_result["is_safe"]:
                detections = scan_result.get("detections", [])
                threat_names = [d.get("pattern_id", "unknown") for d in detections]
                logger.warning(
                    f"System prompt injection detected for agent '{agent_slug}' by tenant {tenant_id}: {threat_names}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"System prompt contains potentially dangerous patterns: {', '.join(threat_names)}",
                )

            db_agent.system_prompt = request.system_prompt
        if request.llm_config is not None:
            # Encrypt API key if present in the update
            updated_llm_config = (
                request.llm_config.copy() if isinstance(request.llm_config, dict) else request.llm_config
            )
            if isinstance(updated_llm_config, dict) and updated_llm_config.get("api_key"):
                from src.services.agents.security import encrypt_value

                updated_llm_config["api_key"] = encrypt_value(updated_llm_config["api_key"])
            db_agent.llm_config = updated_llm_config
        if request.tools_config is not None:
            db_agent.tools_config = request.tools_config
        if request.observability_config is not None:
            db_agent.observability_config = request.observability_config
        if request.suggestion_prompts is not None:
            # SECURITY: Sanitize suggestion_prompts to prevent stored XSS
            from src.services.security.input_sanitizer import sanitize_suggestion_prompts

            db_agent.suggestion_prompts = sanitize_suggestion_prompts(request.suggestion_prompts)
        if request.status is not None:
            db_agent.status = request.status
        if request.is_public is not None:
            db_agent.is_public = request.is_public
        if request.category is not None:
            db_agent.category = request.category
        if request.tags is not None:
            db_agent.tags = request.tags
        if request.voice_enabled is not None:
            db_agent.voice_enabled = request.voice_enabled
        if request.voice_config is not None:
            db_agent.voice_config = request.voice_config
        if request.agent_metadata is not None:
            db_agent.agent_metadata = request.agent_metadata
            flag_modified(db_agent, "agent_metadata")
        # Note: is_adk_workflow_enabled is derived from workflow_type presence, not stored separately
        if request.workflow_type is not None:
            db_agent.workflow_type = request.workflow_type
        if request.workflow_config is not None:
            db_agent.workflow_config = request.workflow_config
        # Role-based agent fields
        if request.role_id is not None:
            db_agent.role_id = uuid.UUID(request.role_id) if request.role_id else None
        if request.human_contact_id is not None:
            db_agent.human_contact_id = uuid.UUID(request.human_contact_id) if request.human_contact_id else None
        if request.routing_mode is not None:
            valid_modes = {"fixed", "round_robin", "cost_opt", "intent", "latency_opt"}
            if request.routing_mode not in valid_modes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid routing_mode '{request.routing_mode}'. Valid values: {sorted(valid_modes)}",
                )
            db_agent.routing_mode = request.routing_mode
        if request.routing_config is not None:
            db_agent.routing_config = request.routing_config
        if request.execution_backend is not None:
            valid_backends = {"celery", "lambda", "cloud_run", "do_functions"}
            if request.execution_backend not in valid_backends:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid execution_backend '{request.execution_backend}'. Valid values: {sorted(valid_backends)}",
                )
            if request.execution_backend != "celery":
                from src.services.billing import PlanRestrictionError, PlanRestrictionService

                _restriction_service = PlanRestrictionService(db)
                try:
                    await _restriction_service.enforce_feature_access(
                        tenant_id, "serverless_execution", "Serverless execution (Cloud Run / Lambda)"
                    )
                except PlanRestrictionError as exc:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
            db_agent.execution_backend = request.execution_backend
        if request.allow_transfer is not None:
            db_agent.allow_transfer = request.allow_transfer
        if request.transfer_scope is not None:
            valid_scopes = {"sub_agents", "siblings", "parent", "any"}
            if request.transfer_scope not in valid_scopes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid transfer_scope '{request.transfer_scope}'. Valid values: {sorted(valid_scopes)}",
                )
            db_agent.transfer_scope = request.transfer_scope

        # Slug is immutable once set — silently ignore any slug in the update payload.

        await db.commit()
        await db.refresh(db_agent)

        # Phase 3b: Snapshot the saved state as a new version
        try:
            from src.services.agents.agent_version_service import create_version

            await create_version(
                db,
                db_agent,
                account_id=current_account.id,
                change_description=request.change_description,
            )
            await db.commit()
        except Exception as version_err:
            # Version creation must not fail the update itself
            logger.warning(f"Failed to create agent version snapshot: {version_err}")

        # Phase 4: Invalidate cache after update
        cache = get_agent_cache()
        await cache.invalidate_agent(slug=db_agent.slug, agent_id=str(db_agent.id), tenant_id=str(tenant_id))
        await cache.invalidate_agents_list(str(tenant_id))  # PERFORMANCE: Also invalidate list cache
        logger.info(f"🗑️  Invalidated cache for agent '{old_agent_name}'")

        # Evict stale agent from memory so the next request reloads it properly
        # via agent_loader_service._resolve_llm_config, which queries AgentLLMConfig
        # and decrypts the API key correctly.  Do NOT recreate here using the
        # inline db_agent.llm_config field — that field may be stale or its api_key
        # still encrypted, which would break the in-memory LLM client.
        if agent_manager.registry.contains(old_agent_name, str(tenant_id)):
            try:
                await agent_manager.delete_agent(old_agent_name, str(tenant_id))
                logger.info(f"Evicted agent '{old_agent_name}' from memory; will reload on next request")
            except Exception as e:
                logger.error(f"Failed to evict agent from memory: {e}")

        return AgentResponse(
            success=True,
            message=f"Agent '{agent_slug}' updated successfully",
            data={
                "agent_name": db_agent.agent_name,
                "slug": db_agent.slug,
                "updated_at": db_agent.updated_at.isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update agent: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update agent")


@agents_index_router.delete("/{agent_slug}", response_model=AgentResponse)
async def delete_agent(
    agent_slug: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    current_account=Depends(get_current_account),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(require_role(AccountRole.ADMIN)),
):
    """
    Delete an agent.

    Args:
        agent_name: Name of the agent to delete
        db: Database session

    Returns:
        Deletion confirmation
    """
    try:
        deleted_from_memory = False
        deleted_from_db = False

        # Try to find agent first to get its agent_name for memory operations
        result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
        db_agent = result.scalar_one_or_none()

        # Try to delete from memory (may not be loaded)
        if db_agent:
            try:
                await agent_manager.delete_agent(db_agent.agent_name, str(tenant_id))
                deleted_from_memory = True
            except KeyError:
                # Agent not in memory, continue to try deleting from database
                pass

        if db_agent:
            await db.delete(db_agent)
            await db.commit()
            deleted_from_db = True

        # If agent wasn't found anywhere, return 404
        if not deleted_from_memory and not deleted_from_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")

        # PERFORMANCE: Invalidate agents list cache for this tenant
        cache = get_agent_cache()
        await cache.invalidate_agents_list(str(tenant_id))

        # Audit: log agent deletion (best-effort)
        try:
            from src.services.activity.activity_log_service import ActivityLogService

            _log_svc = ActivityLogService(db)
            await _log_svc.log_activity(
                tenant_id=tenant_id,
                account_id=current_account.id,
                action="agent.deleted",
                resource_type="agent",
                resource_id=db_agent.id if db_agent else None,
                details={"agent_name": db_agent.agent_name if db_agent else agent_slug},
            )
        except Exception:
            pass

        return AgentResponse(success=True, message=f"Agent '{agent_slug}' deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete agent: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete agent")


@agents_index_router.post("/{agent_slug}/reset", response_model=AgentResponse)
async def reset_agent(
    agent_slug: str,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Reset an agent's state.

    Args:
        agent_name: Name of the agent to reset
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Reset confirmation
    """
    try:
        # SECURITY: Verify agent belongs to tenant before resetting (no public agent reset)
        result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
        db_agent = result.scalar_one_or_none()

        if not db_agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")

        # Try to reset in memory (agent may not be loaded)
        try:
            await agent_manager.reset_agent(db_agent.agent_name, str(tenant_id))
        except KeyError:
            # Agent not in memory, but exists in DB - nothing to reset in memory
            pass

        return AgentResponse(success=True, message=f"Agent '{agent_slug}' reset successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset agent: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reset agent")


@agents_index_router.post("/reset-all", response_model=AgentResponse)
async def reset_all_agents(
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Reset all agents belonging to the current tenant.

    Args:
        tenant_id: Tenant ID from JWT token
        db: Database session

    Returns:
        Reset confirmation
    """
    try:
        # SECURITY: Only reset agents belonging to current tenant
        result = await db.execute(select(Agent.agent_name).filter(Agent.tenant_id == tenant_id))
        tenant_agents = result.all()
        tenant_agent_names = [a[0] for a in tenant_agents]

        reset_count = 0
        for agent_name in tenant_agent_names:
            try:
                await agent_manager.reset_agent(agent_name, str(tenant_id))
                reset_count += 1
            except KeyError:
                # Agent not in memory, skip
                pass

        return AgentResponse(success=True, message=f"Reset {reset_count} agents successfully")

    except Exception as e:
        logger.error(f"Failed to reset all agents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset agents",
        )


@agents_index_router.post("/{agent_slug}/clone", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def clone_agent(
    agent_slug: str,
    request: CloneAgentRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Clone an existing agent with configurable options.

    Args:
        agent_name: Name of the agent to clone
        request: Clone configuration request
        tenant_id: Current tenant ID
        db: Database session

    Returns:
        Clone success response with warnings about OAuth integrations
    """
    try:
        # Check agent creation limit
        from src.models.agent_knowledge_base import AgentKnowledgeBase
        from src.models.agent_llm_config import AgentLLMConfig
        from src.models.agent_sub_agent import AgentSubAgent
        from src.services.billing import PlanRestrictionError, PlanRestrictionService

        restriction_service = PlanRestrictionService(db)
        try:
            await restriction_service.enforce_agent_limit(tenant_id)
        except PlanRestrictionError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        # Get source agent
        result = await db.execute(select(Agent).filter(Agent.slug == agent_slug, Agent.tenant_id == tenant_id))
        source_agent = result.scalar_one_or_none()

        if not source_agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent '{agent_slug}' not found")

        # Check if new name already exists
        existing_result = await db.execute(
            select(Agent).filter(Agent.agent_name == request.new_name, Agent.tenant_id == tenant_id)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=f"Agent '{request.new_name}' already exists"
            )

        # Clone the agent with same settings
        cloned_agent = Agent(
            tenant_id=tenant_id,
            agent_name=request.new_name,
            agent_type=source_agent.agent_type,
            description=source_agent.description,
            avatar=source_agent.avatar,
            system_prompt=source_agent.system_prompt,
            llm_config=source_agent.llm_config.copy() if source_agent.llm_config else {},
            tools_config=source_agent.tools_config.copy()
            if (source_agent.tools_config and request.clone_tools)
            else None,
            agent_metadata=source_agent.agent_metadata.copy() if source_agent.agent_metadata else {},
            observability_config=source_agent.observability_config.copy()
            if source_agent.observability_config
            else None,
            suggestion_prompts=source_agent.suggestion_prompts.copy() if source_agent.suggestion_prompts else [],
            voice_enabled=source_agent.voice_enabled,
            voice_config=source_agent.voice_config.copy() if source_agent.voice_config else None,
            is_public=False,
            category=source_agent.category,
            tags=source_agent.tags.copy() if source_agent.tags else [],
            workflow_type=source_agent.workflow_type if request.clone_workflows else None,
            workflow_config=source_agent.workflow_config.copy()
            if (source_agent.workflow_config and request.clone_workflows)
            else None,
            status="ACTIVE",
            execution_count=0,
            success_count=0,
            likes_count=0,
            dislikes_count=0,
            usage_count=0,
        )

        # Update API key in legacy llm_config if provided (encrypt it first)
        if request.new_api_key:
            from src.services.agents.security import encrypt_value

            if cloned_agent.llm_config:
                cloned_agent.llm_config["api_key"] = encrypt_value(request.new_api_key)

        import re as _re2

        _clone_base_slug = _re2.sub(r"[^a-z0-9-]", "-", request.new_name.lower())
        _clone_base_slug = _re2.sub(r"-+", "-", _clone_base_slug).strip("-") or "agent"
        cloned_agent.slug = _clone_base_slug

        db.add(cloned_agent)
        await db.flush()  # Get ID for relationships

        warnings = []

        # Clone knowledge base relationships if requested
        if request.clone_knowledge_bases:
            kb_result = await db.execute(
                select(AgentKnowledgeBase).filter(AgentKnowledgeBase.agent_id == source_agent.id)
            )
            source_kb_relations = kb_result.scalars().all()

            for kb_rel in source_kb_relations:
                new_kb_rel = AgentKnowledgeBase(
                    agent_id=cloned_agent.id,
                    knowledge_base_id=kb_rel.knowledge_base_id,
                    retrieval_config=kb_rel.retrieval_config.copy() if kb_rel.retrieval_config else None,
                )
                db.add(new_kb_rel)

            if source_kb_relations:
                warnings.append(
                    f"Cloned {len(source_kb_relations)} knowledge base link(s). Note: OAuth-based data sources will require re-authorization."
                )

        # Clone sub-agent relationships if requested
        if request.clone_sub_agents:
            sub_agents_result = await db.execute(
                select(AgentSubAgent).filter(AgentSubAgent.parent_agent_id == source_agent.id)
            )
            source_sub_agents = sub_agents_result.scalars().all()

            for sub_rel in source_sub_agents:
                new_sub_rel = AgentSubAgent(
                    parent_agent_id=cloned_agent.id,
                    sub_agent_id=sub_rel.sub_agent_id,
                    config=sub_rel.config.copy() if sub_rel.config else None,
                )
                db.add(new_sub_rel)

            if source_sub_agents:
                warnings.append(f"Cloned {len(source_sub_agents)} sub-agent relationship(s).")

        # Clone LLM configs from separate table
        llm_configs_result = await db.execute(select(AgentLLMConfig).filter(AgentLLMConfig.agent_id == source_agent.id))
        source_llm_configs = llm_configs_result.scalars().all()

        if source_llm_configs:
            for llm_config in source_llm_configs:
                # If new_api_key is provided and this is the default config, use it and enable the config
                if request.new_api_key and llm_config.is_default:
                    cloned_api_key = encrypt_value(request.new_api_key)
                    cloned_enabled = True
                else:
                    cloned_api_key = ""
                    cloned_enabled = False

                cloned_llm_config = AgentLLMConfig(
                    tenant_id=tenant_id,
                    agent_id=cloned_agent.id,
                    name=llm_config.name,
                    provider=llm_config.provider,
                    model_name=llm_config.model_name,
                    api_key=cloned_api_key,
                    api_base=llm_config.api_base,
                    temperature=llm_config.temperature,
                    max_tokens=llm_config.max_tokens,
                    top_p=llm_config.top_p,
                    additional_params=llm_config.additional_params.copy() if llm_config.additional_params else None,
                    is_default=llm_config.is_default,
                    display_order=llm_config.display_order,
                    enabled=cloned_enabled,
                )
                db.add(cloned_llm_config)

            # Only warn about API keys if new_api_key wasn't provided
            if not request.new_api_key:
                warnings.append(
                    f"Cloned {len(source_llm_configs)} LLM configuration(s) without API keys. Please configure API keys for each LLM config."
                )
            elif len(source_llm_configs) > 1:
                warnings.append(
                    f"Cloned {len(source_llm_configs)} LLM configuration(s). The default config was enabled with the provided API key. Other configs need API keys configured."
                )

        await db.commit()
        await db.refresh(cloned_agent)

        logger.info(
            f"Cloned agent '{agent_slug}' to '{request.new_name}' (tools={request.clone_tools}, kb={request.clone_knowledge_bases}, sub_agents={request.clone_sub_agents}, workflows={request.clone_workflows})"
        )

        # PERFORMANCE: Invalidate agents list cache for this tenant
        cache = get_agent_cache()
        await cache.invalidate_agents_list(str(tenant_id))

        # Include LLM config details in response so user knows what API key is needed
        llm_config_info = []
        for llm_config in source_llm_configs:
            llm_config_info.append(
                {
                    "name": llm_config.name,
                    "provider": llm_config.provider,
                    "model_name": llm_config.model_name,
                    "is_default": llm_config.is_default,
                    "enabled": llm_config.is_default and bool(request.new_api_key),
                }
            )

        return AgentResponse(
            success=True,
            message=f"Agent cloned successfully as '{request.new_name}'",
            data={
                "agent_id": str(cloned_agent.id),
                "agent_name": cloned_agent.agent_name,
                "slug": cloned_agent.slug,
                "source_agent": agent_slug,
                "llm_configs": llm_config_info if llm_config_info else None,
                "warnings": warnings if warnings else None,
                "requires_configuration": not request.new_api_key,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to clone agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to clone agent: {str(e)}"
        )
