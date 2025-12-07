"""
Proxy client integration for playwright-mcp

Manages the connection between FastMCP proxy and the playwright-mcp subprocess,
integrating middleware for response transformation.
"""

import asyncio
import logging
from typing import Any

from fastmcp import Context

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

        self._started = True
        logger.info("Playwright proxy client started")

    async def stop(self) -> None:
        """Stop the proxy client and subprocess"""
        if not self._started:
            return

        logger.info("Stopping playwright proxy client...")

        # Stop subprocess
        await self.process_manager.stop()

        self._started = False
        logger.info("Playwright proxy client stopped")

    def is_healthy(self) -> bool:
        """
        Check if proxy client is healthy.

        Returns:
            True if process is running
        """
        return self._started and self.process_manager.is_healthy()

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
