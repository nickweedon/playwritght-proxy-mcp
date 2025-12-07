"""
Tests for type definitions
"""

from playwright_proxy_mcp.types import (
    BlobMetadata,
    BlobReference,
    PlaywrightToolResponse,
)


class TestTypes:
    """Tests for TypedDict definitions."""

    def test_blob_reference_type(self):
        """Test BlobReference TypedDict."""
        blob_ref: BlobReference = {
            "blob_id": "blob://test-123.png",
            "size_kb": 50,
            "mime_type": "image/png",
            "blob_retrieval_tool": "get_blob",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        assert blob_ref["blob_id"] == "blob://test-123.png"
        assert blob_ref["size_kb"] == 50
        assert blob_ref["mime_type"] == "image/png"
        assert blob_ref["blob_retrieval_tool"] == "get_blob"
        assert blob_ref["expires_at"] == "2024-01-02T00:00:00Z"

    def test_blob_reference_partial(self):
        """Test BlobReference with partial data (total=False)."""
        blob_ref: BlobReference = {
            "blob_id": "blob://test.png",
        }

        assert blob_ref["blob_id"] == "blob://test.png"

    def test_blob_metadata_type(self):
        """Test BlobMetadata TypedDict."""
        metadata: BlobMetadata = {
            "blob_id": "blob://test.png",
            "mime_type": "image/png",
            "size_bytes": 1024,
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
            "tags": ["screenshot", "test"],
        }

        assert metadata["blob_id"] == "blob://test.png"
        assert metadata["mime_type"] == "image/png"
        assert metadata["size_bytes"] == 1024
        assert metadata["created_at"] == "2024-01-01T00:00:00Z"
        assert metadata["expires_at"] == "2024-01-02T00:00:00Z"
        assert metadata["tags"] == ["screenshot", "test"]

    def test_blob_metadata_partial(self):
        """Test BlobMetadata with partial data (total=False)."""
        metadata: BlobMetadata = {
            "blob_id": "blob://test.png",
            "size_bytes": 1024,
        }

        assert metadata["blob_id"] == "blob://test.png"
        assert metadata["size_bytes"] == 1024

    def test_playwright_tool_response_type(self):
        """Test PlaywrightToolResponse TypedDict."""
        response: PlaywrightToolResponse = {
            "success": True,
            "message": "Operation completed",
            "data": {"key": "value"},
            "blob_id": "blob://test.png",
        }

        assert response["success"] is True
        assert response["message"] == "Operation completed"
        assert response["data"] == {"key": "value"}
        assert response["blob_id"] == "blob://test.png"

    def test_playwright_tool_response_partial(self):
        """Test PlaywrightToolResponse with partial data (total=False)."""
        response: PlaywrightToolResponse = {
            "success": True,
        }

        assert response["success"] is True

    def test_playwright_tool_response_with_none(self):
        """Test PlaywrightToolResponse with None values."""
        response: PlaywrightToolResponse = {
            "success": False,
            "message": None,
            "data": None,
            "blob_id": None,
        }

        assert response["success"] is False
        assert response["message"] is None
        assert response["data"] is None
        assert response["blob_id"] is None
