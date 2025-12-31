"""Tests for browser_execute_bulk with JMESPath filtering and other wrapper features."""

import pytest
from unittest.mock import AsyncMock, patch

# Import the implementation directly
from playwright_proxy_mcp.server import browser_execute_bulk as browser_execute_bulk_tool

# Get the actual function from the FunctionTool wrapper
browser_execute_bulk = browser_execute_bulk_tool.fn


@pytest.mark.asyncio
async def test_bulk_navigate_with_jmespath():
    """Test bulk execution calls browser_navigate wrapper with JMESPath filtering."""
    mock_navigate_result = {
        "success": True,
        "url": "https://example.com",
        "cache_key": "nav_123",
        "total_items": 2,
        "offset": 0,
        "limit": 1000,
        "has_more": False,
        "snapshot": '[{"role": "button", "name": {"value": "Submit"}}]',
        "error": None,
        "query_applied": "[?role == 'button']",
        "output_format": "json"
    }

    # Patch the .fn attribute since that's what's in the tool_registry
    with patch("playwright_proxy_mcp.server.browser_navigate.fn", new_callable=AsyncMock) as mock_navigate:
        mock_navigate.return_value = mock_navigate_result

        result = await browser_execute_bulk(
            commands=[
                {
                    "tool": "browser_navigate",
                    "args": {
                        "url": "https://example.com",
                        "jmespath_query": "[?role == 'button']",
                        "output_format": "json"
                    },
                    "return_result": True
                }
            ]
        )

        # Verify browser_navigate was called with JMESPath args
        assert mock_navigate.called
        call_args = mock_navigate.call_args[1]
        assert call_args["url"] == "https://example.com"
        assert call_args["jmespath_query"] == "[?role == 'button']"
        assert call_args["output_format"] == "json"

        # Verify result contains filtered data
        assert result["success"] is True
        assert result["results"][0]["query_applied"] == "[?role == 'button']"
        assert result["results"][0]["snapshot"] == '[{"role": "button", "name": {"value": "Submit"}}]'


@pytest.mark.asyncio
async def test_bulk_snapshot_with_jmespath():
    """Test bulk execution calls browser_snapshot wrapper with JMESPath filtering."""
    mock_snapshot_result = {
        "success": True,
        "url": "",
        "cache_key": "snap_456",
        "total_items": 1,
        "offset": 0,
        "limit": 1000,
        "has_more": False,
        "snapshot": '- role: heading\n  name:\n    value: Title',
        "error": None,
        "query_applied": "[?role == 'heading']",
        "output_format": "yaml"
    }

    with patch("playwright_proxy_mcp.server.browser_snapshot.fn", new_callable=AsyncMock) as mock_snapshot:
        mock_snapshot.return_value = mock_snapshot_result

        result = await browser_execute_bulk(
            commands=[
                {
                    "tool": "browser_snapshot",
                    "args": {
                        "jmespath_query": "[?role == 'heading']",
                        "output_format": "yaml"
                    },
                    "return_result": True
                }
            ]
        )

        # Verify browser_snapshot was called with JMESPath args
        assert mock_snapshot.called
        call_args = mock_snapshot.call_args[1]
        assert call_args["jmespath_query"] == "[?role == 'heading']"
        assert call_args["output_format"] == "yaml"

        # Verify result contains filtered data
        assert result["success"] is True
        assert result["results"][0]["query_applied"] == "[?role == 'heading']"


@pytest.mark.asyncio
async def test_bulk_navigate_with_pagination():
    """Test bulk execution handles pagination through browser_navigate wrapper with JMESPath query."""
    mock_page1 = {
        "success": True,
        "url": "https://example.com",
        "cache_key": "nav_789",
        "total_items": 100,
        "offset": 0,
        "limit": 50,
        "has_more": True,
        "snapshot": "...",
        "error": None,
        "query_applied": "[?role == `button`]",
        "output_format": "json"
    }

    mock_page2 = {
        "success": True,
        "url": "https://example.com",
        "cache_key": "nav_789",
        "total_items": 100,
        "offset": 50,
        "limit": 50,
        "has_more": False,
        "snapshot": "...",
        "error": None,
        "query_applied": None,
        "output_format": "json"
    }

    with patch("playwright_proxy_mcp.server.browser_navigate.fn", new_callable=AsyncMock) as mock_navigate:
        mock_navigate.side_effect = [mock_page1, mock_page2]

        result = await browser_execute_bulk(
            commands=[
                {
                    "tool": "browser_navigate",
                    "args": {
                        "url": "https://example.com",
                        "jmespath_query": "[?role == `button`]",  # Required for pagination
                        "limit": 50
                    },
                    "return_result": True
                },
                {
                    "tool": "browser_navigate",
                    "args": {
                        "url": "https://example.com",
                        "cache_key": "nav_789",  # Cache key allows pagination without query
                        "offset": 50,
                        "limit": 50
                    },
                    "return_result": True
                }
            ]
        )

        assert result["success"] is True
        assert result["results"][0]["has_more"] is True
        assert result["results"][1]["has_more"] is False
        assert mock_navigate.call_count == 2


