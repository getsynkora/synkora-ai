import logging
import re
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_async_session_factory
from src.helpers.chat_helpers import (
    calculate_time_metrics,
    estimate_tokens,
    format_attachment_context,
    validate_conversation_id,
)
from src.helpers.streaming_helpers import (
    extract_user_friendly_error,
    generate_chunk_event,
    generate_done_event,
    generate_error_event,
    generate_first_token_event,
    generate_sse_event,
    generate_start_event,
    generate_status_event,
    generate_tool_status_event,
    is_expected_llm_error,
)
from src.services.agents.adk_tools import ADKToolRegistry, get_tool_registry
from src.services.agents.agent_loader_service import AgentLoaderService
from src.services.agents.chat_service import ChatService
from src.services.agents.context_manager import ContextConfig, ContextManager, ContextStrategy
from src.services.agents.context_window_guard import get_context_guard
from src.services.agents.token_counter import TokenCounter
from src.services.cache.conversation_cache_service import get_conversation_cache
from src.services.security.output_sanitizer import output_sanitizer as default_output_sanitizer

logger = logging.getLogger(__name__)


@dataclass
class StreamState:
    assistant_chunks: list[str]
    chart_data: list[dict[str, Any]]
    diagram_data: list[dict[str, Any]] = None
    infographic_data: list[dict[str, Any]] = None
    generated_images_data: list[dict[str, Any]] = None
    forms_data: list[dict[str, Any]] = None
    fleet_card_data: list[dict[str, Any]] = None
    total_output_tokens: int = 0
    first_token_time: float | None = None
    tool_start_times: dict[str, float] = None  # Track tool execution start times

    def __post_init__(self):
        if self.diagram_data is None:
            self.diagram_data = []
        if self.infographic_data is None:
            self.infographic_data = []
        if self.generated_images_data is None:
            self.generated_images_data = []
        if self.forms_data is None:
            self.forms_data = []
        if self.fleet_card_data is None:
            self.fleet_card_data = []
        if self.tool_start_times is None:
            self.tool_start_times = {}


