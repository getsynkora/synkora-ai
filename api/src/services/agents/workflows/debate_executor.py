"""
Debate Executor — Orchestrates multi-agent debates for the AI War Room.

Supports structured (fixed rounds with synthesis) and freeform debates.
Internal Synkora agents use the chat stream service; external agents get
called via webhook callbacks or can push responses via the participation API.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.helpers.streaming_helpers import generate_sse_event
from src.models.debate_session import DebateSession

logger = logging.getLogger(__name__)

# Participant colors for visual distinction
PARTICIPANT_COLORS = [
    "#6366f1",  # indigo
    "#f43f5e",  # rose
    "#06b6d4",  # cyan
    "#f59e0b",  # amber
    "#10b981",  # emerald
    "#8b5cf6",  # violet
    "#ec4899",  # pink
    "#14b8a6",  # teal
]

# How long to wait for an external agent response per round (seconds)
EXTERNAL_AGENT_TIMEOUT = 120
# Poll interval when waiting for push-based external responses (seconds)
EXTERNAL_POLL_INTERVAL = 2


class DebateExecutor:
    """Orchestrates multi-agent debates."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_debate(
        self,
        session: DebateSession,
        event_callback: Any = None,
    ) -> AsyncGenerator[str, None]:
        """
        Execute a full debate, yielding SSE events as each message is generated.

        Events emitted:
        - debate_start: {topic, participants, rounds}
        - round_start: {round}
        - participant_start: {participant_id, agent_name, round}
        - participant_chunk: {participant_id, content}
        - participant_done: {participant_id, agent_name, round, content}
        - round_end: {round}
        - synthesis_start: {}
        - synthesis_chunk: {content}
        - verdict: {content}
        - debate_end: {status}
        """
        from src.models.agent import Agent
        from src.services.agents.agent_loader_service import AgentLoaderService
        from src.services.agents.agent_manager import AgentManager
        from src.services.agents.chat_service import ChatService
        from src.services.agents.chat_stream_service import ChatStreamService

        participants = session.participants or []
        messages: list[dict] = list(session.messages or [])
        topic = session.topic
        total_rounds = session.rounds

        # Build additional context from debate_metadata
        debate_context = ""
        metadata = session.debate_metadata or {}
        ctx = metadata.get("context", {})
        if ctx.get("type") == "github_pr":
            pr_parts = []
            if ctx.get("pr_title"):
                pr_parts.append(f"PR Title: {ctx['pr_title']}")
            if ctx.get("repo_full_name"):
                pr_parts.append(f"Repository: {ctx['repo_full_name']}")
            if ctx.get("pr_author"):
                pr_parts.append(f"Author: {ctx['pr_author']}")
            if ctx.get("pr_base_branch") and ctx.get("pr_head_branch"):
                pr_parts.append(f"Branch: {ctx['pr_head_branch']} -> {ctx['pr_base_branch']}")
            if ctx.get("pr_description"):
                pr_parts.append(f"\nPR Description:\n{ctx['pr_description']}")
            if ctx.get("pr_files_changed"):
                pr_parts.append(
                    f"\nFiles Changed ({len(ctx['pr_files_changed'])}):\n"
                    + "\n".join(f"  - {f}" for f in ctx["pr_files_changed"])
                )
            if ctx.get("pr_diff"):
                pr_parts.append(f"\nDiff:\n```diff\n{ctx['pr_diff']}\n```")
            debate_context = "\n".join(pr_parts)
        elif ctx.get("type") == "text" and ctx.get("text"):
            debate_context = ctx["text"]

        yield await generate_sse_event(
            "debate_start",
            {
                "topic": topic,
                "participants": participants,
                "rounds": total_rounds,
            },
        )

        # Initialize chat stream service
        agent_manager = AgentManager()
        agent_loader = AgentLoaderService(agent_manager)
        chat_service = ChatService()
        chat_stream_service = ChatStreamService(
            agent_loader=agent_loader,
            chat_service=chat_service,
        )

        # Update status
        session.status = "active"
        await self.db.commit()

        # Run debate rounds
        for round_num in range(1, total_rounds + 1):
            session.current_round = round_num
            await self.db.commit()

            yield await generate_sse_event("round_start", {"round": round_num})

            # Collect prior messages for context
            prior_messages = [f"[{m['agent_name']}] (Round {m['round']}): {m['content']}" for m in messages]
            context_block = "\n\n".join(prior_messages) if prior_messages else "(No prior messages)"

            # Each participant responds in this round
            for participant in participants:
                participant_id = participant["id"]
                agent_name = participant.get("agent_name", "Agent")
                role_label = participant.get("role", "")

                if participant.get("is_external"):
                    # ── External agent: callback webhook or wait for push ──
                    async for event in self._handle_external_participant(
                        session,
                        participant,
                        round_num,
                        total_rounds,
                        topic,
                        context_block,
                        messages,
                    ):
                        yield event
                    continue

                agent_id = participant.get("agent_id")
                if not agent_id:
                    continue

                # Load the agent from DB
                from sqlalchemy import select

                result = await self.db.execute(select(Agent).filter(Agent.id == agent_id))
                agent = result.scalar_one_or_none()
                if not agent:
                    logger.warning(f"Debate agent {agent_id} not found, skipping")
                    continue

                agent_name = participant.get("agent_name") or agent.agent_name

                yield await generate_sse_event(
                    "participant_start",
                    {
                        "participant_id": participant_id,
                        "agent_name": agent_name,
                        "round": round_num,
                        "color": participant.get("color", "#6366f1"),
                    },
                )

                # Build the debate prompt
                role_instruction = f"Your role in this debate: {role_label}. " if role_label else ""
                context_section = ""
                if debate_context:
                    context_section = f"\n[Context]\n{debate_context}\n\n"

                prompt = (
                    f"You are participating in a structured debate.\n\n"
                    f"Topic: {topic}\n\n"
                    f"{role_instruction}"
                    f"This is round {round_num} of {total_rounds}.\n\n"
                    f"{context_section}"
                    f"[Previous messages in this debate]\n{context_block}\n\n"
                    f"Provide your argument for this round. Be concise, persuasive, and address "
                    f"points raised by other participants. 2-4 paragraphs maximum."
                )

                response_chunks: list[str] = []

                logger.info(
                    f"[Debate] Streaming agent '{agent.agent_name}' for participant '{agent_name}' (round {round_num})"
                )
                event_count = 0
                chunk_count = 0

                try:
                    async for sse_event in chat_stream_service.stream_agent_response(
                        agent_name=agent.slug or agent.agent_name,
                        message=prompt,
                        conversation_history=None,
                        conversation_id=None,
                        attachments=None,
                        llm_config_id=None,
                        db=self.db,
                        trigger_source="war_room",
                        trigger_detail=f"Debate: {topic[:50]}",
                    ):
                        event_count += 1
                        if not sse_event.startswith("data: "):
                            continue
                        try:
                            event_data = json.loads(sse_event[6:])
                            event_type = event_data.get("type", "unknown")
                            if event_type == "error":
                                logger.error(
                                    f"[Debate] Agent '{agent.agent_name}' returned error: "
                                    f"{event_data.get('error', 'unknown')}"
                                )
                            if event_type == "chunk":
                                chunk = event_data.get("content", "")
                                response_chunks.append(chunk)
                                chunk_count += 1
                                yield await generate_sse_event(
                                    "participant_chunk",
                                    {
                                        "participant_id": participant_id,
                                        "content": chunk,
                                    },
                                )
                        except json.JSONDecodeError:
                            logger.warning(f"[Debate] Failed to parse SSE event: {sse_event[:200]}")
                except Exception as stream_err:
                    logger.exception(f"[Debate] Exception streaming agent '{agent.agent_name}': {stream_err}")

                logger.info(
                    f"[Debate] Agent '{agent.agent_name}' finished: "
                    f"{event_count} events, {chunk_count} chunks, "
                    f"{len(''.join(response_chunks))} chars"
                )

                full_response = "".join(response_chunks)

                # Record the message
                msg = {
                    "id": str(uuid.uuid4()),
                    "participant_id": participant_id,
                    "agent_name": agent_name,
                    "round": round_num,
                    "content": full_response,
                    "is_verdict": False,
                    "is_external": False,
                    "created_at": datetime.now(UTC).isoformat(),
                    "color": participant.get("color", "#6366f1"),
                }
                messages.append(msg)
                session.messages = messages
                await self.db.commit()

                yield await generate_sse_event(
                    "participant_done",
                    {
                        "participant_id": participant_id,
                        "agent_name": agent_name,
                        "round": round_num,
                        "content": full_response,
                        "color": participant.get("color", "#6366f1"),
                    },
                )

            yield await generate_sse_event("round_end", {"round": round_num})

        # Synthesis / Verdict
        if session.synthesizer_agent_id:
            yield await generate_sse_event("synthesis_start", {})
            session.status = "synthesizing"
            await self.db.commit()

            result = await self.db.execute(select(Agent).filter(Agent.id == session.synthesizer_agent_id))
            synth_agent = result.scalar_one_or_none()

            if synth_agent:
                all_messages = "\n\n".join(
                    [f"[{m['agent_name']}] (Round {m['round']}): {m['content']}" for m in messages]
                )
                context_for_synth = f"\n[Context]\n{debate_context}\n\n" if debate_context else ""
                synth_prompt = (
                    f"You are the debate synthesizer. Analyze the following debate and provide "
                    f"a balanced, thoughtful verdict.\n\n"
                    f"Topic: {topic}\n\n"
                    f"{context_for_synth}"
                    f"[Full debate]\n{all_messages}\n\n"
                    f"Provide your verdict: who made the strongest arguments and why? "
                    f"What are the key takeaways? Be balanced and fair."
                )

                verdict_chunks: list[str] = []
                async for sse_event in chat_stream_service.stream_agent_response(
                    agent_name=synth_agent.agent_name,
                    message=synth_prompt,
                    conversation_history=None,
                    conversation_id=None,
                    attachments=None,
                    llm_config_id=None,
                    db=self.db,
                    trigger_source="war_room",
                    trigger_detail="Verdict synthesis",
                ):
                    if not sse_event.startswith("data: "):
                        continue
                    try:
                        event_data = json.loads(sse_event[6:])
                        if event_data.get("type") == "chunk":
                            chunk = event_data.get("content", "")
                            verdict_chunks.append(chunk)
                            yield await generate_sse_event(
                                "synthesis_chunk",
                                {
                                    "content": chunk,
                                },
                            )
                    except json.JSONDecodeError:
                        pass

                verdict_text = "".join(verdict_chunks)
                session.verdict = verdict_text

                # Add verdict as a message
                verdict_msg = {
                    "id": str(uuid.uuid4()),
                    "participant_id": "synthesizer",
                    "agent_name": synth_agent.agent_name,
                    "round": total_rounds + 1,
                    "content": verdict_text,
                    "is_verdict": True,
                    "is_external": False,
                    "created_at": datetime.now(UTC).isoformat(),
                    "color": "#f59e0b",
                }
                messages.append(verdict_msg)
                session.messages = messages

                yield await generate_sse_event("verdict", {"content": verdict_text})

        session.status = "completed"
        session.completed_at = datetime.now(UTC)
        await self.db.commit()

        yield await generate_sse_event("debate_end", {"status": "completed"})

    async def _handle_external_participant(
        self,
        session: DebateSession,
        participant: dict,
        round_num: int,
        total_rounds: int,
        topic: str,
        context_block: str,
        messages: list[dict],
    ) -> AsyncGenerator[str, None]:
        """
        Handle an external agent's turn in the debate.

        Two modes:
        1. Callback mode: if participant has callback_url, POST round context to it and
           use the response as the agent's argument.
        2. Push mode: if no callback_url, wait for the external agent to submit via
           POST /war-room/debates/{id}/respond (poll session.messages for new entry).
        """
        participant_id = participant["id"]
        agent_name = participant.get("agent_name", "External Agent")
        callback_url = participant.get("callback_url")
        auth_token = participant.get("auth_token")
        color = participant.get("color", "#8b5cf6")

        yield await generate_sse_event(
            "participant_start",
            {
                "participant_id": participant_id,
                "agent_name": agent_name,
                "round": round_num,
                "color": color,
                "is_external": True,
            },
        )

        response_content: str | None = None

        if callback_url:
            # ── Callback mode: POST to the external agent's URL ──
            response_content = await self._call_external_callback(
                callback_url=callback_url,
                auth_token=auth_token,
                topic=topic,
                round_num=round_num,
                total_rounds=total_rounds,
                context_block=context_block,
            )
        else:
            # ── Push mode: wait for the agent to POST via /respond ──
            response_content = await self._wait_for_external_push(
                session=session,
                participant_id=participant_id,
                round_num=round_num,
            )

        if not response_content:
            response_content = f"[{agent_name} did not respond in time for round {round_num}]"

        # Emit the full response as a single chunk + done event
        yield await generate_sse_event(
            "participant_chunk",
            {
                "participant_id": participant_id,
                "content": response_content,
            },
        )

        msg = {
            "id": str(uuid.uuid4()),
            "participant_id": participant_id,
            "agent_name": agent_name,
            "round": round_num,
            "content": response_content,
            "is_verdict": False,
            "is_external": True,
            "created_at": datetime.now(UTC).isoformat(),
            "color": color,
        }
        messages.append(msg)
        session.messages = messages
        await self.db.commit()

        yield await generate_sse_event(
            "participant_done",
            {
                "participant_id": participant_id,
                "agent_name": agent_name,
                "round": round_num,
                "content": response_content,
                "color": color,
                "is_external": True,
            },
        )

    async def _call_external_callback(
        self,
        callback_url: str,
        auth_token: str | None,
        topic: str,
        round_num: int,
        total_rounds: int,
        context_block: str,
    ) -> str | None:
        """POST debate context to an external agent's callback URL and return its response."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        payload = {
            "debate_topic": topic,
            "round": round_num,
            "total_rounds": total_rounds,
            "prior_messages": context_block,
            "instructions": (
                "You are participating in a structured debate. "
                f"This is round {round_num} of {total_rounds}. "
                "Provide your argument. Be concise and persuasive. 2-4 paragraphs maximum."
            ),
        }

        try:
            async with httpx.AsyncClient(timeout=EXTERNAL_AGENT_TIMEOUT) as client:
                resp = await client.post(callback_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                # Accept response as {content: "..."} or plain text
                if isinstance(data, dict):
                    return data.get("content") or data.get("response") or data.get("message") or str(data)
                return str(data)
        except httpx.TimeoutException:
            logger.warning(f"External agent callback timed out: {callback_url}")
            return None
        except Exception as e:
            logger.warning(f"External agent callback failed: {callback_url} — {e}")
            return None

    async def _wait_for_external_push(
        self,
        session: DebateSession,
        participant_id: str,
        round_num: int,
    ) -> str | None:
        """
        Poll the session messages for an external agent's pushed response.

        The external agent submits via POST /war-room/debates/{id}/respond,
        which appends to session.messages. We poll until we find a matching entry.
        """
        elapsed = 0.0
        while elapsed < EXTERNAL_AGENT_TIMEOUT:
            await asyncio.sleep(EXTERNAL_POLL_INTERVAL)
            elapsed += EXTERNAL_POLL_INTERVAL

            # Refresh session to pick up changes from the /respond endpoint
            await self.db.refresh(session)
            current_messages = session.messages or []

            # Look for a message from this participant for this round
            for msg in current_messages:
                if (
                    msg.get("participant_id") == participant_id
                    and msg.get("round") == round_num
                    and msg.get("is_external")
                ):
                    return msg.get("content", "")

        return None
