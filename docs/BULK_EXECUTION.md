# Bulk Command Execution

The `browser_execute_bulk` tool allows sequential execution of multiple browser commands in a single MCP call, dramatically reducing round-trip overhead and improving performance for multi-step workflows.

## Basic Usage

```python
browser_execute_bulk(
    commands=[
        {"tool": "browser_navigate", "args": {"url": "https://example.com", "silent_mode": True}},
        {"tool": "browser_wait_for", "args": {"text": "Loaded"}},
        {"tool": "browser_snapshot", "args": {"jmespath_query": "...", "output_format": "json"}, "return_result": True}
    ]
)
```

## Key Features

### 1. Selective Results

Use `return_result: True` on specific commands to minimize token usage. Only commands marked with this flag will have their results included in the response.

```python
browser_execute_bulk(commands=[
    {"tool": "browser_navigate", "args": {"url": "..."}, "return_result": False},  # No result returned
    {"tool": "browser_snapshot", "args": {...}, "return_result": True}  # Result included
])
```

### 2. Error Handling

Choose between two strategies:
- `stop_on_error=True` (default): Fail-fast - stops at first error
- `stop_on_error=False`: Continue on error - executes all commands and collects all errors

### 3. All Browser Tools Supported

All 45+ browser tools work in bulk execution:
- Navigation: `browser_navigate`
- Interaction: `browser_click`, `browser_type`, `browser_hover`
- Waiting: `browser_wait_for`
- Extraction: `browser_snapshot`, `browser_screenshot`, `browser_evaluate`
- And more...

## Common Workflow Patterns

### Navigate → Wait → Extract

The most common pattern for data extraction:

```python
browser_execute_bulk(commands=[
    {"tool": "browser_navigate", "args": {"url": "https://example.com/product", "silent_mode": True}},
    {"tool": "browser_wait_for", "args": {"text": "Price"}},
    {"tool": "browser_snapshot", "args": {"jmespath_query": "[?role == 'table']", "output_format": "json"}, "return_result": True}
])
```

**Benefits**:
- 67% fewer network round-trips (1 call instead of 3)
- Token savings from `silent_mode` on navigation
- Only final snapshot returned

### Form Filling

Multi-step form interaction:

```python
browser_execute_bulk(commands=[
    {"tool": "browser_navigate", "args": {"url": "https://example.com/form", "silent_mode": True}},
    {"tool": "browser_type", "args": {"element": "textbox", "ref": "e1", "text": "user@example.com"}},
    {"tool": "browser_type", "args": {"element": "textbox", "ref": "e2", "text": "password123"}},
    {"tool": "browser_click", "args": {"element": "button", "ref": "e3"}},
    {"tool": "browser_wait_for", "args": {"text": "Welcome"}},
    {"tool": "browser_snapshot", "args": {}, "return_result": True}
])
```

### Multi-Step Navigation

Navigate through pages and extract data:

```python
browser_execute_bulk(commands=[
    {"tool": "browser_navigate", "args": {"url": "https://example.com", "silent_mode": True}},
    {"tool": "browser_click", "args": {"element": "link", "ref": "e1"}},
    {"tool": "browser_wait_for", "args": {"time": 2000}},
    {"tool": "browser_snapshot", "args": {"output_format": "json"}, "return_result": True}
])
```

## Response Structure

```python
{
    "success": bool,           # True if all commands succeeded
    "executed_count": int,     # Number of commands executed
    "total_count": int,        # Total commands in request
    "results": [Any|null],     # Results array (null if return_result=False)
    "errors": [str|null],      # Errors array (null for successful commands)
    "stopped_at": int|null     # Index where stopped (if stop_on_error=True)
}
```

**Example response**:

```python
{
    "success": True,
    "executed_count": 3,
    "total_count": 3,
    "results": [None, None, {"snapshot": "..."}],  # Only last result returned
    "errors": [None, None, None],
    "stopped_at": None
}
```

## Error Handling Examples

### Stop on First Error (Default)

```python
result = browser_execute_bulk(
    commands=[
        {"tool": "browser_navigate", "args": {"url": "https://example.com"}},
        {"tool": "browser_click", "args": {"element": "button", "ref": "invalid"}},  # Fails here
        {"tool": "browser_snapshot", "args": {}, "return_result": True}  # Not executed
    ],
    stop_on_error=True
)

# Result:
# {
#     "success": False,
#     "executed_count": 2,
#     "stopped_at": 1,
#     "errors": [None, "Element not found", None]
# }
```

### Continue on Error

```python
result = browser_execute_bulk(
    commands=[
        {"tool": "browser_navigate", "args": {"url": "https://example.com"}},
        {"tool": "browser_click", "args": {"element": "button", "ref": "invalid"}},  # Fails
        {"tool": "browser_snapshot", "args": {}, "return_result": True}  # Still executes
    ],
    stop_on_error=False
)

# Result:
# {
#     "success": False,
#     "executed_count": 3,
#     "stopped_at": None,
#     "errors": [None, "Element not found", None]
# }
```

## Performance Optimization Tips

### 1. Use `silent_mode=True` for navigation

Skip ARIA snapshots when you don't need immediate context:

```python
{"tool": "browser_navigate", "args": {"url": "...", "silent_mode": True}}
```

### 2. Mark only critical results

Use `return_result: True` sparingly to minimize token usage:

```python
# DON'T: Return all results (high token usage)
return_all_results=True

# DO: Return only final snapshot
{"tool": "browser_snapshot", "args": {...}, "return_result": True}
```

### 3. Combine with JMESPath filtering

Filter large snapshots before returning:

```python
{"tool": "browser_snapshot", "args": {"jmespath_query": "[?role == 'button']", "output_format": "json"}, "return_result": True}
```

### 4. Use pagination for large datasets

Combine bulk execution with pagination caching:

```python
browser_execute_bulk(commands=[
    {"tool": "browser_navigate", "args": {"url": "...", "limit": 50}},
    {"tool": "browser_snapshot", "args": {"cache_key": "nav_123", "offset": 50, "limit": 50}, "return_result": True}
])
```

## Limitations and Considerations

- **Sequential Execution Only**: Commands execute one after another (browser state is sequential)
- **No Parallel Execution**: Cannot run independent commands concurrently
- **Error Context**: When `stop_on_error=False`, failed commands return null results with error strings
- **Command Validation**: Invalid tool names cause runtime errors during execution (not pre-validated)

## Future Enhancements

Potential additions based on usage patterns:

1. **Pre-built Workflow Templates**: Convenience wrappers like `browser_navigate_wait_snapshot()`
2. **Command Validation**: Pre-flight check of tool names against available tools
3. **Parallel Execution**: Execute independent commands concurrently (requires Playwright context handling)
