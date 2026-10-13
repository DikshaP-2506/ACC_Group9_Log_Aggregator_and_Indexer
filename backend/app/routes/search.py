from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query
from app.models import SearchResponse
from app.services.log_service import log_service

router = APIRouter()


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search and filter indexed logs",
    description="Query logs using Elasticsearch inverted index with keyword search, severity filtering, source filtering, and timestamp range."
)
def search_logs(
    query: Optional[str] = Query(
        default=None,
        description="Full-text search keyword across log messages."
    ),
    level: Optional[str] = Query(
        default=None,
        description="Filter by log severity (e.g. INFO, WARN, WARNING, ERROR, DEBUG)."
    ),
    source: Optional[str] = Query(
        default=None,
        description="Filter by originating service name (e.g. auth-service, payment-service)."
    ),
    partition: Optional[str] = Query(
        default=None,
        description="Filter by logical routing partition (e.g. partition-0, partition-1)."
    ),
    start_time: Optional[datetime] = Query(
        default=None,
        description="Filter logs occurring at or after this ISO-8601 timestamp."
    ),
    end_time: Optional[datetime] = Query(
        default=None,
        description="Filter logs occurring at or before this ISO-8601 timestamp."
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Page number for pagination (1-indexed)."
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of logs per page (max 100)."
    )
) -> SearchResponse:
    """Execute search query against Elasticsearch."""
    return log_service.search_logs(
        query=query,
        level=level,
        source=source,
        partition=partition,
        start_time=start_time,
        end_time=end_time,
        page=page,
        limit=limit
    )


@router.get(
    "/stats",
    summary="Get aggregated log statistics and index metrics",
    description="Real-time aggregation of total logs, error/warning counts, distinct sources, and partition distribution."
)
def get_log_stats():
    """Execute aggregation query against Elasticsearch."""
    return log_service.get_log_stats()

