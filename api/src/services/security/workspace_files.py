"""Bounded reads of owned workspace files, without following symlinks."""

import os
from pathlib import Path, PurePosixPath

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def relative_workspace_path(path: str, root: str) -> str:
    value = PurePosixPath(path)
    base = PurePosixPath(root)
    if not base.is_absolute() or not path or ".." in value.parts or "\x00" in path:
        raise ValueError("Invalid workspace path")
    if value.is_absolute():
        value = value.relative_to(base)
    if not value.parts:
        raise ValueError("A workspace file is required")
    return str(value)


def read_workspace_file(root: str, relative: str) -> bytes:
    parts = PurePosixPath(relative_workspace_path(relative, root)).parts
    descriptor = os.open(str(Path(root).resolve(strict=True)), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in parts[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        with os.fdopen(file_fd, "rb") as handle:
            import stat

            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ValueError("Upload must be a regular file")
            data = handle.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValueError("Upload exceeds 10 MiB")
        return data
    finally:
        os.close(descriptor)
