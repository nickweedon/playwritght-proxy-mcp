# Playwright MCP Proxy

A proxy server for Microsoft's [playwright-mcp](https://github.com/microsoft/playwright-mcp) that provides efficient handling of large binary data (screenshots, PDFs) through blob storage.

## Features

- **Playwright Browser Automation**: Full access to all playwright-mcp browser automation tools
- **Efficient Binary Handling**: Large screenshots and PDFs are automatically stored as blobs to reduce token usage
- **Blob Storage**: Built-in blob management using [mcp-mapped-resource-lib](https://github.com/nickweedon/mcp_mapped_resource_lib)
- **Automatic Cleanup**: TTL-based automatic expiration of old blobs
- **Docker Support**: Containerized deployment with multi-runtime support (Python + Node.js + Playwright)
- **Configurable**: Extensive configuration options for both playwright and blob storage

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Node.js 18+ (for playwright-mcp)
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- Docker (optional, for containerized deployment)

### Installation

1. Clone this repository:

```bash
git clone <this-repo> playwright-proxy-mcp
cd playwright-proxy-mcp
```

2. Install dependencies:

```bash
uv sync
```

3. Create your environment file:

```bash
cp .env.example .env
# Edit .env with your configuration (defaults are sensible)
```

4. Run the server:

```bash
uv run playwright-proxy-mcp
```

The server will:
- Start the playwright-mcp subprocess via npx
- Initialize blob storage
- Listen for MCP client connections on stdio

## Docker Deployment

Build and run with Docker Compose:

```bash
docker compose up -d
```

This will:
- Build a container with Python, Node.js, and Playwright browsers
- Create persistent volumes for blob storage and playwright output
- Start the proxy server on port 8000

## Configuration

Configure the proxy via environment variables in `.env`:

### Playwright Browser Settings

- `PLAYWRIGHT_BROWSER`: Browser to use (chromium, firefox, webkit) - default: chromium
- `PLAYWRIGHT_HEADLESS`: Run headless - default: true
- `PLAYWRIGHT_CAPS`: Capabilities (vision,pdf,testing,tracing) - default: vision,pdf
- `PLAYWRIGHT_TIMEOUT_ACTION`: Action timeout in ms - default: 5000
- `PLAYWRIGHT_TIMEOUT_NAVIGATION`: Navigation timeout in ms - default: 60000

### Blob Storage Settings

- `BLOB_STORAGE_ROOT`: Storage directory - default: /mnt/blob-storage
- `BLOB_MAX_SIZE_MB`: Max size per blob - default: 500
- `BLOB_TTL_HOURS`: Time-to-live for blobs - default: 24
- `BLOB_SIZE_THRESHOLD_KB`: Size threshold for blob storage - default: 50
- `BLOB_CLEANUP_INTERVAL_MINUTES`: Cleanup frequency - default: 60

See `.env.example` for all available options.

## How It Works

### Binary Data Interception

The proxy automatically detects large binary data in playwright tool responses:

1. When playwright tools return screenshots or PDFs
2. If the data size exceeds the threshold (default: 50KB)
3. The proxy stores the binary data as a blob
4. The response is transformed to include a blob reference instead

**Before (direct playwright-mcp):**
```json
{
  "screenshot": "data:image/png;base64,iVBORw0KGgo...500KB of data..."
}
```

**After (through proxy):**
```json
{
  "screenshot": "blob://1733577600-a3f2c1d9e4b5.png",
  "screenshot_size_kb": 500,
  "screenshot_mime_type": "image/png",
  "screenshot_blob_retrieval_tool": "get_blob",
  "screenshot_expires_at": "2024-12-08T10:00:00Z"
}
```

### Retrieving Blobs

Use the `get_blob` tool to retrieve binary data when needed:

```python
result = await get_blob("blob://1733577600-a3f2c1d9e4b5.png")
# Returns the original base64-encoded image data
```

## Available Tools

### Playwright Tools (Proxied)

All playwright-mcp tools are available:

- `playwright_navigate`: Navigate to a URL
- `playwright_click`: Click an element
- `playwright_fill`: Fill a form field
- `playwright_screenshot`: Take a screenshot (auto-stored as blob if large)
- `playwright_get_visible_text`: Get page text
- And many more...

### Blob Management Tools

- `get_blob(blob_id)`: Retrieve binary data by blob ID
- `list_blobs(mime_type, tags, limit)`: List available blobs with filtering
- `delete_blob(blob_id)`: Delete a blob from storage

## Architecture

```
┌─────────────────────────────────┐
│  MCP Client (Claude Desktop)   │
└────────────┬────────────────────┘
             │ stdio
┌────────────▼────────────────────┐
│  FastMCP Proxy (Python)         │
│  - Binary Interception          │
│  - Blob Storage Integration     │
│  - Tool Forwarding              │
└────────────┬────────────────────┘
             │ stdio
┌────────────▼────────────────────┐
│  playwright-mcp (Node.js/npx)   │
│  - Browser Automation           │
│  - Screenshot/PDF Generation    │
└─────────────────────────────────┘
```

## Testing

Run the test suite:

```bash
uv run pytest -v
```

Lint the code:

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## Project Structure

```
src/playwright_proxy_mcp/
├── server.py              # Main MCP proxy server
├── types.py               # TypedDict definitions
├── playwright/            # Playwright proxy components
│   ├── config.py         # Configuration loading
│   ├── process_manager.py # Subprocess management
│   ├── blob_manager.py   # Blob storage wrapper
│   ├── middleware.py     # Binary interception
│   └── proxy_client.py   # Proxy client integration
└── api/
    └── blob_tools.py     # Blob retrieval tools
```

## Benefits

### Token Savings

Large screenshots can consume 50,000+ tokens. With blob storage:
- Screenshots stored as blobs use ~100 tokens for the reference
- Retrieve full data only when needed
- Automatic cleanup prevents storage bloat

### Performance

- Faster response times for tool calls
- Reduced context window usage
- Efficient deduplication of identical screenshots

## Troubleshooting

### npx not found

Ensure Node.js is installed and npx is in your PATH:

```bash
node --version
npx --version
```

### Playwright browser installation fails

Install browsers manually:

```bash
npx playwright@latest install chromium --with-deps
```

### Blob storage permissions

Ensure the blob storage directory is writable:

```bash
chmod -R 755 /mnt/blob-storage
```

## License

MIT

## Contributing

Contributions welcome! Please open an issue or pull request.

## Resources

- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [FastMCP Documentation](https://gofastmcp.com)
- [MCP Mapped Resource Lib](https://github.com/nickweedon/mcp_mapped_resource_lib)
- [Model Context Protocol](https://modelcontextprotocol.io)