@pytest.mark.asyncio
async def test_bulk_navigate_silent_mode():
    """Test bulk execution handles silent_mode through browser_navigate wrapper."""
    mock_silent_result = {
        "success": True,
        "url": "https://example.com",
        "cache_key": "",
        "total_items": 0,
        "offset": 0,
        "limit": 1000,
        "has_more": False,
        "snapshot": None,
        "error": None,
        "query_applied": None,
        "output_format": "yaml"
    }

    with patch("playwright_proxy_mcp.server.browser_navigate.fn", new_callable=AsyncMock) as mock_navigate:
        mock_navigate.return_value = mock_silent_result

        result = await browser_execute_bulk(
            commands=[
                {
                    "tool": "browser_navigate",
                    "args": {"url": "https://example.com", "silent_mode": True}
                }
            ]
        )

        # Verify browser_navigate was called with silent_mode
        assert mock_navigate.called
        call_args = mock_navigate.call_args[1]
        assert call_args["silent_mode"] is True

        assert result["success"] is True


@pytest.mark.asyncio
async def test_bulk_screenshot_returns_blob_uri():
    """Test bulk execution handles blob URI extraction through browser_take_screenshot wrapper."""
    with patch("playwright_proxy_mcp.server.browser_take_screenshot.fn", new_callable=AsyncMock) as mock_screenshot:
        mock_screenshot.return_value = "blob://1234567890-abcdef.png"

        result = await browser_execute_bulk(
            commands=[
                {
                    "tool": "browser_take_screenshot",
                    "args": {"type": "png"},
                    "return_result": True
                }
            ]
        )

        assert result["success"] is True
        assert result["results"][0] == "blob://1234567890-abcdef.png"


@pytest.mark.asyncio
async def test_bulk_pdf_returns_blob_uri():
    """Test bulk execution handles blob URI extraction through browser_pdf_save wrapper."""
    with patch("playwright_proxy_mcp.server.browser_pdf_save.fn", new_callable=AsyncMock) as mock_pdf:
        mock_pdf.return_value = "blob://1234567890-abcdef.pdf"

        result = await browser_execute_bulk(
            commands=[
                {
                    "tool": "browser_pdf_save",
                    "args": {},
                    "return_result": True
                }
            ]
        )

        assert result["success"] is True
        assert result["results"][0] == "blob://1234567890-abcdef.pdf"


@pytest.mark.asyncio
async def test_bulk_mixed_wrapper_functions():
    """Test bulk execution with multiple different wrapper functions."""
    with patch("playwright_proxy_mcp.server.browser_navigate.fn", new_callable=AsyncMock) as mock_navigate, \
         patch("playwright_proxy_mcp.server.browser_wait_for.fn", new_callable=AsyncMock) as mock_wait, \
         patch("playwright_proxy_mcp.server.browser_snapshot.fn", new_callable=AsyncMock) as mock_snapshot:

        mock_navigate.return_value = {
            "success": True,
            "url": "https://example.com",
            "cache_key": "",
            "total_items": 0,
            "offset": 0,
            "limit": 1000,
            "has_more": False,
            "snapshot": None,
            "error": None,
            "output_format": "yaml"
        }
        mock_wait.return_value = {"success": True}
        mock_snapshot.return_value = {
            "success": True,
            "url": "",
            "cache_key": "snap_123",
            "total_items": 5,
            "offset": 0,
            "limit": 1000,
            "has_more": False,
            "snapshot": '[{"role": "button"}]',
            "error": None,
            "query_applied": "[?role == 'button']",
            "output_format": "json"
        }

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com", "silent_mode": True}},
                {"tool": "browser_wait_for", "args": {"text": "Loaded"}},
                {"tool": "browser_snapshot", "args": {"jmespath_query": "[?role == 'button']", "output_format": "json"}, "return_result": True}
            ]
        )

        assert result["success"] is True
        assert mock_navigate.call_count == 1
        assert mock_wait.call_count == 1
        assert mock_snapshot.call_count == 1
        assert result["results"][2]["query_applied"] == "[?role == 'button']"


@pytest.mark.asyncio
async def test_bulk_navigate_back_wrapper():
    """Test bulk execution calls browser_navigate_back wrapper."""
    with patch("playwright_proxy_mcp.server.browser_navigate_back.fn", new_callable=AsyncMock) as mock_back:
        mock_back.return_value = {"success": True}

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate_back", "args": {}, "return_result": True}
            ]
        )

        assert mock_back.called
        assert result["success"] is True


