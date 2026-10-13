from fastapi import APIRouter, Response, status
from app.config import settings
from app.elasticsearch_client import es_client
from app.models import ElasticsearchHealth, HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application and Elasticsearch health check",
    description="Inspects FastAPI service status and active Elasticsearch cluster connectivity."
)
def get_health(response: Response) -> HealthResponse:
    """Check application health and Elasticsearch cluster connectivity."""
    connected = es_client.is_connected()

    if not connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="degraded",
            app=settings.app_name,
            environment=settings.app_env,
            elasticsearch=ElasticsearchHealth(
                connected=False,
                error="Cannot connect to Elasticsearch at " + settings.elasticsearch_url
            )
        )

    cluster_info = es_client.get_cluster_health()
    return HealthResponse(
        status="healthy",
        app=settings.app_name,
        environment=settings.app_env,
        elasticsearch=ElasticsearchHealth(
            connected=True,
            cluster_name=cluster_info.get("cluster_name"),
            cluster_status=cluster_info.get("status"),
            nodes_count=cluster_info.get("number_of_nodes")
        )
    )


@router.get(
    "/health/live",
    summary="Container Liveness Probe",
    description="Fast lightweight check confirming the FastAPI process is running."
)
def get_liveness() -> dict:
    """Fast check for container orchestration and ALB/NLB health checks."""
    return {"status": "live", "app": settings.app_name}


@router.get(
    "/health/ready",
    summary="Dependency Readiness Probe",
    description="Readiness check verifying backend connectivity to Elasticsearch."
)
def get_readiness(response: Response) -> dict:
    """Verifies that the backend is ready to accept and index log traffic."""
    if not es_client.is_connected():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "reason": "Elasticsearch connection offline",
            "elasticsearch_url": settings.elasticsearch_url
        }
    return {
        "status": "ready",
        "elasticsearch": "connected",
        "index": settings.log_index_name
    }

