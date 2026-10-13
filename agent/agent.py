import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from agent.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [agent] %(message)s"
)
logger = logging.getLogger(__name__)


class LogAgent:
    """Monitors local log file, tracks byte offsets, and ships logs to the aggregator with retries."""

    def __init__(
        self,
        source: str = config.source,
        log_file_path: Path = config.log_file_path,
        state_file_path: Optional[Path] = None,
        aggregator_url: str = config.aggregator_url,
        poll_interval: float = config.poll_interval,
        max_retries: int = config.max_retries,
        backoff_factor: float = config.backoff_factor,
        request_timeout: float = config.request_timeout
    ) -> None:
        self.source = source
        self.log_file_path = Path(log_file_path)
        self.state_file_path = Path(state_file_path) if state_file_path else Path(str(self.log_file_path) + ".offset")
        self.aggregator_url = aggregator_url
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.request_timeout = request_timeout

        self._http_client = httpx.Client(timeout=self.request_timeout)

    def load_offset(self) -> int:
        """Load last acknowledged byte offset from state file."""
        if self.state_file_path.exists():
            try:
                with open(self.state_file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content.isdigit():
                        return int(content)
            except Exception as exc:
                logger.warning(f"Could not read offset file '{self.state_file_path}': {exc}. Starting from 0.")
        return 0

    def save_offset(self, offset: int) -> None:
        """Atomically persist acknowledged byte offset."""
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.state_file_path.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(str(offset))
                f.flush()
            temp_file.replace(self.state_file_path)
        except Exception as exc:
            logger.error(f"Failed to persist state offset to '{self.state_file_path}': {exc}")

    def parse_log_line(self, line: str) -> Dict[str, Any]:
        """Parse raw text or JSON log line into valid LogCreate schema."""
        clean_line = line.strip()
        if not clean_line:
            return {}

        # 1. Attempt JSON parsing
        try:
            parsed = json.loads(clean_line)
            if isinstance(parsed, dict) and "message" in parsed:
                return {
                    "id": parsed.get("id"),
                    "timestamp": parsed.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    "level": parsed.get("level", "INFO"),
                    "source": parsed.get("source", self.source),
                    "message": str(parsed["message"]),
                    "metadata": parsed.get("metadata", {})
                }
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. Fallback: Parse plaintext string
        level = "INFO"
        upper = clean_line.upper()
        if "ERROR" in upper or "EXCEPTION" in upper or "FATAL" in upper:
            level = "ERROR"
        elif "WARN" in upper:
            level = "WARNING"
        elif "DEBUG" in upper:
            level = "DEBUG"

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "source": self.source,
            "message": clean_line,
            "metadata": {"format": "unstructured_text"}
        }

    def ship_log_entry(self, payload: Dict[str, Any]) -> bool:
        """Send log entry to FastAPI aggregator with timeout handling and exponential backoff retry."""
        for attempt in range(self.max_retries + 1):
            try:
                response = self._http_client.post(self.aggregator_url, json=payload)

                # HTTP 201 Created: successfully ingested
                if response.status_code == 201:
                    logger.debug(f"[{self.source}] Log acknowledged: {response.json().get('id')}")
                    return True

                # HTTP 409 Conflict: already ingested previously (duplicate)
                if response.status_code == 409:
                    logger.info(f"[{self.source}] Duplicate log entry already acknowledged by aggregator. Advancing offset.")
                    return True

                # Client error (e.g. 422 Unprocessable Entity): unrecoverable validation error
                if 400 <= response.status_code < 500:
                    logger.warning(
                        f"[{self.source}] Client validation error {response.status_code}: {response.text}. Skipping line."
                    )
                    return True

                # Server error (5xx): Retry
                logger.warning(
                    f"[{self.source}] Server returned {response.status_code} on attempt {attempt + 1}/{self.max_retries + 1}. Retrying..."
                )

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                logger.warning(
                    f"[{self.source}] Network failure '{type(exc).__name__}: {exc}' on attempt {attempt + 1}/{self.max_retries + 1}."
                )

            if attempt < self.max_retries:
                sleep_time = self.backoff_factor * (2 ** attempt)
                logger.info(f"[{self.source}] Backing off for {sleep_time:.2f}s before retry...")
                time.sleep(sleep_time)

        logger.error(f"[{self.source}] Max retries exceeded for log shipping. Offset will NOT be advanced.")
        return False

    def process_available_logs(self) -> int:
        """Read and ship newly appended log lines from the current offset."""
        if not self.log_file_path.exists():
            return 0

        current_offset = self.load_offset()
        file_size = self.log_file_path.stat().st_size

        # If file was truncated/rotated, reset offset
        if file_size < current_offset:
            logger.info(f"[{self.source}] Log file rotated or truncated. Resetting offset to 0.")
            current_offset = 0

        processed_count = 0
        with open(self.log_file_path, "r", encoding="utf-8") as f:
            f.seek(current_offset)

            while True:
                line_start_pos = f.tell()
                line = f.readline()

                # Reached end of file for now
                if not line:
                    break

                # If line is incomplete (e.g., in middle of write), rewind and wait
                if not line.endswith("\n") and f.tell() == file_size:
                    f.seek(line_start_pos)
                    break

                payload = self.parse_log_line(line)
                if not payload:
                    # Blank line: advance offset
                    current_offset = f.tell()
                    self.save_offset(current_offset)
                    continue

                shipped = self.ship_log_entry(payload)
                if shipped:
                    current_offset = f.tell()
                    self.save_offset(current_offset)
                    processed_count += 1
                else:
                    # Delivery failed: stop processing to retry on next cycle without losing logs
                    break

        return processed_count

    def run(self, run_once: bool = False) -> None:
        """Start agent polling loop."""
        logger.info(
            f"Starting Log Agent for source '{self.source}' monitoring '{self.log_file_path}'. "
            f"Target aggregator: {self.aggregator_url}"
        )

        try:
            while True:
                count = self.process_available_logs()
                if count > 0:
                    logger.info(f"[{self.source}] Shipped {count} log entries to aggregator.")

                if run_once:
                    break

                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            logger.info(f"Log Agent for '{self.source}' stopped by user.")
        finally:
            self._http_client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Log Shipper Agent for Group9 Log Aggregator")
    parser.add_argument("--source", type=str, default=config.source, help="Source identifier (e.g. server-1, server-2)")
    parser.add_argument("--file", type=str, default=str(config.log_file_path), help="Path to monitored log file")
    parser.add_argument("--state-file", type=str, default=None, help="Path to offset state file (defaults to <file>.offset)")
    parser.add_argument("--aggregator-url", type=str, default=config.aggregator_url, help="Aggregator ingestion URL")
    parser.add_argument("--poll-interval", type=float, default=config.poll_interval, help="Poll interval in seconds")
    parser.add_argument("--once", action="store_true", help="Run a single pass and exit (useful for testing)")

    args = parser.parse_args()

    agent = LogAgent(
        source=args.source,
        log_file_path=Path(args.file),
        state_file_path=Path(args.state_file) if args.state_file else None,
        aggregator_url=args.aggregator_url,
        poll_interval=args.poll_interval
    )
    agent.run(run_once=args.once)


if __name__ == "__main__":
    main()
