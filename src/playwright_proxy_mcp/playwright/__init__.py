"""
Playwright MCP Proxy Package

This package provides proxy functionality for Microsoft's playwright-mcp server,
including subprocess management, blob storage for large binary data, and middleware
for response transformation.
"""

from .blob_manager import PlaywrightBlobManager
from .config import BlobConfig, PlaywrightConfig, load_blob_config, load_playwright_config
from .middleware import BinaryInterceptionMiddleware
from .process_manager import PlaywrightProcessManager
from .proxy_client import PlaywrightProxyClient

__all__ = [
    "PlaywrightBlobManager",
    "BlobConfig",
    "PlaywrightConfig",
    "load_blob_config",
    "load_playwright_config",
    "BinaryInterceptionMiddleware",
    "PlaywrightProcessManager",
    "PlaywrightProxyClient",
]
