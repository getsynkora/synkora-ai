"""
Connector registry — maps DataSourceType (lowercase) → BaseConnector class.

How to register a new connector
---------------------------------
Option A — built-in connector (add to this file):
    from src.services.company_brain.connectors.my_connector import MyConnector
    CONNECTOR_REGISTRY["my_source"] = MyConnector

Option B — CUSTOM type (no code change needed):
    Set DataSource.type = CUSTOM and populate:
      DataSource.custom_connector_config = {
          "connector_class": "mypackage.mymodule.MyConnector",
          ...init_kwargs...
      }
    The registry will import and instantiate it dynamically.

Lookup
------
    connector_cls = get_connector_class("slack")
    connector = connector_cls(config=data_source_config)
"""

import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.company_brain.connectors.base import BaseConnector

logger = logging.getLogger(__name__)

# source_type (lowercase) → connector class
# Add entries here as new built-in connectors are implemented.
CONNECTOR_REGISTRY: dict[str, type] = {}


def _register_builtins() -> None:
    """Lazily register all built-in connectors at first use."""
    try:
        from src.services.company_brain.connectors.slack_connector import SlackConnector

        CONNECTOR_REGISTRY.setdefault("slack", SlackConnector)
    except ImportError:
        pass

    # Future built-in connectors — add here as they are implemented:
    # from src.services.company_brain.connectors.jira_connector import JiraBrainConnector
    # CONNECTOR_REGISTRY.setdefault("jira", JiraBrainConnector)
    #
    # from src.services.company_brain.connectors.github_connector import GitHubConnector
    # CONNECTOR_REGISTRY.setdefault("github", GitHubConnector)


_builtins_registered = False


def get_connector_class(source_type: str, custom_config: dict | None = None) -> type | None:
    """
    Return the connector class for a given source_type string.

    Args:
        source_type:   DataSourceType value, e.g. "SLACK" or "slack" (case-insensitive).
        custom_config: For CUSTOM type — must contain "connector_class" key with
                       a fully-qualified Python class path.

    Returns:
        The connector class, or None if not found.
    """
    global _builtins_registered
    if not _builtins_registered:
        _register_builtins()
        _builtins_registered = True

    key = source_type.lower()

    # CUSTOM type: dynamically import from connector_class field
    if key == "custom" and custom_config:
        return _load_dynamic(custom_config.get("connector_class", ""))

    return CONNECTOR_REGISTRY.get(key)


def get_connector(
    source_type: str,
    config: dict,
    custom_connector_config: dict | None = None,
) -> "BaseConnector | None":
    """
    Instantiate a connector for a DataSource.

    Args:
        source_type:             DataSource.type (e.g. "SLACK")
        config:                  DataSource.config merged with decrypted credentials
        custom_connector_config: DataSource.custom_connector_config (for CUSTOM type)
    """
    cls = get_connector_class(source_type, custom_connector_config)
    if cls is None:
        logger.warning("No connector registered for source_type=%s", source_type)
        return None

    # For CUSTOM type, merge custom_connector_config (minus connector_class) into config
    merged_config = dict(config)
    if custom_connector_config:
        extra = {k: v for k, v in custom_connector_config.items() if k != "connector_class"}
        merged_config.update(extra)

    try:
        return cls(config=merged_config)
    except Exception as exc:
        logger.error("Failed to instantiate connector %s: %s", cls.__name__, exc)
        return None


def list_registered_connectors() -> list[str]:
    """Return a list of all registered source type strings."""
    global _builtins_registered
    if not _builtins_registered:
        _register_builtins()
        _builtins_registered = True
    return sorted(CONNECTOR_REGISTRY.keys())


def _load_dynamic(class_path: str) -> type | None:
    """Dynamically import a connector class from a dotted path."""
    if not class_path or "." not in class_path:
        logger.error("Invalid connector_class path: %r", class_path)
        return None
    module_path, class_name = class_path.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except Exception as exc:
        logger.error("Failed to import connector class %r: %s", class_path, exc)
        return None
