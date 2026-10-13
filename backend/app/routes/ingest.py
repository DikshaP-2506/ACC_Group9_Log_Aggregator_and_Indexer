from fastapi import APIRouter, status
from app.models import IngestResponse, LogCreate
from app.services.log_service import log_service

router = APIRouter()


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a new log entry",
    description="Validates incoming log, assigns or validates unique ID, prevents duplicates, and indexes into Elasticsearch."
)
def ingest_log(payload: LogCreate) -> IngestResponse:
    """Ingest a validated log record into Elasticsearch with duplicate prevention."""
    saved_entry = log_service.ingest_log(payload)
    return IngestResponse(
        status="success",
        message="Log entry ingested successfully",
        id=saved_entry.id,
        partition=saved_entry.partition,
        log=saved_entry
    )
