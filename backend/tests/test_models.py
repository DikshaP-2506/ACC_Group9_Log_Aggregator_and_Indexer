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
