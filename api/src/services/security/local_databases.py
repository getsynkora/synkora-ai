"""Local databases are operator-provisioned, read-only tenant assets."""

import os
import re
from pathlib import Path
from uuid import UUID


def local_database_path(value: str | None, tenant_id, *, memory: bool = False) -> str:
    tenant = str(UUID(str(tenant_id)))  # Never accept an absent/untrusted tenant context.
    if memory and value in (None, "", ":memory:"):
        return ":memory:"
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise ValueError("Use a tenant database filename, not a filesystem path")
    root = Path(os.environ.get("LOCAL_DATABASE_ROOT", "storage/databases")).absolute()
    target = root / tenant / value
    # Reject symlinks in every component, including deployment root ancestors.
    # NOTE (TOCTOU): There is an inherent race between this symlink check and the
    # subsequent file open by DuckDB/SQLite.  A fully race-free solution would
    # require opening the file with O_NOFOLLOW and passing the fd to the database
    # engine, which neither duckdb nor sqlite3 Python bindings support.  The risk
    # is mitigated by the restrictive filename regex above (no path separators,
    # no ".." components) and the requirement that the storage root is operator-
    # controlled and not writable by tenant workloads.
    for path in (target, *target.parents):
        if path.is_symlink():
            raise ValueError("Database symlinks are forbidden")
    if not target.is_file() or target.stat().st_nlink != 1:
        raise ValueError("Tenant database must be provisioned as a regular, unlinked file")
    return str(target)
