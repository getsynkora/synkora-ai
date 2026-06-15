"""
MCP Streamable HTTP server host service.

Implements MCP spec 2025-06-18: exposes each Synkora agent as a single MCP server
with one tool named 'chat'. External MCP clients (Claude Code CLI, Cursor, etc.)
discover the tool via tools/list and invoke the full agent via tools/call.
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2025-06-18"


def _get_integrations_config(agent) -> dict:
    return (agent.agent_metadata or {}).get("integrations_config", {})


def _server_info(agent) -> dict:
    cfg = _get_integrations_config(agent)
    name = cfg.get("mcp_server_name") or agent.agent_name
    return {"name": name, "version": "1.0.0"}


def _build_tool_schema(agent) -> dict:
    """Build the single 'chat' tool schema exposed by this agent."""
    cfg = _get_integrations_config(agent)
    description = (
        cfg.get("mcp_server_description")
        or agent.description
        or f"Send a message to the {agent.agent_name} agent"
    )
    return {
        "name": "chat",
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to send to the agent",
                },
                "conversation_id": {
                    "type": "string",
                    "description": "Optional conversation ID for context continuity",
                },
            },
            "required": ["message"],
        },
    }


async def _collect_agent_response(
    agent,
    message: str,
    conversation_id: str | None,
    db,
) -> str:
    """
    Invoke ChatStreamService and collect the full text response.

    Returns the assembled response text (or an error string).
    """
    from src.services.agents.agent_loader_service import AgentLoaderService
    from src.services.agents.agent_manager import AgentManager
    from src.services.agents.chat_service import ChatService
    from src.services.agents.chat_stream_service import ChatStreamService

    agent_manager = AgentManager()
    agent_loader = AgentLoaderService(agent_manager)
    chat_service = ChatService()
    stream_service = ChatStreamService(agent_loader=agent_loader, chat_service=chat_service)

    chunks: list[str] = []
    async for sse_event in stream_service.stream_agent_response(
        agent_name=agent.slug,
        message=message,
        conversation_history=None,
        conversation_id=conversation_id,
        attachments=None,
        llm_config_id=None,
        db=db,
    ):
        if sse_event.startswith("data: "):
            try:
                data = json.loads(sse_event[6:])
                if data.get("type") == "chunk" and data.get("content"):
                    chunks.append(data["content"])
            except (json.JSONDecodeError, KeyError):
                pass

    return "".join(chunks)


class MCPServerHostService:
    """Handles MCP JSON-RPC requests for a specific agent."""

    async def handle_request(
        self,
        agent,
        payload: dict[str, Any],
        db,
    ) -> dict[str, Any]:
        """
        Dispatch a JSON-RPC request to the appropriate handler.

        Returns a JSON-RPC response dict (or raises ValueError for unknown methods).
        """
        method = payload.get("method")
        req_id = payload.get("id")
        params = payload.get("params", {})

        if method == "initialize":
            return self._handle_initialize(req_id, params, agent)
        elif method == "tools/list":
            return self._handle_tools_list(req_id, agent)
        elif method == "tools/call":
            return await self._handle_tools_call(req_id, params, agent, db)
        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

    def _handle_initialize(self, req_id: Any, params: dict, agent) -> dict:
        """Return server capabilities."""
        client_version = params.get("protocolVersion", MCP_PROTOCOL_VERSION)
        logger.info(f"[MCP] Client initialize, protocolVersion={client_version}")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "serverInfo": _server_info(agent),
                "capabilities": {
                    "tools": {},
                },
            },
        }

    def _handle_tools_list(self, req_id: Any, agent) -> dict:
        """Return the single 'chat' tool this agent exposes."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [_build_tool_schema(agent)],
            },
        }

    async def _handle_tools_call(self, req_id: Any, params: dict, agent, db) -> dict:
        """Execute the 'chat' tool by invoking the agent."""
        tool_name = params.get("name")
        if tool_name != "chat":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": f"Unknown tool: {tool_name}"},
            }

        arguments = params.get("arguments", {})
        message = arguments.get("message", "")
        conversation_id = arguments.get("conversation_id")

        if not message:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "Parameter 'message' is required"},
            }

        try:
            result_text = await _collect_agent_response(agent, message, conversation_id, db)
        except Exception as exc:
            logger.exception(f"[MCP] tools/call failed for agent {agent.id}: {exc}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": "Internal error executing tool"},
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": result_text}],
                "isError": False,
            },
        }

    async def stream_tools_call(
        self,
        agent,
        params: dict,
        db,
    ) -> AsyncGenerator[str, None]:
        """
        SSE streaming variant of tools/call for clients that send Accept: text/event-stream.

        Yields raw SSE lines.
        """
        from src.services.agents.agent_loader_service import AgentLoaderService
        from src.services.agents.agent_manager import AgentManager
        from src.services.agents.chat_service import ChatService
        from src.services.agents.chat_stream_service import ChatStreamService

        arguments = params.get("arguments", {})
        message = arguments.get("message", "")
        conversation_id = arguments.get("conversation_id")

        agent_manager = AgentManager()
        agent_loader = AgentLoaderService(agent_manager)
        chat_service = ChatService()
        stream_service = ChatStreamService(agent_loader=agent_loader, chat_service=chat_service)

        req_id = str(uuid.uuid4())

        async for sse_event in stream_service.stream_agent_response(
            agent_name=agent.slug,
            message=message,
            conversation_history=None,
            conversation_id=conversation_id,
            attachments=None,
            llm_config_id=None,
            db=db,
        ):
            if sse_event.startswith("data: "):
                try:
                    data = json.loads(sse_event[6:])
                    if data.get("type") == "chunk" and data.get("content"):
                        mcp_event = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {
                                "content": [{"type": "text", "text": data["content"]}],
                                "isError": False,
                                "streaming": True,
                            },
                        }
                        yield f"data: {json.dumps(mcp_event)}\n\n"
                except (json.JSONDecodeError, KeyError):
                    pass

        # Final done event
        done_event = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [], "isError": False, "streaming": False},
        }
        yield f"data: {json.dumps(done_event)}\n\n"
