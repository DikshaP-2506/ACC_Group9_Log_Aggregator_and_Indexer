from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    with patch("app.elasticsearch_client.es_client.ensure_index_exists"):
        yield TestClient(app)


def test_health_endpoint_healthy(client):
    """Verify /health returns 200 and cluster details when Elasticsearch is reachable."""
    with patch("app.elasticsearch_client.es_client.is_connected", return_value=True), \
         patch("app.elasticsearch_client.es_client.ensure_index_exists"), \
         patch("app.elasticsearch_client.es_client.get_cluster_health", return_value={
             "cluster_name": "docker-cluster",
             "status": "green",
             "number_of_nodes": 1
         }):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["elasticsearch"]["connected"] is True
        assert data["elasticsearch"]["cluster_name"] == "docker-cluster"


def test_health_endpoint_unreachable_es(client):
    """Verify /health returns 503 and degraded status when Elasticsearch is down."""
    with patch("app.elasticsearch_client.es_client.is_connected", return_value=False):
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["elasticsearch"]["connected"] is False
        assert "error" in data["elasticsearch"]


def test_health_live_probe(client):
    """Verify /health/live always returns 200 OK and live status."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "live"


def test_health_ready_probe_connected(client):
    """Verify /health/ready returns 200 OK when Elasticsearch is reachable."""
    with patch("app.elasticsearch_client.es_client.is_connected", return_value=True), \
         patch("app.elasticsearch_client.es_client.ensure_index_exists"):
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


def test_health_ready_probe_offline(client):
    """Verify /health/ready returns 503 when Elasticsearch is offline."""
    with patch("app.elasticsearch_client.es_client.is_connected", return_value=False):
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

