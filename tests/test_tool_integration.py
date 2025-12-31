"""
Integration tests for Playwright MCP Proxy server tool methods.

This test suite tests the actual tool methods defined in server.py,
rather than the underlying proxy methods. These tests ensure that the
tool wrappers and parameter handling work correctly.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from playwright_proxy_mcp.types import NavigationResponse


@pytest.fixture
def mock_proxy_client():
    """Create a mock proxy client for testing."""
    mock_client = Mock()
    mock_client.is_healthy = AsyncMock(return_value=True)
    mock_client.call_tool = AsyncMock()
    return mock_client


@pytest.fixture
def mock_navigation_cache():
    """Create a mock navigation cache for testing."""
    mock_cache = Mock()
    mock_cache.get = Mock(return_value=None)
    mock_cache.create = Mock(return_value="nav_test123")
    return mock_cache


# =============================================================================
# NAVIGATION TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_navigate_basic(mock_proxy_client, mock_navigation_cache):
    """Test basic browser_navigate call."""
    from playwright_proxy_mcp import server

    # Mock the playwright response
    mock_proxy_client.call_tool.return_value = {
        "content": [
            {
                "type": "text",
                "text": '- button "Submit" [ref=e1]'
            }
        ]
    }

    with patch.object(server, "proxy_client", mock_proxy_client), \
         patch.object(server, "navigation_cache", mock_navigation_cache):

        # Access the underlying function via .fn attribute
        result = await server.browser_navigate.fn(url="https://example.com")

        # Verify the result (NavigationResponse is a TypedDict, so we check dict structure)
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["snapshot"] is not None
        assert "button" in result["snapshot"]

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_navigate",
            {"url": "https://example.com"}
        )


@pytest.mark.asyncio
async def test_browser_navigate_silent_mode(mock_proxy_client, mock_navigation_cache):
    """Test browser_navigate with silent mode."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "content": [{"type": "text", "text": "- button 'Submit'"}]
    }

    with patch.object(server, "proxy_client", mock_proxy_client), \
         patch.object(server, "navigation_cache", mock_navigation_cache):

        result = await server.browser_navigate.fn(
            url="https://example.com",
            silent_mode=True
        )

        # Verify silent mode returns no snapshot
        assert result["success"] is True
        assert result["snapshot"] is None


@pytest.mark.asyncio
async def test_browser_navigate_with_jmespath_query(mock_proxy_client, mock_navigation_cache):
    """Test browser_navigate with JMESPath query."""
    from playwright_proxy_mcp import server

    # Mock the playwright response
    mock_proxy_client.call_tool.return_value = {
        "content": [
            {
                "type": "text",
                "text": '- button "Submit" [ref=e1]\n- button "Cancel" [ref=e2]\n- link "Home" [ref=e3]'
            }
        ]
    }

    with patch.object(server, "proxy_client", mock_proxy_client), \
         patch.object(server, "navigation_cache", mock_navigation_cache):

        result = await server.browser_navigate.fn(
            url="https://example.com",
            jmespath_query='[?role == `button`]'
        )

        # Verify the result
        assert result["success"] is True
        # Should have filtered to only buttons
        assert result["total_items"] == 2


@pytest.mark.asyncio
async def test_browser_navigate_pagination(mock_proxy_client, mock_navigation_cache):
    """Test browser_navigate with pagination requires JMESPath query."""
    from playwright_proxy_mcp import server

    # Mock the playwright response with ARIA-formatted YAML (100 buttons)
    # ARIA format uses special syntax: - button "Name" [ref=eX]
    aria_buttons = '\n'.join([f'- button "Button{i}" [ref=e{i}]' for i in range(100)])

    mock_proxy_client.call_tool.return_value = {
        "content": [
            {
                "type": "text",
                "text": aria_buttons
            }
        ]
    }

    with patch.object(server, "proxy_client", mock_proxy_client), \
         patch.object(server, "navigation_cache", mock_navigation_cache):

        # Test 1: Pagination without query or flatten should fail
        result = await server.browser_navigate.fn(
            url="https://example.com",
            limit=20
        )
        assert result["success"] is False
        assert "Pagination (offset/limit) requires flatten=True, jmespath_query, or cache_key" in result["error"]

        # Test 2: Pagination with query should work
        result = await server.browser_navigate.fn(
            url="https://example.com",
            jmespath_query="[?role == `button`]",  # Filter buttons
            limit=20
        )

        # Verify pagination works with query
        assert result["success"] is True, f"Expected success but got error: {result.get('error')}"
        assert result["total_items"] == 100
        assert result["limit"] == 20
        assert result["offset"] == 0
        assert result["has_more"] is True
        assert result["cache_key"] == "nav_test123"


