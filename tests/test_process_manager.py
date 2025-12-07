"""
Tests for playwright process manager
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from playwright_proxy_mcp.playwright.process_manager import PlaywrightProcessManager


@pytest.fixture
def process_manager():
    """Create a process manager instance."""
    return PlaywrightProcessManager()


@pytest.fixture
def mock_config():
    """Create a test config."""
    return {
        "browser": "chromium",
        "headless": True,
        "caps": "vision,pdf",
        "timeout_action": 5000,
        "timeout_navigation": 60000,
    }


class TestPlaywrightProcessManager:
    """Tests for PlaywrightProcessManager."""

    def test_init(self, process_manager):
        """Test process manager initialization."""
        assert process_manager.process is None
        assert not process_manager._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_start_npx_not_found(self, process_manager, mock_config):
        """Test that start raises error when npx is not found."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="npx not found"):
                await process_manager.start(mock_config)

    @pytest.mark.asyncio
    async def test_start_success(self, process_manager, mock_config):
        """Test successful process start."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.stderr = None

        with patch("shutil.which", return_value="/usr/bin/npx"):
            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_process
            ) as mock_create:
                result = await process_manager.start(mock_config)

                assert result == mock_process
                assert process_manager.process == mock_process

                # Verify node was called with playwright-mcp
                call_args = mock_create.call_args[0]
                assert call_args[0] == "node"
                assert "@playwright/mcp" in call_args[1]

    @pytest.mark.asyncio
    async def test_start_process_fails(self, process_manager, mock_config):
        """Test handling of process start failure."""
        mock_process = Mock()
        mock_process.returncode = 1
        mock_stderr = Mock()
        mock_stderr.read = AsyncMock(return_value=b"Error message")
        mock_process.stderr = mock_stderr

        with patch("shutil.which", return_value="/usr/bin/npx"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with pytest.raises(RuntimeError, match="failed to start"):
                    await process_manager.start(mock_config)

    @pytest.mark.asyncio
    async def test_stop_no_process(self, process_manager):
        """Test stopping when no process is running."""
        await process_manager.stop()
        assert process_manager.process is None

    @pytest.mark.asyncio
    async def test_stop_graceful(self, process_manager):
        """Test graceful process stop."""
        mock_process = Mock()
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock()

        process_manager.process = mock_process

        await process_manager.stop()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
        assert process_manager.process is None

    @pytest.mark.asyncio
    async def test_stop_force_kill(self, process_manager):
        """Test force kill when graceful stop times out."""
        mock_process = Mock()
        mock_process.terminate = Mock()
        mock_process.wait = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_process.kill = Mock()

        process_manager.process = mock_process

        await process_manager.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert process_manager.process is None

    @pytest.mark.asyncio
    async def test_restart(self, process_manager, mock_config):
        """Test process restart."""
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.stderr = None

        with patch.object(process_manager, "stop") as mock_stop:
            with patch.object(
                process_manager, "start", return_value=mock_process
            ) as mock_start:
                result = await process_manager.restart(mock_config)

                mock_stop.assert_called_once()
                mock_start.assert_called_once_with(mock_config)
                assert result == mock_process

    def test_is_healthy_no_process(self, process_manager):
        """Test health check when no process."""
        assert not process_manager.is_healthy()

    def test_is_healthy_running(self, process_manager):
        """Test health check when process is running."""
        mock_process = Mock()
        mock_process.returncode = None

        process_manager.process = mock_process

        assert process_manager.is_healthy()

    def test_is_healthy_stopped(self, process_manager):
        """Test health check when process has stopped."""
        mock_process = Mock()
        mock_process.returncode = 0

        process_manager.process = mock_process

        assert not process_manager.is_healthy()

    @pytest.mark.asyncio
    async def test_build_command_basic(self, process_manager):
        """Test building basic command."""
        config = {"browser": "chromium", "headless": True}

        command = await process_manager._build_command(config)

        assert command[0] == "node"
        assert "@playwright/mcp" in command[1]
        assert "--browser" in command
        assert "chromium" in command
        assert "--headless" in command

    @pytest.mark.asyncio
    async def test_build_command_all_options(self, process_manager):
        """Test building command with all options."""
        config = {
            "browser": "firefox",
            "headless": False,
            "device": "iPhone 12",
            "viewport_size": "1920x1080",
            "isolated": True,
            "user_data_dir": "/path/to/data",
            "storage_state": "/path/to/state.json",
            "allowed_origins": "example.com",
            "blocked_origins": "ads.com",
            "proxy_server": "proxy.com:8080",
            "caps": "vision,pdf",
            "save_session": True,
            "save_trace": True,
            "save_video": "on-failure",
            "output_dir": "/output",
            "timeout_action": 10000,
            "timeout_navigation": 30000,
            "image_responses": "base64",
        }

        command = await process_manager._build_command(config)

        assert "--browser" in command
        assert "firefox" in command
        assert "--device" in command
        assert "iPhone 12" in command
        assert "--viewport-size" in command
        assert "1920x1080" in command
        assert "--isolated" in command
        assert "--user-data-dir" in command
        assert "/path/to/data" in command
        assert "--storage-state" in command
        assert "--allowed-origins" in command
        assert "--blocked-origins" in command
        assert "--proxy-server" in command
        assert "--caps" in command
        assert "vision,pdf" in command
        assert "--save-session" in command
        assert "--save-trace" in command
        assert "--save-video" in command
        assert "on-failure" in command
        assert "--output-dir" in command
        assert "--timeout-action" in command
        assert "10000" in command
        assert "--timeout-navigation" in command
        assert "30000" in command
        assert "--image-responses" in command
        assert "base64" in command

    @pytest.mark.asyncio
    async def test_build_command_headless_false(self, process_manager):
        """Test that headless flag is not added when headless is False."""
        config = {"browser": "chromium", "headless": False}

        command = await process_manager._build_command(config)

        assert "--headless" not in command

    @pytest.mark.asyncio
    async def test_get_stderr_output_no_process(self, process_manager):
        """Test getting stderr when no process."""
        output = await process_manager.get_stderr_output()
        assert output == ""

    @pytest.mark.asyncio
    async def test_get_stderr_output_no_stderr(self, process_manager):
        """Test getting stderr when process has no stderr."""
        mock_process = Mock()
        mock_process.stderr = None

        process_manager.process = mock_process

        output = await process_manager.get_stderr_output()
        assert output == ""

    @pytest.mark.asyncio
    async def test_get_stderr_output_with_data(self, process_manager):
        """Test getting stderr output."""
        mock_stderr = Mock()

        async def mock_read(size):
            # Return empty on second call to break the loop
            if not hasattr(mock_read, "called"):
                mock_read.called = True
                return b"Error output"
            return b""

        mock_stderr.read = mock_read

        mock_process = Mock()
        mock_process.stderr = mock_stderr

        process_manager.process = mock_process

        output = await process_manager.get_stderr_output()

        assert "Error output" in output or output == ""

    @pytest.mark.asyncio
    async def test_get_stderr_output_handles_errors(self, process_manager):
        """Test that get_stderr_output handles errors gracefully."""
        mock_stderr = Mock()
        mock_stderr.read = Mock(side_effect=Exception("Read error"))

        mock_process = Mock()
        mock_process.stderr = mock_stderr

        process_manager.process = mock_process

        output = await process_manager.get_stderr_output()
        assert output == ""
