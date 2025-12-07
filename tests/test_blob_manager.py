"""
Tests for blob storage manager
"""

import base64
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from playwright_proxy_mcp.playwright.blob_manager import PlaywrightBlobManager


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def blob_config(temp_storage):
    """Create test blob configuration."""
    return {
        "storage_root": temp_storage,
        "max_size_mb": 10,
        "ttl_hours": 24,
        "size_threshold_kb": 50,
        "cleanup_interval_minutes": 60,
    }


class TestPlaywrightBlobManager:
    """Tests for PlaywrightBlobManager."""

    def test_init(self, blob_config):
        """Test blob manager initialization."""
        manager = PlaywrightBlobManager(blob_config)

        assert manager.config == blob_config
        assert manager.storage is not None
        assert Path(blob_config["storage_root"]).exists()

    @pytest.mark.asyncio
    async def test_store_base64_data_simple(self, blob_config):
        """Test storing simple base64 data."""
        manager = PlaywrightBlobManager(blob_config)

        # Create test data
        test_data = b"Hello, World!"
        base64_data = base64.b64encode(test_data).decode("utf-8")

        # Mock the storage upload
        with patch.object(manager.storage, "upload_blob") as mock_upload:
            mock_upload.return_value = {
                "blob_id": "blob_test123",
                "created_at": "2024-01-01T00:00:00Z",
            }

            result = await manager.store_base64_data(
                base64_data=base64_data, filename="test.txt", tags=["test"]
            )

            assert result["blob_id"] == "blob_test123"
            assert result["size_bytes"] == len(test_data)
            assert "created_at" in result
            assert "expires_at" in result

            # Verify upload was called with binary data
            mock_upload.assert_called_once()
            call_args = mock_upload.call_args
            assert call_args[1]["data"] == test_data
            assert call_args[1]["filename"] == "test.txt"
            assert call_args[1]["tags"] == ["test"]

    @pytest.mark.asyncio
    async def test_store_base64_data_with_data_uri(self, blob_config):
        """Test storing base64 data with data URI prefix."""
        manager = PlaywrightBlobManager(blob_config)

        # Create test data with data URI
        test_data = b"\x89PNG\r\n\x1a\n"  # PNG header
        base64_data = base64.b64encode(test_data).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_data}"

        with patch.object(manager.storage, "upload_blob") as mock_upload:
            mock_upload.return_value = {
                "blob_id": "blob_test123",
                "created_at": "2024-01-01T00:00:00Z",
            }

            result = await manager.store_base64_data(
                base64_data=data_uri, filename="test.png"
            )

            assert result["mime_type"] == "image/png"
            assert result["size_bytes"] == len(test_data)

            # Verify binary data was extracted correctly
            call_args = mock_upload.call_args
            assert call_args[1]["data"] == test_data

    @pytest.mark.asyncio
    async def test_store_base64_data_failure(self, blob_config):
        """Test handling of storage failure."""
        manager = PlaywrightBlobManager(blob_config)

        with patch.object(
            manager.storage, "upload_blob", side_effect=Exception("Storage full")
        ):
            with pytest.raises(ValueError, match="Failed to store blob"):
                await manager.store_base64_data("invalid", "test.bin")

    @pytest.mark.asyncio
    async def test_retrieve_blob(self, blob_config):
        """Test blob retrieval."""
        manager = PlaywrightBlobManager(blob_config)

        test_data = b"test binary data"

        # Mock the entire storage object to provide get_blob method
        mock_storage = Mock()
        mock_storage.get_blob = Mock(return_value=test_data)
        manager.storage = mock_storage

        result = await manager.retrieve_blob("blob://test-123.png")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_retrieve_blob_strips_prefix(self, blob_config):
        """Test that blob:// prefix is stripped."""
        manager = PlaywrightBlobManager(blob_config)

        # Mock the entire storage object
        mock_storage = Mock()
        mock_storage.get_blob = Mock(return_value=b"data")
        manager.storage = mock_storage

        await manager.retrieve_blob("blob://test-123.png")
        mock_storage.get_blob.assert_called_once_with("test-123.png")

    @pytest.mark.asyncio
    async def test_retrieve_blob_not_found(self, blob_config):
        """Test retrieval of nonexistent blob."""
        manager = PlaywrightBlobManager(blob_config)

        # Mock the entire storage object
        mock_storage = Mock()
        mock_storage.get_blob = Mock(side_effect=Exception("Not found"))
        manager.storage = mock_storage

        with pytest.raises(ValueError, match="Blob not found"):
            await manager.retrieve_blob("blob://nonexistent.png")

    @pytest.mark.asyncio
    async def test_get_blob_metadata(self, blob_config):
        """Test getting blob metadata."""
        manager = PlaywrightBlobManager(blob_config)

        test_metadata = {
            "mime_type": "image/png",
            "size_bytes": 1024,
            "created_at": "2024-01-01T00:00:00Z",
        }

        with patch.object(
            manager.storage, "get_metadata", return_value=test_metadata
        ):
            result = await manager.get_blob_metadata("blob://test.png")
            assert result == test_metadata

    @pytest.mark.asyncio
    async def test_get_blob_metadata_strips_prefix(self, blob_config):
        """Test that blob:// prefix is stripped when getting metadata."""
        manager = PlaywrightBlobManager(blob_config)

        with patch.object(manager.storage, "get_metadata", return_value={}) as mock_get:
            await manager.get_blob_metadata("blob://test-123.png")
            mock_get.assert_called_once_with("test-123.png")

    @pytest.mark.asyncio
    async def test_get_blob_metadata_not_found(self, blob_config):
        """Test getting metadata for nonexistent blob."""
        manager = PlaywrightBlobManager(blob_config)

        with patch.object(
            manager.storage, "get_metadata", side_effect=Exception("Not found")
        ):
            with pytest.raises(ValueError, match="Blob not found"):
                await manager.get_blob_metadata("blob://nonexistent.png")

    @pytest.mark.asyncio
    async def test_list_blobs(self, blob_config, temp_storage):
        """Test listing blobs."""
        manager = PlaywrightBlobManager(blob_config)

        # Create fake blob files
        blob_path = Path(temp_storage)
        (blob_path / "blob_1").touch()
        (blob_path / "blob_2").touch()

        test_metadata = {
            "mime_type": "image/png",
            "size_bytes": 1024,
            "created_at": "2024-01-01T00:00:00Z",
            "expires_at": "2024-01-02T00:00:00Z",
            "tags": ["test"],
        }

        with patch.object(
            manager.storage, "get_metadata", return_value=test_metadata
        ):
            result = await manager.list_blobs()

            assert len(result) == 2
            assert all("blob_id" in blob for blob in result)
            assert all(blob["blob_id"].startswith("blob://") for blob in result)

    @pytest.mark.asyncio
    async def test_list_blobs_with_mime_filter(self, blob_config, temp_storage):
        """Test listing blobs with MIME type filter."""
        manager = PlaywrightBlobManager(blob_config)

        blob_path = Path(temp_storage)
        (blob_path / "blob_1").touch()
        (blob_path / "blob_2").touch()

        metadata_png = {"mime_type": "image/png", "tags": []}
        metadata_pdf = {"mime_type": "application/pdf", "tags": []}

        def get_metadata_side_effect(blob_id):
            if blob_id == "blob_1":
                return metadata_png
            else:
                return metadata_pdf

        with patch.object(
            manager.storage, "get_metadata", side_effect=get_metadata_side_effect
        ):
            result = await manager.list_blobs(mime_type="image/png")

            assert len(result) == 1
            assert result[0]["mime_type"] == "image/png"

    @pytest.mark.asyncio
    async def test_list_blobs_with_tags_filter(self, blob_config, temp_storage):
        """Test listing blobs with tags filter."""
        manager = PlaywrightBlobManager(blob_config)

        blob_path = Path(temp_storage)
        (blob_path / "blob_1").touch()
        (blob_path / "blob_2").touch()

        metadata_with_tag = {"mime_type": "image/png", "tags": ["screenshot"]}
        metadata_without_tag = {"mime_type": "image/png", "tags": ["other"]}

        def get_metadata_side_effect(blob_id):
            if blob_id == "blob_1":
                return metadata_with_tag
            else:
                return metadata_without_tag

        with patch.object(
            manager.storage, "get_metadata", side_effect=get_metadata_side_effect
        ):
            result = await manager.list_blobs(tags=["screenshot"])

            assert len(result) == 1
            assert "screenshot" in result[0]["tags"]

    @pytest.mark.asyncio
    async def test_list_blobs_with_limit(self, blob_config, temp_storage):
        """Test listing blobs with limit."""
        manager = PlaywrightBlobManager(blob_config)

        blob_path = Path(temp_storage)
        for i in range(10):
            (blob_path / f"blob_{i}").touch()

        with patch.object(manager.storage, "get_metadata", return_value={"tags": []}):
            result = await manager.list_blobs(limit=5)

            assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_list_blobs_handles_errors(self, blob_config, temp_storage):
        """Test that list_blobs handles errors gracefully."""
        manager = PlaywrightBlobManager(blob_config)

        blob_path = Path(temp_storage)
        (blob_path / "blob_1").touch()

        with patch.object(
            manager.storage, "get_metadata", side_effect=Exception("Error")
        ):
            result = await manager.list_blobs()

            # Should return empty list on error
            assert result == []

    @pytest.mark.asyncio
    async def test_delete_blob(self, blob_config):
        """Test blob deletion."""
        manager = PlaywrightBlobManager(blob_config)

        with patch.object(manager.storage, "delete_blob") as mock_delete:
            result = await manager.delete_blob("blob://test.png")
            assert result is True
            mock_delete.assert_called_once_with("test.png")

    @pytest.mark.asyncio
    async def test_delete_blob_strips_prefix(self, blob_config):
        """Test that blob:// prefix is stripped when deleting."""
        manager = PlaywrightBlobManager(blob_config)

        with patch.object(manager.storage, "delete_blob") as mock_delete:
            await manager.delete_blob("blob://test-123.png")
            mock_delete.assert_called_once_with("test-123.png")

    @pytest.mark.asyncio
    async def test_delete_blob_failure(self, blob_config):
        """Test handling of deletion failure."""
        manager = PlaywrightBlobManager(blob_config)

        with patch.object(
            manager.storage, "delete_blob", side_effect=Exception("Delete error")
        ):
            result = await manager.delete_blob("blob://test.png")
            assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, blob_config):
        """Test cleanup of expired blobs."""
        manager = PlaywrightBlobManager(blob_config)

        # The function is imported inside cleanup_expired, so patch it at import location
        with patch(
            "mcp_mapped_resource_lib.maybe_cleanup_expired_blobs",
            return_value=5,
        ) as mock_cleanup:
            result = await manager.cleanup_expired()

            assert result == 5
            mock_cleanup.assert_called_once_with(blob_config["storage_root"])

    @pytest.mark.asyncio
    async def test_cleanup_expired_failure(self, blob_config):
        """Test handling of cleanup failure."""
        manager = PlaywrightBlobManager(blob_config)

        with patch(
            "mcp_mapped_resource_lib.maybe_cleanup_expired_blobs",
            side_effect=Exception("Cleanup error"),
        ):
            result = await manager.cleanup_expired()
            assert result == 0

    @pytest.mark.asyncio
    async def test_start_cleanup_task(self, blob_config):
        """Test starting periodic cleanup task."""
        manager = PlaywrightBlobManager(blob_config)

        assert manager._cleanup_task is None

        await manager.start_cleanup_task()

        assert manager._cleanup_task is not None
        assert not manager._cleanup_task.done()

        # Cleanup
        await manager.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_start_cleanup_task_already_running(self, blob_config):
        """Test starting cleanup task when already running."""
        manager = PlaywrightBlobManager(blob_config)

        await manager.start_cleanup_task()
        first_task = manager._cleanup_task

        # Try to start again
        await manager.start_cleanup_task()

        # Should still be the same task
        assert manager._cleanup_task == first_task

        # Cleanup
        await manager.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_stop_cleanup_task(self, blob_config):
        """Test stopping cleanup task."""
        manager = PlaywrightBlobManager(blob_config)

        await manager.start_cleanup_task()
        assert manager._cleanup_task is not None

        await manager.stop_cleanup_task()

        assert manager._cleanup_task is None

    @pytest.mark.asyncio
    async def test_stop_cleanup_task_not_running(self, blob_config):
        """Test stopping cleanup task when not running."""
        manager = PlaywrightBlobManager(blob_config)

        # Should not raise an error
        await manager.stop_cleanup_task()
        assert manager._cleanup_task is None