@pytest.mark.asyncio
async def test_browser_navigate_invalid_output_format(mock_proxy_client, mock_navigation_cache):
    """Test browser_navigate with invalid output format."""
    from playwright_proxy_mcp import server

    with patch.object(server, "proxy_client", mock_proxy_client), \
         patch.object(server, "navigation_cache", mock_navigation_cache):

        result = await server.browser_navigate.fn(
            url="https://example.com",
            output_format="invalid"
        )

        # Verify error response
        assert result["success"] is False
        assert "output_format must be 'json' or 'yaml'" in result["error"]


@pytest.mark.asyncio
async def test_browser_navigate_back(mock_proxy_client):
    """Test browser_navigate_back tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "success"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_navigate_back.fn()

        # Verify the result
        assert result == {"status": "success"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_navigate_back",
            {}
        )


# =============================================================================
# SCREENSHOT & PDF TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_take_screenshot_basic(mock_proxy_client):
    """Test browser_take_screenshot tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "content": [
            {
                "type": "blob",
                "blob_id": "blob://1234567890-abc123.png"
            }
        ]
    }

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_take_screenshot.fn()

        # Verify the result is a blob URI
        assert result == "blob://1234567890-abc123.png"

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_take_screenshot",
            {"type": "png"}
        )


@pytest.mark.asyncio
async def test_browser_take_screenshot_with_params(mock_proxy_client):
    """Test browser_take_screenshot with all parameters."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "content": [
            {
                "type": "blob",
                "blob_id": "blob://1234567890-abc123.jpeg"
            }
        ]
    }

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_take_screenshot.fn(
            type="jpeg",
            filename="test.jpeg",
            element="Submit button",
            ref="e1",
            fullPage=True
        )

        # Verify the result
        assert result == "blob://1234567890-abc123.jpeg"

        # Verify all parameters were passed
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_take_screenshot",
            {
                "type": "jpeg",
                "filename": "test.jpeg",
                "element": "Submit button",
                "ref": "e1",
                "fullPage": True
            }
        )


@pytest.mark.asyncio
async def test_browser_pdf_save_basic(mock_proxy_client):
    """Test browser_pdf_save tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "content": [
            {
                "type": "blob",
                "blob_id": "blob://1234567890-abc123.pdf"
            }
        ]
    }

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_pdf_save.fn()

        # Verify the result is a blob URI
        assert result == "blob://1234567890-abc123.pdf"

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_pdf_save",
            {}
        )


@pytest.mark.asyncio
async def test_browser_pdf_save_with_filename(mock_proxy_client):
    """Test browser_pdf_save with filename."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "content": [
            {
                "type": "blob",
                "blob_id": "blob://1234567890-abc123.pdf"
            }
        ]
    }

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_pdf_save.fn(filename="test.pdf")

        # Verify the result
        assert result == "blob://1234567890-abc123.pdf"

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_pdf_save",
            {"filename": "test.pdf"}
        )


# =============================================================================
# CODE EXECUTION TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_run_code(mock_proxy_client):
    """Test browser_run_code tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "result": "Page Title"
    }

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_run_code.fn(
            code="async (page) => { return await page.title(); }"
        )

        # Verify the result
        assert result == {"result": "Page Title"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_run_code",
            {"code": "async (page) => { return await page.title(); }"}
        )


@pytest.mark.asyncio
async def test_browser_evaluate_basic(mock_proxy_client):
    """Test browser_evaluate tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "result": "evaluated value"
    }

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_evaluate.fn(
            function="() => { return 'test'; }"
        )

        # Verify the result
        assert result == {"result": "evaluated value"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_evaluate",
            {"function": "() => { return 'test'; }"}
        )


@pytest.mark.asyncio
async def test_browser_evaluate_with_element(mock_proxy_client):
    """Test browser_evaluate with element."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "result": "element value"
    }

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_evaluate.fn(
            function="(element) => { return element.value; }",
            element="Submit button",
            ref="e1"
        )

        # Verify the result
        assert result == {"result": "element value"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_evaluate",
            {
                "function": "(element) => { return element.value; }",
                "element": "Submit button",
                "ref": "e1"
            }
        )


