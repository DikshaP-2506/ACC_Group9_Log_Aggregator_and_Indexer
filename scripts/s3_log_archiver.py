#!/usr/bin/env python3
"""
S3 Log Archival & Cold-Storage Script for Group9-Log-Aggregator.

Compresses historical application logs and archived Elasticsearch documents,
uploads them to an Amazon S3 cold storage bucket with AES256 server-side encryption,
and cleans up archived records.

Supports:
- Local historical log file archival (--log-dir)
- Elasticsearch historical document offloading (--from-es)
- Dry-run mode (--dry-run) for safe validation
- Date-based S3 partitioning: s3://<bucket>/archives/YYYY/MM/DD/<filename>.gz
"""

import argparse
from datetime import datetime, timezone, timedelta
import gzip
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None  # Handled gracefully if executed without boto3

try:
    from elasticsearch import Elasticsearch
except ImportError:
    Elasticsearch = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("s3_log_archiver")


class S3LogArchiver:
    """Manages compression, verification, and S3 cold storage uploads."""

    def __init__(
        self,
        bucket_name: str,
        region_name: str = "us-east-1",
        retention_days: int = 7,
        dry_run: bool = False,
        s3_client: Optional[Any] = None
    ) -> None:
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.retention_days = retention_days
        self.dry_run = dry_run
        self._s3_client = s3_client

    @property
    def s3(self) -> Any:
        """Lazy-loaded or injected Boto3 S3 client."""
        if self._s3_client is None:
            if boto3 is None:
                raise RuntimeError("boto3 is not installed. Run 'pip install boto3' to enable S3 archival.")
            self._s3_client = boto3.client("s3", region_name=self.region_name)
        return self._s3_client

    def is_file_eligible(self, file_path: Path, cutoff_time: datetime) -> bool:
        """Determines if a local log file is older than the retention threshold."""
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
            return mtime < cutoff_time
        except Exception as exc:
            logger.warning(f"Could not stat file {file_path}: {exc}")
            return False

    def compress_file(self, source_path: Path, destination_path: Path) -> int:
        """Compresses a file using gzip. Returns compressed byte size."""
        with open(source_path, "rb") as f_in, gzip.open(destination_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        return destination_path.stat().st_size

    def upload_to_s3(self, local_path: Path, s3_key: str) -> bool:
        """Uploads a compressed file to S3 with AES256 server-side encryption."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would upload '{local_path}' -> 's3://{self.bucket_name}/{s3_key}'")
            return True

        try:
            logger.info(f"Uploading '{local_path.name}' to 's3://{self.bucket_name}/{s3_key}'...")
            self.s3.upload_file(
                Filename=str(local_path),
                Bucket=self.bucket_name,
                Key=s3_key,
                ExtraArgs={
                    "ServerSideEncryption": "AES256",
                    "ContentType": "application/gzip",
                    "Metadata": {
                        "archived_at": datetime.now(timezone.utc).isoformat(),
                        "tool": "Group9-S3LogArchiver"
                    }
                }
            )

            # Verify upload exists
            self.s3.head_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Verified successful upload for s3://{self.bucket_name}/{s3_key}")
            return True
        except (BotoCoreError, ClientError) as exc:
            logger.error(f"Failed to upload {local_path} to S3: {exc}")
            return False

    def archive_local_logs(self, log_dir: Path) -> Dict[str, Any]:
        """Scans, compresses, and archives eligible local .log files."""
        if not log_dir.exists():
            logger.warning(f"Log directory '{log_dir}' does not exist.")
            return {"archived": 0, "bytes": 0, "skipped": 0, "errors": 0}

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        logger.info(
            f"Scanning '{log_dir}' for logs older than {self.retention_days} days "
            f"(cutoff: {cutoff.isoformat()}). Dry-run: {self.dry_run}"
        )

        archived_count = 0
        total_compressed_bytes = 0
        skipped_count = 0
        error_count = 0

        for log_file in log_dir.glob("*.log"):
            if not self.is_file_eligible(log_file, cutoff):
                skipped_count += 1
                continue

            # Format partitioned S3 key: archives/raw-logs/YYYY/MM/DD/<name>.gz
            now = datetime.now(timezone.utc)
            date_prefix = now.strftime("%Y/%m/%d")
            s3_key = f"archives/raw-logs/{date_prefix}/{log_file.name}.gz"

            with tempfile.NamedTemporaryFile(suffix=".gz", delete=False) as tmp_gz:
                tmp_path = Path(tmp_gz.name)

            try:
                compressed_size = self.compress_file(log_file, tmp_path)
                success = self.upload_to_s3(tmp_path, s3_key)

                if success:
                    archived_count += 1
                    total_compressed_bytes += compressed_size
                    if not self.dry_run:
                        # Clean up original local file and matching offset
                        log_file.unlink(missing_ok=True)
                        offset_file = Path(str(log_file) + ".offset")
                        offset_file.unlink(missing_ok=True)
                        logger.info(f"Removed archived raw file: {log_file}")
                else:
                    error_count += 1
            except Exception as exc:
                logger.error(f"Error archiving {log_file}: {exc}")
                error_count += 1
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

        return {
            "archived": archived_count,
            "bytes": total_compressed_bytes,
            "skipped": skipped_count,
            "errors": error_count
        }

    def archive_elasticsearch_logs(
        self,
        es_url: str = "http://localhost:9200",
        index_name: str = "logs",
        batch_size: int = 500
    ) -> Dict[str, Any]:
        """Queries historical logs from Elasticsearch, archives to S3, and removes them from the active index."""
        if Elasticsearch is None:
            raise RuntimeError("elasticsearch package is required for ES archival.")

        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        logger.info(
            f"Querying Elasticsearch index '{index_name}' for records prior to {cutoff}... "
            f"(Dry-run: {self.dry_run})"
        )

        es = Elasticsearch(hosts=[es_url], request_timeout=30)
        query = {
            "bool": {
                "filter": [
                    {"range": {"timestamp": {"lt": cutoff}}}
                ]
            }
        }

        # Check document count
        count_res = es.count(index=index_name, query=query)
        total_docs = count_res.get("count", 0)

        if total_docs == 0:
            logger.info("No Elasticsearch documents matched the historical retention threshold.")
            return {"archived_docs": 0, "s3_key": None}

        logger.info(f"Found {total_docs} historical documents eligible for cold storage.")

        if self.dry_run:
            logger.info(f"[DRY-RUN] Would export and delete {total_docs} documents from ES index '{index_name}'.")
            return {"archived_docs": total_docs, "s3_key": "dry-run-preview"}

        # Export documents to compressed JSON Lines
        now = datetime.now(timezone.utc)
        s3_key = f"archives/elasticsearch/{now.strftime('%Y/%m/%d')}/es-logs-{int(now.timestamp())}.jsonl.gz"

        with tempfile.NamedTemporaryFile(suffix=".jsonl.gz", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            with gzip.open(tmp_path, "wt", encoding="utf-8") as gz_out:
                search_res = es.search(
                    index=index_name,
                    query=query,
                    size=batch_size,
                    scroll="2m"
                )
                scroll_id = search_res.get("_scroll_id")
                hits = search_res.get("hits", {}).get("hits", [])

                while hits:
                    for hit in hits:
                        gz_out.write(json.dumps(hit.get("_source", {})) + "\n")

                    if not scroll_id:
                        break
                    scroll_res = es.scroll(scroll_id=scroll_id, scroll="2m")
                    scroll_id = scroll_res.get("_scroll_id")
                    hits = scroll_res.get("hits", {}).get("hits", [])

                if scroll_id:
                    es.clear_scroll(scroll_id=scroll_id)

            # Upload archive to S3
            upload_success = self.upload_to_s3(tmp_path, s3_key)
            if not upload_success:
                raise RuntimeError("Failed to verify S3 upload of exported documents.")

            # Purge archived documents from Elasticsearch
            logger.info(f"Deleting {total_docs} archived records from Elasticsearch...")
            del_res = es.delete_by_query(
                index=index_name,
                query=query,
                wait_for_completion=True,
                conflicts="proceed"
            )
            deleted_count = del_res.get("deleted", 0)
            logger.info(f"Successfully purged {deleted_count} documents from active index '{index_name}'.")

            return {"archived_docs": total_docs, "s3_key": s3_key, "deleted_docs": deleted_count}
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive historical logs to Amazon S3 cold storage.")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET_NAME", ""), help="Target S3 Bucket Name")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"), help="AWS Region (default: us-east-1)")
    parser.add_argument("--retention-days", type=int, default=int(os.getenv("LOG_RETENTION_DAYS", "7")), help="Retention threshold in days")
    parser.add_argument("--log-dir", default=os.getenv("LOG_DIR", "logs"), help="Path to local logs directory")
    parser.add_argument("--from-es", action="store_true", help="Also archive historical documents directly from Elasticsearch")
    parser.add_argument("--es-url", default=os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"), help="Elasticsearch cluster URL")
    parser.add_argument("--es-index", default=os.getenv("LOG_INDEX_NAME", "logs"), help="Elasticsearch index name")
    parser.add_argument("--dry-run", action="store_true", help="Simulate archival without modifying S3, disk, or Elasticsearch")

    args = parser.parse_args()

    if not args.bucket:
        logger.error("S3 Bucket Name is required. Set S3_BUCKET_NAME environment variable or pass --bucket <name>.")
        sys.exit(1)

    archiver = S3LogArchiver(
        bucket_name=args.bucket,
        region_name=args.region,
        retention_days=args.retention_days,
        dry_run=args.dry_run
    )

    logger.info("=== Starting Group9 S3 Log Archival Job ===")
    local_stats = archiver.archive_local_logs(Path(args.log_dir))
    logger.info(f"Local files summary: {local_stats}")

    if args.from_es:
        try:
            es_stats = archiver.archive_elasticsearch_logs(
                es_url=args.es_url,
                index_name=args.es_index
            )
            logger.info(f"Elasticsearch offload summary: {es_stats}")
        except Exception as exc:
            logger.error(f"Elasticsearch archival failed: {exc}")
            sys.exit(1)

    logger.info("=== Archival Job Completed Successfully ===")


if __name__ == "__main__":
    main()
