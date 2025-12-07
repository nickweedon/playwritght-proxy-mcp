"""
Tests for blob storage tools
"""

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
