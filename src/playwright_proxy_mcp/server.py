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

    # All tools now use the browser_ prefix directly matching playwright-mcp
    # No name mapping needed as we use the exact upstream tool names
    actual_tool_name = tool_name

    # Call tool through proxy client
    return await proxy_client.call_tool(actual_tool_name, arguments)


# =============================================================================
# NAVIGATION TOOLS
# =============================================================================


@mcp.tool()
async def browser_navigate(url: str) -> dict[str, Any]:
    """
    Navigate to a URL.

    Args:
        url: The URL to navigate to

    Returns:
        Navigation result
    """
    return await _call_playwright_tool("browser_navigate", {"url": url})


@mcp.tool()
async def browser_navigate_back() -> dict[str, Any]:
    """
    Go back to the previous page.

    Returns:
        Navigation result
    """
    return await _call_playwright_tool("browser_navigate_back", {})


# =============================================================================
# SCREENSHOT & PDF TOOLS
# =============================================================================


@mcp.tool()
async def browser_take_screenshot(
    type: str = "png",
    filename: str | None = None,
    element: str | None = None,
    ref: str | None = None,
    fullPage: bool | None = None,
) -> str:
    """
    Take a screenshot of the current page. You can't perform actions based on the screenshot, use browser_snapshot for actions.

    Screenshots are automatically stored as blobs and returned as blob:// URIs.
    Use a separate MCP Resource Server to retrieve blob data.

    Args:
        type: Image format for the screenshot. Must be 'png' or 'jpeg'. Default is 'png'.
        filename: File name to save the screenshot to. Defaults to page-{timestamp}.{png|jpeg} if not specified.
                  Prefer relative file names to stay within the output directory.
        element: Human-readable element description used to obtain permission to screenshot the element.
                 If not provided, the screenshot will be taken of viewport. If element is provided, ref must be provided too.
        ref: Exact target element reference from the page snapshot. If not provided, the screenshot will be taken of viewport.
             If ref is provided, element must be provided too.
        fullPage: When true, takes a screenshot of the full scrollable page, instead of the currently visible viewport.
                  Cannot be used with element screenshots.

    Returns:
        Blob URI reference (blob://timestamp-hash.png or blob://timestamp-hash.jpeg)
    """
    args = {"type": type}
    if filename is not None:
        args["filename"] = filename
    if element is not None:
        args["element"] = element
    if ref is not None:
        args["ref"] = ref
    if fullPage is not None:
        args["fullPage"] = fullPage

    result = await _call_playwright_tool("browser_take_screenshot", args)

    # Extract blob URI from transformed response
    if isinstance(result, dict) and "content" in result:
        content = result["content"]
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "blob":
                    return item["blob_id"]

    # Fallback: if result is already a string, return it
    if isinstance(result, str):
        return result

    raise RuntimeError(f"Failed to extract blob URI from screenshot result: {result}")


@mcp.tool()
async def browser_pdf_save(filename: str | None = None) -> str:
    """
    Save page as PDF.

    PDFs are automatically stored as blobs and returned as blob:// URIs.
    Use a separate MCP Resource Server to retrieve blob data.

    Args:
        filename: File name to save the pdf to. Defaults to page-{timestamp}.pdf if not specified.
                  Prefer relative file names to stay within the output directory.

    Returns:
        Blob URI reference (blob://timestamp-hash.pdf)
    """
    args = {}
    if filename is not None:
        args["filename"] = filename

    result = await _call_playwright_tool("browser_pdf_save", args)

    # Extract blob URI from transformed response
    if isinstance(result, dict) and "content" in result:
        content = result["content"]
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "blob":
                    return item["blob_id"]

    # Fallback: if result is already a string, return it
    if isinstance(result, str):
        return result

    raise RuntimeError(f"Failed to extract blob URI from PDF result: {result}")


# =============================================================================
# CODE EXECUTION TOOLS
# =============================================================================


@mcp.tool()
async def browser_run_code(code: str) -> dict[str, Any]:
    """
    Run Playwright code snippet.

    Args:
        code: A JavaScript function containing Playwright code to execute. It will be invoked with a single
              argument, page, which you can use for any page interaction.
              For example: async (page) => { await page.getByRole('button', { name: 'Submit' }).click(); return await page.title(); }

    Returns:
        Code execution result
    """
    return await _call_playwright_tool("browser_run_code", {"code": code})


