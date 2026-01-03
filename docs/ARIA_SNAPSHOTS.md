# ARIA Snapshot Management

This document covers the enhanced ARIA snapshot features in `browser_navigate`, `browser_snapshot`, and `browser_evaluate` tools.

## Overview

ARIA snapshots provide accessibility tree representations of web pages. The proxy enhances these with five major features:

1. **Silent Mode** - Skip snapshot processing for navigation-only operations
2. **Flatten Mode** - Convert hierarchical trees to flat node lists
3. **JMESPath Filtering** - Query and transform snapshots
4. **Output Format Control** - Choose JSON or YAML output
5. **Pagination with Caching** - Handle large snapshots efficiently

## Silent Mode

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

## Flatten Mode

Convert hierarchical ARIA trees to flat node lists for easier pagination and analysis:

```python
# Flatten large tree and paginate
result = await browser_navigate(
    url="https://example.com",
    flatten=True,
    limit=50,
    output_format="json"
)
# Returns: First 50 nodes in depth-first order
# cache_key="nav_abc123", total_items=500, has_more=True

# Next page
result2 = await browser_navigate(
    url="https://example.com",
    cache_key="nav_abc123",
    offset=50,
    limit=50
)
# Returns: Nodes 50-99 from cached flattened tree

# Combine flatten with JMESPath to filter by depth
result3 = await browser_snapshot(
    flatten=True,
    jmespath_query='[?_depth < 3]',  # Only first 3 levels
    output_format="json"
)
```

### How Flatten Works

- Hierarchical ARIA tree → Depth-first traversal → Flat list of nodes
- Each node gets metadata: `_depth` (nesting level), `_parent_role` (parent's role), `_index` (position)
- Children removed from nodes (no nesting in output)
- Predictable pagination (each page has exactly `limit` nodes)

### When to Use Flatten

- ✅ **Paginating large raw snapshots** without JMESPath queries (e.g., 500+ node pages)
- ✅ **Discovering all elements** in document order without deep query nesting
- ✅ **Analyzing page structure** depth (e.g., find deeply nested elements)
- ❌ **Don't use** when you need parent-child relationships preserved
- ❌ **Don't use** when JMESPath query already produces flat list (redundant)

### Flatten vs JMESPath for Pagination

| Scenario | Use Flatten | Use JMESPath |
|----------|-------------|--------------|
| Large raw snapshot | ✅ `flatten=True, limit=50` | ❌ No query = 1 root element |
| Extract specific elements | ❌ Loses structure | ✅ `jmespath_query='[?role == "button"]'` |
| Both filter & paginate | ✅ `flatten=True, jmespath_query='[?_depth < 3]', limit=50` | ✅ Works together |

### Example Output

```json
// Before flatten (tree structure - 1 root element)
[
  {
    "role": "document",
    "children": [
      {"role": "banner", "children": [
        {"role": "heading", "name": {"value": "Welcome"}}
      ]},
      {"role": "main", "children": [...]}
    ]
  }
]

// After flatten (14 standalone nodes)
[
  {"role": "document", "_depth": 0, "_parent_role": null, "_index": 0},
  {"role": "banner", "_depth": 1, "_parent_role": "document", "_index": 1},
  {"role": "heading", "name": {"value": "Welcome"}, "_depth": 2, "_parent_role": "banner", "_index": 2},
  {"role": "main", "_depth": 1, "_parent_role": "document", "_index": 3},
  // ... 10 more nodes
]
```

## JMESPath Filtering

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

### CRITICAL SYNTAX NOTE

Field names in ARIA JSON require **double quotes**, NOT backticks:
- ✅ CORRECT: `"role"`, `"name"`, `"name.value"`
- ❌ WRONG: `` `role` `` (backticks create literal strings, not field references)

### Custom Functions Available

- `nvl(value, default)`: Return default if value is null (similar to Oracle's NVL)
- `int(value)`: Convert to integer (returns null on failure)
- `str(value)`: Convert to string
- `regex_replace(pattern, replacement, value)`: Regex substitution

### Common Query Patterns

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

## Output Format Control

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

## Pagination with Caching

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

### Cache Behavior

- **TTL**: 5 minutes of inactivity
- **Scope**: Shared between `browser_navigate` and `browser_snapshot`
- **Processing Order**: Flatten (if enabled) → JMESPath filtering → Pagination → Formatting
- **Expiration**: Automatic lazy cleanup on access

### Pagination Requirements

- Requires **one of**: `flatten=True`, `jmespath_query`, or `cache_key`
- Without these, ARIA snapshots are single tree structures (not pageable)

### Response Structure

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

## Combined Features Examples

```python
# Example 1: Flatten + JMESPath + Pagination
# Navigate, flatten tree, filter by depth, paginate, return as JSON
result = await browser_navigate(
    url="https://example.com",
    flatten=True,
    jmespath_query='[?_depth < 3 && role == `button`]',  # Top 3 levels, buttons only
    output_format="json",
    limit=20
)

# Example 2: JMESPath + Pagination (without flatten)
# Filter buttons, paginate, return as JSON
result = await browser_navigate(
    url="https://example.com",
    jmespath_query='[?role == `button` && !disabled]',
    output_format="json",
    limit=20
)

# Example 3: Flatten + Pagination (no filtering)
# Flatten entire tree, paginate
result = await browser_navigate(
    url="https://example.com",
    flatten=True,
    limit=50,
    output_format="json"
)

# Example 4: Continue pagination with cache
# Get next page of same filtered/flattened results
next_page = await browser_navigate(
    url="https://example.com",
    cache_key=result["cache_key"],
    offset=20,
    limit=20
)
```

## Pagination for browser_evaluate

While `browser_navigate` and `browser_snapshot` support JMESPath filtering for ARIA snapshots, `browser_evaluate` uses simpler pagination for JavaScript evaluation results:

**Key differences:**
- **No JMESPath queries** - Use JavaScript code for filtering (e.g., `.filter()`, `.map()`)
- **No flatten mode** - JavaScript returns data structures directly, not hierarchical trees
- **No output format control** - Results are always JSON-serializable
- **Same cache mechanism** - Uses `cache_key`, `offset`, `limit` parameters

**Common use case:** Extracting large DOM query results (hundreds of links, table rows, form elements)

```python
# Extract all links with pagination (first 100)
result = await browser_evaluate(
    function="() => Array.from(document.links).map(a => ({href: a.href, text: a.innerText}))",
    limit=100
)

# Next page
result2 = await browser_evaluate(
    function="() => Array.from(document.links).map(a => ({href: a.href, text: a.innerText}))",
    cache_key=result["cache_key"],
    offset=100,
    limit=100
)
```

## ARIA Snapshot Processing Utilities

When implementing similar features or extending functionality, use these utilities:

### jmespath_extensions.py

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

### navigation_cache.py

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

### aria_processor.py

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

## Implementation Guidelines from PartsBox MCP Reference

When implementing pagination and query features for MCP tools, follow these patterns:

### 1. Pagination Parameter Standards

- `limit`: 1-10000 (or 1-1000 for stricter control)
- `offset`: Non-negative integer
- `cache_key`: Optional string for cache continuation
- Return `has_more: bool` to indicate additional pages

### 2. Response Structure Pattern

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

### 3. Cache-Then-Query-Then-Paginate Pattern

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

### 4. Error Handling Best Practices

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

## Additional Resources

- ARIA snapshot format examples: [aria-snapshot/playwright_aria_snapshot_format.md](aria-snapshot/playwright_aria_snapshot_format.md)
- Example navigation result: [aria-snapshot/playwright_navigate_result.md](aria-snapshot/playwright_navigate_result.md)
