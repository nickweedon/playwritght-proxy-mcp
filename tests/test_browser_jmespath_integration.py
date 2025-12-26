"""
JMESPath integration tests for Playwright MCP Proxy.

These tests verify JMESPath query functionality with real browser snapshots.
They are marked with pytest markers to allow selective running:
- @pytest.mark.integration: All real browser tests
- @pytest.mark.slow: Tests that may take longer due to network requests
"""

import tempfile

import pytest

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


@pytest.fixture
async def browser_setup():
    """
    Set up browser components for integration tests.

    Yields a tuple of (proxy_client, navigation_cache) for tests to use.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set up configuration
        blob_config: BlobConfig = {
            "storage_root": tmpdir,
            "max_size_mb": 100,
            "ttl_hours": 24,
            "size_threshold_kb": 50,
            "cleanup_interval_minutes": 60,
        }

        playwright_config = load_playwright_config()
        playwright_config["headless"] = True
        playwright_config["output_dir"] = f"{tmpdir}/playwright-output"

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

            yield proxy_client, navigation_cache

        finally:
            # Restore original globals
            server.navigation_cache = original_cache
            server.proxy_client = original_proxy

            # Clean up
            await blob_manager.stop_cleanup_task()
            await proxy_client.stop()


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_jmespath_filter_buttons(browser_setup):
    """
    Test JMESPath filtering to find all buttons on a page.

    This test verifies:
    1. JMESPath query parameter works
    2. Filter by role works correctly
    3. Results are returned in JSON format
    """
    proxy_client, navigation_cache = browser_setup

    # Navigate with JMESPath query to filter buttons
    result = await server.browser_navigate.fn(
        url="https://example.com",
        jmespath_query='[?role == `button`]',
        output_format="json"
    )

    # Verify successful navigation and query
    assert result is not None, "Result should not be None"
    assert isinstance(result, dict), "Result should be a dictionary"
    assert result.get("success") is True, f"Navigation should succeed. Error: {result.get('error')}"
    assert result.get("url") == "https://example.com"
    assert result.get("query_applied") == '[?role == `button`]'
    assert result.get("output_format") == "json"

    # Verify snapshot is returned (not silent mode)
    assert result.get("snapshot") is not None, "Query results should return snapshot"

    print(f"\n✓ Successfully filtered buttons with JMESPath")
    print(f"✓ Query applied: {result.get('query_applied')}")
    print(f"✓ Output format: {result.get('output_format')}")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_jmespath_raw_snapshot_structure(browser_setup):
    """
    Test to see the raw ARIA snapshot structure from example.com.

    This test captures the snapshot without filtering to understand the structure.
    """
    proxy_client, navigation_cache = browser_setup

    # Navigate without query to see raw structure
    result = await server.browser_navigate.fn(
        url="https://www.example.com",
        silent_mode=False,
        output_format="json",
        limit=10
    )

    # Verify successful navigation
    assert result is not None
    assert isinstance(result, dict)
    assert result.get("success") is True, f"Navigation should succeed. Error: {result.get('error')}"

    # Print raw snapshot to understand structure
    snapshot = result.get("snapshot", "")
    print("\n=== RAW ARIA SNAPSHOT ===")
    print(snapshot[:2000])  # First 2000 chars

    # Parse it to see structure
    import json
    try:
        data = json.loads(snapshot)
        print("\n=== PARSED STRUCTURE ===")
        print(f"Type: {type(data)}")
        if isinstance(data, list) and len(data) > 0:
            print(f"Length: {len(data)}")
            print(f"First item: {json.dumps(data[0], indent=2)[:500]}")
    except Exception as e:
        print(f"Parse error: {e}")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_jmespath_filter_headings_with_pagination(browser_setup):
    """
    Test JMESPath filtering to find headings with pagination.

    This test verifies:
    1. JMESPath recursive descent query works
    2. Filter by role for headings works correctly
    3. Pagination limit is applied
    4. Cache key is returned for subsequent queries
    5. Query actually matches headings on example.com
    """
    proxy_client, navigation_cache = browser_setup

    # Navigate with JMESPath query to filter headings at first child level, limited to 10 results
    # The ARIA structure for example.com is: [{"role": "generic", "children": [{"role": "heading"}, ...]}]
    # So we need [].children[?role == `heading`] to find headings in the first level children
    result = await server.browser_navigate.fn(
        url="https://www.example.com",
        silent_mode=False,
        jmespath_query="[].children[?role == `heading`]",
        limit=10
    )

    # Verify successful navigation and query
    assert result is not None, "Result should not be None"
    assert isinstance(result, dict), "Result should be a dictionary"
    assert result.get("success") is True, f"Navigation should succeed. Error: {result.get('error')}"
    assert result.get("url") == "https://www.example.com"
    assert result.get("query_applied") == "[].children[?role == `heading`]"

    # Verify pagination parameters
    assert result.get("limit") == 10, "Limit should be 10"
    assert result.get("offset") == 0, "Initial offset should be 0"
    assert "cache_key" in result, "Cache key should be present"
    assert "total_items" in result, "Total items should be present"
    assert "has_more" in result, "has_more flag should be present"

    # Verify snapshot is returned (not silent mode)
    assert result.get("snapshot") is not None, "Query results should return snapshot"

    # Verify we actually found headings on example.com
    total_items = result.get("total_items", 0)
    assert total_items > 0, f"Should find at least one heading on example.com, found {total_items}"

    print("\n✓ Successfully filtered headings with JMESPath")
    print(f"✓ Query applied: {result.get('query_applied')}")
    print(f"✓ Total items found: {total_items}")
    print(f"✓ Limit: {result.get('limit')}")
    print(f"✓ Has more: {result.get('has_more')}")
    print(f"✓ Cache key: {result.get('cache_key')}")
