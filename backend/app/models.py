from datetime import datetime, timezone
from enum import Enum
import hashlib
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class LogLevel(str, Enum):
    """Allowed log severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Domain classification keyword rules for automatic inference
DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "fintech": [
        "payment", "stripe", "paypal", "ledger", "transaction", "billing",
        "fraud", "invoice", "refund", "card", "bank", "settlement", "wire"
    ],
    "healthcare": [
        "health", "ehr", "emr", "patient", "vitals", "clinic", "hospital", "telehealth",
        "lab", "fhir", "hl7", "icu", "doctor", "medical", "pharmacy", "hipaa"
    ],
    "ecommerce": [
        "order", "cart", "catalog", "inventory", "sku", "warehouse", "product", "shipping",
        "delivery", "stock", "fulfillment", "store", "customer", "checkout"
    ],
    "cybersecurity": [
        "auth", "login", "jwt", "waf", "firewall", "token", "session", "oauth",
        "ddos", "brute", "vulnerability", "malware", "siem", "ssl", "tls", "security"
    ],
    "iot": [
        "iot", "sensor", "telemetry", "firmware", "ota", "lora", "lorawan",
        "mqtt", "coap", "beacon", "meter", "actuator"
    ],
    "streaming": [
        "stream", "video", "audio", "transcode", "codec", "cdn", "hls", "dash",
        "bitrate", "fps", "buffer", "encoder", "segment"
    ],
    "devops": [
        "k8s", "kubernetes", "pod", "container", "docker", "replica", "database", "postgres",
        "mysql", "redis", "cpu", "memory", "disk", "cluster", "deploy", "ci-cd", "node"
    ]
}


def infer_domain(source: str, message: str = "") -> str:
    """Intelligently infer enterprise domain from service source name or message content."""
    src = source.lower()
    # 1. Match against source service name first
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in src for kw in keywords):
            return domain

    # 2. Match against message content with word boundaries
    text = f"{src} {message}".lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(kw)}\b", text) for kw in keywords):
            return domain
    return "general"


class LogCreate(BaseModel):
    """Schema for incoming log ingestion via POST /logs."""

    id: Optional[str] = Field(
        default=None,
        description="Optional unique identifier. If omitted, a deterministic content hash is generated."
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="ISO-8601 UTC timestamp of the log event."
    )
    level: LogLevel = Field(
        description="Severity level (DEBUG, INFO, WARN, WARNING, ERROR, CRITICAL)."
    )
    domain: Optional[str] = Field(
        default=None,
        description="Enterprise domain (e.g. fintech, healthcare, ecommerce, cybersecurity, devops, iot, streaming)."
    )
    message: str = Field(
        min_length=1,
        description="Log message content."
    )
    source: str = Field(
        min_length=1,
        description="Source identifier (e.g. auth-service, payment-service, ehr-service, order-service)."
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional structured metadata context."
    )

    @field_validator("level", mode="before")
    @classmethod
    def normalize_level(cls, v: Any) -> str:
        if isinstance(v, str):
            clean_str = v.strip().upper()
            if clean_str == "WARN":
                return "WARNING"
            return clean_str
        return v

    @field_validator("domain", mode="before")
    @classmethod
    def normalize_domain(cls, v: Any) -> Optional[str]:
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
        return None

    @field_validator("message", "source")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty or contain only whitespace.")
        return v.strip()

    partition: Optional[str] = Field(
        default=None,
        description="Optional target partition. If omitted, the distribution engine routes deterministically."
    )

    def compute_deterministic_id(self) -> str:
        """Assign or compute a unique deterministic identifier for duplicate prevention."""
        if self.id and self.id.strip():
            return self.id.strip()
        # Hash based on event signature: timestamp, level, source, message
        raw = f"{self.timestamp.isoformat()}|{self.level.value}|{self.source}|{self.message}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class LogEntry(BaseModel):
    """Log document stored and retrieved from Elasticsearch."""

    id: str
    timestamp: datetime
    level: str
    domain: str = Field(default="general", description="Categorized enterprise domain.")
    message: str
    source: str
    partition: str = Field(default="partition-0", description="Assigned logical routing partition.")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    """Response returned upon successful log ingestion."""

    status: str = "success"
    message: str = "Log entry ingested successfully"
    id: str
    partition: str
    log: LogEntry


class PartitionNodeInfo(BaseModel):
    """Logical partition health and status."""
    node_id: str
    is_active: bool


class RoutingStatusResponse(BaseModel):
    """Summary of the Distribution Engine state."""
    strategy: str = "Consistent Hashing with Virtual Replicas (SHA-256)"
    active_partitions: List[str]
    total_partitions: int
    partitions: List[PartitionNodeInfo]


class SearchResponse(BaseModel):
    """Paginated search response."""

    total: int
    page: int
    limit: int
    logs: List[LogEntry]


class ElasticsearchHealth(BaseModel):
    """Elasticsearch connectivity details."""

    connected: bool
    cluster_name: Optional[str] = None
    cluster_status: Optional[str] = None
    nodes_count: Optional[int] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Application health endpoint response."""

    status: str
    app: str
    environment: str
    elasticsearch: ElasticsearchHealth
