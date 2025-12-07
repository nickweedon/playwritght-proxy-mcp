# Skeleton MCP Server

A template project for building [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers. This skeleton provides a solid foundation with best practices, Docker support, and example implementations.

## Features

- FastMCP framework for easy MCP server development
- Docker and Docker Compose support for containerized deployment
- VS Code Dev Container configuration for consistent development environments
- Example CRUD API implementation to demonstrate patterns
- Test suite with pytest
- Claude Code integration with custom commands

## Quick Start

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- Docker (optional, for containerized deployment)

### Installation

1. Clone this repository and rename it for your project:

```bash
git clone <this-repo> my-mcp-server
cd my-mcp-server
```

2. Rename the package:
   - Rename `src/skeleton_mcp` to `src/your_project_name`
   - Update `pyproject.toml` with your project name and metadata
   - Update imports in all Python files

3. Install dependencies:

```bash
uv sync
```

4. Create your environment file:

```bash
cp .env.example .env
# Edit .env with your API credentials
```

5. Run the server:

```bash
uv run skeleton-mcp
```

## Project Structure

```
skeleton_mcp/
├── src/skeleton_mcp/
│   ├── __init__.py          # Package initialization
│   ├── server.py            # Main MCP server entry point
│   ├── client.py            # API client for backend communication
│   ├── types.py             # TypedDict definitions
│   ├── api/                  # API modules
│   │   ├── __init__.py
│   │   └── example.py       # Example CRUD operations
│   └── utils/               # Utility modules
│       └── __init__.py
├── tests/                   # Test suite
│   ├── conftest.py          # Pytest fixtures
│   ├── test_example_api.py  # API tests
│   └── test_server.py       # Server tests
├── docs/                    # Documentation
├── .claude/                 # Claude Code configuration
│   ├── commands/            # Custom slash commands
│   └── settings.local.json  # Permission settings
├── .devcontainer/           # VS Code dev container
├── Dockerfile               # Container image definition
├── docker-compose.yml       # Production compose file
├── docker-compose.devcontainer.yml  # Dev container compose
├── pyproject.toml           # Project configuration
├── CLAUDE.md               # Claude context documentation
└── README.md               # This file
```

## Development

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

## Adding Your Own Tools

1. Create a new module in `src/skeleton_mcp/api/`:

```python
# src/skeleton_mcp/api/my_api.py

async def my_tool(param1: str, param2: int = 10) -> dict:
    """
    Description of what this tool does.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value
    """
    # Your implementation here
    return {"result": "success"}
```

2. Register the tool in `server.py`:

```python
from .api import my_api

mcp.tool()(my_api.my_tool)
```

3. Add types in `types.py` if needed:

```python
class MyDataType(TypedDict):
    field1: str
    field2: int
```

## Handling Large Files and Binary Data

For MCP servers that need to handle large file uploads, downloads, or binary blob storage, use the [mcp-mapped-resource-lib](https://github.com/nickweedon/mcp_mapped_resource_lib) library:

```bash
pip install mcp-mapped-resource-lib
```

This library provides:
- Blob management with unique identifiers
- Automatic TTL-based expiration and cleanup
- Content deduplication
- Security features (path traversal prevention, MIME validation)
- Docker volume integration for shared storage

See [CLAUDE.md](CLAUDE.md#handling-large-files-and-binary-data) for detailed usage examples.

## Docker Deployment

### Build and run with Docker Compose:

```bash
docker compose up --build
```

### For development with VS Code Dev Containers:

1. Open the project in VS Code
2. Install the "Dev Containers" extension
3. Click "Reopen in Container" when prompted

## Claude Desktop Integration

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "skeleton-mcp": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--env-file",
        "/path/to/your/.env",
        "skeleton-mcp:latest"
      ]
    }
  }
}
```

Or for local development:

```json
{
  "mcpServers": {
    "skeleton-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/skeleton_mcp", "run", "skeleton-mcp"]
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `health_check` | Check server health and configuration status |
| `list_items` | List all items with filtering and pagination |
| `get_item` | Get a specific item by ID |
| `create_item` | Create a new item |
| `update_item` | Update an existing item |
| `delete_item` | Delete an item |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | Your API key for authentication | (required) |
| `API_BASE_URL` | Base URL for the backend API | `https://api.example.com/v1` |
| `API_TIMEOUT` | Request timeout in seconds | `30` |
| `DEBUG` | Enable debug logging | `false` |

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request
