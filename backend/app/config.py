import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables or .env file."""

    # Application configuration
    app_name: str = "Group9-Log-Aggregator"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    # Elasticsearch configuration
    elasticsearch_url: str = "http://localhost:9200"
    log_index_name: str = "logs"
    request_timeout: int = 10

    # Distribution / Logical Routing configuration
    routing_partitions: str = "partition-0,partition-1,partition-2"
    virtual_replicas: int = 100

    # CORS configuration
    cors_origins: str = "*"

    # AWS & Archival configuration (ap-south-1 Mumbai)
    aws_region: str = "ap-south-1"
    s3_bucket_name: str = ""
    log_retention_days: int = 7

    def get_cors_origins(self) -> list[str]:
        """Parse comma-separated allowed origins or wildcard."""
        if not self.cors_origins or self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def get_routing_partitions(self) -> list[str]:
        return [p.strip() for p in self.routing_partitions.split(",") if p.strip()]

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

