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


@pytest.fixture
def mock_subprocess():
    """Create a mock subprocess with stdout/stderr streams."""
    mock_process = Mock()
    mock_process.pid = 12345
    mock_process.returncode = None

    # Mock stdout stream
    mock_stdout = Mock()
    mock_stdout.readline = AsyncMock(return_value=b"")
    mock_process.stdout = mock_stdout

    # Mock stderr stream with port discovery message
    mock_stderr = Mock()
    # First call returns the "Listening on" message, subsequent calls return empty
    mock_stderr.readline = AsyncMock(
        side_effect=[
            b"Listening on http://127.0.0.1:3000\n",
            b"",
        ]
    )
    mock_process.stderr = mock_stderr

    return mock_process


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
    async def test_start_success(self, process_manager, mock_config, mock_subprocess):
        """Test successful process start."""
        with patch("shutil.which", return_value="/usr/bin/npx"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess) as mock_create:
                with patch.object(process_manager, "_wait_for_http_ready", new_callable=AsyncMock, return_value=True):
                    result = await process_manager.start(mock_config)

                    assert result == mock_subprocess
                    assert process_manager.process == mock_subprocess

                    # Verify npx was called with @playwright/mcp@latest
                    call_args = mock_create.call_args[0]
                    assert call_args[0] == "/usr/bin/npx"
                    assert call_args[1] == "@playwright/mcp@latest"

                    # Clean up background tasks
                    if hasattr(process_manager, "_stdout_task"):
                        process_manager._stdout_task.cancel()
                        try:
                            await process_manager._stdout_task
                        except asyncio.CancelledError:
                            pass
                    if hasattr(process_manager, "_stderr_task"):
                        process_manager._stderr_task.cancel()
                        try:
                            await process_manager._stderr_task
                        except asyncio.CancelledError:
                            pass

    @pytest.mark.asyncio
    async def test_start_process_fails(self, process_manager, mock_config):
        """Test handling of process start failure."""
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.pid = 12345

        # Mock streams for the logging tasks
        mock_stderr = Mock()
        mock_stderr.readline = AsyncMock(return_value=b"")
        mock_stderr.read = AsyncMock(return_value=b"Error message")
        mock_process.stderr = mock_stderr

        mock_stdout = Mock()
        mock_stdout.readline = AsyncMock(return_value=b"")
        mock_stdout.read = AsyncMock(return_value=b"")
        mock_process.stdout = mock_stdout

        with patch("shutil.which", return_value="/usr/bin/npx"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                with patch.object(process_manager, "_wait_for_http_ready", new_callable=AsyncMock, return_value=False):
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
            with patch.object(process_manager, "start", return_value=mock_process) as mock_start:
                result = await process_manager.restart(mock_config)

                mock_stop.assert_called_once()
                mock_start.assert_called_once_with(mock_config)
                assert result == mock_process

    @pytest.mark.asyncio
    async def test_is_healthy_no_process(self, process_manager):
        """Test health check when no process."""
        assert not await process_manager.is_healthy()

    @pytest.mark.asyncio
    async def test_is_healthy_running(self, process_manager):
        """Test health check when process is running."""
        mock_process = Mock()
        mock_process.returncode = None

        process_manager.process = mock_process
        process_manager._actual_port = 3000

        # Mock aiohttp client session
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock()

        mock_session = Mock()
        mock_session.get = Mock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        with patch("aiohttp.ClientSession", return_value=mock_session):
            assert await process_manager.is_healthy()

    @pytest.mark.asyncio
    async def test_is_healthy_stopped(self, process_manager):
        """Test health check when process has stopped."""
        mock_process = Mock()
        mock_process.returncode = 0

        process_manager.process = mock_process
        process_manager._actual_port = 3000

        assert not await process_manager.is_healthy()

    @pytest.mark.asyncio
    async def test_build_command_basic(self, process_manager):
        """Test building basic command."""
        config = {"browser": "chromium", "headless": True}

        command = await process_manager._build_command(config, ["/usr/bin/npx"], "127.0.0.1")

        assert command[0] == "/usr/bin/npx"
        assert command[1] == "@playwright/mcp@latest"
        assert "--host" in command
        assert "127.0.0.1" in command
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

        command = await process_manager._build_command(config, ["/usr/bin/npx"], "127.0.0.1")

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

        command = await process_manager._build_command(config, ["/usr/bin/npx"], "127.0.0.1")

        assert "--headless" not in command

    @pytest.mark.asyncio
    async def test_start_with_wsl_host_connect(self, process_manager, mock_config, mock_subprocess, monkeypatch):
        """Test that PLAYWRIGHT_WSL_HOST_CONNECT enables WSL->Windows mode."""
        monkeypatch.setenv("PLAYWRIGHT_WSL_HOST_CONNECT", "172.22.96.1")

        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/mnt/c/WINDOWS/system32/cmd.exe"

            with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess) as mock_create:
                with patch.object(process_manager, "_wait_for_http_ready", new_callable=AsyncMock, return_value=True):
                    result = await process_manager.start(mock_config)

                    assert result == mock_subprocess

                    # Verify cmd.exe /c npx.cmd was used
                    call_args = mock_create.call_args[0]
                    assert call_args[0] == "/mnt/c/WINDOWS/system32/cmd.exe"
                    assert call_args[1] == "/c"
                    assert call_args[2] == "npx.cmd"
                    assert call_args[3] == "@playwright/mcp@latest"

                    # Verify server binds to Windows host IP in WSL mode
                    assert "--host" in call_args
                    host_idx = call_args.index("--host")
                    assert call_args[host_idx + 1] == "172.22.96.1"

                    # Verify playwright_host was set correctly
                    assert process_manager._playwright_host == "172.22.96.1"

                    # Clean up background tasks
                    if hasattr(process_manager, "_stdout_task"):
                        process_manager._stdout_task.cancel()
                        try:
                            await process_manager._stdout_task
                        except asyncio.CancelledError:
                            pass
                    if hasattr(process_manager, "_stderr_task"):
                        process_manager._stderr_task.cancel()
                        try:
                            await process_manager._stderr_task
                        except asyncio.CancelledError:
                            pass

    @pytest.mark.asyncio
    async def test_start_with_wsl_host_connect_no_cmd_exe(self, process_manager, mock_config, monkeypatch):
        """Test that WSL mode fails when cmd.exe is not found."""
        monkeypatch.setenv("PLAYWRIGHT_WSL_HOST_CONNECT", "172.22.96.1")

        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="cmd.exe not found in PATH"):
                await process_manager.start(mock_config)

    @pytest.mark.asyncio
    async def test_start_without_wsl_host_connect_uses_default(self, process_manager, mock_config, mock_subprocess):
        """Test that default npx is used when PLAYWRIGHT_WSL_HOST_CONNECT is not set."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/npx"

            with patch("asyncio.create_subprocess_exec", return_value=mock_subprocess) as mock_create:
                with patch.object(process_manager, "_wait_for_http_ready", new_callable=AsyncMock, return_value=True):
                    result = await process_manager.start(mock_config)

                    assert result == mock_subprocess

                    # Verify default npx was used
                    call_args = mock_create.call_args[0]
                    assert call_args[0] == "/usr/bin/npx"
                    assert call_args[1] == "@playwright/mcp@latest"

                    # Verify server binds to 127.0.0.1 in standard mode
                    assert "--host" in call_args
                    host_idx = call_args.index("--host")
                    assert call_args[host_idx + 1] == "127.0.0.1"

                    # Verify playwright_host defaults to localhost
                    assert process_manager._playwright_host == "127.0.0.1"

                    # Verify shutil.which was called with "npx"
                    mock_which.assert_called_with("npx")

                    # Clean up background tasks
                    if hasattr(process_manager, "_stdout_task"):
                        process_manager._stdout_task.cancel()
                        try:
                            await process_manager._stdout_task
                        except asyncio.CancelledError:
                            pass
                    if hasattr(process_manager, "_stderr_task"):
                        process_manager._stderr_task.cancel()
                        try:
                            await process_manager._stderr_task
                        except asyncio.CancelledError:
                            pass

    @pytest.mark.asyncio
    async def test_start_npx_not_found_in_path(self, process_manager, mock_config):
        """Test error when npx is not found in PATH and no override is set."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="npx not found in PATH"):
                await process_manager.start(mock_config)

    @pytest.mark.asyncio
    async def test_build_command_with_wsl_mode(self, process_manager):
        """Test that WSL mode binds to 0.0.0.0."""
        config = {"browser": "chromium", "headless": True}

        # WSL mode uses the Windows host IP for binding
        command = await process_manager._build_command(
            config, ["cmd.exe", "/c", "npx.cmd"], "172.22.96.1"
        )

        # Should start with the multi-part command
        assert command[0] == "cmd.exe"
        assert command[1] == "/c"
        assert command[2] == "npx.cmd"
        assert command[3] == "@playwright/mcp@latest"
        assert "--host" in command
        assert "172.22.96.1" in command  # Server binds to Windows host IP in WSL mode
        assert "--browser" in command
        assert "chromium" in command

