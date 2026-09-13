"""
Storage service for file upload and management.
"""

import asyncio
import hashlib
import mimetypes
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.storage import storage_config
from src.core.errors import ValidationError
from src.models import FileSource, FileType, UploadFile


class StorageService:
    """Service for managing file storage."""

    def __init__(self, db: AsyncSession):
        """Initialize storage service."""
        self.db = db
        self.config = storage_config

    def _get_file_type(self, mime_type: str) -> FileType:
        """Determine file type from MIME type."""
        if mime_type.startswith("image/"):
            return FileType.IMAGE
        elif mime_type.startswith("audio/"):
            return FileType.AUDIO
        elif mime_type.startswith("video/"):
            return FileType.VIDEO
        elif mime_type in [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/plain",
            "text/markdown",
            "text/csv",
        ]:
            return FileType.DOCUMENT
        else:
            return FileType.OTHER

    def _generate_file_key(
        self,
        tenant_id: UUID,
        _filename: str,
        extension: str,
    ) -> str:
        """Generate unique file key for storage."""
        # Format: tenant_id/year/month/uuid.ext
        now = datetime.now(UTC)
        file_uuid = uuid4()
        return f"{tenant_id}/{now.year}/{now.month:02d}/{file_uuid}{extension}"

    def _calculate_file_hash(self, file: BinaryIO) -> str:
        """Calculate SHA-256 hash of file content."""
        sha256 = hashlib.sha256()
        file.seek(0)
        while chunk := file.read(8192):
            sha256.update(chunk)
        file.seek(0)
        return sha256.hexdigest()

    def _validate_file(
        self,
        _filename: str,
        size: int,
        extension: str,
    ) -> None:
        """Validate file before upload."""
        # Check file size
        if size > self.config.MAX_FILE_SIZE:
            raise ValidationError(
                f"File size exceeds maximum allowed size of {self.config.MAX_FILE_SIZE / (1024 * 1024):.0f}MB"
            )

        # Check file extension
        if extension.lower() not in self.config.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"File type '{extension}' is not allowed. "
                f"Allowed types: {', '.join(sorted(self.config.ALLOWED_EXTENSIONS))}"
            )

    async def upload_file(
        self,
        file: BinaryIO,
        filename: str,
        tenant_id: UUID,
        created_by: UUID | None = None,
        source: FileSource = FileSource.UPLOAD,
    ) -> UploadFile:
        """
        Upload a file and create database record.

        Args:
            file: File object to upload
            filename: Original filename
            tenant_id: Tenant ID
            created_by: User ID who uploaded the file
            source: Source of the file

        Returns:
            UploadFile: Created file record

        Raises:
            ValidationError: If file validation fails
        """
        # Get file info
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)

        extension = Path(filename).suffix.lower()
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Validate file
        self._validate_file(filename, size, extension)

        # Generate file key
        file_key = self._generate_file_key(tenant_id, filename, extension)

        # Calculate file hash
        file_hash = self._calculate_file_hash(file)

        # Check for duplicate files
        stmt = select(UploadFile).where(
            UploadFile.tenant_id == tenant_id,
            UploadFile.hash == file_hash,
        )
        result = await self.db.execute(stmt)
        existing_file = result.scalar_one_or_none()

        if existing_file:
            # Return existing file instead of uploading duplicate
            return existing_file

        # Store file based on storage type
        if self.config.STORAGE_TYPE == "local":
            await self._store_local(file, file_key)
        elif self.config.STORAGE_TYPE == "s3":
            await self._store_s3(file, file_key)
        elif self.config.STORAGE_TYPE == "azure":
            await self._store_azure(file, file_key)

        # Create database record
        upload_file = UploadFile(
            tenant_id=tenant_id,
            created_by=created_by,
            name=filename,
            key=file_key,
            size=size,
            extension=extension,
            mime_type=mime_type,
            file_type=self._get_file_type(mime_type),
            source=source,
            storage_type=self.config.STORAGE_TYPE,
            hash=file_hash,
        )

        self.db.add(upload_file)
        await self.db.commit()
        await self.db.refresh(upload_file)

        return upload_file

    async def _store_local(self, file: BinaryIO, file_key: str) -> None:
        """Store file in local filesystem.

        Delegates blocking I/O to a thread to avoid stalling the event loop.
        """
        # Ensure storage directory exists
        self.config.ensure_local_storage()

        # Create full path
        file_path = self.config.local_storage_path / file_key

        # Read content before offloading (BinaryIO may not be thread-safe)
        file.seek(0)
        content = file.read()

        # Offload blocking mkdir + write to a thread
        def _write() -> None:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(content)

        await asyncio.to_thread(_write)

    async def _store_s3(self, file: BinaryIO, file_key: str) -> None:
        """Store file in S3. Use get_storage_service() from config/storage.py instead."""
        raise NotImplementedError("Use get_storage_service() from config/storage.py for S3 support")

    async def _store_azure(self, file: BinaryIO, file_key: str) -> None:
        """Store file in Azure Blob Storage."""
        raise NotImplementedError("Azure storage not yet implemented")

    async def get_file(self, file_id: UUID, tenant_id: UUID) -> UploadFile | None:
        """
        Get file by ID.

        Args:
            file_id: File ID
            tenant_id: Tenant ID for access control

        Returns:
            UploadFile or None if not found
        """
        stmt = select(UploadFile).where(
            UploadFile.id == file_id,
            UploadFile.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_file(self, file_id: UUID, tenant_id: UUID) -> bool:
        """
        Delete file.

        Args:
            file_id: File ID
            tenant_id: Tenant ID for access control

        Returns:
            bool: True if deleted, False if not found
        """
        file = await self.get_file(file_id, tenant_id)
        if not file:
            return False

        # Delete from storage
        if self.config.STORAGE_TYPE == "local":
            file_path = self.config.local_storage_path / file.key
            if file_path.exists():
                file_path.unlink()

        # Delete from database
        await self.db.delete(file)
        await self.db.commit()

        return True

    async def list_files(
        self,
        tenant_id: UUID,
        file_type: FileType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[UploadFile]:
        """
        List files for a tenant.

        Args:
            tenant_id: Tenant ID
            file_type: Optional file type filter
            limit: Maximum number of files to return
            offset: Number of files to skip

        Returns:
            List of UploadFile objects
        """
        stmt = select(UploadFile).where(UploadFile.tenant_id == tenant_id)

        if file_type:
            stmt = stmt.where(UploadFile.file_type == file_type)

        stmt = stmt.order_by(UploadFile.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    def get_file_path(self, file: UploadFile) -> Path | None:
        """
        Get local file path.

        Args:
            file: UploadFile object

        Returns:
            Path to file if using local storage, None otherwise
        """
        if self.config.STORAGE_TYPE == "local":
            return self.config.local_storage_path / file.key
        return None

    def get_file_url(self, file: UploadFile) -> str:
        """
        Get file URL.

        Args:
            file: UploadFile object

        Returns:
            URL to access the file
        """
        # For local storage, return API endpoint
        if self.config.STORAGE_TYPE == "local":
            return f"/api/files/{file.id}"
        # For cloud storage, use get_storage_service() from config/storage.py
        return f"/api/files/{file.id}"
