"""
Configuration management for Playwright MCP Proxy

Loads configuration from environment variables with sensible defaults
for both playwright-mcp subprocess and blob storage.
"""

import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv

# HTTP transport configuration
PLAYWRIGHT_HTTP_HOST = "127.0.0.1"  # localhost only for security
PLAYWRIGHT_HTTP_PORT = 0  # Ephemeral port (0 = OS assigns available port)

# Load environment variables from .env file
# Try multiple paths for .env file
for env_path in [
    Path.cwd() / ".env",
    Path(__file__).parent.parent.parent.parent / ".env",
    Path.home() / ".env",
]:
    if env_path.exists():
        load_dotenv(env_path)
        break


class PlaywrightConfig(TypedDict, total=False):
    """Configuration for playwright-mcp subprocess"""

    # Browser settings
    browser: str
    headless: bool
    no_sandbox: bool
    device: str | None
    viewport_size: str | None

    # Profile/storage
    isolated: bool
    user_data_dir: str | None
    storage_state: str | None

    # Network
    allowed_origins: str | None
    blocked_origins: str | None
    proxy_server: str | None

    # Capabilities
    caps: str

    # Output
    save_session: bool
    save_trace: bool
    save_video: str | None
    output_dir: str

    # Timeouts (milliseconds)
    timeout_action: int
    timeout_navigation: int

    # Images
    image_responses: str

    # Stealth settings
    user_agent: str | None
    init_script: str | None
    ignore_https_errors: bool

    # Extension support
    extension: bool
    extension_token: str | None


class BlobConfig(TypedDict):
    """Configuration for blob storage"""

    storage_root: str
    max_size_mb: int
    ttl_hours: int
    size_threshold_kb: int
    cleanup_interval_minutes: int


def _get_bool_env(key: str, default: bool) -> bool:
    """Get boolean environment variable"""
    value = os.getenv(key, str(default)).lower()
    return value in ("true", "1", "yes", "on")


def _get_int_env(key: str, default: int) -> int:
    """Get integer environment variable"""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def load_playwright_config() -> PlaywrightConfig:
    """
    Load playwright-mcp configuration from environment variables.

    Returns:
        PlaywrightConfig with all settings
    """
    config: PlaywrightConfig = {
        "browser": os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
        "headless": _get_bool_env("PLAYWRIGHT_HEADLESS", False),
        "no_sandbox": _get_bool_env("PLAYWRIGHT_NO_SANDBOX", False),
        "isolated": _get_bool_env("PLAYWRIGHT_ISOLATED", False),
        "caps": os.getenv("PLAYWRIGHT_CAPS", "vision,pdf"),
        "save_session": _get_bool_env("PLAYWRIGHT_SAVE_SESSION", False),
        "save_trace": _get_bool_env("PLAYWRIGHT_SAVE_TRACE", False),
        "output_dir": os.getenv("PLAYWRIGHT_OUTPUT_DIR", "/app/playwright-output"),
        "timeout_action": _get_int_env("PLAYWRIGHT_TIMEOUT_ACTION", 15000),
        "timeout_navigation": _get_int_env("PLAYWRIGHT_TIMEOUT_NAVIGATION", 5000),
        "image_responses": os.getenv("PLAYWRIGHT_IMAGE_RESPONSES", "allow"),
        "ignore_https_errors": _get_bool_env("PLAYWRIGHT_IGNORE_HTTPS_ERRORS", False),
        "shared_browser_context": _get_bool_env("PLAYWRIGHT_SHARED_BROWSER_CONTEXT", False),
    }

    # Optional settings - only include if set
    if device := os.getenv("PLAYWRIGHT_DEVICE"):
        config["device"] = device

    # Default viewport size to 1920x1080
    config["viewport_size"] = os.getenv("PLAYWRIGHT_VIEWPORT_SIZE", "1920x1080")

    if user_data_dir := os.getenv("PLAYWRIGHT_USER_DATA_DIR"):
        config["user_data_dir"] = user_data_dir

    if storage_state := os.getenv("PLAYWRIGHT_STORAGE_STATE"):
        config["storage_state"] = storage_state

    if allowed_origins := os.getenv("PLAYWRIGHT_ALLOWED_ORIGINS"):
        config["allowed_origins"] = allowed_origins

    if blocked_origins := os.getenv("PLAYWRIGHT_BLOCKED_ORIGINS"):
        config["blocked_origins"] = blocked_origins

    if proxy_server := os.getenv("PLAYWRIGHT_PROXY_SERVER"):
        config["proxy_server"] = proxy_server

    if save_video := os.getenv("PLAYWRIGHT_SAVE_VIDEO"):
        config["save_video"] = save_video

    # Stealth settings
    if user_agent := os.getenv("PLAYWRIGHT_USER_AGENT"):
        config["user_agent"] = user_agent

    # Default to bundled stealth script if stealth mode is enabled
    if _get_bool_env("PLAYWRIGHT_STEALTH_MODE", False):
        # Use bundled stealth.js script
        stealth_script_path = Path(__file__).parent / "stealth.js"
        if stealth_script_path.exists():
            config["init_script"] = str(stealth_script_path)

    # Allow custom init script to override
    if init_script := os.getenv("PLAYWRIGHT_INIT_SCRIPT"):
        config["init_script"] = init_script

    # Extension support
    config["extension"] = _get_bool_env("PLAYWRIGHT_EXTENSION", False)

    if extension_token := os.getenv("PLAYWRIGHT_MCP_EXTENSION_TOKEN"):
        config["extension_token"] = extension_token

    return config


def load_blob_config() -> BlobConfig:
    """
    Load blob storage configuration from environment variables.

    Returns:
        BlobConfig with all settings
    """
    return {
        "storage_root": os.getenv("BLOB_STORAGE_ROOT", "/mnt/blob-storage"),
        "max_size_mb": _get_int_env("BLOB_MAX_SIZE_MB", 500),
        "ttl_hours": _get_int_env("BLOB_TTL_HOURS", 24),
        "size_threshold_kb": _get_int_env("BLOB_SIZE_THRESHOLD_KB", 50),
        "cleanup_interval_minutes": _get_int_env("BLOB_CLEANUP_INTERVAL_MINUTES", 60),
    }
