"""Test for is_error attribute fix in proxy_client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Any

from playwright_proxy_mcp.playwright.proxy_client import PlaywrightProxyClient


@dataclass
class MockCallToolResult:
    """Mock CallToolResult matching FastMCP Client's dataclass structure."""

    content: list[Any]
    structured_content: dict[str, Any] | None
    meta: dict[str, Any] | None
    data: Any = None
    is_error: bool = False


@pytest.mark.asyncio
async def test_proxy_client_handles_is_error_correctly():
    """Test that proxy_client correctly checks is_error (not isError)."""
    # Create mock components
    mock_process_manager = MagicMock()
    mock_middleware = MagicMock()
    mock_middleware.intercept_response = AsyncMock(return_value={"transformed": "result"})

    # Create proxy client
    proxy_client = PlaywrightProxyClient(mock_process_manager, mock_middleware)

    # Mock the internal client
    mock_client = AsyncMock()
    proxy_client._client = mock_client
    proxy_client._started = True

    # Test case 1: Success (is_error=False)
    mock_result_success = MockCallToolResult(
        content=[MagicMock(text="success")],
        structured_content=None,
        meta=None,
        is_error=False,
    )
    mock_client.call_tool.return_value = mock_result_success

    result = await proxy_client.call_tool("test_tool", {"arg": "value"})
    assert result == {"transformed": "result"}

    # Test case 2: Error (is_error=True)
    mock_result_error = MockCallToolResult(
        content=[MagicMock(text="Tool execution failed")],
        structured_content=None,
        meta=None,
        is_error=True,
    )
    mock_client.call_tool.return_value = mock_result_error

    with pytest.raises(RuntimeError) as exc_info:
        await proxy_client.call_tool("test_tool", {"arg": "value"})

    assert "Tool call failed: Tool execution failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_proxy_client_does_not_use_camelCase_isError():
    """Test that proxy_client doesn't try to access result.isError (camelCase)."""
    # Create mock components
    mock_process_manager = MagicMock()
    mock_middleware = MagicMock()
    mock_middleware.intercept_response = AsyncMock(return_value={"transformed": "result"})

    # Create proxy client
    proxy_client = PlaywrightProxyClient(mock_process_manager, mock_middleware)

    # Mock the internal client
    mock_client = AsyncMock()
    proxy_client._client = mock_client
    proxy_client._started = True

    # Create a mock result that only has is_error, not isError
    # This ensures we're using the correct attribute name
    mock_result = MockCallToolResult(
        content=[MagicMock(text="success")],
        structured_content=None,
        meta=None,
        is_error=False,
    )

    # Verify the mock doesn't have isError attribute
    assert not hasattr(mock_result, "isError")
    assert hasattr(mock_result, "is_error")

    mock_client.call_tool.return_value = mock_result

    # This should NOT raise AttributeError
    result = await proxy_client.call_tool("test_tool", {"arg": "value"})
    assert result == {"transformed": "result"}
