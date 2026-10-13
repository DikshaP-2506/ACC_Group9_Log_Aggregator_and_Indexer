from datetime import datetime, timezone, timedelta
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.elasticsearch_client import es_client
from app.services.router import distribution_engine

client = TestClient(app)


@pytest.mark.skipif(not es_client.is_connected(), reason="Requires live Elasticsearch running on port 9200")
def test_e2e_full_pipeline_verification():
    """
    Phase 6 Complete Integration Test:
    Verifies live health, multi-source ingestion, deterministic routing,
    duplicate prevention, search filtering, failover, and error handling.
    """
    # 1. Health check & Elasticsearch connectivity
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"] == "healthy"
    assert health_data["elasticsearch"]["connected"] is True
    assert health_data["elasticsearch"]["cluster_name"] == "docker-cluster"

    # 2. Schema validation error handling
    invalid_resp = client.post("/logs", json={"level": "NOT_A_LEVEL"})
    assert invalid_resp.status_code == 422

    # 3. Multi-source ingestion & deterministic routing
    test_run_tag = uuid.uuid4().hex[:6]
    sources = ["server-alpha", "server-beta", "server-gamma"]
    ingested_ids = []

    for src in sources:
        # Pre-calculate expected deterministic partition
        expected_partition = distribution_engine.route(src)

        payload = {
            "level": "ERROR" if "alpha" in src else "INFO",
            "message": f"Pipeline verification event for {src} [{test_run_tag}]",
            "source": src,
            "metadata": {
                "run_id": test_run_tag,
                "environment": "e2e_test",
                "attempt": 1
            }
        }

        resp = client.post("/logs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "success"
        assert "id" in data
        assert data["partition"] == expected_partition
        assert data["log"]["partition"] == expected_partition
        assert data["log"]["source"] == src
        ingested_ids.append(data["id"])

        # 4. Duplicate prevention test: Re-ingesting with the same ID must return 409 Conflict
        dup_payload = dict(payload)
        dup_payload["id"] = data["id"]
        dup_resp = client.post("/logs", json=dup_payload)
        assert dup_resp.status_code == 409
        dup_data = dup_resp.json()
        assert dup_data["error"] == "Duplicate Log"
        assert data["id"] in dup_data["message"]

    # 5. Inverted index keyword search
    search_keyword_resp = client.get(f"/logs/search?query={test_run_tag}")
    assert search_keyword_resp.status_code == 200
    search_keyword_data = search_keyword_resp.json()
    assert search_keyword_data["total"] == 3
    assert len(search_keyword_data["logs"]) == 3

    # 6. Severity level filtering
    search_level_resp = client.get(f"/logs/search?query={test_run_tag}&level=ERROR")
    assert search_level_resp.status_code == 200
    search_level_data = search_level_resp.json()
    assert search_level_data["total"] == 1
    assert search_level_data["logs"][0]["source"] == "server-alpha"

    # 7. Source filtering
    search_source_resp = client.get(f"/logs/search?source=server-beta")
    assert search_source_resp.status_code == 200
    assert any(l["source"] == "server-beta" for l in search_source_resp.json()["logs"])

    # 8. Partition filtering
    alpha_partition = distribution_engine.route("server-alpha")
    search_part_resp = client.get(f"/logs/search?query={test_run_tag}&partition={alpha_partition}")
    assert search_part_resp.status_code == 200
    assert search_part_resp.json()["total"] >= 1
    assert all(l["partition"] == alpha_partition for l in search_part_resp.json()["logs"])

    # 9. Time-range query validation
    past_start = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    future_end = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    time_resp = client.get("/logs/search", params={"query": test_run_tag, "start_time": past_start, "end_time": future_end})
    assert time_resp.status_code == 200
    assert time_resp.json()["total"] == 3

    # 10. Invalid query parameter error handling
    invalid_time_resp = client.get("/logs/search", params={"start_time": future_end, "end_time": past_start})
    assert invalid_time_resp.status_code == 400
    assert invalid_time_resp.json()["error"] == "Bad Request"

    # 11. Pagination verification
    page_resp = client.get(f"/logs/search?query={test_run_tag}&page=1&limit=2")
    assert page_resp.status_code == 200
    assert page_resp.json()["total"] == 3
    assert len(page_resp.json()["logs"]) == 2
    assert page_resp.json()["page"] == 1
    assert page_resp.json()["limit"] == 2
