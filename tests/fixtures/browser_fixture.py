"""
Shared browser test fixtures.

This module provides fixtures for browser integration tests that require
a running Playwright browser instance with blob management.
"""

import tempfile

import pytest
import pytest_asyncio

from playwright_proxy_mcp import server
from playwright_proxy_mcp.playwright import (
    BinaryInterceptionMiddleware,
    PlaywrightBlobManager,
    PlaywrightProcessManager,
    PlaywrightProxyClient,
    load_playwright_config,
)
from playwright_proxy_mcp.playwright.config import BlobConfig
from playwright_proxy_mcp.utils.navigation_cache import NavigationCache


@pytest_asyncio.fixture
async def browser_setup():
    """
    Set up browser components for integration tests.

    This fixture initializes all components needed for browser testing:
    - Temporary directory for blob storage
    - Blob manager with cleanup task
    - Process manager for Playwright subprocess
    - Binary interception middleware
    - Proxy client for communicating with Playwright
    - Navigation cache for pagination

    The fixture temporarily patches the global server components to use
    the test instances, then restores them on teardown.

    Yields:
        tuple: (proxy_client, navigation_cache) for tests to use
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up blob configuration
        blob_config: BlobConfig = {
            "storage_root": tmpdir,
            "max_size_mb": 100,
            "ttl_hours": 24,
            "size_threshold_kb": 50,
            "cleanup_interval_minutes": 60,
        }

        # Load and configure Playwright settings
        playwright_config = load_playwright_config()
        playwright_config["headless"] = True
        playwright_config["output_dir"] = f"{tmpdir}/playwright-output"
        playwright_config["caps"] = "vision,pdf"
        playwright_config["browser"] = "chrome"
        playwright_config["timeout_action"] = 15000
        playwright_config["timeout_navigation"] = 5000
        playwright_config["image_responses"] = "allow"

        # Initialize components
        blob_manager = PlaywrightBlobManager(blob_config)
        process_manager = PlaywrightProcessManager()
        middleware = BinaryInterceptionMiddleware(blob_manager, blob_config["size_threshold_kb"])
        proxy_client = PlaywrightProxyClient(process_manager, middleware)
        navigation_cache = NavigationCache(default_ttl=300)

        try:
            # Start proxy client
            await blob_manager.start_cleanup_task()
            await proxy_client.start(playwright_config)

            # Temporarily set global navigation cache for browser_navigate/browser_snapshot
            original_cache = server.navigation_cache
            server.navigation_cache = navigation_cache

            # Temporarily set global proxy_client for the tool functions
            original_proxy = server.proxy_client
            server.proxy_client = proxy_client

            # Temporarily set global blob_manager
            original_blob_manager = server.blob_manager
            server.blob_manager = blob_manager

            # Temporarily set global middleware
            original_middleware = server.middleware
            server.middleware = middleware

            yield proxy_client, navigation_cache

        finally:
            # Restore original globals
            server.navigation_cache = original_cache
            server.proxy_client = original_proxy
            server.blob_manager = original_blob_manager
            server.middleware = original_middleware

            # Clean up
            await blob_manager.stop_cleanup_task()
            await proxy_client.stop()
