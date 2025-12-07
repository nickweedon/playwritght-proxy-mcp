"""
Proxy client integration for playwright-mcp

Manages the connection between FastMCP proxy and the playwright-mcp subprocess,
integrating middleware for response transformation.
"""

import asyncio
import json
import logging
from typing import Any

from .middleware import BinaryInterceptionMiddleware
from .process_manager import PlaywrightProcessManager

logger = logging.getLogger(__name__)


class PlaywrightProxyClient:
    """
    Custom proxy client that integrates process management and middleware.

    This class manages the playwright-mcp subprocess and provides hooks for
    response transformation through middleware.
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
        self._started = False
        self._initialized = False
        self._available_tools: dict[str, Any] = {}
        self._request_id = 0
        self._pending_responses: dict[int, asyncio.Future] = {}
        self._response_reader_task: asyncio.Task | None = None

    async def start(self, config: Any) -> None:
        """
        Start the proxy client and playwright-mcp subprocess.

        Args:
            config: Playwright configuration
        """
        if self._started:
            logger.warning("Proxy client already started")
            return

        logger.info("Starting playwright proxy client...")

        # Start playwright-mcp subprocess
        await self.process_manager.start(config)

        # Start response reader task
        self._response_reader_task = asyncio.create_task(self._read_responses())

        # Perform MCP handshake
        await self._initialize_mcp()

        # Discover available tools
        await self._discover_tools()

        self._started = True
        logger.info("Playwright proxy client started")

    async def stop(self) -> None:
        """Stop the proxy client and subprocess"""
        if not self._started:
            return

        logger.info("Stopping playwright proxy client...")

        # Cancel response reader task
        if self._response_reader_task:
            self._response_reader_task.cancel()
            try:
                await self._response_reader_task
            except asyncio.CancelledError:
                pass

        # Stop subprocess
        await self.process_manager.stop()

        self._started = False
        self._initialized = False
        logger.info("Playwright proxy client stopped")

    def is_healthy(self) -> bool:
        """
        Check if proxy client is healthy.

        Returns:
            True if process is running
        """
        return self._started and self.process_manager.is_healthy()

    async def _send_request(self, method: str, params: Any = None) -> Any:
        """
        Send a JSON-RPC request to the playwright-mcp subprocess.

        Args:
            method: JSON-RPC method name
            params: Optional parameters

        Returns:
            Response result

        Raises:
            RuntimeError: If request fails
        """
        process = self.process_manager.process
        if not process or not process.stdin or not process.stdout:
            raise RuntimeError("Playwright subprocess not properly initialized")

        # Generate request ID
        self._request_id += 1
        request_id = self._request_id

        # Create future for response
        future = asyncio.Future()
        self._pending_responses[request_id] = future

        # Create JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        # Send request
        request_json = json.dumps(request) + "\n"
        logger.debug(f"Sending request: {request_json.strip()}")
        process.stdin.write(request_json.encode("utf-8"))
        await process.stdin.drain()

        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=30.0)
            return response
        except asyncio.TimeoutError:
            self._pending_responses.pop(request_id, None)
            raise RuntimeError(f"Request timeout for method {method}")

    async def _read_responses(self) -> None:
        """Background task to read responses from subprocess"""
        process = self.process_manager.process
        if not process or not process.stdout:
            return

        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                try:
                    response = json.loads(line.decode("utf-8"))
                    logger.debug(f"Received response: {response}")

                    # Handle response
                    if "id" in response:
                        request_id = response["id"]
                        if request_id in self._pending_responses:
                            future = self._pending_responses.pop(request_id)
                            if "error" in response:
                                future.set_exception(
                                    RuntimeError(f"MCP error: {response['error']}")
                                )
                            else:
                                future.set_result(response.get("result"))
                    # Ignore notifications (no id)

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode response: {line.decode('utf-8')}: {e}")
                except Exception as e:
                    logger.error(f"Error processing response: {e}")

        except asyncio.CancelledError:
            logger.debug("Response reader task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in response reader: {e}")

    async def _initialize_mcp(self) -> None:
        """Perform MCP protocol handshake"""
        logger.info("Initializing MCP protocol with playwright-mcp...")

        # Send initialize request
        result = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "playwright-proxy-mcp", "version": "1.0.0"},
            },
        )

        logger.info(f"MCP initialized: {result.get('serverInfo', {}).get('name')}")
        self._initialized = True

    async def _discover_tools(self) -> None:
        """Discover available tools from playwright-mcp"""
        logger.info("Discovering tools from playwright-mcp...")

        result = await self._send_request("tools/list")
        tools = result.get("tools", [])

        for tool in tools:
            tool_name = tool.get("name")
            if tool_name:
                self._available_tools[tool_name] = tool
                logger.debug(f"Discovered tool: {tool_name}")

        logger.info(f"Discovered {len(self._available_tools)} tools from playwright-mcp")

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Call a tool on the playwright-mcp subprocess.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result (potentially transformed by middleware)

        Raises:
            RuntimeError: If tool call fails
        """
        if not self._initialized:
            raise RuntimeError("MCP client not initialized")

        if tool_name not in self._available_tools:
            raise RuntimeError(
                f"Tool '{tool_name}' not found. Available tools: {list(self._available_tools.keys())}"
            )

        logger.debug(f"Calling tool: {tool_name} with args: {arguments}")

        result = await self._send_request(
            "tools/call", {"name": tool_name, "arguments": arguments}
        )

        # Transform through middleware
        transformed_result = await self.transform_response(tool_name, result)

        return transformed_result

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
            response: Response from playwright-mcp

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
