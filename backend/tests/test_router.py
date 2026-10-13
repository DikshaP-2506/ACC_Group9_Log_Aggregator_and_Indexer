import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.router import (
    DestinationUnavailableError,
    DistributionEngine,
    distribution_engine
)

client = TestClient(app)


def test_routing_is_deterministic():
    """Verify that routing for the same source always produces the exact same destination partition."""
    engine = DistributionEngine(nodes=["partition-0", "partition-1", "partition-2"], virtual_replicas=50)

    # Calling route 100 times for server-1 must return the identical partition
    expected_p1 = engine.route("server-1")
    for _ in range(100):
        assert engine.route("server-1") == expected_p1

    expected_p2 = engine.route("server-2")
    for _ in range(100):
        assert engine.route("server-2") == expected_p2


def test_different_sources_distributed_across_partitions():
    """Verify that consistent hashing distributes multiple distinct sources across all configured partitions."""
    partitions = ["node-alpha", "node-beta", "node-gamma"]
    engine = DistributionEngine(nodes=partitions, virtual_replicas=100)

    hits = {p: 0 for p in partitions}
    for i in range(60):
        assigned = engine.route(f"microservice-node-{i}")
        hits[assigned] += 1

    # Every partition should receive at least some load
    for p in partitions:
        assert hits[p] > 0, f"Partition '{p}' received 0 routed keys"


def test_failover_when_partition_unavailable():
    """Verify that if a partition goes down, keys fail over to the next active partition on the hash ring."""
    engine = DistributionEngine(nodes=["part-A", "part-B", "part-C"], virtual_replicas=50)

    initial_dest = engine.route("payment-service")

    # Simulate node failure of the initial destination
    engine.set_node_status(initial_dest, is_active=False)

    # Route again: should fail over to another active partition
    failover_dest = engine.route("payment-service")
    assert failover_dest != initial_dest
    assert failover_dest in ["part-A", "part-B", "part-C"]
    assert engine.nodes[failover_dest].is_active is True

    # Restore node: key should return to primary destination
    engine.set_node_status(initial_dest, is_active=True)
    restored_dest = engine.route("payment-service")
    assert restored_dest == initial_dest


def test_all_destinations_unavailable_raises_error():
    """Verify DestinationUnavailableError is raised if all partitions are offline."""
    engine = DistributionEngine(nodes=["part-1", "part-2"], virtual_replicas=20)
    engine.set_node_status("part-1", False)
    engine.set_node_status("part-2", False)

    with pytest.raises(DestinationUnavailableError):
        engine.route("any-source")


def test_api_routing_status_and_resolve_endpoints():
    """Verify /routing/partitions and /routing/resolve endpoints."""
    # 1. Get partitions
    resp = client.get("/routing/partitions")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_partitions" in data
    assert data["total_partitions"] >= 3
    assert len(data["partitions"]) >= 3

    # 2. Resolve route preview
    resolve_resp = client.get("/routing/resolve?source=server-1")
    assert resolve_resp.status_code == 200
    res_data = resolve_resp.json()
    assert res_data["source"] == "server-1"
    assert "assigned_partition" in res_data
    assert res_data["assigned_partition"].startswith("partition-")


def test_api_ingest_records_assigned_partition():
    """Verify that ingesting a log records and returns the assigned partition."""
    mock_es = MagicMock()
    mock_es.create.return_value = {"result": "created"}

    with patch("app.services.log_service.es_client.client", mock_es):
        payload = {
            "level": "INFO",
            "message": "User session created",
            "source": "auth-service"
        }
        resp = client.post("/logs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "partition" in data
        assert data["partition"].startswith("partition-")
        assert data["log"]["partition"] == data["partition"]


def test_api_ingest_all_partitions_down_returns_503():
    """Verify that attempting ingestion when all partitions are down returns HTTP 503."""
    # Temporarily disable all partitions
    for nid in list(distribution_engine.nodes.keys()):
        distribution_engine.set_node_status(nid, False)

    try:
        payload = {
            "level": "INFO",
            "message": "Test during complete partition failure",
            "source": "server-offline-test"
        }
        resp = client.post("/logs", json=payload)
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"] == "Destination Unavailable"
    finally:
        # Restore all partitions
        for nid in list(distribution_engine.nodes.keys()):
            distribution_engine.set_node_status(nid, True)