# =============================================================================
# PAGE SNAPSHOT & INTERACTION TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_snapshot_with_filename(mock_proxy_client):
    """Test browser_snapshot with filename (original behavior)."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "status": "saved to file"
    }

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_snapshot.fn(filename="snapshot.md")

        # Verify the result
        assert result == {"status": "saved to file"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_snapshot",
            {"filename": "snapshot.md"}
        )


@pytest.mark.asyncio
async def test_browser_snapshot_advanced(mock_proxy_client, mock_navigation_cache):
    """Test browser_snapshot with advanced features."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "content": [
            {
                "type": "text",
                "text": '- button "Submit" [ref=e1]\n- button "Cancel" [ref=e2]'
            }
        ]
    }

    with patch.object(server, "proxy_client", mock_proxy_client), \
         patch.object(server, "navigation_cache", mock_navigation_cache):

        result = await server.browser_snapshot.fn(
            jmespath_query='[?role == `button`]',
            output_format="json",
            limit=10
        )

        # Verify the result
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["output_format"] == "json"


@pytest.mark.asyncio
async def test_browser_click_basic(mock_proxy_client):
    """Test browser_click tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "clicked"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_click.fn(
            element="Submit button",
            ref="e1"
        )

        # Verify the result
        assert result == {"status": "clicked"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_click",
            {"element": "Submit button", "ref": "e1"}
        )


@pytest.mark.asyncio
async def test_browser_click_with_modifiers(mock_proxy_client):
    """Test browser_click with modifiers."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "clicked"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_click.fn(
            element="Link",
            ref="e1",
            doubleClick=True,
            button="right",
            modifiers=["Control", "Shift"]
        )

        # Verify all parameters were passed
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_click",
            {
                "element": "Link",
                "ref": "e1",
                "doubleClick": True,
                "button": "right",
                "modifiers": ["Control", "Shift"]
            }
        )


@pytest.mark.asyncio
async def test_browser_drag(mock_proxy_client):
    """Test browser_drag tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "dragged"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_drag.fn(
            startElement="Item 1",
            startRef="e1",
            endElement="Item 2",
            endRef="e2"
        )

        # Verify the result
        assert result == {"status": "dragged"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_drag",
            {
                "startElement": "Item 1",
                "startRef": "e1",
                "endElement": "Item 2",
                "endRef": "e2"
            }
        )


@pytest.mark.asyncio
async def test_browser_hover(mock_proxy_client):
    """Test browser_hover tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "hovered"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_hover.fn(
            element="Menu item",
            ref="e1"
        )

        # Verify the result
        assert result == {"status": "hovered"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_hover",
            {"element": "Menu item", "ref": "e1"}
        )


@pytest.mark.asyncio
async def test_browser_select_option(mock_proxy_client):
    """Test browser_select_option tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "selected"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_select_option.fn(
            element="Dropdown",
            ref="e1",
            values=["option1", "option2"]
        )

        # Verify the result
        assert result == {"status": "selected"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_select_option",
            {
                "element": "Dropdown",
                "ref": "e1",
                "values": ["option1", "option2"]
            }
        )


@pytest.mark.asyncio
async def test_browser_generate_locator(mock_proxy_client):
    """Test browser_generate_locator tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"locator": "getByRole('button')"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_generate_locator.fn(
            element="Submit button",
            ref="e1"
        )

        # Verify the result
        assert result == {"locator": "getByRole('button')"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_generate_locator",
            {"element": "Submit button", "ref": "e1"}
        )


# =============================================================================
# FORM INTERACTION TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_fill_form(mock_proxy_client):
    """Test browser_fill_form tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "filled"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        fields = [
            {
                "name": "Username",
                "type": "textbox",
                "ref": "e1",
                "value": "testuser"
            },
            {
                "name": "Password",
                "type": "textbox",
                "ref": "e2",
                "value": "password123"
            }
        ]
        result = await server.browser_fill_form.fn(fields=fields)

        # Verify the result
        assert result == {"status": "filled"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_fill_form",
            {"fields": fields}
        )


# =============================================================================
# KEYBOARD TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_press_key(mock_proxy_client):
    """Test browser_press_key tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "pressed"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_press_key.fn(key="Enter")

        # Verify the result
        assert result == {"status": "pressed"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_press_key",
            {"key": "Enter"}
        )


