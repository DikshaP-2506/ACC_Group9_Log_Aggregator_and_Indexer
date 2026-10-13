from datetime import datetime, timezone, timedelta
import gzip
import os
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from scripts.s3_log_archiver import S3LogArchiver


def test_compress_file_and_decompress():
    """Verify gzip compression produces valid compressed data that matches original text."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "test.log"
        dst = Path(tmpdir) / "test.log.gz"
        original_content = b"2026-10-12 INFO [server-1]: Database connection initialized successfully.\n"
        src.write_bytes(original_content)

        archiver = S3LogArchiver(bucket_name="test-bucket", dry_run=False)
        compressed_size = archiver.compress_file(src, dst)

        assert dst.exists()
        assert compressed_size > 0

        # Read back decompressed
        with gzip.open(dst, "rb") as gz_in:
            decompressed = gz_in.read()
        assert decompressed == original_content


def test_is_file_eligible_by_retention_days():
    """Verify file modification time against retention cutoff."""
    with tempfile.TemporaryDirectory() as tmpdir:
        old_file = Path(tmpdir) / "old.log"
        new_file = Path(tmpdir) / "new.log"

        old_file.write_text("old log")
        new_file.write_text("new log")

        now = datetime.now(timezone.utc)
        ten_days_ago = (now - timedelta(days=10)).timestamp()
        one_day_ago = (now - timedelta(days=1)).timestamp()

        # Update modification times
        os.utime(old_file, (ten_days_ago, ten_days_ago))
        os.utime(new_file, (one_day_ago, one_day_ago))

        archiver = S3LogArchiver(bucket_name="test-bucket", retention_days=7)
        cutoff = now - timedelta(days=7)

        assert archiver.is_file_eligible(old_file, cutoff) is True
        assert archiver.is_file_eligible(new_file, cutoff) is False


def test_upload_to_s3_calls_boto3_with_encryption():
    """Verify upload_to_s3 uses AES256 server-side encryption and checks head_object."""
    mock_s3 = MagicMock()
    archiver = S3LogArchiver(bucket_name="my-archive-bucket", dry_run=False, s3_client=mock_s3)

    with tempfile.NamedTemporaryFile(suffix=".gz") as tmp:
        local_path = Path(tmp.name)
        success = archiver.upload_to_s3(local_path, "archives/raw-logs/2026/10/12/server-1.log.gz")

        assert success is True
        mock_s3.upload_file.assert_called_once()
        _, kwargs = mock_s3.upload_file.call_args
        assert kwargs["Bucket"] == "my-archive-bucket"
        assert kwargs["Key"] == "archives/raw-logs/2026/10/12/server-1.log.gz"
        assert kwargs["ExtraArgs"]["ServerSideEncryption"] == "AES256"
        mock_s3.head_object.assert_called_once_with(
            Bucket="my-archive-bucket",
            Key="archives/raw-logs/2026/10/12/server-1.log.gz"
        )


def test_dry_run_does_not_call_s3_or_delete_files():
    """Verify dry-run mode previews actions without invoking S3 APIs or unlinking files."""
    mock_s3 = MagicMock()
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        old_file = log_dir / "old_service.log"
        old_file.write_text("historical error data")

        ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
        os.utime(old_file, (ten_days_ago, ten_days_ago))

        archiver = S3LogArchiver(
            bucket_name="test-bucket",
            retention_days=7,
            dry_run=True,
            s3_client=mock_s3
        )

        stats = archiver.archive_local_logs(log_dir)

        assert stats["archived"] == 1
        assert stats["errors"] == 0
        # File should NOT be deleted in dry run
        assert old_file.exists()
        # S3 upload should NOT be called in dry run
        mock_s3.upload_file.assert_not_called()


def test_archive_local_logs_cleans_up_after_upload():
    """Verify that successful non-dry-run upload removes old raw file and matching offset."""
    mock_s3 = MagicMock()
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        old_file = log_dir / "service.log"
        old_offset = log_dir / "service.log.offset"
        recent_file = log_dir / "recent.log"

        old_file.write_text("old entries")
        old_offset.write_text("123")
        recent_file.write_text("recent entries")

        now = datetime.now(timezone.utc)
        ten_days_ago = (now - timedelta(days=10)).timestamp()
        os.utime(old_file, (ten_days_ago, ten_days_ago))

        archiver = S3LogArchiver(
            bucket_name="test-bucket",
            retention_days=7,
            dry_run=False,
            s3_client=mock_s3
        )

        stats = archiver.archive_local_logs(log_dir)

        assert stats["archived"] == 1
        assert stats["skipped"] == 1
        # Old file and offset should be removed
        assert not old_file.exists()
        assert not old_offset.exists()
        # Recent file should remain
        assert recent_file.exists()
