# Claude Context for Playwright MCP Proxy

This document provides essential context and guidelines for Claude when working with this MCP proxy server project.

## Project Overview

This is a proxy server for Microsoft's playwright-mcp built with Python and FastMCP. It provides efficient handling of large binary data (screenshots, PDFs) by storing them as blobs and returning blob:// URIs.

**Version 2.0.0**: The proxy now supports **browser pools** - multiple isolated browser instances organized into named pools with different configurations.

## Quick Start

### Running the Server

```bash
uv run playwright-proxy-mcp
```

### Running Tests

```bash
uv run pytest -v
```

### Testing the MCP Container

Use `mcptools` for smoke testing (installed in host, not container):

```bash
# List all available tools
mcptools tools uv run --env-file host-test.env playwright-proxy-mcp

# Show help
mcptools -h
mcptools tools -h
```

## Technology Stack

- **Language**: Python 3.10+
- **Framework**: FastMCP
- **Transport**: MCP Stdio
- **Package Manager**: uv
- **Testing**: pytest, pytest-asyncio
- **Linting**: ruff
- **Containerization**: Docker

## Project Structure

```
src/playwright_proxy_mcp/
├── server.py              # Main MCP proxy server
├── types.py               # TypedDict definitions
├── playwright/            # Playwright proxy components
│   ├── config.py         # Configuration loading (env vars, pool config)
│   ├── pool_manager.py   # Browser pool management (v2.0.0)
│   ├── process_manager.py # Subprocess monitoring and logging
│   ├── blob_manager.py   # Blob storage wrapper
│   ├── middleware.py     # Binary interception logic
│   └── proxy_client.py   # Stdio transport integration
├── api/                   # MCP tools
└── utils/                 # Utility functions
    ├── jmespath_extensions.py  # Custom JMESPath functions
    ├── navigation_cache.py     # TTL-based pagination cache
    └── aria_processor.py       # ARIA snapshot processing
```

## Browser Pools Architecture (v2.0.0)

### Key Concepts

- **Pool**: Named group of browser instances with shared configuration (e.g., "CHROMIUM", "FIREFOX")
- **Instance**: Single playwright-mcp subprocess within a pool (identified by numeric ID or alias)
- **Lease**: Temporary exclusive access to a browser instance via RAII pattern (async context manager)
- **FIFO Selection**: When no specific instance is requested, instances are leased in first-in-first-out order

### Configuration

Pools are configured via environment variables using a hierarchical pattern:

```bash
# Global defaults (apply to all pools/instances)
PW_MCP_PROXY_BROWSER=chromium
PW_MCP_PROXY_HEADLESS=true

# Pool-level configuration
PW_MCP_PROXY__DEFAULT_INSTANCES=3
PW_MCP_PROXY__DEFAULT_IS_DEFAULT=true

# Instance-level overrides
PW_MCP_PROXY__DEFAULT__0_BROWSER=firefox
PW_MCP_PROXY__DEFAULT__1_ALIAS=debug
PW_MCP_PROXY__DEFAULT__1_HEADLESS=false
```

**Configuration Precedence**: Instance > Pool > Global

See [docs/BROWSER_POOLS_SPEC.md](docs/BROWSER_POOLS_SPEC.md) for complete configuration reference.

### Using Pools in Tools

All browser tools support two optional parameters:

```python
# Use default pool, FIFO instance selection
await browser_navigate(url="https://example.com")

# Use specific pool
await browser_navigate(url="https://example.com", browser_pool="FIREFOX")

# Use specific instance by ID or alias
await browser_navigate(url="https://example.com", browser_pool="DEFAULT", browser_instance="debug")
```

### Monitoring Pools

```python
# Get status of all pools
status = await browser_pool_status()

# Get status of specific pool
status = await browser_pool_status(pool_name="ISOLATED")
```

### Migration from v1.x

**v1.x** (single proxy client):
```python
proxy_client = server.proxy_client
result = await proxy_client.call_tool("browser_navigate", {"url": "..."})
```

**v2.0** (pool manager):
```python
pool_manager = server.pool_manager
pool = pool_manager.get_pool(None)  # Get default pool
async with pool.lease_instance() as proxy_client:
    result = await proxy_client.call_tool("browser_navigate", {"url": "..."})
```

## Key Development Patterns

### Tool Registration

Tools are registered in [server.py](src/playwright_proxy_mcp/server.py) using the `@mcp.tool()` decorator:

```python
@mcp.tool()
async def my_tool(param: str) -> dict:
    """Tool description shown to clients."""
    return {"result": "value"}
```

### Type Definitions

Use TypedDict classes in [types.py](src/playwright_proxy_mcp/types.py) for structured data:

```python
class ResourceData(TypedDict):
    id: str
    name: str
    description: str | None
```

### Error Handling

- Use `ToolError` from FastMCP for client-facing errors in tool implementations
- Raise `ValueError` for invalid input or not found errors
- Raise `RuntimeError` for server/API errors
- Include descriptive error messages

