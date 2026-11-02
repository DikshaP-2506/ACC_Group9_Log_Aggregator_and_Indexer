import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import random
import time
from typing import Any, Dict, List, Optional

from agent.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [generator] %(message)s"
)
logger = logging.getLogger(__name__)

DOMAIN_TEMPLATES: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "fintech": {
        "INFO": [
            {"msg": "Payment processed successfully for order_{order_id} via Stripe", "meta": {"event": "payment_cleared", "amount": 89.99, "gateway": "stripe"}},
            {"msg": "ACH settlement batch cleared with Federal Reserve bank", "meta": {"batch_id": "ach-9912", "cleared_total": 45290.50}},
            {"msg": "Ledger double-entry reconciliation confirmed balanced", "meta": {"account": "escrow-01", "variance": 0.0}},
            {"msg": "Invoice #{order_id} generated and dispatched to billing customer", "meta": {"invoice_status": "sent"}},
        ],
        "WARNING": [
            {"msg": "Payment retry attempt 2/3 for invoice #{order_id}: Issuer network slow", "meta": {"attempt": 2, "gateway": "adyen"}},
            {"msg": "Fraud detection anomaly score elevated (0.74/1.0) for transaction #{order_id}", "meta": {"risk_score": 0.74, "rule": "velocity_check"}},
            {"msg": "Daily card transaction limit approaching 88% for merchant_{user_id}", "meta": {"merchant_id": "m-401"}},
        ],
        "ERROR": [
            {"msg": "Payment gateway rejected transaction for order_{order_id}: Insufficient funds", "meta": {"gateway": "stripe", "code": "card_declined"}},
            {"msg": "Payment gateway timeout: Connection to banking wire network failed after 5000ms", "meta": {"timeout_ms": 5000, "error": "GatewayTimeout"}},
            {"msg": "Cardholder verification failed: Expired 3D-Secure challenge token", "meta": {"security_level": "3DS2", "error": "AuthChallengeExpired"}},
        ]
    },
    "healthcare": {
        "INFO": [
            {"msg": "HL7 FHIR Patient Encounter record ingested for patient_{user_id}", "meta": {"standard": "FHIR_R4", "resource": "Encounter"}},
            {"msg": "Telehealth encrypted WebRTC consultation session established", "meta": {"session_id": "th-4402", "hipaa_compliant": True}},
            {"msg": "Automated lab diagnostic results synced with Central EHR repository", "meta": {"lab_code": "CBC-882", "status": "verified"}},
            {"msg": "Pharmacy e-prescription dispatched and signature verified", "meta": {"rx_id": "rx-1092", "dea_schedule": "VI"}},
        ],
        "WARNING": [
            {"msg": "Patient telemetry vitals warning: SpO2 dipped to 91% for bed_{user_id}", "meta": {"metric": "SpO2", "value": 91, "threshold": 92}},
            {"msg": "EHR medication interaction caution flagged: Warfarin + Aspirin duplicate protocol", "meta": {"severity": "moderate"}},
            {"msg": "Telehealth streaming bitrate dropped below HD threshold (650 kbps)", "meta": {"bitrate_kbps": 650}},
        ],
        "ERROR": [
            {"msg": "Critical ICU telemetry alert: Cardiac arrhythmia detected on patient_{user_id}", "meta": {"alert": "VTach", "ward": "ICU-North", "code_blue": False}},
            {"msg": "HL7 message parsing exception: Malformed MSH header segment in lab payload", "meta": {"error": "InvalidSegment", "segment": "MSH"}},
            {"msg": "HIPAA audit integrity failure: Unauthorized chart access attempt blocked for user_{user_id}", "meta": {"audit_event": "access_denied"}},
        ]
    },
    "ecommerce": {
        "INFO": [
            {"msg": "Cart checkout verified and order_{order_id} placed successfully", "meta": {"order_id": "ord-8832", "items_count": 3, "total": 142.50}},
            {"msg": "Warehouse stock level updated and cached in Redis buffer for SKU-{user_id}", "meta": {"sku": "SKU-7721", "quantity_delta": -1, "warehouse": "us-east-1"}},
            {"msg": "Package dispatched to carrier with tracking ID trk_{order_id}", "meta": {"carrier": "FedEx", "service": "Express"}},
            {"msg": "Catalog search index refreshed with 120 new product variants", "meta": {"indexed_count": 120}},
        ],
        "WARNING": [
            {"msg": "Low inventory alert: SKU-{user_id} inventory below restock threshold (4 units remaining)", "meta": {"remaining": 4, "threshold": 10}},
            {"msg": "Abandoned checkout detected for user_{user_id} with cart value $189.00", "meta": {"idle_minutes": 35}},
            {"msg": "Carrier API rate limit warning: 85% of shipping quota consumed", "meta": {"quota_used": "85%"}},
        ],
        "ERROR": [
            {"msg": "Downstream inventory-service unreachable (503 Service Unavailable)", "meta": {"service": "inventory-service", "status": 503}},
            {"msg": "Order cancellation failed: Order #{order_id} already locked in fulfillment stage", "meta": {"status": "in_fulfillment"}},
            {"msg": "Warehouse robotics picker communication timeout on bay 4B", "meta": {"bay": "4B", "error": "RobotTimeout"}},
        ]
    },
    "cybersecurity": {
        "INFO": [
            {"msg": "User authentication successful and JWT access token issued for user_{user_id}", "meta": {"auth_method": "oauth2_google", "token_type": "Bearer"}},
            {"msg": "Multi-factor authentication (TOTP) verified for session:{session_id}", "meta": {"mfa": "totp", "verified": True}},
            {"msg": "SSL/TLS automated certificate renewal succeeded for api.cluster.local", "meta": {"issuer": "Let's Encrypt", "days_valid": 90}},
            {"msg": "Security policy audit scan completed: Zero critical CVE vulnerabilities found", "meta": {"cve_count": 0}},
        ],
        "WARNING": [
            {"msg": "WAF rate limit trigger: Client {ip} exceeded 120 req/min threshold", "meta": {"client_ip": "192.168.1.105", "action": "throttled"}},
            {"msg": "Suspicious login attempt from novel geo-location: user_{user_id} from {ip}", "meta": {"country": "RO", "risk": "medium"}},
            {"msg": "Password brute-force mitigation activated: 5 failed attempts for user_{user_id}", "meta": {"attempts": 5, "lockout_sec": 300}},
        ],
        "ERROR": [
            {"msg": "WAF blocked malicious SQL injection pattern in query param 'user_id'", "meta": {"vector": "SQLi", "ip": "198.51.100.24", "blocked": True}},
            {"msg": "Distributed Denial of Service (DDoS) syn-flood attack mitigated at edge ingress", "meta": {"pps": 450000, "mitigation": "BGP_flowspec"}},
            {"msg": "Cryptographic signature verification failed on ingested webhook payload", "meta": {"signature_header": "X-Hub-Signature-256", "error": "InvalidHMAC"}},
        ]
    },
    "devops": {
        "INFO": [
            {"msg": "Kubernetes HorizontalPodAutoscaler scaled deployment to 8 replicas", "meta": {"hpa": "backend-api", "current_replicas": 8, "target_cpu": 70}},
            {"msg": "PostgreSQL streaming replication lag synchronized (<12ms)", "meta": {"lag_ms": 11.4, "primary": "pg-01", "replica": "pg-02"}},
            {"msg": "Cluster node health check passed. Heartbeat acknowledged.", "meta": {"cluster": "k8s-prod", "status": "healthy"}},
            {"msg": "Redis cluster memory defragmentation completed in 450ms", "meta": {"fragmentation_ratio": 1.08}},
        ],
        "WARNING": [
            {"msg": "High CPU utilization detected on worker node: 86.4%", "meta": {"metric": "cpu", "value": 86.4, "threshold": 80.0}},
            {"msg": "Database connection pool near capacity (18/20 active connections)", "meta": {"pool": "postgres", "active": 18, "max": 20}},
            {"msg": "Slow database query detected: SELECT * FROM orders took 2.4s", "meta": {"latency_ms": 2400, "table": "orders"}},
        ],
        "ERROR": [
            {"msg": "Database connection timeout connecting to replica host on port 5432", "meta": {"error": "TimeoutError", "port": 5432, "host": "db-replica-01"}},
            {"msg": "Container OOMKilled: Process exceeded cgroup memory limit of 512MiB", "meta": {"pod": "worker-queue-88", "exit_code": 137}},
            {"msg": "Failed to write payload to disk buffer: No space left on device (/dev/sda1)", "meta": {"disk": "/dev/sda1", "usage": "100%"}},
        ]
    },
    "iot": {
        "INFO": [
            {"msg": "Smart meter telemetry beacon ingested: 3.42 kWh reported", "meta": {"meter_id": "meter-{user_id}", "voltage": 230.1, "unit": "kWh"}},
            {"msg": "Edge IoT sensor node firmware update (OTA v2.4.1) successfully flashed", "meta": {"ota_version": "v2.4.1", "device_type": "ESP32"}},
            {"msg": "MQTT broker persistent session re-established for device_{user_id}", "meta": {"protocol": "MQTT_v5", "qos": 1}},
            {"msg": "Industrial actuator calibration acknowledged within tolerance (0.02mm)", "meta": {"actuator": "axis-Z", "delta": 0.02}},
        ],
        "WARNING": [
            {"msg": "Battery level low on remote telemetry probe: 14% remaining", "meta": {"battery_pct": 14, "solar_charging": False}},
            {"msg": "LoRaWAN gateway packet loss elevated: 8.2% frames dropped", "meta": {"rssi": -118, "snr": -4.2}},
            {"msg": "Ambient temperature warning in server rack 12: 38.6°C", "meta": {"temp_c": 38.6, "limit": 35.0}},
        ],
        "ERROR": [
            {"msg": "Industrial sensor communication offline: Modbus RTU CRC mismatch", "meta": {"bus": "RS485", "error": "CRCFailure"}},
            {"msg": "Edge gateway disconnected from cloud broker: TLS handshake timeout", "meta": {"gateway_id": "edge-gw-09", "error": "HandshakeTimeout"}},
            {"msg": "Critical water flow meter leakage anomaly triggered emergency shutoff", "meta": {"pressure_psi": 12.0, "valve": "closed"}},
        ]
    },
    "streaming": {
        "INFO": [
            {"msg": "Video transcoder chunk completed: 1080p60 H.264 / AAC encoding", "meta": {"segment_index": 42, "bitrate_kbps": 4500, "fps": 60}},
            {"msg": "CDN origin edge stream buffer filled (8.0s lookahead)", "meta": {"cdn": "Cloudflare", "cache_hit": True}},
            {"msg": "Real-time viewer engagement metric aggregated: 24,500 concurrent live streams", "meta": {"stream_id": "live-stream-{order_id}", "viewers": 24500}},
            {"msg": "Content personalization recommendation batch calculated in 18ms", "meta": {"recommendations_count": 20}},
        ],
        "WARNING": [
            {"msg": "Adaptive bitrate throttling: Client {ip} switched to 720p due to buffer underflow", "meta": {"dropped_frames": 14, "resolution": "720p"}},
            {"msg": "CDN edge cache miss ratio spiked to 28% for live segment manifest", "meta": {"miss_rate": 0.28}},
            {"msg": "Audio-video sync drift detected: 85ms skew on ingest stream", "meta": {"drift_ms": 85}},
        ],
        "ERROR": [
            {"msg": "HLS segmenter fatal error: Discontinuity in MPEG-TS audio stream", "meta": {"codec": "AAC", "error": "PTS_DTS_Discontinuity"}},
            {"msg": "CDN origin connection pool exhausted: 504 Gateway Timeout serving video stream", "meta": {"upstream_status": 504}},
            {"msg": "Live RTMP stream broadcast disconnected unexpectedly by ingest peer", "meta": {"stream_key": "live_***_key", "error": "PeerReset"}},
        ]
    }
}

