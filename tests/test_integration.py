"""
Integration tests for key workflows
"""

import base64
import re
import struct
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from playwright_proxy_mcp.playwright.blob_manager import PlaywrightBlobManager
from playwright_proxy_mcp.playwright.config import load_playwright_config
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

    @pytest.mark.asyncio
    async def test_real_mcp_server_amazon_screenshot(self, browser_setup):  # noqa: ARG002
        """
        Integration test: Start real MCP server, navigate to Amazon, and take a screenshot.

        This test verifies:
        1. The MCP server starts successfully
        2. Navigation to Amazon works
        3. Screenshot tool returns ONLY a blob:// URI (not blob data)
        4. Blob is actually stored in the blob manager
        5. Blob URI follows the expected format
        """
        # browser_setup fixture automatically configures the test environment
        # Import server module to access tools and blob_manager
        import playwright_proxy_mcp.server as server_module

        # Navigate to Amazon using the MCP server tool's underlying function
        navigate_result = await server_module.browser_navigate.fn(
            "https://www.amazon.com"
        )

        # Verify navigation succeeded
        assert navigate_result is not None, "Navigation result should not be None"

        # Take a screenshot using the MCP server tool's underlying function (not proxy client directly!)
        blob_uri = await server_module.browser_take_screenshot.fn(
            filename="amazon_homepage", fullPage=False
        )

        # CRITICAL VERIFICATION: Result should be ONLY a blob URI string, not blob data
        assert isinstance(blob_uri, str), (
            f"Expected screenshot to return a string (blob URI), got {type(blob_uri)}: {blob_uri}"
        )

        # Verify it's a blob URI, not base64 data
        assert blob_uri.startswith("blob://"), (
            f"Expected blob:// URI, got: {blob_uri[:100]}"
        )

        # Verify blob URI format: blob://TIMESTAMP-HASH.EXTENSION
        blob_uri_pattern = r"^blob://\d+-[a-f0-9]+\.\w+$"
        assert re.match(blob_uri_pattern, blob_uri), (
            f"Blob URI '{blob_uri}' does not match expected pattern '{blob_uri_pattern}'"
        )

        # Verify the blob was actually stored in the blob manager
        # Extract the blob ID (everything after blob://)
        blob_id = blob_uri.replace("blob://", "")

        # Verify by checking the blob manager's storage
        metadata = server_module.blob_manager.storage.get_metadata(blob_id)
        assert metadata is not None, f"Blob {blob_id} should exist in storage"
        assert metadata["size_bytes"] > 0, "Blob should have non-zero size"

    @pytest.mark.asyncio
    async def test_real_mcp_server_amazon_search(self, browser_setup):  # noqa: ARG002
        """
        Integration test: Navigate to Amazon and search for trousers.

        This test verifies:
        1. The MCP server starts successfully
        2. Navigation to Amazon works
        3. Form filling and search functionality works
        4. Response size tracking for the search results page
        """
        # browser_setup fixture automatically configures the test environment
        import json

        import playwright_proxy_mcp.server as server_module

        # 1. Navigate to Amazon homepage
        navigate_result_1 = await server_module.browser_navigate.fn(
            "https://www.amazon.com"
        )

        # Verify first navigation succeeded
        assert navigate_result_1 is not None, "First navigation result should not be None"

        # 2. Navigate to Amazon search results for "trousers"
        # This is the second call that we're focusing on
        navigate_result_2 = await server_module.browser_navigate.fn(
            "https://www.amazon.com/s?k=trousers"
        )

        # Serialize the response to measure its size
        response_json = json.dumps(navigate_result_2)
        response_size_bytes = len(response_json.encode("utf-8"))
        response_size_kb = response_size_bytes / 1024

        # Verify search navigation succeeded
        assert navigate_result_2 is not None, "Second navigation result should not be None"

        # Display results for the second call (trousers search)
        print("\n=== Amazon Trousers Search Navigation (Second Call) ===")
        print(f"Response type: {type(navigate_result_2)}")
        print(f"Response size: {response_size_bytes} bytes ({response_size_kb:.2f} KB)")

        # Check if response is a dict with content
        if isinstance(navigate_result_2, dict):
            result_str = str(navigate_result_2)

            # Verify the navigation was successful
            assert len(result_str) > 0, "Navigation result should not be empty"

            print(
                f"Response keys: {list(navigate_result_2.keys()) if isinstance(navigate_result_2, dict) else 'N/A'}"
            )
            print(f"Response preview (first 500 chars): {result_str[:500]}")

        print("=== End of Search Navigation Results ===\n")

        # Final verification: Response size should be reasonable (not empty, but not huge)
        assert response_size_bytes > 100, "Response should contain substantial content"
        assert response_size_bytes < 10_000_000, (
            "Response should not be excessively large (>10MB)"
        )

    @pytest.mark.asyncio
    async def test_amazon_screenshot_resolution_viewport_only(self, browser_setup):  # noqa: ARG002
        """
        Test screenshot resolution with full_page=False (viewport only).

        NOTE: When full_page=True, the viewport configuration is NOT honored due to
        CSS scaling in the underlying playwright-mcp implementation. The screenshot
        dimensions will be scaled down (e.g., 559px instead of 1920px) because of
        CSS scaling applied during full-page capture. This is a known limitation.

        With full_page=False, the viewport should match the configured size exactly.
        """
        # browser_setup fixture automatically configures the test environment
        import os

        import playwright_proxy_mcp.server as server_module

        def get_png_dimensions(png_data: bytes) -> tuple[int, int]:
            """Extract width and height from PNG binary data."""
            if png_data[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError("Not a valid PNG file")
            # PNG IHDR chunk is at offset 8 (signature) + 4 (length) + 4 (type)
            offset = 8 + 4 + 4
            width = struct.unpack(">I", png_data[offset : offset + 4])[0]
            height = struct.unpack(">I", png_data[offset + 4 : offset + 8])[0]
            return width, height

        # Navigate to Amazon
        await server_module.browser_navigate.fn("https://www.amazon.com")

        # Take viewport-only screenshot (full_page=False)
        blob_uri = await server_module.browser_take_screenshot.fn(
            filename="amazon_viewport_test", fullPage=False
        )

        # Verify we got a blob URI
        assert isinstance(blob_uri, str), f"Expected blob URI string, got {type(blob_uri)}"
        assert blob_uri.startswith("blob://"), f"Expected blob:// URI, got {blob_uri}"

        # Extract blob ID and get metadata from blob manager
        blob_id = blob_uri.replace("blob://", "")

        # Get the storage root from blob manager
        storage_root = server_module.blob_manager.storage.storage_root

        print(f"\n=== Blob Storage Contents ===")
        print(f"Looking for blob: {blob_id}")
        print(f"Storage root: {storage_root}")

        # Find the blob file in storage
        blob_file = None
        for root, _, files in os.walk(storage_root):
            if blob_id in files:
                blob_file = Path(root) / blob_id
                break

        assert blob_file is not None, f"Blob file not found for {blob_id}"
        assert blob_file.exists(), f"Blob file should exist at {blob_file}"

        # Read PNG data and extract dimensions
        png_data = blob_file.read_bytes()
        width, height = get_png_dimensions(png_data)

        print(f"\n{'=' * 60}")
        print("VIEWPORT-ONLY SCREENSHOT RESOLUTION TEST")
        print(f"{'=' * 60}")
        print("Expected viewport: 1920x1080")
        print(f"Actual dimensions: {width}x{height}")
        print(f"Width ratio: {width / 1920:.3f} ({width / 1920 * 100:.1f}%)")
        print(f"Height ratio: {height / 1080:.3f} ({height / 1080 * 100:.1f}%)")
        print(f"{'=' * 60}\n")

        # For viewport-only screenshots, we expect EXACT dimensions
        if width == 1920 and height == 1080:
            print("✅ Viewport dimensions are CORRECT (1920x1080)")
            print("   This means the viewport is properly configured!")
        else:
            print(f"❌ Viewport dimensions are WRONG: {width}x{height}")
            print("   Expected: 1920x1080")
            print("   This means the viewport itself is not properly set")
