from unittest.mock import MagicMock, patch
from elasticsearch import exceptions
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_search_logs_success():
    """Verify search endpoint builds query, queries ES, and parses hits properly."""
    mock_es = MagicMock()
    mock_es.search.return_value = {
        "hits": {
            "total": {"value": 1, "relation": "eq"},
            "hits": [
                {
                    "_id": "log-abc-123",
                    "_source": {
                        "id": "log-abc-123",
                        "timestamp": "2026-10-12T12:00:00Z",
                        "level": "ERROR",
                        "message": "Payment gateway timeout",
                        "source": "payment-service",
                        "metadata": {"order_id": 999}
                    }
                }
            ]
        }
    }

    with patch("app.services.log_service.es_client.client", mock_es):
        response = client.get("/logs/search?query=payment&level=ERROR&source=payment-service&page=1&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["limit"] == 10
        assert len(data["logs"]) == 1
        assert data["logs"][0]["id"] == "log-abc-123"
        assert data["logs"][0]["level"] == "ERROR"


def test_search_logs_invalid_time_range():
    """Verify start_time > end_time returns HTTP 400 Bad Request."""
    response = client.get("/logs/search?start_time=2026-10-12T15:00:00Z&end_time=2026-10-12T10:00:00Z")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "Bad Request"
    assert "start_time cannot be greater than end_time" in data["message"]


def test_search_logs_es_unavailable():
    """Verify ES connection failure returns 503 during search."""
    mock_es = MagicMock()
    mock_es.search.side_effect = exceptions.ConnectionError("Connection lost")

    with patch("app.services.log_service.es_client.client", mock_es):
        response = client.get("/logs/search?query=test")
        assert response.status_code == 503
        data = response.json()
        assert data["error"] == "Service Unavailable"


def test_get_log_stats_success():
    """Verify stats endpoint aggregates and returns counts, levels, sources, and partitions."""
    mock_es = MagicMock()
    mock_es.search.return_value = {
        "hits": {"total": {"value": 15}},
        "aggregations": {
            "by_level": {
                "buckets": [
                    {"key": "INFO", "doc_count": 10},
                    {"key": "ERROR", "doc_count": 5}
                ]
            },
            "by_source": {
                "buckets": [
                    {"key": "auth-service", "doc_count": 8},
                    {"key": "payment-service", "doc_count": 7}
                ]
            },
            "by_partition": {
                "buckets": [
                    {"key": "partition-0", "doc_count": 9},
                    {"key": "partition-1", "doc_count": 6}
                ]
            }
        }
    }

    with patch("app.services.log_service.es_client.client", mock_es):
        response = client.get("/logs/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 15
        assert data["error_count"] == 5
        assert data["info_count"] == 10
        assert "auth-service" in data["sources"]
        assert "payment-service" in data["sources"]
        assert data["partition_counts"]["partition-0"] == 9

