"""Synkora SDK client — sync and async."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any
from uuid import UUID

import httpx

from .exceptions import (
    AgentNotFoundError,
    APIError,
    AuthError,
    RateLimitError,
    SynkoraError,
)
from .models import (
    AgentInfo,
    ChatResponse,
    ConversationInfo,
    DoneEvent,
    StreamEvent,
)
from .streaming import _aiter_sse_lines, _iter_sse_lines

_DEFAULT_BASE_URL = "https://app.synkora.com"
_DEFAULT_TIMEOUT = 120.0  # seconds; streaming responses can be long


def _raise_for_status(response: httpx.Response) -> None:
    """Convert HTTP error codes to SDK exceptions."""
    if response.status_code == 401:
        raise AuthError("Invalid or missing API key.", status_code=401)
    if response.status_code == 403:
        raise AuthError("API key does not have permission for this action.", status_code=403)
    if response.status_code == 404:
        raise AgentNotFoundError("Agent not found.", status_code=404)
    if response.status_code == 429:
        raise RateLimitError("Rate limit exceeded. Slow down and retry.", status_code=429)
    if response.status_code >= 500:
        raise APIError(f"Server error: {response.status_code}", status_code=response.status_code)
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise SynkoraError(str(detail), status_code=response.status_code)


class SynkoraClient:
    """
    Synchronous Synkora client.

    Usage::

        client = SynkoraClient(api_key="sk-...")
        response = client.chat(agent_id="<uuid>", message="Hello")
        print(response.message)

        for event in client.chat_stream(agent_id="<uuid>", message="Hello"):
            if hasattr(event, "content"):
                print(event.content, end="", flush=True)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        resolved_key = api_key or os.environ.get("SYNKORA_API_KEY")
        if not resolved_key:
            raise AuthError(
                "No API key provided. Pass api_key= or set the SYNKORA_API_KEY environment variable."
            )
        resolved_url = (base_url or os.environ.get("SYNKORA_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")

        self._http = httpx.Client(
            base_url=resolved_url,
            headers={
                "Authorization": f"Bearer {resolved_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "synkora-python/0.1.0",
            },
            timeout=httpx.Timeout(timeout),
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> SynkoraClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    def list_agents(self) -> list[AgentInfo]:
        """List all agents accessible with this API key."""
        resp = self._http.get("/api/v1/public/agents")
        _raise_for_status(resp)
        data = resp.json()
        agents = data if isinstance(data, list) else data.get("agents", [])
        return [
            AgentInfo(
                id=str(a["id"]),
                name=a["name"],
                description=a.get("description"),
                model=a.get("model"),
                capabilities=a.get("capabilities", []),
            )
            for a in agents
        ]

    def get_agent(self, agent_id: str | UUID) -> AgentInfo:
        """Retrieve metadata for a single agent."""
        resp = self._http.get(f"/api/v1/public/agents/{agent_id}")
        _raise_for_status(resp)
        a = resp.json()
        return AgentInfo(
            id=str(a["id"]),
            name=a["name"],
            description=a.get("description"),
            model=a.get("model"),
            capabilities=a.get("capabilities", []),
        )

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    def list_conversations(self, agent_id: str | UUID) -> list[ConversationInfo]:
        """List stored conversations for an agent."""
        resp = self._http.get(f"/api/v1/public/agents/{agent_id}/conversations")
        _raise_for_status(resp)
        data = resp.json()
        items = data if isinstance(data, list) else data.get("conversations", [])
        return [
            ConversationInfo(
                id=str(c["id"]),
                agent_id=str(c["agent_id"]),
                created_at=c["created_at"],
                updated_at=c["updated_at"],
                message_count=c.get("message_count", 0),
            )
            for c in items
        ]

    def delete_conversation(self, agent_id: str | UUID, conversation_id: str | UUID) -> None:
        """Delete a conversation and all its messages."""
        resp = self._http.delete(
            f"/api/v1/public/agents/{agent_id}/conversations/{conversation_id}"
        )
        _raise_for_status(resp)

    # ------------------------------------------------------------------
    # Chat — non-streaming (aggregates stream internally)
    # ------------------------------------------------------------------

    def chat(
        self,
        agent_id: str | UUID,
        message: str,
        *,
        conversation_id: str | UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """
        Send a message and return the full response when complete.

        Internally uses the streaming endpoint and aggregates chunks.
        """
        content_parts: list[str] = []
        conversation_id_out: str | None = None
        done_event: DoneEvent | None = None

        for event in self.chat_stream(
            agent_id=agent_id,
            message=message,
            conversation_id=conversation_id,
            metadata=metadata,
        ):
            if hasattr(event, "content") and event.type == "chunk":
                content_parts.append(event.content)
            if event.type == "done":
                done_event = event  # type: ignore[assignment]
                meta = done_event.metadata
                conversation_id_out = str(meta.get("conversation_id", "")) or conversation_id_out

        meta_out = done_event.metadata if done_event else {}
        return ChatResponse(
            conversation_id=conversation_id_out or str(conversation_id or ""),
            message="".join(content_parts),
            tokens_used=meta_out.get("total_tokens"),
            metadata=meta_out,
            sources=done_event.sources if done_event else [],
        )

    # ------------------------------------------------------------------
    # Chat — streaming
    # ------------------------------------------------------------------

    def chat_stream(
        self,
        agent_id: str | UUID,
        message: str,
        *,
        conversation_id: str | UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[StreamEvent]:
        """
        Stream a chat response, yielding typed events as they arrive.

        Example::

            for event in client.chat_stream(agent_id="...", message="Hello"):
                if event.type == "chunk":
                    print(event.content, end="", flush=True)
                elif event.type == "done":
                    print()  # newline after stream
        """
        body: dict[str, Any] = {"message": message}
        if conversation_id is not None:
            body["conversation_id"] = str(conversation_id)
        if metadata is not None:
            body["metadata"] = metadata

        with self._http.stream(
            "POST",
            f"/api/v1/public/agents/{agent_id}/chat/stream",
            json=body,
        ) as resp:
            _raise_for_status(resp)
            yield from _iter_sse_lines(resp.iter_lines())


class AsyncSynkoraClient:
    """
    Async Synkora client.

    Usage::

        async with AsyncSynkoraClient(api_key="sk-...") as client:
            response = await client.chat(agent_id="<uuid>", message="Hello")
            print(response.message)

            async for event in client.chat_stream(agent_id="<uuid>", message="Hello"):
                if event.type == "chunk":
                    print(event.content, end="", flush=True)
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        resolved_key = api_key or os.environ.get("SYNKORA_API_KEY")
        if not resolved_key:
            raise AuthError(
                "No API key provided. Pass api_key= or set the SYNKORA_API_KEY environment variable."
            )
        resolved_url = (base_url or os.environ.get("SYNKORA_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")

        self._http = httpx.AsyncClient(
            base_url=resolved_url,
            headers={
                "Authorization": f"Bearer {resolved_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "synkora-python/0.1.0",
            },
            timeout=httpx.Timeout(timeout),
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncSynkoraClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    async def list_agents(self) -> list[AgentInfo]:
        resp = await self._http.get("/api/v1/public/agents")
        _raise_for_status(resp)
        data = resp.json()
        agents = data if isinstance(data, list) else data.get("agents", [])
        return [
            AgentInfo(
                id=str(a["id"]),
                name=a["name"],
                description=a.get("description"),
                model=a.get("model"),
                capabilities=a.get("capabilities", []),
            )
            for a in agents
        ]

    async def get_agent(self, agent_id: str | UUID) -> AgentInfo:
        resp = await self._http.get(f"/api/v1/public/agents/{agent_id}")
        _raise_for_status(resp)
        a = resp.json()
        return AgentInfo(
            id=str(a["id"]),
            name=a["name"],
            description=a.get("description"),
            model=a.get("model"),
            capabilities=a.get("capabilities", []),
        )

    # ------------------------------------------------------------------
    # Conversations
    # ------------------------------------------------------------------

    async def list_conversations(self, agent_id: str | UUID) -> list[ConversationInfo]:
        resp = await self._http.get(f"/api/v1/public/agents/{agent_id}/conversations")
        _raise_for_status(resp)
        data = resp.json()
        items = data if isinstance(data, list) else data.get("conversations", [])
        return [
            ConversationInfo(
                id=str(c["id"]),
                agent_id=str(c["agent_id"]),
                created_at=c["created_at"],
                updated_at=c["updated_at"],
                message_count=c.get("message_count", 0),
            )
            for c in items
        ]

    async def delete_conversation(self, agent_id: str | UUID, conversation_id: str | UUID) -> None:
        resp = await self._http.delete(
            f"/api/v1/public/agents/{agent_id}/conversations/{conversation_id}"
        )
        _raise_for_status(resp)

    # ------------------------------------------------------------------
    # Chat — non-streaming
    # ------------------------------------------------------------------

    async def chat(
        self,
        agent_id: str | UUID,
        message: str,
        *,
        conversation_id: str | UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """Send a message and return the full response when complete."""
        content_parts: list[str] = []
        conversation_id_out: str | None = None
        done_event: DoneEvent | None = None

        async for event in self.chat_stream(
            agent_id=agent_id,
            message=message,
            conversation_id=conversation_id,
            metadata=metadata,
        ):
            if hasattr(event, "content") and event.type == "chunk":
                content_parts.append(event.content)
            if event.type == "done":
                done_event = event  # type: ignore[assignment]
                meta = done_event.metadata
                conversation_id_out = str(meta.get("conversation_id", "")) or conversation_id_out

        meta_out = done_event.metadata if done_event else {}
        return ChatResponse(
            conversation_id=conversation_id_out or str(conversation_id or ""),
            message="".join(content_parts),
            tokens_used=meta_out.get("total_tokens"),
            metadata=meta_out,
            sources=done_event.sources if done_event else [],
        )

    # ------------------------------------------------------------------
    # Chat — streaming
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        agent_id: str | UUID,
        message: str,
        *,
        conversation_id: str | UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a chat response, yielding typed events as they arrive."""
        body: dict[str, Any] = {"message": message}
        if conversation_id is not None:
            body["conversation_id"] = str(conversation_id)
        if metadata is not None:
            body["metadata"] = metadata

        async with self._http.stream(
            "POST",
            f"/api/v1/public/agents/{agent_id}/chat/stream",
            json=body,
        ) as resp:
            _raise_for_status(resp)
            async for event in _aiter_sse_lines(resp.aiter_lines()):
                yield event
