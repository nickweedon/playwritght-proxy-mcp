"""
Blob storage manager for playwright binary data

Wraps mcp-mapped-resource-lib to provide efficient storage and retrieval
of large binary data like screenshots, PDFs, and videos.
"""

import asyncio
import base64
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from mcp_mapped_resource_lib import BlobStorage

from .config import BlobConfig

logger = logging.getLogger(__name__)


class PlaywrightBlobManager:
    """Manages blob storage for playwright binary data"""

    def __init__(self, config: BlobConfig) -> None:
        """
        Initialize blob storage manager.

        Args:
            config: Blob storage configuration
        """
        self.config = config
        self._cleanup_task: asyncio.Task | None = None

        # Ensure storage directory exists
        storage_path = Path(config["storage_root"])
        storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize blob storage
        self.storage = BlobStorage(
            storage_root=config["storage_root"],
            max_size_mb=config["max_size_mb"],
            allowed_mime_types=[
                "image/*",  # Screenshots
                "application/pdf",  # PDFs
                "video/*",  # Session videos
                "application/x-tar",  # Trace files
                "application/zip",  # Archive files
            ],
            enable_deduplication=True,
            default_ttl_hours=config["ttl_hours"],
        )

        logger.info(f"Blob storage initialized at {config['storage_root']}")

    async def store_base64_data(
        self, base64_data: str, filename: str, tags: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Convert base64 data to binary and store in blob storage.

        Args:
            base64_data: Base64-encoded data (may include data URI prefix)
            filename: Suggested filename for the blob
            tags: Optional tags for categorization

        Returns:
            Dictionary with blob_id and metadata
        """
        try:
            # Extract MIME type and data from data URI if present
            mime_type = "application/octet-stream"
            data_part = base64_data

            # Check for data URI format: data:mime/type;base64,<data>
            data_uri_match = re.match(r"data:([^;]+);base64,(.+)", base64_data)
            if data_uri_match:
                mime_type = data_uri_match.group(1)
                data_part = data_uri_match.group(2)

            # Decode base64 to binary
            binary_data = base64.b64decode(data_part)

            # Upload to blob storage
            result = self.storage.upload_blob(
                data=binary_data, filename=filename, tags=tags or []
            )

            # Calculate metadata
            size_bytes = len(binary_data)
            expires_at = datetime.now() + timedelta(hours=self.config["ttl_hours"])

            logger.info(
                f"Stored blob {result['blob_id']} ({size_bytes} bytes, type: {mime_type})"
            )

            return {
                "blob_id": result["blob_id"],
                "size_bytes": size_bytes,
                "mime_type": mime_type,
                "created_at": result.get("created_at", datetime.now().isoformat()),
                "expires_at": expires_at.isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to store blob: {e}")
            raise ValueError(f"Failed to store blob: {e}") from e

    async def retrieve_blob(self, blob_id: str) -> bytes:
        """
        Retrieve binary data by blob ID.

        Args:
            blob_id: Blob identifier (e.g., blob://timestamp-hash.png)

        Returns:
            Binary data

        Raises:
            ValueError: If blob not found
        """
        try:
            # Remove blob:// prefix if present
            clean_id = blob_id.replace("blob://", "")

            data = self.storage.get_blob(clean_id)
            logger.debug(f"Retrieved blob {blob_id} ({len(data)} bytes)")
            return data

        except Exception as e:
            logger.error(f"Failed to retrieve blob {blob_id}: {e}")
            raise ValueError(f"Blob not found: {blob_id}") from e

    async def get_blob_metadata(self, blob_id: str) -> dict[str, Any]:
        """
        Get metadata for a blob without retrieving the data.

        Args:
            blob_id: Blob identifier

        Returns:
            Metadata dictionary

        Raises:
            ValueError: If blob not found
        """
        try:
            # Remove blob:// prefix if present
            clean_id = blob_id.replace("blob://", "")

            metadata = self.storage.get_metadata(clean_id)
            return metadata

        except Exception as e:
            logger.error(f"Failed to get metadata for blob {blob_id}: {e}")
            raise ValueError(f"Blob not found: {blob_id}") from e

    async def list_blobs(
        self,
        mime_type: str | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        List available blobs with optional filtering.

        Args:
            mime_type: Filter by MIME type (e.g., "image/png")
            tags: Filter by tags
            limit: Maximum number of results

        Returns:
            List of blob metadata dictionaries
        """
        try:
            # Get all blobs (mcp-mapped-resource-lib doesn't have built-in filtering)
            storage_path = Path(self.config["storage_root"])
            blob_files = list(storage_path.glob("blob_*"))

            results = []
            for blob_file in blob_files[:limit]:
                try:
                    blob_id = blob_file.name
                    metadata = self.storage.get_metadata(blob_id)

                    # Apply filters
                    if mime_type and metadata.get("mime_type") != mime_type:
                        continue

                    if tags:
                        blob_tags = metadata.get("tags", [])
                        if not any(tag in blob_tags for tag in tags):
                            continue

                    results.append(
                        {
                            "blob_id": f"blob://{blob_id}",
                            "mime_type": metadata.get("mime_type"),
                            "size_bytes": metadata.get("size_bytes"),
                            "created_at": metadata.get("created_at"),
                            "expires_at": metadata.get("expires_at"),
                            "tags": metadata.get("tags", []),
                        }
                    )

                except Exception as e:
                    logger.debug(f"Skipping blob {blob_file.name}: {e}")
                    continue

            logger.debug(f"Listed {len(results)} blobs")
            return results

        except Exception as e:
            logger.error(f"Failed to list blobs: {e}")
            return []

    async def delete_blob(self, blob_id: str) -> bool:
        """
        Delete a blob from storage.

        Args:
            blob_id: Blob identifier

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Remove blob:// prefix if present
            clean_id = blob_id.replace("blob://", "")

            self.storage.delete_blob(clean_id)
            logger.info(f"Deleted blob {blob_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete blob {blob_id}: {e}")
            return False

    async def cleanup_expired(self) -> int:
        """
        Cleanup expired blobs based on TTL.

        Returns:
            Number of blobs deleted
        """
        try:
            from mcp_mapped_resource_lib import maybe_cleanup_expired_blobs

            deleted_count = maybe_cleanup_expired_blobs(self.config["storage_root"])
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired blobs")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired blobs: {e}")
            return 0

    async def start_cleanup_task(self) -> None:
        """Start periodic cleanup task for expired blobs"""
        if self._cleanup_task is not None:
            logger.warning("Cleanup task already running")
            return

        interval_seconds = self.config["cleanup_interval_minutes"] * 60

        async def cleanup_loop() -> None:
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    deleted = await self.cleanup_expired()
                    logger.debug(f"Periodic cleanup: {deleted} blobs deleted")
                except asyncio.CancelledError:
                    logger.info("Cleanup task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(
            f"Started blob cleanup task (interval: {self.config['cleanup_interval_minutes']} minutes)"
        )

    async def stop_cleanup_task(self) -> None:
        """Stop periodic cleanup task"""
        if self._cleanup_task is None:
            return

        self._cleanup_task.cancel()
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass

        self._cleanup_task = None
        logger.info("Stopped blob cleanup task")
