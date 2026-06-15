"""
Elasticsearch Internal Tools for Synkora Agents.

Provides generic Elasticsearch search capabilities through configured
database connections. Agents can search any Elasticsearch index that
has been set up in the database connections UI.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database_connection import DatabaseConnection

logger = logging.getLogger(__name__)


async def internal_elasticsearch_search(
    connection_name: str,
    index_pattern: str,
    query: str,
    filters: dict[str, Any] | None = None,
    limit: int = 10,
    config: dict[str, Any] | None = None,
    runtime_context: Any = None,
) -> dict[str, Any]:
    """
    Search an Elasticsearch index through a configured database connection.

    This is a generic search tool that agents can use to query any
    Elasticsearch index configured in database connections.

    Args:
        connection_name: Name of the Elasticsearch database connection
        index_pattern: Index pattern to search (e.g., "slack_messages_*", "product_*")
        query: Search query string
        filters: Optional filters for refined search:
            - date_range: {"field": "timestamp", "gte": "now-30d", "lte": "now"}
            - term_filters: {"channel_name": "product", "user_id": "U1234"}
        limit: Maximum number of results to return (default: 10, max: 100)
        config: Configuration dictionary (unused)
        runtime_context: Runtime context with tenant information

    Returns:
        Dictionary with:
        - success: bool
        - total: int (total matching documents)
        - results: List of search results with index, id, score, and source
        - took_ms: int (query execution time)
        - error: str (if failed)

    Example:
        # Search Slack messages about product features
        result = await internal_elasticsearch_search(
            connection_name="Main Elasticsearch",
            index_pattern="slack_messages_*",
            query="product roadmap features",
            filters={
                "date_range": {
                    "field": "timestamp",
                    "gte": "now-30d"
                },
                "term_filters": {
                    "channel_name": "product"
                }
            },
            limit=10
        )
    """
    try:
        # Validate inputs
        if not connection_name or not isinstance(connection_name, str):
            return {"success": False, "error": "Connection name is required and must be a string"}

        if not index_pattern or not isinstance(index_pattern, str):
            return {"success": False, "error": "Index pattern is required and must be a string"}

        if not query or not isinstance(query, str):
            return {"success": False, "error": "Query is required and must be a string"}

        # Get tenant ID from runtime context
        if not runtime_context:
            return {"success": False, "error": "No runtime context available"}

        tenant_id = getattr(runtime_context, "tenant_id", None)
        if not tenant_id:
            return {"success": False, "error": "No tenant ID in runtime context"}

        # Get db session from runtime context
        db: AsyncSession = getattr(runtime_context, "db_session", None)
        if not db:
            return {"success": False, "error": "No database session in runtime context"}

        try:
            import uuid as _uuid

            def _is_uuid(val: str) -> bool:
                try:
                    _uuid.UUID(val)
                    return True
                except ValueError:
                    return False

            from sqlalchemy import or_

            id_filter = DatabaseConnection.id == connection_name if _is_uuid(connection_name) else None
            name_filter = DatabaseConnection.name == connection_name
            combined = or_(id_filter, name_filter) if id_filter is not None else name_filter

            result = await db.execute(
                select(DatabaseConnection).filter(
                    combined,
                    DatabaseConnection.database_type == "ELASTICSEARCH",
                    DatabaseConnection.tenant_id == tenant_id,
                    DatabaseConnection.deleted_at.is_(None),
                )
            )
            connection = result.scalar_one_or_none()

            if not connection:
                return {
                    "success": False,
                    "error": f"Elasticsearch connection '{connection_name}' not found. Please create it in database connections first.",
                }

            if connection.status != "active":
                return {
                    "success": False,
                    "error": f"Connection '{connection_name}' is not active (status: {connection.status})",
                }

            # Initialize Elasticsearch service
            from src.services.search.elasticsearch_service import ElasticsearchService

            # Get password if encrypted
            password = None
            if connection.password_encrypted:
                try:
                    password = connection.get_password()
                except Exception as e:
                    logger.error(f"Failed to decrypt password: {e}")
                    return {"success": False, "error": "Failed to decrypt connection password"}

            es_service = ElasticsearchService(
                {
                    "host": connection.host,
                    "port": connection.port,
                    "username": connection.username,
                    "password": password,
                    "connection_params": connection.connection_params or {},
                }
            )

            # Perform search
            results = await es_service.search(
                index_pattern=index_pattern,
                query=query,
                filters=filters,
                size=min(limit, 100),  # Cap at 100 for safety
            )

            await es_service.close()

            # Add helpful message
            if results.get("success"):
                results["message"] = f"Found {results['total']} results in {results['took_ms']}ms"

            return results

        except Exception as e:
            logger.error(f"Elasticsearch search inner error: {e}", exc_info=True)
            return {"success": False, "error": str(e), "results": []}

    except Exception as e:
        logger.error(f"Elasticsearch search error: {e}", exc_info=True)
        return {"success": False, "error": str(e), "results": []}


async def internal_elasticsearch_list_indices(
    connection_name: str, config: dict[str, Any] | None = None, runtime_context: Any = None
) -> dict[str, Any]:
    """
    List all indices available in an Elasticsearch connection.

    Args:
        connection_name: Name of the Elasticsearch database connection
        config: Configuration dictionary (unused)
        runtime_context: Runtime context with tenant information

    Returns:
        Dictionary with:
        - success: bool
        - indices: List of index names
        - count: int (number of indices)
        - error: str (if failed)
    """
    try:
        if not connection_name or not isinstance(connection_name, str):
            return {"success": False, "error": "Connection name is required and must be a string"}

        # Get tenant ID from runtime context
        if not runtime_context:
            return {"success": False, "error": "No runtime context available"}

        tenant_id = getattr(runtime_context, "tenant_id", None)
        if not tenant_id:
            return {"success": False, "error": "No tenant ID in runtime context"}

        # Get db session from runtime context
        db: AsyncSession = getattr(runtime_context, "db_session", None)
        if not db:
            return {"success": False, "error": "No database session in runtime context"}

        try:
            import uuid as _uuid

            from sqlalchemy import or_

            def _is_uuid(val: str) -> bool:
                try:
                    _uuid.UUID(val)
                    return True
                except ValueError:
                    return False

            id_filter = DatabaseConnection.id == connection_name if _is_uuid(connection_name) else None
            name_filter = DatabaseConnection.name == connection_name
            combined = or_(id_filter, name_filter) if id_filter is not None else name_filter

            result = await db.execute(
                select(DatabaseConnection).filter(
                    combined,
                    DatabaseConnection.database_type == "ELASTICSEARCH",
                    DatabaseConnection.tenant_id == tenant_id,
                    DatabaseConnection.deleted_at.is_(None),
                )
            )
            connection = result.scalar_one_or_none()

            if not connection:
                return {"success": False, "error": f"Connection '{connection_name}' not found"}

            # Get password if encrypted
            password = None
            if connection.password_encrypted:
                try:
                    password = connection.get_password()
                except Exception as e:
                    logger.error(f"Failed to decrypt password: {e}")
                    return {"success": False, "error": "Failed to decrypt connection password"}

            # Initialize Elasticsearch service
            from src.services.search.elasticsearch_service import ElasticsearchService

            es_service = ElasticsearchService(
                {
                    "host": connection.host,
                    "port": connection.port,
                    "username": connection.username,
                    "password": password,
                    "connection_params": connection.connection_params or {},
                }
            )

            indices = await es_service.get_indices()
            await es_service.close()

            return {
                "success": True,
                "indices": indices,
                "count": len(indices),
                "message": f"Found {len(indices)} indices",
            }

        except Exception as e:
            logger.error(f"Error listing indices inner: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"Error listing indices: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def internal_elasticsearch_get_index_stats(
    connection_name: str, index_pattern: str, config: dict[str, Any] | None = None, runtime_context: Any = None
) -> dict[str, Any]:
    """
    Get statistics for an Elasticsearch index or pattern.

    Args:
        connection_name: Name of the Elasticsearch database connection
        index_pattern: Index pattern to get stats for (e.g., "slack_messages_*")
        config: Configuration dictionary (unused)
        runtime_context: Runtime context with tenant information

    Returns:
        Dictionary with:
        - success: bool
        - document_count: int
        - size_bytes: int
        - indices: List of matching index names
        - error: str (if failed)
    """
    try:
        if not connection_name or not isinstance(connection_name, str):
            return {"success": False, "error": "Connection name is required"}

        if not index_pattern or not isinstance(index_pattern, str):
            return {"success": False, "error": "Index pattern is required"}

        # Get tenant ID from runtime context
        if not runtime_context:
            return {"success": False, "error": "No runtime context available"}

        tenant_id = getattr(runtime_context, "tenant_id", None)
        if not tenant_id:
            return {"success": False, "error": "No tenant ID in runtime context"}

        # Get db session from runtime context
        db: AsyncSession = getattr(runtime_context, "db_session", None)
        if not db:
            return {"success": False, "error": "No database session in runtime context"}

        try:
            import uuid as _uuid

            from sqlalchemy import or_

            def _is_uuid(val: str) -> bool:
                try:
                    _uuid.UUID(val)
                    return True
                except ValueError:
                    return False

            id_filter = DatabaseConnection.id == connection_name if _is_uuid(connection_name) else None
            name_filter = DatabaseConnection.name == connection_name
            combined = or_(id_filter, name_filter) if id_filter is not None else name_filter

            result = await db.execute(
                select(DatabaseConnection).filter(
                    combined,
                    DatabaseConnection.database_type == "ELASTICSEARCH",
                    DatabaseConnection.tenant_id == tenant_id,
                    DatabaseConnection.deleted_at.is_(None),
                )
            )
            connection = result.scalar_one_or_none()

            if not connection:
                return {"success": False, "error": f"Connection '{connection_name}' not found"}

            # Get password if encrypted
            password = None
            if connection.password_encrypted:
                try:
                    password = connection.get_password()
                except Exception as e:
                    logger.error(f"Failed to decrypt password: {e}")
                    return {"success": False, "error": "Failed to decrypt connection password"}

            # Initialize Elasticsearch service
            from src.services.search.elasticsearch_service import ElasticsearchService

            es_service = ElasticsearchService(
                {
                    "host": connection.host,
                    "port": connection.port,
                    "username": connection.username,
                    "password": password,
                    "connection_params": connection.connection_params or {},
                }
            )

            stats = await es_service.get_index_stats(index_pattern)
            await es_service.close()

            if stats.get("success"):
                stats["message"] = f"Index has {stats['document_count']} documents"

            return stats

        except Exception as e:
            logger.error(f"Error getting index stats inner: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    except Exception as e:
        logger.error(f"Error getting index stats: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
