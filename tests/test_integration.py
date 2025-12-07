"""
Integration tests for key workflows
"""

import base64
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest

from playwright_proxy_mcp.playwright.blob_manager import PlaywrightBlobManager
from playwright_proxy_mcp.playwright.middleware import BinaryInterceptionMiddleware


class TestIntegrationWorkflows:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_blob_manager_workflow(self):
        """Test complete blob storage workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "storage_root": tmpdir,
                "max_size_mb": 10,
                "ttl_hours": 24,
                "size_threshold_kb": 50,
                "cleanup_interval_minutes": 60,
            }

            manager = PlaywrightBlobManager(config)

            # Test storage
            test_data = b"Test binary data for integration"
            base64_data = base64.b64encode(test_data).decode("utf-8")

            with patch.object(manager.storage, "upload_blob") as mock_upload:
                mock_upload.return_value = {
                    "blob_id": "blob_test",
                    "created_at": "2024-01-01T00:00:00Z",
                }

                result = await manager.store_base64_data(base64_data, "test.bin")

                assert "blob_id" in result
                assert result["size_bytes"] == len(test_data)

    @pytest.mark.asyncio
    async def test_middleware_integration(self):
        """Test middleware with blob manager integration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {
                "storage_root": tmpdir,
                "max_size_mb": 10,
                "ttl_hours": 24,
                "size_threshold_kb": 50,
                "cleanup_interval_minutes": 60,
            }

            blob_manager = PlaywrightBlobManager(config)
            middleware = BinaryInterceptionMiddleware(blob_manager, 50)

            # Small data should not be intercepted
            small_data = b"x" * 100
            base64_small = base64.b64encode(small_data).decode("utf-8")
            response = {"data": base64_small}

            result = await middleware.intercept_response("non_binary_tool", response)
            assert result == response

    @pytest.mark.asyncio
    async def test_middleware_edge_cases(self):
        """Test middleware with various edge cases."""
        mock_blob_manager = Mock()
        middleware = BinaryInterceptionMiddleware(mock_blob_manager, 50)

        # Empty response
        result = await middleware.intercept_response("tool", {})
        assert result == {}

        # Response with None values
        response_with_none = {"data": None, "status": "ok"}
        result = await middleware.intercept_response("tool", response_with_none)
        assert result == response_with_none

    @pytest.mark.asyncio
    async def test_config_integration(self):
        """Test configuration loading integration."""
        from playwright_proxy_mcp.playwright.config import (
            load_blob_config,
            load_playwright_config,
        )

        # Test that configs load without errors
        pw_config = load_playwright_config()
        blob_config = load_blob_config()

        # Verify required keys exist
        assert "browser" in pw_config
        assert "headless" in pw_config
        assert "storage_root" in blob_config
        assert "max_size_mb" in blob_config