@pytest.mark.asyncio
async def test_browser_type_basic(mock_proxy_client):
    """Test browser_type tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "typed"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_type.fn(
            element="Search box",
            ref="e1",
            text="test query"
        )

        # Verify the result
        assert result == {"status": "typed"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_type",
            {
                "element": "Search box",
                "ref": "e1",
                "text": "test query"
            }
        )


@pytest.mark.asyncio
async def test_browser_type_with_options(mock_proxy_client):
    """Test browser_type with submit and slowly options."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "typed"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_type.fn(
            element="Search box",
            ref="e1",
            text="test query",
            submit=True,
            slowly=True
        )

        # Verify all parameters were passed
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_type",
            {
                "element": "Search box",
                "ref": "e1",
                "text": "test query",
                "submit": True,
                "slowly": True
            }
        )


# =============================================================================
# WAIT & TIMING TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_wait_for_time(mock_proxy_client):
    """Test browser_wait_for with time."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "waited"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_wait_for.fn(time=2.5)

        # Verify the result
        assert result == {"status": "waited"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_wait_for",
            {"time": 2.5}
        )


@pytest.mark.asyncio
async def test_browser_wait_for_text(mock_proxy_client):
    """Test browser_wait_for with text."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "waited"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_wait_for.fn(text="Loading complete")

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_wait_for",
            {"text": "Loading complete"}
        )


@pytest.mark.asyncio
async def test_browser_wait_for_text_gone(mock_proxy_client):
    """Test browser_wait_for with textGone."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "waited"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_wait_for.fn(textGone="Loading...")

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_wait_for",
            {"textGone": "Loading..."}
        )


# =============================================================================
# VERIFICATION TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_verify_element_visible(mock_proxy_client):
    """Test browser_verify_element_visible tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "verified"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_verify_element_visible.fn(
            role="button",
            accessibleName="Submit"
        )

        # Verify the result
        assert result == {"status": "verified"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_verify_element_visible",
            {"role": "button", "accessibleName": "Submit"}
        )


@pytest.mark.asyncio
async def test_browser_verify_text_visible(mock_proxy_client):
    """Test browser_verify_text_visible tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "verified"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_verify_text_visible.fn(text="Welcome")

        # Verify the result
        assert result == {"status": "verified"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_verify_text_visible",
            {"text": "Welcome"}
        )


@pytest.mark.asyncio
async def test_browser_verify_list_visible(mock_proxy_client):
    """Test browser_verify_list_visible tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "verified"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_verify_list_visible.fn(
            element="Menu",
            ref="e1",
            items=["Home", "About", "Contact"]
        )

        # Verify the result
        assert result == {"status": "verified"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_verify_list_visible",
            {
                "element": "Menu",
                "ref": "e1",
                "items": ["Home", "About", "Contact"]
            }
        )


@pytest.mark.asyncio
async def test_browser_verify_value(mock_proxy_client):
    """Test browser_verify_value tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "verified"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_verify_value.fn(
            type="textbox",
            element="Username",
            ref="e1",
            value="testuser"
        )

        # Verify the result
        assert result == {"status": "verified"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_verify_value",
            {
                "type": "textbox",
                "element": "Username",
                "ref": "e1",
                "value": "testuser"
            }
        )


# =============================================================================
# NETWORK TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_network_requests(mock_proxy_client):
    """Test browser_network_requests tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "requests": [
            {"url": "https://api.example.com/data", "method": "GET"}
        ]
    }

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_network_requests.fn(includeStatic=True)

        # Verify the result
        assert "requests" in result

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_network_requests",
            {"includeStatic": True}
        )


# =============================================================================
# TAB MANAGEMENT TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_tabs_list(mock_proxy_client):
    """Test browser_tabs with list action."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "tabs": [
            {"index": 0, "url": "https://example.com", "active": True}
        ]
    }

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_tabs.fn(action="list")

        # Verify the result
        assert "tabs" in result

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_tabs",
            {"action": "list"}
        )


@pytest.mark.asyncio
async def test_browser_tabs_new(mock_proxy_client):
    """Test browser_tabs with new action."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "created"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_tabs.fn(action="new")

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_tabs",
            {"action": "new"}
        )


