"""
Proxy client integration for playwright-mcp

Manages the connection between FastMCP proxy and the playwright-mcp subprocess,
integrating middleware for response transformation.

Logging uses "UPSTREAM_MCP" prefix to distinguish from "CLIENT_MCP" logs.
"""

import asyncio
import json
import logging
import time
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
        logger.debug(f"UPSTREAM_MCP → Request {request_id}: {method}")
        logger.debug(f"UPSTREAM_MCP   Params: {self._truncate_for_log(params)}")
        process.stdin.write(request_json.encode("utf-8"))
        await process.stdin.drain()

        # Wait for response
        start_time = time.time()
        try:
            response = await asyncio.wait_for(future, timeout=30.0)
            duration = (time.time() - start_time) * 1000  # ms
            logger.debug(f"UPSTREAM_MCP ← Response {request_id}: {method} ({duration:.2f}ms)")
            return response
        except asyncio.TimeoutError:
            self._pending_responses.pop(request_id, None)
            duration = (time.time() - start_time) * 1000  # ms
            logger.error(
                f"UPSTREAM_MCP ✗ Timeout {request_id}: {method} ({duration:.2f}ms) - Request timed out after 30s"
            )
            raise RuntimeError(f"Request timeout for method {method}")

    async def _read_responses(self) -> None:
        """Background task to read responses from subprocess"""
        process = self.process_manager.process
        if not process or not process.stdout:
            return

        try:
            # Set a very large buffer limit for reading large JSON responses
            # MCP responses can be very large (especially page snapshots)
            process.stdout._limit = 10 * 1024 * 1024  # 10MB limit

            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                try:
                    response = json.loads(line.decode("utf-8"))

                    # Handle response
                    if "id" in response:
                        request_id = response["id"]
                        if request_id in self._pending_responses:
                            future = self._pending_responses.pop(request_id)
                            if "error" in response:
                                error_info = response["error"]
                                logger.error(
                                    f"UPSTREAM_MCP ✗ Error response {request_id}: {error_info}"
                                )
                                future.set_exception(
                                    RuntimeError(f"MCP error: {error_info}")
                                )
                            else:
                                logger.debug(
                                    f"UPSTREAM_MCP   Result {request_id}: {self._truncate_for_log(response.get('result'))}"
                                )
                                future.set_result(response.get("result"))
                    else:
                        # Log notifications (messages without id)
                        if "method" in response:
                            logger.debug(
                                f"UPSTREAM_MCP ← Notification: {response.get('method')}"
                            )

                except json.JSONDecodeError as e:
                    logger.error(
                        f"UPSTREAM_MCP ✗ JSON decode error: {line.decode('utf-8')[:200]}: {e}"
                    )
                except Exception as e:
                    logger.error(f"UPSTREAM_MCP ✗ Response processing error: {e}")

        except asyncio.CancelledError:
            logger.debug("Response reader task cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in response reader: {e}")

    async def _initialize_mcp(self) -> None:
        """Perform MCP protocol handshake"""
        logger.info("UPSTREAM_MCP → Initializing protocol with playwright-mcp...")

        # Send initialize request
        result = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "playwright-proxy-mcp", "version": "1.0.0"},
            },
        )

        server_name = result.get("serverInfo", {}).get("name", "unknown")
        server_version = result.get("serverInfo", {}).get("version", "unknown")
        logger.info(f"UPSTREAM_MCP ← Initialized: {server_name} v{server_version}")
        self._initialized = True

    async def _discover_tools(self) -> None:
        """Discover available tools from playwright-mcp"""
        logger.info("UPSTREAM_MCP → Discovering tools from playwright-mcp...")

        result = await self._send_request("tools/list")
        tools = result.get("tools", [])

        for tool in tools:
            tool_name = tool.get("name")
            if tool_name:
                self._available_tools[tool_name] = tool
                logger.debug(f"UPSTREAM_MCP   Discovered tool: {tool_name}")

        logger.info(f"UPSTREAM_MCP ← Discovered {len(self._available_tools)} tools")

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

        logger.info(f"UPSTREAM_MCP → Calling tool: {tool_name}")
        logger.debug(f"UPSTREAM_MCP   Arguments: {self._truncate_for_log(arguments)}")

        start_time = time.time()
        try:
            result = await self._send_request(
                "tools/call", {"name": tool_name, "arguments": arguments}
            )

            # Transform through middleware
            transformed_result = await self.transform_response(tool_name, result)

            duration = (time.time() - start_time) * 1000  # ms
            logger.info(f"UPSTREAM_MCP ← Tool result: {tool_name} ({duration:.2f}ms)")

            return transformed_result

        except Exception as e:
            duration = (time.time() - start_time) * 1000  # ms
            logger.error(
                f"UPSTREAM_MCP ✗ Tool call failed: {tool_name} ({duration:.2f}ms) - {type(e).__name__}: {e}"
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

    def _truncate_for_log(self, data: Any, max_length: int = 500) -> str:
        """
        Truncate data for logging to prevent log flooding.

        Args:
            data: Data to truncate
            max_length: Maximum string length (default: 500)

        Returns:
            Truncated string representation
        """
        if data is None:
            return "None"

        try:
            json_str = json.dumps(data, default=str)
            if len(json_str) > max_length:
                return json_str[:max_length] + f"... ({len(json_str)} chars total)"
            return json_str
        except Exception:
            # Fallback to str() if JSON serialization fails
            str_repr = str(data)
            if len(str_repr) > max_length:
                return str_repr[:max_length] + f"... ({len(str_repr)} chars total)"
            return str_repr
