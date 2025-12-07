"""
Binary interception middleware for playwright-mcp responses

Detects large binary data in tool responses and replaces it with
blob storage references to reduce token usage.
"""

import logging
import re
from typing import Any

from .blob_manager import PlaywrightBlobManager

logger = logging.getLogger(__name__)


class BinaryInterceptionMiddleware:
    """
    Intercepts playwright-mcp tool responses containing large binary data
    and replaces them with blob storage references.
    """

    # Tools that always produce binary data
    BINARY_TOOLS = {
        "playwright_screenshot",
        "playwright_pdf",
        "playwright_save_as_pdf",
    }

    # Tools that may produce binary data
    CONDITIONAL_BINARY_TOOLS = {
        "playwright_get_console",
        "playwright_download",
    }

    def __init__(
        self, blob_manager: PlaywrightBlobManager, size_threshold_kb: int = 50
    ) -> None:
        """
        Initialize middleware.

        Args:
            blob_manager: Blob storage manager instance
            size_threshold_kb: Size threshold in KB for blob storage (default: 50)
        """
        self.blob_manager = blob_manager
        self.size_threshold_bytes = size_threshold_kb * 1024

        logger.info(
            f"Binary interception middleware initialized (threshold: {size_threshold_kb}KB)"
        )

    async def intercept_response(
        self, tool_name: str, response: Any
    ) -> Any:
        """
        Intercept and potentially transform a tool response.

        Args:
            tool_name: Name of the tool that was called
            response: The response from the tool

        Returns:
            Potentially transformed response
        """
        # Only process dict responses
        if not isinstance(response, dict):
            return response

        # Check if this tool produces binary data
        should_check = (
            tool_name in self.BINARY_TOOLS
            or tool_name in self.CONDITIONAL_BINARY_TOOLS
        )

        if not should_check:
            return response

        # Look for base64 data in the response
        transformed = await self._transform_response_data(response, tool_name)

        return transformed

    async def _transform_response_data(
        self, data: dict[str, Any], tool_name: str
    ) -> dict[str, Any]:
        """
        Recursively transform base64 data in response.

        Args:
            data: Response data dictionary
            tool_name: Tool name for context

        Returns:
            Transformed data
        """
        result = {}

        for key, value in data.items():
            if isinstance(value, dict):
                # Recursively process nested dicts
                result[key] = await self._transform_response_data(value, tool_name)

            elif isinstance(value, str):
                # Check if this is base64 data
                if await self._should_store_as_blob(value):
                    # Store as blob and replace with reference
                    blob_info = await self._store_as_blob(value, key, tool_name)
                    result[key] = blob_info["blob_id"]

                    # Add metadata fields
                    result[f"{key}_size_kb"] = blob_info["size_bytes"] // 1024
                    result[f"{key}_mime_type"] = blob_info["mime_type"]
                    result[f"{key}_blob_retrieval_tool"] = "get_blob"
                    result[f"{key}_expires_at"] = blob_info["expires_at"]

                    logger.info(
                        f"Stored {key} as blob {blob_info['blob_id']} "
                        f"({blob_info['size_bytes']} bytes)"
                    )
                else:
                    result[key] = value

            else:
                result[key] = value

        return result

    async def _should_store_as_blob(self, value: str) -> bool:
        """
        Determine if a string value should be stored as a blob.

        Args:
            value: String value to check

        Returns:
            True if should be stored as blob
        """
        # Check for data URI pattern
        data_uri_match = re.match(r"data:([^;]+);base64,(.+)", value)
        if not data_uri_match:
            # Not a data URI, check if it's a large base64 string
            # (heuristic: long string with base64 characters)
            if len(value) < 100:
                return False

            # Check if it looks like base64
            if not re.match(r"^[A-Za-z0-9+/]+=*$", value):
                return False

        # Estimate size
        # Base64 encoding increases size by ~33%, so we reverse that
        if data_uri_match:
            base64_data = data_uri_match.group(2)
        else:
            base64_data = value

        estimated_binary_size = len(base64_data) * 3 // 4

        # Check against threshold
        return estimated_binary_size >= self.size_threshold_bytes

    async def _store_as_blob(
        self, base64_data: str, field_name: str, tool_name: str
    ) -> dict[str, Any]:
        """
        Store base64 data as a blob.

        Args:
            base64_data: Base64-encoded data (may include data URI)
            field_name: Field name from response
            tool_name: Tool name for context

        Returns:
            Blob information dict
        """
        # Generate filename based on tool and field
        extension = self._get_extension_from_data_uri(base64_data)
        filename = f"{tool_name}_{field_name}{extension}"

        # Store blob
        blob_info = await self.blob_manager.store_base64_data(
            base64_data=base64_data, filename=filename, tags=[tool_name, field_name]
        )

        return blob_info

    def _get_extension_from_data_uri(self, data: str) -> str:
        """
        Extract file extension from data URI MIME type.

        Args:
            data: Data URI or base64 string

        Returns:
            File extension (e.g., ".png")
        """
        # Check for data URI pattern
        match = re.match(r"data:([^;]+);base64,", data)
        if not match:
            return ".bin"

        mime_type = match.group(1)

        # Map common MIME types to extensions
        mime_to_ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
            "application/pdf": ".pdf",
            "video/webm": ".webm",
            "video/mp4": ".mp4",
            "application/x-tar": ".tar",
            "application/zip": ".zip",
        }

        return mime_to_ext.get(mime_type, ".bin")
