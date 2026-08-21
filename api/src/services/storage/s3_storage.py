"""S3 storage service for file management."""

import logging
import mimetypes
import os
from datetime import UTC, datetime
from io import BytesIO
from typing import BinaryIO
from urllib.parse import unquote, urlsplit
from uuid import UUID

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3StorageService:
    """Service for managing file storage in AWS S3."""

    def __init__(
        self,
        bucket_name: str | None = None,
        region: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ):
        """
        Initialize S3 storage service.

        Args:
            bucket_name: S3 bucket name (defaults to env var)
            region: AWS region (defaults to env var)
            access_key: AWS access key (defaults to env var)
            secret_key: AWS secret key (defaults to env var)
        """
        self.bucket_name = bucket_name or os.getenv("AWS_S3_BUCKET")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")

        # Initialize S3 client
        # Always use explicit credentials from env vars for consistency with MinIO
        env_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        env_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        session_kwargs = {"region_name": self.region}

        # Prefer passed credentials, then env vars
        final_access_key = access_key or env_access_key
        final_secret_key = secret_key or env_secret_key

        if final_access_key and final_secret_key:
            session_kwargs["aws_access_key_id"] = final_access_key
            session_kwargs["aws_secret_access_key"] = final_secret_key

        # Support custom endpoint URL for MinIO or other S3-compatible services
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        if endpoint_url:
            session_kwargs["endpoint_url"] = endpoint_url

        # Remembered so extract_own_key_from_url() can recognize URLs pointing at our
        # own storage (signed with either endpoint) without re-reading env vars.
        self.internal_endpoint_url = endpoint_url
        self.public_endpoint_url = os.getenv("AWS_PUBLIC_ENDPOINT_URL")

        # Force signature version 4 for MinIO compatibility
        # This ensures presigned URLs use X-Amz-Expires instead of Expires
        boto_config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},  # Force path-style for MinIO
        )
        session_kwargs["config"] = boto_config

        self.s3_client = boto3.client("s3", **session_kwargs)

        # Create a separate client for presigned URLs using public endpoint
        # This ensures browser-accessible URLs have correct host in signature
        public_endpoint = self.public_endpoint_url
        logger.debug(f"S3 config: endpoint_url={endpoint_url}, public_endpoint={public_endpoint}")

        if endpoint_url and public_endpoint and endpoint_url != public_endpoint:
            # Create public client with same config but different endpoint
            public_session_kwargs = session_kwargs.copy()
            public_session_kwargs["endpoint_url"] = public_endpoint
            self.presigned_client = boto3.client("s3", **public_session_kwargs)
            logger.info(f"S3 clients initialized - Operations: {endpoint_url}, Presigned URLs: {public_endpoint}")
        else:
            # Use same client if no separate public endpoint
            self.presigned_client = self.s3_client
            if not public_endpoint:
                logger.warning(
                    f"AWS_PUBLIC_ENDPOINT_URL not set - presigned URLs will use internal endpoint: {endpoint_url}"
                )
            logger.info(f"S3 client initialized with endpoint: {endpoint_url}")

        if not self.bucket_name:
            raise ValueError("S3 bucket name must be provided or set in AWS_S3_BUCKET env var")

    def upload_file(
        self,
        file_content: bytes | BinaryIO,
        key: str,
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """
        Upload a file to S3.

        Args:
            file_content: File content as bytes or file-like object
            key: S3 object key (path)
            content_type: MIME type of the file
            metadata: Additional metadata to store with the file

        Returns:
            dict: Upload result with bucket, key, and URL

        Raises:
            Exception: If upload fails
        """
        try:
            # Convert bytes to BytesIO if needed
            if isinstance(file_content, bytes):
                file_obj = BytesIO(file_content)
            else:
                file_obj = file_content

            # Determine content type if not provided
            if not content_type:
                content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"

            # Prepare extra args
            extra_args = {"ContentType": content_type}
            if metadata:
                extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}

            # Upload file
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                key,
                ExtraArgs=extra_args,
            )

            logger.info(f"Successfully uploaded file to S3: {key}")

            return {
                "bucket": self.bucket_name,
                "key": key,
                "url": f"s3://{self.bucket_name}/{key}",
                "region": self.region,
            }

        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise Exception(f"S3 upload failed: {str(e)}")

    def download_file(self, key: str) -> bytes:
        """
        Download a file from S3.

        Args:
            key: S3 object key

        Returns:
            bytes: File content

        Raises:
            Exception: If download fails
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()

        except ClientError as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise Exception(f"S3 download failed: {str(e)}")

    def delete_file(self, key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            key: S3 object key

        Returns:
            bool: True if successful

        Raises:
            Exception: If deletion fails
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Successfully deleted file from S3: {key}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            raise Exception(f"S3 deletion failed: {str(e)}")

    def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        method: str = "get_object",
    ) -> str:
        """
        Generate a presigned URL for temporary access to a file.

        Args:
            key: S3 object key or S3 URI (s3://bucket/key)
            expiration: URL expiration time in seconds (default: 1 hour)
            method: S3 method (get_object, put_object, etc.)

        Returns:
            str: Presigned URL

        Raises:
            Exception: If URL generation fails
        """
        try:
            # Extract key from S3 URI if needed
            if key.startswith("s3://"):
                # Format: s3://bucket/key
                parts = key.replace("s3://", "").split("/", 1)
                if len(parts) == 2:
                    actual_key = parts[1]
                else:
                    raise ValueError(f"Invalid S3 URI format: {key}")
            else:
                actual_key = key

            # Log presigned URL generation
            logger.debug(f"Generating presigned URL for key: {actual_key}, expiration: {expiration}s")

            # Use presigned_client which is configured with public endpoint
            # This ensures the signature includes the correct host header
            url = self.presigned_client.generate_presigned_url(
                method,
                Params={"Bucket": self.bucket_name, "Key": actual_key},
                ExpiresIn=expiration,
            )

            logger.debug(f"Presigned URL: {url[:150]}...")

            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise Exception(f"Presigned URL generation failed: {str(e)}")

    def file_exists(self, key: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            key: S3 object key

        Returns:
            bool: True if file exists
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False

    def get_file_metadata(self, key: str) -> dict:
        """
        Get metadata for a file in S3.

        Args:
            key: S3 object key

        Returns:
            dict: File metadata including size, content_type, last_modified

        Raises:
            Exception: If metadata retrieval fails
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return {
                "size": response["ContentLength"],
                "content_type": response.get("ContentType"),
                "last_modified": response["LastModified"].isoformat() if response.get("LastModified") else None,
                "metadata": response.get("Metadata", {}),
                "etag": response["ETag"].strip('"'),
            }

        except ClientError as e:
            logger.error(f"Failed to get file metadata from S3: {e}")
            raise Exception(f"S3 metadata retrieval failed: {str(e)}")

    def list_files(self, prefix: str = "", max_keys: int = 1000) -> list[dict]:
        """
        List files in S3 with a given prefix.

        Args:
            prefix: Key prefix to filter by
            max_keys: Maximum number of keys to return

        Returns:
            list: List of file metadata dicts

        Raises:
            Exception: If listing fails
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys,
            )

            files = []
            for obj in response.get("Contents", []):
                files.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat() if obj.get("LastModified") else None,
                        "etag": obj["ETag"].strip('"'),
                    }
                )

            return files

        except ClientError as e:
            logger.error(f"Failed to list files in S3: {e}")
            raise Exception(f"S3 listing failed: {str(e)}")

    def generate_key(
        self,
        tenant_id: UUID,
        source_type: str,
        filename: str,
        timestamp: datetime | None = None,
    ) -> str:
        """
        Generate a standardized S3 key for a file.

        Args:
            tenant_id: Tenant UUID
            source_type: Data source type (SLACK, gmail, etc.)
            filename: Original filename
            timestamp: Optional timestamp (defaults to now)

        Returns:
            str: S3 key path
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        # Format: tenants/{tenant_id}/{source_type}/{year}/{month}/{day}/{filename}
        date_path = timestamp.strftime("%Y/%m/%d")
        key = f"tenants/{tenant_id}/{source_type}/{date_path}/{filename}"

        return key

    def copy_file(self, source_key: str, dest_key: str) -> dict:
        """
        Copy a file within S3.

        Args:
            source_key: Source S3 object key
            dest_key: Destination S3 object key

        Returns:
            dict: Copy result

        Raises:
            Exception: If copy fails
        """
        try:
            copy_source = {"Bucket": self.bucket_name, "Key": source_key}
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=dest_key,
            )

            logger.info(f"Successfully copied file in S3: {source_key} -> {dest_key}")

            return {
                "bucket": self.bucket_name,
                "source_key": source_key,
                "dest_key": dest_key,
            }

        except ClientError as e:
            logger.error(f"Failed to copy file in S3: {e}")
            raise Exception(f"S3 copy failed: {str(e)}")

    async def upload_file_content(
        self,
        file_content: bytes,
        key: str,
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        Upload file content to S3 and return the URL (async version).

        Args:
            file_content: File content as bytes
            key: S3 object key (path)
            content_type: MIME type of the file
            metadata: Additional metadata to store with the file

        Returns:
            str: S3 URL (s3://bucket/key format)

        Raises:
            Exception: If upload fails
        """
        result = self.upload_file(file_content, key, content_type, metadata)
        return result["url"]

    async def download_file_content(self, s3_url: str) -> bytes:
        """
        Download file content from S3 URL (async version).

        Args:
            s3_url: S3 URL (s3://bucket/key or https://... format)

        Returns:
            bytes: File content

        Raises:
            Exception: If download fails
        """
        # Extract key from S3 URL
        if s3_url.startswith("s3://"):
            # Format: s3://bucket/key
            parts = s3_url.replace("s3://", "").split("/", 1)
            if len(parts) == 2:
                key = parts[1]
            else:
                raise ValueError(f"Invalid S3 URL format: {s3_url}")
        elif s3_url.startswith("https://"):
            # Format: https://bucket.s3.region.amazonaws.com/key
            # or https://s3.region.amazonaws.com/bucket/key
            if ".s3." in s3_url or ".s3-" in s3_url:
                # Extract key from URL
                parts = s3_url.split("/", 3)
                if len(parts) >= 4:
                    key = parts[3]
                else:
                    raise ValueError(f"Invalid S3 URL format: {s3_url}")
            else:
                raise ValueError(f"Invalid S3 URL format: {s3_url}")
        else:
            # Assume it's already a key
            key = s3_url

        return self.download_file(key)

    def extract_own_key_from_url(self, url: str) -> str | None:
        """
        Return the S3 object key if `url` points at this service's own storage
        (matches our internal or public endpoint + bucket), or None otherwise.

        Presigned URLs are signed with AWS_PUBLIC_ENDPOINT_URL for browser access
        (e.g. "http://localhost:9000" in dev), which isn't reachable from a
        server-side fetch and gets correctly SSRF-blocked. This lets callers
        recognize "this is our own storage" and fetch bytes directly via the S3
        client instead, without weakening SSRF protection for any other URL.
        """
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        known_origins = {o for o in (self.internal_endpoint_url, self.public_endpoint_url) if o}
        if origin not in known_origins:
            return None

        prefix = f"/{self.bucket_name}/"
        if not parsed.path.startswith(prefix):
            return None

        return unquote(parsed.path[len(prefix) :])

    async def download_if_own_url(self, url: str) -> bytes | None:
        """Download bytes directly via the S3 client if `url` is our own storage, else None."""
        key = self.extract_own_key_from_url(url)
        if key is None:
            return None
        return self.download_file(key)

    async def upload_file_streaming(
        self,
        file_stream,
        key: str,
        content_type: str | None = None,
        metadata: dict | None = None,
        chunk_size: int = 5 * 1024 * 1024,  # 5MB chunks for multipart
    ) -> dict:
        """
        Upload a file to S3 using streaming multipart upload.

        PERFORMANCE: This method streams file chunks directly to S3 without
        loading the entire file into memory. Ideal for large files.

        Args:
            file_stream: Async file-like object with read() method
            key: S3 object key (path)
            content_type: MIME type of the file
            metadata: Additional metadata to store with the file
            chunk_size: Size of each chunk for multipart upload (default 5MB)

        Returns:
            dict: Upload result with bucket, key, and URL

        Raises:
            Exception: If upload fails
        """
        import asyncio

        try:
            # Determine content type if not provided
            if not content_type:
                content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"

            # Prepare extra args
            extra_args = {"ContentType": content_type}
            if metadata:
                extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}

            # Initialize multipart upload
            mpu = self.s3_client.create_multipart_upload(Bucket=self.bucket_name, Key=key, **extra_args)
            upload_id = mpu["UploadId"]

            parts = []
            part_number = 1
            total_bytes = 0

            try:
                while True:
                    # Read chunk from stream
                    chunk = await file_stream.read(chunk_size)
                    if not chunk:
                        break

                    total_bytes += len(chunk)

                    # Upload part using run_in_executor to avoid blocking
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: self.s3_client.upload_part(
                            Bucket=self.bucket_name,
                            Key=key,
                            UploadId=upload_id,
                            PartNumber=part_number,
                            Body=chunk,
                        ),
                    )

                    parts.append({"PartNumber": part_number, "ETag": response["ETag"]})
                    part_number += 1

                # Complete multipart upload
                if parts:
                    await loop.run_in_executor(
                        None,
                        lambda: self.s3_client.complete_multipart_upload(
                            Bucket=self.bucket_name, Key=key, UploadId=upload_id, MultipartUpload={"Parts": parts}
                        ),
                    )
                else:
                    # No parts means empty file, abort and use regular upload
                    self.s3_client.abort_multipart_upload(Bucket=self.bucket_name, Key=key, UploadId=upload_id)
                    # Upload empty file
                    self.s3_client.put_object(Bucket=self.bucket_name, Key=key, Body=b"", **extra_args)

                logger.info(f"Successfully uploaded file to S3 via streaming: {key} ({total_bytes} bytes)")

                return {
                    "bucket": self.bucket_name,
                    "key": key,
                    "url": f"s3://{self.bucket_name}/{key}",
                    "region": self.region,
                    "size": total_bytes,
                }

            except Exception as e:
                # Abort multipart upload on error
                logger.error(f"Error during streaming upload, aborting: {e}")
                try:
                    self.s3_client.abort_multipart_upload(Bucket=self.bucket_name, Key=key, UploadId=upload_id)
                except Exception:
                    pass
                raise

        except ClientError as e:
            logger.error(f"Failed to upload file to S3 via streaming: {e}")
            raise Exception(f"S3 streaming upload failed: {str(e)}")


# Singleton instance for consistent S3 client configuration
_s3_storage_instance: S3StorageService | None = None


def get_s3_storage() -> S3StorageService:
    """
    Get the singleton S3StorageService instance.

    Using a singleton ensures consistent S3 client configuration across all usages,
    preventing signature mismatches from configuration differences between instances.

    Returns:
        S3StorageService: The singleton instance

    Raises:
        ValueError: If S3 is not configured (AWS_S3_BUCKET not set)
    """
    global _s3_storage_instance
    if _s3_storage_instance is None:
        _s3_storage_instance = S3StorageService()
        logger.info("Created singleton S3StorageService instance")
    return _s3_storage_instance
