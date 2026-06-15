"""
Elasticsearch Tools Registry

Registers all Elasticsearch-related tools with the ADK tool registry.
This modular approach keeps tool registration organized and maintainable.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_elasticsearch_tools(registry):
    """
    Register all Elasticsearch tools with the ADK tool registry.

    Args:
        registry: ADKToolRegistry instance
    """
    from src.services.agents.internal_tools.elasticsearch_tools import (
        internal_elasticsearch_get_index_stats,
        internal_elasticsearch_list_indices,
        internal_elasticsearch_search,
    )

    BACKGROUND_HIT_THRESHOLD = 100  # auto-defer when ES total hits exceed this

    def _build_es_query_clause(query_str: str) -> dict:
        """Return an ES query clause for the given search string.
        Wildcard/empty queries fall back to match_all; others use multi_match."""
        _WILDCARD = {"", "*", "**", "all", "all records", "everything"}
        if not query_str or query_str.strip().lower() in _WILDCARD:
            return {"match_all": {}}
        return {"multi_match": {"query": query_str, "fields": ["*"], "type": "best_fields"}}

    # Elasticsearch tools - create wrappers that inject runtime_context
    async def internal_elasticsearch_search_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        background = kwargs.get("background", False)

        # Background deferral: build an ES DSL query and defer to Celery
        if background and runtime_context:
            try:
                from src.services.agents.adk_tools import _maybe_defer_to_background

                tenant_id = getattr(runtime_context, "tenant_id", None)
                db_session = getattr(runtime_context, "db_session", None)
                connection_name = kwargs.get("connection_name", "")
                index_pattern = kwargs.get("index_pattern", "*")
                query_str = kwargs.get("query", "")
                limit = kwargs.get("limit", 10)
                filters = kwargs.get("filters") or {}

                # Resolve connection_id from name or UUID
                import uuid as _uuid

                from sqlalchemy import or_, select

                from src.models.database_connection import DatabaseConnection

                def _is_uuid(val):
                    try:
                        _uuid.UUID(str(val))
                        return True
                    except Exception:
                        return False

                id_f = DatabaseConnection.id == connection_name if _is_uuid(connection_name) else None
                name_f = DatabaseConnection.name == connection_name
                combined = or_(id_f, name_f) if id_f is not None else name_f
                res = await db_session.execute(
                    select(DatabaseConnection.id).filter(
                        combined,
                        DatabaseConnection.tenant_id == tenant_id,
                        DatabaseConnection.deleted_at.is_(None),
                    )
                )
                conn_id = res.scalar_one_or_none()

                if conn_id:
                    # Build ES DSL from the search params
                    import json as _json

                    dsl: dict = {"query": _build_es_query_clause(query_str), "size": limit}
                    if filters.get("date_range"):
                        dr = filters["date_range"]
                        dsl["query"] = {
                            "bool": {
                                "must": [dsl["query"]],
                                "filter": [{"range": {dr["field"]: {"gte": dr.get("gte"), "lte": dr.get("lte")}}}],
                            }
                        }
                    if index_pattern and index_pattern != "*":
                        dsl["index"] = index_pattern
                    deferred = await _maybe_defer_to_background(
                        connection_id=str(conn_id),
                        query=_json.dumps(dsl),
                        config={"background": True, "_runtime_context": runtime_context},
                        tenant_id=str(tenant_id),
                        db_session=db_session,
                    )
                    if deferred:
                        return deferred
            except Exception as _e:
                logger.warning("Background deferral failed, running inline: %s", _e)

        # Auto-deferral: if total hits would exceed threshold, run in background
        if not background and runtime_context:
            try:
                from src.services.agents.adk_tools import _maybe_defer_to_background

                tenant_id = getattr(runtime_context, "tenant_id", None)
                db_session = getattr(runtime_context, "db_session", None)
                connection_name = kwargs.get("connection_name", "")
                index_pattern = kwargs.get("index_pattern", "*")
                query_str = kwargs.get("query", "")
                limit = kwargs.get("limit", 10)

                if tenant_id and db_session:
                    import uuid as _uuid

                    from sqlalchemy import or_, select

                    from src.models.database_connection import DatabaseConnection

                    def _is_uuid2(val):
                        try:
                            _uuid.UUID(str(val))
                            return True
                        except Exception:
                            return False

                    id_f2 = DatabaseConnection.id == connection_name if _is_uuid2(connection_name) else None
                    name_f2 = DatabaseConnection.name == connection_name
                    combined2 = or_(id_f2, name_f2) if id_f2 is not None else name_f2
                    res2 = await db_session.execute(
                        select(DatabaseConnection).filter(
                            combined2,
                            DatabaseConnection.tenant_id == tenant_id,
                            DatabaseConnection.deleted_at.is_(None),
                        )
                    )
                    conn2 = res2.scalar_one_or_none()

                    if conn2:
                        from src.services.search.elasticsearch_service import ElasticsearchService

                        password2 = None
                        if conn2.password_encrypted:
                            try:
                                password2 = conn2.get_password()
                            except Exception:
                                pass
                        es2 = ElasticsearchService(
                            {
                                "host": conn2.host,
                                "port": conn2.port,
                                "username": conn2.username,
                                "password": password2,
                                "connection_params": conn2.connection_params or {},
                            }
                        )
                        stats_result = await es2.get_index_stats(index_pattern)
                        await es2.close()
                        total_hits = stats_result.get("document_count", 0) if stats_result.get("success") else 0

                        if total_hits > BACKGROUND_HIT_THRESHOLD:
                            import json as _json

                            dsl = {"query": _build_es_query_clause(query_str), "size": limit}
                            if index_pattern and index_pattern != "*":
                                dsl["index"] = index_pattern
                            deferred = await _maybe_defer_to_background(
                                connection_id=str(conn2.id),
                                query=_json.dumps(dsl),
                                config={"background": True, "_runtime_context": runtime_context},
                                tenant_id=str(tenant_id),
                                db_session=db_session,
                            )
                            if deferred:
                                return {**deferred, "auto_deferred": True, "total_hits": total_hits}
            except Exception as _auto_e:
                logger.warning("Auto-background check failed, running inline: %s", _auto_e)

        return await internal_elasticsearch_search(
            connection_name=kwargs.get("connection_name"),
            index_pattern=kwargs.get("index_pattern"),
            query=kwargs.get("query"),
            filters=kwargs.get("filters"),
            limit=kwargs.get("limit", 10),
            runtime_context=runtime_context,
        )

    async def internal_elasticsearch_list_indices_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_elasticsearch_list_indices(
            connection_name=kwargs.get("connection_name"), runtime_context=runtime_context
        )

    async def internal_elasticsearch_get_index_stats_wrapper(config: dict[str, Any] | None = None, **kwargs):
        runtime_context = config.get("_runtime_context") if config else None
        return await internal_elasticsearch_get_index_stats(
            connection_name=kwargs.get("connection_name"),
            index_pattern=kwargs.get("index_pattern"),
            runtime_context=runtime_context,
        )

    # Register all Elasticsearch tools
    registry.register_tool(
        name="internal_elasticsearch_search",
        description="""Search through Elasticsearch indices using full-text search.
        Use this to find relevant information from indexed data like Slack messages,
        documents, logs, product data, or any other data stored in Elasticsearch.

        You must first have an Elasticsearch connection configured in database connections.
        Ask the user for the connection name if you don't know it, or use
        internal_elasticsearch_list_indices to discover available indices.

        This tool is perfect for:
        - Searching historical Slack messages
        - Finding relevant documents or articles
        - Querying product information
        - Analyzing logs and events
        - Full-text search across any indexed data

        The search supports fuzzy matching and ranks results by relevance score.""",
        parameters={
            "type": "object",
            "properties": {
                "connection_name": {
                    "type": "string",
                    "description": "Name of the Elasticsearch connection from /database-connections (e.g., 'Main Elasticsearch', 'Production ES')",
                },
                "index_pattern": {
                    "type": "string",
                    "description": "Index pattern to search. Can be a specific index or pattern with wildcards (e.g., 'slack_messages_*', 'product_catalog', 'logs-2024-*')",
                },
                "query": {
                    "type": "string",
                    "description": "Search query string. Supports natural language queries that will match across all fields.",
                },
                "filters": {
                    "type": "object",
                    "description": "Optional filters to refine the search",
                    "properties": {
                        "date_range": {
                            "type": "object",
                            "description": "Filter by date range",
                            "properties": {
                                "field": {
                                    "type": "string",
                                    "description": "Date field name (e.g., 'timestamp', 'created_at', '@timestamp')",
                                },
                                "gte": {
                                    "type": "string",
                                    "description": "Greater than or equal to (e.g., '2024-01-01', 'now-30d', 'now-1M')",
                                },
                                "lte": {
                                    "type": "string",
                                    "description": "Less than or equal to (e.g., '2024-12-31', 'now')",
                                },
                            },
                        },
                        "term_filters": {
                            "type": "object",
                            "description": "Exact match filters as key-value pairs (e.g., {'channel_name': 'product', 'user_id': 'U1234'})",
                            "additionalProperties": {"type": "string"},
                        },
                    },
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 10, max: 100)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                },
                "background": {
                    "type": "boolean",
                    "description": "If true, run this search as a background job and post the result back to the conversation when done. Use for large or slow queries, or when the user asks to 'run in background'.",
                },
            },
            "required": ["connection_name", "index_pattern", "query"],
        },
        function=internal_elasticsearch_search_wrapper,
    )

    registry.register_tool(
        name="internal_elasticsearch_list_indices",
        description="""List all available indices in an Elasticsearch connection.

        Use this tool to discover what indices are available before searching.
        This helps you understand what data is indexed and what index patterns
        to use with internal_elasticsearch_search.

        For example, if you see indices like:
        - slack_messages_2024_12
        - slack_messages_2024_11
        - slack_messages_2024_10

        You can search all of them with pattern 'slack_messages_*'""",
        parameters={
            "type": "object",
            "properties": {
                "connection_name": {"type": "string", "description": "Name of the Elasticsearch connection"}
            },
            "required": ["connection_name"],
        },
        function=internal_elasticsearch_list_indices_wrapper,
    )

    registry.register_tool(
        name="internal_elasticsearch_get_index_stats",
        description="""Get statistics for an Elasticsearch index or pattern.

        Use this to understand the size and scope of an index before searching.
        Returns document count, storage size, and list of matching indices.""",
        parameters={
            "type": "object",
            "properties": {
                "connection_name": {"type": "string", "description": "Name of the Elasticsearch connection"},
                "index_pattern": {
                    "type": "string",
                    "description": "Index or pattern to get stats for (e.g., 'slack_messages_*')",
                },
            },
            "required": ["connection_name", "index_pattern"],
        },
        function=internal_elasticsearch_get_index_stats_wrapper,
    )

    logger.info("Registered 3 Elasticsearch tools")
