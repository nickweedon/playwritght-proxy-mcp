# Claude Context for Playwright MCP Proxy

This document provides context and guidelines for Claude when working with this MCP proxy server project.

## Project Overview

This is a proxy server for Microsoft's playwright-mcp built with Python and FastMCP. It provides efficient handling of large binary data (screenshots, PDFs) by storing them as blobs and returning blob:// URIs. All blob retrieval is delegated to a separate MCP Resource Server, following mcp_mapped_resource_lib best practices.

## Blob Storage Architecture

This proxy server follows mcp_mapped_resource_lib best practices:

### Responsibility Separation

1. **This Proxy Server** (playwright-proxy-mcp):
   - Creates blobs from large binary data (screenshots, PDFs)
   - Returns blob:// URI references
   - Handles blob storage lifecycle (TTL, cleanup)
   - **DOES NOT** provide blob retrieval tools

2. **Separate MCP Resource Server**:
   - Retrieves blob data by blob:// URI
   - Lists available blobs
   - Deletes blobs
   - See [mcp-mapped-resource-lib](https://github.com/nickweedon/mcp_mapped_resource_lib)

### Why This Architecture?

- **Clean separation**: Tools create data, resources retrieve it
- **MCP compatibility**: Template resources cause issues with some clients
- **Standard URIs**: blob:// URIs are portable across Resource Servers

### Using Blob Data

When you receive a blob:// URI from this proxy (e.g., `blob://1733577600-hash.png`), use a separate MCP Resource Server to retrieve the actual data. This proxy does NOT provide get_blob, list_blobs, or delete_blob tools.

## Technology Stack

- **Language**: Python 3.10+
- **Framework**: FastMCP
- **HTTP Client**: requests
- **Package Manager**: uv
- **Testing**: pytest, pytest-asyncio
- **Linting**: ruff
- **Containerization**: Docker

## Project Structure

```
src/playwright_proxy_mcp/
├── server.py              # Main MCP proxy server
├── types.py               # TypedDict definitions for blob/playwright types
├── playwright/            # Playwright proxy components
│   ├── __init__.py       # Package initialization
│   ├── config.py         # Configuration loading (env vars)
│   ├── process_manager.py # Subprocess lifecycle management
│   ├── blob_manager.py   # Blob storage wrapper (mcp-mapped-resource-lib)
│   ├── middleware.py     # Binary interception logic
│   └── proxy_client.py   # Proxy client integration
├── api/                   # MCP tools (currently empty)
│   └── __init__.py
└── utils/                 # Utility functions
    ├── jmespath_extensions.py  # Custom JMESPath functions
    ├── navigation_cache.py     # TTL-based pagination cache
    └── aria_processor.py       # ARIA snapshot processing
```

## Key Patterns

### Tool Registration

Tools are registered in `server.py` using the `@mcp.tool()` decorator:

```python
@mcp.tool()
async def my_tool(param: str) -> dict:
    """Tool description shown to clients."""
    return {"result": "value"}
```

Or by importing from API modules:

```python
from .api import my_module
mcp.tool()(my_module.my_function)
```

### API Module Structure

Each API module in `src/playwright_proxy_mcp/api/` should:

1. Define async functions that perform specific operations
2. Include comprehensive docstrings (these become tool descriptions)
3. Use type hints for all parameters and return values
4. Handle errors gracefully with informative messages

Example:

```python
async def get_resource(resource_id: str) -> dict:
    """
    Get a resource by its ID.

    Args:
        resource_id: The unique identifier of the resource

    Returns:
        The resource data

    Raises:
        ValueError: If the resource is not found
    """
    # Implementation here
```

### Type Definitions

Use TypedDict classes in `types.py` for structured data:

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

### FastMCP Documentation

For detailed FastMCP implementation guidance, see:
- [docs/FASTMCP_REFERENCE.md](docs/FASTMCP_REFERENCE.md) - Server implementation (tools, resources, prompts, context, middleware, authentication, deployment)
- [docs/FASTMCP_SDK_REFERENCE.md](docs/FASTMCP_SDK_REFERENCE.md) - Python SDK reference (exceptions, settings, CLI, client, server modules, utilities)

For additional information beyond what's covered in this project's documentation, refer to:
- Official FastMCP documentation: https://gofastmcp.com
- FastMCP GitHub repository: https://github.com/jlowin/fastmcp

## Development Workflow

### Running the Server

```bash
uv run playwright-proxy-mcp
```

### Running Tests

```bash
uv run pytest -v
```

### Linting

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

### Building

```bash
uv build
```

## Coding Standards

1. **Async by default**: All tool functions should be async
2. **Type everything**: Use type hints for parameters, returns, and variables
3. **Document thoroughly**: Docstrings are exposed to MCP clients
4. **Test comprehensively**: Each API function should have tests
5. **Handle errors gracefully**: Provide informative error messages

## Adding New Features

When adding new functionality:

1. Create a new module in `src/playwright_proxy_mcp/api/`
2. Define async functions with proper docstrings
3. Add TypedDict definitions in `types.py` if needed
4. Register tools in `server.py`
5. Write tests in `tests/`
6. Update this documentation if patterns change

## ARIA Snapshot Management

### Enhanced Navigation Tools

The `browser_navigate` and `browser_snapshot` tools have been enhanced to handle large ARIA snapshots efficiently with four major features:

#### 1. Silent Mode
Skip all snapshot processing when you only need navigation/capture without output:

```python
# Navigate without retrieving snapshot (minimal token usage)
await browser_navigate(url="https://example.com", silent_mode=True)

# Capture snapshot without returning it
await browser_snapshot(silent_mode=True)
```

**Use Cases:**
- Pre-loading pages before interaction
- Navigation without context overhead
- Capturing state without immediate analysis

#### 2. JMESPath Filtering

Filter and transform ARIA snapshots using JMESPath queries with custom functions:

```python
# Find all buttons
result = await browser_navigate(
    url="https://example.com",
    jmespath_query='[?role == `button`]'
)

# Extract link names
result = await browser_snapshot(
    jmespath_query='[?role == `link`].name.value'
)

# Safe filtering with nvl() for nullable fields
result = await browser_navigate(
    url="https://example.com",
    jmespath_query='[?contains(nvl(name.value, ""), "Submit")]'
)
```

**CRITICAL SYNTAX NOTE:** Field names in ARIA JSON require **double quotes**, NOT backticks:
- ✅ CORRECT: `"role"`, `"name"`, `"name.value"`
- ❌ WRONG: `` `role` `` (backticks create literal strings, not field references)

**Custom Functions Available:**
- `nvl(value, default)`: Return default if value is null (similar to Oracle's NVL)
- `int(value)`: Convert to integer (returns null on failure)
- `str(value)`: Convert to string
- `regex_replace(pattern, replacement, value)`: Regex substitution

**Common Query Patterns:**
```python
# Filter by role
'[?role == `button`]'

# Filter by disabled state
'[?role == `textbox` && disabled == `true`]'

# Safe name search (handles null names)
'[?contains(nvl(name.value, ""), "text")]'

# Extract specific fields
'[?role == `link`].{name: name.value, ref: ref}'

# Complex filtering
'[?role == `button` && !disabled].name.value'
```

#### 3. Output Format Control

Choose between JSON and YAML output formats:

```python
# JSON output (more compact, easier for programmatic use)
result = await browser_navigate(
    url="https://example.com",
    output_format="json"
)

# YAML output (default, more readable)
result = await browser_snapshot(
    output_format="yaml"
)
```

#### 4. Pagination with Caching

Handle large snapshots efficiently with client-controlled pagination:

```python
# First page - creates cache entry
result1 = await browser_navigate(
    url="https://example.com",
    limit=50  # Return first 50 items
)
# Returns: cache_key="nav_abc123", has_more=True, total_items=200

# Next page - reuses cached snapshot
result2 = await browser_navigate(
    url="https://example.com",
    cache_key="nav_abc123",
    offset=50,
    limit=50
)
# Returns: next 50 items from cache (no re-navigation)

# Continue until has_more=False
result3 = await browser_navigate(
    url="https://example.com",
    cache_key="nav_abc123",
    offset=100,
    limit=50
)
```

**Cache Behavior:**
- **TTL**: 5 minutes of inactivity
- **Scope**: Shared between `browser_navigate` and `browser_snapshot`
- **Query Order**: JMESPath filtering → Pagination → Formatting
- **Expiration**: Automatic lazy cleanup on access

**Response Structure:**
```python
{
    "success": bool,
    "url": str,
    "cache_key": str,        # Use for subsequent paginated calls
    "total_items": int,      # Total items after query, before pagination
    "offset": int,           # Current page offset
    "limit": int,            # Items per page
    "has_more": bool,        # True if more items available
    "snapshot": str | None,  # Formatted output (or None if silent_mode)
    "error": str | None,
    "query_applied": str | None,
    "output_format": str     # "json" or "yaml"
}
```

#### Combined Features Example

```python
# Navigate, filter buttons, paginate, return as JSON
result = await browser_navigate(
    url="https://example.com",
    jmespath_query='[?role == `button` && !disabled]',
    output_format="json",
    limit=20
)

# Get next page of same filtered results
next_page = await browser_navigate(
    url="https://example.com",
    cache_key=result["cache_key"],
    offset=20,
    limit=20
)
```

### ARIA Snapshot Processing Utilities

When implementing similar features or extending functionality, use these utilities:

#### jmespath_extensions.py
Custom JMESPath functions for safer queries:

```python
from playwright_proxy_mcp.utils.jmespath_extensions import search_with_custom_functions

# Query with custom functions
result = search_with_custom_functions(
    expression='items[].nvl(value, `default`)',
    data={'items': [{'value': None}, {'value': 'test'}]}
)
# Returns: ['default', 'test']
```

**Implementation Notes:**
- All custom functions use `{"types": []}` signature to accept any type (including null)
- This prevents JMESPath type validation errors when dealing with nullable fields
- Functions are registered via `jmespath.Options(custom_functions=CustomFunctions())`

#### navigation_cache.py
TTL-based cache for pagination:

```python
from playwright_proxy_mcp.utils.navigation_cache import NavigationCache

cache = NavigationCache(default_ttl=300)  # 5 minutes

# Store data
key = cache.create(url="https://example.com", snapshot_json=data)

# Retrieve (returns None if expired)
entry = cache.get(key)
if entry:
    print(entry.snapshot_json)
    print(entry.url)
```

**Features:**
- Lazy cleanup on each access
- Touch on retrieval to extend TTL
- Returns `None` for expired/missing entries
- Thread-safe for async operations

#### aria_processor.py
ARIA snapshot parsing and formatting:

```python
from playwright_proxy_mcp.utils.aria_processor import (
    parse_aria_snapshot,
    apply_jmespath_query,
    format_output
)

# Parse YAML to JSON
yaml_text = """- button "Submit" [ref=e1]"""
json_data, errors = parse_aria_snapshot(yaml_text)

# Apply query
result, error = apply_jmespath_query(json_data, '[?role == `button`]')

# Format output
formatted = format_output(result, "json")  # or "yaml"
```

### Guidelines from PartsBox MCP Reference Implementation

When implementing pagination and query features for MCP tools, follow these patterns:

#### 1. Pagination Parameter Standards
- `limit`: 1-10000 (or 1-1000 for stricter control)
- `offset`: Non-negative integer
- `cache_key`: Optional string for cache continuation
- Return `has_more: bool` to indicate additional pages

#### 2. Response Structure Pattern
Always return structured responses with these fields:
```python
{
    "success": bool,
    "data": list | dict,
    "total_items": int,
    "offset": int,
    "limit": int,
    "has_more": bool,
    "cache_key": str,
    "error": str | None
}
```

#### 3. Docstring Best Practices

**For Tools WITH JMESPath Query Support:**
Include comprehensive docstrings with:
- One-line summary
- Detailed parameter descriptions
- JMESPath syntax notes (CRITICAL: double quotes vs backticks)
- Standard JMESPath examples
- Custom function documentation
- JSON schema in Returns section (so LLMs understand filterable structure)
- Pagination workflow examples

**Example Template:**
```python
@mcp.tool()
async def list_items(
    limit: int = 50,
    offset: int = 0,
    cache_key: str | None = None,
    query: str | None = None,
) -> dict:
    """
    List items with optional JMESPath query and pagination.

    Args:
        limit: Maximum items (1-1000, default 50)
        offset: Starting index (default 0)
        cache_key: Reuse cached data from previous call. Omit for fresh fetch.
        query: JMESPath expression for filtering/projection with custom functions.

            CRITICAL SYNTAX NOTE: Field names contain special characters.
            You MUST use DOUBLE QUOTES for field identifiers, NOT backticks:
            - CORRECT: "field/name", "data.value"
            - WRONG: `field/name` (backticks create literal strings)

            Standard JMESPath examples:
            - "[?field == 'value']" - filter by field
            - "data[].property" - project property from array

            Custom functions available:
            - nvl(value, default): Returns default if value is null
            - int(value): Convert to integer
            - str(value): Convert to string
            - regex_replace(pattern, replacement, value): Regex substitution

            IMPORTANT: Use nvl() for safe filtering on nullable fields:
            - "[?contains(nvl(name, ''), 'text')]" - safe name search

    Returns:
        PaginatedResponse with items and pagination info.

        Data items schema:
        {
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "optional_field": {"type": "string"}
            }
        }
    """
```

**For Tools WITHOUT Query Support:**
Skip the JSON schema documentation - fixed-structure returns are self-explanatory.

#### 4. Cache-Then-Query-Then-Paginate Pattern

Always follow this order:
```python
# 1. Check cache or fetch fresh data
if cache_key:
    entry = cache.get(cache_key)
    data = entry.data if entry else fetch_fresh()
else:
    data = fetch_fresh()

# 2. Create/reuse cache key
key = cache_key or cache.create(data)

# 3. Apply query (if provided)
if query:
    result = apply_query(data, query)
else:
    result = data

# 4. Handle non-list results
if not isinstance(result, list):
    result = [result]  # Wrap for consistency

# 5. Apply pagination
total = len(result)
page = result[offset : offset + limit]
has_more = offset + limit < total

# 6. Return structured response
return {
    "data": page,
    "total_items": total,
    "has_more": has_more,
    "cache_key": key,
    ...
}
```

#### 5. Error Handling Best Practices

Return structured error responses instead of raising exceptions:

```python
# Validation errors
if limit < 1 or limit > 1000:
    return {"success": False, "error": "limit must be between 1 and 1000", ...}

# Query errors
if query_error:
    return {"success": False, "error": f"Invalid JMESPath: {query_error}", ...}

# Parse errors
if parse_errors:
    return {"success": False, "error": f"Parse errors: {'; '.join(errors)}", ...}
```

#### 6. JMESPath Field Name Handling

**For fields with special characters (slashes, dots, etc.):**
```python
# Define TypedDict with functional syntax
ItemData = TypedDict('ItemData', {
    'item/id': str,
    'item/name': str,
    'data.value': int
})

# In queries: ALWAYS use double quotes
'[?"item/id" == "123"]'  # CORRECT
'[?`item/id` == "123"]'  # WRONG - backticks create literals
```

#### 7. Non-List Query Results

When JMESPath returns scalar or single object (e.g., aggregations):
```python
if not isinstance(result, list):
    # Wrap in list for consistency
    result = [result]
    total = 1
    has_more = False
    # Still paginate - offset=0 returns item, offset>0 returns empty
```

## Handling Large Files and Binary Data

### Using mcp-mapped-resource-lib

For MCP servers that need to handle large file uploads/downloads or binary blob storage, use the **mcp-mapped-resource-lib** library instead of implementing custom blob storage:

**Installation:**
```bash
pip install mcp-mapped-resource-lib
```

**Key Features:**
- Blob management with unique identifiers (`blob://TIMESTAMP-HASH.EXT`)
- Metadata storage alongside blobs
- Automatic TTL-based expiration and cleanup
- Content deduplication via SHA256
- Security features (path traversal prevention, MIME validation, size limits)
- Docker volume integration for shared storage across containers

**Basic Usage:**
```python
from mcp_mapped_resource_lib import BlobStorage

# Initialize storage
storage = BlobStorage(
    storage_root="/mnt/blob-storage",
    max_size_mb=100
)

# Upload a blob
result = storage.upload_blob(
    data=b"file content",
    filename="document.pdf"
)

# Retrieve metadata
metadata = storage.get_metadata(result['blob_id'])

# Delete when done
storage.delete_blob(result['blob_id'])
```

**Docker Setup:**
When using with Docker, mount a shared volume for blob storage:

```yaml
volumes:
  - blob-storage:/mnt/blob-storage
```

**Important:** This library requires `libmagic` for MIME detection:
- Ubuntu/Debian: `apt-get install libmagic1`
- macOS: Install via Homebrew

For more details, see: https://github.com/nickweedon/mcp_mapped_resource_lib

## Common Tasks

### Add a new API endpoint/tool

1. Create function in appropriate `api/` module
2. Add types in `types.py`
3. Register in `server.py`: `mcp.tool()(module.function)`
4. Write tests

### Add a new resource

Resources provide read-only data access:

```python
@mcp.resource("myserver://resource-name")
async def get_resource() -> str:
    """Resource description."""
    return "resource content"
```

### Add a new prompt

Prompts are templates for common operations:

```python
@mcp.prompt()
def my_prompt() -> str:
    """Prompt description."""
    return "Prompt template text..."
```

## Environment Variables

Configure in `.env`:

- `API_KEY`: Authentication key for backend API
- `API_BASE_URL`: Base URL for API requests
- `API_TIMEOUT`: Request timeout in seconds
- `DEBUG`: Enable debug logging

## Troubleshooting

### Checking Claude Desktop Logs

When working in the devcontainer, Claude Desktop MCP server logs are mounted at:
- **Path**: `/workspace/logs/`
- **Source**: `C:\Users\nickw\AppData\Roaming\Claude\logs\`

These logs contain output from the MCP server as it's being used by the Claude Desktop application. When asked to check logs or diagnose issues, refer to the ```mcp-server-playwright-proxy-mcp-docker.log``` file.

**Common log commands**:
```bash
# View last 50 lines
tail -n 50 /workspace/logs/claude-desktop-mcp.log

# Follow logs in real-time
tail -f /workspace/logs/claude-desktop-mcp.log

# Search for errors
grep -i error /workspace/logs/claude-desktop-mcp.log

# View full log
cat /workspace/logs/claude-desktop-mcp.log
```

### Server won't start

1. Check that all dependencies are installed: `uv sync`
2. Verify `.env` file exists and has required variables
3. Check for syntax errors: `uv run python -m py_compile src/playwright_proxy_mcp/server.py`
4. Check Claude Desktop logs: `tail -f /workspace/logs/claude-desktop-mcp.log`

### Tests failing

1. Ensure test dependencies are installed: `uv sync`
2. Run with verbose output: `uv run pytest -v --tb=long`

### Docker issues

1. Rebuild image: `docker compose build --no-cache`
2. Check logs: `docker compose logs -f`
3. Check Claude Desktop MCP logs: `tail -f /workspace/logs/claude-desktop-mcp.log`
