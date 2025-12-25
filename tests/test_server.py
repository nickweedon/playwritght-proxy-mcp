"""
Tests for the Playwright MCP Proxy server
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from playwright_proxy_mcp.server import _call_playwright_tool, mcp


def test_server_name():
    """Test that the server has the correct name"""
    assert mcp.name == "Playwright MCP Proxy"


def test_server_instructions():
    """Test that the server has instructions"""
    assert mcp.instructions is not None
    assert "playwright" in mcp.instructions.lower()
    assert "blob" in mcp.instructions.lower()


@pytest.mark.asyncio
async def test_call_playwright_tool_no_client():
    """Test calling playwright tool when client is not initialized."""
    with patch("playwright_proxy_mcp.server.proxy_client", None):
        with pytest.raises(RuntimeError, match="Playwright subprocess not running"):
            await _call_playwright_tool("navigate", {"url": "https://example.com"})


@pytest.mark.asyncio
async def test_call_playwright_tool_unhealthy():
    """Test calling playwright tool when client is unhealthy."""
    mock_client = Mock()
    mock_client.is_healthy.return_value = False

    with patch("playwright_proxy_mcp.server.proxy_client", mock_client):
        with pytest.raises(RuntimeError, match="Playwright subprocess not running"):
            await _call_playwright_tool("navigate", {"url": "https://example.com"})


@pytest.mark.asyncio
async def test_call_playwright_tool_no_process():
    """Test calling playwright tool when process is not initialized."""
    mock_client = Mock()
    mock_client.is_healthy.return_value = True
    mock_client.call_tool = AsyncMock(
        side_effect=RuntimeError("Playwright subprocess not properly initialized")
    )

    with patch("playwright_proxy_mcp.server.proxy_client", mock_client):
        with pytest.raises(RuntimeError, match="not properly initialized"):
            await _call_playwright_tool("navigate", {"url": "https://example.com"})


@pytest.mark.asyncio
async def test_call_playwright_tool_success():
    """Test successful playwright tool call."""
    mock_client = Mock()
    mock_client.is_healthy.return_value = True
    mock_client.call_tool = AsyncMock(return_value={"status": "success", "data": "transformed"})

    with patch("playwright_proxy_mcp.server.proxy_client", mock_client):
        # Use browser_ prefix directly (no mapping needed)
        result = await _call_playwright_tool("browser_navigate", {"url": "https://example.com"})

        assert result == {"status": "success", "data": "transformed"}

        # Verify call_tool was called with the correct tool name
        mock_client.call_tool.assert_called_once_with(
            "browser_navigate", {"url": "https://example.com"}
        )


@pytest.mark.asyncio
async def test_call_playwright_tool_strips_prefix():
    """Test that tool names are passed through directly without modification."""
    mock_client = Mock()
    mock_client.is_healthy.return_value = True
    mock_client.call_tool = AsyncMock(return_value={})

    with patch("playwright_proxy_mcp.server.proxy_client", mock_client):
        await _call_playwright_tool("browser_navigate", {"url": "https://example.com"})

        # Tool name should be passed through as-is
        mock_client.call_tool.assert_called_once_with(
            "browser_navigate", {"url": "https://example.com"}
        )


@pytest.mark.asyncio
async def test_call_playwright_tool_error_response():
    """Test handling of error response from playwright."""
    mock_client = Mock()
    mock_client.is_healthy.return_value = True
    mock_client.call_tool = AsyncMock(
        side_effect=RuntimeError("MCP error: {'code': -1, 'message': 'Navigation failed'}")
    )

    with patch("playwright_proxy_mcp.server.proxy_client", mock_client):
        with pytest.raises(RuntimeError, match="MCP error"):
            await _call_playwright_tool("navigate", {"url": "https://example.com"})


@pytest.mark.asyncio
async def test_playwright_screenshot_returns_blob_uri():
    """Test that browser_take_screenshot returns blob:// URI directly."""
    mock_client = Mock()
    mock_client.is_healthy.return_value = True

    # Mock response with blob:// URI (after middleware transformation)
    mock_client.call_tool = AsyncMock(
        return_value={
            "screenshot": "blob://1234567890-abc123.png",
            "screenshot_size_kb": 150,
            "screenshot_mime_type": "image/png",
        }
    )

    with patch("playwright_proxy_mcp.server.proxy_client", mock_client):
        # Call _call_playwright_tool directly since the tool is wrapped by FastMCP
        result = await _call_playwright_tool(
            "browser_take_screenshot", {"filename": "test", "fullPage": True}
        )

        # Should return the dict directly, not transform to Image
        assert isinstance(result, dict)
        assert result["screenshot"] == "blob://1234567890-abc123.png"
        assert result["screenshot_size_kb"] == 150
        assert result["screenshot_mime_type"] == "image/png"

        # Verify correct tool call
        mock_client.call_tool.assert_called_once_with(
            "browser_take_screenshot", {"filename": "test", "fullPage": True}
        )
