from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Query, status
from app.models import PartitionNodeInfo, RoutingStatusResponse
from app.services.router import distribution_engine

router = APIRouter()


@router.get(
    "/partitions",
    response_model=RoutingStatusResponse,
    summary="Get routing partitions status",
    description="Inspect logical index nodes/partitions on the consistent hash ring."
)
def get_partitions() -> RoutingStatusResponse:
    """Return configured partitions and their health status."""
    info_list = distribution_engine.get_partitions_info()
    active_nodes = [item["node_id"] for item in info_list if item["is_active"]]
    return RoutingStatusResponse(
        strategy="Consistent Hashing with Virtual Replicas (SHA-256)",
        active_partitions=active_nodes,
        total_partitions=len(info_list),
        partitions=[PartitionNodeInfo(**item) for item in info_list]
    )


@router.post(
    "/partitions/{node_id}/toggle",
    summary="Toggle logical partition active status",
    description="Simulate partition node failure or recovery for testing deterministic failover."
)
def toggle_partition(node_id: str) -> Dict[str, Any]:
    """Toggle the active state of a logical partition to test failover."""
    try:
        current_status = distribution_engine.nodes[node_id].is_active
        new_status = not current_status
        distribution_engine.set_node_status(node_id, new_status)
        return {
            "status": "success",
            "node_id": node_id,
            "is_active": new_status,
            "message": f"Partition '{node_id}' is now {'ACTIVE' if new_status else 'UNAVAILABLE'}."
        }
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partition '{node_id}' not found."
        )


@router.get(
    "/resolve",
    summary="Preview partition routing destination",
    description="Deterministically resolves which partition will receive logs from a given source key."
)
def resolve_route(source: str = Query(..., description="Source identifier to resolve")) -> Dict[str, str]:
    """Check where a given log source would be routed without ingesting."""
    assigned = distribution_engine.route(source)
    return {
        "source": source,
        "assigned_partition": assigned,
        "strategy": "Consistent Hashing"
    }
