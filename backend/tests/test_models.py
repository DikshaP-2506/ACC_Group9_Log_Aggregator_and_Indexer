from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from app.models import LogCreate, LogLevel


def test_log_create_valid_default_fields():
    log = LogCreate(
        level="INFO",
        message="User authentication successful",
        source="auth-service"
    )
    assert log.level == LogLevel.INFO
    assert log.message == "User authentication successful"
    assert log.source == "auth-service"
    assert isinstance(log.timestamp, datetime)
    assert log.id is None
    # Deterministic ID can be computed
    det_id = log.compute_deterministic_id()
    assert isinstance(det_id, str)
    assert len(det_id) == 16


def test_log_create_warn_normalization():
    log_warn = LogCreate(
        level="WARN",
        message="High memory usage",
        source="monitor-service"
    )
    assert log_warn.level == LogLevel.WARNING

    log_warning = LogCreate(
        level="warning",
        message="High memory usage",
        source="monitor-service"
    )
    assert log_warning.level == LogLevel.WARNING


def test_log_create_custom_id_preservation():
    custom_id = "custom-uuid-12345"
    log = LogCreate(
        id=custom_id,
        level="ERROR",
        message="Payment timeout",
        source="payment-service"
    )
    assert log.compute_deterministic_id() == custom_id


def test_deterministic_id_consistency():
    fixed_time = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    log1 = LogCreate(
        timestamp=fixed_time,
        level="INFO",
        message="Order created",
        source="order-service"
    )
    log2 = LogCreate(
        timestamp=fixed_time,
        level="INFO",
        message="Order created",
        source="order-service"
    )
    log3 = LogCreate(
        timestamp=fixed_time,
        level="INFO",
        message="Order cancelled",
        source="order-service"
    )

    # Identical content yields identical deterministic ID
    assert log1.compute_deterministic_id() == log2.compute_deterministic_id()
    # Different content yields different deterministic ID
    assert log1.compute_deterministic_id() != log3.compute_deterministic_id()


def test_invalid_log_level_rejected():
    with pytest.raises(ValidationError):
        LogCreate(
            level="UNKNOWN_LEVEL",
            message="Test message",
            source="test-service"
        )


def test_empty_message_and_source_rejected():
    with pytest.raises(ValidationError):
        LogCreate(
            level="INFO",
            message="",
            source="test-service"
        )

    with pytest.raises(ValidationError):
        LogCreate(
            level="INFO",
            message="Valid message",
            source="   "
        )


def test_log_create_domain_normalization():
    log = LogCreate(
        level="INFO",
        domain="  HEALTHCARE  ",
        message="Patient vitals normal",
        source="ehr-service"
    )
    assert log.domain == "healthcare"

    log_none = LogCreate(
        level="INFO",
        message="Patient vitals normal",
        source="ehr-service"
    )
    assert log_none.domain is None


def test_infer_domain_multi_domains():
    from app.models import infer_domain, LogEntry

    assert infer_domain("ehr-service", "Patient record update") == "healthcare"
    assert infer_domain("payment-service", "Payment processed") == "fintech"
    assert infer_domain("cart-service", "Checkout items") == "ecommerce"
    assert infer_domain("auth-service", "JWT token issued") == "cybersecurity"
    assert infer_domain("db-replica-01", "PostgreSQL replication") == "devops"
    assert infer_domain("sensor-node-hub", "Smart meter telemetry") == "iot"
    assert infer_domain("video-transcoder", "HLS stream segmented") == "streaming"
    assert infer_domain("custom-unknown-service", "Random message") == "general"


def test_log_entry_domain_default():
    from app.models import LogEntry
    entry = LogEntry(
        id="test-123",
        timestamp=datetime.now(timezone.utc),
        level="INFO",
        message="System boot",
        source="kernel"
    )
    assert entry.domain == "general"
