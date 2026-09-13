"""Bound upload buffering even when a client supplies no size metadata."""

from fastapi import HTTPException, UploadFile


async def read_bounded_upload(file: UploadFile, max_bytes: int) -> bytes:
    content = bytearray()
    while True:
        chunk = await file.read(min(65536, max_bytes - len(content) + 1))
        if not chunk:
            return bytes(content)
        content.extend(chunk)
        if len(content) > max_bytes:
            raise HTTPException(status_code=413, detail="File exceeds maximum size")
