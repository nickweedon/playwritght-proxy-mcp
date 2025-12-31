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

    def __init__(
        self,
        log_request_params: bool = True,
        log_response_data: bool = False,
        max_log_length: int = 5000,
    ):
        """
        Initialize the logging middleware.

        Args:
            log_request_params: Log request parameters (default: True)
            log_response_data: Log full response data (default: False for brevity)
                             Response data can be very large for snapshots/screenshots
            max_log_length: Maximum length for logged data before truncation (default: 5000)
        """
        self.log_request_params = log_request_params
        self.log_response_data = log_response_data
        self.max_log_length = max_log_length

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """Log tool calls from MCP clients"""
        # context.message is CallToolRequestParams (Pydantic model with name, arguments)
        tool_name = getattr(context.message, "name", "unknown")
        arguments = getattr(context.message, "arguments", {}) or {}

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
        # context.message is ReadResourceRequestParams (Pydantic model with uri)
        uri = str(getattr(context.message, "uri", "unknown"))

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
        # context.message is GetPromptRequestParams (Pydantic model with name, arguments)
        name = getattr(context.message, "name", "unknown")
        arguments = getattr(context.message, "arguments", {}) or {}

        start_time = time.time()

        logger.info(f"CLIENT_MCP → Prompt request: {name}")
        if self.log_request_params and arguments:
            logger.info(
                f"CLIENT_MCP   Prompt arguments: {self._truncate_data(arguments, max_length=self.max_log_length)}"
            )

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

            # result is a Sequence[Tool], not a dict
            tool_count = len(result) if result else 0
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

            # result is a Sequence[Resource], not a dict
            resource_count = len(result) if result else 0
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

            # result is a Sequence[Prompt], not a dict
            prompt_count = len(result) if result else 0
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
        # context.message is InitializeRequest (Pydantic model with params attribute)
        params = getattr(context.message, "params", None)
        if params:
            client_info = getattr(params, "clientInfo", None)
            protocol_version = getattr(params, "protocolVersion", "unknown")

            # clientInfo is also a Pydantic model (Implementation)
            if client_info:
                client_name = getattr(client_info, "name", "unknown")
                client_version = getattr(client_info, "version", "unknown")
            else:
                client_name = "unknown"
                client_version = "unknown"
        else:
            client_name = "unknown"
            client_version = "unknown"
            protocol_version = "unknown"

        logger.info(
            f"CLIENT_MCP → Initialize: {client_name} "
            f"v{client_version} (protocol: {protocol_version})"
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
            logger.info(f"CLIENT_MCP   Tool '{tool_name}' arguments: (none)")
            return

        # Truncate large arguments to prevent log flooding
        truncated_args = self._truncate_data(arguments, max_length=self.max_log_length)
        logger.info(f"CLIENT_MCP   Tool '{tool_name}' arguments: {truncated_args}")

    def _log_result(self, tool_name: str, result: Any) -> None:
        """Log tool result with truncation for large values"""
        # Truncate large results to prevent log flooding
        truncated_result = self._truncate_data(result, max_length=self.max_log_length)
        logger.info(f"CLIENT_MCP   Tool '{tool_name}' result: {truncated_result}")

    def _truncate_data(self, data: Any, max_length: int) -> str:
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
