"""
Tests for binary interception middleware
"""

import base64
from unittest.mock import AsyncMock, Mock

import pytest

from playwright_proxy_mcp.playwright.middleware import BinaryInterceptionMiddleware


@pytest.fixture
def mock_blob_manager():
    """Create a mock blob manager."""
    manager = Mock()
    manager.store_base64_data = AsyncMock()
    return manager


@pytest.fixture
def middleware(mock_blob_manager):
    """Create middleware instance."""
    return BinaryInterceptionMiddleware(mock_blob_manager, size_threshold_kb=50)


class TestBinaryInterceptionMiddleware:
    """Tests for BinaryInterceptionMiddleware."""

    def test_init(self, mock_blob_manager):
        """Test middleware initialization."""
        middleware = BinaryInterceptionMiddleware(mock_blob_manager, size_threshold_kb=100)

        assert middleware.blob_manager == mock_blob_manager
        assert middleware.size_threshold_bytes == 100 * 1024

    @pytest.mark.asyncio
    async def test_intercept_response_non_dict(self, middleware):
        """Test that non-dict responses are returned unchanged."""
        result = await middleware.intercept_response("some_tool", "string response")
        assert result == "string response"

        result = await middleware.intercept_response("some_tool", 123)
        assert result == 123

        result = await middleware.intercept_response("some_tool", None)
        assert result is None

    @pytest.mark.asyncio
    async def test_intercept_response_calltoolresult_conversion(self, middleware):
        """Test that CallToolResult dataclass is converted to dict."""
        from dataclasses import dataclass
        from typing import Any

        @dataclass
        class MockCallToolResult:
            """Mock CallToolResult matching FastMCP Client's dataclass structure."""
            content: list[Any]
            structured_content: dict[str, Any] | None = None
            meta: dict[str, Any] | None = None
            data: Any = None
            is_error: bool = False

        # Create a mock CallToolResult
        mock_result = MockCallToolResult(
            content=[{"type": "text", "text": "Hello"}],
            structured_content=None,
            meta={"foo": "bar"},
            data=None,
            is_error=False,
        )

        # Test conversion for non-binary tool (should convert but not transform)
        result = await middleware.intercept_response("non_binary_tool", mock_result)

        # Should be converted to dict
        assert isinstance(result, dict)
        assert result["content"] == [{"type": "text", "text": "Hello"}]
        assert result["structured_content"] is None
        assert result["meta"] == {"foo": "bar"}
        assert result["data"] is None
        assert result["is_error"] is False

    @pytest.mark.asyncio
    async def test_intercept_response_non_binary_tool(self, middleware):
        """Test that responses from non-binary tools are returned unchanged."""
        response = {"status": "success", "data": "some data"}

        result = await middleware.intercept_response("non_binary_tool", response)

        assert result == response

    @pytest.mark.asyncio
    async def test_intercept_response_binary_tool_small_data(self, middleware):
        """Test that small binary data is not stored as blob."""
        # Create small data (less than 50KB threshold)
        small_data = b"x" * 100
        base64_data = base64.b64encode(small_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        response = {"screenshot": data_uri}

        result = await middleware.intercept_response("playwright_screenshot", response)

        # Data should not be transformed
        assert result == response

    @pytest.mark.asyncio
    async def test_intercept_response_binary_tool_large_data(self, middleware, mock_blob_manager):
        """Test that large binary data is stored as blob."""
        # Create large data (more than 50KB threshold)
        large_data = b"x" * (60 * 1024)  # 60KB
        base64_data = base64.b64encode(large_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        response = {"screenshot": data_uri}

        # Mock blob storage
        mock_blob_manager.store_base64_data.return_value = {
            "blob_id": "blob://test-123.png",
            "size_bytes": len(large_data),
            "mime_type": "image/png",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        result = await middleware.intercept_response("playwright_screenshot", response)

        # Should have blob reference instead of data
        assert result["screenshot"] == "blob://test-123.png"
        assert result["screenshot_size_kb"] == len(large_data) // 1024
        assert result["screenshot_mime_type"] == "image/png"
        assert result["screenshot_blob_retrieval_tool"] == "get_blob"
        assert "screenshot_expires_at" in result

        # Verify blob storage was called
        mock_blob_manager.store_base64_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_intercept_response_nested_data(self, middleware, mock_blob_manager):
        """Test that nested data is processed recursively."""
        large_data = b"x" * (60 * 1024)
        base64_data = base64.b64encode(large_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        response = {
            "status": "success",
            "result": {
                "screenshot": data_uri,
                "other": "data",
            },
        }

        mock_blob_manager.store_base64_data.return_value = {
            "blob_id": "blob://test.png",
            "size_bytes": len(large_data),
            "mime_type": "image/png",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        result = await middleware.intercept_response("playwright_screenshot", response)

        assert result["status"] == "success"
        assert result["result"]["screenshot"] == "blob://test.png"
        assert result["result"]["other"] == "data"

    @pytest.mark.asyncio
    async def test_should_store_as_blob_data_uri(self, middleware):
        """Test detection of data URI that should be stored."""
        large_data = b"x" * (60 * 1024)
        base64_data = base64.b64encode(large_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        result = await middleware._should_store_as_blob(data_uri)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_store_as_blob_small_data_uri(self, middleware):
        """Test that small data URI is not stored."""
        small_data = b"x" * 100
        base64_data = base64.b64encode(small_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        result = await middleware._should_store_as_blob(data_uri)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_store_as_blob_plain_base64(self, middleware):
        """Test detection of plain base64 string."""
        large_data = b"x" * (60 * 1024)
        base64_data = base64.b64encode(large_data).decode("utf-8")

        result = await middleware._should_store_as_blob(base64_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_store_as_blob_not_base64(self, middleware):
        """Test that non-base64 string is not stored."""
        result = await middleware._should_store_as_blob("This is not base64!")
        assert result is False

    @pytest.mark.asyncio
    async def test_should_store_as_blob_short_string(self, middleware):
        """Test that short strings are not stored."""
        result = await middleware._should_store_as_blob("short")
        assert result is False

    @pytest.mark.asyncio
    async def test_store_as_blob(self, middleware, mock_blob_manager):
        """Test storing data as blob."""
        data_uri = "data:image/png;base64,SGVsbG8="

        mock_blob_manager.store_base64_data.return_value = {
            "blob_id": "blob://test.png",
            "size_bytes": 5,
            "mime_type": "image/png",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        result = await middleware._store_as_blob(data_uri, "screenshot", "playwright_screenshot")

        assert result["blob_id"] == "blob://test.png"

        # Verify blob manager was called with correct arguments
        mock_blob_manager.store_base64_data.assert_called_once()
        call_args = mock_blob_manager.store_base64_data.call_args
        assert call_args[1]["base64_data"] == data_uri
        assert call_args[1]["filename"] == "playwright_screenshot_screenshot.png"
        assert call_args[1]["tags"] == ["playwright_screenshot", "screenshot"]

    def test_get_extension_from_data_uri_png(self, middleware):
        """Test extracting .png extension from data URI."""
        data_uri = "data:image/png;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".png"

    def test_get_extension_from_data_uri_jpeg(self, middleware):
        """Test extracting .jpg extension from data URI."""
        data_uri = "data:image/jpeg;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".jpg"

    def test_get_extension_from_data_uri_pdf(self, middleware):
        """Test extracting .pdf extension from data URI."""
        data_uri = "data:application/pdf;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".pdf"

    def test_get_extension_from_data_uri_webp(self, middleware):
        """Test extracting .webp extension from data URI."""
        data_uri = "data:image/webp;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".webp"

    def test_get_extension_from_data_uri_video(self, middleware):
        """Test extracting video extension from data URI."""
        data_uri = "data:video/webm;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".webm"

    def test_get_extension_from_data_uri_unknown(self, middleware):
        """Test unknown MIME type returns .bin."""
        data_uri = "data:application/unknown;base64,..."
        assert middleware._get_extension_from_data_uri(data_uri) == ".bin"

    def test_get_extension_from_data_uri_no_prefix(self, middleware):
        """Test plain base64 without data URI returns .bin."""
        assert middleware._get_extension_from_data_uri("SGVsbG8=") == ".bin"

    @pytest.mark.asyncio
    async def test_binary_tools_constant(self, middleware):
        """Test that BINARY_TOOLS is defined correctly."""
        assert "playwright_screenshot" in middleware.BINARY_TOOLS
        assert "playwright_pdf" in middleware.BINARY_TOOLS
        assert "playwright_save_as_pdf" in middleware.BINARY_TOOLS

    @pytest.mark.asyncio
    async def test_conditional_binary_tools_constant(self, middleware):
        """Test that CONDITIONAL_BINARY_TOOLS is defined."""
        assert "playwright_get_console" in middleware.CONDITIONAL_BINARY_TOOLS
        assert "playwright_download" in middleware.CONDITIONAL_BINARY_TOOLS

    @pytest.mark.asyncio
    async def test_intercept_pdf_tool(self, middleware, mock_blob_manager):
        """Test intercepting PDF tool response."""
        large_data = b"x" * (60 * 1024)
        base64_data = base64.b64encode(large_data).decode("utf-8")
        data_uri = f"data:application/pdf;base64,{base64_data}"

        response = {"pdf": data_uri}

        mock_blob_manager.store_base64_data.return_value = {
            "blob_id": "blob://test.pdf",
            "size_bytes": len(large_data),
            "mime_type": "application/pdf",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        result = await middleware.intercept_response("playwright_pdf", response)

        assert result["pdf"] == "blob://test.pdf"

    @pytest.mark.asyncio
    async def test_intercept_content_array_with_pydantic_models(self, middleware, mock_blob_manager):
        """Test intercepting content array with Pydantic model objects (not dicts)."""
        from dataclasses import dataclass

        # Create a mock Pydantic-like model with attributes
        @dataclass
        class BinaryContent:
            """Mock BinaryContent matching FastMCP's structure."""
            type: str
            data: str
            mimeType: str

        # Create large base64 data
        large_data = b"x" * (60 * 1024)
        base64_data = base64.b64encode(large_data).decode("utf-8")

        # Create a mock CallToolResult with BinaryContent objects (not dicts)
        @dataclass
        class MockCallToolResult:
            content: list
            is_error: bool = False

        binary_item = BinaryContent(
            type="image",
            data=base64_data,
            mimeType="image/png"
        )

        mock_result = MockCallToolResult(
            content=[binary_item],
            is_error=False
        )

        # Mock blob storage
        mock_blob_manager.store_base64_data.return_value = {
            "blob_id": "blob://test-123.png",
            "size_bytes": len(large_data),
            "mime_type": "image/png",
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
        }

        result = await middleware.intercept_response("browser_take_screenshot", mock_result)

        # Should have transformed the BinaryContent object to a blob reference dict
        assert isinstance(result, dict)
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "blob"
        assert result["content"][0]["blob_id"] == "blob://test-123.png"
        assert result["content"][0]["size_kb"] == len(large_data) // 1024
        assert result["content"][0]["mime_type"] == "image/png"

        # Verify blob storage was called
        mock_blob_manager.store_base64_data.assert_called_once()