@pytest.mark.asyncio
async def test_browser_tabs_close_with_index(mock_proxy_client):
    """Test browser_tabs with close action and index."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "closed"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_tabs.fn(action="close", index=1)

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_tabs",
            {"action": "close", "index": 1}
        )


# =============================================================================
# CONSOLE TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_console_messages(mock_proxy_client):
    """Test browser_console_messages tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {
        "messages": [
            {"level": "info", "text": "Page loaded"}
        ]
    }

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_console_messages.fn(level="info")

        # Verify the result
        assert "messages" in result

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_console_messages",
            {"level": "info"}
        )


# =============================================================================
# DIALOG TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_handle_dialog_accept(mock_proxy_client):
    """Test browser_handle_dialog with accept."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "accepted"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_handle_dialog.fn(accept=True)

        # Verify the result
        assert result == {"status": "accepted"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_handle_dialog",
            {"accept": True}
        )


@pytest.mark.asyncio
async def test_browser_handle_dialog_with_prompt(mock_proxy_client):
    """Test browser_handle_dialog with prompt text."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "accepted"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_handle_dialog.fn(
            accept=True,
            promptText="test input"
        )

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_handle_dialog",
            {"accept": True, "promptText": "test input"}
        )


# =============================================================================
# FILE UPLOAD TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_file_upload(mock_proxy_client):
    """Test browser_file_upload tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "uploaded"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_file_upload.fn(
            paths=["/path/to/file1.txt", "/path/to/file2.txt"]
        )

        # Verify the result
        assert result == {"status": "uploaded"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_file_upload",
            {"paths": ["/path/to/file1.txt", "/path/to/file2.txt"]}
        )


@pytest.mark.asyncio
async def test_browser_file_upload_cancel(mock_proxy_client):
    """Test browser_file_upload without paths (cancel)."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "cancelled"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_file_upload.fn()

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_file_upload",
            {}
        )


# =============================================================================
# TRACING TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_start_tracing(mock_proxy_client):
    """Test browser_start_tracing tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "tracing started"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_start_tracing.fn()

        # Verify the result
        assert result == {"status": "tracing started"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_start_tracing",
            {}
        )


@pytest.mark.asyncio
async def test_browser_stop_tracing(mock_proxy_client):
    """Test browser_stop_tracing tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "tracing stopped"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_stop_tracing.fn()

        # Verify the result
        assert result == {"status": "tracing stopped"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_stop_tracing",
            {}
        )


# =============================================================================
# INSTALLATION TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_install(mock_proxy_client):
    """Test browser_install tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "installed"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_install.fn()

        # Verify the result
        assert result == {"status": "installed"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_install",
            {}
        )


# =============================================================================
# MOUSE TOOLS
# =============================================================================


@pytest.mark.asyncio
async def test_browser_mouse_move_xy(mock_proxy_client):
    """Test browser_mouse_move_xy tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "moved"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_mouse_move_xy.fn(
            element="Canvas",
            x=100.5,
            y=200.5
        )

        # Verify the result
        assert result == {"status": "moved"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_mouse_move_xy",
            {"element": "Canvas", "x": 100.5, "y": 200.5}
        )


@pytest.mark.asyncio
async def test_browser_mouse_click_xy(mock_proxy_client):
    """Test browser_mouse_click_xy tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "clicked"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_mouse_click_xy.fn(
            element="Canvas",
            x=150.0,
            y=250.0
        )

        # Verify the result
        assert result == {"status": "clicked"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_mouse_click_xy",
            {"element": "Canvas", "x": 150.0, "y": 250.0}
        )


@pytest.mark.asyncio
async def test_browser_mouse_drag_xy(mock_proxy_client):
    """Test browser_mouse_drag_xy tool."""
    from playwright_proxy_mcp import server

    mock_proxy_client.call_tool.return_value = {"status": "dragged"}

    with patch.object(server, "proxy_client", mock_proxy_client):
        result = await server.browser_mouse_drag_xy.fn(
            element="Canvas",
            startX=100.0,
            startY=100.0,
            endX=200.0,
            endY=200.0
        )

        # Verify the result
        assert result == {"status": "dragged"}

        # Verify the proxy client was called
        mock_proxy_client.call_tool.assert_called_once_with(
            "browser_mouse_drag_xy",
            {
                "element": "Canvas",
                "startX": 100.0,
                "startY": 100.0,
                "endX": 200.0,
                "endY": 200.0
            }
        )
