"""
Tests for playwright proxy client
"""

from unittest.mock import AsyncMock, Mock

import pytest

from playwright_proxy_mcp.playwright.proxy_client import PlaywrightProxyClient


@pytest.fixture
def mock_process_manager():
    """Create a mock process manager."""
    manager = Mock()
    manager.start = AsyncMock()
    manager.stop = AsyncMock()
    manager.is_healthy = Mock(return_value=True)
    manager.process = Mock()
    return manager


@pytest.fixture
def mock_middleware():
    """Create a mock middleware."""
    middleware = Mock()
    middleware.intercept_response = AsyncMock()
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
    async def test_start(self, proxy_client, mock_process_manager):
        """Test starting the proxy client."""
        config = {"browser": "chromium"}

        await proxy_client.start(config)

        assert proxy_client._started
        mock_process_manager.start.assert_called_once_with(config)

    @pytest.mark.asyncio
    async def test_start_already_started(self, proxy_client):
        """Test starting when already started."""
        config = {"browser": "chromium"}

        await proxy_client.start(config)
        await proxy_client.start(config)

        # Should only start once
        assert proxy_client._started
        assert proxy_client.process_manager.start.call_count == 1

    @pytest.mark.asyncio
    async def test_stop(self, proxy_client, mock_process_manager):
        """Test stopping the proxy client."""
        # Start first
        await proxy_client.start({"browser": "chromium"})

        await proxy_client.stop()

        assert not proxy_client._started
        mock_process_manager.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_not_started(self, proxy_client, mock_process_manager):
        """Test stopping when not started."""
        await proxy_client.stop()

        # Should not call stop on process manager
        mock_process_manager.stop.assert_not_called()

    def test_is_healthy_started(self, proxy_client, mock_process_manager):
        """Test health check when started and healthy."""
        proxy_client._started = True
        mock_process_manager.is_healthy.return_value = True

        assert proxy_client.is_healthy()

    def test_is_healthy_not_started(self, proxy_client):
        """Test health check when not started."""
        assert not proxy_client.is_healthy()

    def test_is_healthy_unhealthy_process(self, proxy_client, mock_process_manager):
        """Test health check when process is unhealthy."""
        proxy_client._started = True
        mock_process_manager.is_healthy.return_value = False

        assert not proxy_client.is_healthy()

    @pytest.mark.asyncio
    async def test_transform_response(self, proxy_client, mock_middleware):
        """Test transforming response through middleware."""
        test_response = {"data": "value"}
        mock_middleware.intercept_response.return_value = {"transformed": "data"}

        result = await proxy_client.transform_response("test_tool", test_response)

        assert result == {"transformed": "data"}
        mock_middleware.intercept_response.assert_called_once_with("test_tool", test_response)

    @pytest.mark.asyncio
    async def test_transform_response_error(self, proxy_client, mock_middleware):
        """Test that transform_response returns original response on error."""
        test_response = {"data": "value"}
        mock_middleware.intercept_response.side_effect = Exception("Transform error")

        result = await proxy_client.transform_response("test_tool", test_response)

        # Should return original response
        assert result == test_response

    def test_get_process(self, proxy_client, mock_process_manager):
        """Test getting the underlying process."""
        result = proxy_client.get_process()

        assert result == mock_process_manager.process
