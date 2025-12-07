"""
Playwright MCP Proxy Server

A proxy server for Microsoft's playwright-mcp that provides efficient handling
of large binary data (screenshots, PDFs) through blob storage.

This server:
1. Runs playwright-mcp as a subprocess using npx
2. Proxies all playwright browser automation tools
3. Intercepts large binary responses and stores them as blobs
4. Provides tools for blob retrieval and management
"""

import asyncio
import json
import logging
from typing import Any

from fastmcp import FastMCP

from .api import blob_tools
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


async def lifespan_context():
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
        blob_tools.set_blob_manager(blob_manager)

        # Initialize process manager
        process_manager = PlaywrightProcessManager()

        # Initialize middleware
        middleware = BinaryInterceptionMiddleware(
            blob_manager, blob_config["size_threshold_kb"]
        )

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

    When a tool returns a blob reference (e.g., blob://timestamp-hash.png),
    use the get_blob(blob_id) tool to retrieve the actual binary data.

    Available blob management tools:
    - get_blob: Retrieve binary data by blob ID
    - list_blobs: List available blobs with filtering
    - delete_blob: Delete a blob from storage
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
        tool_name: Name of the tool
        arguments: Tool arguments

    Returns:
        Tool result (potentially transformed by middleware)
    """
    if not proxy_client or not proxy_client.is_healthy():
        raise RuntimeError("Playwright subprocess not running")

    process = proxy_client.get_process()
    if not process or not process.stdin or not process.stdout:
        raise RuntimeError("Playwright subprocess not properly initialized")

    # Create JSON-RPC request
    request_id = id(arguments)  # Simple request ID
    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    # Send request to subprocess
    request_json = json.dumps(request) + "\n"
    process.stdin.write(request_json.encode("utf-8"))
    await process.stdin.drain()

    # Read response from subprocess
    response_line = await process.stdout.readline()
    response = json.loads(response_line.decode("utf-8"))

    # Check for errors
    if "error" in response:
        error = response["error"]
        raise RuntimeError(f"Playwright tool error: {error.get('message', error)}")

    # Get result
    result = response.get("result", {})

    # Transform through middleware
    transformed_result = await proxy_client.transform_response(tool_name, result)

    return transformed_result


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
async def playwright_screenshot(
    name: str | None = None, full_page: bool = False
) -> dict[str, Any]:
    """
    Take a screenshot of the current page.

    Large screenshots are automatically stored as blobs.

    Args:
        name: Optional name for the screenshot
        full_page: Whether to capture the full scrollable page

    Returns:
        Screenshot result (may include blob reference)
    """
    args = {}
    if name is not None:
        args["name"] = name
    if full_page:
        args["fullPage"] = full_page

    return await _call_playwright_tool("playwright_screenshot", args)


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
# BLOB MANAGEMENT TOOLS
# =============================================================================


@mcp.tool()
async def get_blob(blob_id: str) -> dict[str, Any]:
    """
    Retrieve binary data from blob storage by ID.

    Args:
        blob_id: Blob identifier (e.g., blob://timestamp-hash.png)

    Returns:
        Blob data and metadata
    """
    return await blob_tools.get_blob(blob_id)


@mcp.tool()
async def list_blobs(
    mime_type: str | None = None, tags: list[str] | None = None, limit: int = 100
) -> dict[str, Any]:
    """
    List available blobs in storage.

    Args:
        mime_type: Filter by MIME type (optional)
        tags: Filter by tags (optional)
        limit: Maximum results (default: 100)

    Returns:
        List of blob metadata
    """
    return await blob_tools.list_blobs(mime_type=mime_type, tags=tags, limit=limit)


@mcp.tool()
async def delete_blob(blob_id: str) -> dict[str, Any]:
    """
    Delete a blob from storage.

    Args:
        blob_id: Blob identifier to delete

    Returns:
        Deletion status
    """
    return await blob_tools.delete_blob(blob_id)


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
