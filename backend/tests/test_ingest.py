from unittest.mock import MagicMock, patch
from elasticsearch import exceptions
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_ingest_log_success():
    """Verify successful ingestion returns 201 Created with assigned log ID."""
    mock_es = MagicMock()
    mock_es.create.return_value = {"result": "created"}

    with patch("app.services.log_service.es_client.client", mock_es):
        payload = {
            "level": "INFO",
            "message": "User login succeeded",
            "source": "auth-service",
            "metadata": {"user_id": 42}
        }
        response = client.post("/logs", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert "id" in data
        assert data["log"]["message"] == "User login succeeded"
        assert data["log"]["level"] == "INFO"
        assert data["log"]["source"] == "auth-service"
        assert data["log"]["metadata"]["user_id"] == 42


def test_ingest_duplicate_log_rejected():
    """Verify duplicate ingestion is rejected with HTTP 409 Conflict."""
    mock_es = MagicMock()
    # Simulate Elasticsearch ConflictError when document with ID already exists
    mock_es.create.side_effect = exceptions.ConflictError(
        message="version conflict, document already exists",
        meta=MagicMock(),
        body={"error": "version conflict"}
    )

    with patch("app.services.log_service.es_client.client", mock_es):
        payload = {
            "id": "fixed-duplicate-id-123",
            "level": "ERROR",
            "message": "Database query timeout",
            "source": "order-service"
        }
        response = client.post("/logs", json=payload)
        assert response.status_code == 409
        data = response.json()
        assert data["error"] == "Duplicate Log"
        assert "already exists" in data["message"]


def test_ingest_invalid_payload_validation_error():
    """Verify invalid payloads (missing required fields) return HTTP 422."""
    payload = {
        "level": "INFO"
        # message and source missing
    }
    response = client.post("/logs", json=payload)
    assert response.status_code == 422


def test_ingest_es_unavailable():
    """Verify that when Elasticsearch is down, API returns 503."""
    mock_es = MagicMock()
    mock_es.create.side_effect = exceptions.ConnectionError("Connection refused")

    with patch("app.services.log_service.es_client.client", mock_es):
        payload = {
            "level": "WARN",
            "message": "High disk usage",
            "source": "system-monitor"
        }
        response = client.post("/logs", json=payload)
        assert response.status_code == 503
        data = response.json()
        assert data["error"] == "Service Unavailable"
