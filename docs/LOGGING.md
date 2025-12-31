# MCP Tool Logging

## Overview

All MCP tool calls in the Playwright Proxy MCP server are automatically logged with comprehensive details using the `MCPLoggingMiddleware`. This middleware logs:

- **Tool parameters** (request data)
- **Tool responses** (return values)
- **Execution timing** (milliseconds)
- **Error details** (when tools fail)

## Configuration

The logging middleware is configured in [server.py](../src/playwright_proxy_mcp/server.py#L143) with the following settings:

```python
mcp.add_middleware(
    MCPLoggingMiddleware(
        log_request_params=True,    # Log all tool parameters
        log_response_data=True,     # Log all tool responses
        max_log_length=10000        # Log up to 10KB before truncation
    )
)
```

### Parameters

- **`log_request_params`** (bool): Enable/disable parameter logging (default: `True`)
- **`log_response_data`** (bool): Enable/disable response logging (default: `False`)
- **`max_log_length`** (int): Maximum characters to log before truncation (default: `5000`)

## Log Format

All logs use the **`CLIENT_MCP`** prefix for easy filtering and searching. Here's what gets logged for each tool call:

### Successful Tool Call

```
CLIENT_MCP → Tool call: browser_navigate
CLIENT_MCP   Tool 'browser_navigate' arguments: {"url": "https://example.com", "silent_mode": false}
CLIENT_MCP ← Tool result: browser_navigate (125.34ms)
CLIENT_MCP   Tool 'browser_navigate' result: {"success": true, "url": "https://example.com", ...}
```

### Failed Tool Call

```
CLIENT_MCP → Tool call: browser_click
CLIENT_MCP   Tool 'browser_click' arguments: {"element": "button", "ref": "invalid"}
CLIENT_MCP ✗ Tool error: browser_click (45.21ms) - RuntimeError: Element not found
```

## Log Levels

- **INFO**: Tool calls, parameters, responses, and timing
- **ERROR**: Tool failures and exceptions

All detailed logging is at INFO level for maximum visibility without changing log configuration.

## Filtering Logs

Use the `CLIENT_MCP` prefix to filter logs:

### All Client Tool Calls
```bash
grep "CLIENT_MCP" logs/playwright-proxy-mcp.log
```

### Specific Tool
```bash
grep "CLIENT_MCP.*browser_navigate" logs/playwright-proxy-mcp.log
```

### Only Errors
```bash
grep "CLIENT_MCP ✗" logs/playwright-proxy-mcp.log
```

### Request Parameters Only
```bash
grep "CLIENT_MCP.*arguments:" logs/playwright-proxy-mcp.log
```

### Response Data Only
```bash
grep "CLIENT_MCP.*result:" logs/playwright-proxy-mcp.log
```

### Slow Tool Calls (>1000ms)
```bash
grep -E "CLIENT_MCP.*[0-9]{4,}\.[0-9]{2}ms" logs/playwright-proxy-mcp.log
```

## What Gets Logged

### Tool Calls (`on_call_tool`)
- Tool name
- All arguments/parameters
- Execution time
- Full response data
- Errors (if any)

### Resource Reads (`on_read_resource`)
- Resource URI
- Execution time
- Errors (if any)

### Prompt Requests (`on_get_prompt`)
- Prompt name
- Prompt arguments
- Execution time
- Errors (if any)

### Initialization (`on_initialize`)
- Client name and version
- Protocol version
- Initialization status

### List Operations
- `on_list_tools`: Number of tools returned
- `on_list_resources`: Number of resources returned
- `on_list_prompts`: Number of prompts returned

## Data Truncation

Large data is automatically truncated to prevent log flooding:

- **Default limit**: 5000 characters
- **Current limit**: 10000 characters (configurable)
- **Truncation format**: `"data..."... (15000 chars total)"`

Example:
```
CLIENT_MCP   Tool 'browser_snapshot' result: {"success": true, "snapshot": "- button \"Submit\" [ref=e1]\n- button \"Cancel\" [r... (15342 chars total)"}
```

## Performance Considerations

### Token Usage Impact
Logging large responses (like ARIA snapshots) can consume significant log file space. Consider:

1. **Use `silent_mode=true`** for navigation when you don't need the snapshot
2. **Use JMESPath queries** to filter data before it's returned (and logged)
3. **Adjust `max_log_length`** based on your monitoring needs

### Disk Space
With full logging enabled, log files grow quickly:
- Typical tool call: ~500 bytes
- Large snapshot: ~10-50KB per call
- Recommended: Use log rotation (already configured in `logging_config.py`)

## Customization

To modify logging behavior, edit the middleware initialization in [server.py](../src/playwright_proxy_mcp/server.py#L143):

### Disable Response Logging (Save Space)
```python
mcp.add_middleware(
    MCPLoggingMiddleware(
        log_request_params=True,
        log_response_data=False,  # Only log requests
        max_log_length=10000
    )
)
```

### Minimal Logging (Errors Only)
```python
mcp.add_middleware(
    MCPLoggingMiddleware(
        log_request_params=False,
        log_response_data=False,
        max_log_length=1000
    )
)
```

### Unlimited Logging (Full Details)
```python
mcp.add_middleware(
    MCPLoggingMiddleware(
        log_request_params=True,
        log_response_data=True,
        max_log_length=100000  # 100KB
    )
)
```

## Testing

Run the logging demonstration:
```bash
uv run python examples/test_logging.py
```

Run the test suite:
```bash
uv run pytest tests/test_mcp_logging_middleware.py -v
```

## Implementation Details

The middleware is implemented in [src/playwright_proxy_mcp/middleware/mcp_logging.py](../src/playwright_proxy_mcp/middleware/mcp_logging.py) and uses FastMCP's middleware system to intercept all MCP operations.

Key methods:
- `on_call_tool()`: Logs tool execution
- `on_read_resource()`: Logs resource reads
- `on_get_prompt()`: Logs prompt requests
- `on_initialize()`: Logs client initialization
- `_truncate_data()`: Handles data truncation

## See Also

- [FastMCP Middleware Documentation](FASTMCP_REFERENCE.md#middleware)
- [Logging Configuration](../src/playwright_proxy_mcp/utils/logging_config.py)
- [MCP Logging Middleware Source](../src/playwright_proxy_mcp/middleware/mcp_logging.py)
