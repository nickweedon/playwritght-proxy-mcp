"""
Tests for playwright proxy client
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from playwright_proxy_mcp.playwright.proxy_client import PlaywrightProxyClient


@pytest.fixture
def mock_process_manager():
    """Create a mock process manager."""
    manager = Mock()
    manager.set_process = AsyncMock()
    manager.stop = AsyncMock()
    manager.is_healthy = AsyncMock(return_value=True)
    manager.process = None
    return manager


@pytest.fixture
def mock_middleware():
    """Create a mock middleware."""
    middleware = Mock()
    middleware.intercept_response = AsyncMock(side_effect=lambda tool, resp: resp)
    return middleware


@pytest.fixture
def proxy_client(mock_process_manager, mock_middleware):
    """Create a proxy client instance."""
    return PlaywrightProxyClient(mock_process_manager, mock_middleware)


class TestPlaywrightProxyClient:
    """Tests for PlaywrightProxyClient."""

    def test_init(self, mock_process_manager, mock_middleware):
        """Test proxy client initialization."""
        client = PlaywrightProxyClient(mock_process_manager, mock_middleware)

        assert client.process_manager == mock_process_manager
        assert client.middleware == mock_middleware
        assert not client._started

    @pytest.mark.asyncio
    async def test_start(self, proxy_client):
        """Test starting the proxy client."""
        config = {"browser": "chromium", "headless": True}

        # Mock StdioTransport
        mock_transport = Mock()
        mock_transport._process = None

        # Mock the FastMCP Client and its methods
        mock_client = Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])

        # Patch StdioTransport and Client creation
        with patch('playwright_proxy_mcp.playwright.proxy_client.StdioTransport', return_value=mock_transport):
            with patch('playwright_proxy_mcp.playwright.proxy_client.Client', return_value=mock_client):
                with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                    await proxy_client.start(config)

        assert proxy_client._started
        assert proxy_client._client is not None
        assert proxy_client._transport is not None

    @pytest.mark.asyncio
    async def test_start_already_started(self, proxy_client):
        """Test starting when already started."""
        config = {"browser": "chromium"}

        # Mock StdioTransport
        mock_transport = Mock()
        mock_transport._process = None

        # Mock the FastMCP Client
        mock_client = Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])

        # Patch Client creation
        with patch('playwright_proxy_mcp.playwright.proxy_client.StdioTransport', return_value=mock_transport):
            with patch('playwright_proxy_mcp.playwright.proxy_client.Client', return_value=mock_client):
                with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                    await proxy_client.start(config)
                    await proxy_client.start(config)  # Second call should be no-op

        # Should only start once
        assert proxy_client._started
        assert mock_client.__aenter__.call_count == 1

    @pytest.mark.asyncio
    async def test_stop(self, proxy_client, mock_process_manager):
        """Test stopping the proxy client."""
        # Mock the FastMCP Client
        mock_client = Mock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])

        mock_transport = Mock()
        mock_transport._process = None

        # Patch Client creation
        with patch('playwright_proxy_mcp.playwright.proxy_client.StdioTransport', return_value=mock_transport):
            with patch('playwright_proxy_mcp.playwright.proxy_client.Client', return_value=mock_client):
                with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                    # Start first
                    await proxy_client.start({"browser": "chromium"})
                    await proxy_client.stop()

        assert not proxy_client._started
        mock_process_manager.stop.assert_called_once()
        mock_client.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_not_started(self, proxy_client, mock_process_manager):
        """Test stopping when not started."""
        await proxy_client.stop()

        # Should not call stop on process manager
        mock_process_manager.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_is_healthy_started(self, proxy_client):
        """Test health check when started and healthy."""
        proxy_client._started = True

        # Mock client with successful tool call
        mock_client = Mock()
        mock_client.call_tool = AsyncMock(return_value=Mock())
        proxy_client._client = mock_client

        assert await proxy_client.is_healthy()
        mock_client.call_tool.assert_called_once_with("browser_tabs", {"action": "list"})

    @pytest.mark.asyncio
    async def test_is_healthy_not_started(self, proxy_client):
        """Test health check when not started."""
        assert not await proxy_client.is_healthy()

    @pytest.mark.asyncio
    async def test_is_healthy_tool_call_fails(self, proxy_client):
        """Test health check when tool call fails."""
        proxy_client._started = True

        # Mock client with failing tool call
        mock_client = Mock()
        mock_client.call_tool = AsyncMock(side_effect=Exception("Connection failed"))
        proxy_client._client = mock_client

        assert not await proxy_client.is_healthy()

    @pytest.mark.asyncio
    async def test_call_tool(self, proxy_client, mock_middleware):
        """Test calling a tool."""
        proxy_client._started = True

        # Mock client
        mock_result = Mock()
        mock_result.is_error = False
        mock_result.content = [Mock(text="Success")]

        mock_client = Mock()
        mock_client.call_tool = AsyncMock(return_value=mock_result)
        proxy_client._client = mock_client

        result = await proxy_client.call_tool("browser_navigate", {"url": "https://example.com"})

        mock_client.call_tool.assert_called_once_with("browser_navigate", {"url": "https://example.com"})
        mock_middleware.intercept_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_tool_not_started(self, proxy_client):
        """Test calling a tool when not started."""
        with pytest.raises(RuntimeError, match="not started"):
            await proxy_client.call_tool("browser_navigate", {"url": "https://example.com"})

    @pytest.mark.asyncio
    async def test_call_tool_error_result(self, proxy_client):
        """Test calling a tool that returns an error."""
        proxy_client._started = True

        # Mock client with error result
        mock_result = Mock()
        mock_result.is_error = True
        mock_result.content = [Mock(text="Navigation failed")]

        mock_client = Mock()
        mock_client.call_tool = AsyncMock(return_value=mock_result)
        proxy_client._client = mock_client

        with pytest.raises(RuntimeError, match="Tool call failed"):
            await proxy_client.call_tool("browser_navigate", {"url": "https://example.com"})

    def test_get_available_tools(self, proxy_client):
        """Test getting available tools."""
        proxy_client._available_tools = {"tool1": {"name": "tool1"}, "tool2": {"name": "tool2"}}

        tools = proxy_client.get_available_tools()

        assert len(tools) == 2
        assert "tool1" in tools
        assert "tool2" in tools

    @pytest.mark.asyncio
    async def test_transform_response(self, proxy_client, mock_middleware):
        """Test transform_response."""
        mock_response = Mock()
        # intercept_response is an AsyncMock, so set its return value properly
        async def mock_intercept(tool, resp):
            return "transformed"
        mock_middleware.intercept_response = AsyncMock(side_effect=mock_intercept)

        result = await proxy_client.transform_response("browser_navigate", mock_response)

        assert result == "transformed"
        mock_middleware.intercept_response.assert_called_once_with("browser_navigate", mock_response)

    @pytest.mark.asyncio
    async def test_build_command_standard_mode(self, proxy_client):
        """Test command building in standard mode."""
        config = {"browser": "firefox", "headless": True, "viewport_size": "1024x768"}

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        assert command[0] == '/usr/bin/npx'
        assert '@playwright/mcp@latest' in command
        assert '--browser' in command
        assert 'firefox' in command
        assert '--headless' in command
        assert '--viewport-size' in command
        # Verify NO HTTP args
        assert '--host' not in command
        assert '--port' not in command

    @pytest.mark.asyncio
    async def test_build_command_wsl_windows_mode(self, proxy_client):
        """Test command building in WSL-Windows mode."""
        config = {"browser": "chrome"}

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=True):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='C:\\Windows\\System32\\cmd.exe'):
                command = proxy_client._build_command(config)

        assert 'cmd.exe' in command[0]
        assert '/c' in command
        assert 'npx.cmd' in command
        assert '@playwright/mcp@latest' in command

    def test_build_command_minimal_config(self, proxy_client):
        """Test command building with minimal configuration."""
        config = {}

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        # Should only have npx and package
        assert command == ['/usr/bin/npx', '@playwright/mcp@latest']

    def test_build_command_all_boolean_flags(self, proxy_client):
        """Test command building with all boolean flags enabled."""
        config = {
            "headless": True,
            "no_sandbox": True,
            "isolated": True,
            "save_session": True,
            "save_trace": True,
            "ignore_https_errors": True,
            "extension": True,
            "shared_browser_context": True,
        }

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        assert '--headless' in command
        assert '--no-sandbox' in command
        assert '--isolated' in command
        assert '--save-session' in command
        assert '--save-trace' in command
        assert '--ignore-https-errors' in command
        assert '--extension' in command
        assert '--shared-browser-context' in command

    def test_build_command_all_string_options(self, proxy_client):
        """Test command building with all string-based options."""
        config = {
            "browser": "chromium",
            "device": "iPhone 12",
            "viewport_size": "1920x1080",
            "user_data_dir": "/tmp/user-data",
            "storage_state": "/tmp/storage.json",
            "allowed_origins": "https://example.com",
            "blocked_origins": "https://ads.com",
            "proxy_server": "http://proxy:8080",
            "caps": "video",
            "save_video": "on-failure",
            "output_dir": "/tmp/output",
            "timeout_action": 30000,
            "timeout_navigation": 60000,
            "image_responses": "base64",
            "user_agent": "CustomAgent/1.0",
            "init_script": "/tmp/init.js",
        }

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        # Check all key-value pairs
        assert '--browser' in command and 'chromium' in command
        assert '--device' in command and 'iPhone 12' in command
        assert '--viewport-size' in command and '1920x1080' in command
        assert '--user-data-dir' in command and '/tmp/user-data' in command
        assert '--storage-state' in command and '/tmp/storage.json' in command
        assert '--allowed-origins' in command and 'https://example.com' in command
        assert '--blocked-origins' in command and 'https://ads.com' in command
        assert '--proxy-server' in command and 'http://proxy:8080' in command
        assert '--caps' in command and 'video' in command
        assert '--save-video' in command and 'on-failure' in command
        assert '--output-dir' in command and '/tmp/output' in command
        assert '--timeout-action' in command and '30000' in command
        assert '--timeout-navigation' in command and '60000' in command
        assert '--image-responses' in command and 'base64' in command
        assert '--user-agent' in command and 'CustomAgent/1.0' in command
        assert '--init-script' in command and '/tmp/init.js' in command

    def test_build_command_false_boolean_values(self, proxy_client):
        """Test that false boolean values don't add flags."""
        config = {
            "headless": False,
            "no_sandbox": False,
            "isolated": False,
        }

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        # False values should not add flags
        assert '--headless' not in command
        assert '--no-sandbox' not in command
        assert '--isolated' not in command

    def test_build_command_empty_string_values(self, proxy_client):
        """Test that empty string values don't add options."""
        config = {
            "device": "",
            "viewport_size": "",
            "user_agent": "",
        }

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value='/usr/bin/npx'):
                command = proxy_client._build_command(config)

        # Empty strings should not add options
        assert '--device' not in command
        assert '--viewport-size' not in command
        assert '--user-agent' not in command

    def test_build_command_npx_not_found_standard_mode(self, proxy_client):
        """Test error when npx is not found in standard mode."""
        config = {}

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=False):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value=None):
                with pytest.raises(RuntimeError, match="npx not found in PATH"):
                    proxy_client._build_command(config)

    def test_build_command_cmd_not_found_wsl_mode(self, proxy_client):
        """Test error when cmd.exe is not found in WSL mode."""
        config = {}

        with patch('playwright_proxy_mcp.playwright.proxy_client.should_use_windows_node', return_value=True):
            with patch('playwright_proxy_mcp.playwright.proxy_client.shutil.which', return_value=None):
                with pytest.raises(RuntimeError, match="cmd.exe not found in PATH"):
                    proxy_client._build_command(config)

    def test_build_env_minimal(self, proxy_client):
        """Test environment building with minimal config."""
        config = {}

        with patch('playwright_proxy_mcp.playwright.proxy_client.os.environ', {"PATH": "/usr/bin"}):
            env = proxy_client._build_env(config)

        assert "PATH" in env
        assert "PLAYWRIGHT_MCP_EXTENSION_TOKEN" not in env

    def test_build_env_with_extension_token(self, proxy_client):
        """Test environment building with extension token."""
        config = {"extension_token": "test-token-123"}

        with patch('playwright_proxy_mcp.playwright.proxy_client.os.environ', {"PATH": "/usr/bin"}):
            env = proxy_client._build_env(config)

        assert env["PLAYWRIGHT_MCP_EXTENSION_TOKEN"] == "test-token-123"

    def test_build_env_empty_extension_token(self, proxy_client):
        """Test that empty extension token is not added to env."""
        config = {"extension_token": ""}

        with patch('playwright_proxy_mcp.playwright.proxy_client.os.environ', {"PATH": "/usr/bin"}):
            env = proxy_client._build_env(config)

        assert "PLAYWRIGHT_MCP_EXTENSION_TOKEN" not in env
