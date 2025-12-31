"""
Proxy client integration for playwright-mcp

Manages the connection between FastMCP proxy and the playwright-mcp HTTP server,
integrating middleware for response transformation.

Uses FastMCP Client with StreamableHttpTransport for HTTP-based communication.
"""

import asyncio
import logging
import time
from typing import Any

from fastmcp.client import Client
from fastmcp.client.transports import StreamableHttpTransport

from .middleware import BinaryInterceptionMiddleware
from .process_manager import PlaywrightProcessManager

logger = logging.getLogger(__name__)


class PlaywrightProxyClient:
    """
    Custom proxy client that integrates process management and middleware.

    This class manages the playwright-mcp subprocess (running as HTTP server)
    and provides hooks for response transformation through middleware.
    """

    def __init__(
        self,
        process_manager: PlaywrightProcessManager,
        middleware: BinaryInterceptionMiddleware,
    ) -> None:
        """
        Initialize proxy client.

        Args:
            process_manager: Process manager for playwright-mcp
            middleware: Binary interception middleware
        """
        self.process_manager = process_manager
        self.middleware = middleware
        self._client: Client | None = None
        self._started = False
        self._available_tools: dict[str, Any] = {}

    async def start(self, config: Any) -> None:
        """
        Start the proxy client and playwright-mcp HTTP server.

        Args:
            config: Playwright configuration
        """
        if self._started:
            logger.warning("Proxy client already started")
            return

        logger.info("Starting playwright proxy client...")

        # Start playwright-mcp HTTP server subprocess
        await self.process_manager.start(config)

        # Get the actual port from process manager (discovered from server output)
        actual_port = self.process_manager.get_port()
        logger.info(f"Connecting to playwright-mcp on port {actual_port}")

        # Get the playwright host from process manager (127.0.0.1 or WSL host IP)
        playwright_host = self.process_manager._playwright_host

        # Create HTTP transport with discovered port and host
        transport = StreamableHttpTransport(
            url=f"http://{playwright_host}:{actual_port}/mcp"
        )

        # Create and connect FastMCP client
        self._client = Client(transport=transport)
        await self._client.__aenter__()

        # Discover available tools
        await self._discover_tools()

        self._started = True
        logger.info("Playwright proxy client started")

    async def stop(self) -> None:
        """Stop the proxy client and HTTP server subprocess"""
        if not self._started:
            return

        logger.info("Stopping playwright proxy client...")

        # Disconnect FastMCP client
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")
            finally:
                self._client = None

        # Stop subprocess
        await self.process_manager.stop()

        self._started = False
        logger.info("Playwright proxy client stopped")

    async def is_healthy(self) -> bool:
        """
        Check if the proxy client is healthy.

        Returns:
            True if client is started and process is healthy
        """
        if not self._started or not self._client:
            return False

        return await self.process_manager.is_healthy()

    async def _discover_tools(self) -> None:
        """
        Discover available tools from playwright-mcp.
        """
        try:
            logger.info("UPSTREAM_MCP → Discovering tools...")

            # List tools via FastMCP client
            tools = await self._client.list_tools()

            # Convert to dictionary
            self._available_tools = {}
            for tool in tools:
                self._available_tools[tool.name] = {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }

            logger.info(
                f"UPSTREAM_MCP ← Discovered {len(self._available_tools)} tools: "
                f"{', '.join(self._available_tools.keys())}"
            )

        except Exception as e:
            logger.error(f"UPSTREAM_MCP ✗ Tool discovery failed: {e}")
            raise RuntimeError(f"Failed to discover tools: {e}") from e

    async def _reconnect_client(self) -> None:
        """
        Reconnect the FastMCP client to the upstream playwright-mcp server.

        This is called when a session termination error is detected to attempt
        to recover the connection.
        """
        logger.info("UPSTREAM_MCP ⟳ Reconnecting client...")

        # Disconnect existing client
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error during client disconnect: {e}")
            finally:
                self._client = None

        # Get the actual port from process manager
        actual_port = self.process_manager.get_port()

        # Get the playwright host from process manager (127.0.0.1 or WSL host IP)
        playwright_host = self.process_manager._playwright_host

        # Create new HTTP transport with discovered port and host
        transport = StreamableHttpTransport(
            url=f"http://{playwright_host}:{actual_port}/mcp"
        )

        # Create and connect new FastMCP client
        self._client = Client(transport=transport)
        await self._client.__aenter__()

        # Re-discover tools to verify connection
        await self._discover_tools()

        logger.info("UPSTREAM_MCP ← Client reconnected successfully")

    async def call_tool(self, tool_name: str, arguments: dict[str, Any], _retry_count: int = 0) -> Any:
        """
        Call a tool on the upstream playwright-mcp server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            _retry_count: Internal retry counter (for session recovery)

        Returns:
            Tool result (potentially transformed by middleware)

        Raises:
            RuntimeError: If tool call fails
        """
        if not self._started or not self._client:
            raise RuntimeError("Proxy client not started")

        start_time = time.time()

        # 90-second timeout for tool calls, this is in addition to PLAYWRIGHT_TIMEOUT_NAVIGATION and PLAYWRIGHT_TIMEOUT_ACTION
        timeout_seconds = 90.0  
        try:
            logger.info(f"UPSTREAM_MCP → Calling tool: {tool_name}")

            # Call tool via FastMCP client with 90-second timeout
            # This prevents indefinite hangs when playwright-mcp gets stuck
            # (e.g., browser_navigate_back in certain browser states)
            result = await asyncio.wait_for(
                self._client.call_tool(tool_name, arguments),
                timeout=timeout_seconds
            )
            logger.info(f"Raw tool result for {tool_name}: {result}")

            # Check for errors (FastMCP Client uses snake_case: is_error)
            if result.is_error:
                # Extract error message from first content item
                error_text = (
                    result.content[0].text if result.content else "Unknown error"
                )
                raise RuntimeError(f"Tool call failed: {error_text}")

            # Transform through middleware
            transformed_result = await self.transform_response(tool_name, result)

            duration = (time.time() - start_time) * 1000  # ms
            logger.info(f"UPSTREAM_MCP ← Tool result: {tool_name} ({duration:.2f}ms)")

            return transformed_result

        except asyncio.TimeoutError as e:
            duration = (time.time() - start_time) * 1000  # ms
            logger.error(
                f"UPSTREAM_MCP ✗ Tool call timeout: {tool_name} ({duration:.2f}ms) - "
                f"Exceeded {timeout_seconds:.0f} second timeout"
            )
            raise RuntimeError(f"Tool call timeout after {timeout_seconds:.0f} seconds: {tool_name}") from e

        except Exception as e:
            duration = (time.time() - start_time) * 1000  # ms

            # Check if this is a session termination error and retry once
            error_str = str(e).lower()
            if ("session terminated" in error_str or "session not found" in error_str) and _retry_count == 0:
                logger.warning(
                    f"UPSTREAM_MCP ⟳ Session terminated, attempting to reconnect and retry: {tool_name} ({duration:.2f}ms)"
                )

                # Attempt to reconnect the client
                try:
                    await self._reconnect_client()
                    # Retry the tool call once
                    return await self.call_tool(tool_name, arguments, _retry_count=1)
                except Exception as reconnect_error:
                    logger.error(f"UPSTREAM_MCP ✗ Reconnection failed: {reconnect_error}")
                    raise RuntimeError(f"Session terminated and reconnection failed: {e}") from e

            logger.error(
                f"UPSTREAM_MCP ✗ Tool call failed: {tool_name} ({duration:.2f}ms) - "
                f"{type(e).__name__}: {e}"
            )
            raise

    def get_available_tools(self) -> dict[str, Any]:
        """
        Get the list of available tools.

        Returns:
            Dictionary of tool name to tool definition
        """
        return self._available_tools.copy()

    async def transform_response(self, tool_name: str, response: Any) -> Any:
        """
        Transform a tool response through middleware.

        This is called after receiving a response from playwright-mcp to
        potentially intercept and store large binary data.

        Args:
            tool_name: Name of the tool that was called
            response: Response from playwright-mcp (CallToolResult)

        Returns:
            Potentially transformed response
        """
        try:
            return await self.middleware.intercept_response(tool_name, response)
        except Exception as e:
            logger.error(f"Error transforming response for {tool_name}: {e}")
            # Return original response if transformation fails
            return response

    def get_process(self) -> Any:
        """
        Get the underlying subprocess.

        Returns:
            The playwright-mcp subprocess
        """
        return self.process_manager.process
