# Blob Storage Architecture

This document describes how the proxy server handles large binary data (screenshots, PDFs) using the mcp_mapped_resource_lib library.

## Overview

The proxy server follows mcp_mapped_resource_lib best practices by separating blob creation from blob retrieval:

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

## Why This Architecture?

- **Clean separation**: Tools create data, resources retrieve it
- **MCP compatibility**: Template resources cause issues with some clients
- **Standard URIs**: blob:// URIs are portable across Resource Servers

## Using Blob Data

When you receive a blob:// URI from this proxy (e.g., `blob://1733577600-hash.png`), use a separate MCP Resource Server to retrieve the actual data. This proxy does NOT provide get_blob, list_blobs, or delete_blob tools.

## Using mcp-mapped-resource-lib

For MCP servers that need to handle large file uploads/downloads or binary blob storage, use the **mcp-mapped-resource-lib** library instead of implementing custom blob storage.

### Installation

```bash
pip install mcp-mapped-resource-lib
```

### Key Features

- Blob management with unique identifiers (`blob://TIMESTAMP-HASH.EXT`)
- Metadata storage alongside blobs
- Automatic TTL-based expiration and cleanup
- Content deduplication via SHA256
- Security features (path traversal prevention, MIME validation, size limits)
- Docker volume integration for shared storage across containers

### Basic Usage

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

### Docker Setup

When using with Docker, mount a shared volume for blob storage:

```yaml
volumes:
  - blob-storage:/mnt/blob-storage
```

### System Requirements

This library requires `libmagic` for MIME detection:
- Ubuntu/Debian: `apt-get install libmagic1`
- macOS: Install via Homebrew

### Additional Resources

For more details, see: https://github.com/nickweedon/mcp_mapped_resource_lib