```python
from fastmcp import ToolError

async def get_part(part_id: str) -> dict:
    if not part_id:
        raise ToolError("part_id is required")

    try:
        result = await api_call(part_id)
        return result
    except APIError as e:
        raise ToolError(f"Failed to fetch part: {e}")
```

## Coding Standards

1. **Async by default**: All tool functions should be async
2. **Type everything**: Use type hints for parameters, returns, and variables
3. **Document thoroughly**: Docstrings are exposed to MCP clients
4. **Test comprehensively**: Each API function should have tests
5. **Handle errors gracefully**: Provide informative error messages
6. **Avoid over-engineering**: Only make changes that are directly requested or clearly necessary

## Research and Bug Fixing

When an issue may possibly have anything to do with the upstream Playwright MCP Server, perform web searches to look for known issues and/or documentation.

## Common Development Tasks

### Add a New API Endpoint/Tool

1. Create function in appropriate `api/` module
2. Add types in [types.py](src/playwright_proxy_mcp/types.py)
3. Register in [server.py](src/playwright_proxy_mcp/server.py): `mcp.tool()(module.function)`
4. Write tests

### Add a New Resource

Resources provide read-only data access:

```python
@mcp.resource("myserver://resource-name")
async def get_resource() -> str:
    """Resource description."""
    return "resource content"
```

### Add a New Prompt

Prompts are templates for common operations:

```python
@mcp.prompt()
def my_prompt() -> str:
    """Prompt description."""
    return "Prompt template text..."
```

## Documentation Index

### Core Features

- **[Browser Pools](docs/BROWSER_POOLS_SPEC.md)** - Comprehensive browser pools v2.0.0 architecture, configuration, health monitoring, migration guide
- **[ARIA Snapshots](docs/ARIA_SNAPSHOTS.md)** - Silent mode, flatten mode, JMESPath filtering, pagination, caching, utilities
- **[Bulk Execution](docs/BULK_EXECUTION.md)** - Multi-command workflows, error handling, performance optimization
- **[Blob Storage](docs/BLOB_STORAGE.md)** - Blob architecture, mcp_mapped_resource_lib usage

### Configuration & Setup

- **[Customization](docs/CUSTOMIZATION.md)** - Environment variables, adding custom tools, Docker customization
- **[WSL Windows](docs/WSL_WINDOWS.md)** - WSL→Windows mode configuration, stdio transport benefits
- **[Logging](docs/LOGGING.md)** - MCP tool logging configuration and usage

### Advanced Features

- **[Stealth Mode](docs/STEALTH.md)** - Anti-detection capabilities, browser property spoofing
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues, debugging, Claude Desktop logs

### Framework Reference

- **[FastMCP Reference](docs/FASTMCP_REFERENCE.md)** - Server implementation (tools, resources, prompts, context, middleware)
- **[FastMCP SDK Reference](docs/FASTMCP_SDK_REFERENCE.md)** - Python SDK API reference

### Examples

- **[ARIA Snapshot Format](docs/aria-snapshot/playwright_aria_snapshot_format.md)** - ARIA snapshot structure, TypeScript definitions
- **[Navigation Result Example](docs/aria-snapshot/playwright_navigate_result.md)** - Example navigation result output

## Troubleshooting

### Checking Claude Desktop Logs

Claude Desktop MCP server logs are mounted at:
- **Path**: `/workspace/logs/`
- **File**: `mcp-server-playwright-proxy-mcp-docker.log`

**Common log commands**:
```bash
# View last 50 lines
tail -n 50 /workspace/logs/mcp-server-playwright-proxy-mcp-docker.log

# Follow logs in real-time
tail -f /workspace/logs/mcp-server-playwright-proxy-mcp-docker.log

# Search for errors
grep -i error /workspace/logs/mcp-server-playwright-proxy-mcp-docker.log
```

### Server Won't Start

1. Check dependencies: `uv sync`
2. Verify `.env` file exists and has required variables
3. Check syntax: `uv run python -m py_compile src/playwright_proxy_mcp/server.py`
4. Check Claude Desktop logs

### Tests Failing

1. Ensure test dependencies: `uv sync`
2. Run with verbose output: `uv run pytest -v --tb=long`

### Docker Issues

1. Rebuild image: `docker compose build --no-cache`
2. Check logs: `docker compose logs -f`
3. Check Claude Desktop MCP logs

For more troubleshooting guidance, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Environment Variables

Configure in `.env`:

- `API_KEY`: Authentication key for backend API
- `API_BASE_URL`: Base URL for API requests
- `API_TIMEOUT`: Request timeout in seconds
- `DEBUG`: Enable debug logging
- `PLAYWRIGHT_WSL_WINDOWS`: Enable WSL→Windows mode (any non-empty value)

For complete configuration options, see [docs/CUSTOMIZATION.md](docs/CUSTOMIZATION.md).

## Getting Help

- `/help`: Get help with using Claude Code
- Report issues: https://github.com/anthropics/claude-code/issues
- FastMCP documentation: https://gofastmcp.com
- FastMCP GitHub: https://github.com/jlowin/fastmcp
