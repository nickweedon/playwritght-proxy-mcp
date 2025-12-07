"""
Tests for the Playwright MCP Proxy server
"""

import json
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
    mock_client.get_process.return_value = None

    with patch("playwright_proxy_mcp.server.proxy_client", mock_client):
        with pytest.raises(RuntimeError, match="not properly initialized"):
            await _call_playwright_tool("navigate", {"url": "https://example.com"})


@pytest.mark.asyncio
async def test_call_playwright_tool_success():
    """Test successful playwright tool call."""
    # Create mock process with stdin/stdout
    mock_stdin = Mock()
    mock_stdin.write = Mock()
    mock_stdin.drain = AsyncMock()

    mock_stdout = Mock()
    response_data = {
        "jsonrpc": "2.0",
        "id": 123,
        "result": {"status": "success", "data": "value"},
    }
    mock_stdout.readline = AsyncMock(
        return_value=(json.dumps(response_data) + "\n").encode("utf-8")
    )

    mock_process = Mock()
    mock_process.stdin = mock_stdin
    mock_process.stdout = mock_stdout

    mock_client = Mock()
    mock_client.is_healthy.return_value = True
    mock_client.get_process.return_value = mock_process
    mock_client.transform_response = AsyncMock(
        return_value={"status": "success", "data": "transformed"}
    )

    with patch("playwright_proxy_mcp.server.proxy_client", mock_client):
        result = await _call_playwright_tool("navigate", {"url": "https://example.com"})

        assert result == {"status": "success", "data": "transformed"}

        # Verify request was sent
        mock_stdin.write.assert_called_once()
        mock_stdin.drain.assert_called_once()

        # Verify transformation was called
        mock_client.transform_response.assert_called_once()


@pytest.mark.asyncio
async def test_call_playwright_tool_strips_prefix():
    """Test that playwright_ prefix is stripped from tool name."""
    mock_stdin = Mock()
    mock_stdin.write = Mock()
    mock_stdin.drain = AsyncMock()

    mock_stdout = Mock()
    response_data = {"jsonrpc": "2.0", "id": 123, "result": {}}
    mock_stdout.readline = AsyncMock(
        return_value=(json.dumps(response_data) + "\n").encode("utf-8")
    )

    mock_process = Mock()
    mock_process.stdin = mock_stdin
    mock_process.stdout = mock_stdout

    mock_client = Mock()
    mock_client.is_healthy.return_value = True
    mock_client.get_process.return_value = mock_process
    mock_client.transform_response = AsyncMock(return_value={})

    with patch("playwright_proxy_mcp.server.proxy_client", mock_client):
        await _call_playwright_tool("playwright_navigate", {"url": "https://example.com"})

        # Check the JSON-RPC request that was sent
        call_args = mock_stdin.write.call_args[0][0]
        request = json.loads(call_args.decode("utf-8"))

        # Tool name should be without playwright_ prefix
        assert request["params"]["name"] == "navigate"


@pytest.mark.asyncio
async def test_call_playwright_tool_error_response():
    """Test handling of error response from playwright."""
    mock_stdin = Mock()
    mock_stdin.write = Mock()
    mock_stdin.drain = AsyncMock()

    mock_stdout = Mock()
    response_data = {
        "jsonrpc": "2.0",
        "id": 123,
        "error": {"code": -1, "message": "Navigation failed"},
    }
    mock_stdout.readline = AsyncMock(
        return_value=(json.dumps(response_data) + "\n").encode("utf-8")
    )

    mock_process = Mock()
    mock_process.stdin = mock_stdin
    mock_process.stdout = mock_stdout

    mock_client = Mock()
    mock_client.is_healthy.return_value = True
    mock_client.get_process.return_value = mock_process

    with patch("playwright_proxy_mcp.server.proxy_client", mock_client):
        with pytest.raises(RuntimeError, match="Playwright tool error"):
            await _call_playwright_tool("navigate", {"url": "https://example.com"})


