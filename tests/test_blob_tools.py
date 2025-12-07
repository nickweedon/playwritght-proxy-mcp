"""
Tests for blob storage tools
"""

import base64
from unittest.mock import AsyncMock, Mock

import pytest

from playwright_proxy_mcp.api import blob_tools


class TestBlobTools:
    """Tests for blob storage tools."""

    @pytest.mark.asyncio
    async def test_get_blob_not_initialized(self):
        """Test that get_blob raises error when blob manager not initialized."""
        # Reset blob manager to None
        blob_tools._blob_manager = None

        with pytest.raises(ValueError, match="Blob manager not initialized"):
            await blob_tools.get_blob("blob://test.png")

    @pytest.mark.asyncio
    async def test_list_blobs_not_initialized(self):
        """Test that list_blobs raises error when blob manager not initialized."""
        # Reset blob manager to None
        blob_tools._blob_manager = None

        with pytest.raises(ValueError, match="Blob manager not initialized"):
            await blob_tools.list_blobs()

    @pytest.mark.asyncio
    async def test_delete_blob_not_initialized(self):
        """Test that delete_blob raises error when blob manager not initialized."""
        # Reset blob manager to None
        blob_tools._blob_manager = None

        with pytest.raises(ValueError, match="Blob manager not initialized"):
            await blob_tools.delete_blob("blob://test.png")

    @pytest.mark.asyncio
    async def test_set_blob_manager(self):
        """Test setting the blob manager."""
        mock_manager = Mock()
        blob_tools.set_blob_manager(mock_manager)
        assert blob_tools._blob_manager == mock_manager

    @pytest.mark.asyncio
    async def test_get_blob_success(self):
        """Test successful blob retrieval."""
        # Create mock blob manager
        mock_manager = Mock()
        test_data = b"test binary data"
        test_metadata = {
            "mime_type": "image/png",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        mock_manager.retrieve_blob = AsyncMock(return_value=test_data)
        mock_manager.get_blob_metadata = AsyncMock(return_value=test_metadata)

        blob_tools.set_blob_manager(mock_manager)

        result = await blob_tools.get_blob("blob://test-123.png")

        # Verify result structure
        assert result["blob_id"] == "blob://test-123.png"
        assert result["mime_type"] == "image/png"
        assert result["size_bytes"] == len(test_data)
        assert result["created_at"] == "2024-01-01T00:00:00Z"
        assert result["expires_at"] == "2024-01-02T00:00:00Z"

        # Verify data URI format
        expected_b64 = base64.b64encode(test_data).decode("utf-8")
        assert result["data"] == f"data:image/png;base64,{expected_b64}"

        # Verify manager was called correctly
        mock_manager.retrieve_blob.assert_called_once_with("blob://test-123.png")
        mock_manager.get_blob_metadata.assert_called_once_with("blob://test-123.png")

    @pytest.mark.asyncio
    async def test_get_blob_failure(self):
        """Test blob retrieval failure."""
        mock_manager = Mock()
        mock_manager.retrieve_blob = AsyncMock(side_effect=Exception("Blob not found"))

        blob_tools.set_blob_manager(mock_manager)

        with pytest.raises(ValueError, match="Failed to retrieve blob"):
            await blob_tools.get_blob("blob://nonexistent.png")

    @pytest.mark.asyncio
    async def test_list_blobs_success(self):
        """Test successful blob listing."""
        mock_manager = Mock()
        test_blobs = [
            {
                "blob_id": "blob://test1.png",
                "mime_type": "image/png",
                "size_bytes": 1024,
            },
            {
                "blob_id": "blob://test2.pdf",
                "mime_type": "application/pdf",
                "size_bytes": 2048,
            },
        ]

        mock_manager.list_blobs = AsyncMock(return_value=test_blobs)
        blob_tools.set_blob_manager(mock_manager)

        result = await blob_tools.list_blobs(mime_type="image/png", tags=["test"], limit=50)

        assert result["count"] == 2
        assert result["blobs"] == test_blobs
        assert result["filters"]["mime_type"] == "image/png"
        assert result["filters"]["tags"] == ["test"]
        assert result["filters"]["limit"] == 50

        mock_manager.list_blobs.assert_called_once_with(
            mime_type="image/png", tags=["test"], limit=50
        )

    @pytest.mark.asyncio
    async def test_list_blobs_failure(self):
        """Test blob listing failure."""
        mock_manager = Mock()
        mock_manager.list_blobs = AsyncMock(side_effect=Exception("Storage error"))

        blob_tools.set_blob_manager(mock_manager)

        with pytest.raises(ValueError, match="Failed to list blobs"):
            await blob_tools.list_blobs()

    @pytest.mark.asyncio
    async def test_delete_blob_success(self):
        """Test successful blob deletion."""
        mock_manager = Mock()
        mock_manager.delete_blob = AsyncMock(return_value=True)

        blob_tools.set_blob_manager(mock_manager)

        result = await blob_tools.delete_blob("blob://test.png")

        assert result["blob_id"] == "blob://test.png"
        assert result["deleted"] is True
        assert "successfully" in result["message"]

        mock_manager.delete_blob.assert_called_once_with("blob://test.png")

    @pytest.mark.asyncio
    async def test_delete_blob_failure(self):
        """Test blob deletion failure."""
        mock_manager = Mock()
        mock_manager.delete_blob = AsyncMock(side_effect=Exception("Delete error"))

        blob_tools.set_blob_manager(mock_manager)

        with pytest.raises(ValueError, match="Failed to delete blob"):
            await blob_tools.delete_blob("blob://test.png")
