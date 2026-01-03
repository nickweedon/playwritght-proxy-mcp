"""
Proxy client integration for playwright-mcp

Manages the connection between FastMCP proxy and the playwright-mcp subprocess,
integrating middleware for response transformation.

Uses FastMCP Client with StdioTransport for stdio-based communication.
"""

import asyncio
import logging
import os
import shutil
import time
from typing import Any

from fastmcp.client import Client
from fastmcp.client.transports import StdioTransport

from .config import PlaywrightConfig, should_use_windows_node
from .middleware import BinaryInterceptionMiddleware
from .process_manager import PlaywrightProcessManager

logger = logging.getLogger(__name__)


class PlaywrightProxyClient:
    """
    Custom proxy client that integrates process management and middleware.

    This class manages the playwright-mcp subprocess (running via stdio transport)
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
            process_manager: Process manager for monitoring subprocess
            middleware: Binary interception middleware
        """
        self.process_manager = process_manager
        self.middleware = middleware
        self._client: Client | None = None
        self._transport: StdioTransport | None = None
        self._started = False
        self._available_tools: dict[str, Any] = {}

    async def start(self, config: PlaywrightConfig) -> None:
        """
        Start the proxy client and playwright-mcp via stdio transport.

        Args:
            config: Playwright configuration
        """
        if self._started:
            logger.warning("Proxy client already started")
            return

        logger.info("Starting playwright proxy client with stdio transport...")

        # Build command and environment
        command = self._build_command(config)
        env = self._build_env(config)

        logger.info("=" * 80)
        logger.info("Playwright MCP command configuration:")
        logger.info(f"  Command: {' '.join(command)}")
        logger.info(f"  Working directory: {os.getcwd()}")
        logger.info("=" * 80)

        # Create stdio transport
        self._transport = StdioTransport(
            command=command[0],
            args=command[1:],
            env=env,
            cwd=os.getcwd(),
            keep_alive=True,
            log_file=None,  # We handle logging via process_manager
        )

        # Create FastMCP client with stdio transport
        self._client = Client(transport=self._transport)

        # Start subprocess and connect
        await self._client.__aenter__()

        # Note: StdioTransport manages subprocess internally
        # Process monitoring via process_manager is optional with stdio transport
        # The transport handles subprocess lifecycle automatically

        # Discover available tools
        await self._discover_tools()

        self._started = True
        logger.info("Playwright proxy client started successfully via stdio")
        logger.info("=" * 80)

    async def stop(self) -> None:
        """Stop the proxy client and stdio subprocess"""
        if not self._started:
            return

        logger.info("Stopping playwright proxy client...")

        # Stop process monitoring
        await self.process_manager.stop()

        # Disconnect FastMCP client (automatically terminates subprocess)
        if self._client:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")
            finally:
                self._client = None
                self._transport = None

        self._started = False
        logger.info("Playwright proxy client stopped")

    async def is_healthy(self) -> bool:
        """
        Check if proxy client is healthy with ping verification.

        Returns:
            True if client is started and can respond to tool calls
        """
        if not self._started or not self._client:
            return False

        # Try a lightweight tool call to verify MCP responsiveness
        try:
            # browser_tabs list is lightweight and doesn't navigate
            await asyncio.wait_for(
                self._client.call_tool("browser_tabs", {"action": "list"}),
                timeout=3.0
            )
            return True
        except Exception:
            return False

    def _build_command(self, config: PlaywrightConfig) -> list[str]:
        """
        Build command for stdio mode.

        Args:
            config: Playwright configuration

        Returns:
            List of command parts

        Raises:
            RuntimeError: If required executables are not found
        """
        # Build base command (npx or cmd.exe)
        command = self._build_base_command()

        # Add playwright package
        command.append("@playwright/mcp@latest")

        # Add configuration arguments
        self._add_config_arguments(command, config)

        return command

    def _build_base_command(self) -> list[str]:
        """
        Build the base command (npx or cmd.exe with npx.cmd).

        Returns:
            Base command as list of strings

        Raises:
            RuntimeError: If required executable is not found
        """
        use_windows_node = should_use_windows_node()

        if use_windows_node:
            return self._build_wsl_windows_command()
        else:
            return self._build_standard_command()

    def _build_standard_command(self) -> list[str]:
        """
        Build standard npx command.

        Returns:
            Command starting with npx path

        Raises:
            RuntimeError: If npx is not found in PATH
        """
        logger.info("Standard mode (PW_MCP_PROXY_WSL_WINDOWS not set)")
        logger.info("Using npx from PATH")

        npx_path = shutil.which("npx")
        if not npx_path:
            logger.error("npx not found in PATH")
            raise RuntimeError(
                "npx not found in PATH. Please ensure Node.js is installed."
            )

        logger.info(f"Found npx at: {npx_path}")
        return [npx_path]

    def _build_wsl_windows_command(self) -> list[str]:
        """
        Build WSL->Windows command using cmd.exe.

        Returns:
            Command starting with cmd.exe /c npx.cmd

        Raises:
            RuntimeError: If cmd.exe is not found in PATH
        """
        logger.info("WSL->Windows mode enabled (PW_MCP_PROXY_WSL_WINDOWS set)")
        logger.info("Using Windows npx.cmd via cmd.exe")

        cmd_exe = shutil.which("cmd.exe")
        if not cmd_exe:
            logger.error("cmd.exe not found in PATH")
            raise RuntimeError(
                "cmd.exe not found in PATH. When PW_MCP_PROXY_WSL_WINDOWS is set, "
                "cmd.exe must be available to execute Windows npx.cmd."
            )

        command = [cmd_exe, "/c", "npx.cmd"]
        logger.info(f"Using command: {command}")
        return command

    def _add_config_arguments(self, command: list[str], config: PlaywrightConfig) -> None:
        """
        Add configuration arguments to command.

        Args:
            command: Command list to append to (modified in place)
            config: Playwright configuration
        """
        # Browser configuration
        self._add_browser_args(command, config)

        # Session and storage
        self._add_session_args(command, config)

        # Network and proxy
        self._add_network_args(command, config)

        # Recording and output
        self._add_recording_args(command, config)

        # Timeouts and responses
        self._add_timeout_args(command, config)

        # Stealth and security
        self._add_stealth_args(command, config)

        # Extensions
        self._add_extension_args(command, config)

    def _add_browser_args(self, command: list[str], config: PlaywrightConfig) -> None:
        """Add browser-related arguments."""
        if "browser" in config:
            command.extend(["--browser", config["browser"]])

        if "headless" in config and config["headless"]:
            command.append("--headless")

        if "no_sandbox" in config and config["no_sandbox"]:
            command.append("--no-sandbox")

        if "device" in config and config["device"]:
            command.extend(["--device", config["device"]])

        if "viewport_size" in config and config["viewport_size"]:
            command.extend(["--viewport-size", config["viewport_size"]])

        if "isolated" in config and config["isolated"]:
            command.append("--isolated")

    def _add_session_args(self, command: list[str], config: PlaywrightConfig) -> None:
        """Add session and storage arguments."""
        if "user_data_dir" in config and config["user_data_dir"]:
            command.extend(["--user-data-dir", config["user_data_dir"]])

        if "storage_state" in config and config["storage_state"]:
            command.extend(["--storage-state", config["storage_state"]])

        if "save_session" in config and config["save_session"]:
            command.append("--save-session")

    def _add_network_args(self, command: list[str], config: PlaywrightConfig) -> None:
        """Add network filtering and proxy arguments."""
        if "allowed_origins" in config and config["allowed_origins"]:
            command.extend(["--allowed-origins", config["allowed_origins"]])

        if "blocked_origins" in config and config["blocked_origins"]:
            command.extend(["--blocked-origins", config["blocked_origins"]])

        if "proxy_server" in config and config["proxy_server"]:
            command.extend(["--proxy-server", config["proxy_server"]])

        if "caps" in config and config["caps"]:
            command.extend(["--caps", config["caps"]])

    def _add_recording_args(self, command: list[str], config: PlaywrightConfig) -> None:
        """Add recording and output arguments."""
        if "save_trace" in config and config["save_trace"]:
            command.append("--save-trace")

        if "save_video" in config and config["save_video"]:
            command.extend(["--save-video", config["save_video"]])

        if "output_dir" in config:
            command.extend(["--output-dir", config["output_dir"]])

    def _add_timeout_args(self, command: list[str], config: PlaywrightConfig) -> None:
        """Add timeout and response configuration arguments."""
        if "timeout_action" in config:
            command.extend(["--timeout-action", str(config["timeout_action"])])

        if "timeout_navigation" in config:
            command.extend(["--timeout-navigation", str(config["timeout_navigation"])])

        if "image_responses" in config:
            command.extend(["--image-responses", config["image_responses"]])

    def _add_stealth_args(self, command: list[str], config: PlaywrightConfig) -> None:
        """Add stealth and security arguments."""
        if "user_agent" in config and config["user_agent"]:
            command.extend(["--user-agent", config["user_agent"]])

        if "init_script" in config and config["init_script"]:
            command.extend(["--init-script", config["init_script"]])

        if "ignore_https_errors" in config and config["ignore_https_errors"]:
            command.append("--ignore-https-errors")

    def _add_extension_args(self, command: list[str], config: PlaywrightConfig) -> None:
        """Add extension support arguments."""
        if "extension" in config and config["extension"]:
            command.append("--extension")

        if "shared_browser_context" in config and config["shared_browser_context"]:
            command.append("--shared-browser-context")

    def _build_env(self, config: PlaywrightConfig) -> dict[str, str]:
        """
        Build environment variables for subprocess.

        Args:
            config: Playwright configuration

        Returns:
            Environment dictionary
        """
        env = os.environ.copy()

        # Pass through extension token if configured
        # NOTE: PLAYWRIGHT_MCP_EXTENSION_TOKEN is passed to upstream playwright-mcp server
        # This is one of the limited cases where PLAYWRIGHT_* prefix is correct (not PW_MCP_PROXY_*)
        if "extension_token" in config and config["extension_token"]:
            env["PLAYWRIGHT_MCP_EXTENSION_TOKEN"] = config["extension_token"]
            logger.info("Set PLAYWRIGHT_MCP_EXTENSION_TOKEN in subprocess environment (for upstream playwright-mcp)")

        return env

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

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Call a tool on the upstream playwright-mcp server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result (potentially transformed by middleware)

        Raises:
            RuntimeError: If tool call fails
        """
        if not self._started or not self._client:
            raise RuntimeError("Proxy client not started")

        start_time = time.time()

        # 90-second timeout for tool calls
        timeout_seconds = 90.0
        try:
            logger.info(f"UPSTREAM_MCP → Calling tool: {tool_name}")

            # Call tool via FastMCP client with 90-second timeout
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
            raise RuntimeError(f"Tool call timeout after {timeout_seconds:.0f}s: {tool_name}") from e

        except Exception as e:
            duration = (time.time() - start_time) * 1000  # ms
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
