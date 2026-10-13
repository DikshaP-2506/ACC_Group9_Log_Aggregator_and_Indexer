import uuid
import pytest
from fastapi.testclient import TestClient
from app.elasticsearch_client import es_client
from app.main import app

client = TestClient(app)


@pytest.mark.skipif(not es_client.is_connected(), reason="Elasticsearch is not running locally")
def test_live_end_to_end_ingest_and_search():
    """Integration test verifying real ingestion, duplicate rejection, and search with Elasticsearch."""
    # Ensure index is ready
    es_client.ensure_index_exists()

    unique_keyword = f"order-{uuid.uuid4().hex[:8]}"
    test_id = f"test-log-{uuid.uuid4().hex[:10]}"

    payload = {
        "id": test_id,
        "level": "INFO",
        "message": f"Processing checkout for order {unique_keyword}",
        "source": "checkout-service",
        "metadata": {"amount": 149.99, "currency": "USD"}
    }

    # 1. Ingest log entry
    ingest_resp = client.post("/logs", json=payload)
    assert ingest_resp.status_code == 201
    ingest_data = ingest_resp.json()
    assert ingest_data["status"] == "success"
    assert ingest_data["id"] == test_id
    assert ingest_data["log"]["source"] == "checkout-service"

    # 2. Test duplicate rejection (attempt to ingest the same log ID again)
    dup_resp = client.post("/logs", json=payload)
    assert dup_resp.status_code == 409
    dup_data = dup_resp.json()
    assert dup_data["error"] == "Duplicate Log"
    assert test_id in dup_data["message"]

    # 3. Test searching by exact keyword
    search_resp = client.get(f"/logs/search?query={unique_keyword}&source=checkout-service")
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["total"] >= 1
    matching_log = next((l for l in search_data["logs"] if l["id"] == test_id), None)
    assert matching_log is not None
    assert unique_keyword in matching_log["message"]
    assert matching_log["level"] == "INFO"

    # 4. Test live health check
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"] == "healthy"
    assert health_data["elasticsearch"]["connected"] is True