DOMAIN_SOURCES: Dict[str, List[str]] = {
    "fintech": ["payment-service", "ledger-service", "fraud-detector", "billing-worker"],
    "healthcare": ["ehr-service", "patient-vitals-monitor", "telehealth-gateway", "lab-results-service"],
    "ecommerce": ["order-service", "inventory-service", "cart-service", "catalog-indexer"],
    "cybersecurity": ["auth-service", "waf-edge-proxy", "firewall-guard", "siem-collector"],
    "devops": ["db-replica-01", "k8s-autoscaler", "ingress-controller", "redis-cluster"],
    "iot": ["sensor-node-hub", "telemetry-ingest", "firmware-ota-manager", "edge-gateway"],
    "streaming": ["video-transcoder", "cdn-origin-stream", "hls-segmenter", "content-rec-engine"]
}

LEVEL_WEIGHTS = ["INFO"] * 6 + ["WARNING"] * 3 + ["ERROR"] * 2


def generate_single_log(source: Optional[str] = None, domain: Optional[str] = None) -> str:
    """Generate a single structured log line as a JSON string with enterprise domain."""
    # 1. Determine enterprise domain
    all_domains = list(DOMAIN_TEMPLATES.keys())
    if domain and domain.lower() in DOMAIN_TEMPLATES:
        selected_domain = domain.lower()
    else:
        selected_domain = random.choice(all_domains)

    # 2. Determine source service
    if source:
        selected_source = source
    else:
        selected_source = random.choice(DOMAIN_SOURCES[selected_domain])

    level = random.choice(LEVEL_WEIGHTS)
    template = random.choice(DOMAIN_TEMPLATES[selected_domain][level])

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
    metadata["domain"] = selected_domain
    metadata["source_host"] = source or selected_source
    metadata["pid"] = os.getpid()

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "domain": selected_domain,
        "source": selected_source,
        "message": message,
        "metadata": metadata
    }

    return json.dumps(log_entry)


