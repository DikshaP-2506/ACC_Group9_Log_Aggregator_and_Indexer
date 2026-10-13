import bisect
import hashlib
import logging
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class DestinationUnavailableError(Exception):
    """Raised when no active routing partitions/nodes are available to receive logs."""
    pass


class LogicalPartitionNode:
    """Represents a logical destination partition node."""

    def __init__(self, node_id: str, is_active: bool = True) -> None:
        self.node_id = node_id
        self.is_active = is_active


class DistributionEngine:
    """
    Modular Distribution & Deterministic Routing Engine.
    
    Uses Consistent Hashing with virtual replication points to deterministically
    route log streams to logical partitions.
    
    DISTINCTION NOTE:
    -----------------
    In local development, these partitions represent logical routing destinations
    stored and indexed within our local Elasticsearch instance.
    In a distributed production environment (such as an AWS EC2 or Kubernetes cluster),
    these logical partitions map directly to distinct physical Elasticsearch shards,
    Kafka topic partitions, or independent cluster data nodes.
    """

    def __init__(
        self,
        nodes: Optional[List[str]] = None,
        virtual_replicas: Optional[int] = None
    ) -> None:
        self.virtual_replicas = virtual_replicas or settings.virtual_replicas
        self.nodes: Dict[str, LogicalPartitionNode] = {}
        self.ring: Dict[int, str] = {}
        self.sorted_ring_keys: List[int] = []

        initial_nodes = nodes or settings.get_routing_partitions()
        for node in initial_nodes:
            self.add_node(node)

    def _hash(self, key: str) -> int:
        """Stable 32-bit integer hash generated via SHA-256."""
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    def add_node(self, node_id: str) -> None:
        """Register a logical node and assign virtual replica tokens across the hash ring."""
        clean_id = node_id.strip()
        self.nodes[clean_id] = LogicalPartitionNode(clean_id, is_active=True)

        for i in range(self.virtual_replicas):
            vkey = f"{clean_id}#vn_{i}"
            token = self._hash(vkey)
            self.ring[token] = clean_id

        self.sorted_ring_keys = sorted(self.ring.keys())
        logger.info(f"Registered logical partition '{clean_id}' with {self.virtual_replicas} virtual replicas.")

    def set_node_status(self, node_id: str, is_active: bool) -> None:
        """Toggle active/inactive status for a partition to simulate node failure or recovery."""
        if node_id not in self.nodes:
            raise KeyError(f"Partition '{node_id}' does not exist.")
        self.nodes[node_id].is_active = is_active
        status_label = "ACTIVE" if is_active else "UNAVAILABLE"
        logger.warning(f"Logical partition '{node_id}' status updated to {status_label}.")

    def route(self, partition_key: str) -> str:
        """
        Deterministically map a routing key (e.g. source hostname) to an active partition.
        
        If the primary destination is unavailable, walks clockwise around the hash ring
        to fail over to the next healthy active destination.
        """
        if not self.sorted_ring_keys:
            raise RuntimeError("Hash ring is empty. No destinations configured.")

        active_nodes = {nid for nid, node in self.nodes.items() if node.is_active}
        if not active_nodes:
            logger.error("Routing failure: All logical partitions are marked unavailable.")
            raise DestinationUnavailableError("All logical routing partitions are currently unavailable.")

        key_token = self._hash(partition_key)

        # Locate position on the ring using binary search
        idx = bisect.bisect_right(self.sorted_ring_keys, key_token)
        if idx >= len(self.sorted_ring_keys):
            idx = 0

        # Find first active node along the ring clockwise
        total_tokens = len(self.sorted_ring_keys)
        for offset in range(total_tokens):
            token = self.sorted_ring_keys[(idx + offset) % total_tokens]
            candidate_node = self.ring[token]
            if candidate_node in active_nodes:
                if offset > 0:
                    logger.info(
                        f"Failover triggered for key '{partition_key}': Primary destination was offline; routed to '{candidate_node}'."
                    )
                return candidate_node

        raise DestinationUnavailableError("No healthy destination found for key: " + partition_key)

    def get_partitions_info(self) -> List[Dict[str, Any]]:
        """Return status for all configured partitions."""
        return [
            {"node_id": node_id, "is_active": node.is_active}
            for node_id, node in self.nodes.items()
        ]


# Singleton distribution engine instance
distribution_engine = DistributionEngine()
