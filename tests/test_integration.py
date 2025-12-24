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
from playwright_proxy_mcp.playwright.process_manager import PlaywrightProcessManager
from playwright_proxy_mcp.playwright.proxy_client import PlaywrightProxyClient


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
    async def test_real_mcp_server_amazon_screenshot(self):
        """
        Integration test: Start real MCP server, navigate to Amazon, and take a screenshot.

        This test verifies:
        1. The MCP server starts successfully
        2. Navigation to Amazon works
        3. Screenshot tool returns ONLY a blob:// URI (not blob data)
        4. Blob is actually stored in the blob manager
        5. Blob URI follows the expected format
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up configuration
            blob_config = {
                "storage_root": tmpdir,
                "max_size_mb": 100,
                "ttl_hours": 24,
                "size_threshold_kb": 50,
                "cleanup_interval_minutes": 60,
            }

            playwright_config = load_playwright_config()
            # Ensure headless mode for testing
            playwright_config["headless"] = True
            # Override output_dir to use temp directory instead of /app
            playwright_config["output_dir"] = f"{tmpdir}/playwright-output"

            # Initialize components (mimicking server.py global components)
            blob_manager = PlaywrightBlobManager(blob_config)
            process_manager = PlaywrightProcessManager()
            middleware = BinaryInterceptionMiddleware(
                blob_manager, blob_config["size_threshold_kb"]
            )
            proxy_client = PlaywrightProxyClient(process_manager, middleware)

            # Patch the server's global components to use our test instances
            import playwright_proxy_mcp.server as server_module

            original_proxy_client = server_module.proxy_client
            original_blob_manager = server_module.blob_manager
            original_middleware = server_module.middleware

            server_module.proxy_client = proxy_client
            server_module.blob_manager = blob_manager
            server_module.middleware = middleware

            try:
                # Start the proxy client and playwright-mcp subprocess
                await proxy_client.start(playwright_config)

                # Start blob cleanup task
                await blob_manager.start_cleanup_task()

                # Verify the proxy client is healthy
                assert proxy_client.is_healthy(), "Proxy client should be healthy after starting"

                # Navigate to Amazon using the MCP server tool's underlying function
                navigate_result = await server_module.playwright_navigate.fn(
                    "https://www.amazon.com"
                )

                # Verify navigation succeeded
                assert navigate_result is not None, "Navigation result should not be None"

                # Take a screenshot using the MCP server tool's underlying function (not proxy client directly!)
                blob_uri = await server_module.playwright_screenshot.fn(
                    name="amazon_homepage", full_page=False
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
                metadata = blob_manager.storage.get_metadata(blob_id)
                assert metadata is not None, f"Blob {blob_id} should exist in storage"
                assert metadata["size_bytes"] > 0, "Blob should have non-zero size"

            finally:
                # Restore original server components
                server_module.proxy_client = original_proxy_client
                server_module.blob_manager = original_blob_manager
                server_module.middleware = original_middleware

                # Clean up
                await blob_manager.stop_cleanup_task()
                await proxy_client.stop()

                # Verify cleanup
                assert not proxy_client.is_healthy(), (
                    "Proxy client should not be healthy after stopping"
                )

                server_module.middleware = original_middleware

                # Clean up
                await blob_manager.stop_cleanup_task()
                await proxy_client.stop()

    @pytest.mark.asyncio
    async def test_real_mcp_server_amazon_search(self):
        """
        Integration test: Navigate to Amazon and search for trousers.

        This test verifies:
        1. The MCP server starts successfully
        2. Navigation to Amazon works
        3. Form filling and search functionality works
        4. Response size tracking for the search results page
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up configuration
            blob_config = {
                "storage_root": tmpdir,
                "max_size_mb": 100,
                "ttl_hours": 24,
                "size_threshold_kb": 50,
                "cleanup_interval_minutes": 60,
            }

            playwright_config = load_playwright_config()
            # Ensure headless mode for testing
            playwright_config["headless"] = True
            # Override output_dir to use temp directory instead of /app
            playwright_config["output_dir"] = f"{tmpdir}/playwright-output"

            # Initialize components (mimicking server.py global components)
            blob_manager = PlaywrightBlobManager(blob_config)
            process_manager = PlaywrightProcessManager()
            middleware = BinaryInterceptionMiddleware(
                blob_manager, blob_config["size_threshold_kb"]
            )
            proxy_client = PlaywrightProxyClient(process_manager, middleware)

            # Patch the server's global components to use our test instances
            import playwright_proxy_mcp.server as server_module

            original_proxy_client = server_module.proxy_client
            original_blob_manager = server_module.blob_manager
            original_middleware = server_module.middleware

            server_module.proxy_client = proxy_client
            server_module.blob_manager = blob_manager
            server_module.middleware = middleware

            try:
                # Start the proxy client and playwright-mcp subprocess
                await proxy_client.start(playwright_config)

                # Start blob cleanup task
                await blob_manager.start_cleanup_task()

                # Verify the proxy client is healthy
                assert proxy_client.is_healthy(), "Proxy client should be healthy after starting"

                # 1. Navigate to Amazon homepage
                navigate_result_1 = await server_module.playwright_navigate.fn(
                    "https://www.amazon.com"
                )

                # Verify first navigation succeeded
                assert navigate_result_1 is not None, "First navigation result should not be None"

                # 2. Navigate to Amazon search results for "trousers"
                # This is the second call that we're focusing on
                import json

                navigate_result_2 = await server_module.playwright_navigate.fn(
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

            finally:
                # Restore original server components
                server_module.proxy_client = original_proxy_client
                server_module.blob_manager = original_blob_manager
                server_module.middleware = original_middleware

                # Clean up
                await blob_manager.stop_cleanup_task()
                await proxy_client.stop()

                # Verify cleanup
                assert not proxy_client.is_healthy(), (
                    "Proxy client should not be healthy after stopping"
                )

    @pytest.mark.asyncio
    async def test_amazon_screenshot_resolution(self):
        """
        Integration test: Verify screenshot resolution is 1920px (not 516px).

        This test verifies:
        1. Screenshot is taken successfully from Amazon
        2. Blob is stored and retrievable
        3. PNG dimensions can be read from the blob
        4. Width is 1920px (expected with PLAYWRIGHT_VIEWPORT_SIZE=1920x1080)
        5. NOT 516px (CSS scaling bug)
        """

        def get_png_dimensions(png_data: bytes) -> tuple[int, int]:
            """Extract width and height from PNG binary data."""
            # Read PNG signature (8 bytes)
            if png_data[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError("Not a valid PNG file")

            # Read IHDR chunk (starts at byte 8)
            # Skip chunk length (4 bytes) and chunk type "IHDR" (4 bytes)
            offset = 8 + 4 + 4

            # Read width and height (4 bytes each, big-endian)
            width = struct.unpack(">I", png_data[offset : offset + 4])[0]
            height = struct.unpack(">I", png_data[offset + 4 : offset + 8])[0]

            return width, height

        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up configuration
            blob_config = {
                "storage_root": tmpdir,
                "max_size_mb": 100,
                "ttl_hours": 24,
                "size_threshold_kb": 50,
                "cleanup_interval_minutes": 60,
            }

            playwright_config = load_playwright_config()
            # Ensure headless mode for testing
            playwright_config["headless"] = True
            # Override output_dir to use temp directory instead of /app
            playwright_config["output_dir"] = f"{tmpdir}/playwright-output"

            # Verify viewport is configured correctly
            assert (
                playwright_config.get("viewport_size") == "1920x1080"
            ), "Viewport should be 1920x1080"

            # Initialize components
            blob_manager = PlaywrightBlobManager(blob_config)
            process_manager = PlaywrightProcessManager()
            middleware = BinaryInterceptionMiddleware(
                blob_manager, blob_config["size_threshold_kb"]
            )
            proxy_client = PlaywrightProxyClient(process_manager, middleware)

            # Patch the server's global components
            import playwright_proxy_mcp.server as server_module

            original_proxy_client = server_module.proxy_client
            original_blob_manager = server_module.blob_manager
            original_middleware = server_module.middleware

            server_module.proxy_client = proxy_client
            server_module.blob_manager = blob_manager
            server_module.middleware = middleware

            try:
                # Start the proxy client and playwright-mcp subprocess
                await proxy_client.start(playwright_config)
                await blob_manager.start_cleanup_task()

                # Navigate to Amazon
                await server_module.playwright_navigate.fn("https://www.amazon.com")

                # Take a full-page screenshot
                blob_uri = await server_module.playwright_screenshot.fn(
                    name="amazon_resolution_test", full_page=True
                )

                # Verify we got a blob URI
                assert isinstance(blob_uri, str), f"Expected blob URI string, got {type(blob_uri)}"
                assert blob_uri.startswith("blob://"), f"Expected blob:// URI, got {blob_uri}"

                # Extract blob ID and read blob directly from storage
                blob_id = blob_uri.replace("blob://", "")

                # List files in tmpdir to see where blob was stored
                import os

                print(f"\n=== Blob Storage Contents ===")
                print(f"Looking for blob: {blob_id}")
                print(f"Storage root: {tmpdir}")
                print(f"Files in storage root:")
                for root, dirs, files in os.walk(tmpdir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, tmpdir)
                        print(f"  {rel_path}")

                # Find the blob using mcp-mapped-resource-lib sharding structure
                # Blobs are stored in subdirectories: XX/YY/blob_id
                # where XX and YY are the first 2 and next 2 digits of the timestamp
                blob_path = None
                for root, dirs, files in os.walk(tmpdir):
                    if blob_id in files:
                        blob_path = Path(root) / blob_id
                        break

                assert blob_path is not None, f"Could not find blob {blob_id} in {tmpdir}"
                assert blob_path.exists(), f"Blob file should exist at {blob_path}"

                blob_data = blob_path.read_bytes()
                print(f"Found blob at: {blob_path.relative_to(tmpdir)}")

                # Verify blob exists and has data
                assert blob_data is not None, "Blob data should not be None"
                assert len(blob_data) > 0, "Blob should contain data"

                # Read PNG dimensions
                width, height = get_png_dimensions(blob_data)

                # Print results for debugging
                print(f"\n=== Screenshot Resolution Test ===")
                print(f"Blob URI: {blob_uri}")
                print(f"Blob size: {len(blob_data)} bytes ({len(blob_data) / 1024:.1f} KB)")
                print(f"Dimensions: {width}x{height} pixels")
                print(f"Viewport config: {playwright_config.get('viewport_size')}")

                # Analyze results
                if width >= 1900:
                    print(f"✅ PASS - Screenshot width is {width}px (expected ~1920px)")
                    print("The viewport configuration is working correctly!")
                elif width >= 1200:
                    print(f"⚠️  WARNING - Screenshot width is {width}px (likely 1280px default)")
                    print("The PLAYWRIGHT_VIEWPORT_SIZE env var may not be applied")
                elif width < 600:
                    print(f"❌ FAIL - Screenshot width is {width}px (expected 1920px)")
                    print("This confirms the CSS scaling issue (516px bug)")
                    print("Root cause: scale: 'css' parameter in screenshot call")
                else:
                    print(f"⚠️  UNEXPECTED - Screenshot width is {width}px")

                print(f"=== End of Resolution Test ===\n")

                # Assert the width is correct
                assert width >= 1900, (
                    f"Screenshot width should be ~1920px, got {width}px. "
                    f"This indicates {'the CSS scaling bug (516px)' if width < 600 else 'viewport config issue'}."
                )

            finally:
                # Restore original server components
                server_module.proxy_client = original_proxy_client
                server_module.blob_manager = original_blob_manager
                server_module.middleware = original_middleware

                # Clean up
                await blob_manager.stop_cleanup_task()
                await proxy_client.stop()

    @pytest.mark.asyncio
    async def test_amazon_screenshot_resolution_viewport_only(self):
        """Test screenshot resolution with full_page=False (viewport only)."""
        import os

        def get_png_dimensions(png_data: bytes) -> tuple[int, int]:
            """Extract width and height from PNG binary data."""
            if png_data[:8] != b"\x89PNG\r\n\x1a\n":
                raise ValueError("Not a valid PNG file")
            # PNG IHDR chunk is at offset 8 (signature) + 4 (length) + 4 (type)
            offset = 8 + 4 + 4
            width = struct.unpack(">I", png_data[offset : offset + 4])[0]
            height = struct.unpack(">I", png_data[offset + 4 : offset + 8])[0]
            return width, height

        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up configuration
            blob_config = {
                "storage_root": tmpdir,
                "max_size_mb": 100,
                "ttl_hours": 24,
                "size_threshold_kb": 50,
                "cleanup_interval_minutes": 60,
            }

            playwright_config = load_playwright_config()
            playwright_config["headless"] = True
            playwright_config["output_dir"] = f"{tmpdir}/playwright-output"

            # Verify viewport is configured correctly
            assert (
                playwright_config.get("viewport_size") == "1920x1080"
            ), "Viewport should be 1920x1080"

            # Initialize components
            blob_manager = PlaywrightBlobManager(blob_config)
            process_manager = PlaywrightProcessManager()
            middleware = BinaryInterceptionMiddleware(
                blob_manager, blob_config["size_threshold_kb"]
            )
            proxy_client = PlaywrightProxyClient(process_manager, middleware)

            # Patch the server's global components
            import playwright_proxy_mcp.server as server_module

            original_proxy_client = server_module.proxy_client
            original_blob_manager = server_module.blob_manager
            original_middleware = server_module.middleware

            server_module.proxy_client = proxy_client
            server_module.blob_manager = blob_manager
            server_module.middleware = middleware

            try:
                # Start the proxy client and playwright-mcp subprocess
                await proxy_client.start(playwright_config)
                await blob_manager.start_cleanup_task()

                # Navigate to Amazon
                await server_module.playwright_navigate.fn("https://www.amazon.com")

                # Take viewport-only screenshot (full_page=False)
                blob_uri = await server_module.playwright_screenshot.fn(
                    name="amazon_viewport_test", full_page=False
                )

                # Verify we got a blob URI
                assert isinstance(blob_uri, str), f"Expected blob URI string, got {type(blob_uri)}"
                assert blob_uri.startswith("blob://"), f"Expected blob:// URI, got {blob_uri}"

                # Extract blob ID and read blob directly from storage
                blob_id = blob_uri.replace("blob://", "")

                print(f"\n=== Blob Storage Contents ===")
                print(f"Looking for blob: {blob_id}")
                print(f"Storage root: {tmpdir}")

                # Find the blob file in temp storage
                blob_file = None
                for root, dirs, files in os.walk(tmpdir):
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

            finally:
                # Restore original server components
                server_module.proxy_client = original_proxy_client
                server_module.blob_manager = original_blob_manager
                server_module.middleware = original_middleware

                # Clean up
                await blob_manager.stop_cleanup_task()
                await proxy_client.stop()