@mcp.tool()
async def browser_evaluate(
    function: str,
    element: str | None = None,
    ref: str | None = None,
) -> dict[str, Any]:
    """
    Evaluate JavaScript expression on page or element.

    Args:
        function: () => { /* code */ } or (element) => { /* code */ } when element is provided
        element: Human-readable element description used to obtain permission to interact with the element
        ref: Exact target element reference from the page snapshot

    Returns:
        Evaluation result
    """
    args = {"function": function}
    if element is not None:
        args["element"] = element
    if ref is not None:
        args["ref"] = ref

    return await _call_playwright_tool("browser_evaluate", args)


# =============================================================================
# PAGE SNAPSHOT & INTERACTION TOOLS
# =============================================================================


@mcp.tool()
async def browser_snapshot(filename: str | None = None) -> dict[str, Any]:
    """
    Capture accessibility snapshot of the current page, this is better than screenshot.

    Args:
        filename: Save snapshot to markdown file instead of returning it in the response.

    Returns:
        Page snapshot or save confirmation
    """
    args = {}
    if filename is not None:
        args["filename"] = filename

    return await _call_playwright_tool("browser_snapshot", args)


@mcp.tool()
async def browser_click(
    element: str,
    ref: str,
    doubleClick: bool | None = None,
    button: str | None = None,
    modifiers: list[str] | None = None,
) -> dict[str, Any]:
    """
    Perform click on a web page.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        ref: Exact target element reference from the page snapshot
        doubleClick: Whether to perform a double click instead of a single click
        button: Button to click, must be 'left', 'right', or 'middle'. Defaults to 'left'.
        modifiers: Modifier keys to press. Can include: 'Alt', 'Control', 'ControlOrMeta', 'Meta', 'Shift'.

    Returns:
        Click result
    """
    args = {"element": element, "ref": ref}
    if doubleClick is not None:
        args["doubleClick"] = doubleClick
    if button is not None:
        args["button"] = button
    if modifiers is not None:
        args["modifiers"] = modifiers

    return await _call_playwright_tool("browser_click", args)


@mcp.tool()
async def browser_drag(
    startElement: str,
    startRef: str,
    endElement: str,
    endRef: str,
) -> dict[str, Any]:
    """
    Perform drag and drop between two elements.

    Args:
        startElement: Human-readable source element description used to obtain the permission to interact with the element
        startRef: Exact source element reference from the page snapshot
        endElement: Human-readable target element description used to obtain the permission to interact with the element
        endRef: Exact target element reference from the page snapshot

    Returns:
        Drag result
    """
    return await _call_playwright_tool(
        "browser_drag",
        {
            "startElement": startElement,
            "startRef": startRef,
            "endElement": endElement,
            "endRef": endRef,
        },
    )


@mcp.tool()
async def browser_hover(element: str, ref: str) -> dict[str, Any]:
    """
    Hover over element on page.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        ref: Exact target element reference from the page snapshot

    Returns:
        Hover result
    """
    return await _call_playwright_tool("browser_hover", {"element": element, "ref": ref})


@mcp.tool()
async def browser_select_option(element: str, ref: str, values: list[str]) -> dict[str, Any]:
    """
    Select an option in a dropdown.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        ref: Exact target element reference from the page snapshot
        values: Array of values to select in the dropdown. This can be a single value or multiple values.

    Returns:
        Selection result
    """
    return await _call_playwright_tool("browser_select_option", {"element": element, "ref": ref, "values": values})


@mcp.tool()
async def browser_generate_locator(element: str, ref: str) -> dict[str, Any]:
    """
    Generate locator for the given element to use in tests.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        ref: Exact target element reference from the page snapshot

    Returns:
        Generated locator
    """
    return await _call_playwright_tool("browser_generate_locator", {"element": element, "ref": ref})


# =============================================================================
# FORM INTERACTION TOOLS
# =============================================================================