@pytest.mark.asyncio
async def test_bulk_click_wrapper():
    """Test bulk execution calls browser_click wrapper."""
    with patch("playwright_proxy_mcp.server.browser_click.fn", new_callable=AsyncMock) as mock_click:
        mock_click.return_value = {"success": True}

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_click", "args": {"element": "button", "ref": "e1"}, "return_result": True}
            ]
        )

        assert mock_click.called
        call_args = mock_click.call_args[1]
        assert call_args["element"] == "button"
        assert call_args["ref"] == "e1"
        assert result["success"] is True


@pytest.mark.asyncio
async def test_bulk_type_wrapper():
    """Test bulk execution calls browser_type wrapper."""
    with patch("playwright_proxy_mcp.server.browser_type.fn", new_callable=AsyncMock) as mock_type:
        mock_type.return_value = {"success": True}

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_type", "args": {"element": "textbox", "ref": "e1", "text": "hello"}, "return_result": True}
            ]
        )

        assert mock_type.called
        call_args = mock_type.call_args[1]
        assert call_args["text"] == "hello"
        assert result["success"] is True


@pytest.mark.asyncio
async def test_bulk_error_from_wrapper():
    """Test bulk execution handles errors from wrapper functions."""
    with patch("playwright_proxy_mcp.server.browser_navigate.fn", new_callable=AsyncMock) as mock_navigate:
        # Wrapper returns error response (not exception)
        mock_navigate.return_value = {
            "success": False,
            "url": "https://example.com",
            "error": "Invalid JMESPath query",
            "cache_key": "",
            "total_items": 0,
            "offset": 0,
            "limit": 1000,
            "has_more": False,
            "snapshot": None,
            "output_format": "yaml"
        }

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com", "jmespath_query": "invalid[["}, "return_result": True}
            ]
        )

        # Wrapper function succeeded (no exception), but returned error in response
        assert result["success"] is True  # Bulk succeeded (no exceptions)
        assert result["results"][0]["success"] is False  # Navigate failed
        assert "Invalid JMESPath" in result["results"][0]["error"]


@pytest.mark.asyncio
async def test_bulk_exception_from_wrapper():
    """Test bulk execution handles exceptions from wrapper functions."""
    with patch("playwright_proxy_mcp.server.browser_navigate.fn", new_callable=AsyncMock) as mock_navigate:
        # Wrapper throws exception
        mock_navigate.side_effect = RuntimeError("Navigation failed")

        result = await browser_execute_bulk(
            commands=[
                {"tool": "browser_navigate", "args": {"url": "https://example.com"}, "return_result": True}
            ],
            stop_on_error=True
        )

        assert result["success"] is False
        assert "Navigation failed" in result["errors"][0]


@pytest.mark.asyncio
async def test_bulk_workflow_navigate_filter_snapshot():
    """Test realistic workflow: navigate with filter, wait, snapshot with filter."""
    with patch("playwright_proxy_mcp.server.browser_navigate.fn", new_callable=AsyncMock) as mock_navigate, \
         patch("playwright_proxy_mcp.server.browser_wait_for.fn", new_callable=AsyncMock) as mock_wait, \
         patch("playwright_proxy_mcp.server.browser_snapshot.fn", new_callable=AsyncMock) as mock_snapshot:

        mock_navigate.return_value = {
            "success": True,
            "url": "https://example.com/products",
            "cache_key": "",
            "total_items": 0,
            "offset": 0,
            "limit": 1000,
            "has_more": False,
            "snapshot": None,
            "error": None,
            "output_format": "yaml"
        }

        mock_wait.return_value = {"success": True}

        mock_snapshot.return_value = {
            "success": True,
            "url": "",
            "cache_key": "snap_999",
            "total_items": 3,
            "offset": 0,
            "limit": 1000,
            "has_more": False,
            "snapshot": '[{"role": "button", "name": {"value": "Add to Cart"}}]',
            "error": None,
            "query_applied": "[?role == 'button' && contains(nvl(name.value, ''), 'Cart')]",
            "output_format": "json"
        }

        result = await browser_execute_bulk(
            commands=[
                {
                    "tool": "browser_navigate",
                    "args": {
                        "url": "https://example.com/products",
                        "silent_mode": True
                    }
                },
                {
                    "tool": "browser_wait_for",
                    "args": {"text": "Products loaded"}
                },
                {
                    "tool": "browser_snapshot",
                    "args": {
                        "jmespath_query": "[?role == 'button' && contains(nvl(name.value, ''), 'Cart')]",
                        "output_format": "json"
                    },
                    "return_result": True
                }
            ]
        )

        assert result["success"] is True
        assert result["executed_count"] == 3
        # Verify navigate was called with silent_mode
        assert mock_navigate.call_args[1]["silent_mode"] is True
        # Verify snapshot was called with JMESPath
        assert "[?role == 'button'" in mock_snapshot.call_args[1]["jmespath_query"]
        # Verify filtered result
        assert result["results"][2]["total_items"] == 3
