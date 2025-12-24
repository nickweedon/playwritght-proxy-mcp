"""
Playwright MCP Proxy Server

A proxy server for Microsoft's playwright-mcp that provides efficient handling
of large binary data (screenshots, PDFs) through blob storage.

This server:
1. Runs playwright-mcp as a subprocess using npx
2. Proxies all playwright browser automation tools
3. Intercepts large binary responses and stores them as blobs
4. Returns blob:// URIs for large binary data (retrieval delegated to MCP Resource Server)
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP

from .playwright import (
    BinaryInterceptionMiddleware,
    PlaywrightBlobManager,
    PlaywrightProcessManager,
    PlaywrightProxyClient,
    load_blob_config,
    load_playwright_config,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global components
playwright_config = None
blob_config = None
blob_manager = None
process_manager = None
middleware = None
proxy_client = None


@asynccontextmanager
async def lifespan_context(server):
    """Lifespan context manager for startup and shutdown"""
    global playwright_config, blob_config, blob_manager, process_manager
    global middleware, proxy_client

    logger.info("Starting Playwright MCP Proxy...")

    try:
        # Load configuration
        playwright_config = load_playwright_config()
        blob_config = load_blob_config()

        logger.info(f"Playwright browser: {playwright_config.get('browser', 'chromium')}")
        logger.info(f"Blob storage: {blob_config['storage_root']}")
        logger.info(f"Blob threshold: {blob_config['size_threshold_kb']}KB")

        # Initialize blob storage
        blob_manager = PlaywrightBlobManager(blob_config)

        # Initialize process manager
        process_manager = PlaywrightProcessManager()

        # Initialize middleware
        middleware = BinaryInterceptionMiddleware(blob_manager, blob_config["size_threshold_kb"])

        # Initialize proxy client
        proxy_client = PlaywrightProxyClient(process_manager, middleware)

        # Start playwright-mcp subprocess
        await proxy_client.start(playwright_config)

        # Start blob cleanup task
        await blob_manager.start_cleanup_task()

        logger.info("Playwright MCP Proxy started successfully")

        # Yield control to the server
        yield

    except Exception as e:
        logger.error(f"Failed to start Playwright MCP Proxy: {e}")
        raise

    finally:
        # Shutdown cleanup
        logger.info("Shutting down Playwright MCP Proxy...")

        try:
            # Stop cleanup task
            if blob_manager:
                await blob_manager.stop_cleanup_task()

            # Stop proxy client and subprocess
            if proxy_client:
                await proxy_client.stop()

            logger.info("Playwright MCP Proxy shut down successfully")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# Initialize the MCP server
mcp = FastMCP(
    name="Playwright MCP Proxy",
    instructions="""
    This is a proxy server for Microsoft's playwright-mcp that provides
    efficient handling of large binary data (screenshots, PDFs) through
    blob storage.

    All playwright browser automation tools are available through this proxy.
    Large binary responses (>50KB by default) are automatically stored as blobs
    to reduce token usage.

    When a tool returns a blob reference (blob://timestamp-hash.png format),
    use a separate MCP Resource Server to retrieve, list, or delete blobs.
    This server only creates and returns blob:// URIs.

    """,
    lifespan=lifespan_context,
)


# =============================================================================
# PROXY TOOLS
# =============================================================================
# We need to manually proxy playwright-mcp tools since FastMCP's as_proxy
# requires a running server. We'll communicate directly with the subprocess.


async def _call_playwright_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """
    Call a playwright-mcp tool through the subprocess.

    Args:
        tool_name: Name of the tool (with or without playwright_ prefix)
        arguments: Tool arguments

    Returns:
        Tool result (potentially transformed by middleware)
    """
    if not proxy_client or not proxy_client.is_healthy():
        raise RuntimeError("Playwright subprocess not running")

    # Map playwright_ prefix to browser_ prefix used by playwright-mcp
    # playwright-mcp tools use browser_ prefix with different naming conventions
    # Some tools need explicit mapping beyond simple prefix replacement
    TOOL_NAME_MAP = {
        "playwright_screenshot": "browser_take_screenshot",
        "playwright_navigate": "browser_navigate",
        "playwright_click": "browser_click",
        "playwright_fill": "browser_fill_form",
        "playwright_get_visible_text": "browser_snapshot",
    }

    actual_tool_name = TOOL_NAME_MAP.get(
        tool_name,
        tool_name.replace("playwright_", "browser_", 1)
        if tool_name.startswith("playwright_")
        else tool_name,
    )

    # Call tool through proxy client
    return await proxy_client.call_tool(actual_tool_name, arguments)


# Register common playwright tools
# Note: In a full implementation, we would dynamically discover all tools
# from playwright-mcp. For now, we'll register the most common ones.


@mcp.tool()
async def playwright_navigate(url: str) -> dict[str, Any]:
    """
    Navigate to a URL in the browser.

    Args:
        url: The URL to navigate to

    Returns:
        Navigation result
    """
    return await _call_playwright_tool("playwright_navigate", {"url": url})


@mcp.tool()
async def playwright_screenshot(name: str | None = None, full_page: bool = True) -> str:
    """
    Take a screenshot of the current page.

    Screenshots are automatically stored as blobs and returned as blob:// URIs.
    Use a separate MCP Resource Server to retrieve blob data.

    Args:
        name: Optional name for the screenshot
        full_page: Whether to capture the full scrollable page

    Returns:
        Blob URI reference (blob://timestamp-hash.png)
    """
    args = {}
    if name is not None:
        args["name"] = name
    if full_page:
        args["fullPage"] = full_page

    result = await _call_playwright_tool("playwright_screenshot", args)

    # Extract blob URI from transformed response
    # After middleware transformation, response is: {'content': [{'type': 'text', ...}, {'type': 'blob', 'blob_id': '...', ...}]}
    if isinstance(result, dict) and "content" in result:
        content = result["content"]
        if isinstance(content, list):
            # Find the blob item in the content array
            for item in content:
                if isinstance(item, dict) and item.get("type") == "blob":
                    return item["blob_id"]

    # Fallback: if result is already a string (older format), return it
    if isinstance(result, str):
        return result

    # If we can't find the blob URI, raise an error
    raise RuntimeError(f"Failed to extract blob URI from screenshot result: {result}")


@mcp.tool()
async def playwright_click(selector: str) -> dict[str, Any]:
    """
    Click an element on the page.

    Args:
        selector: CSS selector or accessibility label

    Returns:
        Click result
    """
    return await _call_playwright_tool("playwright_click", {"selector": selector})


@mcp.tool()
async def playwright_fill(selector: str, value: str) -> dict[str, Any]:
    """
    Fill a form field with a value.

    Args:
        selector: CSS selector or accessibility label
        value: Value to fill

    Returns:
        Fill result
    """
    return await _call_playwright_tool("playwright_fill", {"selector": selector, "value": value})


@mcp.tool()
async def playwright_get_visible_text() -> dict[str, Any]:
    """
    Get visible text from the current page.

    Returns:
        Visible text content
    """
    return await _call_playwright_tool("playwright_get_visible_text", {})


# =============================================================================
# RESOURCES
# =============================================================================


@mcp.resource("playwright-proxy://status")
async def get_proxy_status() -> str:
    """Get the current proxy status"""
    if proxy_client and proxy_client.is_healthy():
        return "Playwright MCP Proxy is running"
    else:
        return "Playwright MCP Proxy is not running"


# =============================================================================
# MAIN
# =============================================================================


def main() -> None:
    """Run the MCP proxy server"""
    logger.info("Initializing Playwright MCP Proxy Server...")
    mcp.run()


if __name__ == "__main__":
    main()
