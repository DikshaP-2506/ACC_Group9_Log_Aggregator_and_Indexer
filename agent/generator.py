import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import random
import time
from typing import Dict, List, Optional

from agent.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [generator] %(message)s"
)
logger = logging.getLogger(__name__)

SAMPLE_MESSAGES: Dict[str, List[Dict[str, any]]] = {
    "INFO": [
        {"msg": "User authentication successful for user_{user_id}", "meta": {"event": "auth_success"}},
        {"msg": "HTTP GET /api/v1/products completed with 200 OK", "meta": {"endpoint": "/api/v1/products", "status": 200}},
        {"msg": "Payment processed successfully for order_{order_id}", "meta": {"event": "payment_cleared", "amount": 89.99}},
        {"msg": "Cache hit for key session:{session_id}", "meta": {"cache": "redis", "hit": True}},
        {"msg": "Background sync job completed in 1.2s", "meta": {"job": "inventory_sync", "duration_ms": 1200}},
        {"msg": "Service health check passed. Heartbeat acknowledged.", "meta": {"status": "healthy"}},
    ],
    "WARNING": [
        {"msg": "High CPU utilization detected on node: 86.4%", "meta": {"metric": "cpu", "value": 86.4}},
        {"msg": "Database connection pool near capacity (18/20 connections)", "meta": {"pool": "postgres", "usage": "90%"}},
        {"msg": "Rate limit warning: client {ip} reached 90% of quota", "meta": {"client_ip": "192.168.1.105"}},
        {"msg": "Slow database query detected: SELECT * FROM orders took 2.4s", "meta": {"latency_ms": 2400}},
        {"msg": "Retry attempt 2/3 for dispatching webhook to endpoint", "meta": {"attempt": 2}},
    ],
    "ERROR": [
        {"msg": "Database connection timeout connecting to replica host", "meta": {"error": "TimeoutError", "port": 5432}},
        {"msg": "Payment gateway rejected transaction for order_{order_id}: Insufficient funds", "meta": {"gateway": "stripe", "code": "card_declined"}},
        {"msg": "Unhandled exception in OrderController: KeyError 'customer_id'", "meta": {"trace_id": "trc_9921"}},
        {"msg": "Failed to write payload to disk buffer: No space left on device", "meta": {"disk": "/dev/sda1"}},
        {"msg": "Downstream service inventory-service unreachable (503 Service Unavailable)", "meta": {"service": "inventory-service"}},
    ]
}

LEVEL_WEIGHTS = ["INFO"] * 6 + ["WARNING"] * 3 + ["ERROR"] * 2


def generate_single_log(source: str) -> str:
    """Generate a single structured log line as a JSON string."""
    level = random.choice(LEVEL_WEIGHTS)
    template = random.choice(SAMPLE_MESSAGES[level])

    user_id = random.randint(100, 999)
    order_id = random.randint(10000, 99999)
    session_id = f"sess_{random.randint(1000, 9999)}"
    ip = f"192.168.1.{random.randint(10, 250)}"

    message = template["msg"].format(
        user_id=user_id,
        order_id=order_id,
        session_id=session_id,
        ip=ip
    )

    metadata = dict(template.get("meta", {}))
    metadata["source_host"] = source
    metadata["pid"] = os.getpid()

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "source": source,
        "message": message,
        "metadata": metadata
    }

    return json.dumps(log_entry)


def run_generator(
    source: str,
    output_path: Path,
    count: Optional[int] = None,
    interval: float = 1.0
) -> None:
    """Continuously append generated log events to the target file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Starting log generator for source '{source}' -> writing to '{output_path}'")

    generated = 0
    try:
        while True:
            log_line = generate_single_log(source)
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
                f.flush()

            generated += 1
            logger.info(f"[{source}] Generated log #{generated}: {log_line[:80]}...")

            if count is not None and generated >= count:
                logger.info(f"Reached targeted log count ({count}). Generator stopped.")
                break

            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info(f"Log generator for '{source}' stopped by user.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic Log Generator for Group9 Log Aggregator")
    parser.add_argument("--source", type=str, default=config.source, help="Source identifier (e.g. server-1, server-2)")
    parser.add_argument("--output", type=str, default=str(config.log_file_path), help="Output log file path")
    parser.add_argument("--count", type=int, default=None, help="Number of logs to generate (omit for continuous)")
    parser.add_argument("--interval", type=float, default=1.0, help="Interval in seconds between logs")

    args = parser.parse_args()
    run_generator(
        source=args.source,
        output_path=Path(args.output),
        count=args.count,
        interval=args.interval
    )


if __name__ == "__main__":
    main()
