"""Canonical object names for agent access to shared application storage."""

from typing import Any
from urllib.parse import urlsplit
from uuid import UUID


def storage_tenant(runtime_context: Any = None, config: dict | None = None) -> str:
    context = runtime_context or (config or {}).get("_runtime_context")
    tenant = getattr(context, "tenant_id", None)
    if tenant is None:
        raise ValueError("Verified tenant context is required for storage access")
    return str(UUID(str(tenant)))


def tenant_object_key(value: str, bucket: str, tenant: str, *, prefix: bool = False) -> str:
    """Resolve relative names under tenants/<id>/; reject foreign explicit scopes.

    S3 keys are not filesystem paths: reject ambiguous forms instead of decoding
    or normalizing them differently for downloads, presigning and deletion.
    """
    if not isinstance(value, str) or any(ord(c) < 32 for c in value) or any(c in value for c in "\\%?#"):
        raise ValueError("Invalid storage object name")
    if value.startswith("s3://"):
        parsed = urlsplit(value)
        if parsed.netloc != bucket:
            raise ValueError("Storage object belongs to another bucket")
        value = parsed.path[1:]
    elif "://" in value or value.startswith("/"):
        raise ValueError("Expected a relative object name or an S3 URI")
    components = value.rstrip("/").split("/") if value else []
    if any(part in {"", ".", ".."} for part in components):
        raise ValueError("Invalid storage object path")
    root = f"tenants/{tenant}/"
    if components and components[0] in {"tenants", "data-uploads"}:
        if len(components) < 2 or components[1] != tenant:
            raise ValueError("Storage object does not belong to the current tenant")
        key = "/".join(components)
        if len(components) == 2:
            if not prefix:
                raise ValueError("An object name is required")
            return key + "/"
    else:
        key = root + "/".join(components)
    if not prefix and (not components or value.endswith("/")):
        raise ValueError("An object name is required")
    if prefix and value.endswith("/") and not key.endswith("/"):
        key += "/"
    return key
