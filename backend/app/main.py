from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.elasticsearch_client import es_client
from app.routes import health, ingest, routing, search
from app.services.log_service import (
    DuplicateLogError,
    ElasticsearchUnavailableError,
    InvalidQueryError
)
from app.services.router import DestinationUnavailableError

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for application startup and shutdown."""
    logger.info(f"Starting {settings.app_name} on {settings.app_host}:{settings.app_port}...")
    try:
        if es_client.is_connected():
            logger.info("Connected to Elasticsearch. Verifying index schema...")
            es_client.ensure_index_exists()
        else:
            logger.warning(
                f"Elasticsearch is not reachable at {settings.elasticsearch_url}. "
                "The app will start, but log ingestion/search will be degraded until Elasticsearch is online."
            )
    except Exception as exc:
        logger.error(f"Error during Elasticsearch startup initialization: {exc}")

    yield

    logger.info("Shutting down application...")
    es_client.close()


def create_app() -> FastAPI:
    """Factory function for FastAPI application."""
    application = FastAPI(
        title="Group9 Distributed Log Aggregator & Indexer API",
        description="Scalable log ingestion, deduplication, and inverted-index search service built with FastAPI and Elasticsearch.",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Enable CORS with configurable origins
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request duration and access logging middleware
    @application.middleware("http")
    async def request_logger_middleware(request: Request, call_next):
        import time
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        client_host = request.client.host if request.client else "unknown"
        logger.info(
            f"{client_host} - \"{request.method} {request.url.path}\" "
            f"{response.status_code} ({duration_ms:.2f}ms)"
        )
        return response

    # Register custom exception handlers
    @application.exception_handler(DuplicateLogError)
    async def duplicate_log_handler(request: Request, exc: DuplicateLogError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "Duplicate Log", "message": str(exc)}
        )

    @application.exception_handler(ElasticsearchUnavailableError)
    async def es_unavailable_handler(request: Request, exc: ElasticsearchUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Service Unavailable", "message": str(exc)}
        )

    @application.exception_handler(InvalidQueryError)
    async def invalid_query_handler(request: Request, exc: InvalidQueryError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Bad Request", "message": str(exc)}
        )

    @application.exception_handler(DestinationUnavailableError)
    async def destination_unavailable_handler(request: Request, exc: DestinationUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Destination Unavailable", "message": str(exc)}
        )

    # Register API routers
    application.include_router(health.router, tags=["Health"])
    application.include_router(ingest.router, prefix="/logs", tags=["Logs"])
    application.include_router(search.router, prefix="/logs", tags=["Search"])
    application.include_router(routing.router, prefix="/routing", tags=["Distribution & Routing"])

    return application


app = create_app()
