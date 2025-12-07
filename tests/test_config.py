"""
Tests for configuration loading
"""


from playwright_proxy_mcp.playwright.config import load_blob_config, load_playwright_config


class TestPlaywrightConfig:
    """Tests for Playwright configuration."""

    def test_load_default_config(self):
        """Test loading default configuration."""
        config = load_playwright_config()

        assert config["browser"] == "chromium"
        assert config["headless"] is True
        assert config["caps"] == "vision,pdf"
        assert config["timeout_action"] == 5000
        assert config["timeout_navigation"] == 60000

    def test_load_config_from_env(self, monkeypatch):
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("PLAYWRIGHT_BROWSER", "firefox")
        monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "false")
        monkeypatch.setenv("PLAYWRIGHT_TIMEOUT_ACTION", "10000")

        config = load_playwright_config()

        assert config["browser"] == "firefox"
        assert config["headless"] is False
        assert config["timeout_action"] == 10000


class TestBlobConfig:
    """Tests for blob storage configuration."""

    def test_load_default_blob_config(self):
        """Test loading default blob configuration."""
        config = load_blob_config()

        assert config["storage_root"] == "/mnt/blob-storage"
        assert config["max_size_mb"] == 500
        assert config["ttl_hours"] == 24
        assert config["size_threshold_kb"] == 50
        assert config["cleanup_interval_minutes"] == 60

    def test_load_blob_config_from_env(self, monkeypatch):
        """Test loading blob config from environment variables."""
        monkeypatch.setenv("BLOB_STORAGE_ROOT", "/tmp/blobs")
        monkeypatch.setenv("BLOB_MAX_SIZE_MB", "100")
        monkeypatch.setenv("BLOB_TTL_HOURS", "12")

        config = load_blob_config()

        assert config["storage_root"] == "/tmp/blobs"
        assert config["max_size_mb"] == 100
        assert config["ttl_hours"] == 12