def run_generator(
    source: str,
    output_path: Path,
    domain: Optional[str] = None,
    count: Optional[int] = None,
    interval: float = 1.0
) -> None:
    """Continuously append generated log events to the target file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    domain_label = f"[{domain}]" if domain else "[multi-domain]"
    logger.info(f"Starting multi-domain log generator {domain_label} for source '{source}' -> writing to '{output_path}'")

    generated = 0
    try:
        while True:
            log_line = generate_single_log(source=source, domain=domain)
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(log_line + "\n")
                f.flush()

            generated += 1
            logger.info(f"[{source}] Generated log #{generated}: {log_line[:85]}...")

            if count is not None and generated >= count:
                logger.info(f"Reached targeted log count ({count}). Generator stopped.")
                break

            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info(f"Log generator for '{source}' stopped by user.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic Multi-Domain Log Generator for Group9 Log Aggregator")
    parser.add_argument("--source", type=str, default=config.source, help="Source identifier (e.g. server-1, server-2)")
    parser.add_argument("--domain", type=str, default=None, choices=["all", "fintech", "healthcare", "ecommerce", "cybersecurity", "devops", "iot", "streaming"], help="Target enterprise domain")
    parser.add_argument("--output", type=str, default=str(config.log_file_path), help="Output log file path")
    parser.add_argument("--count", type=int, default=None, help="Number of logs to generate (omit for continuous)")
    parser.add_argument("--interval", type=float, default=1.0, help="Interval in seconds between logs")

    args = parser.parse_args()
    target_domain = None if args.domain == "all" else args.domain

    run_generator(
        source=args.source,
        output_path=Path(args.output),
        domain=target_domain,
        count=args.count,
        interval=args.interval
    )


if __name__ == "__main__":
    main()
