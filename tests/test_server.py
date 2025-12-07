"""
Tests for the Playwright MCP Proxy server
"""

from playwright_proxy_mcp.server import mcp


def test_server_name():
    """Test that the server has the correct name"""
    assert mcp.name == "Playwright MCP Proxy"


def test_server_instructions():
    """Test that the server has instructions"""
    assert mcp.instructions is not None
    assert "playwright" in mcp.instructions.lower()
    assert "blob" in mcp.instructions.lower()
