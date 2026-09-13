"""Canonical, tenant-scoped keys for exported reports."""

from pathlib import Path, PurePosixPath
from uuid import UUID


def report_key(value: str, tenant_id: UUID) -> str:
    if not isinstance(value, str) or any(ord(c) < 32 for c in value) or any(c in value for c in "\\%?#"):
        raise ValueError("Invalid report key")
    parts = value.split("/")
    if len(parts) < 3 or parts[:2] != ["reports", str(tenant_id)] or any(p in {"", ".", ".."} for p in parts):
        raise ValueError("Report does not belong to this tenant")
    if PurePosixPath(value).is_absolute():
        raise ValueError("Invalid report key")
    return value


def local_report_path(root: Path, key: str, tenant_id: UUID) -> Path:
    key = report_key(key, tenant_id)
    root = root.resolve()
    tenant_root = root / "reports" / str(tenant_id)
    path = root / key
    # Reject symlink components, including a tenant directory pointing elsewhere.
    current = root
    for part in key.split("/"):
        current /= part
        if current.is_symlink():
            raise ValueError("Report symlinks are not permitted")
    resolved = path.resolve()
    if not resolved.is_relative_to(tenant_root):
        raise ValueError("Invalid report path")
    return resolved
