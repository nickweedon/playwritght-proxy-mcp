"""
Type Definitions

Define TypedDict classes for playwright proxy and blob storage data structures.
"""

from typing import TypedDict


class BlobReference(TypedDict, total=False):
    """
    Reference to a blob stored in blob storage.

    Used when large binary data (screenshots, PDFs) is stored as a blob
    instead of being returned inline.
    """

    blob_id: str
    size_kb: int
    mime_type: str
    blob_retrieval_tool: str
    expires_at: str


class BlobMetadata(TypedDict, total=False):
    """Metadata about a stored blob."""

    blob_id: str
    mime_type: str
    size_bytes: int
    created_at: str
    expires_at: str
    tags: list[str]


class PlaywrightToolResponse(TypedDict, total=False):
    """
    Generic response from a playwright tool.

    May contain blob references instead of inline binary data.
    """

    success: bool
    message: str | None
    data: dict[str, str] | None
    blob_id: str | None


class NavigationResponse(TypedDict, total=False):
    """
    Response for browser_navigate and browser_snapshot with pagination support.

    Used when navigating to URLs or capturing snapshots with advanced filtering,
    pagination, and output formatting.
    """

    success: bool
    url: str
    cache_key: str
    total_items: int
    offset: int
    limit: int
    has_more: bool
    snapshot: str | None
    error: str | None
    query_applied: str | None
    output_format: str
