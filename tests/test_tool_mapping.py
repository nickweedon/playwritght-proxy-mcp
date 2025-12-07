"""Tests for playwright tool name mapping."""

import pytest


def test_tool_name_mapping():
    """Test that tool names are correctly mapped from playwright_ to browser_ prefix."""
    # This mapping is defined in server.py _call_playwright_tool()
    TOOL_NAME_MAP = {
        "playwright_screenshot": "browser_take_screenshot",
        "playwright_navigate": "browser_navigate",
        "playwright_click": "browser_click",
        "playwright_fill": "browser_fill_form",
        "playwright_get_visible_text": "browser_snapshot",
    }

    # These are the actual tools available from playwright-mcp
    # Based on error log from 2025-12-07
    AVAILABLE_PLAYWRIGHT_TOOLS = [
        "browser_close",
        "browser_resize",
        "browser_console_messages",
        "browser_handle_dialog",
        "browser_evaluate",
        "browser_file_upload",
        "browser_fill_form",
        "browser_install",
        "browser_press_key",
        "browser_type",
        "browser_navigate",
        "browser_navigate_back",
        "browser_network_requests",
        "browser_mouse_move_xy",
        "browser_mouse_click_xy",
        "browser_mouse_drag_xy",
        "browser_pdf_save",
        "browser_run_code",
        "browser_take_screenshot",
        "browser_snapshot",
        "browser_click",
        "browser_drag",
        "browser_hover",
        "browser_select_option",
        "browser_tabs",
        "browser_wait_for",
    ]

    # Verify all mapped tools exist in playwright-mcp
    for proxy_name, playwright_name in TOOL_NAME_MAP.items():
        assert (
            playwright_name in AVAILABLE_PLAYWRIGHT_TOOLS
        ), f"Mapped tool '{playwright_name}' not found in playwright-mcp tools"


def test_screenshot_mapping():
    """
    Regression test for screenshot tool mapping bug.

    Previously: playwright_screenshot -> browser_screenshot (WRONG - doesn't exist)
    Fixed: playwright_screenshot -> browser_take_screenshot (CORRECT)
    """
    TOOL_NAME_MAP = {
        "playwright_screenshot": "browser_take_screenshot",
    }

    # The old simple prefix replacement logic would produce this WRONG mapping
    old_logic_result = "playwright_screenshot".replace("playwright_", "browser_")
    assert old_logic_result == "browser_screenshot"

    # The correct mapping should be
    correct_mapping = TOOL_NAME_MAP["playwright_screenshot"]
    assert correct_mapping == "browser_take_screenshot"

    # Verify they are different
    assert old_logic_result != correct_mapping


def test_mapping_logic():
    """Test the tool name mapping logic works correctly."""

    TOOL_NAME_MAP = {
        "playwright_screenshot": "browser_take_screenshot",
        "playwright_navigate": "browser_navigate",
        "playwright_click": "browser_click",
        "playwright_fill": "browser_fill_form",
        "playwright_get_visible_text": "browser_snapshot",
    }

    def map_tool_name(tool_name: str) -> str:
        """Simulates the mapping logic from server.py"""
        return TOOL_NAME_MAP.get(
            tool_name,
            tool_name.replace("playwright_", "browser_", 1)
            if tool_name.startswith("playwright_")
            else tool_name,
        )

    # Test explicit mappings
    assert map_tool_name("playwright_screenshot") == "browser_take_screenshot"
    assert map_tool_name("playwright_navigate") == "browser_navigate"
    assert map_tool_name("playwright_click") == "browser_click"
    assert map_tool_name("playwright_fill") == "browser_fill_form"
    assert map_tool_name("playwright_get_visible_text") == "browser_snapshot"

    # Test fallback to simple prefix replacement
    assert map_tool_name("playwright_hover") == "browser_hover"
    assert map_tool_name("playwright_type") == "browser_type"

    # Test non-playwright tools pass through
    assert map_tool_name("browser_close") == "browser_close"
    assert map_tool_name("some_other_tool") == "some_other_tool"