class ChatStreamService:
    """Orchestrates chat streaming for agents."""

    def __init__(
        self,
        agent_loader: AgentLoaderService,
        chat_service: ChatService,
        tool_registry: ADKToolRegistry | None = None,
        output_sanitizer=default_output_sanitizer,
    ) -> None:
        self.agent_loader = agent_loader
        self.chat_service = chat_service
        self.tool_registry = tool_registry or get_tool_registry()
        self.output_sanitizer = output_sanitizer

    async def stream_agent_response(
        self,
        agent_name: str,
        message: str,
        conversation_history: list[dict[str, str]] | None,
        conversation_id: str | None,
        attachments: list[dict[str, Any]] | None,
        llm_config_id: str | None,
        db: AsyncSession | None = None,
        user_id: str | None = None,
        trigger_source: str = "chat",
        trigger_detail: str | None = None,
        tenant_id: Any | None = None,
        shared_state: dict[str, Any] | None = None,
        override_agentic_config: dict[str, Any] | None = None,
        override_system_prompt: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream agent response using SSE with function calling, RAG support, and attachments.

        Args:
            user_id: Optional synkora account ID for user-level OAuth token resolution
            tenant_id: Tenant ID for verifying conversation ownership (SECURITY)
            shared_state: Optional shared state for tools (e.g., scheduled task config)
        """
        user_message_saved = None
        db_agent = None
        retrieved_sources: list[dict[str, Any]] = []
        state = StreamState(assistant_chunks=[], chart_data=[])
        conversation_uuid = validate_conversation_id(conversation_id)
        managed_db_session = db is None
        session_factory = get_async_session_factory() if managed_db_session else None
        if managed_db_session:
            db = session_factory()
        _execution_id = None

        async def _track(event_data: dict) -> None:
            if _execution_id:
                try:
                    from src.services.agents.execution_registry import execution_registry

                    await execution_registry.append_event(_execution_id, event_data)
                except Exception:
                    pass

        try:
            # SECURITY: Verify conversation access before saving messages
            if conversation_uuid:
                from uuid import UUID as UUIDType

                from sqlalchemy import or_

                from src.models.agent import Agent
                from src.models.conversation import Conversation

                result = await db.execute(select(Conversation).filter(Conversation.id == conversation_uuid))
                conversation = result.scalar_one_or_none()
                if conversation:
                    # Check 1: Verify user owns this conversation (user-level isolation)
                    # SECURITY: If conversation has account_id, we MUST validate user ownership
                    if conversation.account_id:
                        if not user_id:
                            logger.warning(
                                f"SECURITY: Attempt to access user-owned conversation {conversation_uuid} without user_id"
                            )
                            yield await generate_error_event("Conversation not found or access denied")
                            return
                        try:
                            user_uuid = UUIDType(user_id) if isinstance(user_id, str) else user_id
                            if conversation.account_id != user_uuid:
                                logger.warning(
                                    f"SECURITY: User {user_id} attempted to access conversation {conversation_uuid} belonging to another user"
                                )
                                yield await generate_error_event("Conversation not found or access denied")
                                return
                        except (ValueError, TypeError) as e:
                            logger.warning(
                                f"SECURITY: Invalid user_id format '{user_id}' when accessing conversation {conversation_uuid}: {e}"
                            )
                            yield await generate_error_event("Conversation not found or access denied")
                            return

                    # Check 2: Verify agent access (tenant-level isolation OR public agent OR platform agent)
                    if conversation.agent_id and tenant_id:
                        agent_result = await db.execute(
                            select(Agent).filter(
                                Agent.id == conversation.agent_id,
                                or_(
                                    Agent.tenant_id == tenant_id,
                                    Agent.is_public.is_(True),
                                    Agent.agent_metadata["is_platform_agent"].as_boolean().is_(True),
                                ),
                            )
                        )
                        agent_check = agent_result.scalar_one_or_none()

                        if not agent_check:
                            logger.warning(
                                f"SECURITY: Tenant {tenant_id} attempted to access conversation for agent they don't own and is not public"
                            )
                            yield await generate_error_event("Conversation not found or access denied")
                            return

            # Load conversation history from cache/DB when a conversation_id is present.
            # This is the authoritative source — do not rely on the frontend to send it back.
            # Loaded BEFORE saving the current user message so it only contains prior turns.
            if conversation_uuid:
                from src.services.conversation_service import ConversationService

                try:
                    loaded_history = await ConversationService.get_conversation_history_cached(
                        db=db,
                        conversation_id=conversation_uuid,
                        limit=50,
                    )
                    if loaded_history:
                        conversation_history = loaded_history
                        logger.info(
                            f"📜 Loaded {len(loaded_history)} messages from cache/DB for conversation {conversation_uuid}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to load conversation history from cache/DB: {e}")

            if conversation_uuid:
                user_message_saved = await self.chat_service.save_user_message(
                    conversation_id=conversation_uuid,
                    message=message,
                    db=db,
                    attachments=attachments,
                )

            load_result = await self.agent_loader.load_agent(
                agent_name=agent_name,
                db=db,
                llm_config_id=llm_config_id,
                query=message,
                conversation_history=conversation_history,
                tenant_id=str(tenant_id) if tenant_id else "",
            )

            if load_result.error:
                yield await generate_error_event(load_result.error)
                return

            db_agent = load_result.db_agent
            agent = load_result.agent
            is_workflow_agent = load_result.is_workflow

            logger.info(
                f"✅ Agent loaded: {agent_name}, cache_hit={load_result.cache_hit}, "
                f"time={load_result.loading_time:.3f}s, is_workflow={is_workflow_agent}"
            )

            # Agent trace: fire user_message event
            if conversation_uuid and db_agent and tenant_id:
                try:
                    from src.services.agents.agent_trace_service import fire_user_message

                    _conv_name = getattr(conversation, "name", agent_name) if "conversation" in dir() else agent_name
                    _conv_status = getattr(conversation, "status", "ACTIVE") if "conversation" in dir() else "ACTIVE"
                    fire_user_message(
                        tenant_id=tenant_id,
                        agent_id=db_agent.id,
                        conversation_id=conversation_uuid,
                        message_id=None,
                        content=message,
                        conversation_name=str(_conv_name),
                        conversation_status=str(_conv_status),
                        sequence=1,
                    )
                except Exception:
                    pass  # never block chat

            # Register execution for Live Lab observability (done early so _track is
            # available to all code paths including workflow and claude_code branches)
            if tenant_id and db_agent:
                try:
                    from src.services.agents.execution_registry import execution_registry

                    _execution_id = await execution_registry.register(
                        tenant_id=tenant_id,
                        agent_id=db_agent.id,
                        agent_name=agent_name,
                        trigger_source=trigger_source,
                        trigger_detail=trigger_detail,
                        conversation_id=conversation_id,
                        message_preview=message,
                    )
                except Exception as reg_err:
                    logger.debug(f"Failed to register execution: {reg_err}")

            if is_workflow_agent:
                async for event in self._stream_workflow_agent(
                    agent_name=agent_name,
                    message=message,
                    conversation_id=conversation_id,
                    conversation_uuid=conversation_uuid,
                    db_agent=db_agent,
                    db=db,
                    state=state,
                    track=_track,
                ):
                    yield event
                return

            # Check if this is a Claude Code Agent (uses Claude Agent SDK)
            is_claude_code = db_agent.agent_type and db_agent.agent_type.lower() == "claude_code"

            if is_claude_code:
                async for event in self._stream_claude_code_agent(
                    agent_name=agent_name,
                    message=message,
                    conversation_id=conversation_id,
                    conversation_uuid=conversation_uuid,
                    db_agent=db_agent,
                    agent=agent,
                    db=db,
                    state=state,
                    user_id=user_id,
                    track=_track,
                ):
                    yield event
                return

            if not agent or not agent.llm_client:
                error_msg = f"Agent '{agent_name}' LLM client not initialized properly"
                logger.warning(f"❌ {error_msg}")
                yield await generate_error_event(error_msg)
                return

            start_time = time.time()
            yield await generate_start_event(agent_name, start_time)

            # Store the start event
            await _track({"type": "start", "agent": agent_name})

            attachment_context = ""
            if attachments:
                yield await generate_status_event(f"📎 Processing {len(attachments)} attachment(s)...")
                attachment_context = format_attachment_context(attachments)

            agent_kbs, agent_tools, mcp_tool_names = await self._load_agent_resources(db_agent, db)

            # Detect URLs in user message and queue background Celery crawl tasks (non-blocking).
            # Reuses already-loaded agent_kbs so no extra DB query is needed.
            url_notice = await self._queue_url_crawl_tasks(message, db_agent, agent_kbs)
            if url_notice:
                attachment_context = (attachment_context + "\n\n" + url_notice).strip()
            perf_config = (db_agent.agent_metadata or {}).get("performance_config") or {}
            rag_config = (
                perf_config.get("rag", {"enabled": True}) if isinstance(perf_config, dict) else {"enabled": True}
            )

            should_perform_rag = (
                agent_kbs
                and rag_config.get("enabled", True)
                and len(message.strip()) >= rag_config.get("min_query_length", 10)
            )
            if should_perform_rag:
                yield await generate_status_event("📚 Searching knowledge bases...")
                await _track({"type": "status", "content": "Searching knowledge bases..."})

            context_text, retrieved_sources = await self._retrieve_rag_context(
                message=message,
                db_agent=db_agent,
                agent_kbs=agent_kbs,
                rag_config=rag_config,
                should_perform_rag=should_perform_rag,
            )

            system_prompt, structured_messages = await self._build_prompt(
                db=db,
                db_agent=db_agent,
                conversation_history=conversation_history,
                attachment_context=attachment_context,
                context_text=context_text,
                message=message,
                perf_config=perf_config,
                conversation_id=conversation_id,
                llm_client=agent.llm_client if agent else None,
                override_system_prompt=override_system_prompt,
            )

            # Wire cost-tracking context into the LLM client.
            # Done after system_prompt is built so we can hash it for cache-key stability.
            if agent and agent.llm_client and tenant_id:
                try:
                    import hashlib as _hashlib

                    _selected_llm_cfg = getattr(load_result, "selected_llm_config", None)
                    _routing_rules = (
                        _selected_llm_cfg.routing_rules
                        if _selected_llm_cfg and hasattr(_selected_llm_cfg, "routing_rules")
                        else None
                    )
                    agent.llm_client.set_cost_context(
                        tenant_id=tenant_id,
                        agent_id=db_agent.id if db_agent else None,
                        conversation_id=conversation_uuid,
                        routing_rules=_routing_rules,
                        optimization_flags={},
                        enable_response_cache=bool(perf_config.get("enable_response_cache", False)),
                        system_prompt_hash=_hashlib.sha256((system_prompt or "").encode()).hexdigest()[:16],
                    )
                except Exception:
                    pass  # cost context is optional; never block the request

            # Use accurate token counting (count system prompt + all messages)
            model = agent.llm_client.config.model_name
            messages_content = " ".join([m.get("content", "") for m in structured_messages])
            total_input_tokens = TokenCounter.count_tokens(system_prompt + " " + messages_content, model)

            # Context window guard check
            context_guard = get_context_guard()
            guard_result = context_guard.evaluate(model, total_input_tokens)

            if guard_result.should_block:
                logger.warning(f"Context window exhausted for {agent_name}: {guard_result.message}")
                yield await generate_error_event(
                    f"Context limit reached: {guard_result.remaining_tokens} tokens remaining. "
                    "Please start a new conversation or clear history."
                )
                return

            if guard_result.should_warn:
                logger.info(f"Context window warning for {agent_name}: {guard_result.message}")
                # Emit warning as status event (non-blocking)
                yield await generate_status_event(f"Context usage: {guard_result.remaining_percentage:.0%} remaining")

            # Register platform tools BEFORE _select_tools so their names are included
            platform_tool_names = self.tool_registry.register_platform_tools_for_agent(db_agent)
            if platform_tool_names:
                mcp_tool_names = list(set((mcp_tool_names or []) + platform_tool_names))

            final_tool_names, all_configured_tool_names = self._select_tools(
                agent, agent_tools, message, mcp_tool_names
            )

            trace_id = self._create_trace(agent, agent_name, message, final_tool_names)

            if managed_db_session and db is not None:
                await db.close()
                db = None

            # --- Fallback chain -----------------------------------------------
            # Two triggers for switching to a fallback LLM config:
            #   1. Pre-flight: primary provider's circuit breaker is already OPEN.
            #   2. Mid-stream: primary raises LLMProviderError (rate-limit, 500,
            #      auth failure, etc.) before any content has been yielded so the
            #      response can be retried cleanly.
            #
            # When a fallback is used the full stream is replayed from scratch
            # against the next config — this is only safe when no chunks have been
            # sent yet.  Once at least one chunk has been yielded we break out
            # and let the partial response stand rather than confuse the client.
            # -----------------------------------------------------------------
            from src.services.agents.llm_client import LLMProviderError
            from src.services.performance.circuit_breaker import CircuitState, get_circuit_breaker

            _active_agent = agent
            _all_config_ids = [None] + list(load_result.fallback_config_ids)  # None = already-loaded primary

            for _attempt, _candidate_config_id in enumerate(_all_config_ids):
                if _attempt > 0:
                    # Load the next fallback config.
                    logger.warning(
                        f"[fallback] Provider '{_active_agent.llm_client.provider if _active_agent and _active_agent.llm_client else 'unknown'}' "
                        f"failed, switching to fallback config '{_candidate_config_id}' "
                        f"for agent '{agent_name}' (attempt {_attempt + 1}/{len(_all_config_ids)})"
                    )
                    if managed_db_session:
                        async with session_factory() as fallback_db:
                            fallback_result = await self.agent_loader.load_agent(
                                agent_name=agent_name,
                                db=fallback_db,
                                llm_config_id=_candidate_config_id,
                                tenant_id=str(tenant_id) if tenant_id else "",
                            )
                    else:
                        fallback_result = await self.agent_loader.load_agent(
                            agent_name=agent_name,
                            db=db,
                            llm_config_id=_candidate_config_id,
                            tenant_id=str(tenant_id) if tenant_id else "",
                        )
                    if fallback_result.error or not fallback_result.agent:
                        logger.warning(f"[fallback] Fallback load failed: {fallback_result.error}")
                        continue
                    _active_agent = fallback_result.agent
                else:
                    # First attempt: also do the legacy pre-flight circuit check so
                    # we don't even start if the circuit is already open.
                    if _active_agent and _active_agent.llm_client:
                        cb_name = f"llm_{_active_agent.llm_client.provider}"
                        cb = get_circuit_breaker(name=cb_name, failure_threshold=5, recovery_timeout=60)
                        if cb.state == CircuitState.OPEN and load_result.fallback_config_ids:
                            logger.warning(
                                f"[fallback] Primary model circuit open for '{_active_agent.llm_client.provider}', "
                                f"will attempt fallback configs for agent '{agent_name}'"
                            )
                            continue  # skip straight to first fallback
                    _active_agent = agent

                # Attempt to stream with current config.  Wrap in try/except so
                # that LLMProviderError before any content is yielded triggers the
                # next fallback rather than surfacing an error to the user.
                _chunks_yielded_this_attempt = 0
                try:
                    if final_tool_names:
                        async for event in self._stream_with_tools(
                            agent=_active_agent,
                            db_agent=db_agent,
                            prompt=system_prompt,
                            messages=structured_messages,
                            tool_names=final_tool_names,
                            all_configured_tool_names=all_configured_tool_names,
                            trace_id=trace_id,
                            conversation_uuid=conversation_uuid,
                            user_message_id=user_message_saved.id if user_message_saved else None,
                            start_time=start_time,
                            state=state,
                            db=None if managed_db_session else db,
                            user_id=user_id,
                            shared_state=shared_state,
                            caller_tenant_id=tenant_id,
                            override_agentic_config=override_agentic_config,
                        ):
                            _chunks_yielded_this_attempt += 1
                            yield event
                    else:
                        async for event in self._stream_without_tools(
                            agent=_active_agent,
                            system_prompt=system_prompt,
                            messages=structured_messages,
                            start_time=start_time,
                            state=state,
                            agent_name=agent_name,
                        ):
                            _chunks_yielded_this_attempt += 1
                            yield event
                    break  # Successful stream — exit fallback loop

                except LLMProviderError as provider_err:
                    failed_provider = provider_err.provider
                    if _chunks_yielded_this_attempt > 0:
                        # Content already sent — cannot restart; surface the error.
                        logger.warning(
                            f"[fallback] Provider '{failed_provider}' failed after {_chunks_yielded_this_attempt} "
                            f"chunks; cannot retry cleanly, surfacing error."
                        )
                        raise
                    if _attempt < len(_all_config_ids) - 1:
                        logger.warning(
                            f"[fallback] Provider '{failed_provider}' failed before any content was yielded: "
                            f"{provider_err.original_error}. Trying next fallback config."
                        )
                        continue  # try next config
                    # No more fallbacks — re-raise so the outer handler surfaces the error.
                    logger.warning(
                        f"[fallback] All {len(_all_config_ids)} LLM configs exhausted for agent '{agent_name}'. "
                        f"Last error: {provider_err.original_error}"
                    )
                    raise

            end_time = time.time()
            timing_metrics = calculate_time_metrics(start_time, state.first_token_time, end_time)
            routed_model = (
                _active_agent.llm_client.config.model_name if _active_agent and _active_agent.llm_client else None
            )
            metadata = {
                **timing_metrics,
                "input_tokens": total_input_tokens,
                "output_tokens": state.total_output_tokens,
                "total_tokens": total_input_tokens + state.total_output_tokens,
                "routed_model": routed_model,
                "routing_mode": getattr(db_agent, "routing_mode", "fixed"),
                "conversation_id": str(conversation_uuid) if conversation_uuid else None,
            }
            yield await generate_done_event(sources=retrieved_sources, metadata=metadata)
            final_content = "".join(state.assistant_chunks) if hasattr(state, "assistant_chunks") else ""
            await _track({"type": "done", "content": final_content[:5000], "metadata": metadata})

            # Mark execution complete in Live Lab
            if _execution_id and tenant_id:
                try:
                    from src.services.agents.execution_registry import execution_registry

                    await execution_registry.update_status(
                        tenant_id=tenant_id,
                        execution_id=_execution_id,
                        status="complete",
                        total_tokens=total_input_tokens + state.total_output_tokens,
                    )
                except Exception as reg_err:
                    logger.debug(f"Failed to update execution status: {reg_err}")

            if trace_id:
                try:
                    agent.langfuse_service.flush()
                    logger.info(f"✅ Flushed Langfuse trace: {trace_id}")
                except Exception as e:
                    logger.error(f"Failed to flush Langfuse trace: {e}")

            if conversation_uuid and state.assistant_chunks:
                assistant_content = "".join(state.assistant_chunks)

                if state.chart_data:
                    logger.info(f"💾 Saving {len(state.chart_data)} charts to database metadata")
                if state.diagram_data:
                    logger.info(f"💾 Saving {len(state.diagram_data)} diagrams to database metadata")
                if state.infographic_data:
                    logger.info(f"💾 Saving {len(state.infographic_data)} infographics to database metadata")
                if state.fleet_card_data:
                    logger.info(f"💾 Saving {len(state.fleet_card_data)} fleet cards to database metadata")
                if state.forms_data:
                    logger.info(f"💾 Saving {len(state.forms_data)} forms to database metadata")

                post_db = session_factory() if managed_db_session else db
                try:
                    from src.services.agents.llm_client import _llm_reasoning_ctx

                    assistant_message = await self.chat_service.save_assistant_message(
                        conversation_id=conversation_uuid,
                        content=assistant_content,
                        sources=retrieved_sources,
                        charts=state.chart_data,
                        diagrams=state.diagram_data,
                        infographics=state.infographic_data,
                        generated_images=state.generated_images_data,
                        forms=state.forms_data,
                        fleet_cards=state.fleet_card_data,
                        timing=timing_metrics,
                        usage={
                            "input_tokens": total_input_tokens,
                            "output_tokens": state.total_output_tokens,
                            "total_tokens": total_input_tokens + state.total_output_tokens,
                        },
                        reasoning_content=_llm_reasoning_ctx.get(),
                        db=post_db,
                    )
                    _llm_reasoning_ctx.set(None)
                finally:
                    if managed_db_session and post_db is not None:
                        await post_db.close()

                try:
                    from src.services.agents.agent_trace_service import fire_assistant_message

                    fire_assistant_message(
                        tenant_id=tenant_id or db_agent.tenant_id,
                        agent_id=db_agent.id,
                        conversation_id=conversation_uuid,
                        message_id=assistant_message.id if assistant_message else None,
                        content_preview=assistant_content[:500],
                        total_input_tokens=total_input_tokens,
                        total_output_tokens=state.total_output_tokens,
                        total_cost_usd=0.0,
                        total_latency_ms=int(timing_metrics.get("total_time", 0) * 1000),
                        sequence=0,
                    )
                except Exception:
                    pass  # never block chat

                if assistant_message:
                    stats_db = session_factory() if managed_db_session else db
                    try:
                        await self.chat_service.update_agent_stats(
                            agent=db_agent,
                            success=True,
                            db=stats_db,
                        )
                    finally:
                        if managed_db_session and stats_db is not None:
                            await stats_db.close()
                    self.chat_service.queue_credit_deduction(
                        tenant_id=tenant_id or db_agent.tenant_id,
                        agent_id=db_agent.id,
                        conversation_id=conversation_uuid,
                        message_id=assistant_message.id,
                        agent_name=agent_name,
                        model=agent.llm_client.config.model_name,
                        content=assistant_content,
                    )

                    try:
                        from src.services.agent_output_service import AgentOutputService

                        output_db = session_factory() if managed_db_session else db
                        try:
                            await AgentOutputService(output_db).send_outputs(
                                agent_id=db_agent.id,
                                agent_response=assistant_content,
                                context={"agent_name": agent_name, "trigger_type": "chat"},
                                trigger_type="chat",
                            )
                        finally:
                            if managed_db_session and output_db is not None:
                                await output_db.close()
                    except Exception as _out_err:
                        logger.warning(f"Chat output delivery error: {_out_err}")

        except Exception as e:
            if is_expected_llm_error(e):
                logger.warning(f"Streaming error (expected): {e}")
            else:
                logger.error(f"Streaming error: {e}", exc_info=True)
            user_friendly_error = extract_user_friendly_error(e)
            error_event = await generate_error_event(user_friendly_error)
            logger.info(f"🚨 Yielding error event to client: {user_friendly_error}")
            yield error_event
            await _track({"type": "error", "error": user_friendly_error})

            # Mark execution as error in Live Lab
            if _execution_id and tenant_id:
                try:
                    from src.services.agents.execution_registry import execution_registry

                    await execution_registry.update_status(
                        tenant_id=tenant_id,
                        execution_id=_execution_id,
                        status="error",
                        error=user_friendly_error,
                    )
                except Exception:
                    pass

            failure_db = session_factory() if managed_db_session else db
            try:
                if user_message_saved and failure_db is not None:
                    await self.chat_service.mark_message_failed(
                        message=user_message_saved,
                        error=str(e),
                        db=failure_db,
                    )

                if db_agent and failure_db is not None:
                    await self.chat_service.update_agent_stats(
                        agent=db_agent,
                        success=False,
                        db=failure_db,
                    )
            finally:
                if managed_db_session and failure_db is not None:
                    await failure_db.close()
        finally:
            if managed_db_session and db is not None:
                await db.close()

    async def _stream_workflow_agent(
        self,
        agent_name: str,
        message: str,
        conversation_id: str | None,
        conversation_uuid,
        db_agent,
        db: AsyncSession | None,
        state: StreamState,
        track=None,
    ) -> AsyncGenerator[str, None]:
        import asyncio

        from src.models.agent_sub_agent import AgentSubAgent
        from src.services.agents.workflows import WorkflowFactory

        result = await db.execute(
            select(AgentSubAgent)
            .options(selectinload(AgentSubAgent.sub_agent))
            .filter(AgentSubAgent.parent_agent_id == db_agent.id)
            .order_by(AgentSubAgent.execution_order)
        )
        sub_agents = list(result.scalars().all())

        if not sub_agents:
            error_msg = f"Workflow agent '{agent_name}' has no sub-agents configured"
            logger.warning(error_msg)
            yield await generate_error_event(error_msg)
            return

        executor = WorkflowFactory.create_executor(db_agent, sub_agents)
        if not executor:
            error_msg = f"Failed to create workflow executor for agent '{agent_name}'"
            logger.warning(error_msg)
            yield await generate_error_event(error_msg)
            return

        workflow_start_time = time.time()
        yield await generate_start_event(
            agent_name,
            workflow_start_time,
            workflow_type=db_agent.workflow_type,
        )
        yield await generate_status_event(
            f"🔄 Starting {db_agent.workflow_type} workflow with {len(sub_agents)} agents..."
        )

        # Queue to collect streaming events from workflow execution
        # PERFORMANCE: Use bounded queue to prevent memory issues
        event_queue = asyncio.Queue(maxsize=1000)

        # Create callback to forward sub-agent events
        async def event_callback(event_type: str, data: dict[str, Any]):
            """Forward workflow events to the stream"""
            await event_queue.put({"type": event_type, "data": data})

        # Start workflow execution in background
        workflow_task = asyncio.create_task(
            executor.execute(
                initial_input=message,
                user_id=str(db_agent.tenant_id),
                conversation_id=conversation_id,
                db=db,
                event_callback=event_callback,
            )
        )

        # Stream events as they arrive
        workflow_result = None
        try:
            while True:
                # Wait for events with timeout
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    event_type = event["type"]
                    data = event["data"]

                    # Track first token timing (only emit once at workflow level)
                    if event_type == "first_token" and state.first_token_time is None:
                        state.first_token_time = time.time()
                        time_to_first_token = state.first_token_time - workflow_start_time
                        # Emit ONLY one first_token event with agent context (not duplicate)
                        yield await generate_sse_event(
                            "first_token",
                            {
                                "event_type": "first_token",
                                "agent_name": data.get("agent_name"),
                                "time_to_first_token": time_to_first_token,
                            },
                        )

                    # Stream content chunks from sub-agents in real-time
                    elif event_type == "chunk":
                        chunk_content = data.get("content", "")
                        if chunk_content:
                            # SECURITY: Sanitize workflow sub-agent output
                            sanitization_result = self.output_sanitizer.sanitize(
                                chunk_content,
                                context=f"workflow_{agent_name}_{data.get('agent_name', 'sub_agent')}",
                            )
                            sanitized_chunk = sanitization_result.sanitized_content

                            if sanitization_result.detections:
                                logger.warning(
                                    f"Sanitized {len(sanitization_result.detections)} sensitive items in workflow response. "
                                    f"Agent: {data.get('agent_name')}, Action: {sanitization_result.action_taken}"
                                )

                            state.assistant_chunks.append(sanitized_chunk)
                            state.total_output_tokens += len(sanitized_chunk) // 4
                            # Emit ONLY workflow event with agent context (not duplicate regular chunk)
                            yield await generate_sse_event(
                                "chunk",
                                {
                                    "event_type": "chunk",
                                    "agent_name": data.get("agent_name"),
                                    "content": sanitized_chunk,
                                },
                            )

                    # Only emit workflow events for sub-agent lifecycle events
                    elif event_type == "start":
                        # Sub-agent started
                        yield await generate_status_event(f"🤖 Starting: {data.get('agent_name', 'Unknown')}")
                        yield await generate_sse_event(
                            "workflow_event",
                            {
                                "event_type": "sub_agent_start",
                                "agent_name": data.get("agent_name"),
                                "sub_agent_id": data.get("sub_agent_id"),
                                "input_preview": data.get("input_preview", ""),
                            },
                        )
                        if track:
                            await track({"type": "status", "content": f"Starting: {data.get('agent_name', 'Unknown')}"})

                    elif event_type == "done":
                        # Sub-agent completed
                        yield await generate_status_event(f"✅ Completed: {data.get('agent_name', 'Unknown')}")
                        yield await generate_sse_event(
                            "workflow_event",
                            {
                                "event_type": "sub_agent_complete",
                                "agent_name": data.get("agent_name"),
                                "sub_agent_id": data.get("sub_agent_id"),
                                "output_preview": data.get("output_preview", ""),
                            },
                        )
                        if track:
                            await track(
                                {"type": "status", "content": f"Completed: {data.get('agent_name', 'Unknown')}"}
                            )

                    elif event_type == "error":
                        # Sub-agent error
                        yield await generate_status_event(
                            f"❌ Error in {data.get('agent_name', 'Unknown')}: {data.get('error', 'Unknown')}"
                        )
                        yield await generate_sse_event(
                            "workflow_event",
                            {
                                "event_type": "sub_agent_error",
                                "agent_name": data.get("agent_name"),
                                "sub_agent_id": data.get("sub_agent_id"),
                                "error": data.get("error", "Unknown"),
                            },
                        )

                    elif event_type == "status":
                        # Tool-related status events
                        yield await generate_status_event(data.get("content", ""))

                    # Don't duplicate other events - they're for internal workflow tracking only

                except TimeoutError:
                    # Check if workflow task is done
                    if workflow_task.done():
                        workflow_result = await workflow_task
                        break

            # Get final response from workflow result
            final_response = workflow_result["state"].get("final_response", "")
            if not final_response:
                for key in reversed(list(workflow_result["state"].keys())):
                    if key.endswith("_output") and workflow_result["state"][key]:
                        final_response = workflow_result["state"][key]
                        break

            # Only stream if we haven't already streamed content from sub-agents
            if final_response and not state.assistant_chunks:
                # SECURITY: Sanitize the final workflow response
                sanitization_result = self.output_sanitizer.sanitize(
                    final_response,
                    context=f"workflow_{agent_name}_final",
                )
                sanitized_response = sanitization_result.sanitized_content

                if sanitization_result.detections:
                    logger.warning(
                        f"Sanitized {len(sanitization_result.detections)} sensitive items in workflow final response. "
                        f"Agent: {agent_name}, Action: {sanitization_result.action_taken}"
                    )

                if state.first_token_time is None:
                    state.first_token_time = time.time()
                time_to_first_token = state.first_token_time - workflow_start_time
                yield await generate_first_token_event(time_to_first_token)

                chunk_size = 50
                for i in range(0, len(sanitized_response), chunk_size):
                    chunk = sanitized_response[i : i + chunk_size]
                    state.assistant_chunks.append(chunk)
                    state.total_output_tokens += len(chunk) // 4
                    yield await generate_chunk_event(chunk)
                    await asyncio.sleep(0.01)

            end_time = time.time()
            total_time = end_time - workflow_start_time

            # DON'T include content in done event - it was already streamed via chunks!
            # Only include metadata to avoid overwriting streamed content on frontend
            completion_data = {
                "workflow_metadata": {
                    "workflow_type": db_agent.workflow_type,
                    "total_agents": len(sub_agents),
                    "execution_log": workflow_result.get("execution_log", []),
                    "status": workflow_result.get("status", "completed"),
                },
                "metadata": {
                    "total_time": round(total_time, 2),
                    "time_to_first_token": round(state.first_token_time - workflow_start_time, 2)
                    if state.first_token_time
                    else None,
                    "output_tokens": state.total_output_tokens,
                },
            }
            sanitized_completion = self._sanitize_for_json(completion_data)
            yield await generate_done_event(**sanitized_completion)

            if conversation_uuid and state.assistant_chunks:
                assistant_content = "".join(state.assistant_chunks)
                sanitized_execution_log = self._sanitize_for_json(workflow_result.get("execution_log", []))
                sanitized_workflow_state = self._sanitize_for_json(workflow_result.get("state", {}))

                # Calculate timing and usage for workflow
                workflow_timing = {
                    "total_time": round(total_time, 2),
                    "time_to_first_token": round(state.first_token_time - workflow_start_time, 2)
                    if state.first_token_time
                    else None,
                }

                # Estimate input tokens for the initial message
                estimated_input_tokens = estimate_tokens(message)

                workflow_usage = {
                    "input_tokens": estimated_input_tokens,
                    "output_tokens": state.total_output_tokens,
                    "total_tokens": estimated_input_tokens + state.total_output_tokens,
                }

                await self.chat_service.save_assistant_message(
                    conversation_id=conversation_uuid,
                    content=assistant_content,
                    workflow_type=db_agent.workflow_type,
                    execution_log=sanitized_execution_log,
                    workflow_state=sanitized_workflow_state,
                    timing=workflow_timing,
                    usage=workflow_usage,
                    db=db,
                )

                try:
                    from src.services.agents.agent_trace_service import fire_assistant_message

                    fire_assistant_message(
                        tenant_id=tenant_id or db_agent.tenant_id,
                        agent_id=db_agent.id,
                        conversation_id=conversation_uuid,
                        message_id=None,
                        content_preview=assistant_content[:500],
                        total_input_tokens=workflow_usage.get("input_tokens", 0),
                        total_output_tokens=workflow_usage.get("output_tokens", 0),
                        total_cost_usd=0.0,
                        total_latency_ms=int(workflow_timing.get("total_time", 0) * 1000),
                        sequence=0,
                    )
                except Exception:
                    pass  # never block chat

                await self.chat_service.update_agent_stats(
                    agent=db_agent,
                    success=True,
                    db=db,
                )

                try:
                    from src.services.agent_output_service import AgentOutputService

                    await AgentOutputService(db).send_outputs(
                        agent_id=db_agent.id,
                        agent_response=assistant_content,
                        context={"agent_name": db_agent.agent_name, "trigger_type": "chat"},
                        trigger_type="chat",
                    )
                except Exception as _out_err:
                    logger.warning(f"Workflow chat output delivery error: {_out_err}")

        except Exception as workflow_error:
            if is_expected_llm_error(workflow_error):
                logger.warning(f"Workflow execution failed (expected): {workflow_error}")
            else:
                logger.error(f"Workflow execution failed: {workflow_error}", exc_info=True)
            user_friendly_error = extract_user_friendly_error(workflow_error)
            yield await generate_error_event(user_friendly_error)

    def _sanitize_for_json(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._sanitize_for_json(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._sanitize_for_json(item) for item in value]
        if isinstance(value, tuple):
            return [self._sanitize_for_json(item) for item in value]
        if hasattr(value, "hex") and value.__class__.__name__ == "UUID":
            return str(value)
        return value

    async def _stream_claude_code_agent(
        self,
        agent_name: str,
        message: str,
        conversation_id: str | None,
        conversation_uuid,
        db_agent,
        agent,
        db: AsyncSession | None,
        state: StreamState,
        user_id: str | None = None,
        track=None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream responses from a Claude Code Agent using Claude Agent SDK.

        This handles agents with agent_type='claude_code' that leverage Claude's
        native agentic capabilities for code-focused tasks.
        """
        from src.services.agents.implementations import ClaudeCodeAgent

        start_time = time.time()

        try:
            # Yield start event
            yield await generate_start_event(agent_name, start_time)
            yield await generate_status_event("🤖 Initializing Claude Code Agent...")

            # Check if agent is properly typed
            if not isinstance(agent, ClaudeCodeAgent):
                logger.warning(
                    f"Agent {agent_name} is type claude_code but not ClaudeCodeAgent instance. "
                    "This may happen on first load."
                )

            # Get workspace path from agent metadata if available
            workspace_path = None
            if db_agent.agent_metadata:
                workspace_path = db_agent.agent_metadata.get("workspace_path")

            # Use Claude Agent SDK's built-in tools for code-focused tasks
            # These are the native Claude Code tools available in the SDK
            sdk_builtin_tools = [
                # File operations
                "Read",
                "Write",
                "Edit",
                "Glob",
                "Grep",
                "NotebookEdit",
                # Command execution
                "Bash",
                # Web tools
                "WebFetch",
                "WebSearch",
                # Task management (for subagents and background tasks)
                "Task",
                "TaskOutput",
                "TaskStop",
                "TodoWrite",
                # User interaction
                "AskUserQuestion",
            ]

            # Get model from agent's LLM config if available
            agent_model = None
            if db_agent.llm_config and "model_name" in db_agent.llm_config:
                agent_model = db_agent.llm_config["model_name"]

            yield await generate_status_event("⚡ Running Claude Agent SDK...")

            logger.info(f"[Claude Code] Starting execute_stream for agent: {agent_name}")
            event_count = 0

            # Stream from Claude Code Agent using SDK's built-in tools
            async for event in agent.execute_stream(
                prompt=message,
                system_prompt=db_agent.system_prompt,
                workspace_path=workspace_path,
                allowed_tools=sdk_builtin_tools,
                model=agent_model,
            ):
                event_count += 1
                event_type = event.get("type")
                logger.info(f"[Claude Code] Event #{event_count}: {event_type}")

                if event_type == "first_token":
                    state.first_token_time = time.time()
                    yield await generate_first_token_event(
                        event.get("time_to_first_token", state.first_token_time - start_time)
                    )

                elif event_type == "text":
                    content = event.get("content", "")
                    if content:
                        # Sanitize output
                        sanitization_result = self.output_sanitizer.sanitize(
                            content,
                            context=f"claude_code_{agent_name}",
                        )
                        state.assistant_chunks.append(sanitization_result.sanitized_content)
                        state.total_output_tokens += len(sanitization_result.sanitized_content) // 4
                        yield await generate_chunk_event(sanitization_result.sanitized_content)

                elif event_type == "function_call":
                    _tool = event.get("name", "unknown")
                    yield await generate_tool_status_event(
                        tool_name=_tool,
                        status="started",
                        arguments=event.get("arguments"),
                    )
                    if track:
                        await track({"type": "tool_status", "tool_name": _tool, "status": "started"})

                elif event_type == "function_result":
                    _tool = event.get("name", "unknown")
                    yield await generate_tool_status_event(
                        tool_name=_tool,
                        status="completed",
                    )
                    if track:
                        await track({"type": "tool_status", "tool_name": _tool, "status": "completed"})

                elif event_type == "thinking_start":
                    # Extended thinking started - emit single status event
                    logger.info("Claude Code thinking started")
                    yield await generate_status_event("💭 Thinking...")

                elif event_type == "thinking_end":
                    # Extended thinking ended
                    logger.info("Claude Code thinking completed")

                elif event_type == "thinking":
                    # Legacy thinking content (deprecated, use thinking_start/end)
                    pass  # Ignore individual thinking chunks to avoid flooding

                elif event_type == "error":
                    logger.warning(f"Claude Code Agent error: {event.get('error')}")
                    yield await generate_error_event(event.get("error", "Unknown error"))
                    return

                elif event_type == "done":
                    # Extract metadata from done event
                    metadata = event.get("metadata", {})
                    yield await generate_done_event(
                        metadata={
                            "total_time": metadata.get("total_time"),
                            "time_to_first_token": metadata.get("time_to_first_token"),
                            "input_tokens": metadata.get("input_tokens", 0),
                            "output_tokens": metadata.get("output_tokens", 0),
                            "total_tokens": metadata.get("total_tokens", 0),
                            "cost_usd": metadata.get("cost_usd", 0.0),
                            "agent_type": "claude_code",
                        }
                    )

            logger.info(
                f"[Claude Code] Stream completed: {event_count} events, {len(state.assistant_chunks)} chunks collected"
            )

            # Save assistant message if we have content
            if conversation_uuid and state.assistant_chunks:
                assistant_content = "".join(state.assistant_chunks)
                timing_metrics = {
                    "total_time": time.time() - start_time,
                    "time_to_first_token": (state.first_token_time - start_time) if state.first_token_time else None,
                }
                await self.chat_service.save_assistant_message(
                    conversation_id=conversation_uuid,
                    content=assistant_content,
                    timing=timing_metrics,
                    usage={
                        "output_tokens": state.total_output_tokens,
                    },
                    db=db,
                )

                try:
                    from src.services.agents.agent_trace_service import fire_assistant_message

                    fire_assistant_message(
                        tenant_id=tenant_id or db_agent.tenant_id,
                        agent_id=db_agent.id,
                        conversation_id=conversation_uuid,
                        message_id=None,
                        content_preview=assistant_content[:500],
                        total_input_tokens=0,
                        total_output_tokens=state.total_output_tokens,
                        total_cost_usd=0.0,
                        total_latency_ms=int(timing_metrics.get("total_time", 0) * 1000),
                        sequence=0,
                    )
                except Exception:
                    pass  # never block chat

                await self.chat_service.update_agent_stats(
                    agent=db_agent,
                    success=True,
                    db=db,
                )

                try:
                    from src.services.agent_output_service import AgentOutputService

                    await AgentOutputService(db).send_outputs(
                        agent_id=db_agent.id,
                        agent_response=assistant_content,
                        context={"agent_name": db_agent.agent_name, "trigger_type": "chat"},
                        trigger_type="chat",
                    )
                except Exception as _out_err:
                    logger.warning(f"Claude agent chat output delivery error: {_out_err}")

        except ImportError as e:
            logger.warning(f"Claude Agent SDK not installed: {e}")
            yield await generate_error_event(
                "Claude Agent SDK is not installed. Install with: pip install claude-agent-sdk"
            )

        except Exception as e:
            if is_expected_llm_error(e):
                logger.warning(f"Claude Code Agent streaming failed (expected): {e}")
            else:
                logger.error(f"Claude Code Agent streaming failed: {e}", exc_info=True)
            user_friendly_error = extract_user_friendly_error(e)
            yield await generate_error_event(user_friendly_error)

            if db_agent:
                await self.chat_service.update_agent_stats(
                    agent=db_agent,
                    success=False,
                    db=db,
                )

    async def _queue_url_crawl_tasks(self, message: str, db_agent: Any, agent_kbs: list[Any]) -> str:
        """
        Detect URLs in the user message and queue background Celery crawl tasks.

        No HTTP requests are made here — this is purely fire-and-forget task queuing.
        If the agent has knowledge bases configured, each URL is queued into the first
        available KB using the existing crawl_and_process_kb Celery task.

        Returns a short notice string to inject into agent context so the agent can
        inform the user. Returns empty string if no URLs were found.
        """
        url_pattern = re.compile(r"https?://[^\s<>\"'{}|\\^`\[\]]+")
        urls = list(dict.fromkeys(url_pattern.findall(message)))  # deduplicate, preserve order
        if not urls:
            return ""

        # Only queue crawl if the agent has at least one KB to store into
        if not agent_kbs:
            # No KB configured — just surface the URLs so the agent can use web_fetch if needed
            url_list = "\n".join(f"- {u}" for u in urls)
            return f"[System: The user's message contains these URLs. Use internal_web_fetch to read them if needed.]\n{url_list}"

        target_akb = agent_kbs[0]  # AgentKnowledgeBase join-table object
        kb_id = target_akb.knowledge_base_id
        # knowledge_base relationship is eagerly loaded via selectinload in _load_agent_resources
        tenant_id = target_akb.knowledge_base.tenant_id if target_akb.knowledge_base else None

        if not kb_id:
            return ""

        try:
            from sqlalchemy import select

            # Get or create a WEB data source for this KB (sync DB lookup via existing session-factory)
            from src.core.database import get_async_session_factory
            from src.models.data_source import DataSource, DataSourceStatus, DataSourceType
            from src.tasks.kb_tasks import crawl_and_process_kb

            async with get_async_session_factory()() as db:
                result = await db.execute(
                    select(DataSource).filter(
                        DataSource.knowledge_base_id == kb_id,
                        DataSource.type == DataSourceType.WEB,
                    )
                )
                data_source = result.scalar_one_or_none()
                if not data_source:
                    data_source = DataSource(
                        tenant_id=tenant_id,
                        knowledge_base_id=kb_id,
                        name="Web Crawl",
                        type=DataSourceType.WEB,
                        status=DataSourceStatus.ACTIVE,
                    )
                    db.add(data_source)
                    await db.commit()
                    await db.refresh(data_source)
                ds_id = data_source.id

            queued = []
            for url in urls:
                try:
                    crawl_and_process_kb.delay(
                        data_source_id=ds_id,
                        tenant_id=str(tenant_id) if tenant_id else "",
                        url=url,
                        max_pages=50,  # crawl up to 50 pages per URL
                        include_subpages=True,  # follow same-domain links
                    )
                    queued.append(url)
                    logger.info(f"Queued background crawl: {url} → KB {kb_id}")
                except Exception as exc:
                    logger.warning(f"Failed to queue crawl for {url}: {exc}")

            if not queued:
                return ""

            url_list = "\n".join(f"- {u}" for u in queued)
            return (
                f"[System: The following URL(s) from the user's message have been queued for background "
                f"crawling into knowledge base (id={kb_id}). Content will be available for retrieval "
                f"once processing completes. Inform the user the crawl is underway.]\n{url_list}"
            )

        except Exception as exc:
            logger.warning(f"URL crawl task queuing failed: {exc}")
            return ""

    async def _load_agent_resources(self, db_agent, db: AsyncSession) -> tuple[list[Any], list[Any], list[str]]:
        """
        Load agent resources (knowledge bases, tools, MCP tools, custom tools).

        KB and tool queries are simple SELECTs with no side effects — they run
        sequentially on the caller's session to avoid acquiring extra pool
        connections on every request.

        MCP and custom-tool loading register tools into the global tool_registry
        as a side effect, so they still open dedicated sessions and run in parallel
        with each other (but after the cheap sequential queries above).
        """
        import asyncio

        from src.core.database import get_async_session_factory
        from src.models.agent_knowledge_base import AgentKnowledgeBase
        from src.models.agent_tool import AgentTool

        load_start = time.time()

        # ── Fast sequential queries on the existing session (no extra connections) ──
        try:
            kb_result = await db.execute(
                select(AgentKnowledgeBase)
                .options(selectinload(AgentKnowledgeBase.knowledge_base))
                .filter(
                    AgentKnowledgeBase.agent_id == db_agent.id,
                    AgentKnowledgeBase.is_active,
                )
            )
            agent_kbs = list(kb_result.scalars().all())
        except Exception as e:
            logger.error(f"Error loading knowledge bases: {e}")
            agent_kbs = []

        try:
            tool_result = await db.execute(
                select(AgentTool).filter(
                    AgentTool.agent_id == db_agent.id,
                    AgentTool.enabled,
                )
            )
            agent_tools = list(tool_result.scalars().all())
        except Exception as e:
            logger.error(f"Error loading agent tools: {e}")
            agent_tools = []

        # ── Parallel loading for side-effecting registrations (own sessions) ──
        session_factory = get_async_session_factory()

        async def load_mcp_tools():
            """Load MCP tools using its own session. Returns registered tool names."""
            async with session_factory() as session:
                return await self.tool_registry.load_agent_mcp_tools(
                    agent_id=str(db_agent.id),
                    db=session,
                )

        async def load_custom_tools():
            """Load custom tools using its own session."""
            async with session_factory() as session:
                await self.tool_registry.load_agent_custom_tools(
                    agent_id=str(db_agent.id),
                    db=session,
                )
            return True

        mcp_result, _ = cast(
            tuple[list[str] | Exception, bool | Exception],
            await asyncio.gather(
                load_mcp_tools(),
                load_custom_tools(),
                return_exceptions=True,
            ),
        )

        mcp_tool_names: list[str] = []
        if isinstance(mcp_result, Exception):
            logger.error(f"Error loading MCP tools: {mcp_result}")
        elif mcp_result:
            mcp_tool_names = mcp_result

        logger.info(f"⚡ Resource loading completed in {time.time() - load_start:.3f}s")
        return agent_kbs, agent_tools, mcp_tool_names

    async def _retrieve_rag_context(
        self,
        message: str,
        db_agent,
        agent_kbs: list[Any],
        rag_config: dict[str, Any],
        should_perform_rag: bool,
        llm_client: Any = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Retrieve context from knowledge bases using enhanced RAG.

        Features:
        - Query cleaning (removes platform metadata)
        - Hybrid search (vector + keyword)
        - Cross-encoder reranking
        - Result caching
        - Intelligent deduplication
        """
        from src.services.knowledge_base.enhanced_rag_service import (
            RAGConfig,
            RetrievalStrategy,
            get_enhanced_rag_service,
        )
        from src.services.performance.connection_pool import get_vector_db_pool

        retrieved_sources: list[dict[str, Any]] = []
        context_text = ""

        if not should_perform_rag:
            logger.info(
                f"⚡ Skipping RAG (config: enabled={rag_config.get('enabled', True)}, "
                f"has_kbs={bool(agent_kbs)}, query_len={len(message)})"
            )
            return context_text, retrieved_sources

        # Extract clean query for RAG (strip Slack/platform metadata)
        clean_query = message
        slack_context_pattern = r"\[Slack Context:.*?\]\s*"
        clean_query = re.sub(slack_context_pattern, "", clean_query, flags=re.DOTALL).strip()

        logger.info(f"✅ Performing Enhanced RAG search (query_len={len(clean_query)})")

        # Configure RAG based on agent settings
        rag_strategy = rag_config.get("strategy", "hybrid_rerank")
        strategy_map = {
            "vector_only": RetrievalStrategy.VECTOR_ONLY,
            "hybrid": RetrievalStrategy.HYBRID,
            "hybrid_rerank": RetrievalStrategy.HYBRID_RERANK,
            "advanced": RetrievalStrategy.ADVANCED,
        }

        enhanced_config = RAGConfig(
            strategy=strategy_map.get(rag_strategy, RetrievalStrategy.HYBRID_RERANK),
            vector_top_k=rag_config.get("vector_top_k", 20),
            min_score=rag_config.get("min_score", 0.15),  # Low threshold, let reranker filter
            keyword_weight=rag_config.get("keyword_weight", 0.3),
            enable_reranking=rag_config.get("enable_reranking", True),
            rerank_top_k=rag_config.get("max_results", 5),
            enable_query_expansion=rag_config.get("enable_query_expansion", False),
            enable_cache=rag_config.get("enable_cache", True),
            max_context_tokens=rag_config.get("max_context_tokens", 4000),
        )

        # Get services
        enhanced_rag = get_enhanced_rag_service(enhanced_config)
        vector_db_pool = get_vector_db_pool()

        try:
            # Perform enhanced RAG retrieval
            rag_response = await enhanced_rag.retrieve(
                query=clean_query,
                knowledge_bases=agent_kbs,
                embedding_service=None,  # Each KB uses its own embedding service
                vector_db_pool=vector_db_pool,
                llm_client=llm_client if enhanced_config.enable_query_expansion else None,
            )

            # Convert RAGResult to legacy format for compatibility
            for result in rag_response.results:
                source_data = {
                    "text": result.text[:300],
                    "text_preview": result.text[:300],
                    "full_text": result.text,
                    "score": result.score,
                    "vector_score": result.vector_score,
                    "keyword_score": result.keyword_score,
                    "rerank_score": result.rerank_score,
                    "knowledge_base": result.kb_name,
                    "kb_name": result.kb_name,
                    "kb_id": result.kb_id,
                    "source": result.source,
                    "title": result.metadata.get("title", result.source),
                    "rank": result.rank,
                    "metadata": result.metadata,
                    "document_id": result.metadata.get("document_id"),
                    "segment_id": result.metadata.get("segment_id"),
                }

                # Generate presigned URL if S3 URL exists
                s3_url = result.metadata.get("url", "")
                if s3_url and s3_url.startswith("s3://"):
                    try:
                        from src.services.storage.s3_storage import S3StorageService

                        # Parse S3 URL to get key
                        # Format: s3://bucket-name/path/to/file
                        s3_parts = s3_url.replace("s3://", "").split("/", 1)
                        if len(s3_parts) == 2:
                            s3_key = s3_parts[1]
                            s3_service = S3StorageService()
                            presigned_url = s3_service.generate_presigned_url(
                                key=s3_key,
                                expiration=3600,  # 1 hour
                            )
                            source_data["presigned_url"] = presigned_url
                    except Exception as e:
                        logger.warning(f"Failed to generate presigned URL for {s3_url}: {e}")

                retrieved_sources.append(source_data)

            context_text = rag_response.context_text

            # Log retrieval stats
            cache_status = "HIT" if rag_response.cache_hit else "MISS"
            logger.info(
                f"📚 Enhanced RAG: {len(rag_response.results)} results, "
                f"{rag_response.retrieval_time_ms:.1f}ms, "
                f"strategy={rag_response.strategy_used}, cache={cache_status}"
            )

        except Exception as e:
            logger.warning(f"Enhanced RAG retrieval failed: {e}")
            # Fall back to empty results on error
            context_text = ""

        if retrieved_sources and not context_text:
            context_parts = ["# Retrieved Context from Knowledge Bases\n"]
            for i, source in enumerate(retrieved_sources[:5], 1):
                context_parts.append(
                    f"\n## Source {i} (Relevance: {source['score']:.2f}, "
                    f"KB: {source['kb_name']})\n{source['full_text']}\n"
                )
            context_text = "\n".join(context_parts)
            logger.info(f"Added context from {len(retrieved_sources)} sources")

        return context_text, retrieved_sources

    async def _build_prompt(
        self,
        db: AsyncSession,
        db_agent,
        conversation_history: list[dict[str, str]] | None,
        attachment_context: str,
        context_text: str,
        message: str,
        perf_config: dict[str, Any],
        conversation_id: str | None = None,
        llm_client: Any = None,
        override_system_prompt: str | None = None,
    ) -> tuple[str, list[dict[str, str]]]:
        from src.services.agents.prompt_builder import SystemPromptBuilder

        prompt_builder = SystemPromptBuilder(db)
        prompt_parts: list[str] = []
        structured_messages: list[dict[str, str]] = []  # Structured conversation for LLM

        # Get model from LLM client config for accurate token counting
        model = llm_client.config.model_name if llm_client else "gpt-4"

        context_config_settings = perf_config.get("context_management", {}) if isinstance(perf_config, dict) else {}
        context_files_mode = context_config_settings.get("context_files_mode", "auto")
        # Keep small/medium context files unchanged. Auto-compaction should only
        # engage once attached context becomes large enough to materially impact
        # prompt size.
        context_files_full_threshold = context_config_settings.get("context_files_full_threshold_chars", 10000)
        context_files_preview_chars = context_config_settings.get("context_files_preview_chars", 600)
        context_files_preview_files = context_config_settings.get("context_files_preview_files", 4)

        enhanced_system_prompt = await prompt_builder.build_enhanced_prompt(
            agent=db_agent,
            include_context_files=True,
            max_context_length=10000,
            override_system_prompt=override_system_prompt,
            context_mode=context_files_mode,
            context_query=message,
            full_context_threshold=context_files_full_threshold,
            preview_chars=context_files_preview_chars,
            max_preview_files=context_files_preview_files,
        )
        if enhanced_system_prompt:
            prompt_parts.append(enhanced_system_prompt)

        # Inject available database connection names so the agent knows the exact names to pass to database tools
        allowed_db_ids = (db_agent.agent_metadata or {}).get("allowed_database_connections")
        if allowed_db_ids:
            try:
                from src.models.database_connection import DatabaseConnection

                _result = await db.execute(
                    select(DatabaseConnection).where(
                        DatabaseConnection.id.in_(allowed_db_ids),
                        DatabaseConnection.tenant_id == db_agent.tenant_id,
                        DatabaseConnection.deleted_at.is_(None),
                    )
                )
                _connections = list(_result.scalars().all())
                if _connections:
                    conn_lines = "\n".join(
                        f'- connection_id: "{c.id}" | name: "{c.name}" (type: {c.database_type}, status: {c.status})'
                        for c in _connections
                    )
                    prompt_parts.append(
                        f"# Configured Database Connections\n"
                        f"IMPORTANT: Use the connection_id (UUID) when calling database tools, NOT the name:\n{conn_lines}"
                    )
            except Exception as _e:
                logger.warning("Failed to inject database connection context: %s", _e)

        if context_text:
            prompt_parts.append(context_text)
            prompt_parts.append(
                "\n# Instructions\nPlease answer the user's query using the retrieved context above. "
                "Cite sources when relevant."
            )

        if conversation_history:
            context_config = ContextConfig(
                strategy=ContextStrategy.COMBINED,
                max_tokens=context_config_settings.get("max_tokens", 180000),
                sliding_window_size=context_config_settings.get("sliding_window_size", 15),
                rag_enabled=context_config_settings.get("rag_enabled", True),
                rag_top_k=context_config_settings.get("rag_top_k", 5),
                # Auto-summarization settings (increased thresholds for better Slack thread context)
                auto_summarize=context_config_settings.get("auto_summarize", True),
                summarize_threshold_messages=context_config_settings.get("summarize_threshold_messages", 25),
                summarize_threshold_tokens=context_config_settings.get("summarize_threshold_tokens", 30000),
                summary_max_tokens=context_config_settings.get("summary_max_tokens", 1500),
                incremental_threshold_messages=context_config_settings.get("incremental_threshold_messages", 5),
            )

            context_manager = ContextManager(context_config)

            # Try to get cached summary for this conversation
            conversation_summary = None
            summary_message_count = 0
            cache_service = get_conversation_cache()

            if conversation_id:
                # Try cache first
                conversation_summary = await cache_service.get_conversation_summary(conversation_id)

                # If not in cache, try to load from database
                if not conversation_summary:
                    try:
                        from uuid import UUID as UUIDType

                        from src.models.conversation import Conversation

                        result = await db.execute(
                            select(Conversation).filter(Conversation.id == UUIDType(conversation_id))
                        )
                        conv = result.scalar_one_or_none()
                        if conv and conv.context_summary:
                            conversation_summary = conv.context_summary
                            summary_message_count = conv.summary_message_count or 0
                            logger.info(f"📝 Loaded summary from DB for conversation {conversation_id}")
                            # Re-cache it for faster access next time
                            await cache_service.set_conversation_summary(conversation_id, conversation_summary)
                    except Exception as e:
                        logger.warning(f"Failed to load summary from DB: {e}")

            # Check if we need to auto-summarize
            if llm_client and context_config.auto_summarize:
                # Check with incremental threshold
                should_summarize = context_manager.should_summarize(
                    messages=conversation_history,
                    existing_summary=conversation_summary,
                    summary_message_count=summary_message_count,
                )

                if should_summarize:
                    recent_messages, new_summary = await context_manager.maybe_summarize_old_messages(
                        messages=conversation_history,
                        llm_client=llm_client,
                        existing_summary=conversation_summary,
                    )

                    if new_summary and new_summary != conversation_summary:
                        conversation_summary = new_summary
                        # Save to both cache AND database for persistence
                        if conversation_id:
                            await cache_service.set_conversation_summary(conversation_id, new_summary)
                            # Also persist to database
                            try:
                                from src.models.conversation import Conversation
                                from src.services.agents.conversation_memory_service import (
                                    get_conversation_memory_service,
                                )

                                memory_service = get_conversation_memory_service(db)
                                await memory_service.save_summary(
                                    conversation_id=conversation_id,
                                    summary=new_summary,
                                    message_count=len(conversation_history),
                                    token_count=context_manager.count_messages_tokens(conversation_history),
                                )
                                logger.info(f"💾 Persisted summary to DB for conversation {conversation_id}")
                            except Exception as e:
                                logger.warning(f"Failed to persist summary to DB: {e}")
                        conversation_history = recent_messages

            # Build context with summary
            context_data = context_manager.build_context(
                system_prompt="",
                messages=conversation_history,
                user_preferences=None,
                current_goals=None,
                relevant_history=None,
                conversation_summary=conversation_summary,
                model=model,
            )

            # Add conversation summary to prompt if available
            if conversation_summary:
                prompt_parts.append(
                    f"# Previous Conversation Context (IMPORTANT - Contains pending user requests)\n"
                    f"{conversation_summary}\n\n"
                    f"**Note: If there are pending requests above, prioritize addressing them.**"
                )

            # Extract structured messages for LLM (separate from system prompt)
            # Normalize role to lowercase to handle both "user"/"assistant" and "USER"/"ASSISTANT"
            # (MessageRole enum stores uppercase; cache may have mixed case from different code paths)
            for context_part in context_data["context_parts"]:
                if context_part["type"] == "recent_messages":
                    for msg in context_part["content"]:
                        role = msg.get("role", "user").lower()
                        content = msg.get("content", "")
                        if role in ["user", "assistant"] and content:
                            structured_messages.append({"role": role, "content": content})

            logger.info(
                f"⚡ Context Manager: strategy={context_data['strategy_used']}, "
                f"tokens={context_data['estimated_tokens']}, "
                f"compressed={context_data['compression_applied']}, "
                f"has_summary={context_data.get('has_summary', False)}, "
                f"original_msgs={len(conversation_history)}"
            )

        if attachment_context:
            prompt_parts.append(attachment_context)

        # Add current user message to structured messages (NOT to prompt_parts)
        structured_messages.append({"role": "user", "content": message})

        # Return system prompt and structured messages
        # Note: Context pruning for tool results happens in function_calling.py during the agentic loop
        system_prompt = "\n\n".join(prompt_parts)
        logger.info(f"📝 Built prompt with {len(structured_messages)} structured messages for LLM")
        return system_prompt, structured_messages

    def _select_tools(
        self, agent, agent_tools: list[Any], message: str = "", mcp_tool_names: list[str] | None = None
    ) -> list[str]:
        """
        Select tools for the current request.

        Uses context-aware filtering to only send relevant tools to the LLM,
        reducing token usage and improving response time.
        """
        from src.services.agents.tool_filter import (
            ALWAYS_INCLUDE_TOOLS,
            ToolFilterConfig,
            filter_tool_names_by_message,
        )

        # Gather all configured tool names
        tool_names: list[str] = []
        if agent.config.tools:
            tool_names = [tool.name for tool in agent.config.tools]

        if agent_tools:
            db_tool_names = [t.tool_name for t in agent_tools]
            tool_names = list(set(tool_names + db_tool_names))

        # Include MCP tools registered at runtime
        if mcp_tool_names:
            tool_names = list(set(tool_names + mcp_tool_names))

        # Always include discovery tools so LLM can find additional capabilities
        # These tools allow the LLM to search for tools it might need
        for tool_name in ALWAYS_INCLUDE_TOOLS:
            if tool_name not in tool_names:
                tool_names.append(tool_name)

        if not tool_names:
            logger.info("No tools configured, using no tools")
            return []

        # Apply context-aware filtering based on message content
        # Note: max_tools is dynamically adjusted by filter based on task complexity.
        # Keep a short default shortlist and rely on discovery tools for long-tail
        # capabilities instead of resending every schema every turn.
        filter_config = ToolFilterConfig(
            min_tools=10,
            max_tools=20,
            fallback_to_all=False,
            min_score_threshold=1.0,
        )

        filtered_tools = filter_tool_names_by_message(
            message=message,
            available_tool_names=tool_names,
            tool_registry=self.tool_registry,
            config=filter_config,
        )

        msg_preview = message[:50] + "..." if len(message) > 50 else message
        logger.info(
            f"Tool selection: {len(tool_names)} configured → {len(filtered_tools)} filtered (message: '{msg_preview}')"
        )

        # Return both the filtered set (for initial LLM context) and the full
        # configured set (so discovery tools can expose the rest on demand).
        return filtered_tools, tool_names

    def _create_trace(
        self,
        agent,
        agent_name: str,
        message: str,
        tool_names: list[str],
    ) -> str | None:
        trace_id = None
        if agent.langfuse_service.should_trace(agent.observability_config):
            try:
                trace_id = agent.langfuse_service.create_trace(
                    name=f"agent_chat_{agent_name}",
                    user_id=None,
                    session_id=None,
                    metadata={
                        "agent_name": agent_name,
                        "message": message[:100],
                        "has_tools": len(tool_names) > 0,
                        "tool_count": len(tool_names),
                    },
                )
                agent.current_trace_id = trace_id
                logger.info(f"✅ Created Langfuse trace for chat: {trace_id}")
            except Exception as e:
                logger.error(f"Failed to create Langfuse trace: {e}")
        return trace_id

    async def _stream_with_tools(
        self,
        agent,
        db_agent,
        prompt: str,
        messages: list[dict[str, str]],
        tool_names: list[str],
        all_configured_tool_names: list[str] | None = None,
        trace_id: str | None = None,
        conversation_uuid=None,
        user_message_id=None,
        start_time: float = 0.0,
        state: StreamState | None = None,
        db: AsyncSession | None = None,
        user_id: str | None = None,
        shared_state: dict[str, Any] | None = None,
        caller_tenant_id: Any | None = None,
        override_agentic_config: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        import uuid as uuid_module

        from src.services.agents.function_calling import FunctionCallingHandler
        from src.services.agents.runtime_context import RuntimeContext

        # Convert user_id string to UUID if provided
        user_uuid = None
        if user_id:
            try:
                user_uuid = uuid_module.UUID(user_id) if isinstance(user_id, str) else user_id
            except ValueError:
                logger.warning(f"Invalid user_id format: {user_id}")

        # For platform engineer agents the agent lives in the platform tenant (UUID zeros),
        # but all tool queries must use the CALLING tenant's ID.
        effective_tenant_id = caller_tenant_id if caller_tenant_id else db_agent.tenant_id

        # Resolve compute session once per conversation (DB lookup, cached on context)
        from src.services.compute.resolver import build_compute_session_for_agent

        if db is None:
            session_factory = get_async_session_factory()
            async with session_factory() as compute_db:
                _compute_session = await build_compute_session_for_agent(
                    db_agent.id,
                    compute_db,
                    tenant_id=effective_tenant_id,
                    conversation_id=conversation_uuid,
                )
        else:
            session_factory = None
            _compute_session = await build_compute_session_for_agent(
                db_agent.id,
                db,
                tenant_id=effective_tenant_id,
                conversation_id=conversation_uuid,
            )

        runtime_context = RuntimeContext(
            tenant_id=effective_tenant_id,
            agent_id=db_agent.id,
            db_session=db,
            db_session_factory=session_factory,
            llm_client=agent.llm_client,
            agent_slug=db_agent.slug,
            conversation_id=conversation_uuid,
            message_id=user_message_id,
            user_id=user_uuid,
            shared_state=shared_state,
            compute_session=_compute_session,
            email_template_id=getattr(db_agent, "email_template_id", None),
        )

        # Populate assigned tools so discovery tools expose agent's full capability set.
        # Use the full configured list (not the filtered subset) so that tools excluded
        # from the initial context by the tool-filter are still discoverable via
        # internal_search_available_tools and can be injected dynamically mid-run.
        _discovery_names = set(all_configured_tool_names) if all_configured_tool_names else set(tool_names)
        runtime_context.all_available_tools = [
            t for t in self.tool_registry.list_tools() if t["name"] in _discovery_names
        ]

        # Populate allowed database connections from agent metadata
        if db_agent.agent_metadata:
            allowed_dbs = db_agent.agent_metadata.get("allowed_database_connections")
            if allowed_dbs:
                runtime_context.allowed_database_connections = allowed_dbs

        # Build agentic config from db_agent metadata if available
        from src.services.agents.config import AgenticConfig

        agentic_meta = (db_agent.agent_metadata or {}).get("agentic_config", {}) if db_agent.agent_metadata else {}
        # Caller-supplied overrides (e.g. spawned workers enabling parallel_tools
        # regardless of the orchestrator agent's stored setting)
        if override_agentic_config:
            agentic_meta = {**agentic_meta, **override_agentic_config}
        logger.info(
            f"🔧 agentic_config loaded for '{db_agent.agent_name}': "
            f"max_iterations={agentic_meta.get('max_iterations', 20)}, "
            f"raw_agent_metadata={db_agent.agent_metadata}"
        )
        agentic_config = AgenticConfig(
            max_iterations=agentic_meta.get("max_iterations", 20),
            parallel_tools=agentic_meta.get("parallel_tools", True),
            tool_retry_attempts=agentic_meta.get("tool_retry_attempts", 2),
            tool_retry_delay=agentic_meta.get("tool_retry_delay", 1.0),
        )

        # Cache agent_name now to avoid lazy-load on an expired ORM object
        # during streaming (concurrent tool commits can expire the session)
        agent_name_cached = db_agent.agent_name

        # Build PII redactor (None when feature is off — zero overhead for all existing agents)
        from src.services.security.pii_redactor import PIIRedactionConfig, PIIRedactor

        pii_config = PIIRedactionConfig.from_agent_metadata(db_agent.agent_metadata)
        # If PII redaction is not explicitly configured but the agent has database
        # connections, enable redact_for_llm by default to prevent PII leakage from
        # query results into the LLM context.
        if not pii_config.any_enabled:
            _has_db_connections = bool((db_agent.agent_metadata or {}).get("allowed_database_connections"))
            if _has_db_connections:
                pii_config = PIIRedactionConfig(redact_for_llm=True, redact_for_response=False)
        pii_redactor = PIIRedactor(pii_config) if pii_config.any_enabled else None

        function_handler = FunctionCallingHandler(
            agent.llm_client,
            tools=tool_names,
            runtime_context=runtime_context,
            trace_id=trace_id,
            observability_config=agent.observability_config,
            agentic_config=agentic_config,
            langfuse_service=agent.langfuse_service,
            pii_redactor=pii_redactor,
        )

        # Use max_tokens and temperature from LLM config (configured in database)
        configured_max_tokens = agent.llm_client.config.max_tokens if hasattr(agent.llm_client, "config") else None
        configured_temperature = (
            agent.llm_client.config.temperature
            if hasattr(agent.llm_client, "config") and agent.llm_client.config
            else 0.7
        )
        logger.info(
            f"📝 Using max_tokens={configured_max_tokens}, temperature={configured_temperature} from LLM config"
        )

        # Activate RuntimeContext so llm_client and function_calling hooks can read it
        runtime_context.__enter__()
        try:
            _stream_gen = function_handler.generate_with_functions_stream(
                prompt=prompt,
                temperature=configured_temperature,
                max_tokens=configured_max_tokens,
                max_iterations=agentic_config.max_iterations,
                messages=messages,
            )
            async for event in _stream_gen:
                if event["type"] == "text":
                    if state.first_token_time is None:
                        state.first_token_time = time.time()
                        time_to_first_token = state.first_token_time - start_time
                        yield await generate_first_token_event(time_to_first_token)

                    sanitization_result = self.output_sanitizer.sanitize(
                        event["content"],
                        context=f"agent_chat_{agent_name_cached}",
                    )

                    chunk_out = sanitization_result.sanitized_content

                    # Restore LLM-facing PII tokens for the user.
                    # Skipped when redact_for_response is also on (user sees redacted output).
                    # No-op when pii_redactor is None (all existing agents unaffected).
                    if (
                        pii_redactor
                        and pii_redactor.config.redact_for_llm
                        and not pii_redactor.config.redact_for_response
                    ):
                        chunk_out = pii_redactor.restore_streaming(chunk_out)

                    state.assistant_chunks.append(chunk_out)
                    state.total_output_tokens += TokenCounter.count_tokens(chunk_out)

                    if sanitization_result.detections:
                        logger.warning(
                            f"Sanitized {len(sanitization_result.detections)} sensitive items in agent response. "
                            f"Agent: {agent_name_cached}, Action: {sanitization_result.action_taken}"
                        )

                    yield await generate_chunk_event(chunk_out)

                elif event["type"] == "function_call":
                    # Track tool start time
                    tool_name = event["name"]
                    state.tool_start_times[tool_name] = time.time()

                    # Send rich tool status event with description and details
                    yield await generate_tool_status_event(
                        tool_name=tool_name,
                        status="started",
                        arguments=event.get("arguments"),
                    )

                elif event["type"] == "function_result":
                    tool_name = event["name"]

                    # Calculate execution duration
                    duration_ms = None
                    if tool_name in state.tool_start_times:
                        start_time = state.tool_start_times.pop(tool_name)
                        duration_ms = int((time.time() - start_time) * 1000)

                    yield await generate_tool_status_event(
                        tool_name=tool_name,
                        status="completed",
                        duration_ms=duration_ms,
                    )

                elif event["type"] == "chart":
                    # Two event shapes:
                    # 1. internal_generate_chart: {chart_id, chart_type, chart_config, chart_data}
                    # 2. inline tools: {chart: {chart_type, library, title, data, table_data, config, ...}}
                    chart = event.get("chart", {})
                    # Store full chart object (library, table_data, chart_type) for DB persistence + history reload
                    state.chart_data.append(
                        {
                            "chart_type": chart.get("chart_type") or event.get("chart_type", "bar"),
                            "type": chart.get("chart_type") or event.get("chart_type", "bar"),  # legacy compat
                            "library": chart.get("library") or "chartjs",
                            "title": chart.get("title") or event.get("chart_title", "Chart"),
                            "description": chart.get("description") or "",
                            "data": chart.get("data") or event.get("chart_data") or {},
                            "config": chart.get("config") or event.get("chart_config") or {},
                            "table_data": chart.get("table_data"),
                        }
                    )
                    chart_payload = {k: v for k, v in event.items() if k != "type"}
                    yield await generate_sse_event("chart", chart_payload)

                elif event["type"] == "diagram":
                    diagram = event.get("diagram", {})
                    state.diagram_data.append(diagram)
                    diagram_payload = {k: v for k, v in event.items() if k != "type"}
                    yield await generate_sse_event("diagram", diagram_payload)

                elif event["type"] == "infographic":
                    infographic = event.get("infographic", {})
                    state.infographic_data.append(infographic)
                    infographic_payload = {k: v for k, v in event.items() if k != "type"}
                    yield await generate_sse_event("infographic", infographic_payload)

                elif event["type"] == "generated_image":
                    image = event.get("generated_image", {})
                    state.generated_images_data.append(image)
                    image_payload = {k: v for k, v in event.items() if k != "type"}
                    yield await generate_sse_event("generated_image", image_payload)

                elif event["type"] == "form":
                    form = event.get("form", {})
                    state.forms_data.append(form)
                    form_payload = {k: v for k, v in event.items() if k != "type"}
                    yield await generate_sse_event("form", form_payload)

                elif event["type"] == "vehicle_map":
                    map_payload = {k: v for k, v in event.items() if k != "type"}
                    yield await generate_sse_event("vehicle_map", map_payload)

                elif event["type"] == "fleet_card":
                    card_payload = {k: v for k, v in event.items() if k != "type"}
                    state.fleet_card_data.append(card_payload.get("card", card_payload))
                    yield await generate_sse_event("fleet_card", card_payload)

            # Flush any partial PII token held back in the streaming buffer
            if pii_redactor and pii_redactor.config.redact_for_llm and not pii_redactor.config.redact_for_response:
                trailing = pii_redactor.flush_stream_buffer()
                if trailing:
                    state.assistant_chunks.append(trailing)
                    yield await generate_chunk_event(trailing)

        finally:
            # Deactivate RuntimeContext (clears ContextVar, closes authenticated clients)
            try:
                runtime_context.__exit__(None, None, None)
            except Exception:
                pass
            # Release compute session (stops ephemeral container, closes SSH, etc.)
            if _compute_session is not None:
                try:
                    await _compute_session.close()
                except Exception as _ce:
                    logger.debug(f"Compute session cleanup error: {_ce}")

    async def _stream_without_tools(
        self,
        agent,
        start_time: float,
        state: StreamState,
        agent_name: str = "unknown",
        system_prompt: str = "",
        messages: list[dict[str, str]] | None = None,
        # Legacy parameter kept for any direct callers
        prompt: str = "",
    ) -> AsyncGenerator[str, None]:
        # Build message list: system prompt + conversation history
        # This preserves proper role structure instead of flat string concatenation
        if messages is not None:
            full_messages: list[dict[str, str]] = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)
            stream = agent.llm_client.generate_content_stream_with_messages(full_messages)
        else:
            # Fallback for legacy callers that pass a pre-built prompt string
            stream = agent.llm_client.generate_content_stream(prompt or system_prompt)

        async for chunk in stream:
            if state.first_token_time is None:
                state.first_token_time = time.time()
                time_to_first_token = state.first_token_time - start_time
                yield await generate_first_token_event(time_to_first_token)

            # SECURITY: Sanitize LLM output to prevent token/secret leakage
            sanitization_result = self.output_sanitizer.sanitize(
                chunk,
                context=f"agent_chat_{agent_name}",
            )

            if sanitization_result.detections:
                logger.warning(
                    f"Sanitized {len(sanitization_result.detections)} sensitive items in agent response. "
                    f"Agent: {agent_name}, Action: {sanitization_result.action_taken}"
                )

            state.assistant_chunks.append(sanitization_result.sanitized_content)
            state.total_output_tokens += TokenCounter.count_tokens(sanitization_result.sanitized_content)
            yield await generate_chunk_event(sanitization_result.sanitized_content)
