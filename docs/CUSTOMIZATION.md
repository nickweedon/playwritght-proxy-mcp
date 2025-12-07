# Playwright MCP Proxy Customization Guide

This guide explains how to customize and extend the Playwright MCP Proxy.

## Configuration

### Environment Variables

All configuration is done through environment variables in the `.env` file:

#### Playwright Configuration

```bash
# Browser selection
PLAYWRIGHT_BROWSER=chromium  # chromium, firefox, webkit, msedge

# Run headless
PLAYWRIGHT_HEADLESS=true

# Enable capabilities
PLAYWRIGHT_CAPS=vision,pdf  # vision, pdf, testing, tracing

# Timeouts (milliseconds)
PLAYWRIGHT_TIMEOUT_ACTION=5000
PLAYWRIGHT_TIMEOUT_NAVIGATION=60000

# Output directory
PLAYWRIGHT_OUTPUT_DIR=/app/playwright-output

# Session management
PLAYWRIGHT_SAVE_SESSION=true
PLAYWRIGHT_SAVE_TRACE=false
```

#### Blob Storage Configuration

```bash
# Storage location
BLOB_STORAGE_ROOT=/mnt/blob-storage

# Size limits
BLOB_MAX_SIZE_MB=500
BLOB_SIZE_THRESHOLD_KB=50  # When to use blob vs inline

# Cleanup
BLOB_TTL_HOURS=24
BLOB_CLEANUP_INTERVAL_MINUTES=60
```

See [.env.example](../.env.example) for all available options.

## Adding Custom Tools

While the proxy automatically forwards all playwright-mcp tools, you can add custom tools:

### 1. Create a New API Module

Create `src/playwright_proxy_mcp/api/custom_tools.py`:

```python
"""Custom tools for playwright proxy"""

async def analyze_screenshot(blob_id: str) -> dict:
    """
    Analyze a screenshot blob.

    Args:
        blob_id: The blob ID of the screenshot

    Returns:
        Analysis results
    """
    # Your custom logic here
    return {"analysis": "..."}
```

### 2. Register in server.py

In `src/playwright_proxy_mcp/server.py`:

```python
from .api import custom_tools

@mcp.tool()
async def analyze_screenshot(blob_id: str) -> dict:
    """Analyze a screenshot from blob storage"""
    return await custom_tools.analyze_screenshot(blob_id)
```

## Modifying Middleware Behavior

### Adjusting Binary Detection Threshold

Edit `src/playwright_proxy_mcp/playwright/middleware.py`:

```python
class BinaryInterceptionMiddleware:
    # Add more tools to always intercept
    BINARY_TOOLS = {
        "playwright_screenshot",
        "playwright_pdf",
        "playwright_save_as_pdf",
        "your_custom_binary_tool",  # Add here
    }
```

### Custom Response Transformation

Override the `intercept_response` method:

```python
async def intercept_response(self, tool_name: str, response: Any) -> Any:
    # Custom logic before standard interception
    if tool_name == "special_tool":
        # Do something special
        pass

    # Call parent implementation
    return await super().intercept_response(tool_name, response)
```

## Extending Playwright Configuration

### Adding New Configuration Options

1. Update `src/playwright_proxy_mcp/playwright/config.py`:

```python
class PlaywrightConfig(TypedDict, total=False):
    # ... existing fields ...
    custom_option: str  # Add your option
```

2. Update `load_playwright_config()`:

```python
def load_playwright_config() -> PlaywrightConfig:
    config: PlaywrightConfig = {
        # ... existing config ...
        "custom_option": os.getenv("PLAYWRIGHT_CUSTOM_OPTION", "default"),
    }
    return config
```

3. Update `src/playwright_proxy_mcp/playwright/process_manager.py`:

```python
async def _build_command(self, config: PlaywrightConfig) -> list[str]:
    # ... existing command building ...

    # Add your custom option
    if "custom_option" in config:
        command.extend(["--custom-option", config["custom_option"]])
```

## Custom Blob Storage Logic

### Implementing Custom Cleanup Logic

Override cleanup behavior in `src/playwright_proxy_mcp/playwright/blob_manager.py`:

```python
async def cleanup_expired(self) -> int:
    """Custom cleanup logic"""
    # Your custom logic here

    # Call parent cleanup
    deleted = await super().cleanup_expired()

    # Additional cleanup
    # ...

    return deleted
```

### Custom Blob Metadata

Add custom metadata when storing blobs:

```python
async def store_base64_data(
    self, base64_data: str, filename: str, tags: list[str] | None = None
) -> dict[str, Any]:
    # Add custom tags
    custom_tags = ["custom-tag", "proxy-generated"]
    all_tags = (tags or []) + custom_tags

    # Call parent with enhanced tags
    return await super().store_base64_data(base64_data, filename, all_tags)
```

## Docker Customization

### Installing Additional Browser Engines

Edit `Dockerfile`:

```dockerfile
# Install multiple browsers instead of just chromium
RUN npx playwright@latest install chromium firefox webkit --with-deps
```

### Adding Custom System Dependencies

```dockerfile
# Add your dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    your-package \
    another-package \
    && rm -rf /var/lib/apt/lists/*
```

### Adjusting Resource Limits

Edit `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      memory: 8G      # Increase for heavy usage
      cpus: '4.0'
    reservations:
      memory: 4G
      cpus: '2.0'
```

## Testing Custom Features

Create tests in `tests/test_custom.py`:

```python
"""Tests for custom features"""

import pytest
from playwright_proxy_mcp.api import custom_tools


class TestCustomTools:
    """Tests for custom tools."""

    async def test_custom_tool(self):
        """Test custom tool functionality."""
        result = await custom_tools.analyze_screenshot("blob://test.png")
        assert "analysis" in result
```

Run tests:

```bash
uv run pytest tests/test_custom.py -v
```

## Troubleshooting

### Rebuilding After Changes

If you modify the package structure, rebuild:

```bash
uv sync
```

### Docker Rebuild

After Dockerfile changes:

```bash
docker compose build --no-cache
docker compose up -d
```

### Verifying Configuration

Check loaded configuration:

```bash
uv run python -c "from playwright_proxy_mcp.playwright.config import load_playwright_config, load_blob_config; import json; print(json.dumps(load_playwright_config(), indent=2))"
```

## Best Practices

1. **Keep tools focused**: Each tool should do one thing well
2. **Use type hints**: Helps with documentation and catches errors
3. **Write tests**: Test your custom features thoroughly
4. **Document changes**: Update docstrings and README
5. **Handle errors gracefully**: Provide informative error messages
6. **Use environment variables**: Keep configuration flexible
7. **Monitor resource usage**: Browser automation can be memory-intensive

## Getting Help

- Check the [README](../README.md) for basic usage
- Review [CLAUDE.md](../CLAUDE.md) for development guidelines
- Open an issue on GitHub for bugs or feature requests
