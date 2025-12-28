"""
MCP Request/Response Logging Middleware

Logs all incoming MCP requests and outgoing responses to track client interactions.
Uses clear prefixes to distinguish from upstream playwright-mcp proxy calls.
"""

import json
import logging
import time
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

logger = logging.getLogger(__name__)


class MCPLoggingMiddleware(Middleware):
    """
    Middleware to log all MCP client requests and responses.

    Logs use the prefix "CLIENT_MCP" to distinguish from upstream "UPSTREAM_MCP" logs.
    This makes it easy to filter and search logs using grep or similar tools.

    Examples:
        # Filter for client requests only
        grep "CLIENT_MCP" logs/playwright-proxy-mcp.log

        # Filter for upstream proxy calls only
        grep "UPSTREAM_MCP" logs/playwright-proxy-mcp.log

        # Filter for specific tool calls from clients
        grep "CLIENT_MCP.*tools/call.*browser_navigate" logs/playwright-proxy-mcp.log
    """

    def __init__(self, log_request_params: bool = True, log_response_data: bool = False):
        """
        Initialize the logging middleware.

        Args:
            log_request_params: Log request parameters (default: True)
            log_response_data: Log full response data (default: False for brevity)
                             Response data can be very large for snapshots/screenshots
        """
        self.log_request_params = log_request_params
        self.log_response_data = log_response_data

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Log tool calls from MCP clients"""
        tool_name = context.params.get("name", "unknown")
        arguments = context.params.get("arguments", {})

        start_time = time.time()

        logger.info(f"CLIENT_MCP → Tool call: {tool_name}")
        if self.log_request_params:
            self._log_arguments(tool_name, arguments)

        try:
            result = await call_next(context)
            duration = (time.time() - start_time) * 1000  # ms

            logger.info(f"CLIENT_MCP ← Tool result: {tool_name} ({duration:.2f}ms)")
            if self.log_response_data:
                self._log_result(tool_name, result)

            return result

        except Exception as e:
            duration = (time.time() - start_time) * 1000  # ms
            logger.error(
                f"CLIENT_MCP ✗ Tool error: {tool_name} ({duration:.2f}ms) - {type(e).__name__}: {e}"
            )
            raise

    async def on_read_resource(self, context: MiddlewareContext, call_next):
        """Log resource reads from MCP clients"""
        uri = context.params.get("uri", "unknown")

        start_time = time.time()

        logger.info(f"CLIENT_MCP → Resource read: {uri}")

        try:
            result = await call_next(context)
            duration = (time.time() - start_time) * 1000  # ms

            logger.info(f"CLIENT_MCP ← Resource result: {uri} ({duration:.2f}ms)")
            return result

        except Exception as e:
            duration = (time.time() - start_time) * 1000  # ms
            logger.error(
                f"CLIENT_MCP ✗ Resource error: {uri} ({duration:.2f}ms) - {type(e).__name__}: {e}"
            )
            raise

    async def on_get_prompt(self, context: MiddlewareContext, call_next):
        """Log prompt requests from MCP clients"""
        name = context.params.get("name", "unknown")
        arguments = context.params.get("arguments", {})

        start_time = time.time()

        logger.info(f"CLIENT_MCP → Prompt request: {name}")
        if self.log_request_params and arguments:
            logger.debug(f"CLIENT_MCP   Prompt arguments: {self._truncate_data(arguments)}")

        try:
            result = await call_next(context)
            duration = (time.time() - start_time) * 1000  # ms

            logger.info(f"CLIENT_MCP ← Prompt result: {name} ({duration:.2f}ms)")
            return result

        except Exception as e:
            duration = (time.time() - start_time) * 1000  # ms
            logger.error(
                f"CLIENT_MCP ✗ Prompt error: {name} ({duration:.2f}ms) - {type(e).__name__}: {e}"
            )
            raise

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        """Log tool list requests from MCP clients"""
        start_time = time.time()

        logger.info("CLIENT_MCP → List tools")

        try:
            result = await call_next(context)
            duration = (time.time() - start_time) * 1000  # ms

            tool_count = len(result.get("tools", []))
            logger.info(f"CLIENT_MCP ← List tools result: {tool_count} tools ({duration:.2f}ms)")
            return result

        except Exception as e:
            duration = (time.time() - start_time) * 1000  # ms
            logger.error(
                f"CLIENT_MCP ✗ List tools error: ({duration:.2f}ms) - {type(e).__name__}: {e}"
            )
            raise

    async def on_list_resources(self, context: MiddlewareContext, call_next):
        """Log resource list requests from MCP clients"""
        start_time = time.time()

        logger.info("CLIENT_MCP → List resources")

        try:
            result = await call_next(context)
            duration = (time.time() - start_time) * 1000  # ms

            resource_count = len(result.get("resources", []))
            logger.info(
                f"CLIENT_MCP ← List resources result: {resource_count} resources ({duration:.2f}ms)"
            )
            return result

        except Exception as e:
            duration = (time.time() - start_time) * 1000  # ms
            logger.error(
                f"CLIENT_MCP ✗ List resources error: ({duration:.2f}ms) - {type(e).__name__}: {e}"
            )
            raise

    async def on_list_prompts(self, context: MiddlewareContext, call_next):
        """Log prompt list requests from MCP clients"""
        start_time = time.time()

        logger.info("CLIENT_MCP → List prompts")

        try:
            result = await call_next(context)
            duration = (time.time() - start_time) * 1000  # ms

            prompt_count = len(result.get("prompts", []))
            logger.info(
                f"CLIENT_MCP ← List prompts result: {prompt_count} prompts ({duration:.2f}ms)"
            )
            return result

        except Exception as e:
            duration = (time.time() - start_time) * 1000  # ms
            logger.error(
                f"CLIENT_MCP ✗ List prompts error: ({duration:.2f}ms) - {type(e).__name__}: {e}"
            )
            raise

    async def on_initialize(self, context: MiddlewareContext, call_next):
        """Log MCP initialization from clients"""
        client_info = context.params.get("clientInfo", {})
        protocol_version = context.params.get("protocolVersion", "unknown")

        logger.info(
            f"CLIENT_MCP → Initialize: {client_info.get('name', 'unknown')} "
            f"v{client_info.get('version', 'unknown')} (protocol: {protocol_version})"
        )

        try:
            result = await call_next(context)
            logger.info("CLIENT_MCP ← Initialize complete")
            return result

        except Exception as e:
            logger.error(f"CLIENT_MCP ✗ Initialize error: {type(e).__name__}: {e}")
            raise

    def _log_arguments(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Log tool arguments with truncation for large values"""
        if not arguments:
            logger.debug(f"CLIENT_MCP   Tool '{tool_name}' arguments: (none)")
            return

        # Truncate large arguments to prevent log flooding
        truncated_args = self._truncate_data(arguments)
        logger.debug(f"CLIENT_MCP   Tool '{tool_name}' arguments: {truncated_args}")

    def _log_result(self, tool_name: str, result: Any) -> None:
        """Log tool result with truncation for large values"""
        # Truncate large results to prevent log flooding
        truncated_result = self._truncate_data(result)
        logger.debug(f"CLIENT_MCP   Tool '{tool_name}' result: {truncated_result}")

    def _truncate_data(self, data: Any, max_length: int = 500) -> str:
        """
        Truncate data for logging.

        Args:
            data: Data to truncate
            max_length: Maximum string length

        Returns:
            Truncated string representation
        """
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
