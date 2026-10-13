import logging
from typing import Any, Dict, Optional
from elasticsearch import Elasticsearch, exceptions
from app.config import settings

logger = logging.getLogger(__name__)

INDEX_MAPPING: Dict[str, Any] = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "timestamp": {"type": "date"},
            "level": {"type": "keyword"},
            "source": {"type": "keyword"},
            "message": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                        "ignore_above": 256
                    }
                }
            },
            "partition": {"type": "keyword"},
            "metadata": {"type": "flattened"}
        }
    }
}


class ElasticsearchClientWrapper:
    """Manages connection, health checks, and index initialization for Elasticsearch."""

    def __init__(self, url: Optional[str] = None) -> None:
        self.url = url or settings.elasticsearch_url
        self._client: Optional[Elasticsearch] = None

    @property
    def client(self) -> Elasticsearch:
        """Lazy-loaded Elasticsearch client instance."""
        if self._client is None:
            self._client = Elasticsearch(
                hosts=[self.url],
                request_timeout=settings.request_timeout
            )
        return self._client

    @client.setter
    def client(self, val: Elasticsearch) -> None:
        self._client = val

    @client.deleter
    def client(self) -> None:
        self._client = None

    def is_connected(self) -> bool:
        """Check if Elasticsearch is reachable."""
        try:
            return bool(self.client.ping())
        except Exception as exc:
            logger.warning(f"Elasticsearch ping failed: {exc}")
            return False

    def get_cluster_health(self) -> Dict[str, Any]:
        """Fetch cluster health status."""
        try:
            return dict(self.client.cluster.health())
        except Exception as exc:
            logger.error(f"Failed to fetch Elasticsearch cluster health: {exc}")
            return {"status": "unreachable", "error": str(exc)}

    def ensure_index_exists(self, index_name: Optional[str] = None) -> None:
        """Create the log index with explicit mappings if it does not already exist."""
        idx = index_name or settings.log_index_name
        try:
            if not self.client.indices.exists(index=idx):
                self.client.indices.create(
                    index=idx,
                    mappings=INDEX_MAPPING["mappings"]
                )
                logger.info(f"Created Elasticsearch index '{idx}' with schema mappings.")
            else:
                logger.info(f"Elasticsearch index '{idx}' already exists.")
        except Exception as exc:
            logger.error(f"Error ensuring index '{idx}' exists: {exc}")
            raise

    def close(self) -> None:
        """Close connection pool."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:
                logger.warning(f"Error closing Elasticsearch client: {exc}")


es_client = ElasticsearchClientWrapper()
