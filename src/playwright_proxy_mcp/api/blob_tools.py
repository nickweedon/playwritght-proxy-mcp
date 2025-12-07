"""
MCP tools for blob storage retrieval and management

These tools allow MCP clients to retrieve, list, and delete blobs
that were stored by the proxy for large binary data.
"""

import base64
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Global blob manager instance - will be set by server.py
_blob_manager = None


def set_blob_manager(manager: Any) -> None:
    """Set the global blob manager instance"""
    global _blob_manager
    _blob_manager = manager


async def get_blob(blob_id: str) -> dict[str, Any]:
    """
    Retrieve binary data from blob storage by ID.

    This tool retrieves large binary data (like screenshots or PDFs) that were
    stored as blobs to reduce token usage. The data is returned as base64-encoded.

    Args:
        blob_id: Blob identifier (e.g., blob://1733577600-a3f2c1d9e4b5.png)

    Returns:
        Dictionary with blob data and metadata

    Raises:
        ValueError: If blob not found or blob manager not initialized
    """
    if _blob_manager is None:
        raise ValueError("Blob manager not initialized")

    try:
        # Get blob data
        binary_data = await _blob_manager.retrieve_blob(blob_id)

        # Get metadata
        metadata = await _blob_manager.get_blob_metadata(blob_id)

        # Encode to base64
        base64_data = base64.b64encode(binary_data).decode("utf-8")

        # Create data URI if we have MIME type
        mime_type = metadata.get("mime_type", "application/octet-stream")
        data_uri = f"data:{mime_type};base64,{base64_data}"

        return {
            "blob_id": blob_id,
            "data": data_uri,
            "mime_type": mime_type,
            "size_bytes": len(binary_data),
            "created_at": metadata.get("created_at"),
            "expires_at": metadata.get("expires_at"),
        }

    except Exception as e:
        logger.error(f"Failed to retrieve blob {blob_id}: {e}")
        raise ValueError(f"Failed to retrieve blob: {e}") from e


async def list_blobs(
    mime_type: str | None = None, tags: list[str] | None = None, limit: int = 100
) -> dict[str, Any]:
    """
    List available blobs in storage with optional filtering.

    Useful for finding screenshots, PDFs, or other binary data from previous
    browser automation sessions.

    Args:
        mime_type: Filter by MIME type (e.g., "image/png", "application/pdf")
        tags: Filter by tags (list of tag strings)
        limit: Maximum number of results (default: 100)

    Returns:
        Dictionary with list of blob metadata

    Raises:
        ValueError: If blob manager not initialized
    """
    if _blob_manager is None:
        raise ValueError("Blob manager not initialized")

    try:
        blobs = await _blob_manager.list_blobs(
            mime_type=mime_type, tags=tags, limit=limit
        )

        return {
            "count": len(blobs),
            "blobs": blobs,
            "filters": {
                "mime_type": mime_type,
                "tags": tags,
                "limit": limit,
            },
        }

    except Exception as e:
        logger.error(f"Failed to list blobs: {e}")
        raise ValueError(f"Failed to list blobs: {e}") from e


async def delete_blob(blob_id: str) -> dict[str, Any]:
    """
    Delete a blob from storage.

    Use this to manually remove blobs before their automatic expiration.
    This can help free up storage space.

    Args:
        blob_id: Blob identifier to delete

    Returns:
        Dictionary with deletion status

    Raises:
        ValueError: If blob manager not initialized
    """
    if _blob_manager is None:
        raise ValueError("Blob manager not initialized")

    try:
        success = await _blob_manager.delete_blob(blob_id)

        return {
            "blob_id": blob_id,
            "deleted": success,
            "message": "Blob deleted successfully" if success else "Failed to delete blob",
        }

    except Exception as e:
        logger.error(f"Failed to delete blob {blob_id}: {e}")
        raise ValueError(f"Failed to delete blob: {e}") from e
