"""
Process manager for playwright-mcp subprocess

Handles spawning, lifecycle management, and communication with the
playwright-mcp Node.js server via npx.
"""

import asyncio
import logging
import shutil
from asyncio.subprocess import Process
from typing import Any

from .config import PlaywrightConfig

logger = logging.getLogger(__name__)


class PlaywrightProcessManager:
    """Manages the playwright-mcp subprocess lifecycle"""

    def __init__(self) -> None:
        self.process: Process | None = None
        self._shutdown_event = asyncio.Event()

    async def start(self, config: PlaywrightConfig) -> Process:
        """
        Start the playwright-mcp subprocess.

        Args:
            config: Playwright configuration

        Returns:
            The subprocess Process object

        Raises:
            RuntimeError: If npx is not available or process fails to start
        """
        # Check if npx is available
        if not shutil.which("npx"):
            raise RuntimeError(
                "npx not found. Please ensure Node.js is installed and npx is in PATH."
            )

        # Build command
        command = await self._build_command(config)

        logger.info(f"Starting playwright-mcp: {' '.join(command)}")

        try:
            # Start subprocess with stdio pipes
            self.process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Give it a moment to start
            await asyncio.sleep(0.5)

            # Check if it's still running
            if self.process.returncode is not None:
                stderr_data = await self.process.stderr.read() if self.process.stderr else b""
                error_msg = stderr_data.decode("utf-8", errors="ignore")
                raise RuntimeError(f"playwright-mcp failed to start: {error_msg}")

            logger.info(f"playwright-mcp started with PID {self.process.pid}")
            return self.process

        except Exception as e:
            logger.error(f"Failed to start playwright-mcp: {e}")
            raise RuntimeError(f"Failed to start playwright-mcp: {e}") from e

    async def stop(self) -> None:
        """Stop the playwright-mcp subprocess gracefully"""
        if self.process is None:
            return

        logger.info("Stopping playwright-mcp subprocess...")

        try:
            # Try graceful termination first
            self.process.terminate()

            # Wait up to 5 seconds for graceful shutdown
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
                logger.info("playwright-mcp stopped gracefully")
            except asyncio.TimeoutError:
                # Force kill if it doesn't stop
                logger.warning("playwright-mcp didn't stop gracefully, forcing kill")
                self.process.kill()
                await self.process.wait()
                logger.info("playwright-mcp killed")

        except Exception as e:
            logger.error(f"Error stopping playwright-mcp: {e}")
        finally:
            self.process = None

    async def restart(self, config: PlaywrightConfig) -> Process:
        """
        Restart the playwright-mcp subprocess.

        Args:
            config: Playwright configuration

        Returns:
            The new subprocess Process object
        """
        logger.info("Restarting playwright-mcp...")
        await self.stop()
        await asyncio.sleep(1.0)  # Brief pause before restart
        return await self.start(config)

    def is_healthy(self) -> bool:
        """
        Check if the playwright-mcp process is healthy.

        Returns:
            True if process is running, False otherwise
        """
        if self.process is None:
            return False

        # Check if process is still running
        return self.process.returncode is None

    async def _build_command(self, config: PlaywrightConfig) -> list[str]:
        """
        Build the npx command with arguments from config.

        Args:
            config: Playwright configuration

        Returns:
            List of command and arguments
        """
        command = ["npx", "@playwright/mcp@latest"]

        # Browser
        if "browser" in config:
            command.extend(["--browser", config["browser"]])

        # Headless
        if "headless" in config and config["headless"]:
            command.append("--headless")

        # Device emulation
        if "device" in config and config["device"]:
            command.extend(["--device", config["device"]])

        # Viewport size
        if "viewport_size" in config and config["viewport_size"]:
            command.extend(["--viewport-size", config["viewport_size"]])

        # Isolated mode
        if "isolated" in config and config["isolated"]:
            command.append("--isolated")

        # User data directory
        if "user_data_dir" in config and config["user_data_dir"]:
            command.extend(["--user-data-dir", config["user_data_dir"]])

        # Storage state
        if "storage_state" in config and config["storage_state"]:
            command.extend(["--storage-state", config["storage_state"]])

        # Network filtering
        if "allowed_origins" in config and config["allowed_origins"]:
            command.extend(["--allowed-origins", config["allowed_origins"]])

        if "blocked_origins" in config and config["blocked_origins"]:
            command.extend(["--blocked-origins", config["blocked_origins"]])

        # Proxy server
        if "proxy_server" in config and config["proxy_server"]:
            command.extend(["--proxy-server", config["proxy_server"]])

        # Capabilities
        if "caps" in config and config["caps"]:
            command.extend(["--caps", config["caps"]])

        # Save session
        if "save_session" in config and config["save_session"]:
            command.append("--save-session")

        # Save trace
        if "save_trace" in config and config["save_trace"]:
            command.append("--save-trace")

        # Save video
        if "save_video" in config and config["save_video"]:
            command.extend(["--save-video", config["save_video"]])

        # Output directory
        if "output_dir" in config:
            command.extend(["--output-dir", config["output_dir"]])

        # Timeouts
        if "timeout_action" in config:
            command.extend(["--timeout-action", str(config["timeout_action"])])

        if "timeout_navigation" in config:
            command.extend(["--timeout-navigation", str(config["timeout_navigation"])])

        # Image responses
        if "image_responses" in config:
            command.extend(["--image-responses", config["image_responses"]])

        return command

    async def get_stderr_output(self) -> str:
        """
        Get any stderr output from the process (non-blocking).

        Returns:
            Stderr output as string
        """
        if self.process is None or self.process.stderr is None:
            return ""

        try:
            # Try to read available data without blocking
            data = b""
            while True:
                try:
                    chunk = self.process.stderr.read(1024)
                    if asyncio.iscoroutine(chunk):
                        chunk = await asyncio.wait_for(chunk, timeout=0.1)
                    if not chunk:
                        break
                    data += chunk
                except asyncio.TimeoutError:
                    break

            return data.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.debug(f"Error reading stderr: {e}")
            return ""
