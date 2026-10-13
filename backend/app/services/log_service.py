from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from elasticsearch import exceptions

from app.config import settings
from app.elasticsearch_client import es_client
from app.models import LogCreate, LogEntry, SearchResponse
from app.services.router import distribution_engine, DistributionEngine

logger = logging.getLogger(__name__)


class DuplicateLogError(Exception):
    """Raised when an ingested log ID already exists."""
    pass


class ElasticsearchUnavailableError(Exception):
    """Raised when Elasticsearch is unreachable."""
    pass


class InvalidQueryError(Exception):
    """Raised when search query filters are contradictory or invalid."""
    pass


class LogService:
    """Core business logic for log ingestion, deduplication, and search queries."""

    def __init__(self, client=None, router: Optional[DistributionEngine] = None) -> None:
        self._es = client or es_client
        self.router = router or distribution_engine

    def ingest_log(self, payload: LogCreate) -> LogEntry:
        """Validate, assign ID, prevent duplicates, route to partition, and index log into Elasticsearch."""
        log_id = payload.compute_deterministic_id()
        assigned_partition = payload.partition or self.router.route(payload.source)

        log_entry = LogEntry(
            id=log_id,
            timestamp=payload.timestamp,
            level=payload.level.value,
            message=payload.message,
            source=payload.source,
            partition=assigned_partition,
            metadata=payload.metadata or {}
        )

        doc = {
            "id": log_entry.id,
            "timestamp": log_entry.timestamp.isoformat(),
            "level": log_entry.level,
            "message": log_entry.message,
            "source": log_entry.source,
            "partition": log_entry.partition,
            "metadata": log_entry.metadata
        }

        try:
            # op_type='create' ensures atomic deduplication at the index level
            self._es.client.create(
                index=settings.log_index_name,
                id=log_id,
                document=doc,
                refresh="wait_for"
            )
            logger.info(f"Successfully indexed log ID '{log_id}' from source '{log_entry.source}'")
            return log_entry

        except exceptions.ConflictError:
            logger.warning(f"Duplicate log detected with ID: {log_id}")
            raise DuplicateLogError(f"Duplicate log rejected: entry with ID '{log_id}' already exists.")

        except exceptions.ConnectionError as exc:
            logger.error(f"Elasticsearch connection failed during ingestion: {exc}")
            raise ElasticsearchUnavailableError("Elasticsearch is currently unreachable.")

        except exceptions.ApiError as exc:
            logger.error(f"Elasticsearch API error during log ingestion: {exc}")
            raise

    def search_logs(
        self,
        query: Optional[str] = None,
        level: Optional[str] = None,
        source: Optional[str] = None,
        partition: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        limit: int = 20
    ) -> SearchResponse:
        """Search and filter logs using Elasticsearch inverted index and query DSL."""
        if start_time and end_time and start_time > end_time:
            raise InvalidQueryError("start_time cannot be greater than end_time.")

        must_clauses: List[Dict[str, Any]] = []
        filter_clauses: List[Dict[str, Any]] = []

        # 1. Full-text search across message field using inverted index
        if query and query.strip():
            must_clauses.append({
                "match": {
                    "message": {
                        "query": query.strip(),
                        "operator": "and"
                    }
                }
            })
        else:
            must_clauses.append({"match_all": {}})

        # 2. Exact match filter by severity level
        if level and level.strip():
            normalized_level = level.strip().upper()
            if normalized_level == "WARN":
                normalized_level = "WARNING"
            filter_clauses.append({"term": {"level": normalized_level}})

        # 3. Exact match filter by source service
        if source and source.strip():
            filter_clauses.append({"term": {"source": source.strip()}})

        # 4. Exact match filter by logical routing partition
        if partition and partition.strip():
            filter_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"partition": partition.strip()}},
                        {"term": {"partition.keyword": partition.strip()}}
                    ],
                    "minimum_should_match": 1
                }
            })

        # 5. Range filter by timestamp
        if start_time or end_time:
            time_range: Dict[str, str] = {}
            if start_time:
                time_range["gte"] = start_time.isoformat()
            if end_time:
                time_range["lte"] = end_time.isoformat()
            filter_clauses.append({"range": {"timestamp": time_range}})

        es_query = {
            "bool": {
                "must": must_clauses,
                "filter": filter_clauses
            }
        }

        from_offset = (page - 1) * limit

        try:
            response = self._es.client.search(
                index=settings.log_index_name,
                query=es_query,
                sort=[{"timestamp": {"order": "desc"}}],
                from_=from_offset,
                size=limit
            )

            total_hits = response.get("hits", {}).get("total", {})
            total_count = total_hits.get("value", 0) if isinstance(total_hits, dict) else int(total_hits)

            logs: List[LogEntry] = []
            for hit in response.get("hits", {}).get("hits", []):
                source_data = hit.get("_source", {})
                logs.append(LogEntry(
                    id=source_data.get("id", hit.get("_id")),
                    timestamp=source_data.get("timestamp"),
                    level=source_data.get("level", "INFO"),
                    message=source_data.get("message", ""),
                    source=source_data.get("source", "unknown"),
                    partition=source_data.get("partition", "partition-0"),
                    metadata=source_data.get("metadata", {})
                ))

            return SearchResponse(
                total=total_count,
                page=page,
                limit=limit,
                logs=logs
            )

        except exceptions.ConnectionError as exc:
            logger.error(f"Elasticsearch connection failed during search: {exc}")
            raise ElasticsearchUnavailableError("Elasticsearch is currently unreachable.")

        except exceptions.NotFoundError:
            # If the index has not received any logs yet, return empty list gracefully
            return SearchResponse(total=0, page=page, limit=limit, logs=[])

        except exceptions.ApiError as exc:
            logger.error(f"Elasticsearch API error during search: {exc}")
            raise

    def get_log_stats(self) -> Dict[str, Any]:
        """Aggregate log counts, levels, distinct sources, and partition distribution from Elasticsearch."""
        try:
            res = self._es.client.search(
                index=settings.log_index_name,
                size=0,
                aggs={
                    "by_level": {"terms": {"field": "level", "size": 10}},
                    "by_source": {"terms": {"field": "source", "size": 100}},
                    "by_partition": {"terms": {"field": "partition.keyword", "size": 50}}
                }
            )
            total = res.get("hits", {}).get("total", {})
            total_val = total.get("value", 0) if isinstance(total, dict) else int(total)
            aggs = res.get("aggregations", {})

            level_counts = {
                b["key"]: b["doc_count"]
                for b in aggs.get("by_level", {}).get("buckets", [])
            }
            sources = [
                b["key"]
                for b in aggs.get("by_source", {}).get("buckets", [])
            ]
            partition_counts = {
                b["key"]: b["doc_count"]
                for b in aggs.get("by_partition", {}).get("buckets", [])
            }

            error_count = level_counts.get("ERROR", 0) + level_counts.get("CRITICAL", 0)
            warning_count = level_counts.get("WARNING", 0) + level_counts.get("WARN", 0)
            info_count = level_counts.get("INFO", 0)
            debug_count = level_counts.get("DEBUG", 0)

            return {
                "total": total_val,
                "error_count": error_count,
                "warning_count": warning_count,
                "info_count": info_count,
                "debug_count": debug_count,
                "level_counts": level_counts,
                "sources": sources,
                "partition_counts": partition_counts
            }
        except exceptions.NotFoundError:
            return {
                "total": 0,
                "error_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "debug_count": 0,
                "level_counts": {},
                "sources": [],
                "partition_counts": {}
            }
        except exceptions.ConnectionError as exc:
            logger.error(f"Elasticsearch connection failed during stats aggregation: {exc}")
            raise ElasticsearchUnavailableError("Elasticsearch is currently unreachable.")
        except exceptions.ApiError as exc:
            logger.error(f"Elasticsearch API error during stats aggregation: {exc}")
            raise


log_service = LogService()

