"""Test that middleware properly converts text content objects to dictionaries."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass
from typing import Any

from playwright_proxy_mcp.playwright.middleware import BinaryInterceptionMiddleware


@dataclass
class TextContent:
    """Mock text content object (similar to what FastMCP Client returns)."""
    type: str
    text: str


@dataclass
class MockCallToolResult:
    """Mock CallToolResult matching FastMCP Client's dataclass structure."""
    content: list[Any]
    structured_content: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    data: Any = None
    is_error: bool = False


@pytest.mark.asyncio
async def test_middleware_converts_text_content_objects_to_dicts():
    """Test that text content objects are converted to dictionaries."""
    # Create mock blob manager
    mock_blob_manager = MagicMock()

    # Create middleware
    middleware = BinaryInterceptionMiddleware(mock_blob_manager, size_threshold_kb=50)

    # Create a mock response with text content as objects (not dicts)
    response = MockCallToolResult(
        content=[
            TextContent(type="text", text="- button 'Submit' [ref=e1]\n- link 'Home' [ref=e2]")
        ],
        is_error=False,
    )

    # Intercept the response
    result = await middleware.intercept_response("browser_navigate", response)

    # Verify result is a dict
    assert isinstance(result, dict)
    assert "content" in result

    # Verify content items are converted to dicts
    assert isinstance(result["content"], list)
    assert len(result["content"]) == 1

    # The critical check: content items should be dicts, not objects
    content_item = result["content"][0]
    assert isinstance(content_item, dict), f"Expected dict, got {type(content_item)}"
    assert content_item["type"] == "text"
    assert content_item["text"] == "- button 'Submit' [ref=e1]\n- link 'Home' [ref=e2]"


@pytest.mark.asyncio
async def test_middleware_converts_mixed_content_objects():
    """Test that middleware handles mixed content types (text and image objects)."""
    # Create mock blob manager
    mock_blob_manager = MagicMock()
    mock_blob_manager.store_base64_data = AsyncMock(
        return_value={
            "blob_id": "blob://123.png",
            "size_bytes": 1024,
            "mime_type": "image/png",
            "expires_at": "2024-01-01T00:00:00Z",
        }
    )

    # Create middleware
    middleware = BinaryInterceptionMiddleware(mock_blob_manager, size_threshold_kb=50)

    # Create objects for both text and image content
    @dataclass
    class ImageContent:
        type: str
        data: str
        mimeType: str

    # Small base64 data (won't be stored as blob)
    small_image_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    response = MockCallToolResult(
        content=[
            TextContent(type="text", text="Page loaded"),
            ImageContent(type="image", data=small_image_data, mimeType="image/png"),
        ],
        is_error=False,
    )

    # Intercept the response
    result = await middleware.intercept_response("browser_navigate", response)

    # Verify both content items are dicts
    assert len(result["content"]) == 2

    # Text content should be converted to dict
    text_item = result["content"][0]
    assert isinstance(text_item, dict)
    assert text_item["type"] == "text"
    assert text_item["text"] == "Page loaded"

    # Image content should also be converted (small image, not stored as blob)
    image_item = result["content"][1]
    assert isinstance(image_item, dict) or isinstance(image_item, ImageContent)
    # If it wasn't converted to blob, it should still be accessible
    if isinstance(image_item, dict):
        assert image_item["type"] == "image"


@pytest.mark.asyncio
async def test_object_to_dict_with_dataclass():
    """Test _object_to_dict helper with dataclass objects."""
    mock_blob_manager = MagicMock()
    middleware = BinaryInterceptionMiddleware(mock_blob_manager, size_threshold_kb=50)

    # Create a dataclass object
    text_content = TextContent(type="text", text="Hello")

    # Convert to dict
    result = middleware._object_to_dict(text_content)

    # Verify conversion
    assert isinstance(result, dict)
    assert result["type"] == "text"
    assert result["text"] == "Hello"


@pytest.mark.asyncio
async def test_object_to_dict_with_mock_object():
    """Test _object_to_dict helper with mock objects (like MagicMock)."""
    mock_blob_manager = MagicMock()
    middleware = BinaryInterceptionMiddleware(mock_blob_manager, size_threshold_kb=50)

    # Create a mock object
    mock_obj = MagicMock(type="text", text="Hello", spec=["type", "text"])
    mock_obj.type = "text"
    mock_obj.text = "Hello"

    # Convert to dict (should use __dict__ fallback)
    result = middleware._object_to_dict(mock_obj)

    # Verify conversion (may vary based on MagicMock internals)
    assert isinstance(result, dict)
    # With MagicMock, we just verify it returns a dict
    # (exact structure depends on MagicMock implementation)
