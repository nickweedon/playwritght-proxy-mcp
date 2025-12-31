#!/usr/bin/env python3
"""
Example demonstrating MCP logging middleware functionality.

This script shows how the MCPLoggingMiddleware logs:
- Tool call parameters at INFO level
- Tool responses at INFO level
- Execution timing
- Error handling

The logs use "CLIENT_MCP" prefix for easy filtering.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from playwright_proxy_mcp.middleware.mcp_logging import MCPLoggingMiddleware

# Configure logging to see INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main():
    """Demonstrate logging middleware functionality"""
    print("=" * 80)
    print("MCP Logging Middleware Demonstration")
    print("=" * 80)
    print()

    # Create middleware with full logging enabled
    middleware = MCPLoggingMiddleware(
        log_request_params=True, log_response_data=True, max_log_length=10000
    )

    print("1. Creating mock context for browser_navigate tool call...")
    print()

    # Create mock context
    mock_context = MagicMock()
    mock_context.message = MagicMock()
    mock_context.message.name = "browser_navigate"
    mock_context.message.arguments = {
        "url": "https://example.com",
        "silent_mode": False,
        "jmespath_query": '[?role == "button"]',
        "output_format": "json",
        "limit": 50,
    }

    # Create mock response
    mock_response = {
        "success": True,
        "url": "https://example.com",
        "cache_key": "nav_abc123",
        "total_items": 150,
        "offset": 0,
        "limit": 50,
        "has_more": True,
        "snapshot": '{"elements": [...]}',
        "error": None,
        "output_format": "json",
    }

    # Mock call_next function
    mock_call_next = AsyncMock(return_value=mock_response)

    print("2. Calling middleware.on_call_tool()...")
    print()
    print("Expected logs:")
    print("  - CLIENT_MCP → Tool call: browser_navigate")
    print("  - CLIENT_MCP   Tool 'browser_navigate' arguments: {...}")
    print("  - CLIENT_MCP ← Tool result: browser_navigate (Xms)")
    print("  - CLIENT_MCP   Tool 'browser_navigate' result: {...}")
    print()
    print("Actual logs:")
    print("-" * 80)

    # Execute the middleware
    result = await middleware.on_call_tool(mock_context, mock_call_next)

    print("-" * 80)
    print()
    print(f"3. Result returned: {result}")
    print()

    print("=" * 80)
    print("Demonstration Complete!")
    print()
    print("Key Features:")
    print("  ✓ Request parameters logged at INFO level")
    print("  ✓ Response data logged at INFO level")
    print("  ✓ Execution timing included")
    print("  ✓ Data truncated at 10000 chars (configurable)")
    print("  ✓ Easy filtering with 'CLIENT_MCP' prefix")
    print()
    print("Log Filtering Examples:")
    print("  # All client MCP calls")
    print("  grep 'CLIENT_MCP' logs/playwright-proxy-mcp.log")
    print()
    print("  # Specific tool calls")
    print("  grep 'CLIENT_MCP.*browser_navigate' logs/playwright-proxy-mcp.log")
    print()
    print("  # Only errors")
    print("  grep 'CLIENT_MCP ✗' logs/playwright-proxy-mcp.log")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