@mcp.tool()
async def browser_fill_form(fields: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Fill multiple form fields.

    Args:
        fields: Fields to fill in. Each field is a dict with:
                - name (str): Human-readable field name
                - type (str): Type of the field. Must be 'textbox', 'checkbox', 'radio', 'combobox', or 'slider'.
                - ref (str): Exact target field reference from the page snapshot
                - value (str): Value to fill in the field. If the field is a checkbox, the value should be 'true' or 'false'.
                              If the field is a combobox, the value should be the text of the option.

    Returns:
        Fill result
    """
    return await _call_playwright_tool("browser_fill_form", {"fields": fields})


# =============================================================================
# MOUSE TOOLS (VISION CAPABILITY)
# =============================================================================


@mcp.tool()
async def browser_mouse_move_xy(element: str, x: float, y: float) -> dict[str, Any]:
    """
    Move mouse to a given position.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        x: X coordinate
        y: Y coordinate

    Returns:
        Mouse move result
    """
    return await _call_playwright_tool("browser_mouse_move_xy", {"element": element, "x": x, "y": y})


@mcp.tool()
async def browser_mouse_click_xy(element: str, x: float, y: float) -> dict[str, Any]:
    """
    Click left mouse button at a given position.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        x: X coordinate
        y: Y coordinate

    Returns:
        Mouse click result
    """
    return await _call_playwright_tool("browser_mouse_click_xy", {"element": element, "x": x, "y": y})


@mcp.tool()
async def browser_mouse_drag_xy(
    element: str,
    startX: float,
    startY: float,
    endX: float,
    endY: float,
) -> dict[str, Any]:
    """
    Drag left mouse button to a given position.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        startX: Start X coordinate
        startY: Start Y coordinate
        endX: End X coordinate
        endY: End Y coordinate

    Returns:
        Mouse drag result
    """
    return await _call_playwright_tool(
        "browser_mouse_drag_xy",
        {
            "element": element,
            "startX": startX,
            "startY": startY,
            "endX": endX,
            "endY": endY,
        },
    )


# =============================================================================
# KEYBOARD TOOLS
# =============================================================================


@mcp.tool()
async def browser_press_key(key: str) -> dict[str, Any]:
    """
    Press a key on the keyboard.

    Args:
        key: Name of the key to press or a character to generate, such as 'ArrowLeft' or 'a'

    Returns:
        Key press result
    """
    return await _call_playwright_tool("browser_press_key", {"key": key})


@mcp.tool()
async def browser_type(
    element: str,
    ref: str,
    text: str,
    submit: bool | None = None,
    slowly: bool | None = None,
) -> dict[str, Any]:
    """
    Type text into editable element.

    Args:
        element: Human-readable element description used to obtain permission to interact with the element
        ref: Exact target element reference from the page snapshot
        text: Text to type into the element
        submit: Whether to submit entered text (press Enter after)
        slowly: Whether to type one character at a time. Useful for triggering key handlers in the page.
                By default entire text is filled in at once.

    Returns:
        Type result
    """
    args = {"element": element, "ref": ref, "text": text}
    if submit is not None:
        args["submit"] = submit
    if slowly is not None:
        args["slowly"] = slowly

    return await _call_playwright_tool("browser_type", args)


# =============================================================================
# WAIT & TIMING TOOLS
# =============================================================================


@mcp.tool()
async def browser_wait_for(
    time: float | None = None,
    text: str | None = None,
    textGone: str | None = None,
) -> dict[str, Any]:
    """
    Wait for text to appear or disappear or a specified time to pass.

    Args:
        time: The time to wait in seconds
        text: The text to wait for
        textGone: The text to wait for to disappear

    Returns:
        Wait result
    """
    args = {}
    if time is not None:
        args["time"] = time
    if text is not None:
        args["text"] = text
    if textGone is not None:
        args["textGone"] = textGone

    return await _call_playwright_tool("browser_wait_for", args)


# =============================================================================
# VERIFICATION/TESTING TOOLS
# =============================================================================


@mcp.tool()
async def browser_verify_element_visible(role: str, accessibleName: str) -> dict[str, Any]:
    """
    Verify element is visible on the page.

    Args:
        role: ROLE of the element. Can be found in the snapshot like this: - {ROLE} "Accessible Name":
        accessibleName: ACCESSIBLE_NAME of the element. Can be found in the snapshot like this: - role "{ACCESSIBLE_NAME}"

    Returns:
        Verification result
    """
    return await _call_playwright_tool("browser_verify_element_visible", {"role": role, "accessibleName": accessibleName})


@mcp.tool()
async def browser_verify_text_visible(text: str) -> dict[str, Any]:
    """
    Verify text is visible on the page. Prefer browser_verify_element_visible if possible.

    Args:
        text: TEXT to verify. Can be found in the snapshot like this: - role "Accessible Name": {TEXT} or like this: - text: {TEXT}

    Returns:
        Verification result
    """
    return await _call_playwright_tool("browser_verify_text_visible", {"text": text})


@mcp.tool()
async def browser_verify_list_visible(element: str, ref: str, items: list[str]) -> dict[str, Any]:
    """
    Verify list is visible on the page.

    Args:
        element: Human-readable list description
        ref: Exact target element reference that points to the list
        items: Items to verify

    Returns:
        Verification result
    """
    return await _call_playwright_tool("browser_verify_list_visible", {"element": element, "ref": ref, "items": items})


@mcp.tool()
async def browser_verify_value(type: str, element: str, ref: str, value: str) -> dict[str, Any]:
    """
    Verify element value.

    Args:
        type: Type of the element. Must be 'textbox', 'checkbox', 'radio', 'combobox', or 'slider'.
        element: Human-readable element description
        ref: Exact target element reference that points to the element
        value: Value to verify. For checkbox, use "true" or "false".

    Returns:
        Verification result
    """
    return await _call_playwright_tool("browser_verify_value", {"type": type, "element": element, "ref": ref, "value": value})


# =============================================================================
# NETWORK TOOLS
# =============================================================================


@mcp.tool()
async def browser_network_requests(includeStatic: bool = False) -> dict[str, Any]:
    """
    Returns all network requests since loading the page.

    Args:
        includeStatic: Whether to include successful static resources like images, fonts, scripts, etc. Defaults to false.

    Returns:
        List of network requests
    """
    return await _call_playwright_tool("browser_network_requests", {"includeStatic": includeStatic})


# =============================================================================
# TAB MANAGEMENT TOOLS
# =============================================================================


@mcp.tool()
async def browser_tabs(action: str, index: int | None = None) -> dict[str, Any]:
    """
    List, create, close, or select a browser tab.

    Args:
        action: Operation to perform. Must be 'list', 'new', 'close', or 'select'.
        index: Tab index, used for close/select. If omitted for close, current tab is closed.

    Returns:
        Tab operation result
    """
    args = {"action": action}
    if index is not None:
        args["index"] = index

    return await _call_playwright_tool("browser_tabs", args)


# =============================================================================
# CONSOLE TOOLS
# =============================================================================


@mcp.tool()
async def browser_console_messages(level: str = "info") -> dict[str, Any]:
    """
    Returns all console messages.

    Args:
        level: Level of the console messages to return. Each level includes the messages of more severe levels.
               Must be 'error', 'warning', 'info', or 'debug'. Defaults to "info".

    Returns:
        List of console messages
    """
    return await _call_playwright_tool("browser_console_messages", {"level": level})


# =============================================================================
# DIALOG TOOLS
# =============================================================================


@mcp.tool()
async def browser_handle_dialog(accept: bool, promptText: str | None = None) -> dict[str, Any]:
    """
    Handle a dialog.

    Args:
        accept: Whether to accept the dialog.
        promptText: The text of the prompt in case of a prompt dialog.

    Returns:
        Dialog handling result
    """
    args = {"accept": accept}
    if promptText is not None:
        args["promptText"] = promptText

    return await _call_playwright_tool("browser_handle_dialog", args)


# =============================================================================
# FILE UPLOAD TOOLS
# =============================================================================


@mcp.tool()
async def browser_file_upload(paths: list[str] | None = None) -> dict[str, Any]:
    """
    Upload one or multiple files.

    Args:
        paths: The absolute paths to the files to upload. Can be single file or multiple files.
               If omitted, file chooser is cancelled.

    Returns:
        File upload result
    """
    args = {}
    if paths is not None:
        args["paths"] = paths

    return await _call_playwright_tool("browser_file_upload", args)


# =============================================================================
# TRACING TOOLS
# =============================================================================


@mcp.tool()
async def browser_start_tracing() -> dict[str, Any]:
    """
    Start trace recording.

    Returns:
        Trace start result
    """
    return await _call_playwright_tool("browser_start_tracing", {})


@mcp.tool()
async def browser_stop_tracing() -> dict[str, Any]:
    """
    Stop trace recording.

    Returns:
        Trace stop result
    """
    return await _call_playwright_tool("browser_stop_tracing", {})


# =============================================================================
# INSTALLATION TOOLS
# =============================================================================


@mcp.tool()
async def browser_install() -> dict[str, Any]:
    """
    Install the browser specified in the config. Call this if you get an error about the browser not being installed.

    Returns:
        Installation result
    """
    return await _call_playwright_tool("browser_install", {})


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
